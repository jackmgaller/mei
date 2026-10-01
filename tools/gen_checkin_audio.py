#!/usr/bin/env python3
"""Check-In! audio: instrument samples, three scores, sound effects and ambience loops.

Writes carts/checkin/audio/bank.adp (every sample, Mei ADPCM) and carts/checkin/audio_data.akr
(the tables that carts/checkin/audio.akr reads; declarations only).

Music (a small sequencer in audio.akr plays these scores with ADPCM instruments):
  Title   "Check-In!"     F major, 150 bpm lounge-samba, a 16-bar loop after a desk-bell intro
  Day     "Seaside Lobby" F major bossa nova, 128.6 bpm, AABA head, vibes/Rhodes solos (~3 min form)
  Night   "Night Desk"    Db major swing ballad, 85.7 bpm, muted trumpet head, piano and trumpet
                          solos, walking bass (~4 min form)
All three share one motif: the third, fifth and ninth of the tonic chord, rising (A C G in F,
F Ab Eb in Db). Every part of a section has a few variants and the engine picks one at random
each pass, so the forms rarely repeat exactly. Solos are composed by a seeded phrase generator
(rhythm cells, chord tones on strong beats, scale steps and approaches between them).

Sample rules (as tools/gen_shell_music.py): pitched notes are rendered at the exact pitch they
play (pitch 1.0, or 2.0 for an octave up), because the console resamples by nearest sample and
any other ratio adds grit; only the upright bass (little energy above 1 kHz) is repitched
freely from five native notes. Struck notes are an attack that decays into a short loop of
whole harmonics and the engine continues the decay with VOL; sustained notes (the trumpet)
have their vibrato inside a one-cycle loop. Loops start after a lead-in and are whole 28-sample
blocks. Noise-like sounds (ambience, doors, waves) are stored at 11,025 Hz and played at
pitch 0.5.

Sound effects and ambience are synthesised here too: ringing ones (bells, chimes) also decay
into a loop of partials snapped to the loop's frequency grid, so a 1.5 s ring costs 0.4 s of
ROM. UI chimes use only F, Bb and C, the notes that F major (day) and Db major (night) share,
so they fit whichever music plays. Each effect's volume comes from a target loudness (LUFS,
400 ms windows, as heard with its decay) with its peak kept under -6 dBFS; music sits around
-27 LUFS, effects at -19 (star fanfare) to -32 (footsteps), ambience beds at -33 to -40.
The sound list must match the enums in carts/checkin/audio.akr (checked on every run).

Needs numpy and scipy. Encoded samples are cached in build/checkin_audio_cache/.

    python3 tools/gen_checkin_audio.py [--preview DIR] [--levels]
        --preview DIR: a WAV of every sample; --levels: each sound's volume, peak and loudness
"""
import concurrent.futures, hashlib, math, os, re, sys
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

SR = 22050
FPS = 60
FRAME = SR / FPS
LEAD = 56
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'carts', 'checkin')
AUD = os.path.join(OUT, 'audio')
CACHE = os.path.join(ROOT, 'build', 'checkin_audio_cache')


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ================================================================== DSP helpers

def rng_for(*key):
    h = hashlib.sha1(repr(key).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], 'little'))


def raised(n, a):
    """0..1 raised-cosine ramp over the first a samples."""
    r = np.ones(n)
    a = int(min(max(a, 1), n))
    r[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    return r


def fade_out(x, a):
    a = int(min(a, len(x)))
    if a > 0:
        x[-a:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(1, a + 1) / a)
    return x


def butter(x, kind, fc, sr=SR, order=2):
    nyq = sr / 2
    if kind == 'band':
        lo, hi = fc
        lo, hi = max(lo, 10) / nyq, min(hi, nyq * 0.98) / nyq
        sos = signal.butter(order, [lo, hi], 'bandpass', output='sos')
    else:
        sos = signal.butter(order, min(fc, nyq * 0.98) / nyq, kind, output='sos')
    return signal.sosfilt(sos, x)


def reson(x, f, q, sr=SR):
    """Constant-peak resonant bandpass (RBJ)."""
    w = 2 * np.pi * f / sr
    alpha = np.sin(w) / (2 * q)
    b = [alpha, 0, -alpha]
    a = [1 + alpha, -2 * np.cos(w), 1 - alpha]
    return signal.lfilter(b, a, x)


def noise(n, seed):
    return rng_for('noise', seed).standard_normal(n)


def pink(n, seed):
    w = noise(n, seed)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    y = signal.lfilter(b, a, w)
    return y / (np.std(y) + 1e-12)


def env_exp(n, tau, sr=SR, att=0.001):
    t = np.arange(n) / sr
    return raised(n, int(att * sr)) * np.exp(-t / tau)


def put(buf, start, x):
    s = int(start)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(x))
    buf[s:e] += x[:e - s]


def norm(x, peak=1.0):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def room(x, rt=0.5, mix=0.25, sr=SR, seed=0, lp_hz=4000):
    """A cheap convolution room for baking space into ambience."""
    n = int(rt * sr)
    ir = noise(n, ('room', seed)) * np.exp(-np.arange(n) / (rt * sr / 6.9))
    ir = butter(ir, 'low', lp_hz, sr)
    ir /= np.sqrt(np.sum(ir ** 2))
    wet = signal.fftconvolve(x, ir)[:len(x)]
    return x * (1 - mix) + wet * mix * np.std(x) / (np.std(wet) + 1e-12)


def loopify(y, L, xfade):
    """Makes y[0:L] loop seamlessly by crossfading y[L:L+xfade] onto its start (equal power,
    for noise-like signals). Returns the loop with a LEAD-sample lead-in (loop start LEAD)."""
    assert len(y) >= L + xfade
    z = y[:L].copy()
    k = np.arange(xfade) / xfade
    z[:xfade] = y[:xfade] * np.sin(0.5 * np.pi * k) + y[L:L + xfade] * np.cos(0.5 * np.pi * k)
    return np.concatenate([z[-LEAD:], z]), LEAD


def fit_loop(f, lo, hi):
    """Loop length in lo..hi (whole 28-sample blocks) holding a whole number of cycles of f
    closest in tune: (L, cycles, cents)."""
    best = None
    for L in range(-(-lo // 28) * 28, hi + 1, 28):
        c = round(f * L / SR)
        if c < 1:
            continue
        err = abs(1200 * math.log2(c * SR / L / f))
        if best is None or err < best[2] - 1e-9:
            best = (L, c, err)
    return best


def snap(f, L, sr=SR):
    """f moved to the nearest frequency with a whole number of cycles in L samples."""
    return max(1, round(f * L / sr)) * sr / L


# ================================================================== instruments

def struck(f0, partials, attack_s, cutoff, loop_s=(0.04, 0.12), noises=(), att_ms=2.0, seed=0, sat=0.0):
    """A struck tone that decays into a loop of whole harmonics.

    partials: (ratio, amp, tau, persist); persisting ones must be whole harmonics: they decay
    with their tau until the loop and stay level in it (the engine carries the decay on).
    The others fade out before the loop. noises: arrays added at the start (they are faded
    out before the loop too). Returns (x, loop_start)."""
    L, c, err = fit_loop(f0, int(loop_s[0] * SR), int(loop_s[1] * SR))
    hi = loop_s[1]
    while err > 3.0 and hi < 0.5:
        hi += 0.02
        L, c, err = fit_loop(f0, int(loop_s[0] * SR), int(hi * SR))
    assert err < 4.0, (f0, err)
    f = c * SR / L
    ls = int(math.ceil(attack_s * SR / 28.0)) * 28
    n = ls + L
    t = np.arange(n) / SR
    t_end = (ls - 40) / SR
    tf = min(0.2, t_end * 0.5)
    w = np.clip((t_end - t) / tf, 0, 1)
    w = 0.5 - 0.5 * np.cos(np.pi * w)
    rng = rng_for('struck', f0, seed)
    tl = np.minimum(t, ls / SR)
    x = np.zeros(n)
    for (ratio, amp, tau, persist) in partials:
        fr = ratio * f
        if fr > cutoff or amp <= 0:
            continue
        ph = rng.uniform(0, 2 * np.pi)
        if persist:
            assert abs(ratio - round(ratio)) < 1e-9, ratio
            env = amp * np.exp(-tl / tau)
        else:
            env = amp * np.exp(-t / tau) * w
        x += env * np.sin(2 * np.pi * fr * t + ph)
    for nz in noises:
        m = min(len(nz), n)
        x[:m] += nz[:m] * w[:m]
    x *= raised(n, int(att_ms * SR / 1000))
    if sat > 0:
        x = np.tanh(sat * x / np.max(np.abs(x))) / np.tanh(sat)
    return x, ls


def guitar_render(m, shift):
    """Nylon-string guitar: plucked near the bridge, soft flesh attack, small body resonances."""
    f = mtof(m)
    cutoff = 9500 / 2 ** shift
    beta = 0.17

    def body(fr):
        g = 1.0
        for fc, q, a in ((102, 6, 0.9), (205, 5, 0.6), (390, 4, 0.35), (2600, 1.5, 0.12)):
            g += a / (1 + ((fr - fc) / (fc / q)) ** 2)
        return g

    parts = []
    k = 1
    while k * f < cutoff:
        fr = k * f
        a = abs(math.sin(math.pi * k * beta)) / k ** 0.85 * body(fr) / (1 + (fr / 2600) ** 2)
        tau = 1.1 * (196 / f) ** 0.25 / (1 + (fr / 1300) ** 1.4)
        parts.append((k, a, tau, k <= 5))
        k += 1
    n = int(0.06 * SR)
    thump = butter(noise(n, ('gt', m)), 'low', 400) * env_exp(n, 0.008) * 0.25
    tick = butter(noise(n, ('gt2', m)), 'band', (2000, 5000 / 2 ** shift)) * env_exp(n, 0.002) * 0.04
    return struck(f, parts, 0.22, cutoff, (0.03, 0.08), (thump, tick), att_ms=1.0, seed=m)


def rhodes_render(m, shift):
    """Electric piano: a strong fundamental, a soft second harmonic, a quick inharmonic tine
    'bark' and a little saturation from the pickup."""
    f = mtof(m)
    cutoff = 9000 / 2 ** shift
    lowboost = min(1.0, (f / 300) ** 0.5)
    parts = [(1, 1.0, 2.2, True), (2, 0.28 * lowboost, 1.0, True), (3, 0.09, 0.5, True), (4, 0.03, 0.3, True),
             (6.97, 0.22, 0.045, False), (13.9, 0.06, 0.02, False), (2, 0.12, 0.08, False)]
    n = int(0.05 * SR)
    thunk = butter(noise(n, ('rh', m)), 'low', 900) * env_exp(n, 0.006) * 0.06
    return struck(f, parts, 0.26, cutoff, (0.03, 0.08), (thunk,), att_ms=2.0, seed=m, sat=1.2)


def vibes_render(m, shift):
    """Vibraphone: fundamental plus the bar's tuned fourth partial, soft yarn-mallet attack.
    The motor tremolo comes from the engine."""
    f = mtof(m)
    cutoff = 10000 / 2 ** shift
    parts = [(1, 1.0, 3.0, True), (4, 0.22, 0.6, True), (2, 0.015, 1.0, True),
             (10, 0.05, 0.05, False), (9.92, 0.03, 0.04, False)]
    n = int(0.04 * SR)
    mallet = butter(noise(n, ('vb', m)), 'band', (600, 3000 / 2 ** shift)) * env_exp(n, 0.003) * 0.05
    return struck(f, parts, 0.2, cutoff, (0.03, 0.07), (mallet,), att_ms=1.5, seed=m)


def piano_render(m, shift):
    """Acoustic piano: hammer-position spectrum, slightly stretched upper partials, a doubled
    unison that beats during the attack, and a soft hammer knock."""
    f = mtof(m)
    cutoff = 9000 / 2 ** shift
    B = 0.0003 * (f / 262) ** 0.6
    parts = []
    k = 1
    while k * f < cutoff:
        fk = k * f * math.sqrt(1 + B * k * k)
        a = abs(math.sin(math.pi * k / 7.3)) / k ** 0.75 / (1 + (k * f / 2800) ** 2)
        if k <= 4:
            parts.append((k, a * 0.55, 2.4 / (1 + 0.25 * k), True))
            parts.append((k, a * 0.45, 0.25, False))
            parts.append((fk / f * 1.0011, a * 0.35, 0.35, False))       # second string
        else:
            parts.append((fk / f, a, 0.9 / (k / 4) ** 1.2, False))
        k += 1
    n = int(0.06 * SR)
    knock = butter(noise(n, ('pn', m)), 'low', 700) * env_exp(n, 0.01) * 0.08
    knock += np.sin(2 * np.pi * 95 * np.arange(n) / SR) * env_exp(n, 0.02) * 0.05
    return struck(f, parts, 0.3, cutoff, (0.03, 0.08), (knock,), att_ms=1.0, seed=m)


def bass_render(m, shift):
    """Upright bass, finger pluck: strong fundamental and second, a woody thump."""
    f = mtof(m)
    cutoff = 3500
    parts = [(1, 1.0, 1.4, True), (2, 0.6, 0.9, True), (3, 0.3, 0.5, True), (4, 0.16, 0.35, True),
             (5, 0.12, 0.2, False), (6, 0.08, 0.14, False), (7, 0.05, 0.1, False), (8, 0.04, 0.08, False),
             (9, 0.03, 0.06, False)]
    n = int(0.08 * SR)
    thump = butter(noise(n, ('bs', m)), 'low', 180) * env_exp(n, 0.02) * 0.5
    pluck = butter(noise(n, ('bs2', m)), 'band', (500, 1500)) * env_exp(n, 0.006) * 0.08
    return struck(f, parts, 0.26, cutoff, (0.06, 0.16), (thump, pluck), att_ms=3.0, seed=m)


def trumpet_render(m, shift):
    """Harmon-muted trumpet: nasal formant around 1.5-2.5 kHz, weak fundamental, a breathy
    tongued attack with a small scoop, and one cycle of vibrato in the loop."""
    f0 = mtof(m)
    L, c, err = fit_loop(f0, int(0.19 * SR), int(0.32 * SR))
    assert err < 2.0, (m, err)
    f = c * SR / L
    ls = int(math.ceil(0.11 * SR / 28)) * 28
    n = ls + L
    i = np.arange(n)
    tt = (i - ls) / SR
    t = i / SR
    vib_d = 0.0055 * np.clip(t / (ls / SR), 0, 1) ** 2        # vibrato depth eases in to the loop
    beta = vib_d * f * L / SR / (2 * np.pi) * 2 * np.pi       # phase deviation (radians) = d f / rate
    scoop = -0.02 * 0.02 * (1 - np.exp(-t / 0.02))            # integrated pitch scoop (cycles/f)
    phi = 2 * np.pi * f * tt + beta * np.sin(2 * np.pi * (i - ls) / L) + 2 * np.pi * f * scoop
    x = np.zeros(n)
    rng = rng_for('tp', m)
    k = 1
    while k * f < 7500:
        fk = k * f
        a = (fk / 1600) ** 1.6 / (1 + (fk / 1900) ** 4) + 0.05 / k
        a *= 1 + 0.6 / (1 + ((fk - 1700) / 500) ** 2)
        onset = 1 - np.exp(-t / (0.008 + 0.0035 * k))
        x += a * onset * np.sin(k * phi + rng.uniform(0, 2 * np.pi))
        k += 1
    x *= 1 + 0.06 * np.sin(2 * np.pi * (i - ls) / L) * np.clip(t / (ls / SR), 0, 1)
    nb = int(0.12 * SR)
    breath = butter(noise(nb, ('tpn', m)), 'band', (1200, 4500)) * env_exp(nb, 0.03, att=0.004) * 0.5
    breath *= np.clip((ls - 40 - np.arange(nb)) / 400, 0, 1)
    x[:nb] += breath * np.std(x[ls:])
    x *= raised(n, int(0.012 * SR))
    return x, ls


# ---- drums (one kit; event notes pick the piece)

def kit_render(piece):
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    if piece == 'kick':
        f = 52 + 40 * np.exp(-t / 0.025)
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = np.sin(ph) * env_exp(n, 0.13, att=0.002)
        x += butter(noise(n, 'kk'), 'low', 1500) * env_exp(n, 0.004) * 0.25
        return fade_out(x[:int(0.36 * SR)], 400), 2
    if piece == 'rim':
        n = int(0.14 * SR)
        click = noise(n, 'rim')
        x = reson(click * env_exp(n, 0.002), 480, 12) * 1.0 + reson(click * env_exp(n, 0.0015), 1750, 9) * 0.8
        x += butter(click, 'high', 3000) * env_exp(n, 0.0012) * 0.4
        return fade_out(x, 300), 1
    if piece == 'tap':
        n = int(0.2 * SR)
        x = butter(noise(n, 'tap'), 'band', (1500, 9000)) * env_exp(n, 0.045, att=0.003)
        x += np.sin(2 * np.pi * 190 * np.arange(n) / SR) * env_exp(n, 0.03) * 0.15
        return fade_out(x, 600), 1
    if piece == 'sweep':
        n = int(0.42 * SR)
        e = np.sin(np.pi * np.clip(np.arange(n) / n, 0, 1)) ** 1.6
        x = butter(noise(n, 'sweep'), 'band', (1800, 8000)) * e
        x = butter(x, 'high', 1500)
        return fade_out(x, 600), 1
    if piece == 'shaker':
        n = int(0.09 * SR)
        e = raised(n, int(0.012 * SR)) * np.exp(-np.arange(n) / (0.02 * SR))
        x = butter(noise(n, 'shk'), 'band', (3500, 10000)) * e
        return fade_out(x, 200), 1
    if piece == 'hat':
        n = int(0.11 * SR)
        tt = np.arange(n) / SR
        x = sum(np.sign(np.sin(2 * np.pi * fr * tt)) for fr in (205.3, 304.4, 369.6, 522.7, 540.0, 800.0))
        x = butter(x, 'band', (6000, 10500)) * env_exp(n, 0.022, att=0.002)
        x += butter(noise(n, 'hat'), 'high', 7000) * env_exp(n, 0.015) * 0.3
        return fade_out(x, 300), 1
    raise ValueError(piece)


def ride_render():
    """A brushed ride: inharmonic partials snapped to the loop grid, decaying into a loop."""
    L = 28 * 100
    ls = 28 * 120
    n = ls + L
    t = np.arange(n) / SR
    tl = np.minimum(t, ls / SR)
    rng = rng_for('ride')
    x = np.zeros(n)
    for j in range(46):
        fr = snap(380 * 1.11 ** j * rng.uniform(0.97, 1.03), L)
        if fr > 10000:
            break
        a = rng.uniform(0.4, 1.0) / (1 + (fr / 4000) ** 2) * (fr / 1000) ** 0.3
        x += a * np.exp(-tl / rng.uniform(0.3, 0.9)) * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6.3))
    ping = snap(3150, L)
    x += 1.5 * np.exp(-t / 0.08) * np.sin(2 * np.pi * ping * t) * np.clip((ls - 40 - np.arange(n)) / 2000, 0, 1)
    tip = butter(noise(n, 'ridetip'), 'high', 4000) * env_exp(n, 0.006) * 2
    x += tip * np.clip((ls - 40 - np.arange(n)) / 1000, 0, 1)
    x *= raised(n, 20)
    return x, ls


