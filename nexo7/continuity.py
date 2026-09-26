"""Bounded, user-controlled episodic memory and an explicitly fictional persona."""
from datetime import datetime, timezone
import json
import math
import re
import time
import uuid

DEFAULT = {'name': 'Nexo', 'user_name': '', 'mood': 'calm', 'onboarded': False,
           'remember_activity': False, 'retention_days': 90, 'active_days': []}
MOODS = ('calm', 'curious', 'focused', 'cheerful')


def persona_valid(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ValueError('Unknown persona field')
    p = {**DEFAULT, **value}
    for field in ('name', 'user_name'):
        text = p[field]
        if not isinstance(text, str) or len(text) > 40 or (field == 'name' and not text.strip()):
            raise ValueError('Names must contain 1–40 characters')
        if any(not (c.isalnum() or c in " -_.'’") for c in text):
            raise ValueError('Use letters, numbers, spaces or simple punctuation in names')
        p[field] = text.strip()
    if p['mood'] not in MOODS or type(p['retention_days']) is not int or not 1 <= p['retention_days'] <= 365:
        raise ValueError('Choose a mood and memory retention of 1–365 days')
    if any(type(p[k]) is not bool for k in ('onboarded', 'remember_activity')):
        raise ValueError('Persona switches must be boolean')
    if not isinstance(p['active_days'], list) or len(p['active_days']) > 366:
        raise ValueError('Invalid continuity history')
    for day in p['active_days']:
        if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise ValueError('Invalid continuity date')
        datetime.strptime(day, '%Y-%m-%d')
    p['active_days'] = sorted(set(p['active_days']))
    return p


def episode_valid(value):
    if not isinstance(value, dict): raise ValueError('Invalid memory')
    item = dict(value)
    for key, limit in (('what', 800), ('people', 160)):
        if not isinstance(item.get(key), str) or len(item[key]) > limit or (key == 'what' and not item[key].strip()):
            raise ValueError('Memory needs a short description and optional people')
        item[key] = item[key].strip()
    for key in ('occurred', 'expires'):
        n = item.get(key)
        if type(n) not in (float, int) or not math.isfinite(n) or not 0 < n < 32503680000:
            raise ValueError('Invalid memory date')
    if item.get('kind') not in ('experience', 'decision', 'milestone', 'activity'):
        raise ValueError('Invalid memory category')
    if type(item.get('pinned')) is not bool: raise ValueError('Invalid keep setting')
    count = item.get('occurrences', 1)
    if type(count) is not int or not 1 <= count <= 1000000: raise ValueError('Invalid occurrence count')
    return {k: item[k] for k in ('what', 'people', 'occurred', 'expires', 'kind', 'pinned')} | {'occurrences': count}


class Continuity:
    def __init__(self, store):
        self.store = store
        with store.lock, store.db:
            store.db.execute('''CREATE TABLE IF NOT EXISTS episodes(
                id TEXT PRIMARY KEY, what TEXT NOT NULL, people TEXT NOT NULL, occurred REAL NOT NULL,
                expires REAL NOT NULL, kind TEXT NOT NULL, pinned INTEGER NOT NULL, occurrences INTEGER NOT NULL)''')
            store.db.execute('CREATE INDEX IF NOT EXISTS episodes_expiry ON episodes(expires)')

    def persona(self):
        with self.store.lock:
            row = self.store.db.execute("SELECT value FROM meta WHERE key='persona'").fetchone()
        return persona_valid(json.loads(row[0]) if row else {})

    def _save_persona(self, p):
        self.store.db.execute("INSERT OR REPLACE INTO meta VALUES('persona',?)", (json.dumps(p),))
        self.store._changed()

    def configure(self, updates):
        if not isinstance(updates, dict) or 'active_days' in updates:
            raise ValueError('Continuity history is maintained by the application')
        with self.store.trust.action('persona.configure'), self.store.lock, self.store.db:
            p = persona_valid({**self.persona(), **updates})
            if p['remember_activity'] and not self.store.trust.allowed('memory_write'):
                raise ValueError('Enable memory write permission before remembering activity')
            self._save_persona(p)
            return self.summary()

    def summary(self):
        p = self.persona()
        days = len(p['active_days'])
        return {**p, 'familiarity': 'familiar' if days >= 14 else 'getting acquainted' if days >= 3 else 'new companion',
                'days_together': days, 'simulated_persona': True}

    def completed_chat(self, private=False, now=None):
        # Counters only, never automatically copy messages, people or inferred emotions.
        if private or not self.store.trust.allowed('memory_write') or not self.persona()['remember_activity']: return
        now = time.time() if now is None else now
        with self.store.trust.action('memory_write'), self.store.lock, self.store.db:
            p = self.persona()
            day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
            if day not in p['active_days']:
                p['active_days'] = sorted(set(p['active_days'] + [day]))[-366:]
                self._save_persona(p)
                if self.store.db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] < 500:
                    self._insert(episode_valid({'what': 'Had a conversation', 'people': '', 'occurred': now,
                        'expires': now + p['retention_days'] * 86400, 'kind': 'activity', 'pinned': False}))

    def _insert(self, item, identifier=None):
        identifier = identifier or uuid.uuid4().hex
        self.store.db.execute('INSERT OR REPLACE INTO episodes VALUES(?,?,?,?,?,?,?,?)',
            (identifier, item['what'], item['people'], item['occurred'], item['expires'], item['kind'], int(item['pinned']), item['occurrences']))
        self.store._changed()
        return identifier

    def save(self, body):
        now = time.time()
        if not isinstance(body, dict): raise ValueError('Invalid memory')
        identifier = body.get('id')
        with self.store.trust.action('memory_write'), self.store.lock, self.store.db:
            if identifier and not self.store.db.execute('SELECT 1 FROM episodes WHERE id=?', (identifier,)).fetchone():
                raise ValueError('Memory not found')
            if not identifier and self.store.db.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] >= 500:
                raise ValueError('Memory limit: 500. Review and clear old entries first.')
            item = episode_valid({'what': body.get('what'), 'people': body.get('people', ''),
                'occurred': body.get('occurred', now), 'expires': body.get('expires', now + self.persona()['retention_days'] * 86400),
                'kind': body.get('kind', 'experience'), 'pinned': body.get('pinned', False), 'occurrences': body.get('occurrences', 1)})
            return {'id': self._insert(item, identifier), **item}

    def list(self, include_expired=False, now=None):
        now = time.time() if now is None else now
        with self.store.trust.action('memory_read'), self.store.lock:
            rows = self.store.db.execute('SELECT * FROM episodes WHERE (? OR pinned=1 OR expires>?) ORDER BY occurred DESC LIMIT 500',
                                        (include_expired, now)).fetchall()
        return [{**dict(r), 'pinned': bool(r['pinned'])} for r in rows]

    def forget(self, identifier):
        with self.store.trust.action('memory_write'), self.store.lock, self.store.db:
            if identifier == 'all':
                self.store.db.execute('DELETE FROM episodes')
                p = self.persona(); p['active_days'] = []; self._save_persona(p)
            else: self.store.db.execute('DELETE FROM episodes WHERE id=?', (identifier,))
            self.store._changed()
        return {'removed': True}

    def maintain(self, apply=False, now=None):
        now = time.time() if now is None else now
        with self.store.trust.action('memory_write' if apply else 'memory_read'), self.store.lock, self.store.db:
            rows = [dict(r) for r in self.store.db.execute('SELECT * FROM episodes ORDER BY occurred DESC')]
            expired = [r['id'] for r in rows if not r['pinned'] and r['expires'] <= now]
            groups = {}; duplicates = []
            for r in rows:
                if r['id'] in expired or r['pinned'] or r['occurred'] > now - 30 * 86400: continue
                key = (r['what'], r['people'], r['kind'], int(r['occurred'] // 86400))
                if key in groups: duplicates.append((r, groups[key]))
                else: groups[key] = r
            if apply:
                for identifier in expired: self.store.db.execute('DELETE FROM episodes WHERE id=?', (identifier,))
                for r, target in duplicates:
                    self.store.db.execute('UPDATE episodes SET occurrences=MIN(1000000,occurrences+?),expires=MIN(expires,?) WHERE id=?',
                        (r['occurrences'], r['expires'], target['id']))
                    self.store.db.execute('DELETE FROM episodes WHERE id=?', (r['id'],))
                # Familiarity counts have the same retention policy as automatic activity.
                p = self.persona(); cutoff = datetime.fromtimestamp(now - p['retention_days'] * 86400, timezone.utc).date().isoformat()
                p['active_days'] = [d for d in p['active_days'] if d >= cutoff]
                self._save_persona(p)
            return {'expired': len(expired), 'duplicates': len(duplicates), 'applied': apply,
                    'notice': 'Only unpinned episodes expire. Exact duplicates older than 30 days on the same day are consolidated. Saved Library notes are unchanged.'}

    def matching(self, text):
        if not self.store.trust.allowed('memory_read'): return []
        words = set(re.findall(r'\w{3,}', text.casefold()))
        matches = []
        for r in self.list():
            score = len(words & set(re.findall(r'\w{3,}', (r['what'] + ' ' + r['people']).casefold())))
            if score and r['kind'] != 'activity': matches.append((score, r))
        matches.sort(key=lambda x: (x[0], x[1]['occurred']), reverse=True)
        return [{'id': 'E' + str(i + 1), 'title': 'User-reviewed experience', 'source': 'personal episode; not independently verified',
                 'text': json.dumps({k: r[k] for k in ('what', 'people', 'occurred', 'kind')}, ensure_ascii=False)}
                for i, (_, r) in enumerate(matches[:2])]
