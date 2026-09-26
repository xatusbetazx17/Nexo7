"""Passphrase-unlocked local secrets. No plaintext keys or OAuth tokens on disk."""
import base64
import json
import os
from pathlib import Path
import secrets
import threading
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITERATIONS = 600_000
AAD = b'nexo-vault-v1'


def derive(phrase, salt):
    if not isinstance(phrase, str) or not 16 <= len(phrase) <= 512:
        raise ValueError('Use a passphrase of 16–512 characters; several random words work well')
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(phrase.encode())


def b64(raw): return base64.b64encode(raw).decode('ascii')

def unb64(value): return base64.b64decode(value, validate=True)


def atomic_private(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


class Vault:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock();self._key=None;self._data=None;self._salt=None
    def status(self):
        with self.lock:return {'exists':self.path.exists(),'unlocked':self._key is not None}
    def unlock(self,phrase):
        with self.lock:
            if self.path.exists():
                if self.path.stat().st_size>100_000:raise ValueError('Invalid vault file')
                try:
                    envelope=json.loads(self.path.read_bytes())
                    if envelope['format']!='nexo-vault-v1':raise ValueError()
                    salt=unb64(envelope['salt']);key=derive(phrase,salt)
                    data=json.loads(AESGCM(key).decrypt(unb64(envelope['nonce']),unb64(envelope['ciphertext']),AAD))
                    if not isinstance(data,dict):raise ValueError()
                except Exception:raise ValueError('Could not unlock the vault. Check your passphrase and vault backup.') from None
            else:
                salt=secrets.token_bytes(16);key=derive(phrase,salt);data={}
            self._salt,self._key,self._data=salt,key,data
            self._save()
    def _save(self):
        if self._key is None:raise ValueError('Unlock the connector vault first')
        nonce=secrets.token_bytes(12)
        cipher=AESGCM(self._key).encrypt(nonce,json.dumps(self._data).encode(),AAD)
        atomic_private(self.path,json.dumps({'format':'nexo-vault-v1','salt':b64(self._salt),'nonce':b64(nonce),'ciphertext':b64(cipher)}).encode())
    def get(self,name):
        with self.lock:
            if self._key is None:raise ValueError('Unlock the connector vault first')
            return json.loads(json.dumps(self._data.get(name)))
    def set(self,name,value):
        with self.lock:
            if self._key is None:raise ValueError('Unlock the connector vault first')
            before=dict(self._data)
            if value is None:self._data.pop(name,None)
            else:self._data[name]=value
            try:self._save()
            except Exception:self._data=before;raise
    def lock_now(self):
        with self.lock:self._key=None;self._data=None;self._salt=None
