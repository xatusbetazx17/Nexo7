"""Encrypted local drafts and single-use, exact-message send approvals. No auto-send."""
import base64
from email.message import EmailMessage
from email.policy import SMTP
import hashlib
import re
import secrets
import threading
import time
import uuid
from .trust import canonical


def validate(fields):
    if not isinstance(fields, dict): raise ValueError('Invalid draft')
    result = {}
    for name in ('sender', 'to'):
        value = fields.get(name)
        if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", value):
            raise ValueError('Enter one complete From and To email address, without a display name')
        result[name] = value
    for name, limit in (('subject', 200), ('text', 6000)):
        value = fields.get(name)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit or '\x00' in value:
            raise ValueError('Add a subject (up to 200 characters) and body (up to 6,000)')
        if name == 'subject' and ('\r' in value or '\n' in value): raise ValueError('Subject must be one line')
        result[name] = value.strip()
    return result


class MailDrafts:
    def __init__(self, google):
        self.google, self.vault, self.trust = google, google.vault, google.trust
        self.lock = threading.RLock(); self.approvals = {}

    def mode(self, value=None):
        with self.lock:
            if value is not None:
                if value not in ('off', 'draft', 'confirm-send'): raise ValueError('Unknown mail access level')
                self.vault.set('mail.mode', value); self.approvals.clear()
            return self.vault.get('mail.mode') or 'off'

    def list(self):
        with self.trust.action('memory_read'), self.lock:
            return {'mode': self.mode(), 'drafts': self.vault.get('mail.drafts') or []}

    def save(self, fields):
        with self.trust.action('memory_write'), self.lock:
            if self.mode() == 'off': raise ValueError('Choose local drafts or confirmed sending first')
            content = validate(fields); drafts = self.vault.get('mail.drafts') or []
            identifier = fields.get('id'); old = next((d for d in drafts if d['id'] == identifier), None)
            if identifier and (not old or old['state'] != 'draft'): raise ValueError('Only an unsent draft can be edited')
            if not old and len(drafts) >= 5: raise ValueError('Remove an old draft first (limit 5)')
            draft = {'id': identifier or uuid.uuid4().hex, **content, 'state': 'draft', 'updated': time.time()}
            drafts = [d for d in drafts if d['id'] != draft['id']] + [draft]
            self.vault.set('mail.drafts', drafts); self.approvals.clear()
            return draft

    def remove(self, identifier):
        with self.trust.action('memory_write'), self.lock:
            drafts = self.vault.get('mail.drafts') or []
            self.vault.set('mail.drafts', [d for d in drafts if d['id'] != identifier]); self.approvals.clear()
            return {'removed': True}

    def preview(self, identifier):
        with self.trust.action('google.send.gmail_send'), self.trust.action('memory_read'), self.lock:
            if self.mode() != 'confirm-send': raise ValueError('Choose confirmed sending first')
            draft = next((d for d in self.vault.get('mail.drafts') or [] if d['id'] == identifier), None)
            if not draft or draft['state'] != 'draft': raise ValueError('An unsent draft is required')
            content = validate(draft); token = secrets.token_urlsafe(32)
            # Only the latest preview is actionable. Process restart/lock/edit invalidates it.
            self.approvals = {token: {'id': identifier, 'digest': hashlib.sha256(canonical(content)).hexdigest(),
                'expires': time.monotonic() + 120, 'policy': self.trust.policy_key()}}
            return {'approval': token, 'expires_in': 120, 'id': identifier, **content}

    def clear(self):
        with self.lock: self.approvals.clear()

    def send(self, body):
        with self.trust.action('google.send.gmail_send'), self.trust.action('memory_read'), self.lock:
            if body.get('confirm') is not True: raise ValueError('Review the recipient and exact message, then confirm send')
            approval = self.approvals.pop(body.get('approval', ''), None)
            if not approval or approval['expires'] < time.monotonic() or approval['policy'] != self.trust.policy_key():
                raise ValueError('Approval expired or permissions changed. Review the draft again.')
            if self.mode() != 'confirm-send': raise ValueError('Confirmed sending is disabled')
            drafts = self.vault.get('mail.drafts') or []
            draft = next((d for d in drafts if d['id'] == approval['id']), None)
            if not draft or draft['state'] != 'draft' or hashlib.sha256(canonical(validate(draft))).hexdigest() != approval['digest']:
                raise ValueError('The draft changed. Review it again.')
            connector = self.google.connectors['gmail_send']
            with connector.lock:
                token = connector._token()
                if not self.trust.allowed('google.send.gmail_send'): raise ValueError('Sending permission was revoked')
                message = EmailMessage(policy=SMTP)
                message['From'] = draft['sender']; message['To'] = draft['to']; message['Subject'] = draft['subject']
                message['Message-ID'] = '<' + draft['id'] + '@nexo.local>'
                message.set_content(draft['text'])
                # Persist before dispatch: a crash or uncertain response must never auto-retry.
                draft['state'] = 'delivery-unknown'; self.vault.set('mail.drafts', drafts)
                try:
                    result = connector.transport('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
                        token=token, json_body={'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()})
                    if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                        raise ValueError('Missing send receipt')
                except Exception:
                    raise ValueError('Delivery is uncertain. Check Gmail Sent before creating another draft; this message will not be retried automatically.') from None
                draft['state'] = 'sent'; draft['receipt'] = result['id'][:200]
                self.vault.set('mail.drafts', drafts)
                return {'sent': True, 'id': draft['id'], 'receipt': draft['receipt']}
