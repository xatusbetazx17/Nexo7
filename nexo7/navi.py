"""Optional presence, reminders and connector coordination; no changes to inference."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from zoneinfo import ZoneInfo
from .vault import Vault
from .connectors import GoogleConnections
from .chips import Chips

DEFAULTS={'avatar':False,'voice':False,'voice_language':'en','scheduler':False,
          'briefing':False,'briefing_time':'08:00','timezone':'America/New_York',
          'briefing_calendar':False,'briefing_gmail':False,'briefing_note':''}


class NaviState:
    def __init__(self,path):
        self.lock=threading.RLock();self.db=sqlite3.connect(str(path),check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        if str(path)!=':memory:' and os.name!='nt':Path(path).chmod(0o600)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY,text TEXT NOT NULL,due REAL NOT NULL,done INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,created REAL NOT NULL,seen INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS daily(day TEXT PRIMARY KEY);
        ''')
    def close(self):
        with self.lock:self.db.close()
    def settings(self):
        with self.lock:row=self.db.execute('SELECT body FROM settings WHERE id=1').fetchone()
        return {**DEFAULTS,**(json.loads(row[0]) if row else {})}
    def configure(self,updates):
        if not isinstance(updates,dict) or set(updates)-set(DEFAULTS):raise ValueError('Unknown Navi setting')
        values={**self.settings(),**updates}
        for k in ('avatar','voice','scheduler','briefing','briefing_calendar','briefing_gmail'):
            if type(values[k]) is not bool:raise ValueError('Navi switches must be boolean')
        if values['voice_language'] not in ('en','es'):raise ValueError('Choose English or Spanish for recognition')
        if not isinstance(values['briefing_time'],str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',values['briefing_time']):raise ValueError('Choose a valid morning time')
        if not isinstance(values['timezone'],str) or len(values['timezone'])>80:raise ValueError('Invalid time zone')
        try:ZoneInfo(values['timezone'])
        except Exception:raise ValueError('Choose a valid IANA time zone, such as America/New_York') from None
        if not isinstance(values['briefing_note'],str) or values['briefing_note'] and not re.fullmatch('[a-f0-9]{32}',values['briefing_note']):raise ValueError('Choose a saved note')
        with self.lock,self.db:self.db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)',(json.dumps(values),))
        return values
    def reminders(self,pending=False):
        with self.lock:return [dict(r) for r in self.db.execute('SELECT * FROM reminders '+('WHERE done=0 ' if pending else '')+'ORDER BY due LIMIT 100')]
    def add_reminder(self,text,due):
        if not isinstance(text,str) or not 1<=len(text.strip())<=500:raise ValueError('Reminder text must contain 1–500 characters')
        if type(due) not in (int,float) or not 0<due<32_503_680_000:raise ValueError('Invalid reminder time')
        with self.lock,self.db:
            if self.db.execute('SELECT COUNT(*) FROM reminders').fetchone()[0]>=100:raise ValueError('Remove an old reminder first (limit 100)')
            identifier=uuid.uuid4().hex;self.db.execute('INSERT INTO reminders(id,text,due) VALUES(?,?,?)',(identifier,text.strip(),due))
        return {'id':identifier,'text':text.strip(),'due':due}
    def remove_reminder(self,identifier):
        with self.lock,self.db:self.db.execute('DELETE FROM reminders WHERE id=?',(identifier,))
    def notify(self,identifier,title,body):
        with self.lock,self.db:
            self.db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,0)',(identifier,title[:150],body[:4000],time.time()))
            self.db.execute('DELETE FROM notifications WHERE id NOT IN (SELECT id FROM notifications ORDER BY created DESC LIMIT 100)')
    def notifications(self):
        with self.lock:return [dict(r) for r in self.db.execute('SELECT * FROM notifications ORDER BY created DESC LIMIT 50')]
    def seen(self,identifier):
        with self.lock,self.db:self.db.execute('UPDATE notifications SET seen=1 WHERE id=?',(identifier,))


class Navi:
    def __init__(self,root,store,controller,web):
        self.root=Path(root);self.store,self.controller=store,controller
        self.state=NaviState(self.root/'navi.sqlite3');self.vault=Vault(self.root/'connector-vault.json')
        self.google=GoogleConnections(self.vault,store.trust)
        self.chips=Chips(self.root/'chips',store,web)
        from .voice import Voice
        self.voice=Voice(self.root,store.trust,controller)
        self.stop=threading.Event();self.lock=threading.RLock();self.busy=0;self.listening_until=0;self.happy_until=0
        self.overlay=None;self.error='';self.closed=False;self.last_activity=time.monotonic()
        self.thread=threading.Thread(target=self._loop,name='nexo-reminders',daemon=True);self.thread.start()
    def enter(self):
        with self.lock:self.busy+=1;self.last_activity=time.monotonic()
    def leave(self):
        with self.lock:self.busy=max(0,self.busy-1);self.happy_until=time.monotonic()+4;self.last_activity=time.monotonic()
    def presence(self):
        with self.lock:
            now=time.monotonic()
            phase='thinking' if self.busy or self.controller.operation.locked() else 'listening' if now<self.listening_until else 'happy' if now<self.happy_until else 'sleeping' if now-self.last_activity>180 else 'idle'
        return {'state':phase,'enabled':self.state.settings()['avatar'] and self.store.trust.allowed('presence.show'),
                'unread':sum(not n['seen'] for n in self.state.notifications()),'error':self.error}
    def start_overlay(self):
        if self.overlay and self.overlay.poll() is None:return
        if not self.store.trust.allowed('presence.show'):return
        access=self.root/'access.json'
        command=([sys.executable,'--avatar-worker'] if getattr(sys,'frozen',False) else [sys.executable,'-m','nexo7.avatar'])+[str(access)]
        env=dict(os.environ);env['PYINSTALLER_RESET_ENVIRONMENT']='1'
        with self.store.trust.action('presence.show'):
            self.overlay=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    def configure(self,body):
        updates=body.get('settings',{})
        for key,action in [('avatar','presence.show'),('voice','voice.transcribe'),('scheduler','reminder.deliver')]:
            if updates.get(key) is True and not self.store.trust.allowed(action):raise ValueError('Enable this module’s permission in Trust and permissions first')
        values=self.state.configure(updates)
        if values['avatar']:self.start_overlay()
        elif self.overlay and self.overlay.poll() is None:self.overlay.terminate()
        return values
    def briefing(self):
        with self.store.trust.action('briefing.create'):
            settings=self.state.settings();lines=[]
            if settings['briefing_note']:
                with self.store.trust.action('memory_read'),self.store.lock:
                    row=self.store.db.execute('SELECT title,content FROM documents WHERE id=?',(settings['briefing_note'],)).fetchone()
                    if row:lines.append('Saved note — '+row['title']+': '+row['content'][:500])
            else:
                if self.store.trust.allowed('memory_read'):lines.append(str(len(self.store.documents()))+' saved notes available in your Library.')
            lines.append(str(len(self.state.reminders(pending=True)))+' pending reminders.')
            for service,key in [('calendar','briefing_calendar'),('gmail','briefing_gmail')]:
                if not settings[key]:continue
                try:
                    result=self.google.connectors[service].read()
                    for item in result['items'][:5]:
                        if service=='calendar':lines.append('Calendar — '+item['title']+' · '+item['start'])
                        else:
                            check=self.chips.run('security-watch',item)
                            lines.append('Email — '+item['subject']+(' · Review suggested' if check['flags'] else ''))
                except Exception:lines.append(service.title()+' unavailable: check its permission, vault and connection.')
            lines.append('External titles are untrusted data. No links, attachments or instructions were executed.')
            text='\n'.join(lines)
            self.state.notify('briefing-'+uuid.uuid4().hex,'Your morning briefing',text)
            return {'text':text,'untrusted_external_content':True}
    def tick(self,now=None):
        settings=self.state.settings()
        if not settings['scheduler'] or not self.store.trust.allowed('reminder.deliver'):return
        now=time.time() if now is None else now
        for reminder in self.state.reminders(pending=True):
            if reminder['due']>now:continue
            with self.store.trust.action('reminder.deliver'),self.state.lock,self.state.db:
                self.state.db.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,0)',('reminder-'+reminder['id'],'Reminder',reminder['text'],now))
                self.state.db.execute('UPDATE reminders SET done=1 WHERE id=?',(reminder['id'],))
        local=datetime.fromtimestamp(now,ZoneInfo(settings['timezone']));day=local.date().isoformat()
        if settings['briefing'] and local.strftime('%H:%M')>=settings['briefing_time']:
            with self.state.lock:done=self.state.db.execute('SELECT 1 FROM daily WHERE day=?',(day,)).fetchone()
            if not done:
                self.briefing()
                with self.state.lock,self.state.db:self.state.db.execute('INSERT OR IGNORE INTO daily VALUES(?)',(day,))
    def _loop(self):
        while not self.stop.wait(15):
            try:self.tick()
            except Exception:self.error='A scheduled action could not finish. Check its permissions and connector settings.'
    def snapshot(self):
        return {'settings':self.state.settings(),'presence':self.presence(),'reminders':self.state.reminders(),
                'notifications':self.state.notifications(),'google':self.google.status(),'voice':self.voice.status(),'chips':self.chips.list()}
    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
        self.stop.set();self.google.stop();self.thread.join(timeout=30)
        if self.overlay and self.overlay.poll() is None:
            self.overlay.terminate()
            try:self.overlay.wait(timeout=3)
            except subprocess.TimeoutExpired:self.overlay.kill()
        self.voice.close();self.google.close();self.state.close()
