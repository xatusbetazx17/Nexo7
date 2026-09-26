"""Read-only Google connectors: external browser, PKCE and an encrypted local vault."""
from abc import ABC, abstractmethod
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit, parse_qs
import urllib.request
from .net import NoRedirect

GOOGLE = {
    'calendar': {'scope':'https://www.googleapis.com/auth/calendar.events.readonly','permission':'google.calendar.read'},
    'gmail': {'scope':'https://www.googleapis.com/auth/gmail.readonly','permission':'google.gmail.read'},
}


def request(url, *, form=None, token=None):
    # The caller selects only fixed Google endpoints, never content-provided URLs.
    headers={'Accept':'application/json','User-Agent':'Nexo7/0.18'}
    data=None
    if form is not None:
        data=urlencode(form).encode();headers['Content-Type']='application/x-www-form-urlencoded'
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,data=data,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=8) as response:
            raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError()
        return json.loads(raw) if raw else {}
    except Exception:raise ValueError('Google request failed. Check the connection, API configuration or reconnect this account.') from None


class Connector(ABC):
    """Future connectors must declare scopes and route all reads through this gate."""
    def __init__(self,service,vault,trust,transport=request):
        if service not in GOOGLE:raise ValueError('Unknown connector')
        self.service,self.vault,self.trust,self.transport=service,vault,trust,transport
        self.scope=GOOGLE[service]['scope'];self.permission=GOOGLE[service]['permission']
        self.lock=threading.RLock();self.stopping=threading.Event()
    def _token(self):
        if self.stopping.is_set():raise ValueError('Connector is closing')
        record=self.vault.get('google.'+self.service)
        if not record or not record.get('enabled'):raise ValueError('Connect and enable this account first')
        if record['expires']<=time.time()+60:
            if not record.get('refresh_token'):raise ValueError('Reconnect this account to renew access')
            client=self.vault.get('google.client')
            with self.trust.action('google.refresh.'+self.service):
                result=self.transport('https://oauth2.googleapis.com/token',form={
                    'client_id':client['client_id'],'client_secret':client['client_secret'],
                    'refresh_token':record['refresh_token'],'grant_type':'refresh_token'})
            self._validate_token(result)
            record.update(access_token=result['access_token'],expires=time.time()+min(int(result.get('expires_in',3600)),86400))
            self.vault.set('google.'+self.service,record)
        return record['access_token']
    def _validate_token(self,result):
        if not isinstance(result,dict) or not isinstance(result.get('access_token'),str) or not 1<=len(result['access_token'])<=10000:
            raise ValueError('Google returned an invalid access token')
        if result.get('token_type','Bearer').lower()!='bearer' or type(result.get('expires_in',3600)) is not int or not 0<result.get('expires_in',3600)<=86400:raise ValueError('Google returned invalid token metadata')
        scopes=set(result.get('scope',self.scope).split())
        if self.scope not in scopes or not scopes<={self.scope}:
            raise ValueError('Google returned unexpected scopes. Revoke this grant and connect using a dedicated desktop client.')
    @abstractmethod
    def read(self):pass


