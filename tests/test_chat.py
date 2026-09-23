from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from nexo7.config import Config
from nexo7.engine import Engine, SYSTEM
from nexo7.net import TransportError
from nexo7.providers import Completion, NativeProvider
from nexo7.store import Store


class ChatTests(unittest.TestCase):
    def test_chat_has_no_retrieval_tools_or_network(self):
        with closing(Store(":memory:")) as store:
            provider = Mock()
            provider.complete.return_value = Completion("A chicken is a domesticated bird.")
            engine = Engine(Config(provider="native", model="qwen3.5:0.8b"), store, provider=provider)
            with patch.object(store, "search", side_effect=AssertionError("unrequested retrieval")), \
                 patch.object(engine.web, "recall", side_effect=AssertionError("unrequested web context")):
                result = engine.chat("What is a chiken?", mode="chat", private=True)
            self.assertEqual(result["status"], "completed")
            instructions, _, tools, _, limit = provider.complete.call_args.args
            self.assertLess(len(instructions), len(SYSTEM))
            self.assertEqual(tools, [])
            self.assertLessEqual(limit, 128)
            self.assertEqual(result["stats"]["network_requests"], 0)
            self.assertEqual(result["sources"], [])

    def test_failure_is_not_conversation_memory(self):
        with closing(Store(":memory:")) as store:
            provider = Mock()
            provider.complete.side_effect = TransportError("timeout")
            result = Engine(Config(provider="openai", model="fixture"), store, provider=provider).chat("hello", mode="chat", session="failure")
            self.assertEqual(result["status"], "upstream_error")
            self.assertEqual(store.history("failure", 10), [])

    def test_native_timeout_identifies_local_model(self):
        cfg = Config(provider="native", model="qwen3.5:0.8b")
        with patch("nexo7.native_runtime.verify_native", return_value=(Mock(key="test"), "http://127.0.0.1:1")), \
             patch("nexo7.providers.fetch_json", side_effect=TransportError("The remote service could not be reached within the time limit")):
            with self.assertRaisesRegex(TransportError, "model running on this computer"):
                NativeProvider(cfg).complete("hello", [], [], cfg.model, 64)


if __name__ == "__main__":
    unittest.main()
