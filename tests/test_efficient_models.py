"""3B model choice and own-server provider: efficient defaults on every
platform, bigger brains only on machines the user controls."""
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

try:
    import nexo7.privacy  # noqa: F401
except ModuleNotFoundError:
    # The sandbox lacks the optional 'cryptography' dependency; stub the
    # outbound PII guard so provider tests run without it.
    _fake_privacy = types.ModuleType('nexo7.privacy')
    _fake_privacy.check_outbound = lambda text: None
    sys.modules['nexo7.privacy'] = _fake_privacy

from nexo7.config import Config
from nexo7.hardware import GB, PROFILES, Hardware, plan_local
from nexo7.native_runtime import CATALOG, native_plan
from nexo7.providers import ServerProvider, provider_for


class ThreeBTests(unittest.TestCase):
    def test_catalog_entry_is_pinned_and_verifiable(self):
        item = CATALOG['models']['qwen2.5:3b']
        self.assertRegex(item['sha256'], r'^[a-f0-9]{64}$')
        self.assertTrue(item['url'].startswith('https://huggingface.co/'))
        self.assertIn(item['revision'], item['url'])
        self.assertTrue(item['filename'].endswith('.gguf'))
        self.assertGreater(item['size'], 1_000_000_000)

    def test_profile_sits_between_2b_and_4b(self):
        models = [p.model for p in PROFILES]
        self.assertLess(models.index('qwen3.5:2b'), models.index('qwen2.5:3b'))
        self.assertLess(models.index('qwen2.5:3b'), models.index('qwen3.5:4b'))
        profile = next(p for p in PROFILES if p.model == 'qwen2.5:3b')
        self.assertLessEqual(profile.minimum_budget, 6 * GB)
        self.assertLessEqual(profile.max_download, 2_500_000_000)

    def test_automatic_plan_offers_3b_on_capable_machines(self):
        hw = Hardware('Linux', 'x86_64', 24 * GB, 20 * GB, 8)
        plan = plan_local(hw, native=True)
        models = [p['model'] for p in plan['profiles']]
        self.assertIn('qwen2.5:3b', models)

    def test_automatic_plan_skips_3b_on_small_machines(self):
        hw = Hardware('Linux', 'x86_64', 8 * GB, 5 * GB, 4)
        plan = plan_local(hw, native=True, performance='balanced')
        models = [p['model'] for p in plan['profiles']]
        self.assertNotIn('qwen2.5:3b', models)

    def test_explicit_3b_choice_plans(self):
        hw = Hardware('Linux', 'x86_64', 16 * GB, 12 * GB, 8)
        with patch('nexo7.native_runtime.detect_hardware', return_value=hw):
            plan = native_plan(model_choice='qwen2.5:3b')
        self.assertEqual(plan['profiles'][0]['model'], 'qwen2.5:3b')
        self.assertEqual(plan['profiles'][0]['minimum_budget'], 4_000_000_000)

    def test_explicit_3b_choice_rejected_without_budget(self):
        hw = Hardware('Linux', 'x86_64', 4 * GB, 2 * GB, 2)
        with patch('nexo7.native_runtime.detect_hardware', return_value=hw):
            with self.assertRaises(ValueError):
                native_plan(model_choice='qwen2.5:3b')


class ServerProviderConfigTests(unittest.TestCase):
    def test_lan_http_server_accepted(self):
        c = Config(provider='server', model='qwen2.5:14b', server_url='http://192.168.1.20:11434')
        self.assertEqual(c.server_url, 'http://192.168.1.20:11434')

    def test_loopback_http_server_accepted(self):
        Config(provider='server', model='qwen2.5:7b', server_url='http://127.0.0.1:11434/')

    def test_remote_https_server_accepted(self):
        Config(provider='server', model='qwen2.5:32b', server_url='https://gpu.example.com')

    def test_public_http_rejected(self):
        with self.assertRaises(ValueError):
            Config(provider='server', model='qwen2.5:7b', server_url='http://8.8.8.8:11434')

    def test_missing_url_rejected(self):
        with self.assertRaises(ValueError):
            Config(provider='server', model='qwen2.5:7b', server_url='')

    def test_credentials_in_url_rejected(self):
        with self.assertRaises(ValueError):
            Config(provider='server', model='qwen2.5:7b', server_url='https://user:pass@gpu.example.com')

    def test_unknown_provider_still_rejected(self):
        with self.assertRaises(ValueError):
            Config(provider='datacenter', model='x', server_url='https://gpu.example.com')


class ServerProviderTests(unittest.TestCase):
    def _config(self):
        return Config(provider='server', model='qwen2.5:14b', server_url='http://192.168.1.20:11434')

    def test_provider_for_wires_server(self):
        self.assertIsInstance(provider_for(self._config()), ServerProvider)

    def test_complete_posts_chat_completions(self):
        captured = {}

        def fake_fetch(url, **kwargs):
            captured['url'] = url
            captured['headers'] = kwargs.get('headers')
            captured['payload'] = kwargs.get('payload')
            return {"choices": [{"message": {"role": "assistant", "content": "hola"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2}}

        with patch('nexo7.providers.fetch_json', side_effect=fake_fetch):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('NEXO_SERVER_API_KEY', None)
                result = ServerProvider(self._config()).complete(
                    'sys', [{'role': 'user', 'content': 'hola'}], [], 'qwen2.5:14b', 100)
        self.assertEqual(captured['url'], 'http://192.168.1.20:11434/v1/chat/completions')
        self.assertEqual(captured['payload']['model'], 'qwen2.5:14b')
        self.assertEqual(captured['payload']['messages'][0], {'role': 'system', 'content': 'sys'})
        self.assertNotIn('Authorization', captured['headers'])
        self.assertEqual(result.text, 'hola')
        self.assertEqual(result.usage['output_tokens'], 2)

    def test_api_key_comes_from_environment_only(self):
        captured = {}

        def spy(url, **kw):
            captured.update(kw.get('headers', {}))
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}

        with patch('nexo7.providers.fetch_json', side_effect=spy):
            with patch.dict(os.environ, {'NEXO_SERVER_API_KEY': 'secret-key'}):
                ServerProvider(self._config()).complete('s', [], [], 'm', 10)
        self.assertEqual(captured.get('Authorization'), 'Bearer secret-key')

    def test_empty_answer_raises(self):
        with patch('nexo7.providers.fetch_json', return_value={"choices": []}):
            with self.assertRaises(Exception):
                ServerProvider(self._config()).complete('s', [], [], 'm', 10)

    def test_tool_result_shape(self):
        out = ServerProvider.tool_result({'id': '1', 'name': 'calc'}, {'v': 2})
        self.assertEqual(out['role'], 'tool')
        self.assertEqual(json.loads(out['content']), {'v': 2})


if __name__ == '__main__':
    unittest.main()
