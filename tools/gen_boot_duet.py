#!/usr/bin/env python3
"""Generates the assets of boot theme 0, DUET, in system/boot/duet/.

The look: a clean, bright white stage. A warm sun-drop and a cool moon-drop bounce in, answer
each other with every landing, hop once around each other and leap up together; in the air
they pop into the 日 and 月 halves of 明, two rings splash out and interlock, and MEI bounces
in letter by letter beneath.

  atlas.bin      8-bit texture for slots 2-3, 120 rows: drops (0,0) and (48,0) 48x48, shadow
                 (96,0) 48x24, sparkles (144/160/176,0) 16x16, 日 (0,48) and 月 (64,48) 56x72,
                 M (128,48) 40x40, E (170,48) 32x40, I (204,48) 16x40
  pal.bin        its 256-colour palette (loaded as 8-bit palette 2, colours 512-767)
  mix_l.raw, mix_r.raw   8-bit companded stereo stems (frames 0-290)
  gain.bin       per-block (367.5 samples) volumes for the stems

The score: the sun's voice is a warm electric-piano/marimba tone, the moon's a glassy celesta.
They answer each other on every landing (D5, A5, F#5, B5, A5, D6), meet on a dyad, run up in
sparkles while spinning, and land together on D major 9 when 明 appears.

Uses the shared audio toolkit in boot_audio.py (FDN reverb, compander, mixer model)."""
import math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot_audio as tk
from boot_audio import (SR, FPS, tt, env_points, pan, place_at, chorus, Reverb, compand,
                               compand_with, to_wav, review_png, simulate)
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'system', 'boot', 'duet')
os.makedirs(OUT, exist_ok=True)
REVIEW = None      # --review DIR: also write the simulated mix (.wav), spectrograms and previews
if '--review' in sys.argv:
    REVIEW = sys.argv[sys.argv.index('--review') + 1]
    os.makedirs(REVIEW, exist_ok=True)

def write(name, data):
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(data)

def c15(r, g, b):
    return (min(255, r) >> 3) | ((min(255, g) >> 3) << 5) | ((min(255, b) >> 3) << 10)

FONT = '/System/Library/Fonts/'
SS = 4
BG = np.array([250, 250, 248], float)
SUN = np.array([255, 138, 28], float)
MOON = np.array([72, 140, 250], float)
INK = np.array([62, 60, 70], float)

# ------------------------------------------------------------------ atlas (RGB + alpha)

def sphere(n, base, dark, hi, crescent=False):
    """a shaded drop: sphere shading, rim, highlight; returns (rgb, alpha) at n x n."""
    N = n * SS
    y, x = (np.mgrid[0:N, 0:N] + 0.5) / SS
    c = n / 2
    r = n / 2 - 2.5
    dx, dy = (x - c) / r, (y - c) / r
    d2 = dx * dx + dy * dy
    a = (d2 < 1).astype(float)
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    L = np.array([-0.45, -0.6, 0.66]); L /= np.linalg.norm(L)
    lam = np.clip(dx * L[0] + dy * L[1] + nz * L[2], 0, 1)
    if crescent:
        # a gentle crescent: the lower right falls into shade
        lam = np.clip(lam * 1.25 - 0.18, 0, 1)
    col = dark[None, None] + (base - dark)[None, None] * (lam[..., None] ** 0.8)
    spec = np.clip((lam - 0.86) / 0.14, 0, 1) ** 2
    col = col + (hi - col) * spec[..., None]
    # a soft lighter rim on the shaded side (bounce light from the white floor)
    rim = np.clip((d2 - 0.72) / 0.28, 0, 1) * np.clip(dy + 0.2, 0, 1)
    col = col + (np.array([255, 255, 255.0]) - col) * (0.25 * rim)[..., None]
    rgb = col.reshape(n, SS, n, SS, 3).mean(axis=(1, 3))
    al = a.reshape(n, SS, n, SS).mean(axis=(1, 3))
    return rgb, al

