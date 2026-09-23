"""Explicit, original-note contribution drafts; no account tokens or uploads."""
import hashlib
import json
import re
from urllib.parse import urlencode, urlsplit, urlunsplit
from .learning import privacy_warnings


def prepare(web, body):
    if not isinstance(body, dict) or any(body.get(k) is not True for k in ('own_rights', 'no_private_data', 'publish_and_train')):
        raise ValueError('Review rights, privacy and public CC0/training consent for this exact note')
    source = next((s for s in web.list_sources() if s['id'] == body.get('source_id')), None)
    if source is None:
        raise ValueError('Choose an existing saved web source')
    note = {}
    for key, maximum in (('question', 300), ('answer', 1200), ('rights_statement', 400)):
        value = body.get(key)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            raise ValueError(f'{key} requires 1–{maximum} characters')
        note[key] = value.strip()
    language = body.get('language', '')
    if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z]{2,8})?', language):
        raise ValueError('Use a language code such as en or es')
    # A conservative copied-text screen, not a copyright or plagiarism determination.
    words = lambda text: re.findall(r'\w+', text.casefold())
    original, submitted = words(source['text']), words(note['answer'])
    spans = {tuple(original[i:i+12]) for i in range(max(0, len(original)-11))}
    if (len(original) >= 5 and original == submitted) or any(tuple(submitted[i:i+12]) in spans for i in range(max(0, len(submitted)-11))):
        raise ValueError('The note repeats a saved-source passage. Submit your own original explanation, not copied excerpts')
    parsed = urlsplit(source['url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Source needs a public HTTPS reference')
    reference = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    payload = {'format': 'nexo-contribution-v1', 'question': note['question'], 'answer': note['answer'],
        'language': language, 'reference_url': reference, 'retrieved_at': source['retrieved_at'],
        'license': 'CC0-1.0', 'rights_basis': 'contributor-original', 'rights_statement': note['rights_statement'],
        'public_and_training_consent': True, 'approved': False,
        'notice': 'Original contributor note, not a license grant for the referenced webpage. Awaiting maintainer review.'}
    warnings = privacy_warnings({'question': '', 'answer': json.dumps(payload, ensure_ascii=False)})
    if warnings:
        raise ValueError('Remove possible private data before sharing: ' + '; '.join(warnings))
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload['id'] = hashlib.sha256(canonical.encode()).hexdigest()
    text = ('I submit this original note under CC0-1.0 and permit publication, redistribution and model training. '
            'I have the necessary rights and reviewed it for private data. Source text is not included. '
            'This submission still needs factual and rights review.\n\n```json\n' + json.dumps(payload, ensure_ascii=False, indent=2) + '\n```')
    url = 'https://github.com/xatusbetazx17/Nexo7/issues/new?' + urlencode({'title': 'Knowledge contribution ' + payload['id'][:12], 'body': text})
    if len(url) > 8000:
        raise ValueError('The GitHub draft is too long. Shorten the note or rights explanation')
    return {'payload': payload, 'body': text, 'url': url, 'uploaded': False,
            'warning': 'Automated checks do not establish ownership, privacy or truth. GitHub submission is public; copies may persist.'}
