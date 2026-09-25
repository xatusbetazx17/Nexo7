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
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary')
    parser.add_argument('--simulate-8gb',action='store_true',help='Source-only test: cap detected total/available RAM to 8/4 decimal GB; OS memory guards remain real')
    parser.add_argument('--simulate-4gb',action='store_true',help='Source-only: 4 GB installed, 2.5 GB available; actual 1.5 GB model-process guard')
    parser.add_argument('--candidate',action='store_true',help='Explicit Qwen2.5 1.5B candidate; needs a 3 GB model budget')
    parser.add_argument('--cache',type=Path,help='Optional previously downloaded catalog files; normal hashes are still checked')
    parser.add_argument('--output',default='reports/native-smoke.json')
    args=parser.parse_args()
    if args.simulate_8gb and args.simulate_4gb:parser.error('Choose one memory simulation')
    if (args.simulate_8gb or args.simulate_4gb) and args.binary:parser.error('--simulate-8gb is source-only')
    result={'simulated_memory':args.simulate_8gb or args.simulate_4gb, 'installed_4gb':args.simulate_4gb,'scope':'Desktop API with actual native model, OS guard and no Docker', 'platform':sys.platform,'packaged':bool(args.binary),'answers':[]}
    with tempfile.TemporaryDirectory(prefix='nexo-real-') as tmp:
        root=Path(tmp)
        if args.cache:
            for source in args.cache.rglob('*'):
                if source.is_file() and (source.name.endswith(('.gguf','.tar.gz','.zip'))):
                    target=root/'native'/source.relative_to(args.cache);target.parent.mkdir(parents=True,exist_ok=True)
                    try:os.link(source,target)
                    except OSError:shutil.copy2(source,target)
        command=[str(Path(args.binary).resolve())] if args.binary else [sys.executable,'-m','nexo7.desktop']
        if args.simulate_8gb or args.simulate_4gb:
            total, available = (4_000_000_000, 2_500_000_000) if args.simulate_4gb else (8_000_000_000, 4_000_000_000)
            command=[sys.executable,'-c',
                "from dataclasses import replace; import nexo7.native_runtime as runtime; "
                "original=runtime.detect_hardware; "
                f"runtime.detect_hardware=lambda: (lambda hw: replace(hw,total_bytes=min(hw.total_bytes,{total}),available_bytes=min(hw.available_bytes,{available})))(original()); "
                "from nexo7.desktop import main; main()"]
        process=subprocess.Popen(command+['--no-open','--data-dir',str(root)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        request=None
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
                try:
                    with urlopen(Request(base+path,data=data,headers={'Content-Type':'application/json','X-Nexo-Key':key}),timeout=180) as r:return json.load(r)
                except HTTPError as exc:
                    raise AssertionError(path + ': ' + exc.read().decode()) from None
            request('/api/preferences',{'performance':'fast','cpu_only':True,'model_choice':'qwen2.5:1.5b' if args.candidate else 'automatic'})
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
            if args.simulate_4gb:
                assert result['plan']['ram_limit_bytes'] <= 1_500_000_000
                assert result['plan']['enforced_limit_bytes'] <= 1_500_000_000
            status=request('/api/status');assert status['provider']=='native'
            for prompt,language in [('Di hola en español y explica en una frase qué puedes hacer.','es'),('Write a Python function square(n) that returns n*n.','en')]:
                response=request('/api/chat',{'message':prompt,'language':language,'private':True})
                assert response['status']=='completed',response
                assert response['stats']['model_calls']>=1 and response['stats']['output_tokens']>0,response
                result['answers'].append({'prompt':prompt,'answer':response['answer'],'stats':response['stats']})
            for prompt,language,expected in [('What is a chiken?', 'en', ('bird', 'poultry', 'fowl')), ('¿Qué es una gallina?', 'es', ('ave', 'doméstic', 'huevo'))]:
                response=request('/api/chat',{'message':prompt,'mode':'chat','language':language,'private':True})
                assert response['status']=='completed',response
                assert any(word in response['answer'].lower() for word in expected),response
                assert response['stats']['network_requests']==0 and response['stats']['tool_calls']==0,response
                result['answers'].append({'prompt':prompt,'answer':response['answer'],'stats':response['stats']})
            companion=request('/api/chat',{'message':'What is a computer?','mode':'companion','private':True})
            assert companion['status']=='completed' and companion['stats']['network_requests']==0,companion
            assert companion['companion']['steps'],companion
            device=request('/api/chat',{'message':'/device','mode':'companion','private':True})
            assert device['status']=='completed' and device['stats']['model_calls']==0 and device['device']['total_bytes']>0,device
            learning_pack={'format':'nexo-learning-v1','entries':[{'question':'What is the fictional Zorilo marker?', 'answer':'The fictional Zorilo marker is a violet triangle.', 'language':'en','kind':'correction'}]}
            request('/api/learning/import',{'pack':learning_pack,'consent':True})
            learned=request('/api/chat',{'message':'What is the fictional Zorilo marker?','language':'en','private':True})
            assert learned['status']=='completed' and learned['stats']['model_calls']>=1,learned
            assert any('violet triangle' in s['text'] for s in learned['sources']),learned
            result['answers'].append({'prompt':'What is the fictional Zorilo marker?','answer':learned['answer'],'stats':learned['stats'],'source_admitted':True})
            instant=request('/api/chat',{'message':'What is the fictional Zorilo marker?','mode':'companion','language':'en','private':True})
            assert instant['status']=='completed' and instant['stats']['model_calls']==0 and 'violet triangle' in instant['answer'],instant
            web_reply=request('/api/chat',{'message':'Computer network','mode':'web','remember_web':True,'language':'en'})
            if web_reply['status']=='unavailable':
                # One bounded retry for the live third-party dependency; a second failure still fails CI.
                time.sleep(2)
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
            task=request('/api/tasks',{'goal':'Create a tested square function and its usage note','steps':[
                {'name':'agent-square.py','instruction':'Define square(n) returning n*n. Only file content.','function_tests':[{'function':'square','args':[3],'expected':9},{'function':'square','args':[-4],'expected':16}]},
                {'name':'agent-readme.md','instruction':'Write one short sentence explaining agent-square.py. Include that exact filename.','required':['agent-square.py']}]})
            for index in range(2):
                task=request('/api/tasks/'+task['id']+'/run',{})
                if task['state']=='blocked' and task['steps'][index]['attempts']<2:
                    task=request('/api/tasks/'+task['id']+'/run',{})
                assert task['state']=='awaiting_review',task
                task=request('/api/tasks/'+task['id']+'/apply',{'proposal_id':task['steps'][index]['proposal_id']})
                assert task['steps'][index]['state']=='applied',task
            assert task['state']=='completed',task
            result['agent_task']={'state':task['state'],'steps':[{'name':s['name'],'attempts':s['attempts'],'validation':s['validation']} for s in task['steps']]}
            request('/api/tasks/'+task['id']+'/rollback',{})
            request('/api/tasks/'+task['id']+'/rollback',{})
            result['checks']=['real local multi-step agent generation, scalar function cases, reviewed apply and rollback','real multilingual text generation' ,'real code generation (not executed)','guarded setup','zero-model-call arithmetic','CSV totals','isolated document import','reviewed learning admitted to real model context','live web excerpts used by native model','saved web results reused without network or model calls','clean shutdown']
            request('/api/shutdown',{});process.wait(timeout=30);assert process.returncode==0
            result['passed']=True
        finally:
            if request and process.poll() is None:
                try:request("/api/shutdown",{})
                except Exception:pass
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
            process.stderr.close()
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
