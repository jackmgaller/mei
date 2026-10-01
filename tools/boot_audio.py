#!/usr/bin/env python3
"""Shared audio toolkit for the boot themes' asset generators (gen_boot_*.py): synthesis
voices, an FDN reverb, the block compander for 8-bit stems, an exact model of the console's
mixer (simulate), and review helpers that write a WAV and a spectrogram.

Companding: an 8-bit stem stores x / g(block) and the run time sets the channel volume to
g(block) every frame, block = round(pos / 367.5). The quantisation noise then follows the
signal level, like the block scaling of ADPCM."""
import math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import signal

SR = 22050
FPS = 60
rng = np.random.default_rng(7)

# ------------------------------------------------------------------ audio toolkit
from scipy import signal

def tt(n):
    return np.arange(n) / SR

def env_points(n, pts):
    """piecewise-linear envelope from (seconds, level) points."""
    xs, ys = zip(*pts)
    return np.interp(tt(n), xs, ys)

def pan(x, p):
    """equal-power pan, p in -1..1 -> (L, R)."""
    a = (p + 1) * math.pi / 4
    return x * math.cos(a), x * math.sin(a)

def place_at(buf, x, t0):
    i0 = int(round(t0 * SR))
    n = min(len(x), len(buf) - i0)
    if n > 0:
        buf[i0:i0 + n] += x[:n]

def fm_bell(f, dur, ratio=3.5, index=2.0, tau=1.2, tau_i=0.25, att=0.003, seed=0):
    n = int(dur * SR)
    t = tt(n)
    I = index * np.exp(-t / tau_i)
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t))
    # a second, quieter inharmonic pair for shimmer
    x += 0.3 * np.sin(2 * np.pi * f * 2.76 * t + 0.6 * I * np.sin(2 * np.pi * f * 1.41 * t)) * np.exp(-t / (tau * 0.35))
    e = np.exp(-t / tau) * np.clip(t / att, 0, 1)
    return x * e

def glass_tone(f, dur, att=1.0, rel=1.0, trem=0.0, seed=0):
    """a sustained glassy tone: near-sine with faint upper partials and slow beating."""
    n = int(dur * SR)
    t = tt(n)
    r = np.random.default_rng(seed)
    ph = r.uniform(0, 2 * np.pi, 6)
    x = (np.sin(2 * np.pi * f * t + ph[0]) + 0.8 * np.sin(2 * np.pi * f * 1.0028 * t + ph[1])
         + 0.10 * np.sin(2 * np.pi * 2 * f * t + ph[2]) + 0.035 * np.sin(2 * np.pi * 3.01 * f * t + ph[3])
         + 0.02 * np.sin(2 * np.pi * 4.2 * f * t + ph[4]))
    if trem:
        x *= 1 + trem * np.sin(2 * np.pi * 0.23 * t + ph[5])
    e = np.clip(t / att, 0, 1) ** 2 * np.clip((dur - t) / rel, 0, 1)
    return x * e / 1.8

def warm_voice(f, dur, att=0.5, rel=0.8, bright=1800, seed=0, vib=0.0035):
    """a warm, breathy, horn/choir-like tone: band-limited saw, low-passed, gentle vibrato."""
    n = int(dur * SR)
    t = tt(n)
    r = np.random.default_rng(seed)
    vib_env = np.clip((t - 0.35) / 0.6, 0, 1)
    fm = f * (1 + vib * vib_env * np.sin(2 * np.pi * (4.6 + r.uniform(-0.3, 0.3)) * t + r.uniform(0, 6)))
    phase = 2 * np.pi * np.cumsum(fm) / SR
    x = np.zeros(n)
    for k in range(1, 16):
        if f * k > SR / 2 - 500:
            break
        x += np.sin(k * phase + r.uniform(0, 0.3)) / k ** 1.35
    b, a = signal.butter(2, bright / (SR / 2))
    x = signal.lfilter(b, a, x)
    # breath
    nz = r.standard_normal(n)
    b2, a2 = signal.butter(2, [f * 1.5 / (SR / 2), min(0.95, f * 6 / (SR / 2))], 'band')
    x += 0.06 * signal.lfilter(b2, a2, nz)
    e = np.clip(t / att, 0, 1) ** 1.5 * np.clip((dur - t) / rel, 0, 1)
    return x * e / 2.2

