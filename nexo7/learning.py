"""Bounded, reviewable learning data. Never trains weights or executes imported text."""
import hashlib
import json
import re
import time
import unicodedata
import uuid
from urllib.parse import urlencode

FORMAT = "nexo-learning-v1"
MAX_ENTRIES = 100
MAX_BYTES = 400_000
FIELDS = {"question", "answer", "language", "kind"}


def validate_entry(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("An example requires question, answer, language and kind only")
    result = dict(value)
    for key, limit in (("question", 2000), ("answer", 8000)):
        if not isinstance(result[key], str) or not 1 <= len(result[key].strip()) <= limit:
            raise ValueError(f"{key} must contain 1 to {limit} characters")
        result[key] = result[key].strip()
    if not isinstance(result["language"], str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", result["language"]):
        raise ValueError("Specify a language code, for example es or en")
    if result["kind"] not in ("correction", "procedure"):
        raise ValueError("kind must be correction or procedure")
    return result


def fingerprint(entry):
    return hashlib.sha256(json.dumps(entry, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_pack(pack):
    if not isinstance(pack, dict) or set(pack) != {"format", "entries"} or pack["format"] != FORMAT:
        raise ValueError("Unsupported learning pack; expected nexo-learning-v1")
    if len(json.dumps(pack, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("Learning pack exceeds 400 KB")
    entries = pack["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("A pack must contain 1 to 100 examples")
    normalized = [validate_entry(entry) for entry in entries]
    if len({fingerprint(e) for e in normalized}) != len(normalized):
        raise ValueError("Duplicate examples in pack")
    return normalized


def privacy_warnings(entry):
    text = entry["question"] + "\n" + entry["answer"]
    checks = [
        (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "Possible email address"),
        (r"(?i)(?:gh[pousr]_|github_pat_|sk-)[A-Za-z0-9_-]{10,}", "Possible access token"),
        (r"(?i)(password|contrase[ñn]a|api.?key|secret|bearer)\s*[:= ]", "Possible credential"),
        (r"\b\d{3}[- .]\d{2}[- .]\d{4}\b|(?:\+?\d[ ()-]*){10,}", "Possible personal number"),
        (r"(?i)(?:[A-Z]:\\Users\\|/home/|/Users/)", "Possible personal file path"),
    ]
    return [label for pattern, label in checks if re.search(pattern, text)]


def contribution(entry, consent):
    entry = validate_entry(entry)
    if consent is not True:
        raise ValueError("Explicit consent to publish this exact example is required")
    warnings = privacy_warnings(entry)
    if warnings:
        raise ValueError("Remove possible personal data before sharing: " + "; ".join(warnings))
    # Public GitHub draft only: no credentials, telemetry or background upload.
    payload = json.dumps({"format": FORMAT, "entries": [entry]}, ensure_ascii=False, indent=2)
    body = ("I reviewed this example and consent to publishing it publicly under CC0-1.0. "
            "I have the right to share it; it contains no private or third-party confidential data.\n\n"
            "Proposed learning example (not independently verified):\n\n" + payload)
    url = "https://github.com/xatusbetazx17/Nexo7/issues/new?" + urlencode({
        "title": "Learning contribution (" + entry["language"] + ")", "body": body})
    if len(url) > 7500:
        raise ValueError("Example is too long for a GitHub draft. Shorten it or export a pack for manual review.")
    return {"url": url, "body": body, "uploaded": False}


class Learning:
    def __init__(self, store):
        self.store = store
        with store.lock, store.db:
            store.db.executescript("""
            CREATE TABLE IF NOT EXISTS learning(
                id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL,
                question TEXT NOT NULL, answer TEXT NOT NULL, language TEXT NOT NULL,
                kind TEXT NOT NULL, document_id TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS learning_provenance(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS learning_metrics(
                bucket TEXT PRIMARY KEY, count INTEGER NOT NULL,
                elapsed_ms REAL NOT NULL, tokens INTEGER NOT NULL);
            """)

    def entries(self):
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT l.id,l.question,l.answer,l.language,l.kind,p.metadata FROM learning l "
                "JOIN documents d ON d.id=l.document_id LEFT JOIN learning_provenance p ON p.id=l.id ORDER BY l.created DESC").fetchall()
            entries = []
            for row in rows:
                item = dict(row); metadata = item.pop('metadata')
                if metadata:
                    item['provenance'] = json.loads(metadata)
                    item['expired'] = item['provenance']['expires'] <= time.time()
                entries.append(item)
            return entries

    def import_pack(self, pack, consent):
        if consent is not True:
            raise ValueError("Review and approve the pack before importing")
        entries = validate_pack(pack)
        s = self.store
        with s.lock, s.db:
            # A deleted knowledge document must not leave an invisible learning entry.
            s.db.execute("DELETE FROM learning WHERE document_id NOT IN (SELECT id FROM documents)")
            known = {r[0] for r in s.db.execute("SELECT fingerprint FROM learning")}
            fresh = [e for e in entries if fingerprint(e) not in known]
            if len(known) + len(fresh) > MAX_ENTRIES:
                raise ValueError("The 100-example limit was reached; delete an example first")
            if s.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] + len(fresh) > 200:
                raise ValueError("Not enough space in the 200-document library")
            for e in fresh:
                ident, doc = uuid.uuid4().hex, uuid.uuid4().hex
                title = "Reviewed " + e["kind"] + ": " + e["question"][:120]
                content = ("User-reviewed reference, not independently verified. Language: " + e["language"]
                           + "\nQuestion: " + e["question"] + "\nAnswer: " + e["answer"])
                s.db.execute("INSERT INTO documents VALUES(?,?,?,?,?)", (doc, title, "local learning; user reviewed; not independently verified", content, time.time()))
                summary = "User-reviewed reference, not independently verified.\nQuestion: " + e["question"][:250] + "\nAnswer: " + e["answer"][:1100]
                s.db.execute("INSERT INTO chunks VALUES(?,?,?)", (doc, title, summary))
                for offset in range(0, len(content), 1000):
                    s.db.execute("INSERT INTO chunks VALUES(?,?,?)", (doc, title, content[offset:offset+1150]))
                s.db.execute("INSERT INTO learning VALUES(?,?,?,?,?,?,?,?)", (ident, fingerprint(e), e["question"], e["answer"], e["language"], e["kind"], doc, time.time()))
            if fresh:
                s._changed()
        return {"added": len(fresh), "duplicates": len(entries)-len(fresh), "weight_training": False}

    def export(self, ids):
        if not isinstance(ids, list) or not ids or len(ids) > MAX_ENTRIES or any(not isinstance(x, str) for x in ids):
            raise ValueError("Select 1 to 100 examples to export")
        available = {e["id"]: e for e in self.entries()}
        if len(set(ids)) != len(ids) or any(i not in available for i in ids):
            raise ValueError("Unknown or duplicate example selection")
        if any(available[i].get("provenance") for i in ids):
            raise ValueError("Source-linked notes cannot use this pack format because it would discard provenance and expiry. Use the original-note GitHub contribution workflow instead.")
        pack = {"format": FORMAT, "entries": [{k: available[i][k] for k in FIELDS} for i in ids]}
        validate_pack(pack)
        return pack

    def delete(self, ident):
        s = self.store
        with s.lock, s.db:
            row = s.db.execute("SELECT document_id FROM learning WHERE id=?", (ident,)).fetchone()
            if not row:
                return False
            s.db.execute("DELETE FROM chunks WHERE doc_id=?", (row[0],))
            s.db.execute("DELETE FROM documents WHERE id=?", (row[0],))
            s.db.execute("DELETE FROM learning_provenance WHERE id=?", (ident,))
            s.db.execute("DELETE FROM learning WHERE id=?", (ident,))
            s._changed()
            return True

    def matching(self, question, limit=2):
        # Match Unicode characters, including languages with no space-delimited words.
        # Conservative lexical retrieval, not semantic embeddings or a direct-answer shortcut.
        def grams(text):
            text = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
            return {text[i:i+3] for i in range(max(1, len(text)-2))}
        query = grams(question)
        scored = []
        with self.store.lock:
            rows = self.store.db.execute("SELECT l.*,c.rowid AS chunk_id,c.title,c.content FROM learning l "
                "JOIN chunks c ON c.doc_id=l.document_id WHERE c.rowid=(SELECT MIN(rowid) FROM chunks WHERE doc_id=l.document_id)").fetchall()
        entries = self.entries()
        stale = {e['id'] for e in entries if e.get('expired')}
        provenance = {e['id']:e['provenance'] for e in entries if e.get('provenance')}
        for row in rows:
            if row['id'] in stale:
                continue
            candidate = grams(row["question"])
            score = len(query & candidate) / max(1, len(query | candidate))
            if score >= 0.3:
                scored.append((score, {"id": f"D{row['chunk_id']}", "document_id": row["document_id"],
                    "title": row["title"], "text": row["content"], "source": "user-reviewed learning; not independently verified", **({"provenance": provenance[row["id"]]} if row["id"] in provenance else {})}))
        return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]

    def record_metrics(self, stats, status, private):
        if private or not self.store.preferences()["local_metrics"]:
            return
        bucket = "cache" if stats["cache_hit"] else "tools" if not stats["model_calls"] else "model"
        bucket += ":" + ("completed" if status == "completed" else "other")
        with self.store.lock, self.store.db:
            self.store.db.execute("INSERT INTO learning_metrics VALUES(?,1,?,?) ON CONFLICT(bucket) DO UPDATE SET "
                "count=count+1,elapsed_ms=elapsed_ms+excluded.elapsed_ms,tokens=tokens+excluded.tokens",
                (bucket, stats["elapsed_ms"], stats["input_tokens"] + stats["output_tokens"]))

    def metrics(self):
        with self.store.lock:
            return [dict(r) for r in self.store.db.execute("SELECT * FROM learning_metrics ORDER BY bucket")]

    def clear_metrics(self):
        with self.store.lock, self.store.db:
            self.store.db.execute("DELETE FROM learning_metrics")
