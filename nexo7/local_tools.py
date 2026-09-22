"""Deterministic, read-only helpers for explicitly saved workspace files."""
import ast
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path


def dates(value):
    parts = value.split()
    if len(parts) != 2: raise ValueError('Use two ISO dates: YYYY-MM-DD YYYY-MM-DD')
    first, last = map(date.fromisoformat, parts)
    return {'start':first.isoformat(), 'end':last.isoformat(), 'days':(last-first).days}


def csv_summary(content):
    reader = csv.reader(io.StringIO(content))
    try: headers = next(reader)
    except StopIteration: raise ValueError('CSV is empty')
    if not 1 <= len(headers) <= 50 or len(set(headers)) != len(headers):
        raise ValueError('CSV needs 1 to 50 uniquely named columns')
    columns = [[] for _ in headers]; rows = 0
    for row in reader:
        if len(row) != len(headers): raise ValueError('CSV rows have inconsistent column counts')
        rows += 1
        if rows > 5000: raise ValueError('CSV limit: 5000 rows')
        for column, value in zip(columns, row): column.append(value)
    stats = []
    for name, values in zip(headers, columns):
        nonempty = [v.strip() for v in values if v.strip()]
        item = {'column':name[:120], 'nonempty':len(nonempty), 'missing':rows-len(nonempty)}
        try:
            numbers = [Decimal(v) for v in nonempty]
            if numbers and all(n.is_finite() and abs(n) < Decimal('1e50') and n.as_tuple().exponent >= -50 for n in numbers):
                total = sum(numbers, Decimal(0))
                item.update(sum=str(total), mean=str(total/len(numbers)), minimum=str(min(numbers)), maximum=str(max(numbers)))
        except (InvalidOperation, ValueError): pass
        stats.append(item)
    return {'rows':rows, 'columns':stats, 'note':'Blank cells excluded from numeric statistics; nonnumeric columns have no numeric totals.'}


def find_file(workspace, name):
    if workspace is None: raise ValueError('Workspace tools are available in the desktop application')
    matches = [x for x in workspace.list() if name in (x['id'], x['name'])]
    if len(matches) != 1: raise ValueError('Specify one unique workspace filename or its file ID')
    return workspace.read(matches[0]['id'])


def inspect_file(workspace, name):
    item = find_file(workspace, name); text = item['content']; suffix = Path(item['name']).suffix.lower()
    if suffix == '.csv': return {'file':item['name'], **csv_summary(text)}
    if suffix == '.json':
        try: value = json.loads(text)
        except (ValueError, RecursionError): raise ValueError('Invalid or excessively nested JSON') from None
        return {'file':item['name'], 'valid_json':True, 'type':type(value).__name__,
                'items':len(value) if isinstance(value,(list,dict)) else None,
                'keys':list(value)[:50] if isinstance(value,dict) else []}
    if suffix == '.py':
        try: tree = ast.parse(text)
        except (SyntaxError, RecursionError) as exc:
            return {'file':item['name'], 'syntax_valid':False, 'error':str(exc)[:300], 'executed':False}
        return {'file':item['name'], 'syntax_valid':True,
                'functions':[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))][:50],
                'classes':[n.name for n in ast.walk(tree) if isinstance(n,ast.ClassDef)][:50],
                'executed':False,'note':'Syntax inspection is not a correctness or security audit.'}
    return {'file':item['name'], 'characters':len(text), 'lines':len(text.splitlines()), 'words':len(text.split())}
