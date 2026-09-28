from contextlib import closing
import unittest
from unittest.mock import Mock, patch
from nexo7.config import Config
from nexo7.engine import Engine
from nexo7.store import Store
from nexo7.smalltalk import reply


class SocialReplyTests(unittest.TestCase):
    def test_exact_social_intent_only(self):
        for text in ('¿Cómo estás?', 'hola, como estas?', 'Buenos días', 'Hi, how are you?'):
            self.assertIsNotNone(reply(text))
        for text in ('Hola, calcula 2+2', 'How are you handling my data?', '¿Cómo estás calculando eso?',
                     'cual es la diferencia entre un pollo una gallina', 'Hola, estoy triste'):
            self.assertIsNone(reply(text))
        self.assertIn('Hello', reply('hola', 'en'))
        self.assertIsNone(reply('hola', 'fr'))

    def test_chat_and_companion_no_model_and_history_privacy(self):
        with closing(Store(':memory:')) as store:
            provider=Mock()
            engine=Engine(Config(provider='openai',model='fixture'),store,provider=provider)
            for mode in ('chat','companion'):
                result=engine.chat('Hola, ¿cómo estás?',mode=mode,session=mode,language='es')
                self.assertEqual(result['status'],'completed')
                self.assertIn('listo para ayudarte',result['answer'])
                self.assertEqual(result['stats']['model_calls'],0)
                self.assertEqual(result['stats']['network_requests'],0)
                self.assertEqual(len(store.history(mode,10)),2)
            engine.chat('Hello',mode='chat',session='private',private=True)
            self.assertEqual(store.history('private',10),[])
            provider.complete.assert_not_called()

    def test_telegram_text_route_does_not_load_model_for_greeting(self):
        from nexo7.vision import reply as relay
        with patch('nexo7.providers.NativeProvider') as provider:
            result=relay(Config(provider='native',model='qwen3.5:0.8b'),
                         {'message':'¿Cómo estás?'},require_images=False)
            self.assertEqual(result['stats']['model_calls'],0)
            self.assertIn('listo para ayudarte',result['answer'])
            provider.assert_not_called()

class AppearancePersistenceTests(unittest.TestCase):
    def test_appearance_survives_reopening_and_rejects_arbitrary_style(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'profile.sqlite')
            with closing(Store(path)) as store:
                store.set_preferences({'ui_theme':'dark','ui_accent':'#7251b5'})
                with self.assertRaises(ValueError):store.set_preferences({'ui_accent':'url(https://example.org)'})
            with closing(Store(path)) as store:
                self.assertEqual(store.preferences()['ui_theme'],'dark')
                self.assertEqual(store.preferences()['ui_accent'],'#7251b5')
