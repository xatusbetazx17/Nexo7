import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from nexo7.trust import Trust, PermissionDenied, ACTIONS, route_action
from nexo7.store import Store
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.server import make_server
from nexo7.tools import ToolBox, PubMed
from nexo7.telegram_bridge import Bridge, Settings
from nexo7.web_research import WebResearch


class TrustTests(unittest.TestCase):
    def test_identity_persists_and_key_never_leaves_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trust.sqlite3'
            trust=Trust(path)
            identity=trust.identity()
            secret=trust.key.private_bytes_raw()
            self.assertNotIn(secret.hex(),json.dumps(trust.snapshot()))
            trust.run('calculate',lambda:2)
            trust.close()
            trust=Trust(path)
            try:
                self.assertEqual(identity,trust.identity())
                self.assertEqual(trust.verify()['records'],3)
                if os.name!='nt':self.assertEqual(path.stat().st_mode&0o777,0o600)
                else:
                    self.assertNotIn(secret,path.read_bytes())
            finally:trust.close()

    def test_denied_unknown_and_revoked_tools_do_not_execute(self):
        trust=Trust();self.addCleanup(trust.close)
        fn=Mock()
        for name in ('undeclared private content', 'calculate'):
            if name=='calculate':trust.set_scope('math.use',False)
            with self.assertRaises(PermissionDenied):trust.run(name,fn)
        fn.assert_not_called()
        records=trust.records()['entries']
        self.assertEqual(sum(r['outcome']=='denied' for r in records),2)
        self.assertNotIn('private content',json.dumps(records))
        self.assertTrue(trust.verify()['verified'])

    def test_signed_chain_detects_changes_and_sql_rejects_edits(self):
        trust=Trust();self.addCleanup(trust.close)
        trust.run('calculate',lambda:4)
        with self.assertRaises(sqlite3.IntegrityError):
            trust.db.execute("UPDATE audit SET record='{}' WHERE seq=2")
        trust.db.rollback()
        trust.db.execute('DROP TRIGGER audit_no_update')
        trust.db.execute("UPDATE audit SET signature=? WHERE seq=2",('00'*64,))
        trust.db.commit()
        with self.assertRaisesRegex(ValueError,'integrity'):trust.verify()

    def test_restart_rejects_corrupt_audit_instead_of_resetting_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trust.sqlite3';trust=Trust(path);identity=trust.identity();trust.close()
            with sqlite3.connect(path) as db:
                db.execute('DROP TRIGGER audit_no_update')
                db.execute("UPDATE audit SET digest='bad'")
            db.close()
            with self.assertRaisesRegex(ValueError,'integrity'):Trust(path)
            with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM identity').fetchone()[0],1)
            db.close()

    def test_parallel_receipts_and_pagination(self):
        trust=Trust();self.addCleanup(trust.close)
        threads=[threading.Thread(target=lambda:trust.run('calculate',lambda:1)) for _ in range(20)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(trust.verify()['records'],41)
        first=trust.records(limit=5);second=trust.records(before=first['next_before'],limit=5)
        self.assertTrue(set(r['seq'] for r in first['entries']).isdisjoint(r['seq'] for r in second['entries']))

    def test_failed_call_has_no_sensitive_arguments_or_error_text(self):
        trust=Trust();self.addCleanup(trust.close)
        def fail():raise ValueError('secret password and document content')
        with self.assertRaises(ValueError):trust.run('calculate',fail)
        self.assertEqual(trust.records()['entries'][0]['outcome'],'failed')
        self.assertNotIn('secret',json.dumps(trust.records()))

    def test_another_connection_observes_permission_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=Trust(Path(tmp)/'trust.sqlite3');second=Trust(Path(tmp)/'trust.sqlite3')
            try:
                first.set_scope('network.telegram',False)
                with self.assertRaises(PermissionDenied):second.run('telegram.send',Mock())
                self.assertTrue(first.verify()['verified'])
            finally:first.close();second.close()

    def test_audit_failure_blocks_tool(self):
        trust=Trust();self.addCleanup(trust.close);fn=Mock()
        with patch.object(trust,'_append',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):trust.run('calculate',fn)
        fn.assert_not_called()

    def test_direct_chat_and_toolbox_cannot_bypass_math_revocation_or_cache(self):
        store=Store(':memory:');self.addCleanup(store.close)
        engine=Engine(Config(),store)
        self.assertEqual(engine.chat('/calc 2+2',private=True)['answer'],'4')
        store.trust.set_scope('math.use',False)
        with self.assertRaises(PermissionDenied):engine.chat('/calc 2+2',private=True)
        with self.assertRaises(PermissionDenied):ToolBox(store,PubMed(store)).execute('calculate',{'expression':'2+2'})
        store.trust.set_scope('math.use',True)
        self.assertEqual(engine.chat('/calc 2+2',private=True)['answer'],'4')

    def test_web_and_telegram_revocation_stops_network_before_request(self):
        store=Store(':memory:');self.addCleanup(store.close)
        store.trust.set_scope('network.search',False)
        with patch('nexo7.web_research.fetch_json') as fetch:
            with self.assertRaises(PermissionDenied):WebResearch(store).lookup('chicken')
            fetch.assert_not_called()
        bridge=Bridge(Settings('123:secret',frozenset({1}),Path('/unused')),trust=store.trust)
        store.trust.set_scope('network.telegram',False)
        with patch('nexo7.telegram_bridge.fetch_json') as fetch:
            with self.assertRaises(PermissionDenied):bridge.telegram('sendMessage',{'text':'private'})
            fetch.assert_not_called()

    def test_disabled_memory_does_not_break_startup_seed(self):
        store=Store(':memory:');self.addCleanup(store.close)
        store.trust.set_scope('memory.write',False)
        store.seed(Path(__file__).parent.parent/'nexo7/knowledge/starter.md')
        self.assertEqual(store.documents(),[])

    def test_routes_are_explicit_and_remove_user_identifiers(self):
        self.assertEqual(route_action('POST','/api/tasks/private-id/apply'),'POST /api/tasks/*/apply')
        self.assertIsNone(route_action('POST','/api/future/unregistered'))


class TrustHTTPTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:')
        self.server=make_server(Config(),self.store,port=0,token='owner-token')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.cleanup)
    def cleanup(self):
        self.server.shutdown();self.thread.join();self.server.server_close();self.store.close()
    def request(self,path,body=None,token='owner-token'):
        req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'X-Nexo-Key':token,'Content-Type':'application/json'})
        with urlopen(req,timeout=3) as response:return json.load(response)
    def test_auth_toggle_denial_audit_and_reenable(self):
        for path in ('/api/trust','/api/trust/audit','/api/trust/verify'):
            with self.assertRaises(HTTPError) as error:self.request(path,token='wrong')
            self.assertEqual(error.exception.code,401)
        with self.assertRaises(HTTPError):self.request('/api/trust/permissions',{'scope':'math.use','enabled':False},token='wrong')
        self.request('/api/trust/permissions',{'scope':'math.use','enabled':False})
        with self.assertRaises(HTTPError) as error:self.request('/api/math',{'operation':'quadratic','a':'1','b':'-5','c':'6'})
        self.assertEqual(error.exception.code,403)
        self.request('/api/trust/permissions',{'scope':'math.use','enabled':True})
        self.assertEqual(self.request('/api/chat',{'message':'/calc 2+2','private':True})['answer'],'4')
        audit=self.request('/api/trust/audit')['entries']
        self.assertTrue(any(e['outcome']=='denied' for e in audit))
        self.assertNotIn('/calc 2+2',json.dumps(audit))
        self.assertTrue(self.request('/api/trust/verify')['verified'])
        self.request('/api/trust/permissions',{'scope':'settings.write','enabled':False})
        # Owner can always reenable; the model has no permission-management tool.
        self.request('/api/trust/permissions',{'scope':'settings.write','enabled':True})
    def test_bad_scope_and_boolean_do_not_change_permissions(self):
        for body in ({'scope':'all','enabled':True},{'scope':'math.use','enabled':'false'}):
            with self.assertRaises(HTTPError) as error:self.request('/api/trust/permissions',body)
            self.assertEqual(error.exception.code,400)
        self.assertTrue(self.store.trust.allowed('calculate'))
