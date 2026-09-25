"""Opt-in Telegram relay adapted from the user-supplied bot's feature design.

Uses the standard library and Nexo's authenticated, stateless local endpoint.
No token, prompt, image, reply or chat identifiers are logged or persisted here.
"""
from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit, parse_qs
from .net import fetch, fetch_json, TransportError


@dataclass(frozen=True)
class Settings:
    token: str
    chats: frozenset
    access_file: Path
    scan_images: bool = False
    rules_file: str = ''

    @classmethod
    def from_env(cls):
        from .desktop import data_directory
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,200}', token):
            raise ValueError('Set TELEGRAM_BOT_TOKEN from BotFather before starting the bridge')
        try:
            chats = frozenset(int(x.strip()) for x in os.environ.get('NEXO_TELEGRAM_CHAT_IDS', '').split(',') if x.strip())
        except ValueError:
            raise ValueError('NEXO_TELEGRAM_CHAT_IDS must contain numeric chat IDs') from None
        if not chats or len(chats) > 20 or 0 in chats:
            raise ValueError('Explicitly allow 1–20 chat IDs in NEXO_TELEGRAM_CHAT_IDS')
        return cls(token, chats, Path(os.environ.get('NEXO_ACCESS_FILE', str(data_directory() / 'access.json'))),
                   os.environ.get('NEXO_TELEGRAM_SCAN_IMAGES', '').lower() in ('1', 'true'),
                   os.environ.get('NEXO_TELEGRAM_RULES', ''))


def load_rules(path):
    if not path: return []
    with Path(path).open('rb') as stream: raw = stream.read(12_001)
    if len(raw) > 12_000: raise ValueError('Image rule file exceeds 12 KB')
    rules = json.loads(raw)
    if not isinstance(rules, list) or len(rules) > 8: raise ValueError('Use at most eight image rules')
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {'name', 'description', 'reply', 'emoji'}:
            raise ValueError('Invalid image rule fields')
        name, description = rule.get('name'), rule.get('description')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,23}', name) or name == 'NONE' or name in seen:
            raise ValueError('Use unique uppercase rule names')
        if not isinstance(description, str) or not 1 <= len(description) <= 150: raise ValueError('Rule description needs 1–150 characters')
        if not rule.get('reply') and not rule.get('emoji'): raise ValueError('Rule needs a reply or emoji')
        for field, limit in [('reply', 200), ('emoji', 16)]:
            if field in rule and (not isinstance(rule[field], str) or not 1 <= len(rule[field]) <= limit): raise ValueError('Invalid rule ' + field)
        seen.add(name)
    return rules


def matched_rules(text, rules):
    # Exact tokens only: WINDOWS must never match NOT_WINDOWS or explanatory prose.
    tokens = {x.strip() for x in text.strip().split(',')}
    names = {r['name'] for r in rules}
    if tokens == {'NONE'}: return []
    if not tokens or not tokens <= names: return []
    return [r for r in rules if r['name'] in tokens]


def addressed(message, username, bot_id):
    if message.get('chat', {}).get('type') == 'private': return True
    if message.get('reply_to_message', {}).get('from', {}).get('id') == bot_id: return True
    text = message.get('text') or message.get('caption') or ''
    encoded = text.encode('utf-16-le')
    for entity in message.get('entities', []) + message.get('caption_entities', []):
        if entity.get('type') == 'mention':
            offset, length = entity.get('offset', 0), entity.get('length', 0)
            mention = encoded[offset * 2:(offset + length) * 2].decode('utf-16-le', errors='replace')
            if mention.casefold() == ('@' + username).casefold(): return True
    return False


def chunk_text(text, limit=4000):
    chunks, current, units = [], [], 0
    for char in text[:16_000]:
        width = 2 if ord(char) > 0xffff else 1
        if units + width > limit:
            chunks.append(''.join(current)); current = []; units = 0
        current.append(char); units += width
    if current: chunks.append(''.join(current))
    return chunks


class Albums:
    def __init__(self): self.groups = {}

    def add(self, message, now):
        key = (message['chat']['id'], str(message['media_group_id']))
        if key not in self.groups:
            if len(self.groups) >= 8: return
            self.groups[key] = [now, now + 1.5, []]
        item = self.groups[key]
        # Keep a bounded set; still collect captions from either of the two photos.
        if len(item[2]) < 2: item[2].append(message)
        item[1] = min(item[0] + 5, now + 1.5)

    def due(self, now):
        ready = [key for key, item in self.groups.items() if item[1] <= now]
        return [sorted(self.groups.pop(key)[2], key=lambda m: m['message_id']) for key in ready]


