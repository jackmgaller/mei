#!/usr/bin/env python3
"""Generates the audio of the "Lantern Lake" fishing cart in carts/lantern/.

All files are raw, headerless, mono, signed (8-bit, or 16-bit little-endian).
Pitch = playback rate / 22,050 Hz (the console plays samples nearest-sample, no interpolation).

  file                 fmt   rate      play pitch  kind
  mus_day_pad.raw      s16   5512.5    0.25        loop 16.0 s  C major pad + bass
  mus_day_mel.raw      s8    11025     0.5         loop 13.0 s  kalimba, C major pentatonic
  mus_night_pad.raw    s16   5512.5    0.25        loop 16.0 s  A minor pad + bass
  mus_night_mel.raw    s8    11025     0.5         loop 11.0 s  celesta + echo, A minor pentatonic
  amb_water.raw        s8    11025     0.5         loop 6.0 s   water lapping at the dock
  amb_crickets.raw     s8    22050     1.0         loop 2.0 s   night crickets
  sfx_tension.raw      s8    22050     1.0         loop 5512 samples (0.25 s)  line creak
  sfx_bird1..3.raw     s8    22050     1.0         one-shot     songbird calls
  sfx_frog.raw         s8    11025     0.5         one-shot     ribbit
  sfx_catch.raw, sfx_festival.raw, sfx_firework.raw   s8 11025 (pitch 0.5) one-shots
  every other sfx_*    s8    22050     1.0         one-shot
  sfx_chime.raw: fundamental exactly C6 = 1046.50 Hz at pitch 1.0 (D6 1.1225, E6 1.2599, G6 1.4983,
  A6 1.6818, C7 2.0, C5 0.5 ...).

The two music layers have different loop lengths (pad 16 s vs melody 13 s / 11 s), so they phase
against each other (the full pattern repeats only every 208 s by day and 176 s by night). Both
arrangements use the same five pitch classes (C D E G A), so the reeling chime is always in key.

With `--review DIR`, preview mixes (22,050 Hz stereo WAV, resampled nearest-sample like the
console) are also written to DIR."""
import math, os, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'carts', 'lantern')
PREVIEW = None
if '--review' in sys.argv:
    PREVIEW = sys.argv[sys.argv.index('--review') + 1]
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20260930)

OUT_SR = 22050


# ============================================================================= helpers

def nsamp(dur, sr):
    return int(round(dur * sr))


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def s8(x):
    return np.clip(np.round(x * 127), -127, 127).astype(np.int8).tobytes()


def s16(x):
    return np.clip(np.round(x * 32767), -32767, 32767).astype('<i2').tobytes()


def normalise(x, peak):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def add_at(buf, start, x):
    """Add x into buf at start, truncating at the end."""
    s = max(0, start)
    e = min(len(buf), start + len(x))
    if e > s:
        buf[s:e] += x[s - start:e - start]


def add_wrap(buf, start, x):
    """Circular add: whatever runs past the end wraps to the start (seamless loops)."""
    idx = (np.arange(len(x)) + int(start)) % len(buf)
    np.add.at(buf, idx, x)


def raised(u):
    u = np.clip(u, 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * u)


def ar_env(n, sr, attack, decay):
    """Raised-cosine attack, then exponential decay (decay = 1/s rate)."""
    t = np.arange(n) / sr
    return raised(t / max(attack, 1e-5)) * np.exp(-t * decay)


def asr_env(n, sr, attack, release):
    """Raised-cosine attack, flat, raised-cosine release ending at exactly 0."""
    t = np.arange(n) / sr
    dur = n / sr
    return raised(t / max(attack, 1e-5)) * raised((dur - t - 1 / sr) / max(release, 1e-5))


def fade_tail(x, sr, dur):
    m = min(len(x), nsamp(dur, sr))
    if m > 0:
        x[-m:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, m + 1) / m)
    return x


def phase_of(freq, n, sr, phase0=0.0):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    return phase0 + 2 * np.pi * (np.cumsum(f) - f[0]) / sr


# ---- filters (numpy only)

def onepole_lp(x, fc, sr):
    a = 1 - math.exp(-2 * math.pi * fc / sr)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def biquad(x, sr, fc, q, kind='bp'):
    """RBJ biquad, fc may be an array (time-varying cutoff)."""
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        w = 2 * math.pi * min(fc[i], 0.49 * sr) / sr
        cw, sw = math.cos(w), math.sin(w)
        al = sw / (2 * q)
        if kind == 'bp':
            b0, b1, b2 = al, 0.0, -al
        elif kind == 'lp':
            b0 = b2 = (1 - cw) / 2
            b1 = 1 - cw
        else:  # hp
            b0 = b2 = (1 + cw) / 2
            b1 = -(1 + cw)
        a0, a1, a2 = 1 + al, -2 * cw, 1 - al
        yi = (b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x[i], y1, yi
        y[i] = yi
    return y


def g_lp(fc, order=2):
    return lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * order))


def g_hp(fc, order=2):
    return lambda f: 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def g_bp(lo, hi, order=2):
    return lambda f: g_hp(lo, order)(f) * g_lp(hi, order)(f)


def g_res(f0, q):
    return lambda f: 1 / np.sqrt(1 + q * q * (f / f0 - f0 / np.maximum(f, 1e-3)) ** 2)