class Inst:
    """mode 1: struck (decay after the attack, release at the note's end); mode 2: sustained
    (holds its loop level until the note ends, then releases)."""

    def __init__(self, key, mode, render, vol, tail_tau=1.0, release_s=0.2, reverb=True, trem=(0, 0, 0.0),
                 native_hi=127, free_natives=None, mono=False, cut_s=0.04, prio=0, norm_peak=0.5):
        self.key, self.mode, self.render, self.vol = key, mode, render, vol
        self.tail_tau, self.release_s, self.reverb, self.trem = tail_tau, release_s, reverb, trem
        self.native_hi, self.free_natives, self.mono, self.cut_s, self.prio = native_hi, free_natives, mono, cut_s, prio
        self.norm_peak = norm_peak
        self.used = set()

    def params(self, nmap_base, lo, hi):
        dec = 65535 if self.tail_tau <= 0 else round(65536 * math.exp(-1 / (self.tail_tau * FPS)))
        rel = round(65536 * math.exp(-1 / (self.release_s * FPS)))
        cut = round(65536 * math.exp(-1 / (self.cut_s * FPS)))
        kind, depth, rate = self.trem
        return [self.mode, min(dec, 65535), rel, self.vol, int(self.reverb), kind, round(depth * 256),
                round(rate / FPS * 65536), nmap_base, lo, hi, int(self.mono), cut, self.prio, 0, 0]


KIT_NOTES = {36: 'kick', 37: 'rim', 38: 'tap', 39: 'sweep', 42: 'hat', 51: 'ride', 70: 'shaker'}
KICK, RIM, TAP, SWEEP, HAT, RIDE, SHAKER = 36, 37, 38, 39, 42, 51, 70


def make_insts():
    return {
        'guitar': Inst('guitar', 1, guitar_render, vol=118, tail_tau=1.1, release_s=0.1, native_hi=63, prio=1),
        'rhodes': Inst('rhodes', 1, rhodes_render, vol=92, tail_tau=1.8, release_s=0.1, native_hi=64,
                       trem=(2, 0.55, 3.9)),
        'vibes': Inst('vibes', 1, vibes_render, vol=112, tail_tau=2.2, release_s=0.12, native_hi=75,
                      trem=(1, 0.32, 5.6), prio=2),
        'bass': Inst('bass', 1, bass_render, vol=110, tail_tau=0.9, release_s=0.1, reverb=False,
                     free_natives=[28, 33, 38, 43, 48], mono=True, cut_s=0.05, prio=3),
        'piano': Inst('piano', 1, piano_render, vol=150, tail_tau=1.6, release_s=0.12, native_hi=64),
        'trumpet': Inst('trumpet', 2, trumpet_render, vol=90, release_s=0.08, mono=True, cut_s=0.05, prio=3,
                        norm_peak=0.45),
        'kit': Inst('kit', 1, None, vol=135, tail_tau=1.1, release_s=0.15, prio=1),
        'bell': Inst('bell', 1, None, vol=100, tail_tau=1.3, release_s=0.3, prio=2),
    }


INST_ORDER = ['guitar', 'rhodes', 'vibes', 'bass', 'piano', 'trumpet', 'kit', 'bell']


# ================================================================== harmony

NOTE_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

# quality: chord tones, 4- and 3-voice voicing templates (intervals above the root), the
# scale for lines, and notes to avoid on strong beats
QUAL = {
    'maj7': ([0, 4, 7, 11], [[4, 7, 11, 14], [4, 9, 11, 14], [11, 14, 16, 19]], [[4, 11, 14], [4, 7, 11], [11, 16, 19]],
             [0, 2, 4, 5, 7, 9, 11], [5]),
    'maj7#11': ([0, 4, 7, 11], [[4, 6, 11, 14], [11, 14, 16, 18]], [[4, 11, 18], [6, 11, 16]],
                [0, 2, 4, 6, 7, 9, 11], []),
    '6/9': ([0, 4, 7, 9], [[4, 9, 14, 19], [2, 4, 7, 9]], [[4, 9, 14]], [0, 2, 4, 7, 9], []),
    'm7': ([0, 3, 7, 10], [[3, 7, 10, 14], [10, 14, 15, 19], [3, 10, 14, 17]], [[3, 10, 14], [3, 7, 10], [10, 15, 19]],
           [0, 2, 3, 5, 7, 9, 10], []),
    'm6': ([0, 3, 7, 9], [[3, 7, 9, 14], [9, 14, 15, 19]], [[3, 9, 14], [9, 15, 19]], [0, 2, 3, 5, 7, 9, 11], []),
    'm7b5': ([0, 3, 6, 10], [[3, 6, 10, 12], [10, 12, 15, 18]], [[3, 6, 10], [10, 15, 18]],
             [0, 2, 3, 5, 6, 8, 10], []),
    '7': ([0, 4, 7, 10], [[4, 9, 10, 14], [10, 14, 16, 21], [4, 10, 14, 19]], [[4, 10, 14], [10, 16, 21], [4, 9, 10]],
          [0, 2, 4, 5, 7, 9, 10], [5]),
    '7b9': ([0, 4, 7, 10], [[4, 10, 13, 19], [10, 13, 16, 19]], [[4, 10, 13], [10, 13, 16]],
            [0, 1, 4, 5, 7, 8, 10], [5]),
    '7b13': ([0, 4, 7, 10], [[4, 10, 14, 20], [10, 14, 16, 20]], [[4, 10, 20], [10, 16, 20]],
             [0, 2, 4, 5, 7, 8, 10], [5]),
    '9#11': ([0, 4, 7, 10], [[4, 10, 14, 18], [10, 14, 16, 18]], [[4, 10, 18], [10, 16, 18]],
             [0, 2, 4, 6, 7, 9, 10], []),
    '7sus4': ([0, 5, 7, 10], [[5, 10, 14, 19], [10, 14, 17, 21]], [[5, 10, 14], [10, 17, 21]],
              [0, 2, 4, 5, 7, 9, 10], [4]),
    'dim7': ([0, 3, 6, 9], [[3, 6, 9, 12], [0, 3, 6, 9]], [[3, 6, 9], [6, 9, 12]], [0, 2, 3, 5, 6, 8, 9, 11], []),
}
QALIAS = {'maj9': 'maj7', 'm9': 'm7', '9': '7', '13': '7', 'm7b5': 'm7b5', '13sus': '7sus4', 'dim7': 'dim7'}


