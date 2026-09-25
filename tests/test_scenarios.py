from contextlib import closing
import json
import math
import unittest
from unittest.mock import Mock
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.providers import Completion
from nexo7.scenarios import calculate, hypothetical
from nexo7.store import Store


class ScenarioTests(unittest.TestCase):
    def test_imagined_question_never_needs_search_even_in_web_mode(self):
        question='make a imagination calculation if an ass crash with a truck and fly away what is the result and how much to paint the truck?'
        for mode in ('companion','web','scenario'):
            with self.subTest(mode=mode), closing(Store(':memory:')) as store:
                provider=Mock();provider.complete.return_value=Completion('Assuming you mean a donkey: in a cartoon it could fly away. A real repair cost needs a damage assessment.')
                web=Mock();web.storage_rights=True
                engine=Engine(Config(provider='native',model='qwen3.5:0.8b',local_ram_limit_bytes=1_500_000_000),store,provider=provider,web=web)
                answer=engine.chat(question,mode=mode,allow_internet=True,private=True)
                self.assertEqual(answer['status'],'completed')
                self.assertEqual(answer['stats']['network_requests'],0)
                self.assertEqual(provider.complete.call_count,1)
                web.lookup.assert_not_called();web.recall.assert_not_called()
                instructions,_,tools,_,_=provider.complete.call_args.args
                self.assertIn('assumptions',instructions);self.assertIn('repair bill',instructions)
                self.assertEqual(tools,[])

    def test_uncertainty_in_a_fiction_does_not_trigger_network(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion("I don't know the speed; give the assumed launch speed.")
            web=Mock()
            engine=Engine(Config(provider='native',model='qwen3.5:0.8b'),store,provider=provider,web=web)
            answer=engine.chat('Imagine a truck flies away today',mode='companion',allow_internet=True,private=True)
            self.assertEqual(answer['status'],'completed');self.assertEqual(provider.complete.call_count,1)
            web.lookup.assert_not_called()

    def test_explicit_search_is_not_overridden(self):
        with closing(Store(':memory:')) as store:
            web=Mock();web.storage_rights=True
            web.lookup.return_value={'sources':[],'network_requests':1,'reused':False,'saved':False}
            answer=Engine(Config(),store,web=web).chat('Search online for hypothetical physics examples',mode='web',private=True)
            web.lookup.assert_called_once();self.assertEqual(answer['status'],'no_evidence')
        self.assertTrue(hypothetical('¿Qué pasaría si un burro sale volando?'))
        self.assertFalse(hypothetical('What is a chicken?'))

    def test_flight_closed_form_and_downward_boundary(self):
        result=calculate({'kind':'flight','speed_m_s':10,'angle_degrees':45,'height_m':0})
        self.assertAlmostEqual(result['result']['horizontal_distance_m'],100/9.81,places=3)
        self.assertAlmostEqual(result['result']['maximum_height_m'],25/9.81,places=3)
        drop=calculate({'kind':'flight','speed_m_s':0,'angle_degrees':0,'height_m':10})
        self.assertAlmostEqual(drop['result']['flight_seconds'],math.sqrt(20/9.81),places=3)
        down=calculate({'kind':'flight','speed_m_s':10,'angle_degrees':-90,'height_m':0})
        self.assertEqual(down['result']['flight_seconds'],0)
        self.assertEqual(result['network_requests'],0);self.assertEqual(result['model_calls'],0)

    def test_money_decimal_and_input_rejection(self):
        result=calculate({'kind':'cost','area_m2':3,'rate_per_m2':0.1,'labor_hours':2,'hourly_rate':30,'materials':10})
        self.assertEqual(result['result']['subtotal'],'70.30')
        for x in (float('nan'),float('inf'),True,-1,'10',None,10**400):
            with self.subTest(x=str(x)[:20]),self.assertRaises(ValueError):
                calculate({'kind':'flight','speed_m_s':x,'angle_degrees':45,'height_m':0})

    def test_calculator_chat_command_uses_no_model(self):
        with closing(Store(':memory:')) as store:
            provider=Mock()
            answer=Engine(Config(),store,provider=provider).chat('/scenario '+json.dumps({'kind':'flight','speed_m_s':10,'angle_degrees':45,'height_m':0}),mode='companion',private=True)
            provider.complete.assert_not_called();self.assertEqual(answer['stats']['tool_calls'],1)
            self.assertIn('horizontal_distance_m',answer['answer'])