def star(n, colour):
    N = n * SS
    y, x = (np.mgrid[0:N, 0:N] + 0.5) / SS - n / 2
    ax, ay = np.abs(x), np.abs(y)
    # four-point sparkle: two thin diamonds plus a small core
    s = np.maximum(np.clip(1 - (ax / (n * 0.48) + ay / (n * 0.15)), 0, 1),
                   np.clip(1 - (ay / (n * 0.48) + ax / (n * 0.15)), 0, 1))
    core = np.clip(1 - np.hypot(x, y) / (n * 0.22), 0, 1)
    a = np.clip(np.maximum(s * 2.5, core * 2), 0, 1)
    al = a.reshape(n, SS, n, SS).mean(axis=(1, 3))
    rgb = np.ones((n, n, 3)) * colour
    return rgb, al

def text_img(s, font, size, box, colour):
    ft = ImageFont.truetype(font[0], size * SS, index=font[1])
    W, H = box[0] * SS, box[1] * SS
    img = Image.new('L', (W * 2, H * 2), 0)
    d = ImageDraw.Draw(img)
    d.text((W // 2, H // 2), s, font=ft, fill=255)
    a = np.asarray(img, float) / 255
    ys, xs = np.nonzero(a > 0.02)
    return a, (ys.min(), ys.max(), xs.min(), xs.max())

def down(a, n_h, n_w):
    return a.reshape(n_h, SS, n_w, SS).mean(axis=(1, 3))

def glyph_box(a, bb, box, x_from=None, x_to=None, base=None):
    """crop a big supersampled alpha to a box (w, h) in output pixels, centred."""
    y0, y1, x0, x1 = bb
    if x_from is not None:
        x0, x1 = x_from, x_to
    w, h = box
    cy = (y0 + y1) // 2 if base is None else base
    cx = (x0 + x1) // 2
    Y0 = cy - h * SS // 2
    X0 = cx - w * SS // 2
    crop = a[Y0:Y0 + h * SS, X0:X0 + w * SS]
    if x_from is not None:
        m = np.zeros_like(a); m[:, x_from:x_to] = 1
        crop = crop * m[Y0:Y0 + h * SS, X0:X0 + w * SS]
    return down(crop, h, w)

def make_atlas():
    H, W = 120, 256
    rgb = np.ones((H, W, 3)) * BG
    alpha = np.zeros((H, W))
    def put(u, v, c, a):
        h, w = a.shape
        rgb[v:v + h, u:u + w] = c * a[..., None] + BG * (1 - a[..., None])
        alpha[v:v + h, u:u + w] = a
    # drops (48 x 48 sprites, sphere radius 21.5)
    put(0, 0, *sphere(48, SUN, np.array([226, 84, 18.0]), np.array([255, 236, 170.0])))
    put(48, 0, *sphere(48, MOON, np.array([40, 84, 200.0]), np.array([232, 244, 255.0]), crescent=True))
    # shadow blob: brightness = how much to subtract
    y, x = (np.mgrid[0:24, 0:48] + 0.5)
    sh = np.clip(1 - (((x - 24) / 23.5) ** 2 + ((y - 12) / 11.5) ** 2), 0, 1) ** 1.6
    rgb[0:24, 96:144] = sh[..., None] * 255
    alpha[0:24, 96:144] = (sh > 0.02)
    # sparkles
    put(144, 0, *star(16, np.array([255, 178, 40.0])))
    put(160, 0, *star(16, np.array([96, 160, 255.0])))
    put(176, 0, *star(16, np.array([255, 214, 120.0])))
    # 明 split into 日 and 月 by connected strokes (月's left leg reaches under 日)
    from scipy import ndimage
    a, bb = text_img('明', (FONT + 'Hiragino Sans GB.ttc', 2), 66, (96, 96), None)
    y0, y1, x0, x1 = bb
    lab, nlab = ndimage.label(a > 0.35)
    mid = (x0 + x1) / 2
    left = np.zeros_like(a)
    for k in range(1, nlab + 1):
        ys, xs = np.nonzero(lab == k)
        if xs.mean() < mid - (x1 - x0) * 0.08:
            left[lab == k] = 1
    left = ndimage.binary_dilation(left > 0, iterations=SS).astype(float)
    a_ri, a_yue = a * left, a * (1 - left)
    base = (y0 + y1) // 2
    centres = []
    def crop(img):
        ys, xs = np.nonzero(img > 0.02)
        cx = (xs.min() + xs.max()) // 2
        centres.append(cx / SS)
        w, h = 56, 72
        return down(img[base - h * SS // 2:base + h * SS // 2, cx - w * SS // 2:cx + w * SS // 2], h, w)
    put(0, 48, np.ones((72, 56, 3)) * SUN, crop(a_ri))
    put(64, 48, np.ones((72, 56, 3)) * MOON, crop(a_yue))
    split = centres[1] - centres[0]     # 月's centre is this far right of 日's (pixels)
    assert abs(split - 24) < 1.0, split  # duet.akr places them 24 pixels apart
    # M, E, I, each in its own box on a shared baseline
    boxes = []
    u = 128
    for ch, w in (('M', 40), ('E', 32), ('I', 16)):
        a, bb = text_img(ch, (FONT + 'Supplemental/Arial Rounded Bold.ttf', 0), 34, (w, 40), None)
        # all three are capitals of one font, so centring each box keeps a common baseline
        g = glyph_box(a, bb, (w, 40))
        put(u, 48, np.ones((40, w, 3)) * INK, g)
        boxes.append((u, w))
        u += w + 2
    print('letters (u, w):', boxes, ' 日-月 centre distance %.1f' % split)
    return rgb, alpha

def quantise(rgb, alpha):
    mask = alpha > 0.06
    pix = rgb[mask].astype(np.uint8)
    img = Image.fromarray(pix.reshape(1, -1, 3))
    q = img.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:255 * 3]).reshape(-1, 3)
    idx = np.zeros(alpha.shape, np.uint8)
    idx[mask] = np.asarray(q).reshape(-1) + 1
    colours = [0] + [c15(*map(int, p)) for p in pal]
    colours += [0] * (256 - len(colours))
    return idx, colours, pal

def make_textures():
    rgb, alpha = make_atlas()
    idx, colours, pal = quantise(rgb, alpha)
    write('atlas.bin', idx.tobytes())            # 8-bit: 256 bytes per row
    write('pal.bin', struct.pack('<256H', *colours))
    # preview of what the GPU will see (palette applied, 5-bit)
    full = np.zeros(idx.shape + (3,))
    pal5 = np.array([[((c & 31) << 3), ((c >> 5 & 31) << 3), ((c >> 10 & 31) << 3)] for c in colours])
    full = pal5[idx]
    full[idx == 0] = [200, 230, 200]
    if REVIEW:
        Image.fromarray(full.astype(np.uint8)).resize((768, 384), Image.NEAREST).save(
            os.path.join(REVIEW, 'duet_atlas.png'))

# ------------------------------------------------------------------ DUET's score
FRAMES = 300
MIX_F1 = 290
LAND = {'sun': [(24, 'D5'), (72, 'F#5'), (96, 'A5'), (120, 'E5')],
        'moon': [(48, 'A5'), (84, 'B5'), (108, 'D6'), (120, 'C#6')]}
POP_F = 168
LETTERS_F = (186, 192, 198)

def hz(note):
    return tk.hz(note)

def warm_ep(f, dur=2.0, vel=1.0):
    """the sun: a warm electric-piano / marimba blend."""
    n = int(dur * SR)
    t = tt(n)
    I = 2.0 * vel * np.exp(-t / 0.10) + 0.35
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * t))
    body = np.sin(2 * np.pi * f * t) * np.exp(-t / 1.1)
    tine = np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t / 0.08) * 0.18
    knock = np.sin(2 * np.pi * f * 0.5 * t) * np.exp(-t / 0.05) * 0.2
    e = np.exp(-t / 0.55) * np.clip(t / 0.002, 0, 1)
    return (x * e * 0.6 + body * 0.5 + tine + knock) * np.clip((dur - t) / 0.05, 0, 1) * vel

