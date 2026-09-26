from .trust import guarded
"""Opt-in, bounded Internet lookup and expiring local source memory.

Only fixed provider endpoints are contacted. Result URLs are references, never fetched.
"""
from datetime import datetime, timezone
from html import unescape
import ipaddress
import json
import os
import re
import threading
import time
import unicodedata
from urllib.parse import quote, urlencode, urlsplit
from .net import fetch_json, TransportError

LANGUAGES = {'en','es','pt','fr','de','it','nl','pl','uk','ru','ar','hi','ja','ko','zh','tr','sv','id','vi'}
TTL = 7 * 86400
MAX_SEARCHES = 100


def public_url(value):
    if not isinstance(value,str) or len(value)>2000 or any(ord(c)<33 for c in value):return False
    try:
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):return False
        host=u.hostname.lower()
        if '.' not in host or host.endswith(('.localhost','.local','.internal','.test','.invalid')):return False
        try:return ipaddress.ip_address(host).is_global
        except ValueError:return True
    except ValueError:return False


def clean(value, limit):
    return unescape(re.sub('<[^>]*>','',str(value)))[:limit].strip()


def current_query(query):
    return bool(re.search(r'\b(today|latest|current|now|news|price|prices|weather|hoy|ahora|actual|actuales|últim[oa]s?|noticias|precio|precios|clima)\b',query,re.I))


