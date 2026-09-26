"""Release-pinned chip discovery. Only user-selected downloads contact the network."""
import base64
import json
from pathlib import Path
import re
import urllib.request
from .chips import ROOT, inspect
from .net import NoRedirect

CATALOG = Path(__file__).with_name('chip-discovery.json')


def download(url):
    with urllib.request.build_opener(NoRedirect()).open(url, timeout=15) as response:
        raw = response.read(100001)
    if len(raw) > 100000: raise ValueError('Chip download exceeds 100 KB')
    return raw


class Catalog:
    def __init__(self, chips, transport=download):
        self.chips, self.transport = chips, transport

    def list(self):
        installed = {c['manifest']['name'] for c in self.chips.list() if not c.get('invalid')}
        return [{**item, 'installed': item['name'] in installed} for item in json.loads(CATALOG.read_text())]

    def fetch(self, name):
        with self.chips.store.trust.action('chips.download'):
            item = next((c for c in self.list() if c['name'] == name), None)
            if not item or item['builtin']: raise ValueError('Select a downloadable catalog chip')
            # URL is bundled with this application, never accepted from a request or chip.
            raw = self.transport(item['url']); proof = inspect(raw)
            if any(proof[k] != item[k] for k in ('sha256', 'fingerprint')) or proof['manifest']['name'] != name:
                raise ValueError('Catalog download does not match its pinned signature and hash')
            return {'data': base64.b64encode(raw).decode(), **proof}

    def export(self, name):
        if not isinstance(name, str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,49}', name): raise ValueError('Invalid chip name')
        path = ROOT / (name + '.nexochip')
        builtin = path.is_file()
        if not builtin: path = self.chips.root / (name + '.nexochip')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000: raise ValueError('Chip not available')
        raw = path.read_bytes(); proof = inspect(raw)
        if builtin and self.chips.pins.get(path.name) != proof['sha256']: raise ValueError('Built-in integrity check failed')
        return {'filename': name + '.nexochip', 'data': base64.b64encode(raw).decode(), **proof}
