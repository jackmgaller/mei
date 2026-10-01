#!/usr/bin/env python3
"""Generates the assets of the "eclipse" boot theme (system/boot/eclipse.akr) into
system/boot/eclipse/:

  tex.bin   4-bit texture for slot 0, 128 rows of 128 bytes: the character 明 (sharp and
            blurred), the moon, a soft glow, a sparkle and the MEI wordmark
  pal.bin   4-bit palettes 0 (grey ramp, tinted when drawn) and 1 (moon)
  snd.bin   all sound pieces: signed 8-bit block-companded (see below), or 16-bit
  vol.bin   per-frame channel volumes for every sound event (left, right)
  gen.akr   generated constants: sun mesh, stars, texture layout, sound event table

Sound: everything is synthesised here with numpy (additive, FM, filtered noise, a
convolution reverb with a synthetic impulse response), then cut into "pieces". Each piece is
stored as 8-bit samples together with a per-frame gain: the theme writes that gain into the
channel's VOL register every frame, so a quiet reverb tail keeps its full 8-bit resolution
(block floating point, like the PlayStation's ADPCM). Long tails switch to a half-rate copy
(played at pitch 0.5) once their high frequencies have died away. The opening bowl strike,
which plays alone, is 16-bit. The event table says which
piece starts on which channel at which frame; gen.akr carries it to the theme.

Usage: python3 tools/gen_boot_eclipse.py [--preview DIR]   (DIR gets a wav + spectrogram)
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'system', 'boot', 'eclipse')
SR = 22050
HALF = SR // 2
FRAME = SR / 60.0            # 367.5 samples per frame
THEME_FRAMES = 450           # 7.5 s
BUDGET = 240 * 1024

# ----------------------------------------------------------------------------- textures

def c15(r, g, b):
    return (int(r) >> 3) | ((int(g) >> 3) << 5) | ((int(b) >> 3) << 10)

TEX_W, TEX_H = 256, 128
tex = np.zeros((TEX_H, TEX_W), np.uint8)

def put(region, u, v):
    h, w = region.shape
    assert u + w <= 255 and v + h <= 255
    tex[v:v + h, u:u + w] = region

def quant(a, levels=15, dither=False, seed=0):
    """float 0..1 -> palette index 0..levels (0 transparent)."""
    a = np.clip(a, 0, 1) * levels
    if dither:
        a = a.copy()
        h, w = a.shape
        out = np.zeros_like(a, dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                q = int(np.clip(round(a[y, x]), 0, levels))
                out[y, x] = q
                e = a[y, x] - q
                if x + 1 < w: a[y, x + 1] += e * 7 / 16
                if y + 1 < h:
                    if x > 0: a[y + 1, x - 1] += e * 3 / 16
                    a[y + 1, x] += e * 5 / 16
                    if x + 1 < w: a[y + 1, x + 1] += e * 1 / 16
        return out
    return np.clip(np.round(a), 0, levels).astype(np.uint8)

def render_text(s, font, size, box, spacing=0, ss=4, stroke=0):
    """Supersampled white text on black, returns float array box=(w,h) and letter spans."""
    W, H = box
    img = Image.new('L', (W * ss, H * ss), 0)
    d = ImageDraw.Draw(img)
    F = ImageFont.truetype(font[0], size * ss, index=font[1])
    widths = [F.getlength(c) for c in s]
    total = sum(widths) + spacing * ss * (len(s) - 1)
    bbox = d.textbbox((0, 0), s[0], font=F)
    asc = F.getbbox('M')
    x = (W * ss - total) / 2
    y = (H * ss - (asc[3] - asc[1])) / 2 - asc[1]
    spans = []
    for c, wd in zip(s, widths):
        d.text((x, y), c, font=F, fill=255, stroke_width=int(round(stroke * ss)), stroke_fill=255)
        bb = d.textbbox((x, y), c, font=F)
        spans.append((bb[0] / ss, bb[2] / ss))
        x += wd + spacing * ss
    img = img.resize((W, H), Image.BOX)
    return np.asarray(img, np.float32) / 255.0, spans

def build_textures():
    info = {}
    # --- 明, 92x92 at (0,0), its glow at (92,0)
    G = 92
    ss = 4
    img = Image.new('L', (G * ss, G * ss), 0)
    d = ImageDraw.Draw(img)
    F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ明朝 ProN.ttc', 84 * ss, index=0)
    bb = d.textbbox((0, 0), '明', font=F)
    x = (G * ss - (bb[2] - bb[0])) / 2 - bb[0]
    y = (G * ss - (bb[3] - bb[1])) / 2 - bb[1]
    d.text((x, y), '明', font=F, fill=255)
    img = img.filter(ImageFilter.MaxFilter(5))          # a little heavier than W3
    g = np.asarray(img.resize((G, G), Image.BOX), np.float32) / 255.0
    glyph = quant(g ** 0.8)
    put(glyph, 0, 0)
    # split between 日 and 月: the emptiest column in the middle third
    cols = (glyph > 0).sum(axis=0)
    mid = range(G // 4, G // 2 + 4)
    split = min(mid, key=lambda c: (cols[c], abs(c - G * 0.42)))
    info['GLYPH_SPLIT'] = split
    blur = Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    blur = blur.filter(ImageFilter.GaussianBlur(4.5))
    b = np.asarray(blur, np.float32) / 255.0
    b = b / b.max()
    put(quant(b ** 0.9, dither=True, seed=1), 92, 0)

    # --- the moon, 64x64 at (186,0): radius 28, pale, cool, with maria and craters
    M = 64
    ss = 4
    yy, xx = np.mgrid[0:M * ss, 0:M * ss].astype(np.float32)
    cx = cy = M * ss / 2 - 0.5
    R = 28 * ss
    dx, dy = (xx - cx) / R, (yy - cy) / R
    r2 = dx * dx + dy * dy
    inside = r2 <= 1.0
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    rng = np.random.default_rng(7)
    lum = 0.80 + 0.20 * nz                               # limb darkening
    # maria: blobs of low-frequency noise
    def blob(px, py, rad, amt):
        return amt * np.exp(-(((dx - px) ** 2 + (dy - py) ** 2) / rad ** 2))
    lum -= blob(-0.30, -0.25, 0.32, 0.22) + blob(0.10, -0.38, 0.22, 0.16) + blob(0.28, 0.12, 0.30, 0.18)
    lum -= blob(-0.15, 0.30, 0.20, 0.12) + blob(0.45, -0.20, 0.16, 0.10)
    for i in range(16):                                   # craters: dark floor, bright rim
        px, py = rng.uniform(-0.8, 0.8, 2)
        if px * px + py * py > 0.75:
            continue
        rad = rng.uniform(0.05, 0.14)
        dd = np.sqrt((dx - px) ** 2 + (dy - py) ** 2) / rad
        lum -= 0.10 * np.exp(-dd ** 4)
        lum += 0.08 * np.exp(-((dd - 1.05) / 0.18) ** 2) * (((dx - px) * -0.7 + (dy - py) * -0.7) > 0)
    lum = np.clip(lum, 0, 1)
    lum_s = np.zeros((M, M), np.float32)
    cov = np.zeros((M, M), np.float32)
    for oy in range(ss):
        for ox in range(ss):
            lum_s += np.where(inside, lum, 0)[oy::ss, ox::ss]
            cov += inside[oy::ss, ox::ss]
    lum_m = lum_s / np.maximum(cov, 1)
    moon = np.where(cov >= ss * ss * 0.45, quant((lum_m - 0.40) / 0.60 * 0.93 + 0.07, 15).clip(1, 15), 0)
    put(moon.astype(np.uint8), 186, 0)

    # --- soft round glow, 64x64 at (186,64)
    yy, xx = np.mgrid[0:64, 0:64].astype(np.float32)
    r = np.sqrt((xx - 31.5) ** 2 + (yy - 31.5) ** 2) / 32.0
    glow = np.clip(1 - r, 0, 1) ** 2.2
    put(quant(glow, dither=True), 186, 64)

    # --- sparkle (four-point star), 32x32 at (128,96)
    yy, xx = np.mgrid[0:32, 0:32].astype(np.float32)
    ddx, ddy = (xx - 15.5) / 16, (yy - 15.5) / 16
    rr = np.sqrt(ddx * ddx + ddy * ddy)
    sp = np.exp(-(rr / 0.16) ** 2) + 0.9 * np.exp(-(ddy / 0.045) ** 2) * np.clip(1 - abs(ddx), 0, 1) ** 2 \
        + 0.9 * np.exp(-(ddx / 0.045) ** 2) * np.clip(1 - abs(ddy), 0, 1) ** 2
    put(quant(np.clip(sp, 0, 1)), 128, 96)

    # --- wordmark "MEI", 128x30 at (0,96), Optima, widely spaced
    wm, spans = render_text('MEI', ('/System/Library/Fonts/Optima.ttc', 0), 30, (128, 30), spacing=13, stroke=0.25)
    put(quant(wm ** 0.85), 0, 96)
    info['WM_SPANS'] = [(int(np.floor(a)) - 1, int(np.ceil(b)) + 1) for a, b in spans]

    raw = bytearray(128 * TEX_H)
    for y in range(TEX_H):
        for x in range(0, TEX_W, 2):
            raw[y * 128 + x // 2] = int(tex[y, x]) | (int(tex[y, x + 1]) << 4)
    pal = [0] * 32
    for i in range(1, 16):                                # palette 0: grey ramp
        v = round(255 * i / 15)
        pal[i] = c15(v, v, v)
    lo, hi = np.array([46, 52, 78]), np.array([236, 240, 252])
    for i in range(1, 16):                                # palette 1: the moon
        f = (i - 1) / 14
        c = lo + (hi - lo) * f ** 0.9
        pal[16 + i] = c15(*c)
    return bytes(raw), struct.pack('<32H', *pal), info

# ----------------------------------------------------------------------------- sun mesh

def icosphere():
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
         (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
         (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    cache = {}
    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k not in cache:
            p = v[a] + v[b]
            v.append(p / np.linalg.norm(p))
            cache[k] = len(v) - 1
        return cache[k]
    nf = []
    for a, b, c in f:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
        nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    # orient counter-clockwise seen from outside
    out = []
    for a, b, c in nf:
        n = np.cross(v[b] - v[a], v[c] - v[a])
        out.append((a, b, c) if np.dot(n, v[a]) > 0 else (a, c, b))
    return v, out

# ----------------------------------------------------------------------------- DSP

def secs(n, sr=SR):
    return np.arange(n) / sr

def spectrum_filter(x, sr, gain_fn):
    n = len(x)
    nfft = 1 << int(np.ceil(np.log2(n + 1)))
    X = np.fft.rfft(x, nfft)
    f = np.fft.rfftfreq(nfft, 1 / sr)
    return np.fft.irfft(X * gain_fn(f), nfft)[:n]

def lowpass(x, sr, fc, order=4):
    return spectrum_filter(x, sr, lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * order)))

def highpass(x, sr, fc, order=2):
    return spectrum_filter(x, sr, lambda f: 1 / np.sqrt(1 + (np.maximum(f, 1e-3) / fc) ** (-2 * order)))

def bandpass(x, sr, lo, hi, order=2):
    return highpass(lowpass(x, sr, hi, order), sr, lo, order)

def fftconv(a, b):
    n = len(a) + len(b) - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    return np.fft.irfft(np.fft.rfft(a, nfft) * np.fft.rfft(b, nfft), nfft)[:n]

def reverb_ir(sr, dur, rt_lo, rt_hi, seed, predelay=0.012, bright=1.0):
    """Exponentially decaying noise whose decay time falls with frequency, plus a few
    early reflections. Normalised to unit energy."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = secs(n, sr)
    noise = rng.standard_normal(n)
    edges = [0, 250, 700, 1800, 4000, 8000, sr / 2 + 1]
    ir = np.zeros(n)
    nfft = 1 << int(np.ceil(np.log2(n)))
    N = np.fft.rfft(noise, nfft)
    f = np.fft.rfftfreq(nfft, 1 / sr)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if lo >= sr / 2:
            break
        fc = (lo + min(hi, sr / 2)) / 2
        frac = np.log2(max(fc, 60) / 60) / np.log2(10000 / 60)
        rt = rt_lo + (rt_hi - rt_lo) * min(frac, 1)
        mask = ((f >= lo) & (f < hi)).astype(float)
        band = np.fft.irfft(N * mask, nfft)[:n]
        g = 1.0 if fc < 3000 else bright
        ir += g * band * np.exp(-6.91 * t / rt)
    ir *= np.clip(t / 0.03, 0, 1)                        # diffuse build-up
    pd = int(predelay * sr)
    ir = np.concatenate([np.zeros(pd), ir])[:n]
    for k, (dt, a) in enumerate([(0.007, 0.5), (0.013, -0.35), (0.019, 0.3), (0.029, 0.22)]):
        i = int(dt * sr)
        if i < n:
            ir[i] += a * rng.choice([-1, 1]) * np.sqrt(np.sum(ir ** 2)) * 0.06
    return ir / np.sqrt(np.sum(ir ** 2))

