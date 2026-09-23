"""Explicit source-linked local learning, separate from raw excerpts and publication."""
import time
from .learning import FORMAT, fingerprint, validate_entry


def admit(learning, web, body):
    if body.get('reviewed') is not True:
        raise ValueError('Review the source, accuracy and exact note before saving')
    source = next((s for s in web.list_sources() if s['id'] == body.get('source_id')), None)
    if source is None or source['expired']:
        raise ValueError('Select a saved source that has not expired; refresh and review it first')
    entry = validate_entry(body.get('entry'))
    from datetime import datetime
    expires = datetime.fromisoformat(source['expires_at']).timestamp()
    metadata = {k:source[k] for k in ('id','title','url','retrieved_at','expires_at')}
    metadata.update(reviewed_at=time.time(), review='user-reviewed; not independently fact-checked', expires=expires)
    import json
    store = learning.store
    with store.lock:
        existing = store.db.execute('SELECT l.id,p.metadata FROM learning l LEFT JOIN learning_provenance p ON p.id=l.id WHERE l.fingerprint=?', (fingerprint(entry),)).fetchone()
        if existing and (not existing['metadata'] or json.loads(existing['metadata'])['url'] != source['url']):
            raise ValueError('This exact example already exists with a different source or no source link. Review and remove that example first if you want to replace it.')
        result = learning.import_pack({'format':FORMAT,'entries':[entry]}, True)
        row = store.db.execute('SELECT id FROM learning WHERE fingerprint=?', (fingerprint(entry),)).fetchone()
        linked = store.db.execute('SELECT metadata FROM learning_provenance WHERE id=?', (row['id'],)).fetchone()
        if result['added'] or (linked and json.loads(linked[0])['url'] == source['url']):
            with store.db:
                store.db.execute('INSERT OR REPLACE INTO learning_provenance VALUES(?,?)', (row['id'],json.dumps(metadata)))
                store._changed()
    return {**result,'source':metadata,'uploaded':False,'notice':'Saved as a user-reviewed reference. Automatic reuse ends at the source expiry; weights unchanged.'}
