import argparse
import json
from pathlib import Path
import sys
import webbrowser
from dataclasses import replace
from .config import Config, load_config
from .engine import Engine
from .server import make_server
from .store import Store


def main():
    if len(sys.argv) == 1:
        from .desktop import main as desktop_main
        return desktop_main()
    parser = argparse.ArgumentParser(description="Nexo 7: independent personal assistant")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--open", action="store_true")
    chat = sub.add_parser("chat")
    chat.add_argument("message")
    chat.add_argument("--mode", choices=["eco", "balanced", "deep", "research"], default="balanced")
    chat.add_argument("--session", default="terminal")
    chat.add_argument("--private", action="store_true")
    chat.add_argument("--language", default=None, help="auto, en, es or another language code")
    local = sub.add_parser("local", help="Start the adaptive runtime with a verifiable RAM limit")
    local.add_argument("--cpu", action="store_true", help="Use CPU only")
    local.add_argument("--open", action="store_true")
    local.add_argument("--port", type=int, default=8787)
    local.add_argument("--language", default="auto")
    local_plan = sub.add_parser("local-plan", help="Detect resources without downloading or starting models")
    local_plan.add_argument("--cpu", action="store_true")
    sub.add_parser("local-stop", help="Stop a legacy Docker runtime; native models stop with their app")
    sub.add_parser("local-status", help="Inspect a legacy Docker runtime; native status is in the app")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("file")
    ingest.add_argument("--title")
    args = parser.parse_args()
    if args.command == "local-plan":
        from .native_runtime import native_plan
        report = native_plan(args.cpu)
        report.update(runtime_prerequisites_ok=True, guard_active=False)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return
    if args.command == "local-stop":
        from .local_runtime import stop_local
        stop_local()
        print("Local runtime stopped; downloaded models retained.")
        return
    if args.command == "local-status":
        from .local_runtime import verify_runtime, runtime_metrics
        config = load_config(Path(args.config).resolve().parent / "config.local.toml")
        verify_runtime(config)
        print(json.dumps(runtime_metrics(config), indent=2))
        return
    if args.command == "local":
        from .native_runtime import start_native
        base = Path(args.config).resolve().parent
        # Validate response language before potentially downloading anything.
        language_config = Config(response_language=args.language)
        config, plan = start_native(base / "data/nexo.sqlite3", cpu_only=args.cpu)
        config = replace(config, response_language=language_config.response_language)
    else:
        config = load_config(args.config)
    store = Store(config.database)
    store.seed(Path(__file__).resolve().parent.parent / "knowledge" / "technology.md")
    try:
        if args.command in {"serve", "local"}:
            server = make_server(config, store, args.port)
            url = f"http://127.0.0.1:{server.server_port}/#token={server.access_token}"
            print("Nexo 7 — local server. Stop: Ctrl+C", flush=True)
            print("Provider: " + config.provider, flush=True)
            print("Private access (do not share this link): " + url, flush=True)
            if args.open:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "chat":
            result = Engine(config, store).chat(args.message, session=args.session, mode=args.mode, private=args.private, language=args.language)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            p = Path(args.file)
            if p.suffix.lower() not in {".md", ".txt", ".csv", ".json"} or p.stat().st_size > 500000:
                raise ValueError("Import a text file of at most 500 KB")
            print(store.add_document(args.title or p.name, p.read_text(encoding="utf-8"), p.name))
    finally:
        store.close()
        if args.command == "local":
            from .native_runtime import stop_native
            stop_native(config)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print("Nexo 7: " + str(exc), file=sys.stderr)
        sys.exit(1)
