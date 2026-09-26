"""Local identity, explicit built-in scopes and signed append-only action receipts.

This is an application permission boundary, not an OS sandbox. The device owner
can replace local files; signatures cannot defend against theft of the private key.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCOPES = {
    'math.use': 'Calculations and date tools',
    'memory.read': 'Read saved knowledge and history',
    'memory.write': 'Save or remove local knowledge and history',
    'workspace.read': 'Read and inspect workspace files',
    'workspace.write': 'Create, edit or remove workspace files',
    'creation.use': 'Create drawings, music and documents',
    'images.generate': 'Generate local AI images',
    'network.search': 'Search online when explicitly requested',
    'network.telegram': 'Use the optional Telegram bridge',
    'models.manage': 'Download, start or switch local models',
    'device.read': 'Check local hardware',
    'settings.write': 'Change application settings',
    'chat.use': 'Run chat or vision inference',
}
# Extensions must be reviewed and added here. Unknown action names fail closed.
ACTIONS = {
    'calculate': ('math.use',), 'date_difference': ('math.use',),
    'decimal_math': ('math.use',), 'scenario_calculation': ('math.use',),
    'search_memory': ('memory.read',), 'search_pubmed': ('network.search',),
    'web_lookup': ('network.search',), 'web_save': ('memory.write',),
    'read_workspace': ('workspace.read',), 'inspect_workspace': ('workspace.read',),
    'create_file': ('creation.use',), 'memory_read': ('memory.read',), 'memory_write': ('memory.write',),
    'workspace_write': ('workspace.write', 'workspace.read'), 'device_check': ('device.read',),
    'chat_inference': ('chat.use',), 'model_start': ('models.manage',),
    'image_generate': ('images.generate',), 'image_install': ('models.manage',),
    'telegram.read': ('network.telegram',), 'telegram.send': ('network.telegram',),
    'telegram.download': ('network.telegram',),
}
# Exact route templates: never log user IDs, filenames, query strings or payloads.
ROUTES = {}
def routes(method, paths, scopes=()):
    for path in paths.split():
        action = method + ' ' + path
        ROUTES[(method, path)] = action
        ACTIONS[action] = tuple(scopes)
routes('GET', '/api/status /api/setup /api/images /api/telegram /api/preferences')
routes('GET', '/api/web /api/learning /api/learning/community /api/documents /api/history', ('memory.read',))
routes('GET', '/api/tasks /api/artifacts /api/artifacts/*', ('workspace.read',))
routes('POST', '/api/chat /api/vision /api/relay', ('chat.use',))
routes('POST', '/api/math /api/scenario', ('math.use',))
routes('POST', '/api/creative /api/export/document', ('creation.use',))
routes('POST', '/api/images/start', ('images.generate',))
routes('POST', '/api/images/install /api/setup/start /api/setup/switch', ('models.manage',))
routes('POST', '/api/setup/check', ('device.read',))
routes('POST', '/api/telegram/chats /api/telegram/start', ('network.telegram',))
routes('POST', '/api/telegram/stop /api/images/cancel /api/setup/cancel /api/shutdown')
routes('POST', '/api/web/key /api/preferences', ('settings.write',))
routes('POST', '/api/learning/from-source /api/learning/import /api/feedback /api/documents', ('memory.write',))
routes('POST', '/api/learning/preview /api/learning/export /api/learning/contribute /api/contributions/prepare', ('memory.read',))
routes('POST', '/api/import', ('creation.use',))
routes('POST', '/api/inspect', ('workspace.read',))
routes('POST', '/api/artifacts /api/tasks /api/tasks/plan /api/tasks/*/run /api/tasks/*/edit /api/tasks/*/feedback /api/tasks/*/apply /api/tasks/*/rollback', ('workspace.write',))
routes('POST', '/api/tasks/*/cancel')
routes('DELETE', '/api/tasks/* /api/artifacts/*', ('workspace.write',))
routes('DELETE', '/api/web /api/web/* /api/learning-metrics /api/learning/* /api/documents/* /api/history/*', ('memory.write',))


def route_action(method, path):
    parts = path.split('/')
    exact = ROUTES.get((method, path))
    if exact:
        return exact
    if len(parts) >= 4:
        parts[3] = '*'
        return ROUTES.get((method, '/'.join(parts)))
    return None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def protect_key(raw, decrypt=False):
    """Windows keys are bound to the current login with DPAPI (no UI)."""
    if os.name != 'nt':
        if decrypt:
            if not raw.startswith(b'RAW1'):
                raise ValueError('This identity must be opened on its original platform')
            return raw[4:]
        return b'RAW1' + raw
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    if decrypt:
        if not raw.startswith(b'DPA1'):
            raise ValueError('This identity must be opened on its original platform')
        raw = raw[4:]
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, output = Blob(len(raw), buffer), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError('Windows could not protect or open the local Navi identity')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        value = ctypes.string_at(output.data, output.size)
        return value if decrypt else b'DPA1' + value
    finally:
        kernel.LocalFree(output.data)


class PermissionDenied(ValueError):
    pass


class Trust:
    def __init__(self, path=':memory:'):
        self.lock = threading.RLock()
        if str(path) != ':memory:':
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Create restrictively before SQLite opens it (no permissive-key window).
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            if os.name != 'nt':
                path.chmod(0o600)
        self.db = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS identity(id INTEGER PRIMARY KEY CHECK(id=1), secret BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS grants(scope TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, record TEXT NOT NULL, signature TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
        ''')
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                row = self.db.execute('SELECT secret FROM identity WHERE id=1').fetchone()
                if row is None:
                    if self.db.execute('SELECT 1 FROM audit LIMIT 1').fetchone():
                        raise ValueError('Local identity is missing; restore your trust database from backup')
                    key = Ed25519PrivateKey.generate()
                    self.db.execute('INSERT INTO identity VALUES(1,?)', (protect_key(key.private_bytes_raw()),))
                else:
                    key = Ed25519PrivateKey.from_private_bytes(protect_key(row[0], decrypt=True))
                self.key = key
                self.public_key = key.public_key().public_bytes_raw().hex()
                self.navi_id = 'nexo:' + hashlib.sha256(bytes.fromhex(self.public_key)).hexdigest()
                if row is None:
                    self._append('identity.create', 'completed', uuid.uuid4().hex)
            self.verify()
        except Exception:
            self.db.close()
            raise

    def close(self):
        with self.lock:
            self.db.close()

    def identity(self):
        return {'id': self.navi_id, 'public_key': self.public_key, 'algorithm': 'Ed25519'}

    def _append(self, action, outcome, call_id):
        last = self.db.execute('SELECT seq,digest FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        event = {'seq': last[0]+1 if last else 1, 'previous': last[1] if last else '0'*64,
                 'time': datetime.now(timezone.utc).isoformat(), 'navi_id': self.navi_id,
                 'action': action, 'outcome': outcome, 'call_id': call_id}
        raw = canonical(event)
        signature = self.key.sign(raw).hex()
        digest = hashlib.sha256(raw + bytes.fromhex(signature)).hexdigest()
        self.db.execute('INSERT INTO audit VALUES(?,?,?,?)', (event['seq'], raw.decode(), signature, digest))

    def policy_key(self):
        with self.lock:
            return list(self.db.execute('SELECT scope,enabled FROM grants ORDER BY scope'))

    def allowed(self, action):
        with self.lock:
            grants = dict(self.db.execute('SELECT scope,enabled FROM grants'))
            return action in ACTIONS and all(grants.get(s, True) for s in ACTIONS[action])

    def begin(self, action):
        call = uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            allowed = self.allowed(action)
            # Never put untrusted model-generated names in the audit log.
            self._append(action if action in ACTIONS else 'unknown_action', 'started' if allowed else 'denied', call)
        if not allowed:
            raise PermissionDenied('Tool not authorized: this action is disabled or undeclared. Review Settings → Trust and permissions.')
        return call

    def finish(self, action, call, outcome='completed'):
        if action not in ACTIONS or outcome not in {'completed', 'failed', 'accepted', 'cancelled'}:
            raise ValueError('Invalid audit receipt')
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self._append(action, outcome, call)

    @contextmanager
    def action(self, name):
        call = self.begin(name)
        try:
            yield
        except BaseException:
            self.finish(name, call, 'failed')
            raise
        else:
            self.finish(name, call)

    def run(self, name, fn, *args, **kwargs):
        with self.action(name):
            return fn(*args, **kwargs)

    def set_scope(self, scope, enabled):
        if scope not in SCOPES or type(enabled) is not bool:
            raise ValueError('Choose a declared permission and a boolean setting')
        # Only the authenticated owner UI calls this; tools cannot grant scopes.
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self._append('permission.' + scope, 'enabled' if enabled else 'disabled', uuid.uuid4().hex)
            self.db.execute('INSERT OR REPLACE INTO grants VALUES(?,?)', (scope, int(enabled)))

    def snapshot(self):
        with self.lock:
            grants = dict(self.db.execute('SELECT scope,enabled FROM grants'))
            return {'identity': self.identity(), 'permissions': [
                {'scope': s, 'label': label, 'enabled': bool(grants.get(s, True))}
                for s, label in SCOPES.items()],
                'actions': [{'name': name, 'scopes': list(scopes)} for name, scopes in sorted(ACTIONS.items())]}

    def records(self, before=None, limit=50):
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError('Invalid audit cursor')
        with self.lock:
            rows = self.db.execute('SELECT record,signature,digest FROM audit WHERE seq < ? ORDER BY seq DESC LIMIT ?',
                (before or 2**63-1, min(100, max(1, limit)))).fetchall()
        entries = [{**json.loads(r[0]), 'signature': r[1], 'digest': r[2]} for r in rows]
        return {'entries': entries, 'next_before': entries[-1]['seq'] if entries else None}

    def verify(self):
        previous = '0'*64
        count = 0
        with self.lock:
            for seq, raw, signature, digest in self.db.execute('SELECT seq,record,signature,digest FROM audit ORDER BY seq'):
                try:
                    record = json.loads(raw)
                    if not (seq == count+1 and record['seq'] == seq
                            and record['previous'] == previous and record['navi_id'] == self.navi_id
                            and canonical(record).decode() == raw):
                        raise ValueError('Invalid audit chain')
                    self.key.public_key().verify(bytes.fromhex(signature), raw.encode())
                    if hashlib.sha256(raw.encode()+bytes.fromhex(signature)).hexdigest() != digest:
                        raise ValueError('Invalid audit digest')
                except Exception as exc:
                    raise ValueError('Audit integrity check failed; restore the trust database from a trusted backup') from exc
                previous, count = digest, count+1
        return {'verified': True, 'records': count, 'head': previous}


def guarded(action):
    """Guard a store-backed service method, including direct non-HTTP callers."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(self, *args, **kwargs):
            trust = getattr(self, "store", self).trust
            return trust.run(action, fn, self, *args, **kwargs)
        return wrapped
    return decorate