class Chord:
    def __init__(self, sym):
        mm = re.match(r'([A-G])([#b]?)(.*)$', sym)
        assert mm, sym
        self.sym = sym
        self.root = (NOTE_PC[mm.group(1)] + {'': 0, '#': 1, 'b': -1}[mm.group(2)]) % 12
        q = QALIAS.get(mm.group(3), mm.group(3))
        assert q in QUAL, sym
        self.q = q
        tones, self.v4, self.v3, sc, av = QUAL[q]
        self.tones = [(self.root + i) % 12 for i in tones]
        self.scale = sorted({(self.root + i) % 12 for i in sc})
        self.avoid = {(self.root + i) % 12 for i in av}
        ext = {'maj9': [14], '9': [14], 'm9': [14], '13': [14, 21], '6/9': [14], 'maj7#11': [14, 18], '9#11': [14, 18],
               '7b9': [13], '7b13': [20], '13sus': [14, 21]}.get(mm.group(3), [])
        self.color = sorted(set(self.tones) | {(self.root + i) % 12 for i in ext})

    def bass(self, prev=None, lo=33, hi=45):
        cands = [p for p in range(lo, hi + 1) if p % 12 == self.root]
        if prev is None:
            return cands[len(cands) // 2]
        return min(cands, key=lambda p: abs(p - prev))

    def fifth(self):
        return (self.root + (6 if self.q in ('m7b5', 'dim7') else 7)) % 12


def voicings(ch, n, lo, hi):
    out = []
    for tpl in (ch.v4 if n == 4 else ch.v3):
        base = [ch.root + i for i in tpl]
        for o in range(-3, 6):
            v = [p + 12 * o for p in base]
            if v[0] >= lo and v[-1] <= hi:
                out.append(v)
    return out


def voice_lead(chords, n, lo, hi, prev=None):
    """A voicing per chord, each close to the previous one."""
    res = []
    centre = (lo + hi) / 2
    for ch in chords:
        cands = voicings(ch, n, lo, hi)
        assert cands, (ch.sym, lo, hi)

        def cost(v):
            c = abs(np.mean(v) - centre) * 0.35
            if prev is not None:
                c += sum(abs(a - b) for a, b in zip(sorted(v), sorted(prev)))
            if v[1] - v[0] <= 2 and v[0] < 55:
                c += 6
            return c
        prev = min(cands, key=cost)
        res.append(prev)
    return res


# ================================================================== score building

class Song:
    def __init__(self, key, beat, swing=False):
        self.key, self.beat, self.swing = key, beat, swing
        self.bar = 4 * beat
        self.sections = []
        self.form = []
        self.loop_to = 0
        self.ending = None
        self.exit_bars = False
        self.gain = 84

    def frames(self, b):
        """Beat position (float) to frames; swung songs place off-beat 8ths at 2/3 of the beat."""
        w = math.floor(b + 1e-9)
        fr = b - w
        if self.swing:
            fr = fr * 4 / 3 if fr <= 0.5 else 2 / 3 + (fr - 0.5) * 2 / 3
        return int(round((w + fr) * self.beat))


class Section:
    def __init__(self, song, name, bars):
        self.song, self.name = song, name
        self.chords = []           # (beat start, Chord)
        for bi, bar in enumerate(bars):
            syms = bar.split()
            for j, s in enumerate(syms):
                self.chords.append((bi * 4 + j * 4 / len(syms), Chord(s)))
        self.nbars = len(bars)
        self.length = self.nbars * song.bar
        self.parts = {}
        song.sections.append(self)

    def chord_at(self, beat):
        c = self.chords[0][1]
        for b, ch in self.chords:
            if b <= beat + 1e-9:
                c = ch
        return c

    def next_chord(self, beat):
        for b, ch in self.chords:
            if b > beat + 1e-9:
                return b, ch
        return None, None


class Ev:
    """A part variant's events. period > 0: the engine repeats them every period frames until
    the section ends (drum patterns)."""

    def __init__(self, period=0):
        self.ev = []
        self.period = period

    def add(self, sec, beat, inst, note, vel, pan=64, dur_beats=0.0, dur_frames=None):
        song = sec.song
        t = song.frames(beat)
        if t >= sec.length:
            return
        if dur_frames is None:
            dur = song.frames(beat + dur_beats) - t if dur_beats > 0 else 0
        else:
            dur = dur_frames
        if dur > 0:
            dur = max(2, dur)
        self.ev.append((t, inst, int(note), int(max(1, min(127, round(vel)))), int(max(0, min(127, round(pan)))),
                        int(max(0, min(32767, dur)))))


def parse_mel(bars, key_pc=None):
    """Melody notation, one string per bar: 'A4/8 C5/8 G5/4. r/8 E5/8~E5/2'. Durations /1 /2 /4
    /8 /16, '.' dotted, 't' triplet; '~' ties into the next token. Returns (beat, midi, beats)."""
    out = []
    for bi, bar in enumerate(bars):
        pos = 0.0
        tie = False
        toks = []
        for tk in bar.split():
            parts = tk.split('~')
            toks += [q + '~' for q in parts[:-1] if q] + ([parts[-1]] if parts[-1] else [])
        for tok in toks:
            mm = re.match(r'([A-Gr])([#b]?)(\d?)/(\d+)(\.?)(t?)(~?)$', tok)
            assert mm, tok
            d = 4.0 / int(mm.group(4))
            if mm.group(5):
                d *= 1.5
            if mm.group(6):
                d *= 2 / 3
            if mm.group(1) != 'r':
                p = 12 * (int(mm.group(3)) + 1) + NOTE_PC[mm.group(1)] + {'': 0, '#': 1, 'b': -1}[mm.group(2)]
                if tie and out and out[-1][1] == p:
                    out[-1][2] += d
                else:
                    out.append([bi * 4 + pos, p, d])
            tie = bool(mm.group(7))
            pos += d
        assert abs(pos - 4) < 1e-6, (bar, pos)
    return out


def anticipate(sec, mel):
    """A phrasing variant: long notes on beats 1 and 3 arrive an 8th early, where the note
    before them leaves room (it is shortened, never below an 8th) and the note also fits the
    chord it now starts over."""
    out = [list(n) for n in mel]
    for i, n in enumerate(out):
        b, p, d = n
        if abs(b % 2) > 1e-6 or d < 1 or b < 0.5:
            continue
        ch = sec.chord_at(b - 0.5)
        if p % 12 not in ch.color and (p % 12 not in ch.scale or p % 12 in ch.avoid):
            continue
        if i > 0:
            pb, pp, pd = out[i - 1]
            if pb > b - 1.0 + 1e-6:
                continue                      # the note before starts too late to shorten
            out[i - 1][2] = min(pd, b - 0.5 - pb)
        n[0], n[2] = b - 0.5, d + 0.5
    return out


def check_melody(sec, mel, name):
    """Notes on strong beats (or long ones) must belong to the chord or its colour tones."""
    bad = []
    for b, p, d in mel:
        ch = sec.chord_at(b)
        strong = abs(b - round(b)) < 1e-6 and round(b) % 2 == 0
        if (strong or d >= 1.5) and p % 12 not in ch.color and p % 12 not in ch.scale:
            bad.append((b, p, ch.sym))
    assert not bad, (name, bad)


# ---- parts

def comp_guitar(sec, variant, rng, n=3, lo=52, hi=72, prev=None, inst='guitar', pan=40, vel=78):
    """Bossa-nova chord plucks; a hit in the last 8th of a bar takes the next bar's chord."""
    pats = [
        [0, 3, 6, 10, 13],                    # 1, 2&, 4 | 2, 3&
        [0, 2, 5, 7, 10, 12, 15],             # 1, 2, 3&, 4& | 2, 3, 4&
        [0, 3, 5, 8, 11, 13],                 # 1, 2&, 3& | 1, 2&, 3&
        [0, 4, 8, 12],                        # half notes (sparse)
    ]
    pat = pats[variant % len(pats)]
    ev = Ev()
    hits = []
    for two in range(0, sec.nbars, 2):
        for e8 in pat:
            beat = two * 4 + e8 * 0.5
            if beat >= sec.nbars * 4:
                continue
            ch = sec.chord_at(beat)
            nb, nch = sec.next_chord(beat)
            if nch is not None and nb - beat <= 0.5 + 1e-9 and abs(beat % 1 - 0.5) < 1e-9:
                ch = nch                      # anticipation
            hits.append((beat, ch))
    chords = [c for _, c in hits]
    vs = voice_lead(chords, n, lo, hi, prev)
    for i, ((beat, ch), v) in enumerate(zip(hits, vs)):
        nxt = hits[i + 1][0] if i + 1 < len(hits) else sec.nbars * 4
        cb, cch = sec.next_chord(beat + 0.01)
        if cb is not None and cch is not ch and cb < nxt:
            nxt = cb + 0.1                    # let go when the harmony moves on
        dur = max(0.25, nxt - beat - 0.12)
        acc = 1.0 if abs(beat % 2) < 1e-9 else 0.9
        for j, p in enumerate(v):
            ev.add(sec, beat, inst, p, vel * acc * (0.85 + 0.1 * j) + rng.integers(-4, 5), pan + rng.integers(-4, 5),
                   dur)
    return ev, vs[-1] if vs else prev


def pads(sec, inst, n, lo, hi, vel, pan=64, style='whole', prev=None, rng=None):
    """Sustained chord voicings: one per chord change ('whole'), or short stabs."""
    ev = Ev()
    chs = sec.chords
    vs = voice_lead([c for _, c in chs], n, lo, hi, prev)
    for i, ((b, ch), v) in enumerate(zip(chs, vs)):
        end = chs[i + 1][0] if i + 1 < len(chs) else sec.nbars * 4
        if style == 'whole':
            for j, p in enumerate(v):
                ev.add(sec, b, inst, p, vel - 3 * j, pan, end - b - 0.1)
        elif style == 'stabs':
            for off in (1.5, 3.0):
                if b + off < end:
                    for p in v:
                        ev.add(sec, b + off, inst, p, vel * (1.0 if off < 2 else 0.85), pan, 0.4)
        elif style == 'charleston':
            for off, d in ((0, 1.2), (1.5, 0.9)):
                if b + off < end - 0.1:
                    for p in v:
                        ev.add(sec, b + off, inst, p, vel * (1.0 if off == 0 else 0.8) + rng.integers(-3, 4), pan, d)
        elif style == 'ballad':                 # long chords, a soft re-strike half way when a bar holds one
            for p in v:
                ev.add(sec, b, inst, p, vel + rng.integers(-3, 4), pan, end - b - 0.15)
            if end - b >= 4 and rng.random() < 0.6:
                for p in v[1:]:
                    ev.add(sec, b + 2.5, inst, p, vel * 0.7, pan, 1.3)
    return ev, vs[-1]


def bass_bossa(sec, variant, rng, prev=None):
    """Root on the beat, fifth on the anticipating 8th (the surdo feel); a walk-up variant."""
    ev = Ev()
    note = prev
    for bar in range(sec.nbars):
        b0 = bar * 4
        halves = [(b0, sec.chord_at(b0)), (b0 + 2, sec.chord_at(b0 + 2))]
        for hb, ch in halves:
            r = ch.bass(note, 31, 45)
            note = r
            iv = (ch.fifth() - ch.root) % 12
            f5 = r + iv if r + iv <= 47 else r + iv - 12
            same = hb > b0 and halves[0][1] is ch
            ev.add(sec, hb, 'bass', f5 if same else r, 96 + rng.integers(-5, 4), 64, 1.35)
            nb, nch = sec.next_chord(hb + 1.0)
            if variant == 1 and nch is not None and nb == hb + 2:
                nr = nch.bass(note, 31, 45)
                appr = nr - 1 if rng.random() < 0.5 else nr + 1
                ev.add(sec, hb + 1.5, 'bass', appr, 78, 64, 0.4)
            else:
                ev.add(sec, hb + 1.5, 'bass', f5 if not same else r, 76 + rng.integers(-5, 4), 64, 0.4)
    return ev, note


def bass_walk(sec, rng, prev=None, two_feel=False):
    """Walking bass: chord tone on the beat a chord arrives, scale/chord steps between, a
    chromatic or scale approach into the next root."""
    ev = Ev()
    note = prev
    total = sec.nbars * 4
    for beat in range(total):
        ch = sec.chord_at(beat)
        cb = max(b for b, c in sec.chords if b <= beat + 1e-9)
        nb, nch = sec.next_chord(beat)
        if nb is None:
            nb, nch = total, sec.chords[0][1]
        if two_feel and beat % 2 == 1:
            continue
        if beat == cb:
            p = ch.bass(note, 31, 46)
        elif beat == nb - 1 or (two_feel and beat == nb - 2):
            tgt = nch.bass(note, 31, 46)
            r = rng.random()
            if r < 0.55:
                p = tgt + (1 if note is not None and note > tgt else -1)
            elif r < 0.8:
                p = tgt + 7 if tgt + 7 <= 47 else tgt - 5
            else:
                cand = [q for q in range(tgt - 3, tgt + 4) if q % 12 in nch.scale and q != tgt]
                p = min(cand, key=lambda q: abs(q - note)) if cand else tgt - 1
        else:
            cands = [q for q in range(note - 5, note + 6) if q % 12 in ch.tones and q != note
                     and 29 <= q <= 48]
            steps = [q for q in range(note - 2, note + 3) if q % 12 in ch.scale and q != note and 29 <= q <= 48]
            pool = steps if rng.random() < 0.5 and steps else (cands or steps)
            p = pool[int(rng.integers(len(pool)))]
        d = 1.9 if two_feel else 0.92
        acc = 92 if beat % 2 == 0 else 84
        ev.add(sec, beat, 'bass', p, acc + rng.integers(-5, 5), 64, d)
        note = p
    return ev, note


def drums_bossa(sec, variant, rng, light=False, bars=None):
    """Brushes and shaker 16ths, a soft kick on the surdo rhythm, the cross-stick pattern.
    bars: only that many bars, repeated by the engine. variant 1 ends with a fill."""
    nb = bars or sec.nbars
    ev = Ev(nb * sec.song.bar if bars else 0)
    rim2 = [0, 3, 6, 10, 13]
    for bar in range(nb):
        b0 = bar * 4
        last = bar == nb - 1 and not bars
        for st in range(16):
            v = [56, 30, 40, 30][st % 4]
            if variant == 2:
                v *= 0.8
            ev.add(sec, b0 + st * 0.25, 'kit', SHAKER if not light else TAP, v + rng.integers(-5, 5),
                   82 if not light else 70)
        if not light:
            for b, v in ((0, 64), (1.5, 44), (2, 58), (3.5, 44)):
                ev.add(sec, b0 + b, 'kit', KICK, v + rng.integers(-4, 4), 64)
            if not (last and variant == 1):
                for e8 in rim2:
                    if (bar % 2) * 8 <= e8 < (bar % 2) * 8 + 8:
                        ev.add(sec, b0 + (e8 % 8) * 0.5, 'kit', RIM, 72 + rng.integers(-6, 6), 74)
            else:
                for k, b in enumerate((0, 1, 1.5, 2, 2.5, 3, 3.25, 3.5, 3.75)):
                    ev.add(sec, b0 + b, 'kit', TAP if k % 3 else RIM, 50 + 5 * k, 56 + 4 * k)
        if light or variant == 2:
            for b in (0, 2):
                ev.add(sec, b0 + b, 'kit', SWEEP, 44, 50 if b == 0 else 78)
    return ev


def drums_ballad(sec, variant, rng, ride=False, bars=None):
    """Brush sweeps on 1 and 3, taps and the hi-hat foot on 2 and 4, a ride pattern in the
    solos. variant 1 ends with a small fill."""
    nb = bars or sec.nbars
    ev = Ev(nb * sec.song.bar if bars else 0)
    for bar in range(nb):
        b0 = bar * 4
        last = bar == nb - 1 and not bars
        for b in (0, 2):
            ev.add(sec, b0 + b, 'kit', SWEEP, 46 + rng.integers(-4, 4), 52 if b == 0 else 76)
        for b in (1, 3):
            ev.add(sec, b0 + b, 'kit', TAP, 54 + rng.integers(-5, 5), 66)
            ev.add(sec, b0 + b, 'kit', HAT, 46 + rng.integers(-4, 4), 84)
            if rng.random() < 0.6:
                ev.add(sec, b0 + b + 0.5, 'kit', TAP, 30 + rng.integers(-4, 4), 62)
        if ride:
            for b, v in ((0, 52), (1, 44), (1.5, 34), (2, 50), (3, 44), (3.5, 34)):
                ev.add(sec, b0 + b, 'kit', RIDE, v + rng.integers(-4, 4), 92)
        if b0 == 0 or rng.random() < 0.3:
            ev.add(sec, b0, 'kit', KICK, 34, 64)
        if last and variant == 1:
            for k, b in enumerate((2.5, 3, 3.5)):
                ev.add(sec, b0 + b, 'kit', TAP, 46 + 8 * k, 58 + 6 * k)
    return ev


def melody_events(sec, mel, inst, vel, pan, rng, legato=0.92, accent_off=False):
    ev = Ev()
    for b, p, d in mel:
        v = vel + rng.integers(-5, 5)
        if accent_off and abs(b % 1 - 0.5) < 1e-6:
            v += 6
        if d >= 2:
            v += 3
        ev.add(sec, b, inst, p, v, pan + rng.integers(-3, 4), d * legato)
    return ev


RHY_STRAIGHT = [  # 2-bar rhythm cells over 16 eighths: x onset, - held, . rest
    '.xx-x-x-x---....', 'x--x--x-........', '..x-xxx-x---.x-.', '.x-x-x-xx-------', 'x-.xx-.xx---....',
    '....x-x-xx-x--..', '.xxx-x--.x-x-x--', 'x---.x-x-xx---..', '..xx-x-x---x----', '.x-xx--x-x-x-x--',
]
RHY_SWING = [
    '.xxxx-x-x---....', '..x-x-xxx---....', 'x--xxx-xx-------', '.x-xx-x-....xx--', '..xxxxx-x---.x-.',
    'x-xx-x--........', '.xxx-xx-x-x-x---', '....x-xxx-x--.x-', '.x-x-xxx--------', 'xx-x-x--..xxx---',
]


def solo_line(sec, inst, lo, hi, rng, vel, pan, swing=False, density=0.8, motif=None, start=None, allowed=None):
    """A phrase generator: rhythm cells, chord tones (with colour tones) where a note falls
    on a beat or is held, scale steps or a chromatic approach between them, an arching
    contour, and space between phrases."""
    ev = Ev()
    ok = (lambda q: lo <= q <= hi) if allowed is None else (lambda q: q in allowed)
    cells = RHY_SWING if swing else RHY_STRAIGHT
    p = start if start is not None else (lo + hi) // 2
    total = sec.nbars * 4
    for ph in range(0, sec.nbars, 2):
        b0 = ph * 4
        if rng.random() > density and ph > 0:
            continue
        cell = cells[int(rng.integers(len(cells)))]
        notes = []
        i = 0
        while i < 16:
            if cell[i] == 'x':
                j = i + 1
                while j < 16 and cell[j] == '-':
                    j += 1
                notes.append((i * 0.5, (j - i) * 0.5))
                i = j
            else:
                i += 1
        shape = rng.choice(['arch', 'down', 'up', 'arch'])
        peak = int(rng.integers(len(notes))) if notes else 0
        use_motif = motif is not None and ph == 0
        for k, (nb, d) in enumerate(notes):
            beat = b0 + nb
            if beat >= total:
                break
            ch = sec.chord_at(beat)
            if use_motif and k < 3:
                ivs = motif[k]
                cands = [q for q in range(lo, hi + 1) if q % 12 == (ch.root + ivs) % 12 and ok(q)] or [p]
                p = min(cands, key=lambda q: abs(q - p))
            else:
                up = {'arch': k <= peak, 'down': False, 'up': True}[shape]
                if p > hi - 3:
                    up = False
                if p < lo + 3:
                    up = True
                strong = abs(nb % 1) < 1e-6 or d >= 1 or k == len(notes) - 1
                if strong:
                    pool = [q for q in range(lo, hi + 1) if q % 12 in ch.color and q % 12 not in ch.avoid and ok(q)]
                    pool = pool or [q for q in range(lo, hi + 1) if q % 12 in ch.tones]
                    dirp = [q for q in pool if (q > p if up else q < p) and abs(q - p) <= 7]
                    pool = dirp or pool
                    p = min(pool, key=lambda q: abs(q - p) + rng.random() * 2)
                else:
                    nb2, nch = sec.next_chord(beat)
                    nxt_strong = k + 1 < len(notes) and abs(notes[k + 1][0] % 1) < 1e-6
                    if nxt_strong and rng.random() < 0.25:
                        tgt_ch = sec.chord_at(b0 + notes[k + 1][0])
                        tg = [q for q in range(p - 4, p + 5) if q % 12 in tgt_ch.tones]
                        if tg:
                            q = min(tg, key=lambda q: abs(q - p)) + (1 if up else -1)
                            if ok(q):
                                p = int(np.clip(q, lo, hi))
                    else:
                        sc = [q for q in range(lo, hi + 1) if q % 12 in ch.scale and ok(q)]
                        if sc:
                            idx = min(range(len(sc)), key=lambda m: abs(sc[m] - p))
                            step = int(rng.choice([1, 1, 1, 2]))
                            idx = idx + step if up else idx - step
                            p = sc[int(np.clip(idx, 0, len(sc) - 1))]
            v = vel + rng.integers(-6, 6) + (6 if abs(nb % 1 - 0.5) < 1e-6 and swing else 0)
            if k == peak:
                v += 6
            ev.add(sec, beat, inst, p, v, pan + rng.integers(-4, 5), min(d, total - beat) * 0.9)
    return ev


# ================================================================== the three songs

DAY_A = ['Fmaj9', 'Em7b5 A7b9', 'Dm9', 'Cm9 F13', 'Bbmaj9', 'Bbm6 Eb9', 'Am7 D7b9', 'Gm9 C13']
DAY_B = ['Bbm9', 'Eb13', 'Abmaj9', 'Dbmaj7#11', 'Gm9', 'C13', 'Am7 D7b9', 'Gm9 C7b9']
DAY_INTRO = ['Gm9', 'C13', 'Am7 D7b9', 'Gm9 C7b9']
DAY_INTER = ['Bbmaj9', 'Bbm6 Eb9', 'Am7 D7b9', 'Gm9 C13']
DAY_TAG = ['Gm9 C7b9', 'Fmaj9']

DAY_MEL_A1 = ['r/8 A4/8 C5/8 G5/4. E5/8 F5/8', 'E5/4. D5/8 C#5/4 Bb4/4', 'A4/4 r/8 D5/8 F5/8 E5/8 C5/4',
              'Eb5/4. D5/8 D5/8 Eb5/8 C5/4', 'D5/2 r/8 C5/8 D5/8 F5/8', 'Db5/4. C5/8 Db5/8 F5/8 G5/4',
              'E5/4. C5/8 F#5/4 Eb5/4', 'D5/2 r/8 E5/8 A5/8 G5/8']
DAY_MEL_A2 = ['r/8 A4/8 C5/8 G5/4. E5/8 F5/8', 'E5/4. D5/8 C#5/4 Bb4/4', 'A4/4 r/8 D5/8 F5/8 E5/8 C5/4',
              'Eb5/4. D5/8 D5/8 Eb5/8 C5/4', 'D5/2 r/8 C5/8 D5/8 F5/8', 'Db5/4. C5/8 Db5/8 F5/8 G5/4',
              'C5/4 A4/8 F#4/8 A4/8 C5/8 Eb5/8 F#5/8', 'G5/4 F5/8 D5/8~D5/4 r/8 A4/8']
DAY_MEL_B = ['F5/4. Eb5/8 Db5/8 C5/8 Bb4/4', 'C5/2. r/8 Bb4/8', 'Bb4/8 C5/8 Eb5/8 G5/8~G5/2',
             'G5/8 F5/8 Eb5/8 C5/8~C5/2', 'D5/4. F5/8 A5/4 G5/4', 'E5/2. r/4', 'C5/4. A4/8 Eb5/4 D5/4',
             'Bb4/4. A4/8 G4/4 E4/4']
DAY_MEL_A3 = DAY_MEL_A1[:6] + ['E5/4. C5/8 F#5/4 Eb5/4', 'D5/4 C5/8 A4/8~A4/4 r/8 A4/8']

NIGHT_A = ['Dbmaj9', 'Bb7b13', 'Ebm9', 'Ab13', 'Fm7 Edim7', 'Ebm9 Ab7b9', 'Dbmaj7 Bbm7', 'Ebm7 Ab7']
NIGHT_B = ['Abm9 Db7b9', 'Gbmaj9', 'Gbm9 B9', 'Fm7 Bb7b9', 'Ebm9', 'Ab13', 'Fm7 Bb7', 'Ebm9 Ab7b9']
NIGHT_INTRO = ['Ebm9', 'Ab13sus Ab7b9']
NIGHT_TAG = ['Ebm9 Ab7b9', 'Dbmaj9']
NIGHT_MEL_A1 = ['r/8 F4/8 Ab4/8 Eb5/8~Eb5/2', 'D5/4. C5/8 Bb4/4 Ab4/4', 'Gb4/2. F4/8 Gb4/8', 'F4/2 r/4 Eb4/8 F4/8',
                'Ab4/4. C5/8 Db5/4 Bb4/4', 'Bb4/4. Gb4/8 A4/4 C5/4', 'Db5/2 r/8 Db5/8 F5/8 Db5/8',
                'Eb5/4. Db5/8 C5/4 r/4']
NIGHT_MEL_A2 = NIGHT_MEL_A1[:6] + ['Db5/2 C5/8 Bb4/8 Ab4/8 F4/8', 'Gb4/4. F4/8 Eb4/4 r/4']
NIGHT_MEL_B = ['Eb5/4. B4/8 D5/4 F5/4', 'F5/2. Db5/8 Bb4/8', 'A4/4. Ab4/8 Eb5/4 Db5/4', 'C5/4. Ab4/8 B4/4 D5/4',
               'Gb5/2. F5/8 Eb5/8', 'F5/2 Eb5/8 C5/8 Bb4/4', 'Ab4/4. C5/8 D5/4 Ab4/4', 'Gb4/2 r/4 Eb4/4']
NIGHT_MEL_A3 = NIGHT_MEL_A1[:6] + ['Db5/2 C5/8 Bb4/8 Ab4/8 F4/8', 'Eb4/2 r/2']

TITLE_A = ['Fmaj9', 'Dm9', 'Gm9', 'C13', 'Fmaj9', 'Abmaj9', 'Gm9', 'C7sus4 C13']
TITLE_INTRO = ['C7sus4']
TITLE_TAG = ['Fmaj9']
TITLE_MEL = ['r/8 A4/8 C5/8 G5/8~G5/4 E5/8 F5/8', 'E5/4 D5/8 C5/8~C5/2', 'r/8 Bb4/8 D5/8 A5/8~A5/4 F5/8 G5/8',
             'A5/4 G5/8 E5/8~E5/2', 'r/8 A4/8 C5/8 G5/8~G5/4 A5/8 C6/8', 'Bb5/4 G5/8 Eb5/8~Eb5/2',
             'D5/4. F5/8 A5/4 G5/4', 'F5/2 E5/4 r/4']
TITLE_MEL2 = ['r/8 A5/8 G5/8 E5/8~E5/4 C5/8 D5/8', 'E5/4 F5/8 A5/8~A5/2', 'r/8 G5/8 F5/8 D5/8~D5/4 Bb4/8 A4/8',
              'G4/4 A4/8 E5/8~E5/2', 'r/8 A4/8 C5/8 G5/8~G5/4 A5/8 C6/8', 'Bb5/4 C6/8 G5/8~G5/2',
              'A5/4. G5/8 F5/4 D5/4', 'F5/2 G5/4 r/4']


def day_song():
    S = Song('day', 28)
    rng = np.random.default_rng(1001)
    intro = Section(S, 'intro', DAY_INTRO)
    A1, A2, B, A3 = (Section(S, n, c) for n, c in (('A1', DAY_A), ('A2', DAY_A), ('B', DAY_B), ('A3', DAY_A)))
    As = Section(S, 'As', DAY_A)
    Bs = Section(S, 'Bs', DAY_B)
    Abrk = Section(S, 'Abrk', DAY_A)
    inter = Section(S, 'inter', DAY_INTER)
    tag = Section(S, 'tag', DAY_TAG)

    # drums do not depend on the chords: one set for every 8-bar section
    d_std = drums_bossa(A1, 0, rng, bars=2)
    d_fill = drums_bossa(A1, 1, rng)
    d_soft = drums_bossa(A1, 2, rng, bars=2)
    d_light = drums_bossa(A1, 0, rng, light=True, bars=2)
    drums = [d_std, d_fill, d_soft]

    def harmony(sec):
        g = [comp_guitar(sec, v, rng)[0] for v in (0, 1, 2)]
        b = [bass_bossa(sec, v, rng)[0] for v in (0, 1)]
        r = [pads(sec, 'rhodes', 3, 58, 77, 54, 64, 'whole')[0], pads(sec, 'rhodes', 3, 60, 79, 48, 64, 'stabs')[0], Ev()]
        return g, b, r

    gA, bA, rA = harmony(A1)
    gB, bB, rB = harmony(B)
    for sec, mel in ((A1, DAY_MEL_A1), (A2, DAY_MEL_A2), (A3, DAY_MEL_A3), (B, DAY_MEL_B)):
        m = parse_mel(mel)
        check_melody(sec, m, sec.name)
        m2 = anticipate(sec, m)
        g, b, r = (gB, bB, rB) if sec is B else (gA, bA, rA)
        # the head keeps the Rhodes quiet (stabs or nothing) so the vibes sing
        sec.parts = {'gtr': g, 'bass': b, 'drums': drums, 'rh': r[1:],
                     'mel': [melody_events(sec, m, 'vibes', 92, 84, rng),
                             melody_events(sec, m2, 'vibes', 88, 84, rng)]}
    # solos over A and B: vibes and Rhodes take turns
    for sec, (g, b, r) in ((As, (gA, bA, rA)), (Bs, (gB, bB, rB))):
        sol = [solo_line(sec, 'vibes', 65, 86, rng, 86, 84, density=0.85, motif=[4, 7, 14] if k == 0 else None)
               for k in range(4)]
        sol += [solo_line(sec, 'rhodes', 62, 79, rng, 92, 64, density=0.8) for k in range(2)]
        sec.parts = {'gtr': g, 'bass': b, 'drums': drums, 'rh': r, 'mel': sol}
    # breakdown: no kick or rim, the Rhodes plays the tune softly, guitar sparse
    m = parse_mel(DAY_MEL_A2)
    Abrk.parts = {'gtr': [comp_guitar(Abrk, 3, rng)[0], gA[0]], 'bass': bA[:1], 'drums': [d_light], 'rh': [Ev()],
                  'mel': [melody_events(Abrk, m, 'rhodes', 88, 64, rng), melody_events(Abrk, m, 'vibes', 80, 84, rng)]}
    # intro: guitar first, the band joins in bar 3
    bev = bass_bossa(intro, 0, rng)[0]
    bev.ev = [e for e in bev.ev if e[0] >= 2 * S.bar]
    dev = drums_bossa(intro, 0, rng, light=True)
    dev.ev = [e for e in dev.ev if e[0] >= 2 * S.bar]
    mev = Ev()
    for b, p in ((14, 69), (14.5, 72), (15, 79)):                       # the motif as a pickup
        mev.add(intro, b, 'vibes', p, 70, 84, 0.45 if b < 15 else 0.9)
    intro.parts = {'gtr': [comp_guitar(intro, 1, rng)[0]], 'bass': [bev], 'drums': [dev],
                   'rh': [pads(intro, 'rhodes', 3, 53, 72, 46)[0]], 'mel': [mev]}
    inter.parts = {'gtr': [comp_guitar(inter, 1, rng)[0]], 'bass': [bass_bossa(inter, 1, rng)[0]],
                   'drums': [drums_bossa(inter, 2, rng, bars=2)], 'rh': [pads(inter, 'rhodes', 3, 53, 72, 52)[0]],
                   'mel': [Ev()]}
    # tag: a ii-V and a ringing tonic chord, the motif on top
    gv = comp_guitar(tag, 3, rng)[0]
    gv.ev = [e for e in gv.ev if e[0] < S.bar]
    for p in [57, 64, 67, 72]:
        gv.add(tag, 4, 'guitar', p, 74, 40, 0)
    bev = Ev()
    bev.add(tag, 0, 'bass', 43, 90, 64, 1.8)
    bev.add(tag, 2, 'bass', 36, 86, 64, 1.8)
    bev.add(tag, 4, 'bass', 41, 92, 64, 0)
    mev = Ev()
    for b, p, d in ((4.5, 69, 0.45), (5, 72, 0.45), (5.5, 79, 2.4)):
        mev.add(tag, b, 'vibes', p, 74, 84, d)
    dev = Ev()
    dev.add(tag, 3.5, 'kit', TAP, 50, 60)
    dev.add(tag, 4, 'kit', SWEEP, 46, 64)
    dev.add(tag, 4, 'kit', KICK, 50, 64)
    tag.parts = {'gtr': [gv], 'bass': [bev], 'drums': [dev], 'rh': [pads(tag, 'rhodes', 3, 53, 72, 46)[0]],
                 'mel': [mev]}
    S.form = [intro, A1, A2, B, A3, As, As, Bs, As, Abrk, B, A3, inter]
    S.loop_to = 1
    S.ending = tag
    return S


def night_song():
    S = Song('night', 42, swing=True)
    rng = np.random.default_rng(2002)
    S.gain = 90
    intro = Section(S, 'intro', NIGHT_INTRO)
    A1, A2, B, A3 = (Section(S, n, c) for n, c in (('A1', NIGHT_A), ('A2', NIGHT_A), ('B', NIGHT_B), ('A3', NIGHT_A)))
    Ap, Bp, At, Bt = (Section(S, n, c) for n, c in (('Ap', NIGHT_A), ('Bp', NIGHT_B), ('At', NIGHT_A), ('Bt', NIGHT_B)))
    tag = Section(S, 'tag', NIGHT_TAG)

    brush = [drums_ballad(A1, 0, rng, bars=2), drums_ballad(A1, 1, rng)]
    ride = [drums_ballad(A1, 0, rng, ride=True, bars=2), drums_ballad(A1, 1, rng, ride=True)]

    def piano_comp(sec, styles=('ballad', 'charleston', 'ballad')):
        return [pads(sec, 'piano', 4, 51, 71, 58 if st == 'ballad' else 54, 54, st, rng=rng)[0] for st in styles]

    pA, pB = piano_comp(A1), piano_comp(B)
    wA = [bass_walk(A1, rng)[0] for _ in range(3)]
    wB = [bass_walk(B, rng)[0] for _ in range(3)]
    twoA = [bass_walk(A1, rng, two_feel=True)[0] for _ in range(2)]
    tp_notes = set()
    for sec, mel, two in ((A1, NIGHT_MEL_A1, True), (A2, NIGHT_MEL_A2, False), (B, NIGHT_MEL_B, False),
                          (A3, NIGHT_MEL_A3, False)):
        m = parse_mel(mel)
        check_melody(sec, m, 'night ' + sec.name)
        tp_notes |= {p for b, p, d in m}
        lead = [melody_events(sec, m, 'trumpet', 96, 70, rng, legato=0.95, accent_off=True)]
        # a variant that anticipates the long notes on 1 and 3 by an 8th
        m2 = anticipate(sec, m)
        lead.append(melody_events(sec, m2, 'trumpet', 94, 70, rng, legato=0.95, accent_off=True))
        sec.parts = {'pno': pB if sec is B else pA, 'bass': twoA if two else (wB if sec is B else wA),
                     'drums': brush, 'lead': lead}
    for sec in (Ap, Bp):           # piano solo, trumpet lays out
        sol = [solo_line(sec, 'piano', 63, 84, rng, 74, 76, swing=True, density=0.85,
                         motif=[4, 7, 14] if k == 0 else None) for k in range(4)]
        sec.parts = {'pno': (pB if sec is Bp else pA)[:2], 'bass': wB if sec is Bp else wA, 'drums': ride, 'lead': sol}
    for sec in (At, Bt):           # trumpet solo, on the notes the tune uses
        sol = [solo_line(sec, 'trumpet', 60, 78, rng, 92, 70, swing=True, density=0.75, allowed=tp_notes)
               for _ in range(4)]
        sec.parts = {'pno': pB if sec is Bt else pA, 'bass': wB if sec is Bt else wA, 'drums': [ride[0], brush[1]],
                     'lead': sol}
    # intro: piano alone, then a pickup from the bass
    iev = pads(intro, 'piano', 4, 51, 71, 56, 54, 'ballad', rng=rng)[0]
    rh = Ev()
    for b, p, d in ((0.5, 77, 0.5), (1, 75, 0.5), (1.5, 72, 1.5), (4.5, 80, 0.5), (5, 77, 0.5), (5.5, 75, 1.0)):
        rh.add(intro, b, 'piano', p, 56, 74, d)
    bev = Ev()
    bev.add(intro, 6, 'bass', 44, 80, 64, 0.9)
    bev.add(intro, 7, 'bass', 43, 80, 64, 0.9)
    dv = Ev()
    for b in (4, 6):
        dv.add(intro, b, 'kit', SWEEP, 40, 60)
    intro.parts = {'pno': [iev], 'bass': [bev], 'drums': [dv], 'lead': [rh]}
    # tag
    tev = pads(tag, 'piano', 4, 51, 71, 56, 54, 'whole')[0]
    lev = Ev()
    for b, p, d in ((0.5, 65, 0.5), (1, 68, 0.5), (1.5, 75, 2.0), (4.5, 65, 0.5), (5, 68, 0.5), (5.5, 75, 2.3)):
        lev.add(tag, b, 'trumpet', p, 84, 70, d)
    bev = Ev()
    bev.add(tag, 0, 'bass', 39, 86, 64, 1.8)
    bev.add(tag, 2, 'bass', 44, 84, 64, 1.8)
    bev.add(tag, 4, 'bass', 37, 88, 64, 0)
    dv = Ev()
    for b in (0, 2, 4):
        dv.add(tag, b, 'kit', SWEEP, 42, 60)
    dv.add(tag, 4, 'kit', RIDE, 46, 92)
    tag.parts = {'pno': [tev], 'bass': [bev], 'drums': [dv], 'lead': [lev]}
    S.form = [intro, A1, A2, B, A3, Ap, Ap, Bp, Ap, At, Bt, A3]
    S.loop_to = 1
    S.ending = tag
    return S


def title_song():
    S = Song('title', 24)
    rng = np.random.default_rng(3003)
    S.gain = 80
    intro = Section(S, 'intro', TITLE_INTRO)
    T1 = Section(S, 'T1', TITLE_A)
    T2 = Section(S, 'T2', TITLE_A)
    tag = Section(S, 'tag', TITLE_TAG)
    m1, m2 = parse_mel(TITLE_MEL), parse_mel(TITLE_MEL2)
    check_melody(T1, m1, 'title 1')
    check_melody(T2, m2, 'title 2')
    g = [comp_guitar(T1, v, rng, vel=74)[0] for v in (1, 2)]
    b = [bass_bossa(T1, v, rng)[0] for v in (0, 1)]
    d = [drums_bossa(T1, 0, rng, bars=2), drums_bossa(T1, 1, rng)]
    rh = [pads(T1, 'rhodes', 3, 53, 72, 50, 64, 'stabs')[0], pads(T1, 'rhodes', 3, 53, 72, 50, 64, 'whole')[0]]
    T1.parts = {'gtr': g, 'bass': b, 'drums': d, 'rh': rh, 'mel': [melody_events(T1, m1, 'vibes', 96, 84, rng)]}
    T2.parts = {'gtr': g, 'bass': b, 'drums': d, 'rh': rh[:1],
                'mel': [melody_events(T2, m2, 'rhodes', 92, 64, rng), melody_events(T2, m2, 'vibes', 88, 84, rng)]}
    bell = Ev()
    bell.add(intro, 0, 'bell', 96, 100, 64, 0)
    gi = Ev()
    for p in (58, 65, 70, 74):
        gi.add(intro, 0, 'rhodes', p, 60, 64, 2.6)
    di = Ev()
    for k, bt in enumerate((2, 2.5, 3, 3.25, 3.5, 3.75)):
        di.add(intro, bt, 'kit', TAP if k % 2 else RIM, 50 + 6 * k, 60 + 4 * k)
    bi = Ev()
    bi.add(intro, 3.5, 'bass', 36, 84, 64, 0.4)
    intro.parts = {'gtr': [gi], 'bass': [bi], 'drums': [di], 'rh': [Ev()], 'mel': [bell]}
    tev = Ev()
    for p in (57, 64, 67, 72):
        tev.add(tag, 0, 'rhodes', p, 64, 64, 0)
    mt = Ev()
    for bb, p, dd in ((0, 69, 0.4), (0.5, 72, 0.4), (1, 79, 2.5)):
        mt.add(tag, bb, 'vibes', p, 80, 84, dd)
    bt = Ev()
    bt.add(tag, 0, 'bass', 41, 92, 64, 0)
    dt = Ev()
    dt.add(tag, 0, 'kit', KICK, 60, 64)
    dt.add(tag, 0, 'kit', SWEEP, 50, 64)
    tag.parts = {'gtr': [tev], 'bass': [bt], 'drums': [dt], 'rh': [Ev()], 'mel': [mt]}
    S.form = [intro, T1, T2]
    S.loop_to = 1
    S.ending = tag
    S.exit_bars = True
    return S


PART_ORDER = {'day': ['bass', 'drums', 'gtr', 'rh', 'mel'], 'night': ['bass', 'drums', 'pno', 'lead'],
              'title': ['bass', 'drums', 'gtr', 'rh', 'mel']}


# ================================================================== sound effects

SR2 = SR // 2          # storage rate of noise-like sounds (played at pitch 0.5)


def tone(f, n, sr=SR, ph=0.0):
    return np.sin(2 * np.pi * f * np.arange(n) / sr + ph)


def chirp(f0, f1, n, sr=SR, curve=1.0):
    k = (np.arange(n) / max(1, n - 1)) ** curve
    f = f0 + (f1 - f0) * k
    return np.sin(2 * np.pi * np.cumsum(f) / sr)


def ring(partials, attack_s, loop_s, noises=(), att_ms=1.0, sr=SR, seed=0, extra=None):
    """Bells and chimes: partials (freq, amp, tau, persist, start_s). Persisting partials are
    snapped to the loop's grid and hold their level in it (the engine continues the decay);
    the rest, and the noises (start_s, array), are faded out before the loop. Returns (x, ls)."""
    L = int(round(loop_s * sr / 28)) * 28
    ls = int(math.ceil(attack_s * sr / 28)) * 28
    n = ls + L
    t = np.arange(n) / sr
    w = np.clip((ls - 40 - np.arange(n)) / (0.04 * sr), 0, 1)
    rng = rng_for('ring', seed)
    x = np.zeros(n)
    for p in partials:
        f, amp, tau, persist = p[:4]
        st = p[4] if len(p) > 4 else 0.0
        if f > 0.45 * sr:
            continue
        tt = np.maximum(t - st, 0)
        on = (t >= st) * raised(n, 1)
        if persist:
            f = snap(f, L, sr)
            env = amp * np.exp(-np.minimum(tt, (ls / sr) - st) / tau)
        else:
            env = amp * np.exp(-tt / tau) * w
        a = raised(n - int(st * sr), int(att_ms * sr / 1000))
        e2 = np.zeros(n)
        e2[int(st * sr):] = a
        x += env * on * e2 * np.sin(2 * np.pi * f * tt + rng.uniform(0, 6.28))
    for st, nz in noises:
        s0 = int(st * sr)
        m = min(len(nz), n - s0)
        x[s0:s0 + m] += nz[:m] * w[s0:s0 + m]
    return x, ls


def vibe_partials(f, amp, st, tau=1.5, persist=True):
    return [(f, amp, tau, persist, st), (4 * f, amp * 0.22, 0.4, persist, st), (10 * f, amp * 0.05, 0.05, False, st)]


def mallet(st, n=0.03, amp=0.04, seed=0, band=(800, 4000)):
    m = int(n * SR)
    return (st, butter(noise(m, ('mal', seed)), 'band', band) * env_exp(m, 0.003) * amp)


F5, BB5, C6, F6, BB6, C7, F7 = (mtof(m) for m in (77, 82, 84, 89, 94, 96, 101))


def sfx_click():
    n = int(0.035 * SR)
    x = butter(noise(n, 'click'), 'high', 3000) * env_exp(n, 0.0015) * 0.6
    x += tone(2600, n) * env_exp(n, 0.004) * 0.5
    return fade_out(x, 100), None, 1


def sfx_select():
    n = int(0.12 * SR)
    f = F6 * (1 + 0.04 * np.exp(-np.arange(n) / (0.01 * SR)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.18 * np.sin(2 * ph)) * env_exp(n, 0.035, att=0.002)
    return fade_out(x, 300), None, 1


def sfx_back():
    n = int(0.17 * SR)
    x = np.zeros(n)
    for st, f, a in ((0, C6, 0.8), (0.055, F5, 1.0)):
        m = n - int(st * SR)
        put(x, st * SR, (tone(f, m) + 0.15 * tone(2 * f, m)) * env_exp(m, 0.035, att=0.002) * a)
    return fade_out(x, 300), None, 1


def sfx_error():
    sr = SR2
    n = int(0.36 * sr)
    x = np.zeros(n)
    for st in (0.0, 0.16):
        m = int(0.12 * sr)
        tt = np.arange(m) / sr
        b = sum(np.sign(np.sin(2 * np.pi * f * tt)) for f in (155.0, 163.0)) * 0.5
        b = butter(b, 'low', 1400, sr) * raised(m, int(0.004 * sr)) * fade_out(np.ones(m), int(0.02 * sr))
        put(x, st * sr, b)
    return x, None, 2


def sfx_place():
    n = int(0.22 * SR)
    burst = noise(n, 'place') * env_exp(n, 0.002)
    x = reson(burst, 210, 7) * 1.0 + reson(burst, 640, 10) * 0.5 + reson(burst, 1500, 12) * 0.15
    x += butter(noise(n, 'place2'), 'high', 2500) * env_exp(n, 0.0015) * 0.2
    m = int(0.12 * SR)                                          # the object settles
    s2 = noise(m, 'place3') * env_exp(m, 0.003)
    put(x, 0.045 * SR, (reson(s2, 260, 5) + reson(s2, 900, 8) * 0.3) * 0.35 * np.max(np.abs(x)) / 3)
    x = np.tanh(3 * x / np.max(np.abs(x)))
    return fade_out(x, 400), None, 1


def sfx_demolish():
    sr = SR2
    n = int(0.75 * sr)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * np.cumsum(60 + 70 * np.exp(-t / 0.03)) / sr) * env_exp(n, 0.12, sr) * 0.9
    rng = rng_for('demo')
    for k in range(70):
        st = rng.exponential(0.12)
        if st > 0.6:
            continue
        m = int(rng.uniform(0.01, 0.04) * sr)
        g = butter(rng.standard_normal(m), 'band', (rng.uniform(300, 900), rng.uniform(1500, 4500)), sr)
        put(x, st * sr, g * env_exp(m, m / sr / 4, sr) * rng.uniform(0.2, 0.7) * math.exp(-st / 0.25))
    for k in range(14):
        st = rng.uniform(0.15, 0.65)
        m = int(0.05 * sr)
        put(x, st * sr, tone(rng.uniform(1500, 4200), m, sr) * env_exp(m, 0.012, sr) * 0.15)
    return fade_out(x, int(0.05 * sr)), None, 2


def sfx_build():
    sr = SR2
    n = int(1.32 * sr)
    x = np.zeros(n)
    for k, st in enumerate((0.0, 0.12, 0.24)):                  # hammer
        m = int(0.12 * sr)
        b = noise(m, ('ham', k)) * env_exp(m, 0.0015, sr)
        h = reson(b, 1150, 18, sr) + reson(b, 2700, 20, sr) * 0.6 + reson(b, 140, 4, sr) * 0.8
        put(x, st * sr, h * (0.9 + 0.1 * k))
    m = int(0.34 * sr)                                          # saw
    tt = np.arange(m) / sr
    strokes = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 8.5 * tt))) * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 8.5 * tt)))
    saw = butter(noise(m, 'saw'), 'band', (900, 3800), sr) * strokes * raised(m, 200)
    put(x, 0.36 * sr, fade_out(saw * 0.55, 300))
    m = int(0.26 * sr)                                          # drill
    tt = np.arange(m) / sr
    f = 260 + 140 * np.clip(tt / 0.08, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / sr
    dr = sum(np.sin(k * ph) / k for k in range(1, 12))
    dr = butter(dr, 'low', 2500, sr) * raised(m, 200) * (1 + 0.3 * np.sin(2 * np.pi * 31 * tt))
    put(x, 0.72 * sr, fade_out(dr * 0.35, 400))
    m = int(0.34 * sr)                                          # ta-da sparkle
    sp = np.zeros(m)
    for k, (st, f, a) in enumerate(((0, F5, 0.5), (0.05, C6, 0.45), (0.1, F6, 0.4))):
        mm = m - int(st * sr)
        sp[int(st * sr):] += (tone(f, mm, sr) + 0.2 * tone(4 * f, mm, sr) * np.exp(-np.arange(mm) / (0.05 * sr))) \
            * env_exp(mm, 0.2, sr) * a
    put(x, 0.98 * sr, fade_out(sp, 300))
    return x, None, 2


def sfx_money_in():
    n = int(0.6 * SR)
    x = np.zeros(n)
    for k, (st, f) in enumerate(((0.0, 2650.0), (0.075, 3150.0))):
        m = int(0.4 * SR)
        c = sum(a * tone(f * r, m, ph=k + r) * np.exp(-np.arange(m) / (tau * SR))
                for r, a, tau in ((1, 1.0, 0.12), (2.76, 0.5, 0.06), (5.1, 0.25, 0.03), (1.007, 0.6, 0.12)))
        c += butter(noise(m, ('coin', k)), 'high', 4000) * env_exp(m, 0.002) * 0.6
        put(x, st * SR, c * 0.5)
    for st, f in ((0.14, C6), (0.2, F6)):
        m = n - int(st * SR)
        put(x, st * SR, (tone(f, m) + 0.2 * tone(4 * f, m) * np.exp(-np.arange(m) / (0.04 * SR)))
            * env_exp(m, 0.14, att=0.002) * 0.4)
    return fade_out(x, 800), None, 1


def sfx_money_out():
    n = int(0.42 * SR)
    x = np.zeros(n)
    m = int(0.35 * SR)
    c = sum(a * tone(1850 * r, m) * np.exp(-np.arange(m) / (tau * SR))
            for r, a, tau in ((1, 1.0, 0.1), (2.76, 0.4, 0.05), (1.006, 0.5, 0.1)))
    c += butter(noise(m, 'coin3'), 'high', 3500) * env_exp(m, 0.002) * 0.5
    put(x, 0, c * 0.5)
    for st, f in ((0.09, F6), (0.15, C6)):
        mm = n - int(st * SR)
        put(x, st * SR, tone(f, mm) * env_exp(mm, 0.07, att=0.002) * 0.3)
    return fade_out(x, 600), None, 1


def sfx_star_gained():
    parts = []
    noises = []
    for k, (st, f) in enumerate(((0.0, F5), (0.075, C6), (0.15, F6))):
        parts += vibe_partials(f, 0.55, st, tau=0.18, persist=False)
        noises.append(mallet(st, seed=k))
    st = 0.24
    for k, (f, a) in enumerate(((F5, 0.5), (BB5, 0.45), (C6, 0.5), (F6, 0.55), (C7, 0.25))):
        parts += vibe_partials(f, a, st + 0.012 * k, tau=1.6)
        noises.append(mallet(st + 0.012 * k, seed=10 + k))
    for k in range(6):                                          # sparkles
        f = (F7, mtof(103), mtof(106), mtof(108))[k % 4]
        parts.append((f, 0.12, 0.08, False, 0.3 + 0.045 * k))
    x, ls = ring(parts, 0.62, 0.4, noises)
    n = len(x)
    i = np.arange(n)
    trem = 1 - 0.25 * (0.5 - 0.5 * np.cos(2 * np.pi * 5.0 * np.maximum(i - ls, 0) / SR)) * (i >= ls)
    trem = np.where(i >= ls, 1 - 0.25 * (0.5 - 0.5 * np.cos(2 * np.pi * 2 * (i - ls) / (n - ls))), 1.0)
    return x * trem, ls, 1


def sfx_star_lost():
    parts = []
    noises = []
    for k, (st, f) in enumerate(((0.0, C6), (0.13, BB5), (0.26, F5), (0.39, mtof(72)))):
        parts += vibe_partials(f, 0.5 - 0.05 * k, st, tau=0.2, persist=False)
        noises.append(mallet(st, seed=20 + k))
    st = 0.52
    for f, a in ((mtof(53), 0.6), (mtof(60), 0.4), (mtof(65), 0.2)):
        parts += [(f, a, 1.0, True, st), (2 * f, a * 0.25, 0.3, True, st), (3 * f, a * 0.08, 0.2, True, st)]
    noises.append((st, butter(noise(int(0.05 * SR), 'thud'), 'low', 300) * env_exp(int(0.05 * SR), 0.01) * 0.3))
    x, ls = ring(parts, 0.8, 0.3, noises)
    return x, ls, 1


def sfx_review():
    n = int(0.62 * SR)
    x = np.zeros(n)
    m = int(0.18 * SR)
    wh = butter(noise(m, 'paper'), 'band', (1500, 6000)) * np.sin(np.pi * np.arange(m) / m) ** 2
    put(x, 0, wh * 0.35)
    m = int(0.03 * SR)
    put(x, 0.15 * SR, chirp(500, 1100, m) * env_exp(m, 0.008) * 0.6)
    for st, f in ((0.19, BB5), (0.27, F6)):
        mm = n - int(st * SR)
        put(x, st * SR, (tone(f, mm) + 0.2 * tone(4 * f, mm) * np.exp(-np.arange(mm) / (0.05 * SR)))
            * env_exp(mm, 0.13, att=0.002) * 0.45)
    return fade_out(x, 800), None, 1


def sfx_notify():
    parts = []
    noises = []
    for k, (st, f) in enumerate(((0.0, C6), (0.11, F6))):
        persist = k == 1
        parts += [(f, 0.6, 0.35 if persist else 0.12, persist, st), (3.9 * f, 0.18, 0.03, False, st),
                  (2 * f, 0.08, 0.2, persist, st)]
        noises.append(mallet(st, amp=0.05, seed=30 + k, band=(1500, 6000)))
    return (*ring(parts, 0.3, 0.12, noises), 1)


def sfx_desk_bell():
    f = C7
    L_s = 0.25
    parts = [(f, 1.0, 1.4, True), (f + 4.0, 0.45, 1.4, True), (2.76 * f, 0.4, 0.5, True), (2.76 * f + 4, 0.2, 0.5, True),
             (5.4 * f, 0.2, 0.15, False)]
    m = int(0.02 * SR)
    noises = [(0, butter(noise(m, 'bell'), 'high', 4000) * env_exp(m, 0.0015) * 0.8)]
    x, ls = ring(parts, 0.15, L_s, noises)
    return x, ls, 1


def sfx_elevator_ding():
    f = C6
    parts = [(f, 1.0, 1.8, True), (f + 3.0, 0.35, 1.8, True), (2 * f, 0.15, 0.8, True), (3 * f, 0.05, 0.4, True),
             (2.76 * f, 0.12, 0.15, False)]
    noises = [mallet(0, amp=0.04, seed=40, band=(1000, 5000))]
    return (*ring(parts, 0.12, 1 / 3, noises), 1)


def sfx_elevator_doors():
    sr = SR2
    n = int(1.5 * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    m = int(0.02 * sr)
    put(x, 0, reson(noise(m, 'relay') * env_exp(m, 0.002, sr), 2200, 15, sr) * 0.5)
    e = np.clip((t - 0.05) / 0.15, 0, 1) * np.clip((1.3 - t) / 0.2, 0, 1)
    f = 118 + 10 * np.clip((t - 0.05) / 0.3, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / sr
    whine = sum(np.sin(k * ph) * a for k, a in ((1, 0.5), (2, 0.35), (3, 0.2), (5, 0.08), (7, 0.05)))
    x += whine * e * 0.35
    x += butter(noise(n, 'slide'), 'low', 350, sr) * e * 0.8
    x += butter(noise(n, 'slide2'), 'band', (1500, 4000), sr) * e * 0.04
    m = int(0.25 * sr)
    tt = np.arange(m) / sr
    clunk = np.sin(2 * np.pi * np.cumsum(85 + 40 * np.exp(-tt / 0.02)) / sr) * env_exp(m, 0.05, sr)
    clunk += reson(noise(m, 'clunk') * env_exp(m, 0.003, sr), 900, 6, sr) * 0.4
    put(x, 1.28 * sr, clunk)
    return fade_out(x, int(0.03 * sr)), None, 2


def latch(seed, sr=SR2, amp=1.0):
    m = int(0.04 * sr)
    b = noise(m, ('latch', seed)) * env_exp(m, 0.0015, sr)
    return (reson(b, 2100, 14, sr) + reson(b, 3300, 16, sr) * 0.6 + reson(b, 700, 5, sr) * 0.3) * amp


def sfx_door_open():
    sr = SR2
    n = int(0.5 * sr)
    x = np.zeros(n)
    put(x, 0, latch(1, sr, 0.8))
    put(x, 0.06 * sr, latch(2, sr, 0.6))
    m = int(0.3 * sr)
    tt = np.arange(m) / sr
    cr = chirp(620, 760, m, sr) * (0.6 + 0.4 * butter(noise(m, 'creak'), 'low', 40, sr) / 3) * \
        np.sin(np.pi * tt / tt[-1]) ** 2
    put(x, 0.1 * sr, cr * 0.08)
    m = int(0.35 * sr)
    wh = butter(noise(m, 'whoosh'), 'low', 500, sr) * np.sin(np.pi * np.arange(m) / m) ** 2
    put(x, 0.1 * sr, wh * 0.45)
    return fade_out(x, 200), None, 2


def sfx_door_close():
    sr = SR2
    n = int(0.55 * sr)
    x = np.zeros(n)
    m = int(0.18 * sr)
    put(x, 0, butter(noise(m, 'wh2'), 'low', 600, sr) * np.sin(np.pi * np.arange(m) / m) ** 2 * 0.4)
    m = int(0.3 * sr)
    tt = np.arange(m) / sr
    thud = np.sin(2 * np.pi * np.cumsum(75 + 50 * np.exp(-tt / 0.015)) / sr) * env_exp(m, 0.07, sr)
    thud += reson(noise(m, 'thud2') * env_exp(m, 0.004, sr), 260, 4, sr) * 0.5
    put(x, 0.15 * sr, thud)
    put(x, 0.165 * sr, latch(3, sr, 0.7))
    return fade_out(x, 300), None, 2


def sfx_footstep(seed):
    sr = SR2
    n = int(0.16 * sr)
    x = np.zeros(n)
    m = int(0.07 * sr)
    put(x, 0, butter(noise(m, ('heel', seed)), 'low', 380, sr) * env_exp(m, 0.014, sr, att=0.003))
    put(x, 0.035 * sr, butter(noise(m, ('toe', seed)), 'low', 500, sr) * env_exp(m, 0.012, sr, att=0.003) * 0.55)
    put(x, 0.01 * sr, butter(noise(m, ('scuff', seed)), 'band', (900, 3500), sr) * env_exp(m, 0.02, sr, att=0.01) * 0.05)
    return fade_out(x, 100), None, 2


def sfx_luggage():
    sr = SR2
    n = int(1.4 * sr)
    t = np.arange(n) / sr
    e = np.clip(t / 0.15, 0, 1) * np.clip((1.4 - t) / 0.3, 0, 1)
    x = butter(noise(n, 'roll'), 'low', 260, sr) * (0.7 + 0.3 * np.sin(2 * np.pi * 13 * t)) * e
    x += butter(noise(n, 'roll2'), 'band', (500, 1500), sr) * e * 0.08
    for k in range(int(1.25 / 0.17)):
        st = 0.06 + 0.17 * k
        m = int(0.03 * sr)
        c = reson(noise(m, ('joint', k)) * env_exp(m, 0.002, sr), 1300, 8, sr) * 0.35
        c += butter(noise(m, ('jt', k)), 'low', 200, sr) * env_exp(m, 0.008, sr) * 0.5
        put(x, st * sr, c * e[int(st * sr)])
    return fade_out(x, 300), None, 2


def sfx_phone():
    sr = SR2
    n = int(1.12 * sr)
    t = np.arange(n) / sr
    sel = (np.floor(t * 34) % 2).astype(bool)
    f = np.where(sel, 1210.0, 1460.0)
    ph = 2 * np.pi * np.cumsum(f) / sr
    w = np.tanh(3 * np.sin(ph))
    gate = ((t < 0.42) | ((t > 0.6) & (t < 1.02))).astype(float)
    gate = signal.lfilter([0.02], [1, -0.98], gate)
    x = butter(w * gate, 'band', (500, 3800), sr)
    return fade_out(x, 200), None, 2


def sfx_register():
    sr = SR2
    n = int(1.15 * sr)
    x = np.zeros(n)
    for k, st in enumerate((0.0, 0.08)):
        m = int(0.05 * sr)
        b = noise(m, ('key', k)) * env_exp(m, 0.002, sr)
        put(x, st * sr, reson(b, 1800, 10, sr) + reson(b, 820, 8, sr) * 0.6)
    m = int(0.7 * sr)
    tt = np.arange(m) / sr
    bell = sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / tau)
               for f, a, tau in ((2349.3, 1.0, 0.4), (2353.3, 0.5, 0.4), (4850, 0.15, 0.1)) if f < 5200)
    put(x, 0.16 * sr, bell * 0.55)
    m = int(0.32 * sr)
    tt = np.arange(m) / sr
    dr = butter(noise(m, 'drawer'), 'low', 400, sr) * np.clip(tt / 0.1, 0, 1) * 0.7
    put(x, 0.24 * sr, dr)
    m = int(0.2 * sr)
    tt = np.arange(m) / sr
    put(x, 0.55 * sr, np.sin(2 * np.pi * np.cumsum(90 + 60 * np.exp(-tt / 0.01)) / sr) * env_exp(m, 0.05, sr) * 0.8)
    rng = rng_for('coins')
    for k in range(9):
        st = 0.56 + rng.exponential(0.07)
        m = int(0.1 * sr)
        put(x, st * sr, tone(rng.uniform(2000, 4800), m, sr) * env_exp(m, 0.02, sr) * 0.12)
    return fade_out(x, 300), None, 2


def sfx_cart():
    sr = SR2
    n = int(1.45 * sr)
    t = np.arange(n) / sr
    e = np.clip(t / 0.2, 0, 1) * np.clip((1.45 - t) / 0.35, 0, 1)
    x = butter(noise(n, 'cart'), 'low', 220, sr) * e * 0.7
    rng = rng_for('dishes')
    for k in range(40):
        st = rng.uniform(0.05, 1.3)
        m = int(0.06 * sr)
        put(x, st * sr, tone(rng.uniform(1500, 4800), m, sr) * env_exp(m, 0.01, sr) * rng.uniform(0.05, 0.2) * e[int(st * sr)])
    for st in (0.3, 0.92):
        m = int(0.13 * sr)
        tt = np.arange(m) / sr
        sq = chirp(1750, 2100, m, sr) * (1 + 0.3 * np.sin(2 * np.pi * 40 * tt)) * np.sin(np.pi * tt / tt[-1]) * 0.07
        put(x, st * sr, sq)
    return fade_out(x, 300), None, 2


def sfx_splash():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    m = int(0.015 * SR)
    put(x, 0, noise(m, 'slap') * env_exp(m, 0.003) * 0.8)
    m = int(0.1 * SR)
    tt = np.arange(m) / SR
    put(x, 0, np.sin(2 * np.pi * np.cumsum(90 + 120 * np.exp(-tt / 0.02)) / SR) * env_exp(m, 0.04) * 0.6)
    sp = butter(noise(n, 'splash'), 'band', (400, 8500)) * raised(n, int(0.015 * SR)) * np.exp(-t / 0.22)
    x += sp * 0.6
    rng = rng_for('drops')
    for k in range(26):
        st = 0.12 + rng.exponential(0.2)
        if st > 0.85:
            continue
        m = int(0.02 * SR)
        f0 = rng.uniform(900, 2400)
        put(x, st * SR, chirp(f0, f0 * 1.6, m) * env_exp(m, 0.006) * 0.2 * math.exp(-st / 0.35))
    return fade_out(x, 1000), None, 1


def sfx_cork():
    n = int(0.65 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    m = int(0.06 * SR)
    tt = np.arange(m) / SR
    put(x, 0, np.sin(2 * np.pi * np.cumsum(380 + 220 * np.exp(-tt / 0.008)) / SR) * env_exp(m, 0.018) * 0.9)
    put(x, 0, butter(noise(m, 'pop'), 'high', 1500) * env_exp(m, 0.0015) * 0.7)
    rng = rng_for('fizz')
    fz = np.zeros(n)
    for k in range(260):
        st = 0.04 + rng.exponential(0.18)
        if st > 0.62:
            continue
        put(fz, st * SR, rng.standard_normal(12) * rng.uniform(0.2, 1.0))
    fz = butter(fz, 'high', 3000) * np.exp(-t / 0.3)
    x += fz * 0.6
    return fade_out(x, 800), None, 1


def sfx_tab():
    n = int(0.07 * SR)
    b = noise(n, 'tab') * env_exp(n, 0.0015)
    x = reson(b, 1250, 14) + reson(b, 2600, 16) * 0.5
    m = int(0.03 * SR)
    put(x, 0.022 * SR, (reson(noise(m, 'tab2') * env_exp(m, 0.0015), 1650, 14)) * 0.5)
    return fade_out(x, 150), None, 1


def sfx_modem():
    """A dial-up handshake: tone dialling, the answer tone with its phase flips, then the
    two modems' training warble and hiss."""
    sr = SR2
    n = int(2.05 * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    dtmf = [(697, 1209), (770, 1336), (852, 1477), (697, 1336), (941, 1336), (770, 1209)]
    for k, (a, b) in enumerate(dtmf):
        m = int(0.06 * sr)
        tt = np.arange(m) / sr
        put(x, (0.02 + k * 0.085) * sr,
            (np.sin(2 * np.pi * a * tt) + np.sin(2 * np.pi * b * tt)) * 0.35 * raised(m, 40) * fade_out(np.ones(m), 40))
    st, m = 0.6, int(0.42 * sr)
    tt = np.arange(m) / sr
    ph = 2 * np.pi * 2100 * tt + np.pi * (np.floor(tt / 0.15) % 2)
    put(x, st * sr, np.sin(ph) * 0.4 * raised(m, 60) * fade_out(np.ones(m), 60))
    st, m = 1.05, int(0.95 * sr)
    tt = np.arange(m) / sr
    sel = np.floor(tt * 24) % 2
    f = np.where(sel > 0, 1650.0, 980.0) * (1 + 0.15 * (tt > 0.35) * np.sin(2 * np.pi * 7 * tt))
    w = np.sin(2 * np.pi * np.cumsum(f) / sr) * 0.3
    w += butter(noise(m, 'modem'), 'band', (900, 3400), sr) * (tt > 0.45) * 0.22
    w += np.sin(2 * np.pi * np.cumsum(2400 - 1200 * (tt % 0.2) / 0.2) / sr) * 0.12 * (tt > 0.6)
    put(x, st * sr, w * raised(m, 80) * fade_out(np.ones(m), 300))
    x = butter(x, 'band', (300, 3600), sr)          # through the phone line
    return x, None, 2


def sfx_save():
    """A floppy drive seeks and writes, then a confirming three-note chime (F, Bb, C)."""
    sr = SR2
    n = int(1.0 * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    m = int(0.36 * sr)
    tt = np.arange(m) / sr
    steps = np.zeros(m)
    for k in range(14):
        put(steps, (0.02 + k * 0.022) * sr, noise(int(0.008 * sr), ('step', k)) * 0.8)
    steps = reson(steps, 700, 6, sr) + reson(steps, 1900, 8, sr) * 0.5
    motor = np.sin(2 * np.pi * 300 * tt) * 0.06 * raised(m, 100)
    put(x, 0, (steps + motor) * fade_out(np.ones(m), 200))
    for k, (st, f) in enumerate(((0.42, F5), (0.5, BB5), (0.58, C6))):
        mm = n - int(st * sr)
        put(x, st * sr, (np.sin(2 * np.pi * f * np.arange(mm) / sr) + 0.2 * np.sin(2 * np.pi * 4 * f * np.arange(mm) / sr)
                         * np.exp(-np.arange(mm) / (0.03 * sr))) * env_exp(mm, 0.18, sr, att=0.002) * 0.45)
    return fade_out(x, int(0.05 * sr)), None, 2


def sfx_hire():
    """A rubber stamp on the contract, then a little bell."""
    n = int(0.62 * SR)
    x = np.zeros(n)
    m = int(0.12 * SR)
    tt = np.arange(m) / SR
    put(x, 0, np.sin(2 * np.pi * np.cumsum(110 + 90 * np.exp(-tt / 0.01)) / SR) * env_exp(m, 0.035) * 0.9)
    put(x, 0, reson(noise(m, 'stamp') * env_exp(m, 0.003), 900, 4) * 0.5)
    put(x, 0.012 * SR, latch(7, SR, 0.25))
    m = n - int(0.13 * SR)
    tt = np.arange(m) / SR
    bell = sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt / tau)
               for f, a, tau in ((BB6, 1.0, 0.25), (BB6 + 3, 0.4, 0.25), (2.76 * BB6, 0.25, 0.08)) if f < 10500)
    put(x, 0.13 * SR, bell * raised(m, 20) * 0.45)
    return fade_out(x, 800), None, 1


def sfx_break():
    """Something gives out: a clank, a sproing and an electrical fizzle."""
    sr = SR2
    n = int(0.85 * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    m = int(0.25 * sr)
    tt = np.arange(m) / sr
    b = noise(m, 'brk') * env_exp(m, 0.003, sr)
    put(x, 0, reson(b, 520, 10, sr) + reson(b, 1370, 14, sr) * 0.6 + reson(b, 2900, 18, sr) * 0.3)
    m = int(0.5 * sr)
    tt = np.arange(m) / sr
    f = 420 * np.exp(-tt / 0.35) + 140 + 35 * np.sin(2 * np.pi * 18 * tt) * np.exp(-tt / 0.2)
    put(x, 0.05 * sr, np.sin(2 * np.pi * np.cumsum(f) / sr) * env_exp(m, 0.16, sr) * 0.45)
    rng = rng_for('fizzle')
    fz = np.zeros(n)
    for k in range(120):
        st = 0.15 + rng.exponential(0.15)
        if st > 0.8:
            continue
        put(fz, st * sr, rng.standard_normal(5) * rng.uniform(0.3, 1))
    x += butter(fz, 'high', 2000, sr) * 0.3
    return fade_out(x, int(0.04 * sr)), None, 2


# ================================================================== ambience

def murmur_bed():
    """Crowd chatter: a dozen pseudo-speech talkers (glottal pulses through vowel formants,
    syllables in phrases with pauses and a little sibilance), in a small room."""
    sr = SR2
    Lsec = 3.2
    n = int((Lsec + 0.6) * sr)
    vowels = [(730, 1090, 2440), (530, 1840, 2480), (270, 2290, 3010), (570, 840, 2410), (300, 870, 2240),
              (660, 1720, 2410), (490, 1350, 2500), (640, 1190, 2390)]
    rng = rng_for('murmur')
    out = np.zeros(n)
    for tk in range(13):
        male = tk % 2 == 0
        f0b = rng.uniform(95, 135) if male else rng.uniform(175, 235)
        dist = rng.uniform(0.3, 1.0)
        y = np.zeros(n)
        t = rng.uniform(-0.5, 0.3)
        while t < Lsec + 0.6:
            nsyl = int(rng.integers(3, 11))
            for s in range(nsyl):
                d = rng.uniform(0.11, 0.26)
                st = int(t * sr)
                m = int(d * sr)
                if st >= 0 and st + m < n:
                    tt = np.arange(m) / sr
                    f0 = f0b * (1 + 0.12 * rng.uniform(-1, 1)) * (1 - 0.15 * s / nsyl) * (1 + 0.04 * np.sin(np.pi * tt / d))
                    ph = 2 * np.pi * np.cumsum(f0) / sr
                    src = sum(np.sin(k * ph) / k ** 1.1 for k in range(1, int(3500 / f0b) + 1))
                    F = vowels[int(rng.integers(len(vowels)))]
                    sylb = sum(reson(src, fq * (1.15 if not male else 1.0), fq / bw, sr) * g
                               for fq, bw, g in zip(F, (90, 110, 160), (1.0, 0.6, 0.25)))
                    sylb *= np.sin(np.pi * np.arange(m) / m) ** 0.7
                    if rng.random() < 0.3:
                        cm = int(0.05 * sr)
                        sylb[:cm] += butter(rng.standard_normal(cm), 'band', (2500, 5000), sr) * \
                            np.sin(np.pi * np.arange(cm) / cm) * 0.15 * np.std(sylb)
                    y[st:st + m] += sylb
                t += d + rng.uniform(0.0, 0.05)
            t += rng.uniform(0.25, 1.1)
        y = butter(y, 'low', 3800 - 2200 * dist, sr) * (1.0 - 0.6 * dist)
        out += y / (np.std(y) + 1e-9)
    out = room(out, 0.7, 0.45, sr, 'mur', 3000)
    return loopify(out, int(Lsec * sr) // 28 * 28, int(0.5 * sr)) + (2,)


def sizzle_bed():
    sr = SR
    Lsec = 1.2
    n = int((Lsec + 0.3) * sr)
    rng = rng_for('sizzle')
    imp = np.zeros(n)
    k = rng.poisson(380 * n / sr)
    pos = rng.integers(0, n - 30, k)
    amps = rng.exponential(1.0, k) * rng.choice([-1, 1], k)
    np.add.at(imp, pos, amps)
    cr = butter(imp, 'high', 2200)
    cr = signal.lfilter([1], [1, -0.6], cr)
    hiss = butter(noise(n, 'hiss'), 'band', (3000, 9500)) * (0.8 + 0.2 * butter(noise(n, 'hm'), 'low', 3) * 8)
    x = cr / np.std(cr) + hiss * 0.5
    x = butter(x, 'high', 800)
    return loopify(x, int(Lsec * sr) // 28 * 28, int(0.25 * sr)) + (1,)


def hum_bed():
    sr = SR2
    L = 2 * sr // 28 * 28
    n = L + int(0.3 * sr)
    t = np.arange(n) / sr
    f = sr / L * round(100 * L / sr)
    x = sum(a * np.sin(2 * np.pi * k * f * t + k) for k, a in ((1, 0.5), (2, 0.25), (3, 0.12), (4, 0.06)))
    trem = 0.5 - 0.5 * np.cos(2 * np.pi * t * sr / L)          # one tumble per loop
    x += butter(noise(n, 'drum'), 'low', 220, sr) * (0.6 + 0.6 * trem) * 1.2
    x += butter(noise(n, 'water'), 'band', (300, 1200), sr) * (0.2 + 0.5 * trem ** 2) * 0.5
    return loopify(x, L, int(0.25 * sr)) + (2,)


def surf_bed():
    sr = SR2
    Lsec = 2.4
    n = int((Lsec + 0.5) * sr)
    t = np.arange(n) / sr
    x = butter(pink(n, 'surf'), 'low', 2200, sr) * (0.8 + 0.2 * np.sin(2 * np.pi * t / Lsec))
    x += butter(noise(n, 'surf2'), 'band', (1500, 4500), sr) * 0.12 * (0.7 + 0.3 * np.sin(2 * np.pi * t / Lsec + 1))
    return loopify(x, int(Lsec * sr) // 28 * 28, int(0.4 * sr)) + (2,)


def roomtone_bed():
    sr = SR2
    Lsec = 2.0
    n = int((Lsec + 0.3) * sr)
    t = np.arange(n) / sr
    x = butter(pink(n, 'hvac'), 'low', 650, sr)
    L = int(Lsec * sr) // 28 * 28
    f = sr / L * round(120 * L / sr)
    x += 0.15 * np.sin(2 * np.pi * f * t) + 0.05 * np.sin(2 * np.pi * 2 * f * t)
    return loopify(x, L, int(0.25 * sr)) + (2,)


def spr_clink(seed):
    n = int(0.22 * SR)
    rng = rng_for('clink', seed)
    x = np.zeros(n)
    for j in range(int(rng.integers(1, 3))):
        st = j * rng.uniform(0.04, 0.08)
        m = n - int(st * SR)
        f = rng.uniform(2400, 4200)
        c = sum(a * tone(f * r, m, ph=r) * np.exp(-np.arange(m) / (tau * SR))
                for r, a, tau in ((1, 1.0, 0.05), (1.73, 0.6, 0.035), (2.9, 0.4, 0.02)) if f * r < 10500)
        c += butter(noise(m, ('ck', seed, j)), 'high', 3500) * env_exp(m, 0.0015) * 0.5
        put(x, st * SR, c * (1 - 0.3 * j))
    return fade_out(x, 300), None, 1


def spr_glass():
    n = int(0.45 * SR)
    x = np.zeros(n)
    for j, (st, f) in enumerate(((0, 2350.0), (0.004, 2610.0))):
        m = n - int(st * SR)
        x[int(st * SR):] += sum(a * tone(f * r, m, ph=j + r) * np.exp(-np.arange(m) / (tau * SR))
                                for r, a, tau in ((1, 1.0, 0.18), (2.32, 0.4, 0.08), (4.1, 0.15, 0.04)) if f * r < 10500)
    x += butter(noise(n, 'gl'), 'high', 4000) * env_exp(n, 0.0015) * 0.4
    return fade_out(x, 600), None, 1


def spr_ice():
    n = int(0.3 * SR)
    x = np.zeros(n)
    rng = rng_for('ice')
    for k in range(9):
        st = rng.exponential(0.06)
        if st > 0.22:
            continue
        m = int(0.04 * SR)
        b = noise(m, ('ic', k)) * env_exp(m, 0.002)
        put(x, st * SR, (reson(b, rng.uniform(1800, 3500), 12) + reson(b, rng.uniform(4000, 6000), 14) * 0.5) * 0.6)
    return fade_out(x, 300), None, 1


def spr_pan():
    sr = SR2
    n = int(0.55 * sr)
    t = np.arange(n) / sr
    x = sum(a * np.sin(2 * np.pi * f * t + f) * np.exp(-t / tau)
            for f, a, tau in ((310, 1.0, 0.25), (742, 0.6, 0.15), (1390, 0.35, 0.1), (2170, 0.2, 0.06)))
    x += noise(n, 'pan') * env_exp(n, 0.003, sr) * 0.5
    return fade_out(x, 300), None, 2


def spr_chop():
    sr = SR2
    n = int(0.5 * sr)
    x = np.zeros(n)
    for k in range(3):
        m = int(0.06 * sr)
        b = noise(m, ('chop', k)) * env_exp(m, 0.003, sr)
        put(x, 0.14 * k * sr, (reson(b, 420, 5, sr) + reson(b, 1100, 6, sr) * 0.5) * (1 - 0.15 * k))
    return fade_out(x, 200), None, 2


def spr_tick():
    sr = SR2
    n = int(0.15 * sr)
    b = noise(n, 'zip') * env_exp(n, 0.002, sr)
    x = reson(b, 1600, 15, sr) + reson(b, 2900, 15, sr) * 0.5
    x += butter(noise(n, 'thmp'), 'low', 150, sr) * env_exp(n, 0.03, sr) * 0.8
    return fade_out(x, 100), None, 2


def spr_wave():
    sr = SR2
    n = int(2.7 * sr)
    t = np.arange(n) / sr
    rise = np.clip(t / 0.9, 0, 1) ** 2
    crash = np.exp(-np.maximum(t - 0.9, 0) / 0.9) * (t >= 0.9) + rise * (t < 0.9)
    body = pink(n, 'wave')
    lo = butter(body, 'low', 600, sr)
    hi = butter(body, 'band', (800, 5000), sr)
    x = lo * crash * 0.8 + hi * crash * np.clip((t - 0.6) / 0.4, 0, 1) * 0.5
    rng = rng_for('foam')
    fz = np.zeros(n)
    for k in range(500):
        st = 1.0 + rng.exponential(0.7)
        if st > 2.6:
            continue
        put(fz, st * sr, rng.standard_normal(6) * rng.uniform(0.2, 1))
    x += butter(fz, 'high', 2000, sr) * 0.25
    return fade_out(x, int(0.4 * sr)), None, 2


def spr_gull():
    sr = SR2
    n = int(0.7 * sr)
    x = np.zeros(n)
    for st, d, f0, f1 in ((0, 0.26, 2100, 1350), (0.33, 0.3, 2250, 1250)):
        m = int(d * sr)
        tt = np.arange(m) / sr
        f = f0 + (f1 - f0) * (tt / d) ** 0.7 + 60 * np.sin(2 * np.pi * 28 * tt)
        ph = 2 * np.pi * np.cumsum(f) / sr
        c = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
        c *= np.sin(np.pi * tt / d) ** 0.8 * (0.8 + 0.2 * butter(noise(m, ('rasp', st)), 'low', 300, sr) / 2)
        put(x, st * sr, c)
    return fade_out(x, 200), None, 2


def spr_icemachine():
    sr = SR2
    n = int(0.75 * sr)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * np.cumsum(70 + 30 * np.exp(-t / 0.02)) / sr) * env_exp(n, 0.08, sr)
    rng = rng_for('cubes')
    for k in range(18):
        st = 0.05 + rng.exponential(0.12)
        if st > 0.65:
            continue
        m = int(0.03 * sr)
        b = noise(m, ('cube', k)) * env_exp(m, 0.002, sr)
        put(x, st * sr, reson(b, rng.uniform(900, 2500), 10, sr) * 0.4)
    return fade_out(x, 300), None, 2


# ---- tables

SFX_ORDER = ['Click', 'Select', 'Back', 'Error', 'Place', 'Demolish', 'BuildRoom', 'MoneyIn', 'MoneyOut',
             'StarGained', 'StarLost', 'ReviewPosted', 'Notification', 'DeskBell', 'ElevatorDing', 'ElevatorDoors',
             'DoorOpen', 'DoorClose', 'Footstep', 'LuggageRoll', 'PhoneRing', 'CashRegister', 'RoomServiceCart',
             'PoolSplash', 'CorkPop', 'Tab', 'Modem', 'Save', 'Hire', 'Break']
AMB_ORDER = ['Lobby', 'Restaurant', 'Bar', 'Kitchen', 'Laundry', 'Sea', 'Night']

# sound: (renderers (alternatives), target loudness LUFS at full level, priority, reverb, pitch
#         jitter, max instances, music duck frames, ring tail tau s)
SFX_DEF = {
    'Click': ([sfx_click], -31, 2, False, 0.04, 1, 0, 0),
    'Select': ([sfx_select], -27, 3, False, 0.0, 1, 0, 0),
    'Back': ([sfx_back], -27, 3, False, 0.0, 1, 0, 0),
    'Error': ([sfx_error], -24, 5, False, 0.0, 1, 0, 0),
    'Place': ([sfx_place], -24, 4, True, 0.06, 2, 0, 0),
    'Demolish': ([sfx_demolish], -21, 5, True, 0.05, 2, 0, 0),
    'BuildRoom': ([sfx_build], -21, 6, True, 0.0, 1, 0, 0),
    'MoneyIn': ([sfx_money_in], -23, 4, True, 0.0, 1, 0, 0),
    'MoneyOut': ([sfx_money_out], -25, 4, True, 0.0, 1, 0, 0),
    'StarGained': ([sfx_star_gained], -19, 9, True, 0.0, 1, 150, 1.2),
    'StarLost': ([sfx_star_lost], -21, 9, True, 0.0, 1, 120, 0.9),
    'ReviewPosted': ([sfx_review], -24, 6, True, 0.0, 1, 0, 0),
    'Notification': ([sfx_notify], -24, 6, True, 0.0, 1, 0, 0.5),
    'DeskBell': ([sfx_desk_bell], -23, 5, True, 0.0, 1, 0, 1.4),
    'ElevatorDing': ([sfx_elevator_ding], -25, 4, True, 0.0, 1, 0, 1.3),
    'ElevatorDoors': ([sfx_elevator_doors], -27, 3, True, 0.0, 2, 0, 0),
    'DoorOpen': ([sfx_door_open], -28, 2, True, 0.06, 2, 0, 0),
    'DoorClose': ([sfx_door_close], -27, 2, True, 0.06, 2, 0, 0),
    'Footstep': ([lambda: sfx_footstep(0), lambda: sfx_footstep(1), lambda: sfx_footstep(2)], -32, 1, False, 0.08, 2, 0, 0),
    'LuggageRoll': ([sfx_luggage], -29, 2, True, 0.05, 1, 0, 0),
    'PhoneRing': ([sfx_phone], -24, 6, True, 0.0, 1, 0, 0),
    'CashRegister': ([sfx_register], -24, 5, True, 0.0, 1, 0, 0),
    'RoomServiceCart': ([sfx_cart], -28, 2, True, 0.04, 1, 0, 0),
    'PoolSplash': ([sfx_splash], -24, 3, True, 0.08, 2, 0, 0),
    'CorkPop': ([sfx_cork], -24, 3, True, 0.05, 1, 0, 0),
    'Tab': ([sfx_tab], -30, 2, False, 0.03, 1, 0, 0),
    'Modem': ([sfx_modem], -26, 5, False, 0.0, 1, 0, 0),
    'Save': ([sfx_save], -26, 6, False, 0.0, 1, 0, 0),
    'Hire': ([sfx_hire], -24, 5, False, 0.0, 1, 0, 0),
    'Break': ([sfx_break], -23, 5, True, 0.04, 1, 0, 0),
}

# sprinkles: name -> (renderer or existing sfx, loudness LUFS at full level, reverb, pitch jitter, tail tau)
SPR_DEF = {
    'clink_a': (lambda: spr_clink(1), -27, True, 0.06, 0),
    'clink_b': (lambda: spr_clink(2), -27, True, 0.06, 0),
    'glass': (spr_glass, -27, True, 0.04, 0),
    'ice': (spr_ice, -29, True, 0.06, 0),
    'pan': (spr_pan, -27, True, 0.06, 0),
    'chop': (spr_chop, -28, True, 0.05, 0),
    'tick': (spr_tick, -30, True, 0.1, 0),
    'wave': (spr_wave, -25, False, 0.06, 0),
    'gull': (spr_gull, -28, True, 0.08, 0),
    'icemachine': (spr_icemachine, -28, True, 0.03, 0),
    'far_ding': ('ElevatorDing', -33, True, 0.0, 1.3),
    'far_door': ('DoorClose', -33, True, 0.06, 0),
    'far_luggage': ('LuggageRoll', -34, True, 0.05, 0),
    'cork': ('CorkPop', -31, True, 0.05, 0),
}

# kind: (bed renderer, bed pitch, bed loudness LUFS at level 256, sprinkles, min, max frames between)
AMB_DEF = {
    'Lobby': ('murmur', 0.53, -33, ['far_ding', 'far_luggage', 'far_door'], 360, 900),
    'Restaurant': ('murmur', 0.5, -32, ['clink_a', 'clink_b', 'clink_a', 'glass'], 20, 80),
    'Bar': ('murmur', 0.45, -33, ['glass', 'ice', 'glass', 'clink_b', 'cork'], 50, 170),
    'Kitchen': ('sizzle', 1.0, -33, ['pan', 'chop', 'clink_b', 'chop'], 40, 140),
    'Laundry': ('hum', 0.5, -34, ['tick'], 30, 110),
    'Sea': ('surf', 0.5, -33, ['wave', 'wave', 'gull'], 200, 420),
    'Night': ('roomtone', 0.5, -40, ['icemachine', 'far_ding', 'far_door'], 700, 1600),
}
BEDS = {'murmur': murmur_bed, 'sizzle': sizzle_bed, 'hum': hum_bed, 'surf': surf_bed, 'roomtone': roomtone_bed}


# ================================================================== loudness

def heard(x, ls, div, tail):
    """A sample as the engine plays it (looped and decaying), at 22,050 Hz."""
    x = np.repeat(np.asarray(x, dtype=np.float64), div)
    if ls is None:
        return x
    lp = ls * div
    hold_s = lp / SR
    n_out = int((hold_s + 3 * max(tail, 0.3)) * SR)
    out = [x]
    tot = len(x)
    while tot < n_out:
        out.append(x[lp:])
        tot += len(x) - lp
    x = np.concatenate(out)[:n_out]
    if tail > 0:
        x = x * np.exp(-np.maximum(0, np.arange(len(x)) / SR - hold_s) / tail)
    return x


def to48k(x, sr):
    g = math.gcd(48000, sr)
    return signal.resample_poly(x, 48000 // g, sr // g)


def loudness(x, sr=SR):
    """Momentary loudness (max over 400 ms windows, K-weighted, mono as both channels), LUFS."""
    y = to48k(x, sr)
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    y = signal.lfilter(b1, a1, y)
    y = signal.lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], y)
    blk = 19200
    if len(y) < blk:
        y = np.concatenate([y, np.zeros(blk - len(y))])
    p = signal.fftconvolve(y ** 2, np.ones(blk) / blk, 'valid')
    return -0.691 + 10 * math.log10(2 * np.max(p) + 1e-20)


def integrated(x, sr=SR):
    y = to48k(x, sr)
    y = signal.lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285],
                       [1.0, -1.69065929318241, 0.73248077421585], y)
    y = signal.lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], y)
    return -0.691 + 10 * math.log10(2 * np.mean(y ** 2) + 1e-20)


