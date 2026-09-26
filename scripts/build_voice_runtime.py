"""Build the pinned, offline eSpeak NG WAV renderer and bundle complete sources."""
import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REV='4870adfa25b1a32b4361592f1be8a40337c58d6c'

def run(*args):subprocess.run(list(map(str,args)),check=True)
def main():
    source=ROOT/'build/espeak-source';build=ROOT/'build/espeak-build';dest=ROOT/'nexo7/voice_runtime'
    if not source.exists():run('git','clone','https://github.com/espeak-ng/espeak-ng.git',source)
    run('git','-C',source,'checkout','--detach',REV)
    cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake')
    run(cmake,'-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DUSE_LIBPCAUDIO=OFF','-DUSE_MBROLA=OFF','-DUSE_ASYNC=OFF','-DUSE_LIBSONIC=OFF','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded')
    run(cmake,'--build',build,'--config','Release','--target','espeak-ng-bin','data','--parallel','2')
    exe='espeak-ng.exe' if os.name=='nt' else 'espeak-ng'
    candidates=[p for p in build.rglob(exe) if p.is_file()]
    if not candidates:raise RuntimeError('eSpeak executable was not built')
    dest.mkdir(parents=True,exist_ok=True);shutil.copy2(candidates[0],dest/exe)
    shutil.copytree(build/'espeak-ng-data',dest/'espeak-ng-data',dirs_exist_ok=True)
    with tarfile.open(dest/'espeak-sources.tar.gz','w:gz') as archive:
        for p in source.rglob('*'):
            if p.is_file() and '.git' not in p.relative_to(source).parts:archive.add(p,arcname='espeak-ng/'+str(p.relative_to(source)))
        archive.add(Path(__file__),arcname='build_voice_runtime.py')
    shutil.copy2(source/'COPYING',dest/'COPYING.txt')
    (dest/'manifest.json').write_text(json.dumps({'revision':REV,'version':'1.52.0','sha256':hashlib.sha256((dest/exe).read_bytes()).hexdigest()}))
    print('Built offline voice renderer:',dest)
if __name__=='__main__':main()
