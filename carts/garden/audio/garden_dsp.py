"""Small DSP helpers shared by the garden's audio generators (gen_sounds.py, gen_music.py).

NumPy and SciPy. Everything is float64 in -1..1 until bank() turns it into ADPCM.
Loops are made circular (FFT noise, whole cycles over the loop), so a loop's end runs into its
start without a seam.
"""
import math, os, sys
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mei_adpcm  # noqa: E402

SR = 22050
BLOCK = 28
LEAD = 56          # samples of a loop's own end put before it, so its first block is entered
                   # with the same ADPCM history the first time as on every later pass


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def blocks(n):
    """n rounded to a whole number of ADPCM blocks."""
    return max(BLOCK, int(round(n / BLOCK)) * BLOCK)


def secs(s, sr):
    return int(round(s * sr))


def tt(n, sr):
    return np.arange(n) / sr


# ------------------------------------------------------------------ filters

def _sos(kind, f, sr, order):
    nyq = sr / 2
    if kind == 'band':
        lo, hi = f
        hi = min(hi, nyq * 0.95)
        return signal.butter(order, [lo, hi], 'band', fs=sr, output='sos')
    return signal.butter(order, min(f, nyq * 0.95), kind, fs=sr, output='sos')


def lp(x, fc, sr, order=2):
    return signal.sosfilt(_sos('low', fc, sr, order), x)


def hp(x, fc, sr, order=2):
    return signal.sosfilt(_sos('high', fc, sr, order), x)


def bp(x, lo, hi, sr, order=2):
    return signal.sosfilt(_sos('band', (lo, hi), sr, order), x)


def peak(x, f, q, sr):
    """A resonant band (a two-pole peak at f)."""
    b, a = signal.iirpeak(min(f, sr * 0.47), q, fs=sr)
    return signal.lfilter(b, a, x)


def speaker(x, sr, lo=380, hi=3600, drive=1.6):
    """A small loudspeaker on a pole: band-limited and lightly overdriven."""
    y = bp(x, lo, hi, sr, 2)
    y = np.tanh(drive * y / (np.max(np.abs(y)) + 1e-9)) / math.tanh(drive)
    return peak(y, 1900, 2.0, sr) * 0.4 + y


# ------------------------------------------------------------------ circular (loopable) material

def circ_noise(n, sr, shape, seed):
    """Noise of n samples whose spectrum's magnitude is shape(f) (an array function of Hz);
    random phase, so it loops seamlessly. Normalised to unit RMS."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1 / sr)
    mag = shape(np.maximum(f, 1e-3))
    mag[0] = 0
    ph = rng.uniform(0, 2 * np.pi, len(f))
    x = np.fft.irfft(mag * np.exp(1j * ph), n)
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def circ_filter(x, sr, shape):
    """Filters a loop by multiplying its spectrum (circular: the loop stays seamless)."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    return np.fft.irfft(np.fft.rfft(x) * shape(np.maximum(f, 1e-3)), n)


def band_shape(lo, hi, order=2):
    return lambda f: 1 / np.sqrt(1 + (lo / f) ** (2 * order)) / np.sqrt(1 + (f / hi) ** (2 * order))


def circ_env(n, seed, terms=((1, 0.5), (2, 0.3), (3, 0.2)), floor=0.0):
    """A slow envelope that repeats exactly over n samples: 1 + sum of a_k sin(2 pi k i / n),
    then scaled to 0..1 (above floor)."""
    rng = np.random.default_rng(seed)
    i = np.arange(n) / n
    e = np.zeros(n)
    for k, a in terms:
        e += a * np.sin(2 * np.pi * k * i + rng.uniform(0, 2 * np.pi))
    e = (e - e.min()) / (e.max() - e.min() + 1e-12)
    return floor + (1 - floor) * e


def circ_add(dst, src, at):
    """Adds src into dst at sample `at`, wrapping round the end (for loops)."""
    n = len(dst)
    idx = (at + np.arange(len(src))) % n
    np.add.at(dst, idx, src)


def add(dst, src, at):
    """Adds src into dst at sample `at`, clipped to dst's length."""
    at = int(at)
    if at >= len(dst):
        return
    m = min(len(src), len(dst) - at)
    dst[at:at + m] += src[:m]


# ------------------------------------------------------------------ sources

def expdec(n, sr, tau, att=0.002):
    t = tt(n, sr)
    a = np.minimum(t / att, 1.0) if att > 0 else np.ones(n)
    return a * np.exp(-t / tau)


def modal(n, sr, modes, seed=0, att=0.0005):
    """A struck object: modes = [(Hz, amp, tau)]."""
    rng = np.random.default_rng(seed)
    t = tt(n, sr)
    x = np.zeros(n)
    for f, a, tau in modes:
        if f >= sr * 0.48:
            continue
        x += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi)) * np.exp(-t / tau)
    return x * np.minimum(t / att, 1.0)


def chirp(n, sr, f0, f1, curve='exp'):
    """Phase of a sweep from f0 to f1 over n samples (returns sin)."""
    u = np.arange(n) / max(1, n - 1)
    if curve == 'exp':
        f = f0 * (f1 / f0) ** u
    else:
        f = f0 + (f1 - f0) * u
    return np.sin(2 * np.pi * np.cumsum(f) / sr)


