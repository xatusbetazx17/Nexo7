from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from nexo7.config import Config
from nexo7.hardware import Hardware
from nexo7.image_generation import ImageGenerator, memory_plan, validate
from nexo7.setup import SetupController


class DiffusionTests(unittest.TestCase):
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
            def worker(command,limit,key):
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