class GoogleReadOnly(Connector):
    def read(self):
        with self.trust.action('google.read.'+self.service),self.lock:
            token=self._token()
            if self.service=='calendar':
                now=datetime.now(timezone.utc)
                url='https://www.googleapis.com/calendar/v3/calendars/primary/events?'+urlencode({
                    'timeMin':now.isoformat(),'timeMax':(now+timedelta(days=7)).isoformat(),
                    'singleEvents':'true','orderBy':'startTime','maxResults':20})
                data=self.transport(url,token=token)
                return {'kind':'calendar','untrusted':True,'items':[
                    {'id':str(x.get('id',''))[:200],'title':str(x.get('summary','Untitled event'))[:300],
                     'start':x.get('start',{}).get('dateTime',x.get('start',{}).get('date','')),
                     'description':str(x.get('description',''))[:1000]}
                    for x in data.get('items',[])[:20] if isinstance(x,dict)],'retrieved_at':now.isoformat()}
            data=self.transport('https://gmail.googleapis.com/gmail/v1/users/me/messages?'+urlencode({'maxResults':10,'labelIds':'INBOX'}),token=token)
            items=[]
            for entry in data.get('messages',[])[:10]:
                identifier=entry.get('id','')
                if not isinstance(identifier,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,128}',identifier):continue
                # Recheck the permission on each network action, including mid-fetch revocation.
                with self.trust.action('google.message.gmail'):
                    token=self._token()
                    message=self.transport('https://gmail.googleapis.com/gmail/v1/users/me/messages/'+identifier+'?format=full',token=token)
                payload=message.get('payload',{})
                headers={str(h.get('name','')).lower():str(h.get('value',''))[:500] for h in payload.get('headers',[])[:100] if isinstance(h,dict)}
                names=[]
                def attachments(part,depth=0):
                    if depth>4 or not isinstance(part,dict):return
                    if part.get('filename'):names.append(str(part['filename'])[:180])
                    for child in part.get('parts',[])[:20]:attachments(child,depth+1)
                attachments(payload)
                items.append({'id':identifier,'subject':headers.get('subject','No subject'),
                    'from':headers.get('from',''),'date':headers.get('date',''),
                    'snippet':str(message.get('snippet',''))[:1000],'attachments':names[:30]})
            return {'kind':'gmail','untrusted':True,'items':items,'retrieved_at':datetime.now(timezone.utc).isoformat()}