def freq_sin(f, sr, ph0=0.0):
    """A sine following the per-sample frequency array f."""
    return np.sin(ph0 + 2 * np.pi * np.cumsum(f) / sr)


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def burst(n, sr, lo, hi, tau, seed, att=0.0005):
    return bp(noise(n, seed), lo, hi, sr) * expdec(n, sr, tau, att)


def grains(n, sr, count, span, lo, hi, seed, dur=(0.001, 0.004), amp=(0.3, 1.0), decay=None):
    """Tiny noise grains scattered over the first `span` seconds (gravel, leaves, debris)."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for _ in range(count):
        u = rng.random()
        at = int((u ** 1.6 if decay else u) * span * sr)
        m = max(8, int(rng.uniform(*dur) * sr))
        g = rng.standard_normal(m) * np.hanning(m) * rng.uniform(*amp)
        if decay:
            g *= math.exp(-at / sr / decay)
        add(x, g, at)
    return bp(x, lo, hi, sr)


def bubble(sr, f0, dur, seed=0):
    """A water bubble: a short rising sine with a fast decay."""
    n = secs(dur, sr)
    return chirp(n, sr, f0, f0 * 1.9) * expdec(n, sr, dur / 3, 0.001)


def bell(n, sr, f0, ratios, taus, amps, beat=0.0, seed=0):
    """A bell: partials at f0 x ratios; with beat, each partial is a pair beat Hz apart (the
    slow wavering of a large bell)."""
    rng = np.random.default_rng(seed)
    t = tt(n, sr)
    y = np.zeros(n)
    for r, tau, a in zip(ratios, taus, amps):
        f = f0 * r
        if f >= sr * 0.48:
            continue
        ph = rng.uniform(0, 2 * np.pi)
        if beat:
            d = beat * rng.uniform(0.6, 1.4)
            p = 0.5 * (np.sin(2 * np.pi * (f - d / 2) * t + ph) + np.sin(2 * np.pi * (f + d / 2) * t + ph * 1.7))
        else:
            p = np.sin(2 * np.pi * f * t + ph)
        y += a * p * np.exp(-t / tau)
    return y * np.minimum(t / 0.0008, 1.0)


def pluck(n, sr, f0, bright=0.5, tau=0.8, seed=0):
    """A plucked string (koto-like): harmonics whose upper partials die first, a slight
    inharmonic stretch, and the pluck's click."""
    rng = np.random.default_rng(seed)
    t = tt(n, sr)
    x = np.zeros(n)
    for k in range(1, 16):
        f = f0 * k * (1 + 0.0004 * k * k)
        if f > sr * 0.45:
            break
        a = (1.0 / k ** (1.3 - 0.5 * bright)) * (1.0 if k % 2 else 0.8)
        x += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t * k ** 0.85 / tau)
    m = secs(0.006, sr)
    x[:m] += 0.25 * bp(noise(m, seed + 5), 1500, 7000, sr) * np.hanning(m)
    return x * np.minimum(t / 0.0015, 1.0)


def glock(n, sr, f0, tau=0.5, seed=0):
    t = tt(n, sr)
    return modal(n, sr, [(f0, 1.0, tau), (f0 * 2.76, 0.28, tau * 0.3), (f0 * 5.40, 0.1, tau * 0.12)], seed) \
        * np.minimum(t / 0.0008, 1.0)


def flute(n, sr, f0, att=0.06, rel=0.15, vib=5.2, depth=0.006, breath=0.12, seed=0):
    """A breathy bamboo flute note of n samples."""
    t = tt(n, sr)
    f = f0 * (1 + depth * np.sin(2 * np.pi * vib * t) * np.minimum(t / 0.3, 1.0))
    ph = 2 * np.pi * np.cumsum(f) / sr
    x = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    b = bp(noise(n, seed), f0 * 0.8, min(f0 * 4, sr * 0.45), sr) * breath
    env = np.minimum(t / att, 1.0) * np.minimum(1.0, np.maximum(0, (n / sr - t) / rel))
    chiff = bp(noise(n, seed + 1), 1000, 6000, sr) * np.exp(-t / 0.03) * 0.2
    return (x + b) * env + chiff * np.minimum(t / 0.004, 1)


def norm(x, peak_=0.9):
    m = np.max(np.abs(x))
    return x * (peak_ / m) if m > 0 else x


def rms_norm(x, r=0.2):
    v = np.sqrt(np.mean(x ** 2))
    return x * (r / v) if v > 0 else x


def fade(x, sr, a=0.002, r=0.02):
    n = len(x)
    e = np.ones(n)
    na, nr = min(n, secs(a, sr)), min(n, secs(r, sr))
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return x * e


def echoes(x, sr, taps, tail=0.0):
    """Baked echoes: taps = [(seconds, gain)]; the result is lengthened to hold them."""
    extra = int(max(d for d, g in taps) * sr) + secs(tail, sr)
    y = np.concatenate([x, np.zeros(extra)])
    for d, g in taps:
        add(y, lp(x, 2600, sr) * g, int(d * sr))
    return y


def mix(*xs):
    """Sums arrays of different lengths (from their starts)."""
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[:len(x)] += x
    return out


def to_int16(x, peak_=0.9):
    return np.clip(np.round(norm(x, peak_) * 32767), -32767, 32767).astype(np.int64)


def save_preview(path, x, sr):
    mei_adpcm.save_wav(path, np.clip(np.round(x * 32767), -32767, 32767).astype(np.int16), sr)