def reverb(x, sr, wet, ir):
    y = fftconv(x, ir)
    out = np.zeros(len(y))
    out[:len(x)] += x * (1 - wet * 0.35)
    out += y * wet * 0.35 * 6
    return out

def adsr_attack(n, sr, att):
    e = np.ones(n)
    a = max(1, int(att * sr))
    e[:a] = np.linspace(0, 1, a) ** 1.5
    return e

def fade_tail(x, sr, dur):
    n = int(dur * sr)
    x = x.copy()
    if n > 0:
        x[-n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
    return x

def norm(x, peak=1.0):
    return x * (peak / (np.max(np.abs(x)) + 1e-12))

NOTE = {'D2': 73.42, 'A2': 110.0, 'D3': 146.83, 'A3': 220.0, 'D4': 293.66, 'E4': 329.63,
        'F#4': 369.99, 'A4': 440.0, 'B4': 493.88, 'D5': 587.33, 'E5': 659.25, 'F#5': 739.99,
        'A5': 880.0, 'B5': 987.77, 'D6': 1174.66, 'E6': 1318.51, 'F#6': 1479.98, 'A6': 1760.0,
        'B6': 1975.53, 'D7': 2349.32, 'E7': 2637.02}

# ----------------------------------------------------------------------------- instruments

def bowl(f0, dur, sr, seed=3):
    """Singing bowl / temple bell: inharmonic partials in beating pairs, felt mallet."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = secs(n, sr)
    ratios = [1.0, 2.0, 2.74, 4.1, 5.35, 7.9, 10.6]
    amps = [1.0, 0.16, 0.62, 0.10, 0.32, 0.12, 0.06]
    taus = [7.0, 3.0, 3.8, 1.6, 2.0, 1.1, 0.7]
    beat = [0.9, 1.3, 1.7, 2.3, 2.6, 3.4, 4.1]
    y = np.zeros(n)
    for r, a, tau, bt in zip(ratios, amps, taus, beat):
        f = f0 * r
        if f > sr * 0.45:
            continue
        ph = rng.uniform(0, 2 * np.pi, 2)
        y += a * np.exp(-t / tau) * (np.sin(2 * np.pi * f * t + ph[0]) + 0.85 * np.sin(2 * np.pi * (f + bt) * t + ph[1]))
    y *= adsr_attack(n, sr, 0.004)
    # mallet: a soft low thump and a little filtered noise
    thump = np.sin(2 * np.pi * f0 * 0.5 * t) * np.exp(-t / 0.08) * 0.5
    nz = lowpass(rng.standard_normal(n), sr, 1800, 2) * np.exp(-t / 0.012) * 0.6
    return y + thump + nz

def warm_bell(f, dur, sr):
    """The sun's voice: a soft FM bell, close to a vibraphone, warm and round."""
    n = int(dur * sr)
    t = secs(n, sr)
    idx = 2.0 * np.exp(-t / 0.22) + 0.35
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    y *= np.exp(-t / 1.3) * (1 + 0.10 * np.sin(2 * np.pi * 4.6 * t))
    y += 0.30 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.45)
    y += 0.18 * np.sin(2 * np.pi * 3.98 * f * t) * np.exp(-t / 0.10)
    y *= adsr_attack(n, sr, 0.003)
    return lowpass(y, sr, 3200, 2)

