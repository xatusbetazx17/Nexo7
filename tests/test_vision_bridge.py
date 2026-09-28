from nexo7.trust import Trust
import base64
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from nexo7.config import Config
from nexo7.hardware import Hardware
from nexo7.native_runtime import CATALOG, native_plan
from nexo7.providers import Completion
from nexo7.setup import SetupController
from nexo7.vision import normalize, prepare, reply
from nexo7.telegram_bridge import Albums, Bridge, Settings, addressed, chunk_text, matched_rules, load_rules


def picture(size=(80, 60), color='red', fmt='PNG'):
    output = io.BytesIO(); Image.new('RGB', size, color).save(output, format=fmt)
    return base64.b64encode(output.getvalue()).decode()


class VisionTests(unittest.TestCase):
    def test_worker_normalizes_resizes_and_discards_metadata(self):
        result = prepare([picture((1000, 800), fmt='WEBP')])[0]
        self.assertEqual((result['width'], result['height']), (512, 410))
        with Image.open(io.BytesIO(base64.b64decode(result['data']))) as image:
            self.assertEqual(image.format, 'PNG'); self.assertEqual(image.mode, 'RGB'); self.assertEqual(image.info, {})

    def test_rejects_compressed_large_pixels_invalid_data_and_count(self):
        for data in ['not base64', picture((4100, 4000))]:
            with self.assertRaises(ValueError): prepare([data])
        with self.assertRaises(ValueError): prepare([picture()] * 3)
        with self.assertRaises(ValueError): normalize('A' * 5_333_340)

    def test_no_cloud_or_text_only_image_fallback_and_no_tools(self):
        for cfg in [Config(), Config(provider='openai', model='fixture'), Config(provider='native', model='qwen3.5:0.8b')]:
            with self.assertRaises(ValueError): reply(cfg, {'images': [picture()]})
        cfg = Config(provider='native', model='lfm2-vl:450m')
        with patch('nexo7.providers.NativeProvider.complete', return_value=Completion('red', usage={'input_tokens': 20, 'output_tokens': 1})) as complete:
            result = reply(cfg, {'message': 'color?', 'images': [picture()]})
        self.assertTrue(result['private']); self.assertEqual(result['stats']['network_requests'], 0)
        self.assertEqual(complete.call_args.args[2], [])
        self.assertTrue(complete.call_args.args[1][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertNotIn('data', str(result))

    def test_vision_plan_counts_projector_and_respects_minimum_memory(self):
        with patch('nexo7.native_runtime.detect_hardware', return_value=Hardware('Linux', 'x86_64', 4_000_000_000, 2_500_000_000, 4)):
            plan = native_plan(model_choice='lfm2-vl:450m')
        self.assertEqual(plan['ram_limit_bytes'], 1_500_000_000)
        self.assertEqual(plan['profiles'][0]['download_bytes'], 323197440)
        self.assertEqual(plan['backend'], 'cpu')
        self.assertRegex(CATALOG['models']['lfm2-vl:450m']['projector']['sha256'], r'^[a-f0-9]{64}$')

    def test_switch_unloads_before_loading_and_preserves_database(self):
        controller = SetupController('/tmp/not-opened.sqlite')
        old = Config(provider='native', model='qwen3.5:0.8b', database='/tmp/not-opened.sqlite')
        controller.config = old; controller.owns_runtime = True
        operations = []
        new = replace(old, model='lfm2-vl:450m')
        with patch('nexo7.setup.stop_native', side_effect=lambda cfg: operations.append('stop')):
            with patch('nexo7.setup.start_native', side_effect=lambda *a, **kw: (operations.append('start') or new, {'hardware': {}})):
                controller.start(switch=True); controller.thread.join(5)
        self.assertEqual(operations, ['stop', 'start']); self.assertEqual(controller.config, new)


class BridgeTests(unittest.TestCase):
    def make(self):
        bridge = Bridge(Settings('123:' + 'x'*25, frozenset({10}), Path('/unused')), trust=Trust())
        bridge.bot_id = 99; bridge.username = 'nexo_bot'; bridge.telegram = Mock(); bridge.local = Mock(return_value={'answer': 'hello'})
        return bridge

    def test_explicit_allowlist_blocks_queries_downloads_and_replies(self):
        bridge = self.make()
        bridge.process([{'message_id': 1, 'chat': {'id': 11, 'type': 'private'}, 'text': 'hello', 'photo': [{'file_id': 'secret'}]}])
        bridge.telegram.assert_not_called(); bridge.local.assert_not_called()
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': '123:'+'a'*25, 'NEXO_TELEGRAM_CHAT_IDS': ''}):
            with self.assertRaises(ValueError): Settings.from_env()

    def test_default_does_not_scan_unaddressed_group_images(self):
        bridge = self.make()
        bridge.process([{'message_id': 1, 'chat': {'id': 10, 'type': 'group'}, 'photo': [{'file_id': 'test'}]}])
        bridge.telegram.assert_not_called(); bridge.local.assert_not_called()

    def test_utf16_mention_and_exact_rule_matching(self):
        msg = {'chat': {'type': 'group'}, 'text': '😀 @nexo_bot hello', 'entities': [{'type': 'mention', 'offset': 3, 'length': 9}]}
        self.assertTrue(addressed(msg, 'nexo_bot', 99))
        rules = [{'name': 'WINDOWS'}, {'name': 'LINUX'}]
        self.assertEqual(matched_rules('NOT_WINDOWS', rules), [])
        self.assertEqual(matched_rules('WINDOWS, LINUX', rules), rules)
        self.assertEqual(matched_rules('I see WINDOWS', rules), [])
        self.assertTrue(all(len(x.encode('utf-16-le'))//2 <= 4000 for x in chunk_text('😀'*5000)))

    def test_album_caption_on_second_image_and_reply_image(self):
        bridge = self.make(); bridge.image = Mock(side_effect=[picture(), picture()])
        group = [{'message_id': 1, 'chat': {'id': 10, 'type': 'group'}},
                 {'message_id': 2, 'chat': {'id': 10, 'type': 'group'}, 'caption': '@nexo_bot describe', 'caption_entities': [{'type': 'mention', 'offset': 0, 'length': 9}]}]
        bridge.process(group)
        self.assertEqual(bridge.local.call_count, 2)
        self.assertTrue(all(len(c.args[1]) == 1 for c in bridge.local.call_args_list))
        self.assertEqual(bridge.local.call_args.args[0], 'describe')
        bridge = self.make(); bridge.image = Mock(side_effect=[None, picture()])
        bridge.process([{'message_id': 3, 'chat': {'id': 10, 'type': 'private'}, 'text': 'describe', 'reply_to_message': {'message_id': 2}}])
        self.assertEqual(len(bridge.local.call_args.args[1]), 1)

    def test_album_buffers_bounded_and_scoped_per_chat(self):
        albums = Albums()
        for i in range(100): albums.add({'chat': {'id': 10}, 'media_group_id': 'a', 'message_id': i}, 0)
        albums.add({'chat': {'id': 20}, 'media_group_id': 'a', 'message_id': 1}, 0)
        ready = albums.due(2)
        self.assertEqual(len(ready), 2); self.assertEqual(len(ready[0]), 2); self.assertFalse(albums.groups)

    def test_local_access_rejects_remote_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/'access.json'; file.write_text(json.dumps({'url': 'https://evil.example/#token=secret'}))
            bridge = Bridge(Settings('123:x', frozenset({10}), file), trust=Trust())
            with patch('nexo7.telegram_bridge.fetch_json') as request:
                with self.assertRaises(ValueError): bridge.local('hello', [])
                request.assert_not_called()

    def test_bad_rule_file_fails_without_default_reactions(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'rules.json'; file.write_text('[{"name":"NONE","description":"x","reply":"x"}]')
            with self.assertRaises(ValueError): load_rules(file)


if __name__ == '__main__': unittest.main()

class TelegramLifecycleTests(unittest.TestCase):
    def test_discovery_requires_consent_and_returns_no_message_content(self):
        from nexo7.telegram_bridge import BridgeController
        controller=BridgeController('/unused/access.json',trust=Trust());body={'token':'123:'+'x'*25,'consent':True}
        with patch('nexo7.telegram_bridge.Bridge.telegram', return_value=[{'message':{'chat':{'id':10,'type':'private'},'text':'private text'}}]) as network:
            with self.assertRaises(ValueError): controller.discover({**body,'consent':False})
            network.assert_not_called()
            result=controller.discover(body)
        self.assertEqual(result['chats'],[{'id':10,'type':'private'}]);self.assertNotIn('private text',str(result))
    def test_stopped_bridge_never_starts_another_send(self):
        from nexo7.net import TransportError
        stop=threading.Event();bridge=Bridge(Settings('123:x',frozenset({10}),Path('/unused')),stop,trust=Trust());stop.set()
        with patch('nexo7.telegram_bridge.fetch_json') as network:
            with self.assertRaises(TransportError):bridge.send({'chat':{'id':10},'message_id':1},'reply')
            network.assert_not_called()
    def test_desktop_lifecycle_keeps_token_out_of_status_and_stops(self):
        from nexo7.telegram_bridge import BridgeController
        controller=BridgeController('/unused',trust=Trust());started=threading.Event()
        def run(bridge):started.set();bridge.stop.wait(2)
        token='123:'+'x'*25
        with patch.object(Bridge,'run',run):
            controller.start({'consent':True,'token':token,'chat_ids':[10]});self.assertTrue(started.wait(2))
            self.assertNotIn(token,str(controller.snapshot()));controller.stop();controller.thread.join(2)
        self.assertEqual(controller.snapshot()['phase'],'off')


class SetupReadinessTests(unittest.TestCase):
    def test_ready_is_not_visible_until_preference_save_and_operation_release(self):
        saving=threading.Event();finish=threading.Event()
        def save(values):saving.set();finish.wait(3);return values
        controller=SetupController('/tmp/fixture.sqlite',save_preferences=save)
        cfg=Config(provider='native',model='lfm2-vl:450m',database='/tmp/fixture.sqlite')
        with patch('nexo7.setup.start_native',return_value=(cfg,{'hardware':{}})):
            try:
                controller.start();self.assertTrue(saving.wait(2))
                self.assertFalse(controller.snapshot()['ready'])
                self.assertFalse(controller.operation.acquire(blocking=False))
            finally:finish.set();controller.thread.join(3)
        self.assertTrue(controller.snapshot()['ready'])
        self.assertTrue(controller.operation.acquire(blocking=False));controller.operation.release()


class TelegramDiagnosticsTests(unittest.TestCase):
    def test_bot_id_is_rejected_before_start(self):
        from nexo7.telegram_bridge import BridgeController
        controller = BridgeController('/unused', trust=Trust())
        with patch.object(Bridge, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'bot ID'):
                controller.start({'token': '123:' + 'x'*25, 'consent': True, 'chat_ids': [123]})
            run.assert_not_called()
        self.assertEqual(controller.snapshot()['phase'], 'off')

    def test_polling_routes_private_reply_and_counts_disallowed_chat(self):
        from nexo7.telegram_bridge import BridgeController
        controller = BridgeController('/unused', trust=Trust())
        controller.stop_event.clear()
        bridge = Bridge(Settings('123:'+'x'*25, frozenset({10}), Path('/unused')), trust=controller.trust, report=controller.report)
        bridge.local = Mock(return_value={'answer': 'hello'})
        polls = 0
        sends = []
        def network(method, payload):
            nonlocal polls
            if method == 'getMe': return {'id': 123, 'username': 'nexo_bot'}
            if method == 'sendMessage': sends.append(payload); return {'message_id': 5}
            if method == 'getUpdates':
                polls += 1
                if polls == 1: return []
                if polls == 2:
                    return [{'update_id': i, 'message': {'message_id': i, 'chat': {'id': chat, 'type': 'private'}, 'text': 'hello'}} for i, chat in [(1, 99), (2, 10)]]
                bridge.stop.set(); return []
            self.fail(method)
        bridge.telegram = network
        bridge.run()
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0]['chat_id'], 10)
        self.assertEqual(sends[0]['reply_parameters'], {'message_id': 2})
        self.assertEqual(bridge.local.call_count, 1)
        state = controller.snapshot()
        self.assertEqual((state['received'], state['ignored'], state['replied']), (1, 1, 1))
        self.assertNotIn('hello', str(state))

    def test_poll_errors_report_conflict_and_recover_without_leaking(self):
        from nexo7.net import TransportError
        reports = []
        bridge = Bridge(Settings('123:'+'x'*25, frozenset({10}), Path('/unused')), trust=Trust(), report=lambda **s: reports.append(s))
        polls = 0
        def network(method, payload):
            nonlocal polls
            if method == 'getMe': return {'id': 123, 'username': 'nexo_bot'}
            polls += 1
            if polls == 2: raise TransportError('HTTP 409 secret-token-content')
            if polls == 3: bridge.stop.set()
            return []
        bridge.telegram = network
        with patch.object(bridge.stop, 'wait', return_value=False): bridge.run()
        self.assertTrue(any(r.get('phase') == 'reconnecting' and 'conflict' in r.get('error', '') for r in reports))
        self.assertEqual(reports[-1], {'phase': 'running', 'error': None})
        self.assertNotIn('secret-token-content', str(reports))

    def test_start_does_not_claim_running_before_authentication(self):
        from nexo7.telegram_bridge import BridgeController
        from nexo7.net import TransportError
        entered, release = threading.Event(), threading.Event()
        controller = BridgeController('/unused', trust=Trust())
        def network(*args):
            entered.set(); release.wait(2)
            raise TransportError('HTTP 401 secret')
        with patch.object(Bridge, 'telegram', network):
            try:
                controller.start({'token': '123:'+'x'*25, 'consent': True, 'chat_ids': [10]})
                self.assertTrue(entered.wait(2))
                self.assertEqual(controller.snapshot()['phase'], 'starting')
            finally:
                release.set(); controller.thread.join(2)
        self.assertEqual(controller.snapshot()['phase'], 'off')
        self.assertIn('rejected the token', controller.snapshot()['error'])
        self.assertNotIn('secret', str(controller.snapshot()))

class TelegramPingTests(unittest.TestCase):
    def test_ping_and_start_do_not_depend_on_model(self):
        from contextlib import closing
        with closing(Trust()) as trust:
            bridge=Bridge(Settings('123:'+'x'*25,frozenset({10}),Path('/unused')),trust=trust)
            bridge.username='nexo_bot';bridge.bot_id=123
            bridge.local=Mock(side_effect=ValueError('Model unavailable'))
            bridge.send=Mock()
            for command in ('/ping','/start','/ping@nexo_bot'):
                bridge.process([{'message_id':1,'chat':{'id':10,'type':'private'},'text':command}])
            self.assertEqual(bridge.send.call_count,3);bridge.local.assert_not_called()
            bridge.process([{'message_id':2,'chat':{'id':99,'type':'private'},'text':'/ping'}])
            self.assertEqual(bridge.send.call_count,3)
            self.assertTrue(addressed({'chat':{'type':'group'},'text':'/ping@nexo_bot'},'nexo_bot',123))