def fft_filter(x, sr, gain, circular=True):
    """Zero-phase magnitude filter. circular=True keeps a loop seamless (it filters one period of
    the periodic signal); circular=False zero-pads so one-shots don't wrap."""
    n = len(x)
    m = n if circular else 1 << int(math.ceil(math.log2(n + int(0.1 * sr) + 1)))
    X = np.fft.rfft(x, m)
    f = np.fft.rfftfreq(m, 1 / sr)
    return np.fft.irfft(X * gain(f), m)[:n]


def colored(n, sr, gain, circular=True):
    y = fft_filter(rng.standard_normal(n), sr, gain, circular)
    return y / (np.sqrt(np.mean(y * y)) + 1e-12)


# ---- instruments

def partials(f0, n, sr, parts, attack=0.003, limit=None, bend=None):
    """Additive synth: parts = [(ratio, amp, decay_rate)], drops partials near Nyquist."""
    limit = limit or 0.43 * sr
    t = np.arange(n) / sr
    out = np.zeros(n)
    for ratio, amp, dec in parts:
        f = f0 * ratio
        if f >= limit:
            continue
        taper = min(1.0, (limit - f) / (0.15 * limit))       # fade partials approaching the limit
        fr = f if bend is None else f * bend
        out += amp * taper * np.sin(phase_of(fr, n, sr, rng.uniform(0, 0.3))) * np.exp(-t * dec)
    return out * raised(t / attack)


KALIMBA = [(1, 1.0, 3.4), (2.0, 0.08, 7), (3.0, 0.05, 11), (5.95, 0.20, 16), (8.8, 0.05, 25)]
CELESTA = [(1, 1.0, 1.9), (1.0013, 0.35, 2.1), (2.0, 0.30, 3.2), (3.0, 0.10, 5.5), (4.07, 0.10, 8)]
BELL = [(1, 1.0, 4.0), (2.0, 0.35, 7), (3.0, 0.15, 11), (4.2, 0.12, 15), (5.4, 0.06, 20)]
CHIME = [(1, 1.0, 4.2), (2.0, 0.16, 7.5), (3.0, 0.05, 12), (4.2, 0.04, 18)]
PLUCK = [(k, 1 / k ** 1.25, 3 + 3.0 * k) for k in range(1, 9)]


def note(f0, dur, sr, parts, attack=0.003, tail=0.3, limit=None):
    n = nsamp(dur, sr)
    return fade_tail(partials(f0, n, sr, parts, attack, limit), sr, tail * dur)