class WebResearch:
    def __init__(self, store, transport=None, clock=time.time):
        self.store,self.transport,self.clock=store,transport or fetch_json,clock
        self.lock=threading.RLock()
        self.key=os.environ.get('BRAVE_SEARCH_API_KEY','')
        self.storage_rights=False
        with store.lock,store.db:
            store.db.executescript('''
            CREATE TABLE IF NOT EXISTS web_searches(key TEXT PRIMARY KEY,query TEXT,provider TEXT,language TEXT,retrieved REAL,expires REAL);
            CREATE TABLE IF NOT EXISTS web_sources(id INTEGER PRIMARY KEY AUTOINCREMENT,search_key TEXT,title TEXT,url TEXT,text TEXT,retrieved REAL,expires REAL,provider TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS web_index USING fts5(source_id UNINDEXED,title,text,tokenize='unicode61 remove_diacritics 2');
            ''')

    def set_key(self,key,storage_rights=False):
        if not isinstance(key,str) or len(key)>512 or any(ord(c)<33 or ord(c)>126 for c in key):
            raise ValueError('Invalid search key')
        if type(storage_rights) is not bool:raise ValueError('Storage rights must be boolean')
        with self.lock:self.key,self.storage_rights=key,storage_rights
        return {'brave_configured':bool(key),'storage_rights':storage_rights}

    def status(self):
        with self.lock:ready=bool(self.key)
        return {'brave_configured':ready,'storage_rights':self.storage_rights,'providers':['wikipedia','brave'],'sources':self.list_sources(),
                'reuse_days':7,'automatic_upload':False}

    @staticmethod
    def _source(row):
        return {'id':'W'+str(row['id']),'title':row['title'],'text':row['text'],'url':row['url'],
                'source':row['provider']+' excerpt; not independently verified',
                'retrieved_at':datetime.fromtimestamp(row['retrieved'],timezone.utc).isoformat(),
                'expires_at':datetime.fromtimestamp(row['expires'],timezone.utc).isoformat()}

    def list_sources(self):
        with self.store.lock:
            rows=self.store.db.execute('SELECT * FROM web_sources ORDER BY retrieved DESC,id DESC').fetchall()
        return [{**self._source(r),'expired':r['expires']<=self.clock()} for r in rows]

    @guarded("memory_write")
    def delete(self,ident=None):
        if ident is not None and (not isinstance(ident,str) or not re.fullmatch(r'W\d+',ident)):
            raise ValueError('Invalid web source ID')
        s=self.store
        with s.lock,s.db:
            if ident is None:
                s.db.execute('DELETE FROM web_sources');s.db.execute('DELETE FROM web_index');s.db.execute('DELETE FROM web_searches')
            else:
                row=s.db.execute('SELECT search_key FROM web_sources WHERE id=?',(int(ident[1:]),)).fetchone()
                if not row:return False
                # Invalidate exact-query reuse after any source is removed; other sources remain searchable.
                s.db.execute('DELETE FROM web_searches WHERE key=?',(row[0],))
                s.db.execute('DELETE FROM web_index WHERE source_id=?',(int(ident[1:]),))
                s.db.execute('DELETE FROM web_sources WHERE id=?',(int(ident[1:]),))
            s._changed()
        return True

    @guarded("memory_read")
    def recall(self,query,limit=2):
        if current_query(query):return []
        terms=[t for t in re.findall(r'\w+',query.casefold()) if len(t)>2][:12]
        if not terms:return []
        match=' OR '.join('"'+t+'"' for t in terms)
        with self.store.lock:
            rows=self.store.db.execute('SELECT s.* FROM web_index w JOIN web_sources s ON s.id=w.source_id '
                'WHERE web_index MATCH ? AND s.expires>? ORDER BY bm25(web_index) LIMIT ?',
                (match,self.clock(),min(4,max(1,limit)))).fetchall()
        return [self._source(r) for r in rows]

    def _forget_search(self,key):
        self.store.db.execute('DELETE FROM web_index WHERE source_id IN (SELECT id FROM web_sources WHERE search_key=?)',(key,))
        self.store.db.execute('DELETE FROM web_sources WHERE search_key=?',(key,))
        self.store.db.execute('DELETE FROM web_searches WHERE key=?',(key,))

    @guarded("web_lookup")
    def lookup(self,query,*,provider='wikipedia',language='en',remember=False,refresh=False,private=False):
        if not isinstance(query,str) or not 2<=len(query.strip())<=500 or len(query.split())>75:
            raise ValueError('Search requires 2 to 500 characters and at most 75 words; use a short topic')
        if provider not in {'wikipedia','brave'}:raise ValueError('Unknown web provider')
        if language not in LANGUAGES:raise ValueError('Choose a supported search language')
        if any(type(v) is not bool for v in (remember,refresh,private)):raise ValueError('Search options must be boolean')
        if provider=='brave' and remember and not private and not self.storage_rights:
            raise ValueError('Saving Brave results requires a plan with storage rights; confirm this in search settings or uncheck Remember')
        if remember and not private:
            self.store.trust.run('web_save', lambda: None)
        query=query.strip()
        norm=' '.join(unicodedata.normalize('NFKC',query).casefold().split())
        key=self.store.cache_key([provider,language,norm])
        refresh=refresh or current_query(query)
        if not refresh:
            with self.store.lock:
                row=self.store.db.execute('SELECT 1 FROM web_searches WHERE key=? AND expires>?',(key,self.clock())).fetchone()
                rows=self.store.db.execute('SELECT * FROM web_sources WHERE search_key=? ORDER BY id',(key,)).fetchall() if row else []
            if rows:return {'sources':[self._source(r) for r in rows],'reused':True,'network_requests':0,'saved':False}
        from .privacy import check_outbound
        check_outbound(query)
        with self.lock:api_key=self.key
        if provider=='brave' and not api_key:raise ValueError('Add your Brave Search API key in My knowledge, or choose Wikipedia')
        now=self.clock()
        headers={'User-Agent':'Nexo7/0.7 (https://github.com/xatusbetazx17/Nexo7)','Accept':'application/json'}
        if provider=='wikipedia':
            params={'action':'query','format':'json','generator':'search','gsrsearch':query,'gsrnamespace':0,'gsrlimit':3,
                    'prop':'extracts','exintro':1,'explaintext':1,'exchars':1000,'exlimit':3}
            data=self.transport('https://'+language+'.wikipedia.org/w/api.php?'+urlencode(params),headers=headers,timeout=20,max_bytes=500000)
            if 'error' in data:raise TransportError('Wikipedia could not complete this query')
            query_data=data.get('query',{})
            if not isinstance(query_data,dict):raise TransportError('Invalid encyclopedia results')
            pages=query_data.get('pages',{})
            if not isinstance(pages,dict):raise TransportError('Invalid encyclopedia results')
            raw=[{'title':p.get('title',''),'url':'https://'+language+'.wikipedia.org/wiki/'+quote(str(p.get('title','')).replace(' ','_'),safe=''),
                  'text':p.get('extract','')} for p in list(pages.values())[:3] if isinstance(p,dict)]
        else:
            headers['X-Subscription-Token']=api_key
            if refresh:headers['Cache-Control']='no-cache'
            params={'q':query,'count':3,'result_filter':'web','text_decorations':'false'}
            # Brave uses a distinct code for simplified Chinese.
            params['search_lang']='zh-hans' if language=='zh' else language
            data=self.transport('https://api.search.brave.com/res/v1/web/search?'+urlencode(params),headers=headers,timeout=20,max_bytes=500000)
            web_data=data.get('web',{})
            if not isinstance(web_data,dict):raise TransportError('Invalid web search results')
            results=web_data.get('results',[])
            if not isinstance(results,list):raise TransportError('Invalid web search results')
            raw=[{'title':r.get('title',''),'url':r.get('url',''),'text':r.get('description','')} for r in results[:3] if isinstance(r,dict)]
        sources=[];seen=set()
        for item in raw:
            if not isinstance(item['title'],str) or not isinstance(item['text'],str):continue
            if not public_url(item['url']) or item['url'] in seen:continue
            title,text=clean(item['title'],250),clean(item['text'],1000)
            if not title or not text:continue
            seen.add(item['url']);sources.append({'id':'W'+str(len(sources)+1),'title':title,'text':text,'url':item['url'],
                'source':provider+' excerpt; not independently verified','retrieved_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                'expires_at':datetime.fromtimestamp(now+TTL,timezone.utc).isoformat()})
        saved=False
        if remember and not private and sources:
            s=self.store
            with s.lock,s.db:
                self._forget_search(key)
                s.db.execute('INSERT INTO web_searches VALUES(?,?,?,?,?,?)',(key,query,provider,language,now,now+TTL))
                for source in sources:
                    cursor=s.db.execute('INSERT INTO web_sources(search_key,title,url,text,retrieved,expires,provider) VALUES(?,?,?,?,?,?,?)',
                        (key,source['title'],source['url'],source['text'],now,now+TTL,provider))
                    ident=cursor.lastrowid;source['id']='W'+str(ident)
                    s.db.execute('INSERT INTO web_index VALUES(?,?,?)',(ident,source['title'],source['text']))
                # Orphaned groups (from individual deletion) count toward the same bounded capacity.
                groups=s.db.execute('SELECT search_key FROM web_sources GROUP BY search_key ORDER BY MAX(retrieved) DESC,MAX(id) DESC').fetchall()
                for row in groups[MAX_SEARCHES:]:self._forget_search(row[0])
                s._changed();saved=True
        return {'sources':sources,'reused':False,'network_requests':1,'saved':saved}
