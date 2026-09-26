"""Build pinned baseline and AVX2 diffusion engines with a baseline CPU probe."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
COMMIT=json.loads((ROOT/'nexo7/image_catalog.json').read_text())['engine_commit']
SUFFIX='.exe' if os.name=='nt' else ''

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    target=ROOT/'nexo7/image_runtime';target.mkdir(exist_ok=True)
    manifest=target/'manifest.json'
    old=json.loads(manifest.read_text()) if manifest.exists() else {}
    def verified(entry):
        return isinstance(entry,dict) and (target/entry.get('filename','missing')).is_file() and sha(target/entry['filename'])==entry.get('sha256')
    if old.get('commit')==COMMIT and old.get('format')==2 and all(verified(old.get('variants',{}).get(k)) for k in ('baseline','avx2')) and verified(old.get('probe')) and (target/'third-party-sources.tar.gz').exists():return
    baseline=target/('sd-cli'+SUFFIX)
    reuse_baseline=old.get('commit')==COMMIT and baseline.is_file() and sha(baseline)==old.get('sha256')
    source=ROOT/'build/sd-source'
    if not (source/'.git').exists():
        source.parent.mkdir(exist_ok=True)
        subprocess.run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/leejet/stable-diffusion.cpp.git',str(source)],check=True)
    subprocess.run(['git','checkout',COMMIT],cwd=source,check=True)
    subprocess.run(['git','submodule','update','--init','--depth','1','ggml'],cwd=source,check=True)
    common=['-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POLICY_DEFAULT_CMP0091=NEW','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded']
    if os.name!='nt':common+=['-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc']
    variants={}
    for variant in ('baseline','avx2'):
        executable=baseline if variant=='baseline' else target/('sd-cli-avx2'+SUFFIX)
        if not (variant=='baseline' and reuse_baseline):
            build=ROOT/('build/sd-'+variant)
            enabled='ON' if variant=='avx2' else 'OFF'
            flags=[*common,'-DGGML_NATIVE=OFF','-DGGML_AVX512=OFF','-DGGML_BMI2=OFF','-DGGML_OPENMP=OFF',
                   '-DSD_WEBP=OFF','-DSD_WEBM=OFF','-DSD_SERVER_BUILD_FRONTEND=OFF',
                   '-DSD_BUILD_SHARED_LIBS=OFF','-DSD_BUILD_SHARED_GGML_LIB=OFF','-DBUILD_SHARED_LIBS=OFF']
            flags += ['-DGGML_'+name+'='+enabled for name in ('AVX','AVX2','FMA','F16C','SSE42')]
            subprocess.run(['cmake','-S',str(source),'-B',str(build),*flags],check=True)
            subprocess.run(['cmake','--build',str(build),'--config','Release','--target','sd-cli','--parallel','2'],check=True)
            matches=list((build/'bin').rglob('sd-cli'+SUFFIX))
            if len(matches)!=1:raise RuntimeError('Expected exactly one built image executable')
            shutil.copy2(matches[0],executable)
        variants[variant]={'filename':executable.name,'sha256':sha(executable)}
    probe_source=ROOT/'build/image-probe-source';probe_source.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'scripts/image_cpu_probe.cpp',probe_source/'probe.cpp')
    (probe_source/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(NexoCPU LANGUAGES CXX)\nadd_executable(nexo-cpu-probe probe.cpp)\n')
    probe_build=ROOT/'build/image-probe'
    subprocess.run(['cmake','-S',str(probe_source),'-B',str(probe_build),*common],check=True)
    subprocess.run(['cmake','--build',str(probe_build),'--config','Release','--parallel','2'],check=True)
    probe=target/('nexo-cpu-probe'+SUFFIX)
    matches=list(probe_build.rglob(probe.name))
    if len(matches)!=1:raise RuntimeError('Expected one CPU probe')
    shutil.copy2(matches[0],probe)
    notices=['LICENSE','ggml/LICENSE']
    for folder in ('thirdparty','ggml/src'):
        for path in (source/folder).rglob('*'):
            if path.is_file() and path.name.lower() in ('license','license.txt','license.md','copying','copyright'):
                notices.append(str(path.relative_to(source)))
    for name in notices:shutil.copyfile(source/name,target/(name.replace('/','-').replace('\\','-')+'.txt'))
    with tarfile.open(target/'third-party-sources.tar.gz','w:gz') as archive:
        archive.add(source/'thirdparty',arcname='thirdparty')
        archive.add(source/'ggml/src',arcname='ggml/src')
        archive.add(source/'ggml/LICENSE',arcname='ggml/LICENSE')
    manifest.write_text(json.dumps({'format':2,'commit':COMMIT,'variants':variants,
        'probe':{'filename':probe.name,'sha256':sha(probe)},'backend':'cpu','avx_required':False},indent=2)+'\n')
    subprocess.run([str(baseline),'--help'],check=True,stdout=subprocess.DEVNULL)
    capability=subprocess.check_output([str(probe)],text=True).strip()
    if capability=='avx2':subprocess.run([str(target/variants['avx2']['filename']),'--help'],check=True,stdout=subprocess.DEVNULL)

if __name__=='__main__':main()