def pad_note(freq, dur, sr, attack, release, nharm=6, tilt=1.6, maxf=2300, detune=0.0035):
    """Warm chorus pad voice: 3 detuned voices with slow vibrato, low harmonics only."""
    n = nsamp(dur, sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    for det in (-detune, 0.0, detune * 1.1):
        lfo = 1 + 0.0012 * np.sin(2 * np.pi * rng.uniform(0.15, 0.35) * t + rng.uniform(0, 6.28))
        for k in range(1, nharm + 1):
            f = freq * k * (1 + det)
            if f >= maxf:
                break
            taper = min(1.0, (maxf - f) / (0.25 * maxf))
            x += taper * k ** -tilt * np.sin(phase_of(f * lfo, n, sr, rng.uniform(0, 6.28)))
    return x * asr_env(n, sr, attack, release) / 3


def bass_note(freq, dur, sr, attack=0.2, decay=0.3, release=0.9):
    n = nsamp(dur, sr)
    t = np.arange(n) / sr
    ph = phase_of(freq, n, sr)
    x = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
    return x * asr_env(n, sr, attack, release) * np.exp(-t * decay)


def flute(freq, dur, sr, vib=0.004):
    n = nsamp(dur, sr)
    t = np.arange(n) / sr
    v = 1 + vib * np.sin(2 * np.pi * 5.2 * t) * raised((t - 0.15) / 0.3)
    ph = phase_of(freq * v, n, sr)
    x = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    breath = colored(n, sr, g_res(freq, 3.0), circular=False) * 0.06
    return (x + breath) * asr_env(n, sr, 0.045, min(0.12, dur * 0.4))


def sweep(f_start, f_end, n, _sr=None, curve='exp'):
    u = np.arange(n) / max(n - 1, 1)
    if curve == 'exp':
        return f_start * (f_end / f_start) ** u
    return f_start + (f_end - f_start) * u


def bloop(f0, f1, dur, sr, decay, attack=0.003):
    """A water bloop: sine gliding from f0 to f1 with a fast decay."""
    n = nsamp(dur, sr)
    return np.sin(phase_of(sweep(f0, f1, n, sr), n, sr)) * ar_env(n, sr, attack, decay)


# ============================================================================= file bookkeeping

FILES = []   # (name, fmt, sr, loop, nsamples, bytes, data_float)


def write(name, x, fmt, sr, loop=False, peak=None, trim=True):
    peak = peak if peak is not None else (0.85 if fmt == 's16' else 0.88)
    x = np.asarray(x, float)
    if loop:
        x = x - np.mean(x)
    x = normalise(x, peak)
    data = s16(x) if fmt == 's16' else s8(x)
    if not loop and trim and fmt == 's8':
        q = np.frombuffer(data, np.int8)
        nz = np.nonzero(q)[0]
        data = data[:nz[-1] + 2] if len(nz) else data[:1]
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(data)
    FILES.append((name, fmt, sr, loop, len(data) // (2 if fmt == 's16' else 1), len(data)))


def decode(name):
    for nm, fmt, sr, loop, n, b in FILES:
        if nm == name:
            raw = open(os.path.join(OUT, name), 'rb').read()
            if fmt == 's16':
                return np.frombuffer(raw, '<i2') / 32767.0, sr
            return np.frombuffer(raw, np.int8) / 127.0, sr
    raise KeyError(name)


# ============================================================================= music

PAD_SR = 5512.5
MEL_SR = 11025


def make_pad(chords, top, sr, length_s, attack, release, nharm, tilt, maxf, bass_gain, overlap):
    L = nsamp(length_s, sr)
    buf = np.zeros(L)
    seg = length_s / len(chords)
    for ci, (bass, voices) in enumerate(chords):
        st = ci * seg - overlap
        dur = seg + overlap + release
        for m in voices:
            add_wrap(buf, nsamp(st, sr), pad_note(mtof(m), dur, sr, attack, release, nharm, tilt, maxf) * 0.30)
        if top is not None:
            add_wrap(buf, nsamp(st + 0.6, sr),
                     pad_note(mtof(top[ci]), dur - 0.6, sr, attack * 1.3, release, 3, 2.2, maxf) * 0.17)
        add_wrap(buf, nsamp(ci * seg, sr), bass_note(mtof(bass), seg + 0.9, sr, 0.25, 0.25, 0.9) * bass_gain)
    # final gentle circular low-pass keeps everything under ~2.2 kHz and seamless
    return fft_filter(buf, sr, g_lp(maxf * 0.8, 3))


# Day: Cmaj7 - Am7 - Fmaj7 - G6sus4, one chord per 4 s (a slow 60 BPM, one 4/4 bar each)
DAY_CHORDS = [(36, [48, 55, 59, 64]),     # C2 | C3 G3 B3 E4
              (33, [48, 55, 57, 64]),     # A1 | C3 G3 A3 E4
              (41, [48, 53, 57, 64]),     # F2 | C3 F3 A3 E4
              (43, [48, 55, 62, 64])]     # G2 | C3 G3 D4 E4
DAY_TOP = [71, 72, 69, 67]                # B4 C5 A4 G4 soft top line
day_pad = make_pad(DAY_CHORDS, DAY_TOP, PAD_SR, 16.0, 1.1, 1.8, 6, 1.6, 2300, 0.55, 0.3)
write('mus_day_pad.raw', day_pad, 's16', PAD_SR, loop=True)

# Night: Am9 - Fmaj9 - Cmaj7 - Em7, lower, darker (fewer harmonics), slower swells
NIGHT_CHORDS = [(33, [48, 52, 55, 59]),   # A1 | C3 E3 G3 B3
                (29, [45, 48, 52, 55]),   # F1 | A2 C3 E3 G3
                (36, [47, 52, 55, 60]),   # C2 | B2 E3 G3 C4
                (28, [47, 50, 55, 59])]   # E1 | B2 D3 G3 B3
night_pad = make_pad(NIGHT_CHORDS, None, PAD_SR, 16.0, 2.2, 3.0, 3, 2.2, 1400, 0.7, 0.9)
write('mus_night_pad.raw', night_pad, 's16', PAD_SR, loop=True)

# Day melody: kalimba, C major pentatonic C5-C6, 12 notes in 13 s
DAY_MEL = [(0.00, 76, 0.95), (0.50, 79, 0.70), (2.00, 81, 0.85), (3.25, 79, 0.65),
           (4.75, 84, 0.80), (5.25, 81, 0.60), (7.50, 76, 0.90), (8.00, 74, 0.65),
           (8.50, 72, 0.75), (10.25, 79, 0.85), (11.25, 74, 0.60), (11.75, 76, 0.70)]
L = nsamp(13.0, MEL_SR)
mel = np.zeros(L)
for t0, m, vel in DAY_MEL:
    add_wrap(mel, nsamp(t0, MEL_SR), note(mtof(m), 1.15, MEL_SR, KALIMBA, 0.004, 0.5) * vel)
mel = fft_filter(mel, MEL_SR, g_lp(4200, 2))
write('mus_day_mel.raw', mel, 's8', MEL_SR, loop=True)

# Night melody: celesta / music box, A minor pentatonic, 8 notes in 11 s, wrap-around echo
NIGHT_MEL = [(0.00, 81, 0.90), (1.50, 88, 0.70), (2.25, 84, 0.75), (4.50, 86, 0.80),
             (6.00, 79, 0.70), (7.50, 76, 0.80), (8.25, 81, 0.85), (9.75, 84, 0.60)]
L = nsamp(11.0, MEL_SR)
dry = np.zeros(L)
for t0, m, vel in NIGHT_MEL:
    add_wrap(dry, nsamp(t0, MEL_SR), note(mtof(m), 1.8, MEL_SR, CELESTA, 0.004, 0.45) * vel)
mel = dry.copy()
tap = dry
for k, g in enumerate((0.40, 0.20, 0.09)):
    tap = fft_filter(tap, MEL_SR, g_lp(2600 - 300 * k, 1))       # each repeat a little darker
    mel += g * np.roll(tap, nsamp(0.5 * (k + 1), MEL_SR))         # roll = circular echo
mel = fft_filter(mel, MEL_SR, g_lp(4200, 2))
write('mus_night_mel.raw', mel, 's8', MEL_SR, loop=True)


# ============================================================================= ambience

# ---- water lapping against a wooden dock (6 s loop at 11,025 Hz)
sr = 11025
L = nsamp(6.0, sr)
T = L / sr
t = np.arange(L) / sr
swell = (0.55 + 0.22 * np.sin(2 * np.pi * 1 * t / T + 0.4) + 0.14 * np.sin(2 * np.pi * 3 * t / T + 2.1)
         + 0.08 * np.sin(2 * np.pi * 5 * t / T + 4.0))            # integer cycles per loop
swell = np.maximum(swell, 0.12)
water = colored(L, sr, lambda f: g_bp(110, 800, 1)(f)) * swell * 0.30
water += colored(L, sr, g_bp(1300, 2600, 2)) * (swell ** 2) * 0.06            # faint shimmer
LAPS = [0.15, 0.82, 1.35, 2.30, 2.62, 3.40, 4.05, 4.55, 5.30]
for k, t0 in enumerate(LAPS):
    n = nsamp(0.32, sr)
    burst = colored(n, sr, g_bp(250, 1700, 2), circular=False)
    burst *= ar_env(n, sr, rng.uniform(0.010, 0.025), rng.uniform(12, 22))
    knock = np.sin(phase_of(rng.uniform(170, 240), n, sr)) * ar_env(n, sr, 0.004, 45)   # soft wood
    add_wrap(water, nsamp(t0 + rng.uniform(-0.04, 0.04), sr),
             (burst * 0.55 + knock * 0.25 * (k % 3 == 0)) * rng.uniform(0.6, 1.0))
for t0 in [0.45, 1.70, 2.95, 3.70, 4.90, 5.65]:
    f0 = rng.uniform(170, 260)
    g = bloop(f0, f0 * rng.uniform(1.5, 1.9), 0.09, sr, 40, 0.006)
    add_wrap(water, nsamp(t0, sr), g * rng.uniform(0.25, 0.4))
water = fft_filter(water, sr, g_lp(2600, 2))
write('amb_water.raw', water, 's8', sr, loop=True, peak=0.85)

# ---- crickets (2 s loop at 22,050 Hz): a few crickets at different rates and pitches
sr = 22050
L = nsamp(2.0, sr)
cr = np.zeros(L)
#            carrier  chirps/loop  pulses  pulse gap  amp   offset
CRICKETS = [(4350, 5, 3, 0.024, 1.00, 0.03),
            (4780, 7, 2, 0.020, 0.55, 0.17),
            (3980, 3, 5, 0.028, 0.45, 0.41),
            (5150, 9, 2, 0.018, 0.25, 0.09)]
for fc, per_loop, npulse, gap, amp, off in CRICKETS:
    for c in range(per_loop):
        t0 = off + c * 2.0 / per_loop + rng.uniform(-0.008, 0.008)
        a = amp * rng.uniform(0.8, 1.0)
        for p in range(npulse):
            n = nsamp(0.013, sr)
            w = np.sin(np.pi * np.arange(n) / n) ** 2
            f = fc * (1 + 0.01 * rng.uniform(-1, 1))
            pul = np.sin(phase_of(f, n, sr, rng.uniform(0, 6.28))) * w
            add_wrap(cr, nsamp(t0 + p * gap, sr), pul * a * (0.85 + 0.15 * (p == 0)))
# a faint distant trill bed, swelling twice per loop
tt = np.arange(L) / sr
bed = np.sin(2 * np.pi * 4520 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 46 * tt)) ** 2
cr += bed * 0.06 * (0.6 + 0.4 * np.sin(2 * np.pi * 2 * tt / 2.0))
cr = fft_filter(cr, sr, g_lp(6500, 2))
write('amb_crickets.raw', cr, 's8', sr, loop=True, peak=0.85)


def chirp_seg(f_traj, sr, attack_frac=0.2, release_frac=0.45, vib=None):
    n = len(f_traj)
    if vib is not None:
        f_traj = f_traj * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * np.arange(n) / sr))
    u = np.arange(n) / n
    env = raised(u / attack_frac) * raised((1 - u) / release_frac)
    return np.sin(phase_of(f_traj, n, sr)) * env


