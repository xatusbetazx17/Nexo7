import base64
from contextlib import closing
import io
import json
import unittest
from unittest.mock import Mock, patch
import zipfile
from PIL import Image
from nexo7.config import Config
from nexo7.creation_requests import intent, create
from nexo7.engine import Engine
from nexo7.providers import Completion, NativeProvider
from nexo7.store import Store


class CreationTests(unittest.TestCase):
    def test_native_drawing_constrains_output_and_still_uses_memory_guard(self):
        with closing(Store(':memory:')) as store, \
             patch('nexo7.native_runtime.verify_native',return_value=(Mock(key='fixture'),'http://127.0.0.1:1')), \
             patch('nexo7.hardware.detect_hardware',return_value=Mock(available_bytes=2_000_000_000)), \
             patch('nexo7.providers.fetch_json',return_value={'choices':[{'message':{'content':'{"background":"#ffffff","shapes":[{"type":"ellipse","box":[50,50,450,450],"color":"#ff0000"}]}'},'finish_reason':'stop'}]}) as fetch:
            config=Config(provider='native',model='lfm2-vl:450m')
            result=Engine(config,store,provider=NativeProvider(config)).chat('Draw a red ball',mode='companion',private=True)
            self.assertEqual(result['status'],'completed')
            payload=fetch.call_args.kwargs['payload']
            self.assertEqual(payload['response_format']['schema']['required'],['background','shapes'])
            self.assertEqual(payload['temperature'],0)
            self.assertLessEqual(payload['max_tokens'],config.max_output_tokens)

    def test_circle_vocabulary_is_validated_after_normalization(self):
        files=create('drawing',json.dumps({'background':'white','shapes':[{'type':'circle','center':[256,256],'radius':100,'fill':'red'}]}))
        image=Image.open(io.BytesIO(base64.b64decode(files[0]['data'])))
        self.assertEqual(image.getpixel((256,256)),(255,0,0))
        with self.assertRaises(ValueError):
            create('drawing',json.dumps({'shapes':[{'type':'circle','center':[0,0],'radius':100}]}))

    def test_screenshot_requests_work_without_model_or_web(self):
        for prompt in ('Draw me a chicken?', 'Draw me a hand', 'Dibujame una gallina', 'Dibuja una mano'):
            with self.subTest(prompt=prompt), closing(Store(':memory:')) as store:
                provider, web = Mock(), Mock()
                result = Engine(Config(), store, provider=provider, web=web).chat(prompt, mode='companion', private=True, allow_internet=True)
                self.assertEqual(result['status'], 'completed')
                self.assertIn('built-in', result['answer'])
                self.assertEqual([f['name'] for f in result['files']], ['drawing.png','drawing.svg'])
                image = Image.open(io.BytesIO(base64.b64decode(result['files'][0]['data'])))
                self.assertEqual(image.size, (512,512))
                self.assertGreater(len(image.getcolors()), 1)
                provider.complete.assert_not_called(); web.lookup.assert_not_called(); web.recall.assert_not_called()
                self.assertEqual(store.history(result['session']), [])

    def test_model_scene_is_rendered_and_invalid_output_never_claims_success(self):
        valid = json.dumps({'shapes':[{'type':'ellipse','box':[20,20,300,300],'color':'#ff0000'}]})
        for output, status in ((valid,'completed'), ('Sorry I cannot draw','unavailable'), ('{"shapes":[]}', 'unavailable'), ('{"shapes":[{"type":"script"}]}', 'unavailable')):
            with self.subTest(output=output), closing(Store(':memory:')) as store:
                provider=Mock();provider.complete.return_value=Completion(output)
                result=Engine(Config(provider='native',model='lfm2-vl:450m'),store,provider=provider).chat('Draw a red ball',mode='companion',private=True)
                self.assertEqual(result['status'],status)
                self.assertEqual('files' in result,status=='completed')
                self.assertEqual(provider.complete.call_count,1)
                self.assertEqual(provider.complete.call_args.args[2],[])

    def test_word_document_contains_content_and_text_download(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion('# Letter\nDear [Name],\nThank you for your help.')
            engine=Engine(Config(provider='native',model='lfm2-vl:450m'),store,provider=provider)
            result=engine.chat('Create a Word document with a thank-you letter',mode='companion',private=True)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['creation'],'document')
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(result['files'][0]['data']))) as archive:
                self.assertIn('Thank you for your help.',archive.read('word/document.xml').decode())
            self.assertIn(b'Thank you',base64.b64decode(result['files'][1]['data']))

    def test_incomplete_and_disabled_do_not_create_files(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion('{',incomplete=True)
            result=Engine(Config(provider='native',model='lfm2-vl:450m'),store,provider=provider).chat('Draw a house')
            self.assertEqual(result['status'],'incomplete');self.assertNotIn('files',result)
            result=Engine(Config(max_tool_calls=0),store).chat('Draw me a chicken')
            self.assertEqual(result['status'],'unavailable');self.assertNotIn('files',result)

    def test_music_files_and_document_refusal(self):
        with closing(Store(':memory:')) as store:
            provider=Mock();provider.complete.return_value=Completion('{"bpm":120,"notes":[{"pitch":60,"start":0,"duration":1}]}')
            engine=Engine(Config(provider='native',model='lfm2-vl:450m'),store,provider=provider)
            result=engine.chat('Make a short melody',mode='companion',private=True)
            self.assertEqual([f['name'] for f in result['files']],['music.wav','music.mid'])
            self.assertTrue(base64.b64decode(result['files'][0]['data']).startswith(b'RIFF'))
            provider.complete.return_value=Completion("I cannot create a document.")
            result=engine.chat('Create a Word document',mode='companion',private=True)
            self.assertNotIn('files',result);self.assertEqual(result['status'],'unavailable')
            provider.complete.return_value=Completion("Dear Ana, I cannot attend tomorrow. Best wishes.")
            result=engine.chat('Write a letter declining an invitation',mode='companion',private=True)
            self.assertEqual(result['status'],'completed');self.assertIn('files',result)

    def test_routing_does_not_hijack_questions_or_negation(self):
        for text in ('What is a drawing?', 'Do not draw a chicken', 'How can I make a document?', 'What does draw mean?', 'Draw conclusions from this report'):
            self.assertIsNone(intent(text))
        self.assertEqual(intent('Please create an image of a house'),'drawing')
        self.assertEqual(intent('Puedes dibujar un perro'),'drawing')
        self.assertEqual(intent('Escribe una carta'),'document')
