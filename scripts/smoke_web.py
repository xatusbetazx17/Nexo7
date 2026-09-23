"""Packaged-app live encyclopedia lookup, then local reuse. No paid API needed."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen


def main():
    binary=str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix='nexo-web-') as tmp:
        proc=subprocess.Popen([binary,'--no-open','--data-dir',tmp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            access=Path(tmp)/'access.json';deadline=time.monotonic()+45
            while not access.exists():
                if proc.poll() is not None:raise RuntimeError('App exited before startup')
                if time.monotonic()>deadline:raise RuntimeError('Startup timed out')
                time.sleep(.1)
            parsed=urlsplit(json.loads(access.read_text())['url']);key=parse_qs(parsed.fragment)['token'][0]
            def req(path,body=None):
                data=json.dumps(body).encode() if body is not None else None
                with urlopen(Request(f'http://127.0.0.1:{parsed.port}'+path,data=data,headers={'Content-Type':'application/json','X-Nexo-Key':key}),timeout=45) as response:return json.load(response)
            body={'message':'Computer network','mode':'web','remember_web':True,'synthesize_web':False}
            first=req('/api/chat',body)
            assert first['status']=='completed' and first['sources'],first
            assert first['stats']['network_requests']==1 and first['stats']['model_calls']==0
            second=req('/api/chat',body)
            assert second['stats']['network_requests']==0 and second['stats']['web_reused'],second
            assert [s['id'] for s in first['sources']]==[s['id'] for s in second['sources']]
            local=req('/api/chat',{'message':'Computer network','private':True})
            assert local['stats']['web_reused'] and local['stats']['network_requests']==0
            req('/api/shutdown',{});proc.wait(timeout=25);assert proc.returncode==0
            print(json.dumps({'passed':True,'platform':sys.platform,'packaged':True,'live_provider':'wikipedia',
                'initial_search_requests':1,'repeated_search_requests':0,'model_calls':0,'ordinary_chat_reuses_saved_sources':True,
                'scope':'Live encyclopedia excerpt retrieval and reuse, not answer accuracy or broad web coverage'}))
        finally:
            if proc.poll() is None:proc.kill();proc.wait(timeout=10)

if __name__=='__main__':main()
