"""Signed declarative chips. No Python, JS, shell, imports or arbitrary networking."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .trust import canonical
from .vault import atomic_private

OPERATIONS={'math.solve':('math.use',),'memory.reviewed-save':('memory.read','memory.write'),
            'security.email-check':()}
ROOT=Path(__file__).parent/'chips'


def inspect(raw):
    if not isinstance(raw,bytes) or len(raw)>100_000:raise ValueError('Chip ZIP limit: 100 KB')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names=archive.namelist()
            if sorted(names)!=['manifest.json','program.json','signature.json']:raise ValueError('A chip must contain only manifest.json, program.json and signature.json')
            if any(i.file_size>20_000 or i.flag_bits&1 for i in archive.infolist()):raise ValueError('Oversized or encrypted chip entry')
            manifest=json.loads(archive.read('manifest.json'));program=json.loads(archive.read('program.json'));proof=json.loads(archive.read('signature.json'))
        if set(manifest)!={'format','name','version','author','permissions','entry_point'} or manifest['format']!='nexo-chip-v1':raise ValueError('Unsupported chip manifest')
        for field in ('name','version','author'):
            if not isinstance(manifest[field],str) or not 1<=len(manifest[field])<=80:raise ValueError('Invalid chip metadata')
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,49}',manifest['name']):raise ValueError('Invalid chip name')
        if manifest['entry_point']!='program.json' or not isinstance(program,dict) or set(program)!={'operation'}:raise ValueError('Only declarative operation chips are supported')
        operation=program['operation']
        if operation not in OPERATIONS or manifest['permissions']!=list(OPERATIONS[operation]):raise ValueError('Undeclared chip operation or permissions')
        public=bytes.fromhex(proof['public_key']);signature=bytes.fromhex(proof['signature'])
        Ed25519PublicKey.from_public_bytes(public).verify(signature,canonical({'manifest':manifest,'program':program}))
        return {'manifest':manifest,'program':program,'fingerprint':hashlib.sha256(public).hexdigest(),'sha256':hashlib.sha256(raw).hexdigest()}
    except (KeyError,TypeError,zipfile.BadZipFile,json.JSONDecodeError,UnicodeError):raise ValueError('Invalid signed chip') from None
    except Exception as exc:
        if isinstance(exc,ValueError):raise
        raise ValueError('Chip signature verification failed') from None


def email_check(message):
    if not isinstance(message,dict):raise ValueError('An email record is required')
    text=' '.join(str(message.get(k,''))[:2000] for k in ('subject','from','snippet')).casefold()
    flags=[]
    if re.search(r'urgent|urgente|act now|immediately|inmediatamente|account.{0,20}(suspend|closed)|cuenta.{0,20}suspend',text):flags.append('Pressure to act urgently')
    if re.search(r'password|contrase[nñ]a|verification code|c[oó]digo de verificaci[oó]n|gift card|tarjeta de regalo|seed phrase|wire transfer',text):flags.append('Request involving credentials, codes or unusual payment')
    if 'xn--' in text or re.search(r'https?://(?:\d{1,3}\.){3}\d{1,3}',text):flags.append('Unusual link hostname')
    names=message.get('attachments',[])
    if not isinstance(names,list) or len(names)>30:raise ValueError('Invalid attachment metadata')
    for name in names:
        if re.search(r'\.(exe|scr|js|vbs|bat|cmd|ps1|msi|lnk|iso|img|jar|docm|xlsm|zip|rar|7z)$',str(name),re.I):
            flags.append('Attachment needs manual inspection: '+str(name)[:180])
    return {'flags':flags,'verdict':'review' if flags else 'no_heuristic_flags',
        'notice':'Heuristic warning only. No attachment was opened or scanned; absence of flags does not prove an email is safe.'}


class Chips:
    def __init__(self,root,store,web):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.store,self.web=store,web
        self.pins=json.loads((ROOT/'catalog.json').read_text())
    def list(self):
        result=[]
        for path,builtin in [(p,True) for p in ROOT.glob('*.nexochip')]+[(p,False) for p in self.root.glob('*.nexochip')]:
            try:
                raw=path.read_bytes();item=inspect(raw)
                if builtin and self.pins.get(path.name)!=item['sha256']:raise ValueError('Builtin chip integrity failed')
                result.append({**item,'builtin':builtin})
            except Exception:result.append({'manifest':{'name':path.stem},'invalid':True,'builtin':builtin})
        return result
    def preview(self,encoded):return inspect(base64.b64decode(encoded,validate=True))
    def install(self,body):
        with self.store.trust.action('chips.install'):
            if body.get('consent') is not True:raise ValueError('Review and approve the chip publisher and permissions first')
            raw=base64.b64decode(body.get('data',''),validate=True);item=inspect(raw)
            if body.get('fingerprint')!=item['fingerprint']:raise ValueError('Confirm the exact reviewed publisher fingerprint')
            name=item['manifest']['name']
            if (ROOT/(name+'.nexochip')).exists():raise ValueError('Built-in chips cannot be replaced')
            if len(list(self.root.glob('*.nexochip')))>=30 and not (self.root/(name+'.nexochip')).exists():raise ValueError('Chip limit: 30')
            atomic_private(self.root/(name+'.nexochip'),raw)
            return item
    def remove(self,name):
        if not isinstance(name,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,49}',name):raise ValueError('Invalid chip name')
        with self.store.trust.action('chips.install'):(self.root/(name+'.nexochip')).unlink(missing_ok=True)
        return {'removed':True}
    def run(self,name,payload):
        if not isinstance(name,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,49}',name):raise ValueError('Invalid chip name')
        builtin=(ROOT/(name+'.nexochip')).is_file()
        path=(ROOT if builtin else self.root)/(name+'.nexochip')
        if not path.is_file():raise ValueError('Chip not installed')
        raw=path.read_bytes();item=inspect(raw)
        if builtin and self.pins.get(path.name)!=item['sha256']:raise ValueError('Builtin chip integrity failed')
        if len(json.dumps(payload))>120_000:raise ValueError('Chip input is too large')
        action={'math.solve':'chip.math','memory.reviewed-save':'chip.memory','security.email-check':'chip.security'}[item['program']['operation']]
        def execute():
            with self.store.trust.action(action):
                operation=item['program']['operation']
                if operation=='math.solve':
                    from .advanced_math import solve
                    return solve(payload)
                if operation=='memory.reviewed-save':
                    from .reviewed_sources import admit
                    from .learning import Learning
                    return admit(Learning(self.store),self.web,payload)
                return email_check(payload)
        return execute() if builtin else self.store.trust.run('chips.run',execute)
