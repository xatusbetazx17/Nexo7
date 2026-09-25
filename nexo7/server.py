from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit, parse_qs
from .engine import Engine
from .net import TransportError


def make_server(config, store, port=8787, token=None, engine=None, controller=None):
    token = token or secrets.token_urlsafe(32)
    slots = threading.BoundedSemaphore(1 if config.provider == "ollama" else 2)
    requests = deque()
    request_lock = threading.Lock()
    web = Path(__file__).parent / "web"
    from .workspace import Workspace
    workspace = Workspace(Path(config.database).resolve().parent / "workspace") if controller else None

    from .web_research import WebResearch
    web_research = WebResearch(store)
    engine = engine or Engine(config, store, workspace=workspace, web=web_research)
    from .learning import Learning, validate_pack, contribution
    learning = Learning(store)
    from .task_agent import TaskAgent
    agent = TaskAgent(store, workspace) if workspace else None
    from .telegram_bridge import BridgeController
    telegram = BridgeController(Path(config.database).resolve().parent / "access.json") if controller else None
    import_slots = threading.BoundedSemaphore(1)
    creative_slots = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        server_version = "Nexo7"

        def log_message(self, *args):
            pass  # No prompts, tokens, credentials or query strings in access logs.

        def _send(self, code, value, content_type="application/json; charset=utf-8"):
            data = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith("application/json") else value
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _allowed(self, api=False):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts:
                self._send(403, {"error": "Host not allowed"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {"http://" + h for h in hosts}:
                self._send(403, {"error": "Origin not allowed"})
                return False
            if api and not hmac.compare_digest(self.headers.get("X-Nexo-Key", ""), token):
                self._send(401, {"error": "Open the private access link from the Nexo launcher"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self._allowed(path.startswith("/api/")):
                return
            static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in static:
                name, mime = static[path]
                return self._send(200, (web / name).read_bytes(), mime)
            if path == "/api/status":
                active = controller.config if controller else config
                return self._send(200, {"name": "Nexo 7", "version": "0.15.0", "provider": active.provider,
                    "model": active.model or "No model connected", "fast_model": active.fast_model,
                    "deep_model": active.deep_model, "persist_history": active.persist_history,
                    "max_model_calls": active.max_model_calls, "max_output_tokens": active.max_output_tokens,
                    "research_network": active.research_network, "response_language": active.response_language,
                    "local_ram_limit_bytes": active.local_ram_limit_bytes if active.provider in {"native", "ollama"} else None,
                    "local_backend": active.local_backend if active.provider in {"native", "ollama"} else None,
                    "vision": active.provider == "native" and active.model == "lfm2-vl:450m", "desktop": controller is not None})
            if path == "/api/telegram" and telegram:
                return self._send(200, telegram.snapshot())
            if path == "/api/tasks" and agent:
                return self._send(200, {"tasks":agent.list()})
            if path == "/api/setup" and controller:
                return self._send(200, controller.snapshot())
            if path == "/api/web":
                return self._send(200, web_research.status())
            if path == "/api/learning/community":
                pack = json.loads((Path(__file__).parent / "knowledge" / "community.json").read_text(encoding="utf-8"))
                return self._send(200, {"format": "nexo-learning-v1", "entries": validate_pack(pack)})
            if path == "/api/learning":
                return self._send(200, {"entries": learning.entries(), "metrics": learning.metrics(), "weight_training": False})
            if path == "/api/preferences":
                return self._send(200, store.preferences())
            if path == "/api/artifacts" and workspace:
                return self._send(200, {"artifacts": workspace.list()})
            if path.startswith("/api/artifacts/") and workspace:
                try:
                    return self._send(200, workspace.read(path.rsplit("/",1)[1]))
                except (ValueError, OSError):
                    return self._send(404, {"error": "Artifact not found"})
            if path == "/api/documents":
                return self._send(200, {"documents": store.documents()})
            if path == "/api/history":
                session = parse_qs(urlsplit(self.path).query).get("session", [""])[0]
                return self._send(200, {"messages": store.history(session, 100)})
            self._send(404, {"error": "Unknown route"})

        def do_POST(self):
            if not self._allowed(True):
                return
            with request_lock:
                now = time.monotonic()
                while requests and requests[0] < now - 60:
                    requests.popleft()
                if len(requests) >= 60:
                    return self._send(429, {"error": "Too many requests; wait one minute"})
                requests.append(now)
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 <= size <= (10_800_000 if urlsplit(self.path).path in ("/api/vision", "/api/relay") else 6_800_000 if urlsplit(self.path).path == "/api/import" else 500000):
                    return self._send(413, {"error": "Request too large or missing Content-Length"})
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self._send(415, {"error": "application/json is required"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("A JSON object is required")
                path = urlsplit(self.path).path
                if path == '/api/telegram/chats' and telegram:
                    return self._send(200, telegram.discover(body))
                if path == '/api/telegram/start' and telegram:
                    if controller.config.provider != 'native':raise ValueError('Start a local model first')
                    return self._send(202, telegram.start(body))
                if path == '/api/telegram/stop' and telegram:
                    return self._send(202, telegram.stop())
                if path in ('/api/vision', '/api/relay') and controller:
                    if not controller.operation.acquire(blocking=False):return self._send(429, {'error':'Another local model operation is running'})
                    try:
                        from .vision import reply
                        result = reply(controller.config, body, require_images=path == '/api/vision')
                    finally:controller.operation.release()
                    return self._send(200, result)
                if path == '/api/tasks/plan' and agent:
                    if not controller.operation.acquire(blocking=False):return self._send(429,{'error':'Another model operation is running'})
                    try:result=agent.plan(body.get('goal'),Engine(controller.config,store,workspace=workspace,web=web_research))
                    finally:controller.operation.release()
                    return self._send(200,result)
                if path == '/api/tasks' and agent:
                    return self._send(201, agent.create(body))
                if path.startswith('/api/tasks/') and agent:
                    parts = path.split('/')
                    if len(parts)!=5:raise ValueError('Invalid task action')
                    identifier,action=parts[3:]
                    if action=='run':
                        if not controller.operation.acquire(blocking=False):return self._send(429, {'error':'Another model/setup operation is running'})
                        try:result=agent.run(identifier,Engine(controller.config,store,workspace=workspace,web=web_research))
                        finally:controller.operation.release()
                    elif action=='edit':result=agent.edit(identifier,body.get('content'),body.get('expected_hash'))
                    elif action=='feedback':result=agent.feedback(identifier,body.get('text'))
                    elif action=='apply':result=agent.apply(identifier,body.get('proposal_id'))
                    elif action=='rollback':result=agent.rollback(identifier)
                    elif action=='cancel':result=agent.cancel(identifier)
                    else:raise ValueError('Unknown task action')
                    return self._send(200,result)
                if path == "/api/scenario":
                    active = controller.config if controller else config
                    if active.max_tool_calls < 1:
                        raise ValueError('Math tools are disabled')
                    from .scenarios import calculate
                    return self._send(200, calculate(body))
                if path == "/api/creative" and controller:
                    if not creative_slots.acquire(blocking=False):
                        return self._send(429, {"error": "Another creative render is running"})
                    try:
                        from .creative import render
                        result = render(body)
                    finally:
                        creative_slots.release()
                    return self._send(200, result)
                if path == "/api/export/document":
                    from .doc_export import export_document
                    return self._send(200, export_document(body))
                if path == "/api/learning/from-source":
                    from .reviewed_sources import admit
                    return self._send(201, admit(learning, web_research, body))
                if path == "/api/math":
                    active = controller.config if controller else config
                    if active.max_tool_calls < 1:
                        raise ValueError("Math tools are disabled")
                    from .advanced_math import solve
                    return self._send(200, solve(body))
                if path == "/api/contributions/prepare":
                    from .contributions import prepare
                    return self._send(200, prepare(web_research, body))
                if path == "/api/web/key":
                    return self._send(200, web_research.set_key(body.get("key"),body.get("storage_rights",False)))
                if path == "/api/learning/preview":
                    return self._send(200, {"entries": validate_pack(body.get("pack"))})
                if path == "/api/learning/import":
                    return self._send(201, learning.import_pack(body.get("pack"), body.get("consent")))
                if path == "/api/learning/export":
                    return self._send(200, learning.export(body.get("ids")))
                if path == "/api/learning/contribute":
                    return self._send(200, contribution(body.get("entry"), body.get("consent")))
                if path == "/api/import":
                    if not import_slots.acquire(blocking=False):
                        return self._send(429,{"error":"Another document import is running"})
                    try:
                        from .documents import import_document
                        result = import_document(body.get("name"),body.get("data"))
                    finally: import_slots.release()
                    return self._send(200,result)
                if path == "/api/inspect" and workspace:
                    from .local_tools import inspect_file
                    return self._send(200,inspect_file(workspace,body.get("filename")))
                if path == "/api/preferences":
                    values = store.set_preferences(body)
                    if controller:
                        controller.preferences = values
                    return self._send(200, values)
                if path == "/api/feedback":
                    return self._send(201, store.record_feedback(body.get("question"), body.get("answer"), body.get("rating")))
                if path == "/api/artifacts" and workspace:
                    item = workspace.create(body.get("name"), body.get("content"))
                    from .local_tools import inspect_file
                    try:
                        item['verification'] = inspect_file(workspace, item['id'])
                    except ValueError as exc:
                        item['verification'] = {'error': str(exc), 'passed': False}
                    return self._send(201, item)
                if controller and path == "/api/setup/check":
                    if type(body.get("cpu_only", False)) is not bool:
                        raise ValueError("cpu_only must be a boolean")
                    return self._send(200, controller.check(body.get("cpu_only", False)))
                if controller and path == "/api/setup/switch":
                    return self._send(202, controller.start(cpu_only=body.get("cpu_only", False), language=body.get("language", "auto"), switch=True))
                if controller and path == "/api/setup/start":
                    return self._send(202, controller.start(cpu_only=body.get("cpu_only", False),
                                                           language=body.get("language", "auto")))
                if controller and path == "/api/setup/cancel":
                    controller.cancel.set()
                    return self._send(202, {"cancel_requested": True})
                if controller and path == "/api/shutdown":
                    controller.cancel.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return self._send(202, {"stopping": True})
                if path == "/api/chat":
                    if type(body.get("private", False)) is not bool:
                        raise ValueError("private must be a boolean")
                    chat_lock = controller.operation if controller else slots
                    if not chat_lock.acquire(blocking=False):
                        return self._send(429, {"error": "The assistant is busy; wait for the current operation"})
                    try:
                        active_engine = Engine(controller.config, store, workspace=workspace, web=web_research) if controller else engine
                        result = active_engine.chat(body.get("message"), session=body.get("session"), mode=body.get("mode", "balanced"), private=body.get("private", False), language=body.get("language"), web_provider=body.get("web_provider", "wikipedia"), web_language=body.get("web_language", "en"), remember_web=body.get("remember_web", False), refresh_web=body.get("refresh_web", False), synthesize_web=body.get("synthesize_web", True), allow_internet=body.get("allow_internet", False))
                    finally:
                        chat_lock.release()
                    return self._send(200, result)
                if path == "/api/documents":
                    doc_id = store.add_document(body.get("title"), body.get("content"), body.get("source", "personal"))
                    return self._send(201, {"id": doc_id})
                self._send(404, {"error": "Unknown route"})
            except (ValueError, TypeError, UnicodeError) as exc:
                self._send(400, {"error": str(exc)[:300]})
            except TransportError as exc:
                self._send(502, {"error": str(exc)})
            except Exception:
                self._send(500, {"error": "Internal error; check the project configuration"})

        def do_DELETE(self):
            if not self._allowed(True):
                return
            path = urlsplit(self.path).path
            if path.startswith('/api/tasks/') and agent:
                try:return self._send(200,agent.delete(path.rsplit('/',1)[1]))
                except ValueError as exc:return self._send(400,{'error':str(exc)})
            if path == "/api/web":
                return self._send(200, {"deleted": web_research.delete()})
            if path.startswith("/api/web/"):
                try:
                    return self._send(200, {"deleted": web_research.delete(path.rsplit("/",1)[1])})
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
            if path == "/api/learning-metrics":
                learning.clear_metrics()
                return self._send(200, {"deleted": True})
            if path.startswith("/api/learning/"):
                return self._send(200, {"deleted": learning.delete(path.rsplit("/", 1)[1])})
            if path.startswith("/api/artifacts/") and workspace:
                try:
                    return self._send(200, {"deleted": workspace.delete(path.rsplit("/",1)[1])})
                except (ValueError, OSError):
                    return self._send(404, {"error": "Artifact not found"})
            if path.startswith("/api/documents/"):
                return self._send(200, {"deleted": store.delete_document(path.rsplit("/", 1)[1])})
            if path.startswith("/api/history/"):
                store.delete_history(path.rsplit("/", 1)[1])
                return self._send(200, {"deleted": True})
            self._send(404, {"error": "Unknown route"})

    class LocalServer(ThreadingHTTPServer):
        daemon_threads = True
        def get_request(self):
            sock, address = super().get_request()
            sock.settimeout(15)
            return sock, address

    server = LocalServer(("127.0.0.1", port), Handler)
    server.telegram_controller = telegram
    server.access_token = token
    return server
