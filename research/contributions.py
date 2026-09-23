"""Convert explicitly reviewed contribution JSON into training-only JSONL."""
import argparse
import hashlib
import json
from pathlib import Path
from nexo7.learning import privacy_warnings
from .data import validate


def convert(paths, reviews, output):
    if not 1 <= len(paths) <= 100 or Path(output).exists():
        raise ValueError('Use 1–100 submissions and a new output path')
    if Path(reviews).stat().st_size > 1_000_000:
        raise ValueError('Review file exceeds 1 MB')
    decisions = json.loads(Path(reviews).read_text(encoding='utf-8'))
    if not isinstance(decisions, dict):
        raise ValueError('Reviews must map contribution IDs to decisions')
    rows = []
    seen = set()
    for path in paths:
        if Path(path).stat().st_size > 20000:
            raise ValueError('Oversized contribution')
        item = json.loads(Path(path).read_text(encoding='utf-8'))
        identifier = item.pop('id')
        if hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest() != identifier:
            raise ValueError('Contribution changed since its ID was generated')
        if identifier in seen:
            raise ValueError('Duplicate contribution')
        seen.add(identifier)
        decision = decisions.get(identifier, {})
        if any(decision.get(k) is not True for k in ('rights_checked','privacy_checked','facts_checked','approved')):
            raise ValueError('Every selected note needs an explicit maintainer review; omit rejected notes')
        reviewer, reason = decision.get('reviewer'), decision.get('reason')
        if not isinstance(reviewer,str) or not reviewer.strip() or not isinstance(reason,str) or not reason.strip():
            raise ValueError('Review identity and reason required')
        if item.get('format') != 'nexo-contribution-v1' or item.get('license') != 'CC0-1.0' or item.get('public_and_training_consent') is not True or item.get('rights_basis') != 'contributor-original':
            raise ValueError('Missing supported rights/consent declaration')
        if privacy_warnings({'question':item['question'],'answer':item['answer']}):
            raise ValueError('Possible private data; re-review before admission')
        source = item['reference_url']
        rows.append({'id':identifier, 'group':hashlib.sha256(source.encode()).hexdigest(), 'split':'train',
            'prompt':item['question'], 'answer':item['answer'], 'language':item['language'],
            'source':source, 'license':'CC0-1.0', 'approved':True, 'training_allowed':True,
            'provenance':{'contribution':identifier, 'reviewer':reviewer, 'review_reason':reason,
                          'rights_statement':item['rights_statement'], 'retrieved_at':item['retrieved_at']}})
    validate(rows, require_all=False)
    with Path(output).open('x',encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('submissions',nargs='+');parser.add_argument('--reviews',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();convert(args.submissions,args.reviews,args.output)
