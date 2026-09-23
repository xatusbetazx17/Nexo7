"""End-to-end native inference through the desktop HTTP API, without Docker."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary')
    parser.add_argument('--simulate-8gb',action='store_true',help='Source-only test: cap detected total/available RAM to 8/4 decimal GB; OS memory guards remain real')
    parser.add_argument('--cache',type=Path,help='Optional previously downloaded catalog files; normal hashes are still checked')
    parser.add_argument('--output',default='reports/native-smoke.json')
    args=parser.parse_args()
    if args.simulate_8gb and args.binary:parser.error('--simulate-8gb is source-only')
    result={'simulated_memory':args.simulate_8gb,'scope':'Desktop API with actual native model, OS guard and no Docker', 'platform':sys.platform,'packaged':bool(args.binary),'answers':[]}
    with tempfile.TemporaryDirectory(prefix='nexo-real-') as tmp:
        root=Path(tmp)
        if args.cache:
            for source in args.cache.rglob('*'):
                if source.is_file() and (source.name.endswith(('.gguf','.tar.gz','.zip'))):
                    target=root/'native'/source.relative_to(args.cache);target.parent.mkdir(parents=True,exist_ok=True)
                    try:os.link(source,target)
                    except OSError:shutil.copy2(source,target)
        command=[str(Path(args.binary).resolve())] if args.binary else [sys.executable,'-m','nexo7.desktop']
        if args.simulate_8gb:
            command=[sys.executable,'-c',
                "from dataclasses import replace; import nexo7.native_runtime as runtime; "
                "original=runtime.detect_hardware; "
                "runtime.detect_hardware=lambda: (lambda hw: replace(hw,total_bytes=min(hw.total_bytes,8_000_000_000),available_bytes=min(hw.available_bytes,4_000_000_000)))(original()); "
                "from nexo7.desktop import main; main()"]
        process=subprocess.Popen(command+['--no-open','--data-dir',str(root)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+45
            access=root/'access.json'
            while not access.exists():
                if process.poll() is not None:raise AssertionError('Desktop exited before startup')
                if time.monotonic()>deadline:raise AssertionError('Desktop startup timed out')
                time.sleep(.1)
            parsed=urlsplit(json.loads(access.read_text())['url']);base=f'http://127.0.0.1:{parsed.port}'
            key=parse_qs(parsed.fragment)['token'][0]
            def request(path,body=None):
                data=json.dumps(body).encode() if body is not None else None
                with urlopen(Request(base+path,data=data,headers={'Content-Type':'application/json','X-Nexo-Key':key}),timeout=180) as r:return json.load(r)
            request('/api/preferences',{'performance':'fast','cpu_only':True})
            report=request('/api/setup/check',{'cpu_only':True})
            assert report['requirements_ok'],report
            assert report['plan']['runtime']=='native'
            request('/api/setup/start',{'cpu_only':True,'language':'auto'})
            deadline=time.monotonic()+900
            while True:
                state=request('/api/setup')
                if state['phase']=='error':raise AssertionError(state)
                if state['ready']:break
                if time.monotonic()>deadline:raise AssertionError('Native setup timed out')
                time.sleep(1)
            result['plan']=state['report']['plan']
            assert result['plan']['ram_limit_bytes']<=16_000_000_000
            if args.simulate_8gb:
                assert result['plan']['ram_limit_bytes']<=3_000_000_000
                assert result['plan']['enforced_limit_bytes']<=3_000_000_000
            status=request('/api/status');assert status['provider']=='native'
            for prompt,language in [('Di hola en español y explica en una frase qué puedes hacer.','es'),('Write a Python function square(n) that returns n*n.','en')]:
                response=request('/api/chat',{'message':prompt,'language':language,'private':True})
                assert response['status']=='completed',response
                assert response['stats']['model_calls']>=1 and response['stats']['output_tokens']>0,response
                result['answers'].append({'prompt':prompt,'answer':response['answer'],'stats':response['stats']})
            learning_pack={'format':'nexo-learning-v1','entries':[{'question':'What is the fictional Zorilo marker?', 'answer':'The fictional Zorilo marker is a violet triangle.', 'language':'en','kind':'correction'}]}
            request('/api/learning/import',{'pack':learning_pack,'consent':True})
            learned=request('/api/chat',{'message':'What is the fictional Zorilo marker?','language':'en','private':True})
            assert learned['status']=='completed' and learned['stats']['model_calls']>=1,learned
            assert any('violet triangle' in s['text'] for s in learned['sources']),learned
            result['answers'].append({'prompt':'What is the fictional Zorilo marker?','answer':learned['answer'],'stats':learned['stats'],'source_admitted':True})
            web_reply=request('/api/chat',{'message':'Computer network','mode':'web','remember_web':True,'language':'en'})
            assert web_reply['status']=='completed' and web_reply['stats']['model_calls']==1,web_reply
            assert web_reply['stats']['network_requests']==1 and any(s['id'].startswith('W') for s in web_reply['sources']),web_reply
            reuse=request('/api/chat',{'message':'Computer network','mode':'web','synthesize_web':False,'private':True})
            assert reuse['stats']['network_requests']==0 and reuse['stats']['model_calls']==0 and reuse['stats']['web_reused'],reuse
            result['answers'].append({'prompt':'Computer network (live Wikipedia excerpts)','answer':web_reply['answer'],'stats':web_reply['stats']})
            calc=request('/api/chat'  ,{'message':'/calc 24.5 * 40','private':True})
            assert calc['answer']=='980.0' and calc['stats']['model_calls']==0
            request('/api/artifacts',{'name':'sales.csv','content':'amount\n10.25\n20.75\n'})
            analysis=request('/api/chat',{'message':'/inspect sales.csv','private':True})
            assert json.loads(analysis['answer'])['columns'][0]['sum']=='31.00'
            imported=request('/api/import',{'name':'note.txt','data':base64.b64encode(b'Local document').decode()})
            assert imported['content']=='Local document'
            result['checks']=['real multilingual text generation','real code generation (not executed)','guarded setup','zero-model-call arithmetic','CSV totals','isolated document import','reviewed learning admitted to real model context','live web excerpts used by native model','saved web results reused without network or model calls','clean shutdown']
            request('/api/shutdown',{});process.wait(timeout=30);assert process.returncode==0
            result['passed']=True
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
            process.stderr.close()
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
