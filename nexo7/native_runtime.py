"""Pinned native llama.cpp runtime, bounded startup, local authenticated inference."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import queue
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from .config import Config
from .hardware import detect_hardware, plan_local
from .net import fetch_json, TransportError

CATALOG = json.loads(Path(__file__).with_name('native_catalog.json').read_text())
ACTIVE = {}
LOCK = threading.RLock()


def cancelled(cancel):
    if cancel is not None and cancel.is_set(): raise ValueError('Setup cancelled')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def download(entry, target, emit=print, cancel=None):
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    cancelled(cancel)
    if target.exists() and target.stat().st_size == entry['size'] and digest(target) == entry['sha256']:
        return target
    if shutil.disk_usage(target.parent).free < entry['size'] + 300_000_000:
        raise ValueError('Not enough free disk space for this download')
    part = target.with_suffix(target.suffix+'.part'); part.unlink(missing_ok=True)
    total = 0; next_notice = 0; sha = hashlib.sha256()
    # Only pinned HTTPS URLs from the bundled catalog are supplied by the application.
    try:
        request = urllib.request.Request(entry['url'], headers={'User-Agent':'Nexo7/0.5', 'Accept-Encoding':'identity'})
        with urllib.request.urlopen(request, timeout=30) as response, part.open('xb') as output:
            if not response.geturl().startswith('https://'): raise ValueError('Non-HTTPS download redirect rejected')
            while True:
                cancelled(cancel)
                block = response.read(1024*1024)
                if not block: break
                total += len(block)
                if total > entry['size']: raise ValueError('Download exceeds pinned size')
                sha.update(block); output.write(block)
                if total >= next_notice:
                    emit(f'Download {target.name}: {100*total/entry["size"]:.0f}%')
                    next_notice = total + max(10_000_000, entry['size']//20)
        if total != entry['size'] or sha.hexdigest() != entry['sha256']:
            raise ValueError('Download checksum mismatch; file was not installed')
        cancelled(cancel); part.replace(target)
        return target
    finally:
        part.unlink(missing_ok=True)


def extract_runtime(archive, destination):
    """Extract bounded members; materialize safe archive-internal links as regular files."""
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    def safe(name):
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name: raise ValueError('Unsafe archive path')
        return destination.joinpath(*p.parts)
    total = 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            if len(z.infolist()) > 1000: raise ValueError('Runtime archive has too many entries')
            for item in z.infolist():
                p = safe(item.filename)
                if item.is_dir(): continue
                total += item.file_size
                if total > 600_000_000: raise ValueError('Runtime archive exceeds limit')
                p.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, p.open('wb') as dst: shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            if len(members) > 1000: raise ValueError('Runtime archive has too many entries')
            for item in members:
                p = safe(item.name)
                if item.isdir(): continue
                if not (item.isfile() or item.issym()): raise ValueError('Unsupported archive member')
                if item.issym(): safe(str(PurePosixPath(item.name).parent / item.linkname))
                src = tar.extractfile(item)
                if src is None: raise ValueError('Missing runtime member')
                p.parent.mkdir(parents=True, exist_ok=True)
                with src, p.open('wb') as dst:
                    while block := src.read(1024*1024):
                        total += len(block)
                        if total > 600_000_000: raise ValueError('Runtime archive exceeds limit')
                        dst.write(block)
                p.chmod(0o700 if item.mode & 0o111 else 0o600)
    matches = list(destination.rglob('llama.exe' if os.name == 'nt' else 'llama'))
    if len(matches) != 1: raise ValueError('Native executable missing from archive')
    return matches[0]


def native_plan(cpu_only=False, performance='balanced'):
    hw = detect_hardware()
    if hw.system not in {'Windows','Linux'} or hw.machine.lower() not in {'amd64','x86_64'}:
        raise ValueError('This native release supports 64-bit x86 Windows and glibc Linux')
    # Vulkan drivers can reserve large virtual address ranges on Linux. Strict RLIMIT_AS
    # is retained there by using CPU; Windows can attempt Vulkan with committed-memory limits.
    use_cpu = cpu_only or hw.system == 'Linux' or hw.gpu_hint != 'nvidia' or hw.gpu_index != 0
    plan = plan_local(hw, cpu_only=use_cpu, performance=performance)
    if performance == 'fast': plan['profiles'] = [p for p in plan['profiles'] if p['model'] == 'qwen3.5:0.8b']
    plan['runtime'] = 'native'
    plan['backend'] = 'vulkan' if plan['backend'] == 'nvidia' and not use_cpu else 'cpu'
    plan['guard_scope'] = ('Windows job committed memory (worker + model)' if hw.system == 'Windows'
                           else 'Linux virtual address space per model process')
    plan['guard_scope'] += '; excludes app/browser, OS, dedicated VRAM and disk storage'
    for profile in plan['profiles']:
        profile['context_tokens'] = min(profile['context_tokens'], 6144)
        profile['download_bytes'] = CATALOG['models'][profile['model']]['size']
    return plan


def worker_command():
    if getattr(sys, 'frozen', False): return [sys.executable, '--native-worker']
    return [sys.executable, '-m', 'nexo7.native_worker']


class NativeProcess:
    def __init__(self, command, limit, key):
        env = dict(os.environ); env['MALLOC_ARENA_MAX'] = '2'
        self.process = subprocess.Popen(worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, env=env,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.process.stdin.write((json.dumps({'command':command,'limit':limit,'key':key})+'\n').encode())
        self.process.stdin.flush()
        receipt = queue.Queue()
        threading.Thread(target=lambda:receipt.put(self.process.stdout.readline(4096)), daemon=True).start()
        error = "Native process could not establish its memory guard"
        try:
            self.receipt = json.loads(receipt.get(timeout=20))
            if "error" in self.receipt:
                error += ": " + self.receipt["error"]
            if self.receipt.get('limit') != limit or self.receipt.get('guard') not in {'linux_virtual_address_space','windows_job_committed_memory'}:
                raise ValueError('Native guard was not verified')
        except Exception:
            self.close(); raise ValueError(error) from None
        self.key = key
    def close(self):
        if self.process.stdin and not self.process.stdin.closed: self.process.stdin.close()
        try: self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait(timeout=5)
        self.process.stdout.close()


def start_native(database, *, cpu_only=False, emit=print, cancel=None, performance='balanced'):
    cancelled(cancel)
    plan = native_plan(cpu_only, performance)
    root = Path(database).resolve().parent / 'native'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    system = platform.system()
    last_error = 'No profile could load'
    backends = [plan['backend']] + (['cpu'] if plan['backend'] != 'cpu' else [])
    for backend in backends:
        current = native_plan(backend == 'cpu', performance)
        backend = current['backend']
        entry = CATALOG['runtimes'][system+'-'+backend]
        archive = download(entry, root / entry['url'].rsplit('/',1)[1], emit, cancel)
        # Re-extract the verified archive at each launch; no stale DLL/executable mixing.
        folder = root / (CATALOG['release']+'-'+backend)
        if folder.exists(): shutil.rmtree(folder)
        executable = extract_runtime(archive, folder)
        for profile in current['profiles']:
            cancelled(cancel)
            model = CATALOG['models'][profile['model']]
            emit('Preparing '+profile['model']+' with '+backend.upper()+'; '+current['guard_scope'])
            model_path = download(model, root / 'models' / model['filename'], emit, cancel)
            # Recheck available host RAM after downloads and immediately before loading.
            refreshed = native_plan(backend == 'cpu', performance)
            if profile['minimum_budget'] > refreshed['ram_limit_bytes']: continue
            limit = refreshed['ram_limit_bytes']
            key = secrets.token_urlsafe(32)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
            command = [str(executable), 'serve', '-m', str(model_path), '--alias', profile['model'],
                       '--host','127.0.0.1','--port',str(port), '-t',str(current['threads']), '-tb',str(current['threads']),
                       '-c',str(profile['context_tokens']), '-np','1', '-n','512', '-lm','none',
                       '-ngl','99' if backend == 'vulkan' else '0', '--fit','off','--reasoning','off',
                       '--no-webui','--no-agent','--no-ui-mcp-proxy','--no-slots','--log-disable']
            if backend == 'vulkan': command += ['--device','Vulkan0']
            runtime = None
            try:
                runtime = NativeProcess(command, limit, key)
                url = f'http://127.0.0.1:{port}'
                deadline = time.monotonic()+180
                while time.monotonic() < deadline:
                    cancelled(cancel)
                    if runtime.process.poll() is not None: raise ValueError('Native engine exited while loading')
                    try:
                        health = fetch_json(url+'/health', headers={'Authorization':'Bearer '+key},timeout=2)
                        if health.get('status') == 'ok': break
                    except TransportError: pass
                    time.sleep(.2)
                else: raise ValueError('Native engine startup timed out')
                cancelled(cancel)
                identifier = secrets.token_hex(16)
                cfg = Config(provider='native', model=profile['model'], native_runtime_id=identifier,
                             database=str(database), local_ram_limit_bytes=limit, local_threads=current['threads'],
                             local_backend=backend, ollama_context_tokens=profile['context_tokens'], history_messages=4,
                             max_context_chars=12000, max_output_tokens=256 if performance == 'fast' else 512,
                             max_model_calls=2 if performance == 'fast' else 3,
                             max_total_output_tokens=512 if performance == 'fast' else 1536, timeout_seconds=180)
                with LOCK: ACTIVE[identifier] = (runtime,url,cfg)
                current.update(ram_limit_bytes=limit,selected_model=profile['model'],guard=runtime.receipt['guard'])
                emit('Ready: native local AI. Downloads are reused on future launches.')
                return cfg, current
            except (ValueError,OSError,TransportError) as exc:
                last_error = str(exc)
                emit('Could not load this profile within the memory limit; trying a smaller supported profile.')
            finally:
                if runtime and not any(value[0] is runtime for value in ACTIVE.values()): runtime.close()
        emit('Trying CPU fallback.' if backend != 'cpu' else 'No native CPU profile loaded.')
    raise ValueError(last_error+'. No unbounded model process was started.')


def verify_native(config):
    with LOCK: active = ACTIVE.get(config.native_runtime_id)
    if not active or active[2] != config and replace(active[2],response_language=config.response_language) != config:
        raise ValueError('Native runtime is not owned by this application; use desktop setup')
    runtime,url,_ = active
    if runtime.process.poll() is not None: raise ValueError('Native runtime stopped; restart Nexo to reload it')
    return runtime,url


def stop_native(config):
    with LOCK: entry = ACTIVE.pop(config.native_runtime_id,None)
    if entry: entry[0].close()