class Bridge:
    def __init__(self, settings, stop=None):
        self.settings = settings
        self.stop = stop or threading.Event()
        self.rules = load_rules(settings.rules_file) if settings.scan_images else []
        self.username = ''; self.bot_id = None
        self.albums = Albums()

    def telegram(self, method, payload):
        if self.stop.is_set(): raise TransportError('Telegram bridge stopped')
        data = fetch_json('https://api.telegram.org/bot' + self.settings.token + '/' + method,
                          payload=payload, timeout=25, max_bytes=2_000_000)
        if not data.get('ok'): raise TransportError('Telegram request failed')
        return data.get('result')

    def local(self, prompt, images):
        if self.stop.is_set(): raise ValueError('Telegram bridge stopped')
        access = json.loads(self.settings.access_file.read_text())
        parsed = urlsplit(access['url'])
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port or parsed.username or parsed.password:
            raise ValueError('Nexo access file must point to its local loopback server')
        key = parse_qs(parsed.fragment).get('token', [''])[0]
        if not key: raise ValueError('Nexo local access token is missing')
        return fetch_json(f'http://127.0.0.1:{parsed.port}/api/relay',
                          payload={'message': prompt, 'images': images}, headers={'X-Nexo-Key': key}, timeout=200)

    def image(self, message):
        photos = message.get('photo') or []
        item = photos[-1] if photos else message.get('document', {})
        if not photos and item.get('mime_type') not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif'): return None
        if not item or item.get('file_size', 0) > 4_000_000: return None
        file = self.telegram('getFile', {'file_id': item['file_id']})
        path = file.get('file_path', '')
        if file.get('file_size', 0) > 4_000_000 or not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or '..' in path.split('/'):
            return None
        raw = fetch('https://api.telegram.org/file/bot' + self.settings.token + '/' + path, max_bytes=4_000_000, timeout=20)
        return base64.b64encode(raw).decode('ascii')

    def send(self, trigger, text):
        for chunk in chunk_text(text):
            self.telegram('sendMessage', {'chat_id': trigger['chat']['id'], 'text': chunk,
                          'reply_parameters': {'message_id': trigger['message_id']}, 'link_preview_options': {'is_disabled': True}})

    def process(self, messages):
        # Recheck at the action boundary; albums cannot bypass the allowlist.
        messages = [m for m in messages if m.get('chat', {}).get('id') in self.settings.chats and not m.get('from', {}).get('is_bot')]
        if not messages: return
        requested = [m for m in messages if addressed(m, self.username, self.bot_id)]
        if not requested and not self.rules: return
        trigger = requested[0] if requested else messages[0]
        sources = list(messages)
        referenced = trigger.get('reply_to_message')
        if referenced: sources.append(referenced)
        images = []
        for source in sources:
            if len(images) == 2: break
            encoded = self.image(source)
            if encoded: images.append(encoded)
        if requested:
            text = next((m.get('text') or m.get('caption') for m in requested if m.get('text') or m.get('caption')), '')
            prompt = re.sub(r'@' + re.escape(self.username) + r'\b', '', text, flags=re.I).strip()
            if len(prompt.encode('utf-8')) > 1800:
                self.send(trigger, 'Please shorten your question to 1800 UTF-8 bytes.'); return
            for index, batch in enumerate([[image] for image in images] or [[]]):
                result = self.local(prompt or ('Describe the image briefly.' if images else 'Hello'), batch)
                label = 'Image ' + str(index + 1) + ' (analyzed separately):\n' if len(images) > 1 else ''
                self.send(trigger, label + result['answer'])
        if images and self.rules:
            prompt = 'Classify these images. Reply only with matching names separated by commas, or NONE.\n' + '\n'.join(r['name'] + ': ' + r['description'] for r in self.rules)
            try:
                names = set()
                for image in images:
                    names.update(r['name'] for r in matched_rules(self.local(prompt, [image])['answer'], self.rules))
                matches = [r for r in self.rules if r['name'] in names]
                for rule in matches:
                    if rule.get('reply'): self.send(trigger, rule['reply'])
                emoji = next((r['emoji'] for r in matches if r.get('emoji')), None)
                if emoji:
                    self.telegram('setMessageReaction', {'chat_id': trigger['chat']['id'], 'message_id': trigger['message_id'], 'reaction': [{'type': 'emoji', 'emoji': emoji}]})
            except (TransportError, ValueError): pass

    def run(self):
        me = self.telegram('getMe', {}); self.username = me['username']; self.bot_id = me['id']
        # Skip pre-start backlog; an old message must not trigger an unexpected reply.
        latest = self.telegram('getUpdates', {'offset': -1, 'timeout': 0, 'limit': 1, 'allowed_updates': ['message']})
        offset = latest[-1]['update_id'] + 1 if latest else 0
        while not self.stop.is_set():
            try:
                updates = self.telegram('getUpdates', {'offset': offset, 'timeout': 1 if self.albums.groups else 15, 'limit': 20, 'allowed_updates': ['message']})
            except TransportError:
                self.stop.wait(3); continue
            for update in updates:
                offset = max(offset, update['update_id'] + 1)
                message = update.get('message', {})
                if message.get('chat', {}).get('id') not in self.settings.chats or message.get('from', {}).get('is_bot'): continue
                if message.get('media_group_id'): self.albums.add(message, time.monotonic())
                else: self.process_safely([message])
            for group in self.albums.due(time.monotonic()): self.process_safely(group)

    def process_safely(self, group):
        try: self.process(group)
        except (TransportError, ValueError, OSError, KeyError):
            # No raw exception, URLs or tokens sent to Telegram or persisted.
            if group and addressed(group[0], self.username, self.bot_id):
                try: self.send(group[0], 'Local request failed. Check that Nexo is running and the selected model supports your input.')
                except TransportError: pass