def glass_bell(f, dur, sr):
    """The moon's voice: a glassy celesta, bright and cool."""
    n = int(dur * sr)
    t = secs(n, sr)
    idx = 1.4 * np.exp(-t / 0.06)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * 3.5 * f * t)) * np.exp(-t / 1.1)
    y += 0.35 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.35)
    y += 0.20 * np.sin(2 * np.pi * 5.40 * f * t) * np.exp(-t / 0.12)
    y *= adsr_attack(n, sr, 0.0015)
    return y

def gong(f0, dur, sr, seed=5):
    """A big low gong: inharmonic partials whose upper ones bloom after the strike."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = secs(n, sr)
    y = np.zeros(n)
    ratios = [1.0, 1.51, 2.0, 2.47, 2.94, 3.55, 4.18, 4.9, 5.7, 6.6, 7.7, 9.1]
    for i, r in enumerate(ratios):
        f = f0 * r
        a = 1.0 / (1 + 0.45 * i)
        tau = 5.0 / (1 + 0.35 * i)
        bloom = 1 - np.exp(-t / (0.02 + 0.06 * i))
        for k in range(2):
            ff = f * (1 + rng.uniform(-0.004, 0.004))
            y += a * 0.6 * bloom * np.exp(-t / tau) * np.sin(2 * np.pi * ff * t + rng.uniform(0, 6.3))
    nz = lowpass(rng.standard_normal(n), sr, 900, 2) * np.exp(-t / 0.05) * 1.5
    sub = np.sin(2 * np.pi * f0 * 0.5 * t) * np.exp(-t / 0.5) * 0.8 * adsr_attack(n, sr, 0.01)
    return lowpass(y + nz + sub, sr, 3000, 3)

def choir_loop(notes, period, sr, seed):
    """An 'ah' choir chord that loops seamlessly: every frequency is a whole number of
    cycles per loop, and the reverb is a circular convolution over the loop."""
    rng = np.random.default_rng(seed)
    n = int(period * sr)
    t = secs(n, sr)
    y = np.zeros(n)
    fmts = [(750, 90, 1.0), (1150, 110, 0.55), (2650, 160, 0.25), (3300, 200, 0.12)]
    def formant(f):
        g = 0.02
        for fc, bw, a in fmts:
            g += a / (1 + ((f - fc) / bw) ** 2)
        return g
    for f in notes:
        for v in range(3):
            fv = round(f * period + rng.integers(-2, 3)) / period     # whole cycles per loop
            vib_rate = round(rng.uniform(4.5, 5.8) * period) / period
            vib = 0.0035 * fv / vib_rate
            vph = rng.uniform(0, 2 * np.pi)
            k = 1
            while k * fv < min(4200, sr * 0.45):
                a = formant(k * fv) / k ** 0.9
                y += a * np.sin(2 * np.pi * k * fv * t + k * vib * np.sin(2 * np.pi * vib_rate * t + vph) + rng.uniform(0, 6.3))
                k += 1
    # breath: noise shaped by the formants, periodic by construction
    spec = np.zeros(n // 2 + 1, complex)
    f = np.fft.rfftfreq(n, 1 / sr)
    spec[1:] = np.array([formant(x) for x in f[1:]]) * np.exp(1j * rng.uniform(0, 6.3, len(f) - 1))
    breath = np.fft.irfft(spec, n)
    y = y / np.max(np.abs(y)) + 0.6 * breath / np.max(np.abs(breath))
    # circular reverb: fold the impulse response onto the loop length
    ir = reverb_ir(sr, 3.0, 3.2, 1.6, seed + 11)
    fold = np.zeros(n)
    for i in range(0, len(ir), n):
        seg = ir[i:i + n]
        fold[:len(seg)] += seg
    wet = np.fft.irfft(np.fft.rfft(y) * np.fft.rfft(fold), n)
    out = 0.45 * y + 0.9 * wet / np.max(np.abs(wet)) * np.max(np.abs(y))
    return lowpass_circ(out, sr, 4000)

def lowpass_circ(x, sr, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return np.fft.irfft(X / np.sqrt(1 + (f / fc) ** 8), len(x))

def shimmer(dur, sr, seed=9):
    """A burst of glassy tings in D major pentatonic, smeared by a bright reverb."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = secs(n, sr)
    y = np.zeros(n)
    pool = ['D6', 'E6', 'F#6', 'A6', 'B6', 'D7', 'E7', 'A5', 'B5', 'D5', 'F#5']
    for i in range(46):
        st = rng.exponential(0.25)
        if st > dur - 0.3:
            continue
        f = NOTE[pool[rng.integers(len(pool))]] * (1 + rng.uniform(-0.002, 0.002))
        m = int(min(1.2, dur - st) * sr)
        s = int(st * sr)
        tt = secs(m, sr)
        tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.15, 0.5))
        tone += 0.3 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt / 0.08)
        tone *= adsr_attack(m, sr, 0.002) * rng.uniform(0.3, 1.0) * np.exp(-st / 0.6)
        y[s:s + m] += tone
    air = highpass(rng.standard_normal(n), sr, 5000, 2) * np.exp(-t / 0.35) * 0.25
    y = y + air
    ir = reverb_ir(sr, 3.0, 3.0, 2.4, seed + 1, bright=1.2)
    return reverb(y, sr, 0.75, ir)[:n]

