"""Real guarded vision via the desktop API; no Telegram account or messages used."""
import argparse
import base64
import io
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
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def fixture(color, shape):
    image = Image.new('RGB', (320, 240), 'white'); draw = ImageDraw.Draw(image)
    (draw.rectangle if shape == 'rectangle' else draw.ellipse)((60, 30, 260, 210), fill=color)
    buffer = io.BytesIO(); image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary'); parser.add_argument('--cache', type=Path)
    parser.add_argument('--simulate-4gb', action='store_true'); parser.add_argument('--output', default='reports/native-vision-smoke.json')
    args = parser.parse_args()
    if args.binary and args.simulate_4gb: parser.error('Memory simulation uses source')
    report = {'packaged': bool(args.binary), 'platform': sys.platform, 'simulated_4gb': args.simulate_4gb, 'answers': []}
    with tempfile.TemporaryDirectory(prefix='nexo-vision-') as tmp:
        root = Path(tmp)
        if args.cache:
            for source in args.cache.rglob('*'):
                if source.is_file() and source.name.endswith(('.gguf', '.tar.gz', '.zip')):
                    target = root/'native'/source.relative_to(args.cache); target.parent.mkdir(parents=True, exist_ok=True)
                    try: os.link(source, target)
                    except OSError: shutil.copy2(source, target)
        command = [str(Path(args.binary).resolve())] if args.binary else [sys.executable, '-m', 'nexo7.desktop']
        if args.simulate_4gb:
            command = [sys.executable, '-c', "from dataclasses import replace; import nexo7.native_runtime as n; original=n.detect_hardware; n.detect_hardware=lambda: (lambda h: replace(h,total_bytes=min(h.total_bytes,4000000000),available_bytes=min(h.available_bytes,2500000000)))(original()); from nexo7.desktop import main; main()"]
        process = subprocess.Popen(command + ['--no-open', '--data-dir', str(root)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        request = None
        try:
            deadline = time.monotonic()+45
            while not (root/'access.json').exists():
                if process.poll() is not None or time.monotonic()>deadline: raise AssertionError('Desktop failed to start')
                time.sleep(.1)
            parsed = urlsplit(json.loads((root/'access.json').read_text())['url']); key = parse_qs(parsed.fragment)['token'][0]
            def request(path, body=None, authenticated=True):
                headers={'Content-Type':'application/json'}
                if authenticated: headers['X-Nexo-Key']=key
                req=Request(f'http://127.0.0.1:{parsed.port}'+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
                with urlopen(req, timeout=200) as response: return json.load(response)
            try: request('/api/vision', {'images':[fixture('red','rectangle')]}, False)
            except HTTPError as exc: assert exc.code==401
            else: raise AssertionError('Unauthenticated image accepted')
            request('/api/preferences', {'model_choice':'lfm2-vl:450m', 'performance':'fast', 'cpu_only':True})
            def ready():
                deadline=time.monotonic()+900
                while True:
                    state=request('/api/setup')
                    if state['phase']=='error': raise AssertionError(state)
                    if state['phase']=='ready': return state
                    if time.monotonic()>deadline: raise AssertionError('Vision model startup timed out')
                    time.sleep(.5)
            request('/api/setup/start', {'cpu_only':True}); state=ready(); report['plan']=state['report']['plan']
            assert request('/api/status')['vision']
            if args.simulate_4gb: assert report['plan']['enforced_limit_bytes']<=1_500_000_000
            for color,shape in [('red','rectangle'),('blue','circle')]:
                result=request('/api/vision', {'message':'What color is the '+shape+'?', 'images':[fixture(color,shape)]})
                assert color in result['answer'].lower(), result
                assert result['private'] and result['stats']['network_requests']==0
                report['answers'].append(result)
            try: request('/api/vision', {'message':'Describe both', 'images':[fixture('red','rectangle'),fixture('blue','circle')]})
            except HTTPError as exc: assert exc.code == 400
            else: raise AssertionError('Unsupported simultaneous-image analysis accepted')
            assert request('/api/history?session=vision')['messages']==[]
            # Reload in place to exercise unload-before-load and runtime/DLL ownership.
            request('/api/setup/switch', {'cpu_only':True}); ready()
            result=request('/api/relay', {'message':'Return only JSON with name Ana and age 30.'})
            assert result['answer'].strip() and result['private']
            report['relay_reply']=result['answer']; report['passed']=True
            report['scope']='Two single-image color checks, rejection of unsupported simultaneous-image requests, stateless relay and model reload. Not general visual, OCR or reasoning accuracy. Telegram sends were mocked in unit tests only.'
        finally:
            if request and process.poll() is None:
                try: request('/api/shutdown', {})
                except Exception: pass
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'platform':sys.platform,'packaged':bool(args.binary),'simulated_4gb':args.simulate_4gb}))


if __name__=='__main__': main()