def bend(fa, fb, fc, n):
    """Frequency path fa -> fb (at 40%) -> fc."""
    k = int(n * 0.4)
    return np.concatenate([sweep(fa, fb, k, 0), sweep(fb, fc, n - k, 0)])


# ---- birds (22,050 Hz one-shots)
sr = 22050
b = np.zeros(nsamp(0.40, sr))                        # bird1: "tweet tweet tsew"
add_at(b, 0, chirp_seg(bend(2700, 5000, 4500, nsamp(0.07, sr)), sr))
add_at(b, nsamp(0.115, sr), chirp_seg(bend(2900, 5300, 4700, nsamp(0.07, sr)), sr) * 0.9)
add_at(b, nsamp(0.235, sr), chirp_seg(sweep(5200, 3000, nsamp(0.10, sr)), sr, 0.1, 0.6) * 0.75)
write('sfx_bird1.raw', fade_tail(b, sr, 0.02), 's8', sr)

b = np.zeros(nsamp(0.40, sr))                        # bird2: a quick descending trill
for k in range(9):
    drift = 1 - 0.018 * k
    seg = chirp_seg(sweep(5000 * drift, 3500 * drift, nsamp(0.027, sr)), sr, 0.15, 0.5)
    add_at(b, nsamp(0.012 + k * 0.036, sr), seg * (0.55 + 0.45 * math.sin(math.pi * (k + 1) / 10)))
