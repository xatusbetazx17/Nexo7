"""Build the pinned CPU diffusion CLI for the current OS; no AVX requirement."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
COMMIT=json.loads((ROOT/'nexo7/image_catalog.json').read_text())['engine_commit']


def main():
    target=ROOT/'nexo7/image_runtime';target.mkdir(exist_ok=True)
    executable=target/('sd-cli.exe' if os.name=='nt' else 'sd-cli')
    manifest=target/'manifest.json'
    if manifest.exists() and executable.exists():
        info=json.loads(manifest.read_text())
        if info.get('commit')==COMMIT and hashlib.sha256(executable.read_bytes()).hexdigest()==info.get('sha256'):
            return
    source=ROOT/'build/sd-source'
    if not (source/'.git').exists():
        source.parent.mkdir(exist_ok=True)
        subprocess.run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/leejet/stable-diffusion.cpp.git',str(source)],check=True)
    subprocess.run(['git','checkout',COMMIT],cwd=source,check=True)
    subprocess.run(['git','submodule','update','--init','--depth','1','ggml'],cwd=source,check=True)
    build=ROOT/'build/sd-cpu'
    flags=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POLICY_DEFAULT_CMP0091=NEW','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded','-DGGML_NATIVE=OFF','-DGGML_AVX=OFF','-DGGML_AVX2=OFF',
           '-DGGML_FMA=OFF','-DGGML_F16C=OFF','-DGGML_AVX512=OFF','-DGGML_BMI2=OFF','-DGGML_SSE42=OFF','-DGGML_OPENMP=OFF',
           '-DSD_WEBP=OFF','-DSD_WEBM=OFF','-DSD_SERVER_BUILD_FRONTEND=OFF',
           '-DSD_BUILD_SHARED_LIBS=OFF','-DSD_BUILD_SHARED_GGML_LIB=OFF','-DBUILD_SHARED_LIBS=OFF']
    if os.name!='nt':flags+=['-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc']
    subprocess.run(['cmake','-S',str(source),'-B',str(build),*flags],check=True)
    subprocess.run(['cmake','--build',str(build),'--config','Release','--target','sd-cli','--parallel','2'],check=True)
    matches=list((build/'bin').rglob(executable.name))
    if len(matches)!=1:raise RuntimeError('Expected exactly one built image executable')
    shutil.copy2(matches[0],executable)
    # Include upstream notices alongside the bundled static binary.
    notices=['LICENSE','ggml/LICENSE']
    for folder in ('thirdparty','ggml/src'):
        for path in (source/folder).rglob('*'):
            if path.is_file() and path.name.lower() in ('license','license.txt','license.md','copying','copyright'):
                notices.append(str(path.relative_to(source)))
    for name in notices:
        shutil.copyfile(source/name,target/(name.replace('/','-').replace('\\','-')+'.txt'))
    manifest.write_text(json.dumps({'commit':COMMIT,'sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
        'backend':'cpu','avx_required':False},indent=2)+'\n')
    subprocess.run([str(executable),'--help'],check=True,stdout=subprocess.DEVNULL)


if __name__=='__main__':main()
