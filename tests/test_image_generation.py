from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from nexo7.config import Config
from nexo7.hardware import Hardware
from nexo7.image_generation import CATALOG, ImageGenerator, memory_plan, runtime_path, validate
from nexo7.setup import SetupController


class DiffusionTests(unittest.TestCase):
    def test_cpu_selection_checks_probe_and_binary_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def entry(name):
                (root/name).write_bytes(name.encode())
                return {'filename':name,'sha256':hashlib.sha256(name.encode()).hexdigest()}
            info={'format':2,'commit':CATALOG['engine_commit'],'probe':entry('probe'),
                  'variants':{'baseline':entry('baseline'),'avx2':entry('avx2')}}
            (root/'manifest.json').write_text(json.dumps(info))
            with patch('nexo7.image_generation.RUNTIME_ROOT',root),patch('nexo7.image_generation.subprocess.run',return_value=Mock(stdout='avx2\n')) as run:
                self.assertEqual(runtime_path().name,'avx2')
                run.reset_mock();self.assertEqual(runtime_path(force_baseline=True).name,'baseline');run.assert_not_called()
                run.side_effect=subprocess.TimeoutExpired('probe',5)
                self.assertEqual(runtime_path().name,'baseline')
                run.side_effect=None
                (root/'avx2').write_bytes(b'tampered')
                with self.assertRaisesRegex(ValueError,'verification'):runtime_path()

    def test_limits_and_available_ram(self):
        for body in ({'prompt':''},{'prompt':'x','size':1024},{'prompt':'x','steps':99},{'prompt':'x','seed':True},{'prompt':'x','style':'unknown'}):
            with self.assertRaises(ValueError):validate(body)
        hw=Hardware('Linux','x86_64',8_000_000_000,4_000_000_000,4)
        with patch('nexo7.image_generation.detect_hardware',return_value=hw):
            plan=memory_plan(512)
            self.assertEqual(plan['ram_limit_bytes'],3_250_000_000)
            self.assertEqual(plan['threads'],3)
        with patch('nexo7.image_generation.detect_hardware',return_value=replace(hw,available_bytes=2_000_000_000)):
            with self.assertRaises(ValueError):memory_plan(256)

    def test_job_unloads_then_renders_then_restores_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller=SetupController(Path(tmp)/'db',{'cpu_only':True,'performance':'fast','model_choice':'lfm2-vl:450m'})
            original=Config(provider='native',model='lfm2-vl:450m',database=str(Path(tmp)/'db'))
            controller.config=original;controller.owns_runtime=True
            generator=ImageGenerator(controller);generator.root.mkdir()
            catalog={'model':{'filename':'model','size':1,'sha256':'ok','name':'test'},'decoder':{'filename':'decoder','size':1,'sha256':'ok'}}
            for name in ('model','decoder'):(generator.root/name).write_bytes(b'x')
            events=[]
            def worker(command,limit,key,**kwargs):
                events.append('render')
                self.assertFalse(controller.owns_runtime)
                Image.new('RGB',(256,256),'red').save(command[command.index('-o')+1])
                result=Mock();result.process.poll.return_value=0;result.process.returncode=0
                result.receipt={'guard':'linux_virtual_address_space','enforced_limit':limit}
                return result
            def restore(*a,**k):events.append('restore');return original,{'hardware':{}}
            with patch('nexo7.image_generation.CATALOG',catalog),patch('nexo7.image_generation.runtime_path',return_value=Path('/fixture/sd-cli')), \
                 patch('nexo7.image_generation.digest',return_value='ok'),patch('nexo7.image_generation.memory_plan',return_value={'ram_limit_bytes':2_000_000_000,'threads':2}), \
                 patch('nexo7.image_generation.stop_native',side_effect=lambda _:events.append('unload')),patch('nexo7.image_generation.start_native',side_effect=restore), \
                 patch('nexo7.image_generation.NativeProcess',side_effect=worker):
                generator.begin({'prompt':'red fox','size':256,'seed':7})
                generator.thread.join(3)
                result=generator.snapshot()
                self.assertEqual(result['phase'],'completed',result)
                self.assertEqual(events,['unload','render','restore'])
                self.assertEqual(result['files'][0]['name'],'Nexo-image.png')
                self.assertTrue(controller.owns_runtime)
                self.assertTrue(controller.operation.acquire(blocking=False));controller.operation.release()

    def test_missing_model_and_busy_do_not_start_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator=ImageGenerator(SetupController(Path(tmp)/'db'))
            with patch('nexo7.image_generation.runtime_path',return_value=Path('/fixture/sd-cli')):
                with self.assertRaisesRegex(ValueError,'Install AI images'):generator.begin({'prompt':'fox'})
                generator.controller.operation.acquire()
                with self.assertRaisesRegex(ValueError,'Wait'):generator.begin({},install=True)
                generator.controller.operation.release()

    def test_cancel_and_worker_failure_release_resources(self):
        for cancel in (True,False):
            with self.subTest(cancel=cancel),tempfile.TemporaryDirectory() as tmp:
                generator=ImageGenerator(SetupController(Path(tmp)/'db'))
                worker=Mock();worker.process.returncode=1
                worker.process.poll.return_value=None if cancel else 1
                worker.receipt={'enforced_limit':2_000_000_000}
                def start(*args,**kwargs):
                    if cancel:generator.cancel.set()
                    return worker
                with patch.object(generator,'installed',return_value=True),patch('nexo7.image_generation.runtime_path',return_value=Path('/fixture/sd-cli')), \
                     patch('nexo7.image_generation.digest',side_effect=lambda path:next(e['sha256'] for e in CATALOG.values() if isinstance(e,dict) and e['filename']==path.name)), \
                     patch('nexo7.image_generation.memory_plan',return_value={'ram_limit_bytes':2_000_000_000,'threads':2}), \
                     patch('nexo7.image_generation.NativeProcess',side_effect=start):
                    generator.begin({'prompt':'fox','size':256});generator.thread.join(3)
                    self.assertEqual(generator.snapshot()['phase'],'cancelled' if cancel else 'error')
                    self.assertEqual(generator.snapshot()['files'],[])
                    worker.close.assert_called_once()
                    self.assertTrue(generator.controller.operation.acquire(blocking=False));generator.controller.operation.release()