write('sfx_bird2.raw', fade_tail(b, sr, 0.02), 's8', sr)

b = np.zeros(nsamp(0.45, sr))                        # bird3: whistled "fee-bee-bee"
add_at(b, 0, chirp_seg(sweep(3800, 4050, nsamp(0.15, sr), 0), sr, 0.15, 0.3))
add_at(b, nsamp(0.20, sr), chirp_seg(sweep(3250, 3020, nsamp(0.11, sr), 0), sr, 0.12, 0.35, (28, 0.012)) * 0.85)
add_at(b, nsamp(0.34, sr), chirp_seg(sweep(3250, 3000, nsamp(0.08, sr), 0), sr, 0.12, 0.45, (28, 0.012)) * 0.7)
write('sfx_bird3.raw', fade_tail(b, sr, 0.02), 's8', sr)

# ---- frog (11,025 Hz): low pulsed "rib-bit"
sr = 11025
fr = np.zeros(nsamp(0.40, sr))
for st, dur, fa, fb, amp in [(0.0, 0.13, 150, 132, 1.0), (0.18, 0.17, 165, 140, 0.9)]:
    n = nsamp(dur, sr)
    f0 = sweep(fa, fb, n, sr)
    ph = phase_of(f0, n, sr)
    x = np.zeros(n)
    for k in range(1, 20):
        fk = fa * k
        if fk > 2600:
            break
        w = math.exp(-((fk - 380) / 170) ** 2) + 0.45 * math.exp(-((fk - 950) / 280) ** 2) + 0.08
        x += w * np.sin(k * ph)
    tt = np.arange(n) / sr
    am = (0.5 + 0.5 * np.cos(2 * np.pi * 34 * tt)) ** 2                # pulsed croak
    add_at(fr, nsamp(st, sr), x * (0.25 + 0.75 * am) * asr_env(n, sr, 0.015, 0.05) * amp)
fr = fft_filter(fr, sr, g_lp(1800, 2), circular=False)
write('sfx_frog.raw', fade_tail(fr, sr, 0.01), 's8', sr)


# ============================================================================= effects (22,050 Hz)

sr = 22050

# cast: band-passed noise sweeping up then settling (rod swish)
n = nsamp(0.40, sr)
u = np.arange(n) / n
fc = 500 * (3200 / 500) ** np.minimum(u / 0.35, 1) * (1 - 0.45 * raised((u - 0.35) / 0.65))
x = biquad(rng.standard_normal(n), sr, fc, 2.2, 'bp')
env = raised(u / 0.28) * raised((1 - u) / 0.65)
x = x * env
x += np.sin(phase_of(sweep(1900, 1500, n, sr), n, sr)) * env ** 2 * 0.08   # faint line whine
write('sfx_cast.raw', fade_tail(x, sr, 0.01), 's8', sr)

# plop: falling bloop + small rising droplet + tiny splash
n = nsamp(0.30, sr)
x = np.zeros(n)
add_at(x, 0, bloop(620, 210, 0.11, sr, 32, 0.002))
add_at(x, nsamp(0.06, sr), bloop(520, 1050, 0.05, sr, 70, 0.002) * 0.35)
spl = colored(n, sr, g_bp(1800, 5000, 2), circular=False) * ar_env(n, sr, 0.002, 30) * 0.18
x += spl
x = fft_filter(x, sr, g_lp(6000, 2), circular=False)
write('sfx_plop.raw', fade_tail(x, sr, 0.03), 's8', sr)

# splash: a fish breaking the surface: thump, broad noise, sputters and bubbles
n = nsamp(0.45, sr)
x = colored(n, sr, g_bp(350, 4000, 2), circular=False) * ar_env(n, sr, 0.006, 9) * 0.6
for k in range(4):
    st = nsamp(rng.uniform(0.06, 0.25), sr)
    m = nsamp(0.06, sr)
    add_at(x, st, colored(m, sr, g_bp(800, 5000, 2), circular=False) * ar_env(m, sr, 0.003, 50) * 0.3)
add_at(x, 0, bloop(110, 70, 0.08, sr, 30, 0.003) * 0.6)
for k in range(9):
    f0 = rng.uniform(350, 1100)
    add_at(x, nsamp(rng.uniform(0.04, 0.33), sr),
           bloop(f0, f0 * rng.uniform(1.6, 2.3), 0.05, sr, 60, 0.002) * rng.uniform(0.15, 0.35))
x = fft_filter(x, sr, g_lp(5500, 2), circular=False)
write('sfx_splash.raw', fade_tail(x, sr, 0.06), 's8', sr)

# click: one reel ratchet tick
n = nsamp(0.035, sr)
tt = np.arange(n) / sr
x = (np.sin(2 * np.pi * 2900 * tt) * np.exp(-tt * 260) +
     0.5 * np.sin(2 * np.pi * 1300 * tt) * np.exp(-tt * 140) +
     colored(n, sr, g_hp(3000, 2), circular=False) * np.exp(-tt * 900) * 0.4) * raised(tt / 0.0004)
