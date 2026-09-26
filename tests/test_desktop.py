from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from nexo7.config import Config
from nexo7.desktop import instance_lock
from nexo7.hardware import GB, Hardware, plan_local
from nexo7.local_runtime import SetupCancelled, start_local
from nexo7.server import make_server
from nexo7.setup import SetupController
from nexo7.store import Store


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.controller = SetupController(Path(self.directory.name) / 'data.sqlite3')

    def test_single_instance_lock_releases_after_exit(self):
        path = Path(self.directory.name)
        with instance_lock(path) as acquired:
            self.assertTrue(acquired)
            with instance_lock(path) as second:
                self.assertFalse(second)
        with instance_lock(path) as acquired:
            self.assertTrue(acquired)

    def test_unsupported_native_hardware_does_not_enable_ai(self):
        with patch('nexo7.setup.native_plan', side_effect=ValueError('Unsupported hardware')):
            report = self.controller.check()
        self.assertFalse(report['requirements_ok'])
        self.assertEqual(self.controller.config.provider, 'demo')

    def test_setup_failure_releases_operation_and_keeps_demo(self):
        with patch('nexo7.setup.start_native', side_effect=ValueError('guard failed')):
            self.controller.start()
            self.controller.thread.join(timeout=2)
        self.assertEqual(self.controller.snapshot()['phase'], 'error')
        self.assertEqual(self.controller.config.provider, 'demo')
        self.assertTrue(self.controller.operation.acquire(blocking=False))
        self.controller.operation.release()

    def test_success_only_switches_provider_after_setup_finishes(self):
        entered, release = threading.Event(), threading.Event()
        hw = Hardware('Linux', 'x86_64', 16*GB, 12*GB, 8)
        plan = plan_local(hw)
        cfg = Config(provider='native', model='qwen3.5:4b', database=self.controller.config.database)
        def prepare(*args, **kwargs):
            entered.set()
            release.wait(3)
            return cfg, plan
        with patch('nexo7.setup.start_native', side_effect=prepare):
            self.controller.start(language='es')
            self.assertTrue(entered.wait(2))
            self.assertEqual(self.controller.config.provider, 'demo')
            with self.assertRaises(ValueError):
                self.controller.start()
            release.set()
            self.controller.thread.join(timeout=2)
        self.assertEqual(self.controller.config.response_language, 'es')
        self.assertTrue(self.controller.snapshot()['ready'])
        self.assertTrue(self.controller.owns_runtime)

    def test_cancel_before_start_does_not_touch_docker(self):
        cancel = threading.Event()
        cancel.set()
        with patch('nexo7.local_runtime.local_daemon') as daemon:
            with self.assertRaises(SetupCancelled):
                start_local('unused.sqlite3', cancel=cancel)
            daemon.assert_not_called()

    def test_setup_logs_are_bounded_and_snapshot_is_independent(self):
        for number in range(300):
            self.controller.emit(str(number) + 'x'*2000)
        state = self.controller.snapshot()
        self.assertEqual(len(state['logs']), 80)
        self.assertTrue(all(len(line) <= 500 for line in state['logs']))
        state['logs'].clear()
        self.assertEqual(len(self.controller.snapshot()['logs']), 80)

    def test_setup_endpoints_require_auth_and_block_chat_during_setup(self):
        store = Store(':memory:')
        server = make_server(self.controller.config, store, port=0, token='test-key', controller=self.controller)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def request(path, body=None, key='test-key'):
            data = json.dumps(body).encode() if body is not None else None
            return urlopen(Request(base+path, data=data, headers={'Content-Type':'application/json','X-Nexo-Key':key}), timeout=3)
        try:
            with self.assertRaises(HTTPError) as error:
                request('/api/setup/start', {}, key='wrong-key')
            self.assertEqual(error.exception.code, 401)
            self.assertIsNone(self.controller.thread)
            for path,body in (('/api/images',None),('/api/images/install',{}),('/api/images/start',{'prompt':'fox'}),('/api/images/cancel',{})):
                with self.assertRaises(HTTPError) as error:
                    request(path,body,key='wrong-key')
                self.assertEqual(error.exception.code,401)
            self.assertIsNone(self.controller.image_generator.thread)
            with request('/api/status') as response:
                self.assertTrue(json.load(response)['desktop'])
            self.controller.operation.acquire()
            try:
                with self.assertRaises(HTTPError) as error:
                    request('/api/chat', {'message':'2+2'})
                self.assertEqual(error.exception.code, 429)
            finally:
                self.controller.operation.release()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            store.close()


if __name__ == '__main__':
    unittest.main()
