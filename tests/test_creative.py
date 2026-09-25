import base64
import io
import struct
import unittest
import wave
from xml.etree import ElementTree
from nexo7.creative import render


class CreativeTests(unittest.TestCase):
    def test_drawing_real_png_and_inert_svg(self):
        from PIL import Image
        files = render({'kind':'drawing','spec':{'width':64,'height':64,'shapes':[
            {'type':'rect','box':[0,0,64,64],'color':'#ff0000'},
            {'type':'text','x':0,'y':32,'text':'<script>&"','size':8}]}})['files']
        with Image.open(io.BytesIO(base64.b64decode(files[0]['data']))) as image:
            self.assertEqual(image.size, (64,64))
            self.assertEqual(image.getpixel((1,1)), (255,0,0))
        svg = ElementTree.fromstring(base64.b64decode(files[1]['data']))
        self.assertFalse(any('script' in el.tag for el in svg.iter()))
        self.assertIn('<script>&"', ''.join(svg.itertext()))

    def test_score_wav_duration_amplitude_and_midi(self):
        files=render({'kind':'music','spec':{'bpm':120,'notes':[
            {'pitch':69,'start':0,'duration':1}, {'pitch':72,'start':0,'duration':1}]}})['files']
        with wave.open(io.BytesIO(base64.b64decode(files[0]['data']))) as stream:
            self.assertEqual((stream.getnchannels(),stream.getframerate(),stream.getnframes()),(1,16000,8000))
            samples=struct.unpack('<8000h',stream.readframes(8000))
            self.assertGreater(max(samples), 1000)
            self.assertLessEqual(max(abs(v) for v in samples), 26000)
            self.assertEqual(samples[0],0)
        midi=base64.b64decode(files[1]['data'])
        self.assertEqual(midi[:14],b'MThd'+struct.pack('>IHHH',6,0,1,480))
        self.assertEqual(struct.unpack('>I',midi[18:22])[0],len(midi)-22)
        self.assertTrue(midi.endswith(b'\x00\xff\x2f\x00'))

    def test_limits_and_injection(self):
        for spec in [
            {'width':100000,'shapes':[{}]}, {'shapes':[{'type':'script'}]},
            {'shapes':[{'type':'rect','box':[0,0,20,20],'color':'url(https://example.com)'}]},
            {'shapes':[{}]*129}, {'width':float('nan'),'shapes':[{}]},
            {'width':True,'shapes':[{}]}, {'shapes':[{'type':'text','text':'\x00'}]},
        ]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):render({'kind':'drawing','spec':spec})
        for spec in [
            {'notes':[{'pitch':60,'start':64,'duration':8}]},
            {'notes':[{'pitch':60+i,'start':0,'duration':1} for i in range(9)]},
            {'notes':[{'pitch':60,'start':0,'duration':float('inf')}]},
            {'notes':[{}]*257}, {'notes':[]},
        ]:
            with self.subTest(spec=spec), self.assertRaises(ValueError):render({'kind':'music','spec':spec})
        with self.assertRaises(ValueError):render({'kind':'shell','spec':{}})
