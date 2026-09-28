"""Strict model-accuracy diagnostic, separate from application packaging acceptance.

CI intentionally shows this known failure without claiming it is fixed. Actual
answers are retained in model-answer-review artifacts. Do not replace with a
canned answer or interpret a keyword pass as general accuracy.
"""
import json
from pathlib import Path
import sys

report=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if report.get('spanish_comparison_quality_passed') is not True:
    raise SystemExit('KNOWN MODEL ACCURACY FAILURE: Spanish chicken/hen comparison. See actual answer in native-smoke.json. This release fixes application features, not this model limitation.')
print('Comparison keyword check passed; semantic review is still required.')
