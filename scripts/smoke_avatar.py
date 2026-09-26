"""Real Tk window and state transitions; run under Xvfb on Linux CI."""
import json,subprocess,sys,tempfile,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
root=Path(__file__).resolve().parents[1]
states=['idle','listening','thinking','happy','sleeping'];seen=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  assert self.headers.get('X-Nexo-Key')=='test-only-key'
  i=len(seen);phase=states[min(i,len(states)-1)];seen.append(phase)
  raw=json.dumps({'state':phase,'unread':1,'enabled':i<len(states)}).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
s=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
try:
 with tempfile.TemporaryDirectory() as temp:
  access=Path(temp)/'access.json';access.write_text(json.dumps({'url':f'http://127.0.0.1:{s.server_port}/#token=test-only-key'}))
  command=([sys.argv[1],'--avatar-worker'] if len(sys.argv)>1 else [sys.executable,'-m','nexo7.avatar'])+[str(access)]
  result=subprocess.run(command,cwd=root,timeout=20,capture_output=True)
  assert result.returncode==0,result.stderr.decode(errors='replace')
  assert set(states)<=set(seen),seen
  print('Avatar displayed and traversed all five states.')
finally:s.shutdown();s.server_close()
