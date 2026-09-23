from contextlib import closing
import tempfile
import unittest
from unittest.mock import Mock
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.providers import Completion
from nexo7.store import Store
from nexo7.task_agent import TaskAgent,digest
from nexo7.workspace import Workspace

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name+'/tasks.sqlite')
        self.workspace=Workspace(self.tmp.name+'/files');self.agent=TaskAgent(self.store,self.workspace)
        self.provider=Mock();self.engine=Engine(Config(provider='native',model='qwen3.5:0.8b',max_model_calls=2),self.store,provider=self.provider,workspace=self.workspace)
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def create(self,steps=None):
        return self.agent.create({'goal':'Build a tiny square project','steps':steps or [{'name':'square.py','instruction':'Define square(n) returning n*n','required':['def square']}]})
    def test_review_apply_verify_persistence_and_reverse_rollback(self):
        job=self.create([{'name':'square.py','instruction':'Define square(n)'},{'name':'README.md','instruction':'Explain square.py'}])
        self.provider.complete.side_effect=[Completion('def square(n):\n    return n*n\n'),Completion('Use square.py to square a number.')]
        job=self.agent.run(job['id'],self.engine);self.assertEqual(job['state'],'awaiting_review');self.assertEqual(self.workspace.list(),[])
        with self.assertRaises(ValueError):self.agent.apply(job['id'],'stale')
        job=self.agent.apply(job['id'],job['steps'][0]['proposal_id']);self.assertEqual(job['state'],'ready')
        task=TaskAgent(self.store,self.workspace);self.assertEqual(task.get(job['id'])['steps'][0]['state'],'applied')
        job=task.run(job['id'],self.engine);job=task.apply(job['id'],job['steps'][1]['proposal_id']);self.assertEqual(job['state'],'completed')
        self.assertEqual(len(self.workspace.list()),2)
        with self.assertRaises(ValueError):task.run(job['id'],self.engine)
        job=task.rollback(job['id']);self.assertEqual(job['state'],'cancelled');self.assertEqual(len(self.workspace.list()),1)
        task.rollback(job['id']);self.assertEqual(self.workspace.list(),[])
    def test_invalid_output_correction_and_no_execution(self):
        job=self.create();self.provider.complete.side_effect=[Completion('def square(:'),Completion('def square(n):\n    return n*n\n')]
        job=self.agent.run(job['id'],self.engine)
        self.assertEqual(job['state'],'awaiting_review');self.assertEqual(job['steps'][0]['attempts'],2)
        self.assertIn('syntax',str(job['steps'][0]['validation']))
        self.assertEqual(self.workspace.list(),[])
    def test_repeated_invalid_output_stops_and_blocks_false_completion(self):
        job=self.create();self.provider.complete.return_value=Completion('not valid python !')
        job=self.agent.run(job['id'],self.engine);self.assertEqual(job['state'],'blocked');self.assertEqual(self.provider.complete.call_count,2)
        with self.assertRaises(ValueError):self.agent.run(job['id'],self.engine)
        with self.assertRaises(ValueError):self.agent.apply(job['id'],'anything')
    def test_stale_base_and_rollback_never_overwrite_newer_work(self):
        item=self.workspace.create('square.py','original = True\n');job=self.create();self.provider.complete.return_value=Completion('def square(n):\n    return n*n\n')
        job=self.agent.run(job['id'],self.engine)
        self.workspace.replace(item['id'],digest('original = True\n'),'changed = True\n')
        with self.assertRaises(ValueError):self.agent.apply(job['id'],job['steps'][0]['proposal_id'])
        self.assertEqual(self.workspace.read(item['id'])['content'],'changed = True\n')
        job=self.create();job=self.agent.run(job['id'],self.engine);job=self.agent.apply(job['id'],job['steps'][0]['proposal_id'])
        self.workspace.replace(item['id'],job['steps'][0]['after_hash'],'newer = True\n')
        with self.assertRaises(ValueError):self.agent.rollback(job['id'])
    def test_limits_local_only_interruption_and_deletion(self):
        for name in ['../escape.py','CON.py','bad.exe']:
            with self.assertRaises(ValueError):self.create([{'name':name,'instruction':'write'}])
        job=self.create();cloud=Engine(Config(provider='openai',model='fixture'),self.store,provider=Mock())
        with self.assertRaises(ValueError):self.agent.run(job['id'],cloud)
        job['state']='running';self.agent.save(job)
        self.assertEqual(TaskAgent(self.store,self.workspace).get(job['id'])['state'],'blocked')
        self.agent.delete(job['id']);self.assertEqual(self.agent.list(),[])
    def test_one_call_profile_resumes_without_exceeding_request_limit(self):
        from dataclasses import replace
        self.engine.config=replace(self.engine.config,max_model_calls=1)
        job=self.create();self.provider.complete.side_effect=[Completion('bad syntax !'),Completion('def square(n):\n return n*n')]
        job=self.agent.run(job['id'],self.engine);self.assertEqual(self.provider.complete.call_count,1);self.assertEqual(job['state'],'blocked')
        job=self.agent.run(job['id'],self.engine);self.assertEqual(job['state'],'awaiting_review');self.assertEqual(self.provider.complete.call_count,2)
    def test_truncated_output_is_not_approved(self):
        job=self.create();self.provider.complete.return_value=Completion('def square(n):\n return n*n',incomplete=True)
        job=self.agent.run(job['id'],self.engine);self.assertEqual(job['state'],'blocked');self.assertEqual(self.workspace.list(),[])
    def test_behavioral_cases_catch_valid_but_wrong_code_and_correct_it(self):
        job=self.create([{'name':'square.py','instruction':'Return n squared','function_tests':[{'function':'square','args':[3],'expected':9}]}])
        self.provider.complete.side_effect=[Completion('def square(n):\n return n+1'),Completion('def square(n):\n return n*n')]
        job=self.agent.run(job['id'],self.engine)
        self.assertEqual(job['state'],'awaiting_review');self.assertEqual(job['steps'][0]['attempts'],2)
        self.assertTrue(any(c.get('actual')==9 and c['passed'] for c in job['steps'][0]['validation']['checks']))
    def test_pure_checker_rejects_execution_and_unbounded_constructs(self):
        from nexo7.pure_checks import check
        tests=[{'function':'f','args':[2],'expected':4}]
        for code in ['import os\ndef f(n): return n*n','def f(n): return __import__("os").getcwd()','def f(n):\n while True: pass','@danger\ndef f(n): return n*n','def f(n): return n**1000000']:
            with self.assertRaises(ValueError):check(code,tests)
        self.assertTrue(check('def f(n): return n*n',tests)[0]['passed'])
    def test_model_plan_is_a_draft_and_cannot_change_files(self):
        self.provider.complete.return_value=Completion('[{"name":"readme.md","instruction":"Write a short guide","required":[]}]')
        plan=self.agent.plan('Write a guide',self.engine)
        self.assertEqual(plan['steps'][0]['name'],'readme.md');self.assertEqual(self.agent.list(),[]);self.assertEqual(self.workspace.list(),[])
        self.provider.complete.return_value=Completion('[{"name":"../escape.py","instruction":"write"}]')
        with self.assertRaises(ValueError):self.agent.plan('Write a guide',self.engine)