write('sfx_click.raw', fade_tail(x, sr, 0.008), 's8', sr)

# chime: pure soft glass bell, fundamental exactly C6 = 1046.50 Hz at pitch 1.0. Partials are
# kept below 5.5 kHz so they still sit below Nyquist when the game plays it at pitch 2.0.
CHIME_HZ = 1046.50
x = note(CHIME_HZ, 0.65, sr, CHIME, attack=0.002, tail=0.35, limit=5400)
write('sfx_chime.raw', x, 's8', sr)

# bite: a quick tug bloop, a second smaller one, and a small splash
n = nsamp(0.30, sr)
x = np.zeros(n)
add_at(x, 0, bloop(460, 160, 0.09, sr, 28, 0.002))
add_at(x, nsamp(0.085, sr), bloop(380, 180, 0.07, sr, 40, 0.002) * 0.55)
add_at(x, nsamp(0.015, sr), colored(nsamp(0.15, sr), sr, g_bp(1500, 5000, 2), circular=False)
       * ar_env(nsamp(0.15, sr), sr, 0.003, 35) * 0.22)
x = fft_filter(x, sr, g_lp(6000, 2), circular=False)
write('sfx_bite.raw', fade_tail(x, sr, 0.03), 's8', sr)

# nibble: a tiny soft rising bloop
n = nsamp(0.13, sr)
x = np.zeros(n)
add_at(x, 0, bloop(480, 760, 0.07, sr, 55, 0.004))
add_at(x, nsamp(0.05, sr), bloop(560, 820, 0.05, sr, 80, 0.004) * 0.35)
write('sfx_nibble.raw', fade_tail(x, sr, 0.02), 's8', sr)

# new entry: an upward pentatonic glissando of small chimes with a soft sparkle
n = nsamp(0.75, sr)
x = np.zeros(n)
for k, m in enumerate([84, 86, 88, 91, 93, 96, 98, 100, 103]):          # C6 .. G7
    add_at(x, nsamp(k * 0.045, sr), note(mtof(m), 0.45, sr, BELL, 0.002, 0.4, limit=9500)
           * (0.55 + 0.05 * k))
for k in range(10):
    add_at(x, nsamp(rng.uniform(0.15, 0.5), sr),
           note(rng.uniform(5500, 8000), 0.06, sr, [(1, 1, 50)], 0.002, 0.5, limit=10000) * 0.12)
write('sfx_new.raw', fade_tail(x, sr, 0.2), 's8', sr)

# snap: a soft low twang (pitch sagging) and a small sad falling tone
n = nsamp(0.42, sr)
x = np.zeros(n)
sag = 1 - 0.035 * (1 - np.exp(-np.arange(nsamp(0.3, sr)) / sr * 12))
add_at(x, 0, partials(220, nsamp(0.3, sr), sr, [(k, 1 / k ** 1.5, 6 + 4 * k) for k in range(1, 8)],
                      0.002, 3500, bend=sag) * 0.8)
add_at(x, 0, colored(nsamp(0.02, sr), sr, g_bp(1500, 4000, 1), circular=False)
       * ar_env(nsamp(0.02, sr), sr, 0.0005, 200) * 0.3)
m = nsamp(0.34, sr)
fall = np.sin(phase_of(sweep(659.25, 392.0, m, sr), m, sr)) * asr_env(m, sr, 0.03, 0.18) * np.exp(-np.arange(m) / sr * 3)
add_at(x, nsamp(0.06, sr), fall * 0.45)
write('sfx_snap.raw', fade_tail(x, sr, 0.04), 's8', sr)

# blip: a soft menu cursor blip (E6)
x = note(mtof(88), 0.06, sr, [(1, 1, 45), (2, 0.15, 80)], 0.002, 0.3)
write('sfx_blip.raw', x, 's8', sr)

# ok: two quick rising bell notes (G5 -> C6)
n = nsamp(0.25, sr)
x = np.zeros(n)
add_at(x, 0, note(mtof(79), 0.2, sr, BELL, 0.002, 0.3) * 0.75)
add_at(x, nsamp(0.065, sr), note(mtof(84), 0.185, sr, BELL, 0.002, 0.35))
write('sfx_ok.raw', fade_tail(x, sr, 0.02), 's8', sr)

# back: soft falling two notes (A5 -> E5)
n = nsamp(0.17, sr)
x = np.zeros(n)
soft = [(1, 1, 14), (2, 0.12, 25), (3, 0.04, 35)]
add_at(x, 0, note(mtof(81), 0.12, sr, soft, 0.004, 0.3) * 0.8)
add_at(x, nsamp(0.06, sr), note(mtof(76), 0.11, sr, soft, 0.004, 0.4))
write('sfx_back.raw', fade_tail(x, sr, 0.02), 's8', sr)

# coin: classic short-then-long ding, a fourth up (A5 -> E6), gentle
n = nsamp(0.28, sr)
x = np.zeros(n)
coin = [(1, 1, 9), (2, 0.18, 14), (3, 0.10, 18)]
add_at(x, 0, note(mtof(81), 0.075, sr, coin, 0.002, 0.25) * 0.8)
add_at(x, nsamp(0.07, sr), note(mtof(88), 0.21, sr, coin, 0.002, 0.4))
write('sfx_coin.raw', fade_tail(x, sr, 0.02), 's8', sr)