# ================================================================== build

class Bank:
    def __init__(self):
        self.items = []         # (key, pcm int16, loop start or None)
        self.rows = []

    def add(self, key, x, loop, peak=0.5, div=1):
        pcm = np.clip(np.round(norm(x, peak) * 32767), -32767, 32767).astype(np.int64)
        self.items.append((key, pcm, loop, div))
        return len(self.items) - 1


def _encode(args):
    pcm, loop = args
    h = hashlib.sha1(pcm.astype('<i2').tobytes() + repr(loop).encode()).hexdigest()
    path = os.path.join(CACHE, h + '.adp')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return f.read()
    data = mei_adpcm.encode(pcm, loop_start=loop)
    os.makedirs(CACHE, exist_ok=True)
    with open(path + '.tmp', 'wb') as f:
        f.write(data)
    os.replace(path + '.tmp', path)
    return data


def build(preview=None):
    insts = make_insts()
    songs = [title_song(), day_song(), night_song()]
    for S in songs:
        for sec in S.sections:
            for part, vs in sec.parts.items():
                for v in vs:
                    for (t, inst, note, vel, pan, dur) in v.ev:
                        insts[inst].used.add(note)
    bank = Bank()
    tables = dict(samp=[], inst=[], nmap=[], song=[], form=[], sect=[], pslot=[], var=[], ev=[], spec=[], amb=[], spr=[])

    # ---- instruments
    render_jobs = []
    plan = {}
    for key in INST_ORDER:
        ins = insts[key]
        if not ins.used:
            continue
        nm = {}
        if key == 'kit':
            for m in sorted(ins.used):
                nm[m] = (('kit', KIT_NOTES[m]), 1.0)
        elif key == 'bell':
            nm = {m: (('bell', m), 1.0) for m in ins.used}
        elif ins.free_natives:
            for m in sorted(ins.used):
                src = min(ins.free_natives, key=lambda s: abs(s - m))
                nm[m] = ((key, src, 0), 2 ** ((m - src) / 12))
        else:
            for m in sorted(ins.used):
                sh = 0
                while m - 12 * sh > ins.native_hi:
                    sh += 1
                nm[m] = ((key, m - 12 * sh, sh), float(2 ** sh))
        plan[key] = nm
    # render each distinct source once, at the largest shift it plays at
    srcs = {}
    for key, nm in plan.items():
        for m, (src, pitch) in nm.items():
            if src[0] in ('kit', 'bell'):
                srcs[src] = 0
            else:
                srcs[(src[0], src[1])] = max(srcs.get((src[0], src[1]), 0), src[2] if len(src) > 2 else 0)
    rendered = {}
    for s, sh in sorted(srcs.items(), key=lambda kv: str(kv[0])):
        if s[0] == 'kit':
            if s[1] == 'ride':
                x, ls = ride_render()
                rendered[s] = (x, ls, 1, 0.5)
            else:
                x, div = kit_render(s[1])
                if div == 2:
                    x = signal.resample_poly(x, 1, 2)
                rendered[s] = (x, None, div, 0.6)
        elif s[0] == 'bell':
            x, ls, div = sfx_desk_bell()
            rendered[s] = (x, ls, div, 0.5)
        else:
            ins = insts[s[0]]
            x, ls = ins.render(s[1], sh)
            rendered[s] = (x, ls, 1, ins.norm_peak)
    sid = {}
    for s, (x, ls, div, pk) in rendered.items():
        sid[s] = (bank.add(s, x, ls, pk, div), ls, div)

    # ---- sfx and sprinkles. Each sample is scaled so that its volume lands near 200 (fine
    # steps for the engine's decay) at the target loudness, and the output peak stays below
    # -6 dBFS.
    spec_rows = []
    sfx_samples = {}

    def level(x, ls, div, tail, target, vol_aim=200):
        h = heard(norm(x, 0.9), ls, div, tail)
        L = loudness(h)
        vol = 255 * 10 ** ((target - L) / 20)        # at sample peak 0.9
        peak = 0.9
        if vol < vol_aim:
            peak = 0.9 * vol / vol_aim
            vol = vol_aim
        vol = min(vol, 255, 0.5 / peak * 256)
        return peak, int(round(vol)), L + 20 * math.log10(peak / 0.9)

    for name in SFX_ORDER:
        rends, lufs_t, prio, rev, jit, maxi, duck, tail = SFX_DEF[name]
        ids = []
        outs = [r() for r in rends]
        peak, vol, L = level(*outs[0], tail, lufs_t)
        for k, (x, ls, div) in enumerate(outs):
            ids.append(bank.add(('sfx', name, k), x, ls, peak, div))
        sfx_samples[name] = (ids, outs[0], peak, L)
        spec_rows.append(dict(name=name, ids=ids, lufs=lufs_t, prio=prio, rev=rev, jit=jit, maxi=maxi, duck=duck,
                              tail=tail, vol=vol, meas=L, peak=peak))
    beds = {}
    for b, fn in BEDS.items():
        x, ls, div = fn()
        beds[b] = (bank.add(('bed', b), x, ls, 0.9, div), div)
    spr_index = {}
    for name, (r, lufs_t, rev, jit, tail) in SPR_DEF.items():
        if isinstance(r, str):
            ids = sfx_samples[r][0][:1]
            peak, L = sfx_samples[r][2], sfx_samples[r][3]
            vol = int(round(min(255, 255 * 10 ** ((lufs_t - L) / 20), 0.5 / peak * 256)))
        else:
            x, ls, div = r()
            peak, vol, L = level(x, ls, div, tail, lufs_t)
            ids = [bank.add(('spr', name), x, ls, peak, div)]
        spr_index[name] = len(spec_rows)
        spec_rows.append(dict(name='spr_' + name, ids=ids, lufs=lufs_t, prio=0, rev=rev, jit=jit, maxi=2, duck=0,
                              tail=tail, vol=vol, meas=L, peak=peak))

    # ---- encode everything (in parallel; cached in build/)
    with concurrent.futures.ProcessPoolExecutor() as ex:
        datas = list(ex.map(_encode, [(it[1], it[2]) for it in bank.items]))
    blob = bytearray()
    for (key, pcm, loop, div), data in zip(bank.items, datas):
        tables['samp'] += [len(blob), len(pcm), -1 if loop is None else loop]
        blob += data
    decoded = [mei_adpcm.decode(d, len(it[1])) for d, it in zip(datas, bank.items)]

    # ---- instrument tables
    nmap_rows = []
    for key in INST_ORDER:
        ins = insts[key]
        if key not in plan:
            tables['inst'] += [0] * 16
            continue
        nm = plan[key]
        lo, hi = min(nm), max(nm)
        base = len(nmap_rows) // 3
        for m in range(lo, hi + 1):
            if m in nm:
                src, pitch = nm[m]
                skey = src if src[0] in ('kit', 'bell') else (src[0], src[1])
                i, ls, div = sid[skey]
                p = pitch / div
                hold = 0 if ls is None else int(round(ls * div / pitch / FRAME))
                nmap_rows += [i, round(p * 65536), hold]
            else:
                nmap_rows += [-1, 0, 0]
        tables['inst'] += ins.params(base, lo, hi)
    tables['nmap'] = nmap_rows

    # ---- songs
    inst_idx = {k: i for i, k in enumerate(INST_ORDER)}
    var_cache = {}
    for S in songs:
        form_base = len(tables['form'])
        sec_ids = {}
        for sec in S.sections:
            sec_ids[id(sec)] = len(tables['sect']) // 3
            order = PART_ORDER[S.key]
            pbase = len(tables['pslot']) // 2
            for part in order:
                vs = sec.parts.get(part, [Ev()])
                vb = len(tables['var']) // 3
                for v in vs:
                    if id(v) not in var_cache:
                        ev = sorted(v.ev, key=lambda e: (e[0], e[1]))
                        eb = len(tables['ev']) // 2
                        for (t, inst, note, vel, pan, dur) in ev:
                            assert 0 <= t < 65536 and dur < 32768, (t, dur)
                            tables['ev'] += [t | (dur << 16), inst_idx[inst] | (note << 5) | (vel << 12) | (pan << 19)]
                        var_cache[id(v)] = (eb, len(ev), v.period)
                    tables['var'] += list(var_cache[id(v)])
                tables['pslot'] += [vb, len(vs)]
            tables['sect'] += [sec.length, pbase, len(order)]
        for sec in S.form:
            tables['form'].append(sec_ids[id(sec)])
        tables['song'] += [form_base, len(S.form), form_base + S.loop_to, sec_ids[id(S.ending)], S.bar,
                           int(S.exit_bars), S.gain, 0]

    # ---- sfx and sprinkle specs (volume from the target loudness)
    def sample_div(i):
        return bank.items[i][3]

    for r in spec_rows:
        i0 = r['ids'][0]
        loop = bank.items[i0][2]
        div = sample_div(i0)
        tail = r['tail']
        hold_s = 0 if loop is None else loop * div / SR
        r['heard'] = loudness(heard(decoded[i0].astype(np.float64) / 32768, loop, div, tail)) + \
            20 * math.log10(r['vol'] / 255)
        dec = 65536 if tail <= 0 else round(65536 * math.exp(-1 / (tail * FPS)))
        hold = 0 if loop is None else int(round(hold_s * FPS))
        pitch = 1.0 / div
        tables['spec'] += [i0, len(r['ids']), r['vol'], r['prio'], int(r['rev']), round(pitch * 65536),
                           round(r['jit'] * pitch * 65536), min(dec, 65536), hold, r['maxi'], r['duck'], 0]
    # ambience
    for kind in AMB_ORDER:
        bed, pitch, lufs_t, sprs, lo, hi = AMB_DEF[kind]
        bi, div = beds[bed]
        x = decoded[bi].astype(np.float64) / 32768
        L = integrated(x, SR // div)
        vol = int(round(255 * 10 ** ((lufs_t - L) / 20)))
        if vol > 255:
            print('  note: bed %s wants volume %d (capped)' % (kind, vol))
            vol = 255
        sb = len(tables['spr'])
        for s in sprs:
            tables['spr'].append(spr_index[s])
        tables['amb'] += [bi, round(pitch * 65536), vol, sb, len(sprs), lo, hi, 0]

    report = []
    sizes = {}
    for (key, pcm, loop, div), data in zip(bank.items, datas):
        cat = key[0] if key[0] in ('sfx', 'spr', 'bed', 'kit', 'bell') else 'music:' + key[0]
        sizes[cat] = sizes.get(cat, 0) + len(data)
    report.append('bank %d bytes: %s' % (len(blob), ', '.join('%s %d' % kv for kv in sorted(sizes.items()))))
    tbytes = 4 * sum(len(v) for v in tables.values())
    report.append('tables %d bytes; %d samples, %d events' % (tbytes, len(bank.items), len(tables['ev']) // 2))
    report.append('audio ROM total ~%d bytes' % (len(blob) + tbytes))
    if preview:
        os.makedirs(preview, exist_ok=True)
        for (key, pcm, loop, div), d in zip(bank.items, decoded):
            name = '_'.join(str(k) for k in key).replace(' ', '')
            x = d.astype(np.float64) / 32768
            if div == 2:
                x = np.repeat(x, 2)
                loop = None if loop is None else loop * 2
            if loop is not None:
                x = np.concatenate([x] + [x[loop:]] * int(math.ceil(1.0 * SR / max(1, len(x) - loop))))
            mei_adpcm.save_wav(os.path.join(preview, name + '.wav'), np.round(x * 32767).astype(np.int16))
    return dict(songs=songs, insts=insts, tables=tables, blob=bytes(blob), report=report, spec_rows=spec_rows)



def write(st):
    os.makedirs(AUD, exist_ok=True)
    with open(os.path.join(AUD, 'bank.adp'), 'wb') as f:
        f.write(st['blob'])
    T = st['tables']
    L = ['// Generated by tools/gen_checkin_audio.py - do not edit.',
         '// Check-In! samples, scores, sound effect and ambience tables, read by audio.akr.', '',
         'embed SND_BANK: u8 = "audio/bank.adp"', '',
         'const MUS_NSONGS = %d' % (len(T['song']) // 8),
         'const MUS_NPSLOT = %d' % (len(T['pslot']) // 2),
         'const SND_NSFX = %d' % len(SFX_ORDER),
         'const SND_NAMB = %d' % len(AMB_ORDER), '']

    def arr(name, vals, comment, per=16):
        L.append('// ' + comment)
        rows = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]s32 = [%s]' % (name, len(vals), (',\n    ').join(rows)))
    arr('SND_SAMP', T['samp'], 'per sample: byte offset in SND_BANK, length (samples), loop start (-1: one-shot)', 15)
    arr('MUS_INST', T['inst'], 'per instrument (guitar rhodes vibes bass piano trumpet kit bell): mode (1 struck, '
        '2 sustained), decay and release per frame (x65536), volume, reverb send, tremolo kind (1 level, 2 pan), '
        'depth (x256), rate (cycles x65536 per frame), note map row, lowest and highest note, mono, cut-off release, '
        'steal protection, 0, 0', 16)
    arr('MUS_NMAP', T['nmap'], 'per note: sample (-1 none), pitch (16.16), frames before the decay', 15)
    arr('MUS_SONG', T['song'], 'per song (title, day, night): first form entry, entries, entry to loop back to, '
        'ending section, frames per bar, may end at any bar, gain (x256), 0', 8)
    arr('MUS_FORM', T['form'], 'the form: section numbers')
    arr('MUS_SECT', T['sect'], 'per section: length (frames), first part slot, parts', 15)
    arr('MUS_PSLOT', T['pslot'], 'per part slot: first variant, variants', 16)
    arr('MUS_VAR', T['var'], 'per variant: first event, events, repeat period (frames, 0: none)', 15)
    arr('MUS_EV', T['ev'], 'per event: frame | duration << 16 (frames, 0 = let ring), '
        'inst | note << 5 | velocity << 12 | pan << 19', 8)
    arr('SND_SPEC', T['spec'], 'per sound (Sfx order, then ambience sprinkles): sample, alternatives, volume, '
        'priority, reverb, pitch (16.16), pitch jitter, decay per frame (x65536), frames before the decay, '
        'max instances, music duck frames, 0', 12)
    arr('SND_AMB', T['amb'], 'per ambience (Ambience order): bed sample, bed pitch, bed volume, first sprinkle, '
        'sprinkles, min and max frames between sprinkles, 0', 8)
    arr('SND_SPR', T['spr'], 'sprinkles: SND_SPEC rows')
    with open(os.path.join(OUT, 'audio_data.akr'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def check_enums():
    """audio.akr's enums must list the sounds in this file's order."""
    path = os.path.join(OUT, 'audio.akr')
    if not os.path.exists(path):
        return
    src = open(path).read()
    for name, order in (('Sfx', SFX_ORDER), ('Ambience', AMB_ORDER)):
        mm = re.search(r'enum\s+%s\s*\{([^}]*)\}' % name, src)
        assert mm, name
        got = [w.strip() for w in re.sub(r'//[^\n]*', '', mm.group(1)).replace('\n', ',').split(',') if w.strip()]
        assert got == order, (name, got, order)


def main():
    preview = None
    if '--preview' in sys.argv:
        preview = sys.argv[sys.argv.index('--preview') + 1]
    st = build(preview)
    write(st)
    check_enums()
    for line in st['report']:
        print(line)
    if '--levels' in sys.argv:
        for r in st['spec_rows']:
            print('  %-18s volume %3d, peak %6.1f dBFS, loudness %6.1f LUFS (target %d)' % (
                r['name'], r['vol'], 20 * math.log10(r['vol'] / 256 * r['peak']), r['heard'], r['lufs']))


if __name__ == '__main__':
    main()
