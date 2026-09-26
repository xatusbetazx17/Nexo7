"""Optional offline voice: short Vosk recognition jobs and eSpeak NG WAV synthesis."""
import base64,io,json,os,secrets,shutil,subprocess,sys,tempfile,threading,time,wave,zipfile
from pathlib import Path,PurePosixPath
from .native_runtime import download,NativeProcess,cancelled
CATALOG=json.loads(Path(__file__).with_name('voice_catalog.json').read_text())
RUNTIME=Path(__file__).with_name('voice_runtime')


def unpack(archive,destination,folder):
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if len(entries)>200 or sum(x.file_size for x in entries)>200_000_000:raise ValueError('Voice archive exceeds limits')
        for item in entries:
            p=PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=folder or '\\' in item.filename or ':' in item.filename or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe voice archive')
            target=destination.joinpath(*p.parts)
            if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)


def checked_wav(raw):
    if len(raw)>1_050_000:raise ValueError('Record at most 30 seconds')
    try:
        with wave.open(io.BytesIO(raw)) as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000 or not 1<=wav.getnframes()<=480000:raise ValueError()
            pcm=wav.readframes(wav.getnframes())
            if len(pcm)!=wav.getnframes()*2:raise ValueError()
        return pcm
    except Exception:raise ValueError('Use a mono, 16 kHz, 16-bit WAV recording of at most 30 seconds') from None


class Voice:
    def __init__(self,root,trust,controller):
        self.root=Path(root)/'voice';self.root.mkdir(parents=True,exist_ok=True)
        self.trust,self.controller=trust,controller;self.lock=threading.RLock();self.cancel=threading.Event()
        self.thread=None;self.progress='';self.error='';self.active=None
    def status(self):
        return {'languages':[{'id':k,'installed':(self.root/v['folder']/'installed.json').is_file(),'download_bytes':v['bytes']} for k,v in CATALOG.items()],
            'tts_available':(RUNTIME/('espeak-ng.exe' if os.name=='nt' else 'espeak-ng')).is_file(),
            'busy':bool(self.thread and self.thread.is_alive()),'progress':self.progress,'error':self.error,'max_seconds':30}
    def install(self,language):
        if language not in CATALOG:raise ValueError('Choose English or Spanish')
        with self.lock:
            if self.thread and self.thread.is_alive():raise ValueError('A voice download is already running')
            self.cancel.clear();self.error='';self.progress='Downloading speech recognition…'
            def job():
                try:
                    with self.trust.action('voice.install'):
                        entry=CATALOG[language];archive=download({**entry,'size':entry['bytes']},self.root/entry['filename'],lambda s:setattr(self,'progress',s),self.cancel)
                        with tempfile.TemporaryDirectory(dir=self.root) as temp:
                            unpack(archive,Path(temp),entry['folder']);cancelled(self.cancel)
                            if not self.trust.allowed('voice.install'):raise ValueError('Voice download permission was revoked')
                            dest=self.root/entry['folder']
                            if dest.exists():shutil.rmtree(dest)
                            (Path(temp)/entry['folder']).rename(dest)
                            (dest/'installed.json').write_text(json.dumps({'sha256':entry['sha256']}))
                        self.progress='Speech recognition is ready.'
                except Exception as exc:self.error=str(exc)[:250];self.progress=''
            self.thread=threading.Thread(target=job,name='nexo-voice-download',daemon=True);self.thread.start()
        return self.status()
    def transcribe(self,body):
        with self.trust.action('voice.transcribe'):
            language=body.get('language','en')
            if language not in CATALOG:raise ValueError('Choose English or Spanish')
            model=self.root/CATALOG[language]['folder']
            if not (model/'installed.json').is_file():raise ValueError('Download this recognition language in Navi → Voice first')
            try:raw=base64.b64decode(body.get('data',''),validate=True)
            except Exception:raise ValueError('Invalid recording') from None
            checked_wav(raw)
            if not self.controller.operation.acquire(blocking=False):raise ValueError('Wait for the current model operation before transcribing')
            try:
                from .hardware import detect_hardware
                hardware=detect_hardware(probe_gpu=False)
                if hardware.available_bytes<1_650_000_000:raise ValueError('Close other apps to free 1.65 GB before transcribing')
                with tempfile.TemporaryDirectory(dir=self.root) as temp:
                    folder=Path(temp);audio=folder/'recording.wav';output=folder/'transcript.json';audio.write_bytes(raw)
                    command=([sys.executable,'--voice-worker'] if getattr(sys,'frozen',False) else [sys.executable,'-m','nexo7.voice'])+[str(model),str(audio),str(output)]
                    runtime=NativeProcess(command,1_500_000_000,secrets.token_hex(16),capture_output=True);self.active=runtime
                    try:
                        deadline=time.monotonic()+60
                        while runtime.process.poll() is None and not output.exists():
                            if time.monotonic()>deadline:raise ValueError('Recognition timed out; try a shorter recording')
                            if not self.trust.allowed('voice.transcribe'):raise ValueError('Voice permission was revoked')
                            time.sleep(.05)
                        if not output.is_file():raise ValueError('Recognition worker stopped (exit '+str(runtime.process.poll())+'). Close other apps and retry a shorter recording.')
                        result=json.loads(output.read_text())
                        if 'error' in result:raise ValueError('Could not recognize this recording ('+str(result['error'])[:50]+').')
                        return {'text':str(result.get('text',''))[:4000],'local':True}
                    finally:runtime.close();self.active=None
            finally:self.controller.operation.release()
    def speak(self,body):
        with self.trust.action('voice.speak'):
            text=body.get('text');language=body.get('language','en')
            if not isinstance(text,str) or not 1<=len(text.strip())<=1500:raise ValueError('Read aloud accepts 1–1500 characters')
            if language not in ('en','es','fr','de','it','pt'):raise ValueError('Unsupported voice language')
            executable=RUNTIME/('espeak-ng.exe' if os.name=='nt' else 'espeak-ng')
            if not executable.is_file():raise ValueError('This build does not include the offline voice renderer')
            with self.lock,tempfile.TemporaryDirectory(dir=self.root) as temp:
                source=Path(temp)/'text.txt';output=Path(temp)/'speech.wav';source.write_text(text,encoding='utf-8')
                env=dict(os.environ);env['ESPEAK_DATA_PATH']=str(RUNTIME)
                subprocess.run([str(executable),'-v',language,'-s','165','-b','1','-f',str(source),'-w',str(output)],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True,env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                if output.stat().st_size>10_000_000:raise ValueError('Speech output exceeded its size limit')
                return {'data':base64.b64encode(output.read_bytes()).decode(),'mime':'audio/wav','local':True}
    def close(self):
        self.cancel.set()
        if self.active:self.active.close()
        if self.thread:self.thread.join(timeout=35)


def worker_main():
    model,audio,output=map(Path,sys.argv[-3:])
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    try:
        import vosk
        vosk.SetLogLevel(-1);recognizer=vosk.KaldiRecognizer(vosk.Model(str(model)),16000)
        pcm=checked_wav(audio.read_bytes());parts=[]
        for offset in range(0,len(pcm),8000):
            if recognizer.AcceptWaveform(pcm[offset:offset+8000]):parts.append(json.loads(recognizer.Result()).get('text',''))
        parts.append(json.loads(recognizer.FinalResult()).get('text',''))
        value={'text':' '.join(x for x in parts if x)}
    except Exception as exc:value={'error':type(exc).__name__}
    stage=output.with_suffix('.part');stage.write_text(json.dumps(value),encoding='utf-8');stage.replace(output)
if __name__=='__main__':worker_main()
