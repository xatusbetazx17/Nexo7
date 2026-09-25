"""HTML acceptance criteria adapted from Emir Code TaskContract/TaskValidator.

Copyright (c) 2026 Agah Emir and Emir Code Contributors; MIT.
Python adaptation: parse real tags rather than substrings; no generated JS execution.
See licenses/EMIRCODE-MIT.txt. Structural evidence is not proof of functionality.
"""
from html.parser import HTMLParser

ALLOWED = {'html_structure', 'inline_style', 'inline_script'}


def criteria(value, name):
    if not isinstance(value, list) or len(value) > 3 or any(not isinstance(x, str) or x not in ALLOWED for x in value):
        raise ValueError('Supported criteria: html_structure, inline_style, inline_script')
    if value and not name.lower().endswith('.html'):
        raise ValueError('HTML criteria require an HTML target')
    return list(dict.fromkeys(value))


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(); self.opened = set(); self.closed = set(); self.block = None
        self.body = {'style': '', 'script': ''}; self.doctype = False

    def handle_decl(self, decl):
        if decl.lower().strip() == 'doctype html': self.doctype = True

    def handle_starttag(self, tag, attrs):
        self.opened.add(tag)
        if tag in self.body: self.block = tag

    def handle_endtag(self, tag):
        self.closed.add(tag)
        if tag == self.block: self.block = None

    def handle_data(self, data):
        if self.block: self.body[self.block] += data


def validate_html(content, checks):
    document = Structure(); document.feed(content); document.close()
    results = []
    for name in checks:
        if name == 'html_structure':
            passed = document.doctype and {'html', 'head', 'body'} <= document.opened & document.closed
        elif name == 'inline_style':
            css = document.body['style'].strip()
            passed = 'style' in document.closed and all(s in css for s in ('{', ':', '}'))
        else:
            passed = 'script' in document.closed and bool(document.body['script'].strip())
        results.append({'check': name + ' (structure only, not execution)', 'passed': passed})
    return results