class BridgeController:
    """Desktop opt-in lifecycle. Credentials exist only in process memory."""
    def __init__(self, access_file):
        self.access_file = Path(access_file)
        self.lock = threading.Lock(); self.stop_event = threading.Event(); self.thread = None
        self.phase = 'off'; self.error = None; self.chat_count = 0

    def snapshot(self):
        with self.lock: return {'phase': self.phase, 'error': self.error, 'chat_count': self.chat_count}

    def discover(self, body):
        if body.get('consent') is not True: raise ValueError('Consent is required to read recent chat IDs from Telegram')
        token = body.get('token')
        if not isinstance(token, str) or not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,200}', token): raise ValueError('Enter a valid BotFather token')
        with self.lock:
            if self.thread and self.thread.is_alive(): raise ValueError('Stop the bridge before discovering chat IDs')
            bridge = Bridge(Settings(token, frozenset(), self.access_file))
            updates = bridge.telegram('getUpdates', {'limit': 20, 'timeout': 0, 'allowed_updates': ['message']})
        chats = {}
        for update in updates:
            chat = update.get('message', {}).get('chat', {})
            if type(chat.get('id')) is int: chats[chat['id']] = {'id': chat['id'], 'type': chat.get('type', 'unknown')}
        return {'chats': list(chats.values()), 'notice': 'Choose only your intended chat IDs. Message content was not saved. If empty, send a new message to your bot in Telegram and try again.'}

    def start(self, body):
        if body.get('consent') is not True: raise ValueError('Enable Telegram only after reviewing where messages will be sent')
        token, chats = body.get('token'), body.get('chat_ids')
        if not isinstance(token, str) or not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,200}', token): raise ValueError('Enter a valid BotFather token')
        if not isinstance(chats, list) or not 1 <= len(chats) <= 20 or any(type(x) is not int or not x or abs(x) > 2**52 for x in chats): raise ValueError('Enter 1–20 numeric Telegram chat IDs')
        with self.lock:
            if self.thread and self.thread.is_alive(): raise ValueError('Stop the active Telegram bridge first')
            self.stop_event = threading.Event(); self.phase = 'starting'; self.error = None; self.chat_count = len(set(chats))
            settings = Settings(token, frozenset(chats), self.access_file)
            def work():
                try:
                    with self.lock: self.phase = 'running'
                    Bridge(settings, self.stop_event).run()
                except Exception:
                    with self.lock: self.error = 'Telegram could not start or continue. Check the token, connection and Nexo setup.'
                finally:
                    with self.lock: self.phase = 'off'; self.chat_count = 0
            self.thread = threading.Thread(target=work, name='nexo-telegram', daemon=True)
            self.thread.start()
        return self.snapshot()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            if self.thread and self.thread.is_alive(): self.phase = 'stopping'
        return self.snapshot()


def main():
    try: Bridge(Settings.from_env()).run()
    except KeyboardInterrupt: pass


if __name__ == '__main__': main()
