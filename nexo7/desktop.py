"""Portable desktop launcher with a local browser UI and per-user data."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import threading
import webbrowser
from .server import make_server
from .setup import SetupController
from .store import Store


def data_directory():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    path = base / "Nexo7"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@contextmanager
def instance_lock(directory):
    """OS-owned lock is released even after a crash; avoid duplicate model owners."""
    stream = (directory / "instance.lock").open("a+b")
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    acquired = False
    try:
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        if acquired:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Nexo 7 desktop assistant")
    parser.add_argument("--version", action="version", version="Nexo 7 0.5.0")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser automatically")
    parser.add_argument("--port", type=int, default=0, help="Local port; 0 selects an available port")
    parser.add_argument("--data-dir", type=Path, help="Override the per-user application data directory")
    args = parser.parse_args(argv)
    directory = args.data_dir.resolve() if args.data_dir else data_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with instance_lock(directory) as acquired:
        access = directory / "access.json"
        if not acquired:
            if access.exists() and not args.no_open:
                from urllib.parse import urlsplit
                url = json.loads(access.read_text())["url"]
                parsed = urlsplit(url)
                if parsed.scheme == "http" and parsed.hostname == "127.0.0.1":
                    webbrowser.open(url)
            return
        store = Store(directory / "nexo.sqlite3")
        controller = SetupController(directory / "nexo.sqlite3", store.preferences(), store.set_preferences)
        store.seed(Path(__file__).parent / "knowledge" / "starter.md")
        server = make_server(controller.config, store, args.port, controller=controller)
        url = f"http://127.0.0.1:{server.server_port}/#token={server.access_token}"
        access.write_text(json.dumps({"url": url}), encoding="utf-8")
        if sys.platform != "win32":
            access.chmod(0o600)
        if sys.stdout:
            print("Nexo 7 — keep the launcher running. Use Quit Nexo in the interface to exit.", flush=True)
            print(url, flush=True)
        if not args.no_open:
            webbrowser.open(url)
        if controller.preferences["auto_start"]:
            controller.start(cpu_only=controller.preferences["cpu_only"], language=controller.preferences["response_language"])
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            try:
                controller.close()
            finally:
                store.close()
                access.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
