from contextlib import closing
import json
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from nexo7.config import Config
from nexo7.lan_companion import Companion,private_host
from nexo7.trust import Trust

class CompanionBrowserTests(unittest.TestCase):
    def test_host_policy(self):
        for host in ('127.0.0.1','192.168.1.10','10.2.3.4'):self.assertTrue(private_host(host))
        for host in ('example.com','8.8.8.8','0.0.0.0','169.254.169.254','100.64.0.1'):self.assertFalse(private_host(host))

    def test_browser_auth_scopes_and_stop(self):
        with closing(Trust()) as trust:
            controller=SimpleNamespace(config=Config(provider='native',model='qwen3.5:0.8b'),operation=threading.Lock())
            companion=Companion(controller,trust)
            with self.assertRaises(ValueError):companion.start({})
            trust.set_scope('network.companion',True)
            with patch('nexo7.lan_companion.local_addresses',return_value=['127.0.0.1']):companion.start({'consent':True})
            port=companion.server.server_port;key=companion.key;base=f'http://127.0.0.1:{port}'
            def ask(path,body=None,token=key,origin=None):
                headers={'Content-Type':'application/json','X-Nexo-Companion':token}
                if origin:headers['Origin']=origin
                return urlopen(Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=3)
            try:
                with ask('/') as result:self.assertIn(b'Nexo companion',result.read())
                for path,token,origin in [('/chat','wrong',None),('/chat',key,'https://evil.example'),('/api/trust',key,None)]:
                    with self.assertRaises(HTTPError) as error:ask(path,{'message':'hola'},token,origin)
                    self.assertIn(error.exception.code,(401,403,404))
                with ask('/chat',{'message':'Hola, ¿cómo estás?'}) as response:
                    result=json.load(response)
                self.assertEqual(result['stats']['model_calls'],0)
                self.assertIn('listo para ayudarte',result['answer'])
                trust.set_scope('chat.use',False)
                with self.assertRaises(HTTPError):ask('/chat',{'message':'hola'})
                trust.set_scope('chat.use',True)
                trust.set_scope('network.companion',False)
                with self.assertRaises(HTTPError):ask('/chat',{'message':'hola'})
                trust.set_scope('network.companion',True)
                with self.assertRaises(HTTPError):ask('/chat',{'message':'hola','tools':['read_files']})
            finally:companion.stop()
            self.assertFalse(companion.snapshot()['running']);self.assertEqual(companion.key,'');self.assertEqual(companion.urls,[])