class GoogleConnections:
    def __init__(self,vault,trust,transport=request):
        self.vault,self.trust,self.transport=vault,trust,transport
        self.connectors={s:GoogleReadOnly(s,vault,trust,transport) for s in GOOGLE}
        self.lock=threading.RLock();self.pending={};self.servers=[];self.last_error=''
    def status(self):
        result=[]
        for service,decl in GOOGLE.items():
            record=self.vault.get('google.'+service) if self.vault.status()['unlocked'] else None
            result.append({'name':service,'scope':decl['scope'],'permission':decl['permission'],
                'connected':bool(record),'enabled':bool(record and record.get('enabled')),
                'allowed':self.trust.allowed('google.read.'+service)})
        return {'vault':self.vault.status(),'connectors':result,'error':self.last_error}
    def configure(self,body):
        raw=body.get('client',{});client=raw.get('installed') if isinstance(raw,dict) else None
        if not isinstance(client,dict):raise ValueError('Upload a Google Desktop app OAuth client JSON file')
        identifier=client.get('client_id','');secret=client.get('client_secret','')
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{10,200}\.apps\.googleusercontent\.com',identifier):raise ValueError('Invalid desktop client ID')
        if not isinstance(secret,str) or not 1<=len(secret)<=300:raise ValueError('Invalid desktop client secret')
        self.vault.set('google.client',{'client_id':identifier,'client_secret':secret})
        return {'configured':True}
    def authorize(self,service):
        if service not in GOOGLE:raise ValueError('Unknown connector')
        with self.trust.action('google.connect.'+service),self.lock:
            client=self.vault.get('google.client')
            if not client:raise ValueError('Configure your desktop OAuth client first')
            self.close_pending()
            verifier=secrets.token_urlsafe(48);state=secrets.token_urlsafe(32)
            owner=self
            class Callback(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    parsed=urlsplit(self.path);query=parse_qs(parsed.query)
                    valid=(self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}' and parsed.path=='/'
                           and len(query.get('state',[]))==1 and secrets.compare_digest(query['state'][0],state))
                    if not valid:return self._reply(400,'Invalid sign-in callback. Return to Nexo and try again.')
                    try:
                        if len(query.get('code',[]))!=1 or len(query['code'][0])>4096:raise ValueError('Sign-in was declined or incomplete')
                        owner.complete(state,query['code'][0])
                        self._reply(200,'Connected. You can close this tab and return to Nexo.')
                    except Exception:
                        owner.last_error='Google connection did not complete. Check the vault, scopes and consent screen, then try again.'
                        self._reply(400,owner.last_error)
                def _reply(self,status,text):
                    data=text.encode();self.send_response(status);self.send_header('Content-Type','text/plain; charset=utf-8')
                    self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
                    self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            class CallbackServer(HTTPServer):
                def get_request(self):
                    sock,address=super().get_request();sock.settimeout(5);return sock,address
            server=CallbackServer(('127.0.0.1',0),Callback);server.timeout=1
            redirect=f'http://127.0.0.1:{server.server_port}'
            self.pending[state]={'service':service,'verifier':verifier,'redirect':redirect,'expires':time.monotonic()+300}
            stop=threading.Event();self.servers.append((server,stop))
            def wait():
                try:
                    while not stop.is_set() and time.monotonic()<self.pending.get(state,{}).get('expires',0):server.handle_request()
                finally:
                    server.server_close()
                    with self.lock:self.pending.pop(state,None)
            threading.Thread(target=wait,name='nexo-google-oauth',daemon=True).start()
            self.last_error=''
            url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({
                'client_id':client['client_id'],'redirect_uri':redirect,'response_type':'code',
                'scope':GOOGLE[service]['scope'],'access_type':'offline','prompt':'consent',
                'include_granted_scopes':'false','state':state,'code_challenge_method':'S256',
                'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()})
            return {'url':url,'expires_in':300}
    def complete(self,state,code):
        with self.lock:
            pending=self.pending.pop(state,None)
            if not pending or pending['expires']<time.monotonic():raise ValueError('Sign-in expired')
            service=pending['service'];client=self.vault.get('google.client')
            with self.trust.action('google.connect.'+service):
                result=self.transport('https://oauth2.googleapis.com/token',form={
                    'client_id':client['client_id'],'client_secret':client['client_secret'],'code':code,
                    'code_verifier':pending['verifier'],'redirect_uri':pending['redirect'],'grant_type':'authorization_code'})
                self.connectors[service]._validate_token(result)
                refresh=result.get('refresh_token','')
                if not isinstance(refresh,str) or not 1<=len(refresh)<=10000:raise ValueError('Google did not issue offline access; reconnect with consent')
                self.vault.set('google.'+service,{'enabled':True,'access_token':result['access_token'],
                    'refresh_token':refresh,'expires':time.time()+min(int(result.get('expires_in',3600)),86400)})
    def toggle(self,service,enabled):
        if service not in GOOGLE or type(enabled) is not bool:raise ValueError('Invalid connector setting')
        with self.connectors[service].lock:
            record=self.vault.get('google.'+service)
            if not record:raise ValueError('Connect this account first')
            record['enabled']=enabled;self.vault.set('google.'+service,record)
        return self.status()
    def revoke(self,service):
        if service not in GOOGLE:raise ValueError('Unknown connector')
        with self.connectors[service].lock:
            record=self.vault.get('google.'+service);revoked=True
            if record:
                try:
                    with self.trust.action('google.revoke'):
                        self.transport('https://oauth2.googleapis.com/revoke',form={'token':record.get('refresh_token') or record['access_token']})
                except Exception:revoked=False
                finally:self.vault.set('google.'+service,None)
        return {'removed_locally':True,'revoked_at_google':revoked,
            'message':'Disconnected.' if revoked else 'Removed locally. Google could not be reached; also remove access at myaccount.google.com/permissions.'}
    def close_pending(self):
        with self.lock:
            for server,stop in self.servers:stop.set()
            self.servers=[];self.pending.clear()
    def stop(self):
        for connector in self.connectors.values():connector.stopping.set()
        self.close_pending()
    def close(self):self.stop();self.vault.lock_now()
