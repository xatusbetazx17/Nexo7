"""Real offline STT/TTS, import, chip and permission checks against a running app."""
import argparse,base64,io,json,os,subprocess,sys,tempfile,time,urllib.request,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary');a=p.parse_args()
 with tempfile.TemporaryDirectory() as temp:
  command=([a.binary] if a.binary else [sys.executable,'-m','nexo7.desktop'])+['--no-open','--data-dir',temp]
  child=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   access=Path(temp)/'access.json';deadline=time.monotonic()+45
   while not access.exists():
    if child.poll() is not None or time.monotonic()>deadline:raise AssertionError('App startup failed')
    time.sleep(.1)
   from urllib.parse import urlsplit,parse_qs
   url=json.loads(access.read_text())['url'];parsed=urlsplit(url);base=url.split('/#')[0];token=parse_qs(parsed.fragment)['token'][0]
   def call(path,body=None):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'X-Nexo-Key':token,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=100) as response:return json.load(response)
   initial=call('/api/navi');assert not any(initial['settings'][k] for k in ('voice','avatar','scheduler'))
   call('/api/trust/permissions',{'scope':'voice.use','enabled':True});call('/api/navi/settings',{'settings':{'voice':True}})
   call('/api/navi/voice/install',{'language':'en'});deadline=time.monotonic()+180
   while True:
    state=call('/api/navi')['voice']
    if not state['busy']:break
    if time.monotonic()>deadline:raise AssertionError('Voice download timed out')
    time.sleep(.3)
   assert not state['error'],state
   audio=base64.b64decode(call('/api/navi/voice/speak',{'text':'one two three four five','language':'en'})['data'])
   import audioop
   with wave.open(io.BytesIO(audio)) as f:pcm=audioop.ratecv(f.readframes(f.getnframes()),2,1,f.getframerate(),16000,None)[0]
   out=io.BytesIO()
   with wave.open(out,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
   result=call('/api/navi/voice/transcribe',{'data':base64.b64encode(out.getvalue()).decode(),'language':'en'})
   assert 'one' in result['text'] and 'five' in result['text'],result
   assert call('/api/math',{'operation':'statistics','values':[2,4,6]})['result']['mean']=='4'
   for scope in ('transfer.export','transfer.import'):call('/api/trust/permissions',{'scope':scope,'enabled':True})
   phrase='several test pairing words for transfer';bundle=call('/api/navi/transfer/export',{'consent':True,'phrase':phrase});imported=call('/api/navi/transfer/import',{'consent':True,'phrase':phrase,'bundle':bundle})
   assert imported['identity']['id']==call('/api/trust')['identity']['id']
   assert call('/api/trust/verify')['verified']
   print(json.dumps({'passed':True,'voice':result,'chips':True,'encrypted_transfer':True,'binary':bool(a.binary)}))
   call('/api/shutdown',{});child.wait(timeout=45)
  finally:
   if child.poll() is None:child.terminate();child.wait(timeout=15)
if __name__=='__main__':main()