def glass_celesta(f, dur=2.4, vel=1.0):
    """the moon: a cool, glassy celesta."""
    n = int(dur * SR)
    t = tt(n)
    I = 1.3 * vel * np.exp(-t / 0.18)
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * 3.0 * t))
    oct_ = np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t / 0.35) * 0.35
    air = np.sin(2 * np.pi * f * 5.03 * t) * np.exp(-t / 0.09) * 0.12
    e = np.exp(-t / 0.95) * np.clip(t / 0.004, 0, 1)
    return (x * e * 0.8 + oct_ + air) * np.clip((dur - t) / 0.05, 0, 1) * vel

def glock(f, dur=1.2):
    n = int(dur * SR)
    t = tt(n)
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.15)
         + 0.15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / 0.06))
    return x * np.exp(-t / 0.4) * np.clip(t / 0.001, 0, 1)

def thump(dur=0.25, f=110):
    t = tt(int(dur * SR))
    return np.sin(2 * np.pi * f * t * (1 + 0.6 * np.exp(-t / 0.02))) * np.exp(-t / 0.05)

def score():
    T = FRAMES / FPS
    n = int(T * SR)
    dL, dR, wL, wR = (np.zeros(n) for _ in range(4))
    def add(x, t0, p=0.0, dry=0.8, wet=0.35):
        l, r = pan(x, p)
        place_at(dL, l * dry, t0); place_at(dR, r * dry, t0)
        place_at(wL, l * wet, t0); place_at(wR, r * wet, t0)
    def add_ch(x, t0, p, dry=0.8, wet=0.35, seed=0):
        L, R = chorus(x, voices=3, cents=7, seed=seed)
        l2, r2 = pan(np.ones(1), p)
        place_at(dL, L * dry * l2[0] * 1.4, t0); place_at(dR, R * dry * r2[0] * 1.4, t0)
        place_at(wL, L * wet, t0); place_at(wR, R * wet, t0)
    # landings: sun answers moon, a soft thump under each
    for i, (f, note) in enumerate(LAND['sun']):
        add_ch(warm_ep(hz(note), 2.0, 0.9) * 0.30, f / FPS, -0.45, seed=i)
        add(thump() * 0.10, f / FPS, -0.3, 1.0, 0.0)
    for i, (f, note) in enumerate(LAND['moon']):
        add_ch(glass_celesta(hz(note), 2.2, 0.9) * 0.24, f / FPS, 0.45, seed=10 + i)
        add(thump(f=150) * 0.07, f / FPS, 0.3, 1.0, 0.0)
    # the spin: a sparkle run climbing while they orbit in the air (panned around)
    run = ['D6', 'E6', 'F#6', 'A6', 'B6', 'D7', 'E7']
    for i, note in enumerate(run):
        f = 128 + i * 6
        add(glock(hz(note)) * (0.06 + 0.012 * i), f / FPS, math.sin(i * 1.3) * 0.8, 0.6, 0.6)
    # the pop: both voices together on D major 9, a sparkle, a soft pad underneath
    tp = POP_F / FPS
    for k, note in enumerate(('D5', 'F#5', 'A5')):
        add_ch(warm_ep(hz(note), 2.4, 1.0) * 0.21, tp + 0.012 * k, -0.4, seed=40 + k)
    for k, note in enumerate(('D6', 'F#6', 'A6')):
        add_ch(glass_celesta(hz(note), 2.6, 1.0) * 0.17, tp + 0.02 + 0.012 * k, 0.4, seed=50 + k)
    add(glock(hz('E7'), 1.6) * 0.09, tp + 0.07, 0.6, 0.5, 0.8)
    add(glock(hz('A7'), 1.4) * 0.05, tp + 0.15, -0.6, 0.5, 0.8)
    tpad = tt(int(2.3 * SR))
    pad = np.zeros(len(tpad))
    for k, note in enumerate(('D4', 'A4', 'C#5', 'E5', 'F#5')):
        pad += tk.warm_voice(hz(note), 2.3, att=0.18, rel=1.3, bright=2400, seed=70 + k)
    add_ch(pad * 0.07, tp, 0.0, 0.7, 0.5, seed=60)
    # a little pop: a filtered noise blip
    r = np.random.default_rng(3)
    blip = r.standard_normal(int(0.06 * SR)) * np.exp(-tt(int(0.06 * SR)) / 0.012)
    b, a = signal.butter(2, [1500 / (SR / 2), 6000 / (SR / 2)], 'band')
    add(signal.lfilter(b, a, blip) * 0.25, tp, 0.0, 1.0, 0.3)
    # MEI's letters land: three soft plucks
    for k, (f, note) in enumerate(zip(LETTERS_F, ('A4', 'D5', 'F#5'))):
        add(warm_ep(hz(note), 1.0, 0.5) * 0.10, f / FPS, -0.2 + 0.2 * k, 0.8, 0.3)
    rvL, rvR = Reverb(rt60=1.9, damp=0.35, predelay=0.02)(wL, wR)
    return dL + rvL[:n], dR + rvR[:n]

