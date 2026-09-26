"""Encrypted offline transfer. Imports create a separate profile; no live data is overwritten."""
import base64
import hashlib
import json
from pathlib import Path
import secrets
import shutil
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .vault import derive,b64,unb64,ITERATIONS
from .trust import Trust

AAD=b'nexo-transfer-v1'
MAX_BYTES=4_000_000


def validate(payload):
    if not isinstance(payload,dict) or payload.get('format')!='nexo-profile-v1':raise ValueError('Unsupported profile bundle')
    if len(json.dumps(payload).encode())>MAX_BYTES:raise ValueError('Profile limit: 4 MB')
    identity=payload.get('identity',{})
    try:
        raw=bytes.fromhex(identity['private_key']);key=Ed25519PrivateKey.from_private_bytes(raw)
        public=key.public_key().public_bytes_raw().hex()
        if identity['public_key']!=public or identity['id']!='nexo:'+hashlib.sha256(bytes.fromhex(public)).hexdigest():raise ValueError()
    except Exception:raise ValueError('Profile identity is invalid') from None
    docs=payload.get('documents',[])
    if not isinstance(docs,list) or len(docs)>200:raise ValueError('Profile limit: 200 saved documents')
    for doc in docs:
        if not isinstance(doc,dict):raise ValueError('Invalid saved document')
        for field,limit in [('title',160),('content',200000),('source',500)]:
            if not isinstance(doc.get(field),str) or not (0 if field=='source' else 1)<=len(doc[field].strip())<=limit:raise ValueError('Invalid saved document field')
        example=doc.get('example')
        if example is not None:
            from .learning import validate_entry
            validate_entry(example)
            provenance=doc.get('provenance')
            if provenance is not None and (not isinstance(provenance,dict) or type(provenance.get('expires')) not in (int,float) or len(json.dumps(provenance))>10000):raise ValueError('Invalid note provenance')
    prefs=payload.get('preferences',{})
    from .personality import PERSONALITIES
    if not isinstance(prefs,dict) or prefs.get('personality','neutral') not in PERSONALITIES:raise ValueError('Invalid personality')
    reminders=payload.get('reminders',[])
    if not isinstance(reminders,list) or len(reminders)>100:raise ValueError('Invalid reminders')
    for reminder in reminders:
        if not isinstance(reminder,dict) or not isinstance(reminder.get('text'),str) or not 1<=len(reminder['text'])<=500:raise ValueError('Invalid reminder')
        due=reminder.get('due')
        if type(due) not in (int,float) or not 0<due<32_503_680_000:raise ValueError('Invalid reminder time')
    return payload


def encrypt(payload,phrase):
    validate(payload);salt=secrets.token_bytes(16);nonce=secrets.token_bytes(12)
    cipher=AESGCM(derive(phrase,salt)).encrypt(nonce,json.dumps(payload,ensure_ascii=False).encode(),AAD)
    return {'format':'nexo-transfer-v1','kdf':'PBKDF2-SHA256','iterations':ITERATIONS,
            'salt':b64(salt),'nonce':b64(nonce),'ciphertext':b64(cipher)}


def decrypt(envelope,phrase):
    try:
        if not isinstance(envelope,dict) or envelope.get('format')!='nexo-transfer-v1' or envelope.get('kdf')!='PBKDF2-SHA256' or envelope.get('iterations')!=ITERATIONS:raise ValueError()
        if len(json.dumps(envelope))>6_000_000:raise ValueError()
        salt,nonce,cipher=map(unb64,(envelope['salt'],envelope['nonce'],envelope['ciphertext']))
        if len(salt)!=16 or len(nonce)!=12:raise ValueError()
        payload=json.loads(AESGCM(derive(phrase,salt)).decrypt(nonce,cipher,AAD))
    except Exception:raise ValueError('Could not decrypt the bundle. Check the pairing phrase and file.') from None
    return validate(payload)


def export_profile(store,reminders,phrase):
    with store.trust.action('transfer.export'),store.lock:
        documents=[dict(r) for r in store.db.execute('SELECT id,title,content,source FROM documents ORDER BY created LIMIT 201')]
        from .learning import Learning
        Learning(store)
        for doc in documents:
            example=store.db.execute('SELECT l.question,l.answer,l.language,l.kind,p.metadata FROM learning l LEFT JOIN learning_provenance p ON p.id=l.id WHERE l.document_id=?',(doc.pop('id'),)).fetchone()
            if example:
                doc['example']={k:example[k] for k in ('question','answer','language','kind')}
                if example['metadata']:doc['provenance']=json.loads(example['metadata'])
        # No OAuth tokens, web API keys, audit history or downloaded model weights.
        payload={'format':'nexo-profile-v1','identity':{**store.trust.identity(),'private_key':store.trust.key.private_bytes_raw().hex()},
            'preferences':{k:v for k,v in store.preferences().items() if k in ('personality','adapt_tone','style','response_language')},
            'documents':documents,'reminders':reminders}
        return encrypt(payload,phrase)


def import_profile(root,envelope,phrase):
    payload=decrypt(envelope,phrase)
    root=Path(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    identifier=secrets.token_hex(16);stage=root/('.import-'+identifier);destination=root/identifier
    stage.mkdir(mode=0o700)
    store=None
    try:
        initial=Trust(stage/'trust.sqlite3',initial_secret=bytes.fromhex(payload['identity']['private_key']));initial.close()
        from .store import Store
        store=Store(stage/'nexo.sqlite3')
        from .learning import Learning,fingerprint
        import time,uuid
        Learning(store)
        for doc in payload['documents']:
            document_id=store.add_document(doc['title'],doc['content'],doc['source'])
            if doc.get('example'):
                e=doc['example'];example_id=uuid.uuid4().hex
                with store.lock,store.db:
                    store.db.execute('INSERT OR IGNORE INTO learning VALUES(?,?,?,?,?,?,?,?)',(example_id,fingerprint(e),e['question'],e['answer'],e['language'],e['kind'],document_id,time.time()))
                    if doc.get('provenance'):store.db.execute('INSERT INTO learning_provenance VALUES(?,?)',(example_id,json.dumps(doc['provenance'])))
        store.set_preferences(payload.get('preferences',{}))
        with store.lock,store.db:store.db.execute("INSERT OR REPLACE INTO meta VALUES('seeded','1')")
        # Scheduler remains off on a newly imported device until its user enables it.
        from .navi import NaviState
        state=NaviState(stage/'navi.sqlite3')
        try:
            for r in payload.get('reminders',[]):state.add_reminder(r['text'],r['due'])
        finally:state.close()
        store.close();store=None
        stage.rename(destination)
        return {'profile':identifier,'identity':{k:v for k,v in payload['identity'].items() if k!='private_key'},
            'documents':len(payload['documents']),'reminders':len(payload.get('reminders',[])),
            'message':'Imported into a separate profile. Switch to it to use this Navi identity; your current profile remains intact.'}
    except Exception:
        if store:store.close()
        shutil.rmtree(stage,ignore_errors=True)
        raise
