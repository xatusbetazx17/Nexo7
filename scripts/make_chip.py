"""Author a declarative chip using your own Ed25519 key (never commit the key)."""
import argparse,io,json,zipfile,hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from nexo7.chips import OPERATIONS
from nexo7.trust import canonical

def package(key,name,operation,author='Nexo project',version='1.0.0'):
    manifest={'format':'nexo-chip-v1','name':name,'version':version,'author':author,
              'permissions':list(OPERATIONS[operation]),'entry_point':'program.json'}
    program={'operation':operation}
    proof={'public_key':key.public_key().public_bytes_raw().hex(),
           'signature':key.sign(canonical({'manifest':manifest,'program':program})).hex()}
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in [('manifest.json',manifest),('program.json',program),('signature.json',proof)]:z.writestr(name,canonical(data))
    return out.getvalue()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--key',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--operation',choices=OPERATIONS,required=True);p.add_argument('--author',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_bytes(package(Ed25519PrivateKey.from_private_bytes(a.key.read_bytes()),a.name,a.operation,a.author))