def chorus(x, voices=3, cents=7, seed=0):
    """detuned copies through slowly modulated delays; returns (L, R)."""
    r = np.random.default_rng(seed)
    n = len(x)
    t = tt(n)
    L = np.zeros(n); R = np.zeros(n)
    idx = np.arange(n)
    for v in range(voices):
        d = 0.012 + 0.004 * v + 0.0025 * np.sin(2 * np.pi * r.uniform(0.15, 0.4) * t + r.uniform(0, 6))
        y = np.interp(idx - d * SR, idx, x, left=0)
        l, rr = pan(y, -0.8 + 1.6 * v / max(1, voices - 1))
        L += l; R += rr
    return L / voices * 1.4, R / voices * 1.4

class Reverb:
    """8-line feedback delay network, processed in blocks (all delays exceed the block),
    with frequency-dependent decay, input diffusion and decorrelated stereo outputs."""
    DEL = [1153, 1327, 1559, 1801, 2087, 2311, 2633, 2903]

    def __init__(self, rt60=3.5, damp=0.45, predelay=0.025):
        self.rt60, self.damp, self.pre = rt60, damp, predelay

    def __call__(self, L, R):
        n = len(L) + int(self.rt60 * SR)
        B = 1024
        nb = -(-n // B)
        n = nb * B
        inp = np.zeros(n); inp[:len(L)] = (L + R) * 0.5
        side = np.zeros(n); side[:len(L)] = (L - R) * 0.5
        pre = int(self.pre * SR)
        inp = np.concatenate([np.zeros(pre), inp])[:n]
        side = np.concatenate([np.zeros(pre), side])[:n]
        # diffusion: four allpasses
        for d, g in ((142, 0.62), (107, 0.62), (379, 0.55), (277, 0.55)):
            b = np.zeros(d + 1); b[0] = -g; b[d] = 1
            a = np.zeros(d + 1); a[0] = 1; a[d] = -g
            inp = signal.lfilter(b, a, inp)
            side = signal.lfilter(b, a, side)
        D = self.DEL
        m = len(D)
        g = np.array([10 ** (-3 * d / (self.rt60 * SR)) for d in D])
        A = np.eye(m) - 2.0 / m
        sgn_in = np.array([1, -1, 1, -1, 1, -1, 1, -1]) 
        sgn_side = np.array([1, 1, -1, -1, 1, 1, -1, -1])
        u = np.zeros((m, n))
        f = np.zeros((m, n))
        zi = [np.zeros(1) for _ in range(m)]
        bd, ad = [1 - self.damp], [1, -self.damp]
        for k in range(nb):
            s0, s1 = k * B, (k + 1) * B
            y = np.zeros((m, B))
            for i, d in enumerate(D):
                a0, a1 = s0 - d, s1 - d
                if a1 > 0:
                    lo = max(a0, 0)
                    y[i, lo - a0:] = u[i, lo:a1]
                f[i, s0:s1], zi[i] = signal.lfilter(bd, ad, y[i] * g[i], zi=zi[i])
            u[:, s0:s1] = A @ f[:, s0:s1] + np.outer(sgn_in, inp[s0:s1]) + np.outer(sgn_side, side[s0:s1]) * 0.7
        oL = np.array([1, 1, 1, 1, -1, -1, -1, -1]) @ f
        oR = np.array([1, -1, -1, 1, 1, -1, 1, -1]) @ f
        return oL * 0.35, oR * 0.35

# quantiser settings (see compand): dither amount and error-feedback filter. Measured on
# this score, plain rounding gives the best A-weighted SNR (about 48 dB): the block volumes keep
# every block at 40+ steps, so the error is already noise-like, and quiet blocks have tiny steps.
DITHER = 0.0
SHAPE = (0.0, 0.0)

def compand(y, start_parity=0):
    """8-bit block-companded encoding of y (output units, |y| < 32767).
    Returns (int8 samples, per-block u8 volumes). Block k covers floor(367.5k) .. ."""
    n = len(y)
    nb = int(math.ceil(n / 367.5)) + 1
    bnd = [int(math.floor(367.5 * k)) for k in range(nb + 1)]
    peak = np.zeros(nb)
    for k in range(nb):
        a, b = max(0, bnd[k] - 2), min(n, bnd[k + 1] + 2)
        if a < b:
            peak[k] = np.abs(y[a:b]).max()
    v = np.clip(np.ceil(peak / 118.0), 1, 255)
    # limit the step between neighbouring blocks to 25 %
    for k in range(1, nb):
        v[k] = max(v[k], math.ceil(v[k - 1] / 1.25))
    for k in range(nb - 2, -1, -1):
        v[k] = max(v[k], math.ceil(v[k + 1] / 1.25))
    v = np.clip(v, 1, 255).astype(int)
    # quantise with TPDF dither and second-order error feedback (noise pushed up in frequency)
    r = np.random.default_rng(11)
    d = (r.uniform(-0.5, 0.5, n) + r.uniform(-0.5, 0.5, n))
    q = np.zeros(n, np.int8)
    e1 = e2 = 0.0
    k = 0
    for i in range(n):
        while i >= bnd[k + 1]:
            k += 1
        g = v[k]
        target = y[i] - (SHAPE[0] * e1 + SHAPE[1] * e2)
        s = int(round(target / g + d[i] * DITHER))
        s = -127 if s < -127 else 127 if s > 127 else s
        q[i] = s
        e2 = e1
        e1 = s * g - target
    return q, v.astype(np.uint8)

def to_wav(path, L, R):
    import wave
    st = np.stack([L, R], 1)
    st = np.clip(np.round(st), -32768, 32767).astype('<i2')
    w = wave.open(path, 'wb')
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st.tobytes())
    w.close()