# tension: creaky line strain loop, 5512 samples (0.25 s). Stick-slip pulses through wood-like
# resonances, filtered circularly so the loop is seamless.
L = 5512
imp = np.zeros(L)
pos = 0.0
while pos < L - 1:
    imp[int(pos)] += rng.uniform(0.5, 1.0) * rng.choice([1, -1], p=[0.8, 0.2])
    pos += sr / rng.uniform(48, 78)
res = lambda f: g_res(720, 7)(f) + 0.7 * g_res(1650, 9)(f) + 0.3 * g_res(2900, 10)(f)
x = fft_filter(imp, sr, res)
x += colored(L, sr, g_bp(900, 1800, 2)) * 0.05
x *= 0.8 + 0.2 * np.sin(2 * np.pi * 4 * np.arange(L) / L)                # 4 cycles per loop
x = fft_filter(x, sr, g_lp(3000, 2))
write('sfx_tension.raw', x, 's8', sr, loop=True, peak=0.85)


# ============================================================================= 11,025 Hz one-shots

sr = 11025

# catch: bright pluck arpeggio up C major pentatonic, then a held, softly ringing chord
n = nsamp(1.6, sr)
x = np.zeros(n)
for k, m in enumerate([72, 74, 76, 79, 81, 84]):                        # C5 D5 E5 G5 A5 C6
    add_at(x, nsamp(k * 0.075, sr), note(mtof(m), 0.5, sr, PLUCK, 0.002, 0.4) * 0.6)
    add_at(x, nsamp(k * 0.075, sr), note(mtof(m + 12), 0.3, sr, BELL, 0.002, 0.4) * 0.12)
st = nsamp(0.48, sr)
for m in [72, 76, 79, 84, 88]:                                          # C5 E5 G5 C6 E6
    dur = (n - st) / sr
    nn = n - st
    tt = np.arange(nn) / sr
    v = (note(mtof(m), dur, sr, BELL, 0.003, 0.3) * 0.25 +
         np.sin(phase_of(mtof(m) * (1 + 0.003 * np.sin(2 * np.pi * 5 * tt)), nn, sr))
         * ar_env(nn, sr, 0.02, 1.4) * 0.18)
    add_at(x, st, fade_tail(v, sr, 0.35))
x = fft_filter(x, sr, g_lp(4600, 2), circular=False)
write('sfx_catch.raw', fade_tail(x, sr, 0.05), 's8', sr)

# festival: taiko + shaker intro, soft flute melody doubled by bells, building to a held C chord
n = nsamp(3.0, sr)
x = np.zeros(n)
E8 = 0.22                                                               # eighth note (~136 BPM)
for t0, a in [(0, 1.0), (E8, 0.55), (2 * E8, 0.9), (4 * E8, 0.7), (8 * E8, 0.8)]:
    m = nsamp(0.35, sr)
    taiko = (np.sin(phase_of(sweep(95, 58, m, sr), m, sr)) * ar_env(m, sr, 0.003, 9) +
             colored(m, sr, g_lp(500, 2), circular=False) * ar_env(m, sr, 0.001, 40) * 0.25)
    add_at(x, nsamp(t0, sr), taiko * a * 0.9)
for k in range(10):
    m = nsamp(0.08, sr)
    sh = colored(m, sr, g_bp(3500, 5200, 2), circular=False) * ar_env(m, sr, 0.008, 45)
    add_at(x, nsamp(k * E8, sr), sh * (0.22 if k % 2 == 0 else 0.13))
MELODY = [(2, 79, 1), (3, 81, 1), (4, 84, 2), (6, 81, 1), (7, 84, 1), (8, 86, 1.5), (9.5, 84, 0.5)]
for e0, m, d in MELODY:
    add_at(x, nsamp(e0 * E8, sr), flute(mtof(m), d * E8 + 0.04, sr) * 0.42)
    add_at(x, nsamp(e0 * E8, sr), note(mtof(m), 0.6, sr, BELL, 0.002, 0.4, limit=4800) * 0.14)
st = nsamp(10 * E8, sr)
dur = (n - st) / sr
v = flute(mtof(88), dur, sr, vib=0.006)                                 # held E6
add_at(x, st, fade_tail(v, sr, 0.5 * dur) * 0.42)
for m in [60, 64, 67, 72, 76]:                                          # C4 E4 G4 C5 E5
    v = flute(mtof(m), dur, sr, vib=0.003) * ar_env(nsamp(dur, sr), sr, 0.12, 0.6)
    add_at(x, st, fade_tail(v, sr, 0.5 * dur) * 0.16)
    add_at(x, st, note(mtof(m + 12), 1.0, sr, BELL, 0.002, 0.4, limit=4800) * 0.08)
x = fft_filter(x, sr, g_lp(4300, 2), circular=False)
write('sfx_festival.raw', fade_tail(x, sr, 0.05), 's8', sr)

