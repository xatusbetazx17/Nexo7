from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from nexo7.hardware import Hardware, GB, plan_local
from nexo7.store import Store
from nexo7.workspace import Workspace

class AdaptiveTests(unittest.TestCase):
    def test_eight_gb_and_fast_profile(self):
        hw=Hardware('Linux','x86_64',8*GB,7*GB,4)
        self.assertEqual(plan_local(hw)['profiles'][0]['model'],'qwen3.5:2b')
        self.assertEqual(plan_local(hw,performance='fast')['profiles'][0]['model'],'qwen3.5:0.8b')
        self.assertLessEqual(plan_local(hw)['ram_limit_bytes'],5*GB)
    def test_vram_pressure_reduces_profile_and_falls_back(self):
        hw=Hardware('Linux','x86_64',32*GB,26*GB,16,'nvidia','fixture',14*GB,16*GB,1)
        self.assertEqual(plan_local(hw)['profiles'][0]['model'],'qwen3.5:9b')
        p=plan_local(replace(hw,gpu_free_bytes=5*GB,gpu_total_bytes=6*GB))
        self.assertEqual(p['profiles'][0]['model'],'qwen3.5:2b')
        self.assertFalse(p['video_budget_enforced'])
        self.assertEqual(plan_local(replace(hw,gpu_free_bytes=GB))['backend'],'cpu')
    def test_preferences_persist_and_reject_unsafe_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db.sqlite'
            store=Store(path)
            store.set_preferences({'performance':'fast','response_language':'es','auto_start':True})
            store.close()
            store=Store(path)
            self.assertEqual(store.preferences()['performance'],'fast')
            self.assertTrue(store.preferences()['auto_start'])
            for update in ({'shell':True},{'performance':'unlimited'},{'auto_start':'yes'}):
                with self.assertRaises(ValueError):store.set_preferences(update)
            store.close()
    def test_only_approved_examples_become_documents(self):
        store=Store(':memory:')
        before=store.revision()
        store.record_feedback('test question','wrong answer','incorrect')
        self.assertEqual(store.documents(),[])
        self.assertNotEqual(store.revision(),before)
        result=store.record_feedback('test question','approved answer','useful')
        self.assertFalse(result['weight_training'])
        self.assertEqual(len(store.documents()),1)
        self.assertIn('not independently verified',store.documents()[0]['source'])
        store.close()

class WorkspaceTests(unittest.TestCase):
    def test_roundtrip_without_execution_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Workspace(Path(tmp)/'workspace')
            a=ws.create('script.py',"raise RuntimeError('not executed')\n")
            b=ws.create('script.py','print(2)')
            self.assertNotEqual(a['id'],b['id'])
            self.assertIn('not executed',ws.read(a['id'])['content'])
            self.assertEqual(len(ws.list()),2)
            ws.delete(a['id'])
            with self.assertRaises(ValueError):ws.read(a['id'])
    def test_traversal_reserved_and_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Workspace(tmp)
            for name in ('../a.py','/tmp/a.py','a/b.py','CON.txt','x.exe','a\\b.py'):
                with self.assertRaises(ValueError):ws.create(name,'x')
            with self.assertRaises(ValueError):ws.create('ok.txt','é'*100001)
            with self.assertRaises(ValueError):ws.read('../etc/passwd')
    def test_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Workspace(Path(tmp)/'workspace')
            target=Path(tmp)/'private.txt';target.write_text('private')
            try:(ws.root/('a'*32+'--test.txt')).symlink_to(target)
            except OSError:self.skipTest('Symlink unavailable')
            self.assertEqual(ws.list(),[])
            with self.assertRaises(ValueError):ws.read('a'*32)
