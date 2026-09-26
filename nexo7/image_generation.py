"""Optional, offline diffusion jobs with one-model ownership and OS RAM limits."""
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import time
from .config import Config
from .creative import file
from .hardware import detect_hardware
from .native_runtime import NativeProcess, digest, download, start_native, stop_native

CATALOG = json.loads(Path(__file__).with_name('image_catalog.json').read_text())
RUNTIME_ROOT=Path(__file__).parent/'image_runtime'
STYLES = {'photo':'photograph, natural lighting, detailed, ', 'art':'digital painting, detailed illustration, ',
          'anime':'anime illustration, ', 'none':''}


def runtime_path(force_baseline=False):
    root = RUNTIME_ROOT
    manifest = root / 'manifest.json'
    if not manifest.is_file():
        raise ValueError('This build has no image engine. Install the Windows/Linux desktop release, or run scripts/build_image_runtime.py for a source checkout.')
    info = json.loads(manifest.read_text())
    if info.get('commit') != CATALOG['engine_commit'] or info.get('format')!=2:
        raise ValueError('Image engine verification failed. Reinstall the desktop release.')
    def verified(entry):
        name=entry.get('filename','')
        if not name or Path(name).name!=name:raise ValueError('Invalid image engine manifest.')
        path=root/name
        if not path.is_file() or digest(path)!=entry.get('sha256'):raise ValueError('Image engine verification failed. Reinstall the desktop release.')
        if os.name!='nt':path.chmod(0o700)
        return path
    variant='baseline'
    if not force_baseline:
        probe=verified(info['probe'])
        try:
            result=subprocess.run([str(probe)],capture_output=True,text=True,timeout=5,check=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if result.stdout.strip()=='avx2':variant='avx2'
        except (OSError,subprocess.SubprocessError):pass
    return verified(info['variants'][variant])


def validate(body):
    prompt = body.get('prompt')
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1000 or any(ord(c)<32 and c not in '\n\t' for c in prompt):
        raise ValueError('Describe the image using 1–1000 characters.')
    size, steps, style = body.get('size',256), body.get('steps',2), body.get('style','photo')
    if type(size) is not int or size not in (256,512):
        raise ValueError('Image size must be 256 or 512 pixels.')
    if type(steps) is not int or steps not in (2,4,8):
        raise ValueError('Choose 2, 4 or 8 image-generation steps.')
    if not isinstance(style,str) or style not in STYLES:
        raise ValueError('Choose photo, art, anime or none.')
    seed=body.get('seed',-1)
    if type(seed) is not int or not -1 <= seed <= 2147483647:
        raise ValueError('Seed must be -1 (random) or an integer from 0 to 2147483647.')
    return dict(prompt=prompt.strip(), size=size, steps=steps, style=style,
                seed=secrets.randbelow(2147483648) if seed==-1 else seed)


def memory_plan(size):
    hw=detect_hardware(probe_gpu=False)
    if hw.system not in ('Windows','Linux') or hw.machine.lower() not in ('amd64','x86_64'):
        raise ValueError('The image engine supports x86-64 Windows and Linux.')
    limit=min(4_000_000_000, hw.available_bytes-750_000_000)
    minimum=2_000_000_000 if size==256 else 3_000_000_000
    if limit<minimum:
        raise ValueError(f'Image generation at {size}px needs at least {(minimum+750_000_000)/1e9:.2f} GB available RAM after chat unloads. Close other apps or select 256px draft.')
    return {'ram_limit_bytes':limit,'threads':max(1,min(4,hw.cpu_threads-1)),
            'available_bytes':hw.available_bytes,'size':size,'backend':'cpu'}


class ImageGenerator:
    def __init__(self, controller):
        self.controller=controller
        self.root=Path(controller.config.database).resolve().parent/'image-models'
        self.lock=threading.RLock()
        self.cancel=threading.Event()
        self.thread=None
        self.state={'phase':'idle','message':'Install the optional image model to begin.','id':None,'files':[]}

    def installed(self):
        return all((self.root/e['filename']).is_file() and (self.root/e['filename']).stat().st_size==e['size'] for e in (CATALOG['model'],CATALOG['decoder']))

    def snapshot(self):
        with self.lock:
            installed=self.installed()
            state=dict(self.state)
            if state['phase']=='idle' and installed:state['message']='Image model installed. Describe an image to generate offline.'
            return {**state,'installed':installed,'download_bytes':sum(CATALOG[k]['size'] for k in ('model','decoder')),
                    'model':CATALOG['model']['name'],'engine_available':(Path(__file__).parent/'image_runtime'/'manifest.json').is_file()}

    def emit(self, message):
        with self.lock:self.state['message']=str(message)[:500]

    def begin(self, body, install=False):
        options=None if install else validate(body)
        executable=runtime_path()
        if not install and not self.installed():
            raise ValueError('Install AI images in Create first (about 1.64 GB). Simple illustrations remain available by turning off AI images in chat.')
        if not self.controller.operation.acquire(blocking=False):
            raise ValueError('Wait for the current chat, setup or image operation to finish.')
        self.cancel.clear()
        with self.lock:
            self.state={'phase':'installing' if install else 'generating','message':'Preparing…','id':secrets.token_hex(12),'files':[], 'started_at':time.time()}
        def work():
            was_ready=self.controller.owns_runtime
            original=self.controller.config
            files=[];notice='';error=None;cancelled=False
            try:
                if not install and was_ready:
                    self.emit('Unloading chat to free memory for the image…')
                    stop_native(original)
                    with self.controller.lock:
                        self.controller.owns_runtime=False
                        self.controller.config=Config(database=original.database,persist_history=original.persist_history)
                        self.controller.state.update(phase='idle',error=None)
                for key in ('model','decoder'):
                    entry=CATALOG[key];target=self.root/entry['filename']
                    if install:
                        download(entry,target,self.emit,self.cancel)
                    elif digest(target)!=entry['sha256']:
                        raise ValueError('Image model checksum failed. Install the model again.')
                if install:
                    notice='Image model installed. Generation works offline. English prompts work best.'
                else:
                    plan=memory_plan(options['size'])
                    plan['cpu_variant']='avx2' if 'avx2' in executable.name else 'baseline'
                    with self.lock:self.state['plan']=plan
                    self.emit('Generating on CPU. This can take several minutes on a modest PC. You can cancel.')
                    with tempfile.TemporaryDirectory(prefix='nexo-image-') as tmp:
                        output=Path(tmp)/'image.png'
                        command=[str(executable),'-m',str(self.root/CATALOG['model']['filename']),
                                 '--taesd',str(self.root/CATALOG['decoder']['filename']),
                                 '-p',STYLES[options['style']]+options['prompt'],
                                 '-o',str(output),'-W',str(options['size']),'-H',str(options['size']),
                                 '--steps',str(options['steps']),'--cfg-scale','1.0','--sampling-method','lcm',
                                 '--seed',str(options['seed']),'-t',str(plan['threads']),'--diffusion-fa','--rng','cpu']
                        worker=NativeProcess(command,plan['ram_limit_bytes'],'',capture_output=True)
                        try:
                            with self.lock:self.state['guard']=worker.receipt
                            deadline=time.monotonic()+900
                            while worker.process.poll() is None:
                                if self.cancel.wait(.2):raise ValueError('Image generation cancelled.')
                                if time.monotonic()>deadline:raise ValueError('Image generation exceeded 15 minutes. Try 256px and 2 steps.')
                            if self.cancel.is_set():raise ValueError('Image generation cancelled.')
                            if worker.process.returncode or not output.is_file():
                                with self.lock:self.state['diagnostic']=worker.output_tail()
                                raise ValueError(f'The image engine stopped (exit {worker.process.returncode}). Try 256px, close other apps, or reinstall the image model. Technical details are available from the local image status API.')
                            if output.stat().st_size>8_000_000:raise ValueError('Image output exceeded the size limit.')
                            from PIL import Image
                            with Image.open(output) as img:
                                if img.size!=(options['size'],options['size']):raise ValueError('Unexpected image dimensions.')
                                clean=io.BytesIO();img.convert('RGB').save(clean,format='PNG')
                            files=[file('Nexo-image.png','image/png',clean.getvalue())]
                            notice='Generated offline with DreamShaper 8 LCM. Download to keep the image. Faces, hands, lettering and prompt accuracy can be imperfect.'
                        finally:
                            worker.close()
                            if not files:
                                with self.lock:self.state['diagnostic']=worker.output_tail()
            except Exception as exc:
                error=str(exc)[:500];cancelled=self.cancel.is_set()
            finally:
                if not install and was_ready and not self.controller.cancel.is_set():
                    self.emit('Image operation ended. Restoring your chat model…')
                    try:
                        cfg,plan=start_native(original.database,cpu_only=self.controller.preferences.get('cpu_only',False),
                            performance=self.controller.preferences.get('performance','fast'),
                            model_choice=self.controller.preferences.get('model_choice','automatic'),
                            emit=lambda _:None,cancel=self.controller.cancel)
                        with self.controller.lock:
                            self.controller.config=replace(cfg,response_language=original.response_language,persist_history=original.persist_history)
                            self.controller.owns_runtime=True
                            self.controller.state.update(phase='ready',error=None,report={'requirements_ok':True,'plan':plan,'hardware':plan['hardware'],'error':None})
                    except Exception:
                        recovery=' Chat could not reload; use Settings to start it again.'
                        if error:error+=recovery
                        else:notice+=recovery
                with self.lock:
                    self.state.update(phase='cancelled' if cancelled else 'error' if error else 'completed',message=error or notice,files=files,
                                      options=options,elapsed_seconds=round(time.time()-self.state['started_at'],1))
                self.controller.operation.release()
        self.thread=threading.Thread(target=work,name='nexo-image-generation',daemon=True)
        self.thread.start()
        return self.snapshot()

    def close(self):
        self.cancel.set()
        if self.thread:self.thread.join()
