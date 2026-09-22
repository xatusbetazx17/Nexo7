"""Private process supervisor: apply OS limits before starting the native model."""
import ctypes
import json
import os
import subprocess
import sys
import threading


def windows_job(limit):
    from ctypes import wintypes as w
    size = ctypes.c_size_t
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                    ('flags', w.DWORD), ('min_working', size), ('max_working', size),
                    ('active', w.DWORD), ('affinity', size), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', size), ('job_memory', size),
                    ('peak_process', size), ('peak_job', size)]
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]; k.CreateJobObjectW.restype = w.HANDLE
    k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    k.GetCurrentProcess.restype = w.HANDLE
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    k.CloseHandle.argtypes = [w.HANDLE]
    job = k.CreateJobObjectW(None, None)
    if not job: raise OSError('Cannot create memory job')
    info = Extended(); info.basic.flags = 0x2000 | 0x200  # kill on close + aggregate committed memory
    info.job_memory = limit
    if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        k.CloseHandle(job); raise OSError('Cannot set job memory limit')
    if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
        k.CloseHandle(job); raise OSError('Cannot enter memory job')
    actual = Extended()
    if not k.QueryInformationJobObject(job, 9, ctypes.byref(actual), ctypes.sizeof(actual), None):
        raise OSError('Cannot verify memory job')
    if actual.job_memory != limit or actual.basic.flags & info.basic.flags != info.basic.flags:
        raise OSError('Memory job verification failed')
    return job  # Keep open for the supervisor lifetime; exit closes it and kills descendants.


def ensure_stdio():
    if sys.stdin is None or sys.stdout is None:
        import msvcrt
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.GetStdHandle.argtypes = [ctypes.c_ulong]; k.GetStdHandle.restype = ctypes.c_void_p
        if sys.stdin is None:
            sys.stdin = os.fdopen(msvcrt.open_osfhandle(k.GetStdHandle(-10), os.O_RDONLY), 'r', encoding='utf-8')
        if sys.stdout is None:
            sys.stdout = os.fdopen(msvcrt.open_osfhandle(k.GetStdHandle(-11), os.O_WRONLY), 'w', encoding='utf-8')


def main():
    ensure_stdio()
    spec = json.loads(sys.stdin.buffer.readline(65536))
    limit = spec['limit']
    if type(limit) is not int or not 1_000_000_000 <= limit <= 16_000_000_000:
        raise ValueError('Invalid native memory limit')
    if sys.platform == 'win32':
        job = windows_job(limit)
        guard = 'windows_job_committed_memory'
    elif sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        if resource.getrlimit(resource.RLIMIT_AS) != (limit, limit): raise OSError('Memory limit not applied')
        guard = 'linux_virtual_address_space'
    else:
        raise OSError('Native guard supports Windows and Linux only')
    # Do not inherit llama agent settings, user tool configuration, proxy API credentials,
    # or PyInstaller's private library paths into the model runtime.
    env = {k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_', 'GGML_', 'NEXO_', 'PYINSTALLER_', '_PYI_'))}
    env.pop('OPENAI_API_KEY', None)
    env.pop('LD_PRELOAD', None)
    if 'LD_LIBRARY_PATH_ORIG' in env: env['LD_LIBRARY_PATH'] = env.pop('LD_LIBRARY_PATH_ORIG')
    else: env.pop('LD_LIBRARY_PATH', None)
    env['LLAMA_API_KEY'] = spec.get('key', '')
    env['MALLOC_ARENA_MAX'] = '2'
    if sys.platform == 'win32': ctypes.windll.kernel32.SetDllDirectoryW(None)
    child = subprocess.Popen(spec['command'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=env,
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    print(json.dumps({'guard': guard, 'limit': limit, 'pid': child.pid}), flush=True)
    def watch_parent():
        # Pipe EOF handles both orderly app shutdown and an application crash.
        while os.read(sys.stdin.fileno(), 1):
            pass
        if child.poll() is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill()
    threading.Thread(target=watch_parent, daemon=True).start()
    raise SystemExit(child.wait())

if __name__ == '__main__':
    main()