# firework: a soft distant pop, then a thinning crackle
n = nsamp(0.85, sr)
x = np.zeros(n)
add_at(x, 0, colored(nsamp(0.2, sr), sr, g_lp(700, 2), circular=False) * ar_env(nsamp(0.2, sr), sr, 0.002, 30) * 0.8)
add_at(x, 0, np.sin(phase_of(sweep(85, 55, nsamp(0.3, sr), sr), nsamp(0.3, sr), sr)) * ar_env(nsamp(0.3, sr), sr, 0.003, 14) * 0.7)
for k in range(70):
    t0 = 0.08 + rng.exponential(0.22)
    if t0 > 0.78:
        continue
    m = nsamp(0.004, sr)
    cr_ = colored(m, sr, g_bp(1200, 3800, 1), circular=False) * ar_env(m, sr, 0.0003, 900)
    add_at(x, nsamp(t0, sr), cr_ * rng.uniform(0.15, 0.4) * math.exp(-(t0 - 0.08) * 2.2))
x = fft_filter(x, sr, g_lp(3000, 2), circular=False)
write('sfx_firework.raw', fade_tail(x, sr, 0.08), 's8', sr)


# ============================================================================= report

print('%-20s %-4s %8s %5s %8s %7s %7s' % ('file', 'fmt', 'rate', 'loop', 'samples', 'sec', 'bytes'))
total = 0
for name, fmt, rate, loop, ns, nb in FILES:
    total += nb
    print('%-20s %-4s %8g %5s %8d %7.3f %7d' % (name, fmt, rate, 'yes' if loop else '', ns, ns / rate, nb))
print('total: %d bytes (%.1f KiB) in %d files' % (total, total / 1024, len(FILES)))

print('\nloop seams (|last - first| / peak; median |adjacent diff| / peak for comparison):')
for name, fmt, rate, loop, ns, nb in FILES:
    if loop:
        x, _ = decode(name)
        pk = np.max(np.abs(x))
        print('  %-20s seam %.4f   typical step %.4f' % (name, abs(x[-1] - x[0]) / pk,
                                                         np.median(np.abs(np.diff(x))) / pk))


# ============================================================================= preview mixes

def play(name, pitch, dur_s, loop):
    """Nearest-sample resampling to 22,050 Hz, like the console."""
    x, _ = decode(name)
    n = nsamp(dur_s, OUT_SR)
    idx = np.floor(np.arange(n) * pitch).astype(np.int64)
    if loop:
        return x[idx % len(x)]
    idx = idx[idx < len(x)]
    out = np.zeros(n)
    out[:len(idx)] = x[idx]
    return out


def mix_preview(fname, stems, events, dur_s=60.0):
    n = nsamp(dur_s, OUT_SR)
    L = np.zeros(n)
    R = np.zeros(n)
    print('\n%s:' % fname)
    for label, name, pitch, vol, pan in stems:
        y = play(name, pitch, dur_s, True) * vol
        L += y * (1 - pan)
        R += y * (1 + pan)
        print('  %-14s peak %.3f  rms %.3f' % (label, np.max(np.abs(y)), np.sqrt(np.mean(y * y))))
    ev_peak = 0.0
    for name, t0, pitch, vol, pan in events:
        y = play(name, pitch, 2.0, False) * vol
        s = nsamp(t0, OUT_SR)
        e = min(n, s + len(y))
        L[s:e] += y[:e - s] * (1 - pan)
        R[s:e] += y[:e - s] * (1 + pan)
        ev_peak = max(ev_peak, np.max(np.abs(y)))
    print('  %-14s peak %.3f  (%d one-shots)' % ('events', ev_peak, len(events)))
    st = np.stack([L, R], 1)
    print('  %-14s peak %.3f  rms %.3f' % ('MIX', np.max(np.abs(st)), np.sqrt(np.mean(st * st))))
    pcm = np.clip(np.round(st * 32767), -32767, 32767).astype('<i2')
    with wave.open(os.path.join(PREVIEW, fname), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(OUT_SR)
        w.writeframes(pcm.tobytes())


try:
    if PREVIEW is None:
        raise SystemExit(0)
    os.makedirs(PREVIEW, exist_ok=True)
    prv = np.random.default_rng(7)
    birds = [('sfx_bird%d.raw' % prv.integers(1, 4), float(t), float(prv.uniform(0.85, 1.2)), 0.18,
              float(prv.uniform(-0.7, 0.7))) for t in np.sort(prv.uniform(2, 57, 7))]
    mix_preview('day_mix.wav',
                [('day pad', 'mus_day_pad.raw', 0.25, 0.42, 0.0),
                 ('day mel', 'mus_day_mel.raw', 0.5, 0.34, 0.1),
                 ('water', 'amb_water.raw', 0.5, 0.16, -0.2)], birds)
    frogs = [('sfx_frog.raw', t, float(prv.uniform(0.45, 0.55)), 0.22, float(prv.uniform(-0.5, 0.5)))
             for t in (9.0, 31.5, 48.0)]
    mix_preview('night_mix.wav',
                [('night pad', 'mus_night_pad.raw', 0.25, 0.45, 0.0),
                 ('night mel', 'mus_night_mel.raw', 0.5, 0.30, -0.1),
                 ('water', 'amb_water.raw', 0.5, 0.13, 0.2),
                 ('crickets', 'amb_crickets.raw', 1.0, 0.07, 0.3)], frogs)
    print('\npreview WAVs in', PREVIEW)
except OSError as e:
    print('preview skipped:', e, file=sys.stderr)
