"""Authenticated desktop endpoints for optional Navi modules."""
import re,threading,time
from pathlib import Path
from .transfer import export_profile,import_profile
from .vault import atomic_private
import json


def post(navi,path,body,server):
    operation=path.removeprefix('/api/navi/')
    state=navi.state;google=navi.google;trust=navi.store.trust
    if operation=='settings':return navi.configure(body)
    if operation=='reminder':return state.add_reminder(body.get('text'),body.get('due'))
    if operation=='remove-reminder':state.remove_reminder(body.get('id'));return {'removed':True}
    if operation=='seen':state.seen(body.get('id'));return {'seen':True}
    if operation=='listening':
        if type(body.get('active')) is not bool:raise ValueError('Invalid microphone state')
        with navi.lock:navi.listening_until=time.monotonic()+35 if body['active'] else 0
        return navi.presence()
    if operation=='briefing':return navi.briefing()
    if operation=='vault/unlock':navi.vault.unlock(body.get('phrase'));return google.status()
    if operation=='vault/lock':google.close_pending();navi.vault.lock_now();return google.status()
    if operation=='google/configure':return google.configure(body)
    if operation=='google/authorize':return google.authorize(body.get('service'))
    if operation=='google/toggle':return google.toggle(body.get('service'),body.get('enabled'))
    if operation=='google/revoke':
        if body.get('consent') is not True:raise ValueError('Confirm disconnection first')
        return google.revoke(body.get('service'))
    if operation=='google/read':
        service=body.get('service')
        if service not in google.connectors:raise ValueError('Unknown connector')
        result=google.connectors[service].read()
        if service=='gmail':
            for item in result['items']:item['security']=navi.chips.run('security-watch',item)
        return result
    if operation=='chips/preview':return navi.chips.preview(body.get('data',''))
    if operation=='chips/install':return navi.chips.install(body)
    if operation=='chips/remove':return navi.chips.remove(body.get('name'))
    if operation=='chips/run':return navi.chips.run(body.get('name'),body.get('input',{}))
    if operation.startswith('voice/'):
        if not state.settings()['voice']:raise ValueError('Enable local voice in Navi first')
        if operation=='voice/install':return navi.voice.install(body.get('language'))
        if operation=='voice/transcribe':return navi.voice.transcribe(body)
        if operation=='voice/speak':return navi.voice.speak(body)
    if operation=='transfer/export':
        if body.get('consent') is not True:raise ValueError('Confirm export of identity, personality, saved notes and reminders')
        return export_profile(navi.store,state.reminders(pending=True),body.get('phrase'))
    if operation=='transfer/import':
        if body.get('consent') is not True:raise ValueError('Confirm import into a separate profile')
        with trust.action('transfer.import'):return import_profile(navi.root/'profiles',body.get('bundle'),body.get('phrase'))
    if operation=='transfer/switch':
        if body.get('consent') is not True:raise ValueError('Confirm switching profiles and restarting Nexo')
        identifier=body.get('profile')
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid imported profile')
        destination=navi.root/'profiles'/identifier
        if destination.is_symlink() or not (destination/'nexo.sqlite3').is_file():raise ValueError('Imported profile not found')
        if not navi.controller.operation.acquire(blocking=False):raise ValueError('Finish the current model operation before switching')
        try:
            atomic_private(navi.root/'profile-choice.json',json.dumps({'profile':identifier}).encode())
            server.next_profile=destination
            threading.Thread(target=server.shutdown,daemon=True).start()
        finally:navi.controller.operation.release()
        return {'restarting':True}
    raise ValueError('Unknown Navi action')
