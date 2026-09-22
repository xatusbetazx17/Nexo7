import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid


class Store:
    """Single-user SQLite store. Retrieval uses FTS5; no embedding API calls."""
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA secure_delete=ON;
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,title TEXT,source TEXT,content TEXT,created REAL);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(doc_id UNINDEXED,title,content,tokenize='unicode61 remove_diacritics 2');
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        INSERT OR IGNORE INTO meta VALUES('revision','0');
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,session TEXT,role TEXT,content TEXT);
        CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,value TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, rating TEXT, created REAL);
        """)

    def close(self):
        with self.lock:
            self.db.close()

    def preferences(self):
        defaults = {"performance": "balanced", "response_language": "auto", "style": "concise",
                    "cpu_only": False, "auto_start": False}
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key='preferences'").fetchone()
        if row:
            defaults.update(json.loads(row[0]))
        return defaults

    def set_preferences(self, updates):
        from .config import Config
        with self.lock:
            if not isinstance(updates, dict) or set(updates) - set(self.preferences()):
                raise ValueError("Unknown preference")
            values = {**self.preferences(), **updates}
            if values["performance"] not in {"fast", "balanced", "quality"} or values["style"] not in {"concise", "detailed"}:
                raise ValueError("Invalid preference value")
            for key in ("cpu_only", "auto_start"):
                if type(values[key]) is not bool:
                    raise ValueError(key + " must be a boolean")
            Config(response_language=values["response_language"])
            with self.lock, self.db:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES('preferences',?)", (json.dumps(values),))
                self._changed()
            return values

    def record_feedback(self, question, answer, rating):
        if rating not in {"useful", "incorrect"}:
            raise ValueError("Invalid feedback rating")
        if not isinstance(question, str) or not 1 <= len(question) <= 8000 or not isinstance(answer, str) or not 1 <= len(answer) <= 30000:
            raise ValueError("Invalid feedback text")
        doc_id = None
        with self.lock:
            if rating == "useful":
                doc_id = self.add_document("Approved example: " + question[:120],
                                           "Question: " + question + "\nUser-approved answer: " + answer,
                                           "user-approved example; not independently verified")
            with self.db:
                self.db.execute("INSERT INTO feedback(rating,created) VALUES(?,?)", (rating, time.time()))
                self.db.execute("DELETE FROM feedback WHERE id NOT IN (SELECT id FROM feedback ORDER BY id DESC LIMIT 200)")
                self._changed()
        return {"document_id": doc_id, "rating": rating, "weight_training": False}

    def revision(self):
        with self.lock:
            return self.db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]

    def _changed(self):
        self.db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
        self.db.execute("DELETE FROM cache")

    def add_document(self, title, content, source="personal"):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise ValueError("Title must contain 1 to 160 characters")
        if not isinstance(content, str) or not 1 <= len(content.strip()) <= 200000:
            raise ValueError("Text must contain 1 to 200000 characters")
        if not isinstance(source, str) or len(source) > 500:
            raise ValueError("Source is too long")
        doc_id = uuid.uuid4().hex
        with self.lock, self.db:
            if self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] >= 200:
                raise ValueError("The 200-document limit was reached; remove a document first")
            self.db.execute("INSERT INTO documents VALUES(?,?,?,?,?)", (doc_id, title.strip(), source, content, time.time()))
            for offset in range(0, len(content), 1000):
                self.db.execute("INSERT INTO chunks VALUES(?,?,?)", (doc_id, title.strip(), content[offset:offset+1150]))
            self._changed()
        return doc_id

    def seed(self, path):
        with self.lock:
            if self.db.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
                return
            p = Path(path)
            if p.exists():
                self.add_document("Nexo starter guide", p.read_text(encoding="utf-8"), "knowledge/technology.md")
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES('seeded','1')")

    def documents(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT id,title,source,length(content) AS characters FROM documents ORDER BY created DESC")]

    def delete_document(self, doc_id):
        with self.lock, self.db:
            self.db.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            count = self.db.execute("DELETE FROM documents WHERE id=?", (doc_id,)).rowcount
            if count:
                self._changed()
            return bool(count)

    def search(self, query, limit=4):
        stop = {"que", "qué", "como", "cómo", "para", "con", "una", "las", "los", "del", "por", "the", "and", "what", "about", "quiero", "puedes", "buscar", "explica"}
        terms = [t for t in re.findall(r"\w+", str(query).lower()) if len(t) > 2 and t not in stop][:14]
        if not terms:
            return []
        match = " OR ".join('"' + term + '"' for term in terms)
        with self.lock:
            rows = self.db.execute("""SELECT chunks.rowid, chunks.doc_id, chunks.title, chunks.content,
                    documents.source FROM chunks JOIN documents ON documents.id=chunks.doc_id
                    WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?""", (match, min(max(int(limit), 1), 8))).fetchall()
        return [{"id": f"D{r['rowid']}", "document_id": r["doc_id"], "title": r["title"],
                 "text": r["content"], "source": r["source"]} for r in rows]

    def history(self, session, limit=8):
        if limit <= 0:
            return []
        with self.lock:
            rows = self.db.execute("SELECT role,content FROM messages WHERE session=? ORDER BY id DESC LIMIT ?", (session, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def save_turn(self, session, user, assistant):
        with self.lock, self.db:
            self.db.executemany("INSERT INTO messages(session,role,content) VALUES(?,?,?)",
                                [(session, "user", user), (session, "assistant", assistant)])
            self.db.execute("DELETE FROM messages WHERE session=? AND id NOT IN (SELECT id FROM messages WHERE session=? ORDER BY id DESC LIMIT 100)", (session, session))
            self.db.execute("DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT 10000)")

    def delete_history(self, session):
        with self.lock, self.db:
            self.db.execute("DELETE FROM messages WHERE session=?", (session,))
            self.db.execute("DELETE FROM cache")

    def get_cache(self, key):
        with self.lock:
            row = self.db.execute("SELECT value FROM cache WHERE key=? AND expires>?", (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def put_cache(self, key, value, ttl):
        if ttl <= 0:
            return
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, json.dumps(value, ensure_ascii=False), time.time()+ttl))
            self.db.execute("DELETE FROM cache WHERE expires<?", (time.time(),))
            self.db.execute("DELETE FROM cache WHERE key NOT IN (SELECT key FROM cache ORDER BY expires DESC LIMIT 256)")

    @staticmethod
    def cache_key(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
