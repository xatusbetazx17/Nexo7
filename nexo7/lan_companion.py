"""Optional private-LAN browser relay. Never exposes the desktop admin API."""
import hmac
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import socket
import threading
from urllib.parse import urlsplit


def private_host(value):
    try:
        address = ipaddress.ip_address(value)
        return address.version == 4 and (address.is_loopback or any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')))
    except ValueError:
        return False


def local_addresses():
    addresses = {'127.0.0.1'}
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))  # Route selection only; no packet is sent.
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in addresses if private_host(a))


class Companion:
    def __init__(self, controller, trust):
        self.controller, self.trust = controller, trust
        self.lock = threading.RLock()
        self.readers = threading.BoundedSemaphore(2)
        self.server = None
        self.key = ''
        self.urls = []

    def snapshot(self):
        with self.lock:
            return {'running': self.server is not None, 'urls': list(self.urls),
                    'notice': 'Same trusted home Wi-Fi only. This connection uses HTTP, not encryption. Do not send secrets. Keep Nexo and this PC awake. Stopping revokes the link.'}

    def stop(self):
        with self.lock:
            server = self.server
            self.server = None
            self.key = ''
            self.urls = []
        if server:
            server.shutdown()
            server.server_close()
        return self.snapshot()

    def start(self, body):
        if body.get('consent') is not True:
            raise ValueError('Confirm use on your trusted private Wi-Fi')
        with self.lock:
            if self.server: return self.snapshot()
            self.key = secrets.token_urlsafe(32)
            allowed = local_addresses()
            owner = self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def send(self, status, value, mime='application/json'):
                    data = value if isinstance(value, bytes) else json.dumps(value).encode()
                    self.send_response(status)
                    for key, val in {'Content-Type':mime,'Content-Length':str(len(data)), 'Cache-Control':'no-store',
                                     'Referrer-Policy':'no-referrer', 'X-Content-Type-Options':'nosniff',
                                     'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'"}.items():
                        self.send_header(key, val)
                    self.end_headers()
                    self.wfile.write(data)
                def valid(self, auth=False):
                    hosts = {a+':'+str(self.server.server_port) for a in allowed}
                    if not private_host(self.client_address[0]) or self.headers.get('Host') not in hosts:
                        self.send(403, {'error':'Private network access only'});return False
                    if self.headers.get('Origin') not in (None, 'http://'+self.headers.get('Host','')):
                        self.send(403, {'error':'Origin not allowed'});return False
                    if auth and (not owner.key or not hmac.compare_digest(self.headers.get('X-Nexo-Companion',''), owner.key)):
                        self.send(401, {'error':'Open the current private link from Nexo Settings'});return False
                    return True
                def do_GET(self):
                    if not self.valid(): return
                    paths={'/media-studio.js':('media-studio.js','text/javascript'),'/':('companion.html','text/html; charset=utf-8'),'/companion.js':('companion.js','text/javascript'),'/companion.css':('companion.css','text/css')}
                    item=paths.get(urlsplit(self.path).path)
                    if not item:return self.send(404,{'error':'Not found'})
                    return self.send(200,(Path(__file__).parent/'web'/item[0]).read_bytes(),item[1])
                def do_POST(self):
                    if not owner.readers.acquire(blocking=False):return self.send(429,{'error':'Too many requests. Try again shortly.'})
                    try:self.chat_request()
                    finally:owner.readers.release()
                def chat_request(self):
                    if not self.valid(True):return
                    if urlsplit(self.path).path!='/chat':return self.send(404,{'error':'Not found'})
                    try:
                        if self.headers.get('Content-Type')!='application/json':raise ValueError('JSON required')
                        size=int(self.headers.get('Content-Length','0'))
                        if not 1<=size<=5_400_000:raise ValueError('Request too large')
                        body=json.loads(self.rfile.read(size))
                        if not isinstance(body,dict) or set(body)-{'message','images','language'}:raise ValueError('Unsupported fields')
                        if not owner.controller.operation.acquire(blocking=False):return self.send(429,{'error':'The PC is busy. Try again shortly.'})
                        try:
                            from .vision import reply
                            result=owner.trust.run('companion.reply',reply,owner.controller.config,body,require_images=False)
                        finally:owner.controller.operation.release()
                        self.send(200,result)
                    except (ValueError, TypeError, json.JSONDecodeError):self.send(400,{'error':'Check your question, selected model and image size. Start the local model on the PC first.'})
                    except Exception:self.send(503,{'error':'Local reply failed. Check Nexo on the PC.'})
            class Server(ThreadingHTTPServer):
                daemon_threads=True
                def get_request(self):
                    connection,address=super().get_request();connection.settimeout(15);return connection,address
            self.server=Server(('0.0.0.0',0),Handler)
            self.urls=['http://'+a+':'+str(self.server.server_port)+'/#key='+self.key for a in allowed if a!='127.0.0.1']
            threading.Thread(target=self.server.serve_forever,daemon=True,name='nexo-companion').start()
            return self.snapshot()
