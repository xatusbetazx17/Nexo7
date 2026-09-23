from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from nexo7.contributions import prepare
from nexo7.advanced_math import solve
from nexo7.tools import calculate
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.store import Store
from research.contributions import convert


class ContributionMathTests(unittest.TestCase):
    def draft(self, **changes):
        body=dict(source_id='W1',question='What is a network?',answer='Connected devices exchange information.',language='en',
                  rights_statement='I wrote this explanation myself from facts I checked.',own_rights=True,no_private_data=True,publish_and_train=True)
        body.update(changes)
        web=Mock();web.list_sources.return_value=[dict(id='W1',text='This is a long saved source passage that must not be copied into a public contribution.',url='https://example.org/network?tracking=123#fragment',retrieved_at='2026-09-23T12:00:00+00:00')]
        return prepare(web,body)

    def test_draft_is_opt_in_and_has_no_raw_source(self):
        with self.assertRaises(ValueError):self.draft(publish_and_train=False)
        result=self.draft()
        self.assertFalse(result['uploaded']);self.assertFalse(result['payload']['approved'])
        self.assertEqual(result['payload']['reference_url'],'https://example.org/network')
        self.assertNotIn('long saved source passage',result['body'])
        with self.assertRaises(ValueError):self.draft(answer='This is a long saved source passage that must not be copied into a public contribution.')
        with self.assertRaises(ValueError):self.draft(answer='Contact person@example.org for my secret.')

    def test_reviewed_import_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);item=self.draft()['payload'];ident=item['id']
            (root/'note.json').write_text(json.dumps(item),encoding='utf-8')
            (root/'reviews.json').write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):convert([root/'note.json'],root/'reviews.json',root/'train.jsonl')
            decision=dict(rights_checked=True,privacy_checked=True,facts_checked=True,approved=True,reviewer='maintainer',reason='Reviewed original factual explanation and reference.')
            (root/'reviews.json').write_text(json.dumps({ident:decision}),encoding='utf-8')
            convert([root/'note.json'],root/'reviews.json',root/'train.jsonl')
            row=json.loads((root/'train.jsonl').read_text());self.assertTrue(row['approved']);self.assertEqual(row['split'],'train')
            item['answer']='Changed after review';(root/'note.json').write_text(json.dumps(item),encoding='utf-8')
            with self.assertRaises(ValueError):convert([root/'note.json'],root/'reviews.json',root/'changed.jsonl')

    def test_linear_and_degenerate_system(self):
        result=solve({'operation':'linear','matrix':[[2,1],[1,-1]],'vector':[5,1]})['result']
        self.assertEqual(list(map(float,result['solution'])),[2,1])
        self.assertEqual(float(result['maximum_absolute_residual']),0)
        with self.assertRaises(ValueError):solve({'operation':'linear','matrix':[[1,2],[2,4]],'vector':[3,6]})

    def test_quadratic_statistics_and_input_limits(self):
        result=solve({'operation':'quadratic','a':1,'b':-5,'c':6})['result']
        self.assertEqual(set(map(float,result['roots'])),{2,3})
        self.assertEqual(solve({'operation':'quadratic','a':1,'b':0,'c':1})['result']['roots'][0]['imaginary'],'1')
        self.assertEqual(solve({'operation':'statistics','values':['0.1','0.2','0.3']})['result']['mean'],'0.2')
        for value in ['NaN','Infinity',True,'1e100000']:
            with self.assertRaises(ValueError):solve({'operation':'statistics','values':[value]})
        self.assertAlmostEqual(calculate('sin(pi/2)'),1)
        with self.assertRaises(ValueError):calculate("__import__('os')")

    def test_companion_math_needs_no_model_or_internet(self):
        with closing(Store(':memory:')) as store:
            model=Mock();engine=Engine(Config(provider='openai',model='fixture'),store,provider=model)
            result=engine.chat('/math {"operation":"linear","matrix":[[2]],"vector":[8]}',mode='companion',private=True)
            self.assertEqual(json.loads(result['answer'])['result']['solution'],['4'])
            self.assertEqual(result['stats']['model_calls'],0);model.complete.assert_not_called()
            result=engine.chat('calculate sin(pi/2)',mode='companion',private=True)
            self.assertEqual(float(result['answer']),1);model.complete.assert_not_called()
