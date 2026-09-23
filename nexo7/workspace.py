"""User-reviewed text artifacts. No generated code is automatically executed."""
from pathlib import Path
import re
import threading
import uuid

class Workspace:
    EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.html', '.css', '.js', '.py', '.sql'}

    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ValueError('Workspace cannot be a symbolic link')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = self.root.resolve()
        self.lock = threading.RLock()

    def list(self):
        with self.lock:
            return [{'id': p.name[:32], 'name': p.name[34:], 'bytes':p.stat().st_size}
                    for p in sorted(self.root.iterdir()) if p.is_file() and not p.is_symlink()
                    and re.fullmatch(r'[a-f0-9]{32}--[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', p.name)]

    def revision(self):
        import hashlib
        with self.lock:
            signature = [(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file() and not p.is_symlink()]
        return hashlib.sha256(repr(sorted(signature)).encode()).hexdigest()

    def create(self, name, content):
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name):
            raise ValueError('Use a simple filename without folders (maximum 80 characters)')
        if Path(name).suffix.lower() not in self.EXTENSIONS or name.endswith('.'):
            raise ValueError('Unsupported file extension')
        if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}:
            raise ValueError('Reserved filename')
        if not isinstance(content,str) or not 1 <= len(content.encode('utf-8')) <= 200000:
            raise ValueError('File content must contain 1 to 200000 UTF-8 bytes')
        with self.lock:
            entries=self.list()
            if len(entries)>=200 or sum(e['bytes'] for e in entries)+len(content.encode('utf-8'))>20_000_000:
                raise ValueError('Workspace quota reached: 200 files / 20 MB')
            identifier=uuid.uuid4().hex
            path=self.root/(identifier+'--'+name)
            with path.open('x',encoding='utf-8',newline='') as f:f.write(content)
            path.chmod(0o600)
            return {'id':identifier,'name':name,'bytes':path.stat().st_size}

    def read(self, identifier):
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9]{32}',identifier):
            raise ValueError('Invalid artifact identifier')
        with self.lock:
            matches=list(self.root.glob(identifier+'--*'))
            if len(matches)!=1 or matches[0].is_symlink() or not matches[0].is_file():
                raise ValueError('Artifact not found')
            p=matches[0]
            if p.stat().st_size>200000:raise ValueError('Artifact exceeds size limit')
            return {'id':identifier,'name':p.name[34:],'content':p.read_bytes().decode('utf-8')}

    def delete(self, identifier):
        with self.lock:
            item=self.read(identifier)
            (self.root/(identifier+'--'+item['name'])).unlink()
            return True

    def replace(self, identifier, expected_hash, content):
        """Atomic text replacement, conditional on the exact reviewed base content."""
        import hashlib
        import os
        if not isinstance(content,str) or not 0 <= len(content.encode('utf-8')) <= 200000:
            raise ValueError('Replacement content must contain at most 200000 UTF-8 bytes')
        with self.lock:
            item=self.read(identifier)
            if hashlib.sha256(item['content'].encode()).hexdigest()!=expected_hash:
                raise ValueError('File changed since review; reload and propose a new change')
            if sum(e['bytes'] for e in self.list())-len(item['content'].encode())+len(content.encode())>20_000_000:
                raise ValueError('Workspace quota reached')
            target=self.root/(identifier+'--'+item['name'])
            temporary=self.root/('.change-'+uuid.uuid4().hex)
            try:
                with temporary.open('x',encoding='utf-8',newline='') as stream:
                    stream.write(content);stream.flush();os.fsync(stream.fileno())
                temporary.chmod(0o600);os.replace(temporary,target)
            finally:
                temporary.unlink(missing_ok=True)
            return self.read(identifier)
