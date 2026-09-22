import base64
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from nexo7.config import Config
from nexo7.documents import extract, import_document
from nexo7.engine import Engine
from nexo7.hardware import GB, Hardware
from nexo7.local_tools import csv_summary, dates, inspect_file
from nexo7.native_runtime import CATALOG, NativeProcess, download, extract_runtime, native_plan, verify_native
from nexo7.providers import NativeProvider
from nexo7.store import Store
from nexo7.workspace import Workspace

class NativeTests(unittest.TestCase):
    def test_catalog_has_pinned_hashes_and_supported_models(self):
        self.assertEqual(set(CATALOG['models']),{'qwen3.5:0.8b','qwen3.5:2b','qwen3.5:4b','qwen3.5:9b'})
        for item in [*CATALOG['models'].values(),*CATALOG['runtimes'].values()]:
            self.assertRegex(item['sha256'],r'^[a-f0-9]{64}$')
            self.assertTrue(item['url'].startswith('https://'))
    def test_native_eight_gb_requires_no_docker(self):
        hw=Hardware('Linux','x86_64',8*GB,6*GB,4)
        with patch('nexo7.native_runtime.detect_hardware',return_value=hw):
            plan=native_plan(performance='fast')
        self.assertEqual(plan['profiles'][0]['model'],'qwen3.5:0.8b')
        self.assertLessEqual(plan['ram_limit_bytes'],4*GB)
        self.assertEqual(plan['backend'],'cpu')
    def test_external_or_forged_native_runtime_fails_closed(self):
        with self.assertRaises(ValueError):verify_native(Config(provider='native',model='qwen3.5:0.8b',native_runtime_id='unknown'))
    def test_actual_os_limit_rejects_allocation_and_process_exits(self):
        script="import sys\ntry:\n b=bytearray(1_200_000_000)\nexcept MemoryError:\n sys.exit(0)\nsys.exit(9)"
        runtime=NativeProcess([sys.executable,'-c',script],1_000_000_000,'')
        try:
            self.assertEqual(runtime.process.wait(timeout=20),0)
            self.assertEqual(runtime.receipt['limit'],1_000_000_000)
        finally:runtime.close()
    def test_closing_supervisor_stops_child(self):
        runtime=NativeProcess([sys.executable,'-c','import time;time.sleep(60)'],1_000_000_000,'')
        runtime.close()
        self.assertIsNotNone(runtime.process.poll())
    def test_cancel_does_not_create_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancel=threading.Event();cancel.set()
            with self.assertRaises(ValueError):download(CATALOG['models']['qwen3.5:0.8b'],Path(tmp)/'x',cancel=cancel)
            self.assertEqual(list(Path(tmp).iterdir()),[])
    def test_tampered_download_is_not_installed(self):
        class Response(io.BytesIO):
            def geturl(self):return 'https://example.invalid/file'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';entry={'url':'https://example.invalid/file','size':3,'sha256':hashlib.sha256(b'yes').hexdigest()}
            with patch('urllib.request.urlopen',return_value=Response(b'bad')):
                with self.assertRaises(ValueError):download(entry,p,emit=lambda _:None)
            self.assertFalse(p.exists());self.assertFalse(p.with_suffix('.part').exists())
    def test_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../bad.txt','bad')
            with self.assertRaises(ValueError):extract_runtime(archive,Path(tmp)/'out')
            self.assertFalse((Path(tmp)/'bad.txt').exists())

class LocalToolsTests(unittest.TestCase):
    def test_csv_totals_missing_cells_and_bad_rows(self):
        result=csv_summary('item,amount\na,10.25\nb,20.75\nc,\n')
        self.assertEqual(result['columns'][1]['sum'],'31.00')
        self.assertEqual(result['columns'][1]['missing'],1)
        with self.assertRaises(ValueError):csv_summary('a,b\n1\n')
        self.assertNotIn('sum',csv_summary('a\nNaN\n')['columns'][0])
    def test_natural_language_arithmetic_avoids_model(self):
        store=Store(':memory:')
        try:
            for prompt in ('Calculate 24.5 * 40','Cuánto es 24.5 * 40?'):
                result=Engine(Config(),store).chat(prompt,private=True)
                self.assertEqual(result['answer'],'980.0');self.assertEqual(result['stats']['model_calls'],0)
        finally:store.close()
    def test_pdf_text_import_in_guarded_worker(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:self.skipTest('Install requirements-runtime.txt for PDF tests')
        writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 100 Td (Offline PDF text) Tj ET')
        page[NameObject('/Contents')]=stream
        output=io.BytesIO();writer.write(output)
        result=import_document('document.pdf',base64.b64encode(output.getvalue()).decode())
        self.assertIn('Offline PDF text',result['content'])
    def test_calendar_leap_year(self):
        self.assertEqual(dates('2024-02-28 2024-03-01')['days'],2)
    def test_workspace_syntax_check_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Workspace(tmp);ws.create('test.py','raise RuntimeError("must not run")\ndef f(): return 1')
            result=inspect_file(ws,'test.py');self.assertTrue(result['syntax_valid']);self.assertFalse(result['executed'])
            ws.create('test.py','invalid $ code')
            with self.assertRaises(ValueError):inspect_file(ws,'test.py')
    def test_direct_tools_obey_tool_budget(self):
        store=Store(':memory:')
        try:
            result=Engine(Config(max_tool_calls=0),store).chat('/date 2024-01-01 2024-01-02')
            self.assertEqual(result['status'],'unavailable');self.assertEqual(result['stats']['tool_calls'],0)
        finally:store.close()
    def test_docx_import_and_text_size_limit(self):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Offline notes</w:t></w:r></w:p></w:document>')
        self.assertEqual(extract('notes.docx',data.getvalue())['content'],'Offline notes')
        with self.assertRaises(ValueError):extract('notes.txt',b'x'*200001)
    def test_import_worker_runs_without_model(self):
        result=import_document('notes.txt',base64.b64encode('Hola español'.encode()).decode())
        self.assertEqual(result['content'],'Hola español')
    def test_pdf_without_text_reports_ocr_limitation(self):
        try:from pypdf import PdfWriter
        except ImportError:self.skipTest('Install requirements-runtime.txt for PDF tests')
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);data=io.BytesIO();writer.write(data)
        with self.assertRaisesRegex(ValueError,'OCR'):extract('scan.pdf',data.getvalue())

class MigrationTests(unittest.TestCase):
    def test_only_exact_bundled_guide_is_upgraded(self):
        store=Store(':memory:')
        try:
            store.seed(Path(__file__).parent/'fixtures/legacy_starter.md')
            personal=store.add_document('My notes','Docker is useful for my other projects')
            store.seed(Path(__file__).parents[1]/'nexo7/knowledge/starter.md')
            self.assertTrue(any(d['id']==personal for d in store.documents()))
            content=store.db.execute("SELECT content FROM documents WHERE title='Nexo starter guide'").fetchone()[0]
            self.assertIn('needs no Docker',content)
            self.assertEqual(len(store.documents()),2)
        finally:store.close()