def S(f):
    return int(math.floor(f * 367.5))

def make_audio():
    L, R = score()
    L, R = tk.bus_compress(L, R, thr_db=-12.0, ratio=2.5)
    n1 = S(MIX_F1)
    L, R = L[:n1].copy(), R[:n1].copy()
    fo = np.clip((n1 - np.arange(n1)) / (0.45 * SR), 0, 1) ** 1.5
    L *= fo; R *= fo
    peak = max(np.abs(L).max(), np.abs(R).max())
    L *= 27000 / peak; R *= 27000 / peak
    _, gv = compand(np.maximum(np.abs(L), np.abs(R)))
    ql = compand_with(L, gv)
    qr = compand_with(R, gv)
    write('mix_l.raw', ql.tobytes())
    write('mix_r.raw', qr.tobytes())
    write('gain.bin', gv.tobytes())
    total = len(ql) + len(qr)
    print('audio bytes: %d + %d = %d' % (len(ql), len(qr), total))
    assert total <= 240 * 1024
    def comp_vol(side):
        def f(fr, pos):
            k = min((pos * 2 + 367) // 735, len(gv) - 1)
            g = int(gv[k])
            return (g, 0) if side == 'L' else (0, g)
        return f
    parts = [{'events': {0: (ql.astype(np.int64), 8, 65536, None)}, 'vol': comp_vol('L')},
             {'events': {0: (qr.astype(np.int64), 8, 65536, None)}, 'vol': comp_vol('R')}]
    sL, sR, clipped = simulate(parts, FRAMES, S(FRAMES))
    print('simulated mix: peak %d, clipped %d' % (max(np.abs(sL).max(), np.abs(sR).max()), clipped))
    assert clipped == 0
    if not REVIEW:
        return
    to_wav(os.path.join(REVIEW, 'duet_mix.wav'), sL, sR)
    marks = [f for v in LAND.values() for f, _ in v] + [POP_F]
    review_png(os.path.join(REVIEW, 'duet_mix.png'), sL, sR, marks=marks)
    rms = [20 * math.log10(np.sqrt(np.mean(((sL + sR) / 2)[i:i + SR // 4] ** 2)) + 1e-9) - 90.3
           for i in range(0, len(sL) - SR // 4, SR // 4)]
    print('RMS dBFS per 0.25 s:', ' '.join('%.0f' % v for v in rms))

if __name__ == '__main__':
    make_textures()
    if '--no-audio' not in sys.argv:
        make_audio()
