from contextlib import closing
import tempfile
import unittest
from unittest.mock import Mock
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.providers import Completion
from nexo7.store import Store
from nexo7.workspace import Workspace
from nexo7.companion import evidence_review


class CompanionTests(unittest.TestCase):
    def config(self):
        return Config(provider='openai',model='fixture',max_model_calls=2,max_output_tokens=128,max_total_output_tokens=256)

    def test_local_fast_path_and_permission(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion('A chicken is a bird.')
            engine=Engine(self.config(),store,provider=provider)
            result=engine.chat('What is a chicken?',mode='companion',session='local')
            self.assertEqual(result['stats']['model_calls'],1)
            self.assertEqual(result['stats']['network_requests'],0)
            self.assertEqual(len(store.history('local',10)),2)
            blocked=engine.chat('latest news',mode='companion')
            self.assertEqual(blocked['status'],'needs_internet')
            self.assertEqual(provider.complete.call_count,1)

    def test_exact_reviewed_answer_needs_no_model_and_disable_is_respected(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion('Unknown.')
            engine=Engine(self.config(),store,provider=provider)
            engine.learning.import_pack({'format':'nexo-learning-v1','entries':[{'question':'My project code?',
                'answer':'Blue fox','language':'en','kind':'correction'}]},True)
            result=engine.chat('My project code?',mode='companion',language='en',private=True)
            self.assertEqual(result['answer'],'Blue fox');provider.complete.assert_not_called()
            store.set_preferences({'use_learning':False})
            engine.chat('My project code?',mode='companion',language='en',private=True)
            provider.complete.assert_called_once()

    def test_uncertainty_research_once_and_only_final_turn_saved(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.side_effect=[Completion("I don't know.",usage={'output_tokens':10}),Completion('Evidence says example [W1].',usage={'output_tokens':10})]
            web=Mock(storage_rights=True)
            web.lookup.return_value={'sources':[{'id':'W1','title':'Example','text':'Example evidence.','url':'https://example.org/a','source':'excerpt'}],
                                     'network_requests':1,'reused':False,'saved':False}
            engine=Engine(self.config(),store,provider=provider,web=web)
            result=engine.chat('Explain unfamiliar Zorilo',mode='companion',allow_internet=True,session='test')
            self.assertEqual(result['stats']['model_calls'],2)
            self.assertEqual(result['stats']['output_tokens'],20)
            self.assertEqual(len(store.history('test',10)),2)
            web.lookup.assert_called_once()
            self.assertFalse(result['companion']['evidence']['truth_verified'])

    def test_repair_does_not_execute_or_overwrite(self):
        with closing(Store(':memory:')) as store, tempfile.TemporaryDirectory() as tmp:
            workspace=Workspace(tmp);item=workspace.create('broken.py','def f(:\n pass')
            provider=Mock();provider.complete.return_value=Completion('```python\ndef f():\n    pass\n```')
            engine=Engine(self.config(),store,provider=provider,workspace=workspace)
            result=engine.chat('/repair broken.py',mode='companion',private=True,allow_internet=True)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(workspace.read(item['id'])['content'],'def f(:\n pass')
            self.assertEqual(len(workspace.list()),1)
            self.assertEqual(result['stats']['network_requests'],0)

    def test_source_diversity_is_not_claimed_as_truth(self):
        audit=evidence_review([{'id':'W1','url':'https://a.example/x'},{'id':'W2','url':'https://b.example/y'}])
        self.assertTrue(audit['multiple_domains']);self.assertFalse(audit['independence_verified'])
        self.assertFalse(audit['truth_verified'])
