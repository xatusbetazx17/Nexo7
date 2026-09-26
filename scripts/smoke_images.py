"""Real text-to-image generation through the desktop API; save review images."""
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
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen
from PIL import Image,ImageStat

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary');parser.add_argument('--simulate-4gb-free',action='store_true')
    parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args()
    output=ROOT/'reports/diffusion';output.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'build/image-model-cache';cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nexo-diffusion-') as tmp:
        root=Path(tmp);models=root/'image-models';models.mkdir()
        for source in cache.iterdir():
            try:os.link(source,models/source.name)
            except OSError:shutil.copy2(source,models/source.name)
        command=[str(Path(args.binary).resolve())] if args.binary else [sys.executable,'-m','nexo7.desktop']
        if args.simulate_4gb_free or args.baseline:
            if args.binary:raise ValueError('Memory simulation needs source')
            code="from dataclasses import replace; import nexo7.image_generation as g; original=g.detect_hardware; g.detect_hardware=lambda **kw:replace(original(**kw),available_bytes=4000000000); "
            if args.baseline:code+="original_runtime=g.runtime_path; g.runtime_path=lambda:original_runtime(force_baseline=True); "
            command=[sys.executable,'-c',code+"from nexo7.desktop import main; main()"]
        process=subprocess.Popen(command+['--no-open','--data-dir',str(root)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        request=None
        try:
            deadline=time.monotonic()+60
            while not (root/'access.json').exists():
                if process.poll() is not None or time.monotonic()>deadline:raise AssertionError('Desktop did not start')
                time.sleep(.2)
            parsed=urlsplit(json.loads((root/'access.json').read_text())['url']);token=parse_qs(parsed.fragment)['token'][0]
            def request(path,body=None):
                req=Request(f'http://127.0.0.1:{parsed.port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'X-Nexo-Key':token,'Content-Type':'application/json'})
                with urlopen(req,timeout=60) as r:return json.load(r)
            def wait():
                deadline=time.monotonic()+1200
                while True:
                    state=request('/api/images')
                    if state['phase'] not in ('installing','generating'):return state
                    if time.monotonic()>deadline:raise AssertionError('Image job timed out')
                    time.sleep(1)
            request('/api/images/install',{});state=wait()
            assert state['phase']=='completed',state
            for source in models.iterdir():
                if not (cache/source.name).exists():shutil.copy2(source,cache/source.name)
            if args.binary:
                request('/api/preferences',{'model_choice':'lfm2-vl:450m','performance':'fast','cpu_only':True})
                request('/api/setup/start',{'cpu_only':True})
                deadline=time.monotonic()+600
                while True:
                    setup=request('/api/setup')
                    if setup['phase']=='ready':break
                    if setup['phase']=='error' or time.monotonic()>deadline:raise AssertionError(setup)
                    time.sleep(1)
            prompt='A portrait photograph of an adult woman with curly hair, soft natural light' if args.simulate_4gb_free else 'A photograph of a red fox in a sunlit forest, detailed fur'
            size=256 if args.baseline else 512
            job=request('/api/chat',{'message':'Draw '+prompt,'mode':'companion','private':True,'image_mode':'diffusion','image_size':size,'image_steps':2 if args.baseline else 4})
            assert job.get('image_job'),job
            state=wait();assert state['phase']=='completed',state
            if args.binary:
                setup=request('/api/setup')
                assert setup['phase']=='ready',setup
                answer=request('/api/chat',{'message':'Say hello.','mode':'companion','private':True})
                assert request('/api/status')['provider']=='native'
                assert answer.get('answer') and answer.get('status')=='completed',answer
                (output/'chat-restored.json').write_text(json.dumps(answer,indent=2))
            assert state['guard']['enforced_limit']<=4_000_000_000,state['guard']
            if args.simulate_4gb_free:assert state['guard']['enforced_limit']<=3_250_000_000
            if args.baseline:assert state['plan']['cpu_variant']=='baseline',state['plan']
            else:assert state['plan']['cpu_variant']=='avx2',state['plan']
            name='portrait-baseline-draft' if args.baseline else ('portrait-4gb-free' if args.simulate_4gb_free else 'fox-packaged')
            png=output/(name+'.png');png.write_bytes(base64.b64decode(state['files'][0]['data']))
            with Image.open(png) as img:
                assert img.size==(size,size)
                assert max(ImageStat.Stat(img).stddev)>12,'Blank or nearly uniform image'
            state.pop('files',None);(output/(name+'.json')).write_text(json.dumps(state,indent=2))
            print(json.dumps({'passed':True,'platform':sys.platform,'packaged':bool(args.binary),'elapsed_seconds':state['elapsed_seconds'],'guard':state['guard']}))
            if args.simulate_4gb_free and not args.baseline:
                request('/api/images/start',{'prompt':'A red fox','size':512,'steps':8})
                deadline=time.monotonic()+30
                while 'guard' not in request('/api/images'):
                    if time.monotonic()>deadline:raise AssertionError('Cancellation test worker did not start')
                    time.sleep(.2)
                request('/api/images/cancel',{})
                cancelled=wait()
                assert cancelled['phase']=='cancelled' and not cancelled['files'],cancelled
                (output/'cancellation.json').write_text(json.dumps(cancelled,indent=2))
        finally:
            if request and process.poll() is None:
                try:request('/api/shutdown',{})
                except Exception:pass
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


if __name__=='__main__':main()
