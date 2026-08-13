import math
import os
import struct
import wave

from PIL import Image, ImageDraw

import config


def ensure_assets(app):
    os.makedirs(config.ICON_DIR, exist_ok=True)
    _ensure_icons()
    sounds_dir = os.path.join(app.static_folder, 'sounds')
    os.makedirs(sounds_dir, exist_ok=True)
    _ensure_sounds(sounds_dir)


# --------------------------------------------------------------- иконки

def _draw_icon(size, path):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c1 = (47, 181, 167)
    c2 = (22, 126, 124)
    base = Image.new('RGBA', (size, size))
    px = base.load()
    for y in range(size):
        t = y / size
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b, 255)
    mask = Image.new('L', (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1],
                         radius=int(size * 0.22), fill=255)
    img.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(img)
    cy = int(size * 0.5)
    # капсула
    d.rounded_rectangle(
        [int(size * 0.12), cy - int(size * 0.15),
         int(size * 0.88), cy + int(size * 0.15)],
        radius=int(size * 0.15), fill=(255, 255, 255, 240))
    # крестик
    cx, cy = int(size * 0.5), int(size * 0.5)
    w = int(size * 0.065)
    h = int(size * 0.27)
    color = (30, 130, 126, 255)
    d.rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=color)
    d.rectangle([cx - h // 2, cy - w // 2, cx + h // 2, cy + w // 2], fill=color)
    img.save(path, 'PNG')


def _ensure_icons():
    for size in (192, 512):
        path = os.path.join(config.ICON_DIR, f'icon-{size}.png')
        if not os.path.exists(path):
            _draw_icon(size, path)
    # Если custom-icon.png — это просто старый авто-копия стандартной иконки,
    # убираем её, чтобы честно отличать «пользователь загрузил иконку» от «нет».
    custom = os.path.join(config.ICON_DIR, 'custom-icon.png')
    if os.path.exists(custom):
        try:
            with open(custom, 'rb') as f1, \
                    open(os.path.join(config.ICON_DIR, 'icon-192.png'), 'rb') as f2:
                if f1.read() == f2.read():
                    os.remove(custom)
        except OSError:
            pass


# --------------------------------------------------------------- звуки

SR = 22050


def _tone(dur, freq, vol=0.5, attack=0.01, decay=2.0, harmonics=()):
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / attack) if attack else 1.0
        env *= math.exp(-decay * t)
        s = math.sin(2 * math.pi * freq * t)
        for hf, hv in harmonics:
            s += hv * math.sin(2 * math.pi * freq * hf * t)
        out.append(vol * env * s)
    return out


def _write(path, tracks, seconds):
    n = int(SR * seconds)
    samples = [0.0] * n
    for tr in tracks:
        for i, v in enumerate(tr):
            if i < n:
                samples[i] += v
    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        data = b''.join(
            struct.pack('<h', int(max(-1, min(1, s)) * 32767)) for s in samples)
        w.writeframes(data)


def _chime():
    dur = 2.2
    tracks = []
    for t, f, v in [(0.0, 523.25, 0.50), (0.45, 659.25, 0.45), (0.9, 783.99, 0.40)]:
        tone = _tone(1.3, f, v, attack=0.004, decay=1.8,
                     harmonics=[(2, 0.25), (3, 0.10), (4, 0.05)])
        track = [0.0] * int(SR * dur)
        idx = int(t * SR)
        for i, x in enumerate(tone):
            if idx + i < len(track):
                track[idx + i] = x
        tracks.append(track)
    return tracks, dur


def _bell():
    dur = 2.6
    tone = _tone(dur, 880, 0.5, attack=0.002, decay=1.4,
                 harmonics=[(2.01, 0.22), (2.7, 0.13), (3.98, 0.07), (5.4, 0.03)])
    return [tone], dur


def _pulse():
    dur = 2.0
    tracks = []
    for k in range(4):
        tone = _tone(0.35, 660, 0.42, attack=0.01, decay=7)
        track = [0.0] * int(SR * dur)
        idx = int(k * 0.5 * SR)
        for i, x in enumerate(tone):
            if idx + i < len(track):
                track[idx + i] = x
        tracks.append(track)
    return tracks, dur


def _marimba():
    dur = 2.2
    tracks = []
    for t, f in [(0.0, 659.25), (0.4, 830.61), (0.8, 987.77), (1.2, 1244.5)]:
        tone = _tone(0.8, f, 0.42, attack=0.004, decay=4.5,
                     harmonics=[(4, 0.16), (9, 0.04)])
        track = [0.0] * int(SR * dur)
        idx = int(t * SR)
        for i, x in enumerate(tone):
            if idx + i < len(track):
                track[idx + i] = x
        tracks.append(track)
    return tracks, dur


def _ensure_sounds(sounds_dir):
    files = {
        'chime.wav': _chime,
        'bell.wav': _bell,
        'pulse.wav': _pulse,
        'marimba.wav': _marimba,
    }
    for name, fn in files.items():
        path = os.path.join(sounds_dir, name)
        if not os.path.exists(path):
            tracks, dur = fn()
            _write(path, tracks, dur)
