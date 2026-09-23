"""Assemble a Windows x86-64 preview using official embeddable CPython and a C launcher.

Unlike PyInstaller, this launcher can be cross-compiled. Native Windows execution
must be validated separately before claiming runtime compatibility.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.14.7'
PYTHON_SHA256 = 'd297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15'
PYTHON_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'


def main():
    build = ROOT / 'build/windows-portable'
    stage = build / 'Nexo7-0.9.0-windows-x86_64-preview'
    stage.mkdir(parents=True, exist_ok=True)
    archive = build / f'python-{PYTHON_VERSION}-embed-amd64.zip'
    if not archive.exists():
        with urlopen(PYTHON_URL, timeout=60) as response:
            data = response.read(40_000_001)
        if len(data) > 40_000_000:
            raise ValueError('Unexpected Python archive size')
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise ValueError('Python archive checksum mismatch')
    runtime = stage / 'runtime'
    runtime.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as file:
        for info in file.infolist():
            destination = (runtime / info.filename).resolve()
            if not destination.is_relative_to(runtime.resolve()):
                raise ValueError('Unsafe runtime archive path')
        file.extractall(runtime)
    (runtime / 'python314._pth').write_text('python314.zip\n.\n../app\n', encoding='utf-8')
    app = stage / 'app'
    app.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'nexo7', app / 'nexo7', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ROOT / 'desktop_entry.py', app / 'desktop_entry.py')
    import pypdf
    shutil.copytree(Path(pypdf.__file__).parent, app/'pypdf', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    subprocess.run([sys.executable, '-m', 'ziglang', 'cc', '-target', 'x86_64-windows-gnu',
                    str(ROOT / 'packaging/windows_launcher.c'), '-o', str(stage / 'Nexo7.exe'),
                    '-municode', '-Wl,--subsystem,windows', '-O2', '-s', '-luser32'], check=True)
    data = (stage / 'Nexo7.exe').read_bytes()
    assert data[:2] == b'MZ'
    pe = struct.unpack_from('<I', data, 60)[0]
    assert data[pe:pe+4] == b'PE\0\0' and struct.unpack_from('<H', data, pe+4)[0] == 0x8664
    assert struct.unpack_from('<H', data, pe+24+68)[0] == 2
    for source, target in [('LICENSE','LICENSE.txt'), ('docs/QUICKSTART.md','START-HERE.md'), ('THIRD-PARTY.md','THIRD-PARTY.md')]:
        shutil.copy2(ROOT / source, stage / target)
    (stage / 'PREVIEW-NOTICE.txt').write_text('Windows preview assembled on Linux with an x86-64 PE launcher and official embeddable CPython.\nIt has NOT been executed on Windows in this environment. Native validation is still required.\nExtract every file, then open Nexo7.exe. Native engine and model downloads are separate prerequisites; no Docker needed.\n', encoding='utf-8')
    import ziglang
    licenses = stage / 'licenses'
    licenses.mkdir(exist_ok=True)
    compiler = Path(ziglang.__file__).parent
    shutil.copy2(compiler / 'lib/libc/mingw/COPYING', licenses / 'MINGW-COPYING.txt')
    shutil.copy2(compiler / 'LICENSE', licenses / 'ZIG-LICENSE.txt')
    manifest = {'python_url': PYTHON_URL, 'python_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'launcher':'Zig 0.15.2 targeting x86_64-windows-gnu', 'native_windows_execution_tested':False,
                'files':{str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(stage.rglob('*')) if p.is_file()}}
    (stage / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    output = ROOT / 'release'
    output.mkdir(exist_ok=True)
    result = output / (stage.name + '.zip')
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as file:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                file.write(path, path.relative_to(stage.parent))
    checksum = hashlib.sha256(result.read_bytes()).hexdigest()
    (output / (result.name+'.sha256')).write_text(checksum+'  '+result.name+'\n')
    print(json.dumps({'file':str(result),'bytes':result.stat().st_size,'sha256':checksum,
                      'native_windows_execution_tested':False}, indent=2))


if __name__ == '__main__':
    main()