def review_png(path, L, R, marks=()):
    """waveform strip + log spectrogram of the mono sum, with frame markers."""
    x = (L + R) / 2
    nfft, hop = 1024, 128
    win = np.hanning(nfft)
    frames = 1 + (len(x) - nfft) // hop
    S = np.array([np.abs(np.fft.rfft(x[i * hop:i * hop + nfft] * win)) for i in range(frames)]).T
    S = 20 * np.log10(S + 1e-3)
    S = np.clip((S - (S.max() - 80)) / 80, 0, 1)
    # log-frequency rows 30 Hz .. 11 kHz
    H = 256
    fr = np.geomspace(30, SR / 2, H)
    rows = np.clip((fr / (SR / 2) * (nfft // 2)).astype(int), 0, nfft // 2)
    img = S[rows][::-1]
    W = min(1400, frames)
    cols = np.linspace(0, frames - 1, W).astype(int)
    img = img[:, cols]
    wave_h = 80
    wv = np.zeros((wave_h, W))
    seg = np.array_split(np.arange(len(x)), W)
    for c, idx in enumerate(seg):
        for ch, yoff in ((L, 0), (R, wave_h // 2)):
            m = np.abs(ch[idx]).max() / 32768
            h = int(m * (wave_h // 2 - 2))
            mid = yoff + wave_h // 4
            wv[mid - h // 2:mid + h // 2 + 1, c] = 1
    rgb = np.zeros((H + wave_h, W, 3))
    rgb[:wave_h, :, 1] = wv * 0.9
    rgb[:wave_h, :, 2] = wv
    rgb[wave_h:, :, 0] = img ** 1.2
    rgb[wave_h:, :, 1] = img ** 2
    rgb[wave_h:, :, 2] = 0.3 + 0.7 * img ** 3
    for fr_mark in marks:
        c = int(fr_mark / FPS * SR / len(x) * W)
        if 0 <= c < W:
            rgb[:, c, :] = [1, 1, 0]
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(path)

def simulate(parts, frames, nsamp):
    """Exact model of the console's mixer (src/core/audio.c) for a theme that drives its
    channels once per frame. parts: list of dicts with key 'events': {frame: (data, bits,
    pitch16, loop_start or None)}, 'vol': fn(frame, pos) -> (vl, vr), 'pitch': fn(frame) or None.
    Ticks alternate 367, 368 samples."""
    outL = np.zeros(nsamp + 400, np.int64); outR = np.zeros(nsamp + 400, np.int64)
    o = 0
    state = []
    for p in parts:
        state.append({'data': None, 'pos': 0, 'playing': False})
    for f in range(frames):
        n = 367 if f % 2 == 0 else 368
        for p, st in zip(parts, state):
            if f in p['events']:
                ev = p['events'][f]
                if ev is None:
                    st['playing'] = False
                else:
                    data, bits, pitch, loop = ev
                    st.update(data=data, bits=bits, pitch=pitch, loop=loop, pos=0, playing=True)
            if not st['playing']:
                st['vl'] = st['vr'] = 0
                continue
            if p.get('pitch'):
                st['pitch'] = p['pitch'](f)
            st['vl'], st['vr'] = p['vol'](f, st['pos'] >> 16)
        for p, st in zip(parts, state):
            if not st['playing']:
                continue
            data = st['data']; ln = len(data)
            pos = st['pos'] + st['pitch'] * np.arange(n, dtype=np.int64)
            idx = pos >> 16
            if st['loop'] is not None:
                lp = st['loop']
                over = idx >= ln
                if over.any():
                    span = (ln - lp) << 16
                    pos = np.where(pos >= (ln << 16), (lp << 16) + (pos - (ln << 16)) % span, pos)
                    idx = pos >> 16
                st['pos'] = int(pos[-1] + st['pitch'])
                if st['pos'] >= (ln << 16):
                    st['pos'] = (lp << 16) + (st['pos'] - (ln << 16)) % ((ln - lp) << 16)
                valid = np.ones(n, bool)
            else:
                valid = idx < ln
                st['pos'] = int(st['pos'] + st['pitch'] * n)
                if not valid.all():
                    st['playing'] = False
            s = np.zeros(n, np.int64)
            s[valid] = data[idx[valid]].astype(np.int64) * (256 if st['bits'] == 8 else 1)
            outL[o:o + n] += (s * st['vl']) >> 8
            outR[o:o + n] += (s * st['vr']) >> 8
        o += n
    L = np.clip(outL[:o], -32768, 32767); R = np.clip(outR[:o], -32768, 32767)
    clipped = int((np.abs(outL[:o]) > 32767).sum() + (np.abs(outR[:o]) > 32767).sum())
    return L.astype(float), R.astype(float), clipped



def S(f):
    return int(math.floor(f * 367.5))

def hz(note):
    names = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    n, o = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o + 1) - 69) / 12)


def bus_compress(L, R, thr_db=-14.0, ratio=3.0, att=0.010, rel=0.35):
    """a gentle stereo-linked RMS compressor with a soft clip, so the score sits denser."""
    x = np.maximum(np.abs(L), np.abs(R))
    peak = x.max()
    L, R, x = L / peak, R / peak, x / peak
    b, a = signal.butter(1, 1 / (0.05 * SR) / (SR / 2) * 2)
    env = np.sqrt(np.maximum(signal.lfilter(b, a, x * x), 1e-12))
    thr = 10 ** (thr_db / 20)
    g = np.where(env > thr, (thr / env) ** (1 - 1 / ratio), 1.0)
    # smooth the gain: fast attack, slow release
    out = np.empty_like(g)
    ka, kr = math.exp(-1 / (att * SR)), math.exp(-1 / (rel * SR))
    cur = 1.0
    for i in range(len(g)):
        k = ka if g[i] < cur else kr
        cur = g[i] + (cur - g[i]) * k
        out[i] = cur
    L, R = L * out, R * out
    return np.tanh(L * 1.2) / 1.2, np.tanh(R * 1.2) / 1.2


def compand_with(y, v):
    """quantise y against a given block-volume table (see compand)."""
    n = len(y)
    r = np.random.default_rng(13)
    d = (r.uniform(-0.5, 0.5, n) + r.uniform(-0.5, 0.5, n))
    q = np.zeros(n, np.int8)
    e1 = e2 = 0.0
    k = 0
    for i in range(n):
        while i >= int(math.floor(367.5 * (k + 1))):
            k += 1
        g = int(v[k])
        target = y[i] - (SHAPE[0] * e1 + SHAPE[1] * e2)
        s = int(round(target / g + d[i] * DITHER))
        s = -127 if s < -127 else 127 if s > 127 else s
        q[i] = s
        e2 = e1
        e1 = s * g - target
    return q
