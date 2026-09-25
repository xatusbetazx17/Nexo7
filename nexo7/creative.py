"""Bounded offline graphics and score rendering; no generated code execution."""
import base64
import io
import math
import re
import struct
import wave
from xml.sax.saxutils import escape


def number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number from {low} to {high}')
    return value


def integer(value, low, high, label):
    number(value, low, high, label)
    if type(value) is not int:
        raise ValueError(f'{label} must be an integer')
    return value


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Colors must use #RRGGBB')
    return value


def file(name, mime, data):
    return {'name': name, 'mime': mime, 'data': base64.b64encode(data).decode('ascii')}


def drawing(spec):
    from PIL import Image, ImageDraw
    width = integer(spec.get('width', 512), 64, 1024, 'width')
    height = integer(spec.get('height', 512), 64, 1024, 'height')
    background = color(spec.get('background', '#ffffff'))
    shapes = spec.get('shapes')
    if not isinstance(shapes, list) or not 1 <= len(shapes) <= 128:
        raise ValueError('Supply 1 to 128 shapes')
    image = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(image)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" fill="{background}"/>']
    for shape in shapes:
        if not isinstance(shape, dict):
            raise ValueError('Each shape must be an object')
        kind = shape.get('type')
        fill = color(shape.get('color', '#000000'))
        if kind in ('ellipse', 'rect', 'line'):
            box = shape.get('box')
            if not isinstance(box, list) or len(box) != 4:
                raise ValueError('box must contain x1, y1, x2, y2')
            x1, y1, x2, y2 = [integer(v, 0, width if i % 2 == 0 else height, 'coordinate') for i, v in enumerate(box)]
            if kind != 'line' and (x2 <= x1 or y2 <= y1):
                raise ValueError('Shape bounds must have positive width and height')
            if kind == 'line':
                stroke = integer(shape.get('stroke', 3), 1, 32, 'stroke')
                draw.line(box, fill=fill, width=stroke)
                svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{fill}" stroke-width="{stroke}"/>')
            elif kind == 'rect':
                draw.rectangle(box, fill=fill)
                svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{fill}"/>')
            else:
                draw.ellipse(box, fill=fill)
                svg.append(f'<ellipse cx="{(x1+x2)/2}" cy="{(y1+y2)/2}" rx="{(x2-x1)/2}" ry="{(y2-y1)/2}" fill="{fill}"/>')
        elif kind == 'text':
            text = shape.get('text')
            if not isinstance(text, str) or not 1 <= len(text) <= 120 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in text):
                raise ValueError('Text must contain 1 to 120 printable characters')
            x = integer(shape.get('x', 0), 0, width, 'x')
            y = integer(shape.get('y', 0), 0, height, 'y')
            size = integer(shape.get('size', 24), 8, 72, 'text size')
            draw.text((x, y), text, fill=fill, font_size=size)
            svg.append(f'<text x="{x}" y="{y+size}" font-size="{size}" fill="{fill}">{escape(text)}</text>')
        else:
            raise ValueError('Shape type must be ellipse, rect, line or text')
    svg.append('</svg>')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return [file('drawing.png', 'image/png', output.getvalue()),
            file('drawing.svg', 'image/svg+xml', ''.join(svg).encode())]


def vlq(value):
    result = [value & 127]
    while value >> 7:
        value >>= 7
        result.insert(0, (value & 127) | 128)
    return bytes(result)


def music(spec):
    bpm = integer(spec.get('bpm', 100), 40, 240, 'bpm')
    instrument = spec.get('instrument', 'soft')
    if instrument not in ('soft', 'bell', 'synth'):
        raise ValueError('instrument must be soft, bell or synth')
    notes = spec.get('notes')
    if not isinstance(notes, list) or not 1 <= len(notes) <= 256:
        raise ValueError('Supply 1 to 256 notes')
    events, parsed = [], []
    for note in notes:
        if not isinstance(note, dict):
            raise ValueError('Each note must be an object')
        pitch = integer(note.get('pitch'), 36, 96, 'MIDI pitch')
        start = number(note.get('start'), 0, 64, 'start beat')
        duration = number(note.get('duration'), 0.125, 8, 'duration beats')
        velocity = integer(note.get('velocity', 80), 1, 127, 'velocity')
        end = start + duration
        if end * 60 / bpm > 30:
            raise ValueError('Music is limited to 30 seconds; shorten the score or raise bpm')
        parsed.append((pitch, start * 60 / bpm, duration * 60 / bpm, velocity))
        events.extend([(round(start*480), 1, pitch, velocity), (round(end*480), 0, pitch, 0)])
    # Bound synthesis work as well as output duration: at most eight simultaneous voices.
    active = 0
    pitches = set()
    for _, on, pitch, _ in sorted(events):
        if on and pitch in pitches:
            raise ValueError('Notes with the same pitch cannot overlap; merge or move them')
        if on: pitches.add(pitch)
        else: pitches.discard(pitch)
        active += 1 if on else -1
        if active > 8:
            raise ValueError('At most eight simultaneous notes are supported')
    rate = 16000
    length = math.ceil(max(start + duration for _, start, duration, _ in parsed) * rate)
    from array import array
    samples = array('f', [0]) * length
    for pitch, start, duration, velocity in parsed:
        frequency = 440 * 2 ** ((pitch-69)/12)
        first, count = round(start*rate), round(duration*rate)
        for offset in range(min(count, length-first)):
            t = offset/rate
            envelope = min(1, t/0.01, max(0, (duration-t)/0.04))
            phase = 2*math.pi*frequency*t
            value = math.sin(phase)
            if instrument == 'bell':
                value = (value + 0.3*math.sin(2*phase)) * math.exp(-3*t/duration)
            elif instrument == 'synth':
                value = (value + 0.25*math.sin(2*phase) + 0.12*math.sin(3*phase)) / 1.37
            samples[first+offset] += value * envelope * velocity/127
    peak = max(1.0, max(abs(v) for v in samples))
    pcm = bytearray(length*2)
    for i, value in enumerate(samples):
        struct.pack_into('<h', pcm, i*2, round(value/peak*26000))
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(pcm)
    tempo = round(60_000_000/bpm)
    program = {'soft': 0, 'bell': 10, 'synth': 80}[instrument]
    track = bytearray(b'\x00\xff\x51\x03' + tempo.to_bytes(3, 'big') + bytes([0, 0xc0, program]))
    previous = 0
    for tick, on, pitch, velocity in sorted(events):
        track.extend(vlq(tick-previous) + bytes([0x90 if on else 0x80, pitch, velocity]))
        previous = tick
    track.extend(b'\x00\xff\x2f\x00')
    midi = b'MThd' + struct.pack('>IHHH', 6, 0, 1, 480) + b'MTrk' + struct.pack('>I', len(track)) + track
    return [file('music.wav', 'audio/wav', output.getvalue()), file('music.mid', 'audio/midi', midi)]


def render(body):
    spec = body.get('spec')
    if not isinstance(spec, dict):
        raise ValueError('spec must be a drawing or music JSON object')
    kind = body.get('kind')
    if kind not in ('drawing', 'music'):
        raise ValueError('Choose drawing or music')
    return {'files': drawing(spec) if kind == 'drawing' else music(spec),
            'notice': 'Rendered offline. No model calls, uploads or automatic saving. Synthesized instruments are not vocals. Text appearance can differ between PNG and SVG.'}