def swell(dur, sr, seed=13):
    """Reverse reverb of a bright chord plus a rising noise: pulls into the eclipse."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = secs(n, sr)
    y = np.zeros(n)
    for name in ['D5', 'A5', 'E6', 'F#6', 'A6']:
        y += glass_bell(NOTE[name], dur, sr)
    ir = reverb_ir(sr, 2.0, 2.0, 1.6, seed)
    wet = fftconv(y, ir)[:n]
    rev = wet[::-1] * (t / dur) ** 0.5
    nz = rng.standard_normal(n)
    riser = np.zeros(n)
    # sweep a band of noise upward
    blocks = 24
    for b in range(blocks):
        a, e = b * n // blocks, (b + 1) * n // blocks
        fc = 400 * (2 ** (4.5 * b / blocks))
        seg = bandpass(nz, sr, fc * 0.7, fc * 1.4, 2)[a:e]
        riser[a:e] = seg
    riser *= (t / dur) ** 2.5 * 0.5
    out = norm(rev) + norm(riser) * 0.35
    out *= np.clip((dur - t) / 0.01, 0, 1)                     # stop dead at the eclipse
    return out

# ----------------------------------------------------------------------------- pieces and events

class Pieces:
    """Sound pieces and the events that play them.

    A piece is 8-bit and block-companded (a gain per frame, written to VOL by the theme),
    or 16-bit with a plain volume envelope. Half-rate pieces play at pitch 0.5. Pieces are
    encoded in finish(), once the events are known, and trimmed to what the events use."""
    def __init__(self):
        self.data = bytearray()
        self.pieces = {}
        self.events = []

    def add(self, name, y, half=False, loop=False, bits=8):
        """y: float signal in output units (16-bit scale), at SR or HALF."""
        self.pieces[name] = dict(y=np.asarray(y, float), half=half, loop=loop, bits=bits, tail=None)

    def add_split(self, name, y, head_frames, xfade_frames=8, lp=3600, head_bits=8):
        """A long sound: full rate for head_frames, then a half-rate low-passed tail that
        starts xfade_frames before the head ends (both even, so the tail lines up exactly)."""
        assert head_frames % 2 == 0 and xfade_frames % 2 == 0
        start_tail = head_frames - xfade_frames
        o = int(start_tail * FRAME)
        h = int(head_frames * FRAME)
        head = y[:h].copy()
        xf = h - o
        w = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2
        head[o:] *= 1 - w
        ylp = lowpass(y, SR, lp, 4)
        tail = ylp[o::2].copy()
        tail[:len(w[::2])] *= w[::2]
        self.add(name, head, bits=head_bits)
        self.add(name + '~', tail, half=True)
        self.pieces[name]['tail'] = (name + '~', start_tail)

    def play(self, name, start, pan=(1.0, 1.0), gain=1.0, fade_at=None, fade_len=30, ch=None):
        p = self.pieces[name]
        self.events.append(dict(piece=name, start=start, pan=pan, gain=gain, fade_at=fade_at,
                                fade_len=fade_len, ch=ch))
        if p['tail']:
            tn, off = p['tail']
            self.events.append(dict(piece=tn, start=start + off, pan=pan, gain=gain, fade_at=fade_at,
                                    fade_len=fade_len, ch=None))

    def loop(self, name, start, env, pan=(1.0, 1.0), ch=None):
        """env: per-frame envelope (0..1); the loop stops when it ends."""
        self.events.append(dict(piece=name, start=start, pan=pan, env=np.asarray(env, float), ch=ch, loop=True))

    @staticmethod
    def frames_of(p, n):
        return int(np.ceil(n * (2 if p['half'] else 1) / FRAME))

    def encode(self, name):
        p = self.pieces[name]
        y = p['y']
        rate_div = 2 if p['half'] else 1
        n = len(y)
        if self.data and len(self.data) & 1:
            self.data += b'\0'
        p['off'] = len(self.data)
        p['len'] = n
        if p['bits'] == 16:
            q = np.clip(np.round(y * 256 / 255), -32767, 32767).astype('<i2')
            p['q'] = q
            p['v'] = 255
            self.data += q.tobytes()
            return
        if p['loop']:
            v = int(min(255, np.ceil(np.max(np.abs(y)) / 127)))
            q = np.clip(np.round(y / v), -127, 127).astype(np.int8)
            p['q'], p['v'] = q, v
            self.data += q.tobytes()
            return
        frames = self.frames_of(p, n)
        bounds = [min(n, int(np.floor(k * FRAME / rate_div))) for k in range(frames + 1)]
        gains = np.zeros(frames, int)
        for k in range(frames):
            a, b = max(0, bounds[k] - 1), min(n, bounds[k + 1] + 1)
            pk = np.max(np.abs(y[a:b])) if b > a else 0
            gains[k] = int(min(255, max(1, np.ceil(pk / 125.0))))
        # plain rounding with a little dither (at 22 kHz there is no band to hide shaped
        # noise in: error feedback measured worse, weighted, than white noise)
        q = np.zeros(n, np.int8)
        rng = np.random.default_rng(len(self.data))
        for k in range(frames):
            a, b = bounds[k], bounds[k + 1]
            seg = y[a:b] / gains[k] + (rng.random(b - a) - 0.5) * 0.5
            q[a:b] = np.clip(np.round(seg), -127, 127)
        p['q'], p['gains'] = q, gains
        self.data += q.tobytes()

    def finish(self, nch=6, end=THEME_FRAMES):
        """Trim and encode the pieces, allocate channels, build per-event volume tables."""
        evs = sorted(self.events, key=lambda e: e['start'])
        # how long each event lasts, and so how much of each piece is needed
        need = {}
        for e in evs:
            p = self.pieces[e['piece']]
            if e.get('loop'):
                nfr = len(e['env'])
            else:
                nfr = self.frames_of(p, len(p['y']))
                if e.get('fade_at') is not None:
                    nfr = min(nfr, e['fade_at'] + e['fade_len'] - e['start'])
            nfr = min(nfr, end - e['start'])
            e['frames'] = nfr
            need[e['piece']] = max(need.get(e['piece'], 0), nfr)
        for name, p in self.pieces.items():
            if name not in need:
                continue
            if not p['loop']:
                keep = int(np.ceil(need[name] * FRAME / (2 if p['half'] else 1))) + 2
                p['y'] = p['y'][:keep]
            self.encode(name)
        busy = [-1] * nch
        vols = bytearray()
        for e in evs:
            p = self.pieces[e['piece']]
            nfr = e['frames']
            k = np.arange(nfr) + e['start']
            if e.get('loop'):
                g = p['v'] * e['env'][:nfr]
            else:
                if p['bits'] == 16:
                    g = np.full(nfr, 255.0) * e['gain']
                else:
                    g = p['gains'][:nfr].astype(float) * e['gain']
                if e.get('fade_at') is not None:
                    g = g * np.clip(1 - (k - e['fade_at']) / e['fade_len'], 0, 1)
                g = g * np.clip((end - 2 - k) / 36.0, 0, 1) ** 1.5   # silent by the theme's end
            vl = np.clip(np.round(g * e['pan'][0]), 0, 255).astype(int)
            vr = np.clip(np.round(g * e['pan'][1]), 0, 255).astype(int)
            if e['ch'] is None:
                free = [c for c in range(nch) if busy[c] <= e['start']]
                if not free:
                    raise SystemExit('no free channel at frame %d for %s (busy until %s)' % (e['start'], e['piece'], busy))
                e['ch'] = free[0]
            else:
                assert busy[e['ch']] <= e['start'], (e, busy)
            busy[e['ch']] = e['start'] + nfr
            e['voff'] = len(vols)
            for a, b in zip(vl, vr):
                vols += bytes((a, b))
        self.events = evs
        return bytes(vols)

    def simulate(self, vols, nframes, ideal=False):
        """Mix exactly as the console will (out = sample * VOL / 256), frames of 367/368
        samples. ideal: use the unquantised signal (to measure the quantisation noise)."""
        total = int(np.ceil(nframes * FRAME)) + 2
        L = np.zeros(total)
        R = np.zeros(total)
        bounds = [int(np.floor(k * FRAME)) for k in range(nframes + 2)]
        for e in self.events:
            p = self.pieces[e['piece']]
            if p['bits'] == 16:
                q = p['q'].astype(float) / 256
            else:
                q = p['q'].astype(float)
            step = 0.5 if p['half'] else 1.0
            pos = 0.0
            for k in range(e['frames']):
                fr = e['start'] + k
                if fr >= nframes:
                    break
                vl = vols[e['voff'] + 2 * k]
                vr = vols[e['voff'] + 2 * k + 1]
                a, b = bounds[fr], bounds[fr + 1]
                idx = (pos + np.arange(b - a) * step).astype(int)
                if p['loop']:
                    idx %= p['len']
                else:
                    idx = idx[idx < p['len']]
                    b = a + len(idx)
                s = q[idx]
                if ideal:
                    s = p['y'][idx] / (p['v'] if p['loop'] or p['bits'] == 16 else p['gains'][k])
                    if p['bits'] == 16:
                        s = p['y'][idx] / 255
                L[a:b] += s * vl
                R[a:b] += s * vr
                pos += (bounds[fr + 1] - bounds[fr]) * step
        return L, R

    def mls(self, prefix):
        P = prefix.upper()
        n = len(self.events)
        def arr(name, vals):
            return 'const %s_EV_%s: [%d]s32 = [%s]\n' % (P, name, n, ', '.join(str(int(v)) for v in vals))
        ev = self.events
        pc = [self.pieces[e['piece']] for e in ev]
        s = 'const %s_EV_COUNT = %d\n' % (P, n)
        s += arr('START', [e['start'] for e in ev])
        s += arr('FRAMES', [e['frames'] for e in ev])
        s += arr('CH', [e['ch'] for e in ev])
        s += arr('OFF', [p['off'] for p in pc])
        s += arr('LEN', [p['len'] for p in pc])
        s += arr('PITCH', [32768 if p['half'] else 65536 for p in pc])
        s += arr('CTRL', [(3 if p['loop'] else 1) | (4 if p['bits'] == 16 else 0) for p in pc])
        s += arr('VOFF', [e['voff'] for e in ev])
        return s

# ----------------------------------------------------------------------------- the score

# Frames (60 per second). The theme's visuals use the same numbers (gen.akr).
T_BOWL = 12
T_SUN = [44, 152]                 # sun phrase: notes at +0, +18, +36
SUN_NOTES = [0, 18, 36]
T_MOON = [100, 184, 330]          # moon phrase: notes at +0, +10, +20, +34
MOON_NOTES = [0, 10, 20, 34]
T_SWELL_END = 250                 # the eclipse
T_UNION = 330                     # 明 + MEI, bowl again

def score():
    P = Pieces()
    # the sun: a bowl strike and a rising warm phrase (D4 F#4 A4)
    b = bowl(NOTE['D3'], 4.0, SR)
    irw = reverb_ir(SR, 3.0, 3.4, 1.8, 21)
    b = reverb(b, SR, 0.45, irw)[:int(4.0 * SR)]
    P.add_split('bowl', fade_tail(norm(b, 15000), SR, 0.8), head_frames=60, head_bits=16)

    n = int(2.5 * HALF)
    sp = np.zeros(n)
    for off, name in zip(SUN_NOTES, ['D4', 'F#4', 'A4']):
        s = int(off * FRAME / 2)
        sp[s:] += warm_bell(NOTE[name], (n - s) / HALF, HALF) * (0.9 if name != 'A4' else 1.0)
    sp = reverb(sp, HALF, 0.5, reverb_ir(HALF, 2.5, 2.6, 1.6, 22))[:n]
    P.add('sun', fade_tail(norm(sp, 11000), HALF, 0.5), half=True)

    # the moon: a quicker glassy answer (E5 F#5 A5 D6)
    n = int(2.2 * SR)
    mp = np.zeros(n)
    for off, name in zip(MOON_NOTES, ['E5', 'F#5', 'A5', 'D6']):
        s = int(off * FRAME)
        mp[s:] += glass_bell(NOTE[name], (n - s) / SR, SR) * (1.0 if name != 'D6' else 0.8)
    mp = reverb(mp, SR, 0.55, reverb_ir(SR, 2.5, 2.4, 1.9, 23, bright=1.1))[:n]
    P.add_split('moon', fade_tail(norm(mp, 9000), SR, 0.5), head_frames=64)

    # into the eclipse
    sw = swell(1.0, SR)
    P.add('swell', norm(sw, 9000))
    g = gong(NOTE['D2'], 3.4, HALF)
    g = reverb(g, HALF, 0.4, reverb_ir(HALF, 3.0, 3.8, 2.0, 24))[:int(3.4 * HALF)]
    P.add('gong', fade_tail(norm(g, 16000), HALF, 0.8), half=True)
    sh = shimmer(2.4, SR)
    P.add_split('shimmer', fade_tail(norm(sh, 9000), SR, 0.5), head_frames=56)

    # the union: a choir in D major add9, two decorrelated loops for left and right
    chord = [NOTE[x] for x in ['D3', 'A3', 'D4', 'E4', 'F#4', 'A4']]
    cl = choir_loop(chord, 1.0, HALF, 31)
    cr = choir_loop(chord, 1.0, HALF, 37)
    P.add('choirL', norm(cl, 9500), half=True, loop=True)
    P.add('choirR', norm(cr, 9500), half=True, loop=True)

    # --- events
    P.play('bowl', T_BOWL, pan=(1.0, 0.72), fade_at=190, fade_len=16)
    P.play('sun', T_SUN[0], pan=(1.0, 0.45))
    P.play('moon', T_MOON[0], pan=(0.45, 1.0))
    P.play('sun', T_SUN[1], pan=(1.0, 0.6), gain=0.95, fade_at=262, fade_len=24)
    P.play('moon', T_MOON[1], pan=(0.6, 1.0), gain=0.95)
    P.play('swell', T_SWELL_END - 60, pan=(1.0, 1.0))
    P.play('gong', T_SWELL_END, pan=(1.0, 1.0), fade_at=340, fade_len=40)
    P.play('shimmer', T_SWELL_END, pan=(0.9, 1.0), fade_at=346, fade_len=28)
    # the choir swells in under the moon's second answer and peaks at the eclipse
    env = np.concatenate([np.linspace(0, 1, 44) ** 2.2, np.ones(130), np.linspace(1, 0, 70) ** 1.5])
    P.loop('choirL', T_SWELL_END - 44, env, pan=(1.0, 0.0))
    P.loop('choirR', T_SWELL_END - 44, env, pan=(0.0, 1.0))
    P.play('bowl', T_UNION, pan=(0.95, 0.95), gain=0.9)
    P.play('moon', T_UNION, pan=(0.8, 0.95), gain=0.8)
    return P

# ----------------------------------------------------------------------------- output

def write_wav(path, L, R):
    a = np.clip(np.stack([L, R], 1), -32768, 32767).astype('<i2')
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + a.nbytes) + b'WAVEfmt ' +
                struct.pack('<IHHIIHH', 16, 1, 2, SR, SR * 4, 4, 16) + b'data' + struct.pack('<I', a.nbytes))
        f.write(a.tobytes())

def spectrogram_png(path, L, R, title=''):
    x = (L + R) / 2
    nfft, hop = 1024, 256
    win = np.hanning(nfft)
    cols = []
    for i in range(0, len(x) - nfft, hop):
        cols.append(20 * np.log10(np.abs(np.fft.rfft(x[i:i + nfft] * win)) / (nfft / 4 * 32768) + 1e-9))
    S = np.array(cols).T[::-1]
    S = np.clip((S + 110) / 100, 0, 1)        # -110 .. -10 dBFS
    h = S.shape[0]
    img = (np.stack([S ** 0.8, S ** 1.6, S ** 0.5 * 0.6 + S * 0.3], 2) * 255).astype(np.uint8)
    spec = Image.fromarray(img).resize((900, 300))
    wave = Image.new('RGB', (900, 120), (10, 10, 20))
    d = ImageDraw.Draw(wave)
    n = len(L)
    for px in range(900):
        a, b = px * n // 900, (px + 1) * n // 900
        for sig, col, off in ((L, (255, 180, 80), 0), (R, (120, 180, 255), 60)):
            seg = sig[a:b]
            if len(seg):
                lo, hi = seg.min() / 32768, seg.max() / 32768
                d.line([(px, off + 30 - hi * 30), (px, off + 30 - lo * 30)], fill=col)
    out = Image.new('RGB', (900, 440), (0, 0, 0))
    out.paste(spec, (0, 0))
    out.paste(wave, (0, 310))
    d = ImageDraw.Draw(out)
    for s in range(int(n / SR) + 1):
        xx = int(s * SR / n * 900)
        d.line([(xx, 0), (xx, 440)], fill=(80, 80, 80))
        d.text((xx + 2, 2), '%ds' % s, fill=(255, 255, 255))
    d.text((4, 425), title, fill=(255, 255, 255))
    out.save(path)

def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
    os.makedirs(OUT, exist_ok=True)
    raw, pal, info = build_textures()
    open(os.path.join(OUT, 'tex.bin'), 'wb').write(raw)
    open(os.path.join(OUT, 'pal.bin'), 'wb').write(pal)

    verts, faces = icosphere()
    P = score()
    vols = P.finish()
    assert len(P.data) <= BUDGET, 'sound data %d bytes is over the %d byte budget' % (len(P.data), BUDGET)
    open(os.path.join(OUT, 'snd.bin'), 'wb').write(bytes(P.data))
    open(os.path.join(OUT, 'vol.bin'), 'wb').write(vols)

    rng = np.random.default_rng(1234)
    stars = []
    while len(stars) < 56:
        x, y = rng.uniform(4, 316), rng.uniform(4, 236)
        if any((x - a) ** 2 + (y - b) ** 2 < 150 for a, b, *_ in stars):
            continue
        stars.append((x, y, rng.uniform(0.25, 1.0) ** 1.5, rng.uniform(0, 1024), rng.uniform(0.6, 2.2)))
    stars.sort(key=lambda s: s[2])

    def fx(v):
        return int(round(v * 65536))
    s = '// Generated by tools/gen_boot_eclipse.py - do not edit.\n'
    s += 'embed ECLIPSE_TEX: u8 = "tex.bin"\n'
    s += 'embed ECLIPSE_PAL: u16 = "pal.bin"\n'
    s += 'embed ECLIPSE_SND: s8 = "snd.bin"\n'
    s += 'embed ECLIPSE_VOLS: u8 = "vol.bin"\n\n'
    s += 'const ECLIPSE_GLYPH_SPLIT = %d\n' % info['GLYPH_SPLIT']
    sp = info['WM_SPANS']
    s += 'const ECLIPSE_WM_U0: [3]s32 = [%s]\n' % ', '.join(str(a) for a, b in sp)
    s += 'const ECLIPSE_WM_U1: [3]s32 = [%s]\n' % ', '.join(str(b) for a, b in sp)
    s += '\n// sun: an icosphere, unit radius (16.16), faces counter-clockwise from outside\n'
    s += 'const ECLIPSE_SUN_NV = %d\nconst ECLIPSE_SUN_NF = %d\n' % (len(verts), len(faces))
    s += 'const ECLIPSE_SUN_V: [%d]s32 = [%s]\n' % (3 * len(verts), ', '.join(str(fx(c)) for v in verts for c in v))
    s += 'const ECLIPSE_SUN_F: [%d]u8 = [%s]\n' % (3 * len(faces), ', '.join(str(i) for f in faces for i in f))
    s += '\n// stars: x, y, brightness 0..255, twinkle phase 0..1023, twinkle speed (x256)\n'
    s += 'const ECLIPSE_STAR_N = %d\n' % len(stars)
    s += 'const ECLIPSE_STAR: [%d]s32 = [%s]\n' % (5 * len(stars), ', '.join(
        '%d, %d, %d, %d, %d' % (round(x), round(y), round(b * 255), round(p), round(v * 256)) for x, y, b, p, v in stars))
    s += '\n// score (frames)\n'
    s += 'const ECLIPSE_T_BOWL = %d\n' % T_BOWL
    s += 'const ECLIPSE_T_SUN: [%d]s32 = [%s]\n' % (len(T_SUN), ', '.join(map(str, T_SUN)))
    s += 'const ECLIPSE_SUN_NOTES: [%d]s32 = [%s]\n' % (len(SUN_NOTES), ', '.join(map(str, SUN_NOTES)))
    s += 'const ECLIPSE_T_MOON: [%d]s32 = [%s]\n' % (len(T_MOON), ', '.join(map(str, T_MOON)))
    s += 'const ECLIPSE_MOON_NOTES: [%d]s32 = [%s]\n' % (len(MOON_NOTES), ', '.join(map(str, MOON_NOTES)))
    s += 'const ECLIPSE_T_ECLIPSE = %d\n' % T_SWELL_END
    s += 'const ECLIPSE_T_UNION = %d\n' % T_UNION
    s += 'const ECLIPSE_FRAMES = %d\n' % THEME_FRAMES
    s += '\n// sound events: piece offset/length in ECLIPSE_SND, volume table offset in ECLIPSE_VOLS\n'
    s += P.akr('eclipse')
    open(os.path.join(OUT, 'gen.akr'), 'w').write(s)

    print('eclipse: sound %d bytes (%.1f%% of budget), %d events, volume tables %d bytes' %
          (len(P.data), 100 * len(P.data) / BUDGET, len(P.events), len(vols)))
    for e in P.events:
        print('  frame %3d..%3d ch %d  %s' % (e['start'], e['start'] + e['frames'], e['ch'], e['piece']))
    if preview:
        L, R = P.simulate(vols, THEME_FRAMES)
        print('  mix peak %d (L) %d (R)' % (np.max(np.abs(L)), np.max(np.abs(R))))
        write_wav(os.path.join(preview, 'eclipse_mix.wav'), L, R)
        IL, IR = P.simulate(vols, THEME_FRAMES, ideal=True)
        spectrogram_png(os.path.join(preview, 'eclipse_noise.png'), L - IL, R - IR, 'eclipse 8-bit error')
        for sec in range(int(len(L) / SR)):
            a, b = sec * SR, (sec + 1) * SR
            sig = np.sqrt(np.mean(IL[a:b] ** 2)) + 1e-9
            err = np.sqrt(np.mean((L[a:b] - IL[a:b]) ** 2)) + 1e-9
            print('  %ds: level %5.1f dBFS, snr %4.1f dB' % (sec, 20 * np.log10(sig / 32768), 20 * np.log10(sig / err)))
        spectrogram_png(os.path.join(preview, 'eclipse_mix.png'), L, R, 'eclipse (simulated console mix)')

if __name__ == '__main__':
    main()
