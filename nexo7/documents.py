"""Document extraction in a separate, memory-limited worker. Never fetches URLs."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_UPLOAD = 5_000_000
MAX_TEXT = 200_000


def extract(name, data):
    if not 1 <= len(data) <= MAX_UPLOAD: raise ValueError('Import limit: 5 MB')
    suffix = Path(name).suffix.lower()
    if suffix in {'.txt','.md','.csv','.json','.py','.html','.css','.js','.sql'}:
        text = data.decode('utf-8-sig')
    elif suffix == '.docx':
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            info = z.getinfo('word/document.xml')
            if info.file_size > 8_000_000: raise ValueError('DOCX text exceeds import limit')
            root = ET.fromstring(z.read(info))
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        text = '\n'.join(''.join(t.text or '' for t in p.iter(ns+'t')) for p in root.iter(ns+'p'))
    elif suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted: raise ValueError('Encrypted PDFs are not supported')
        if len(reader.pages) > 100: raise ValueError('PDF import limit: 100 pages')
        pieces = []; length = 0
        for page in reader.pages:
            part = page.extract_text() or ''; pieces.append(part); length += len(part)
            if length > MAX_TEXT: raise ValueError('Extracted text exceeds 200000 characters')
        text = '\n'.join(pieces)
    else: raise ValueError('Supported imports: PDF, DOCX and UTF-8 text/code/CSV/JSON')
    if not text.strip(): raise ValueError('No text found. Scanned PDFs need OCR, which is not included.')
    if len(text) > MAX_TEXT: raise ValueError('Extracted text exceeds 200000 characters')
    return {'title':Path(name).name[:160], 'content':text,
            'notice':'Review extracted text before saving. Images, macros and embedded files are not imported.'}


def import_document(name, encoded):
    if not isinstance(name,str) or not 1 <= len(name) <= 200 or not isinstance(encoded,str) or len(encoded)>6_700_000:
        raise ValueError('Invalid import request')
    try: data = base64.b64decode(encoded,validate=True)
    except ValueError: raise ValueError('Invalid file encoding') from None
    if not 1 <= len(data) <= MAX_UPLOAD: raise ValueError('Import limit: 5 MB')
    command = ([sys.executable,'--document-worker'] if getattr(sys,'frozen',False)
               else [sys.executable,'-m','nexo7.documents'])
    try:
        completed = subprocess.run(command, input=json.dumps({'name':name,'data':encoded}).encode(),
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=25,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired:
        raise ValueError('Document extraction exceeded 25 seconds') from None
    if completed.returncode or not completed.stdout:
        raise ValueError('Document extraction failed or exceeded its resource limit')
    result = json.loads(completed.stdout)
    if 'error' in result: raise ValueError(result['error'])
    return result


def worker_main():
    from .native_worker import ensure_stdio, windows_job
    ensure_stdio()
    if sys.platform == 'win32': job = windows_job(1_000_000_000)
    else:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(1_000_000_000,1_000_000_000))
    try:
        spec = json.loads(sys.stdin.buffer.read(6_800_000))
        result = extract(spec['name'],base64.b64decode(spec['data'],validate=True))
    except Exception as exc:
        result = {'error':str(exc)[:300] or 'Could not extract text within the resource limit'}
    sys.stdout.write(json.dumps(result,ensure_ascii=True));sys.stdout.flush()

if __name__ == '__main__': worker_main()
