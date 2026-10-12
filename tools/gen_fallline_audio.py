#!/usr/bin/env python3
"""Fall Line's music and sound effects, synthesised from nothing (no samples, no transcription).

Music. Two original tracks in F minor, late-1990s breakbeat for a downhill racer:
  run    "Fall Line": drum and bass with big-beat parts, 171.82 bpm, a 3.0 s riser before the
         drop (the length of the countdown), then a 32-bar loop (44.7 s): A drop (rolling reese
         bass, chord stabs), B the hook (a saw lead with a ping-pong delay), C the breakdown (open
         pads, a bell arpeggio, half-time drums, a snare roll and a riser), D the last drop (the
         hook, an acid line, a ride).
  title  "Synergen": big beat, 132.35 bpm with swung sixteenths, a one-bar filtered intro and an
         8-bar loop (14.5 s): a fat distorted break, an acid bassline, brass stabs and scratches.
Each track is three ADPCM stems that the console loops by itself (the loop is in the samples, so
it never drifts and costs the CPU nothing): `beat`, the drums and bass in mono, dry, and `air L`
and `air R`, a stereo pair (pads, stabs, leads, arpeggios, cymbals, risers) sent to the reverb.
A bar is a whole number of 28-sample ADPCM blocks, the loop is rendered twice and the second
pass kept, so every tail that crosses the loop point wraps into its start.

Sound effects: two wind loops (decorrelated, for width) and a snow-hiss loop, which sfx.akr
pitches and fades with the speed and the carve, and one-shots: landing thump, gate chime, miss
buzz, crash, countdown beep, go, finish sting and menu blip. Loops are made from circular noise
(shaped in the frequency domain, so they repeat seamlessly) with a two-block lead-in.

The reverb is the console's: preset 4 (space, 45 ms predelay) with its decay shortened, the
open air of a mountain.

Writes carts/fallline/audio/music.adp, carts/fallline/audio/sfx.adp and carts/fallline/mu_data.akr
(the tables carts/fallline/music.akr and sfx.akr read).
    python3 tools/gen_fallline_audio.py [--preview DIR]
--preview writes title.wav and run.wav (the stems decoded and mixed as the console mixes them,
without the reverb; the loop plays twice so its seam can be heard), the stems, and every sound
effect, as WAVs. With FL_QUICK=1 in the environment, --preview writes the unencoded stems and
effects only (seconds instead of a minute) and nothing in the cart. Needs NumPy and SciPy.
"""
import argparse, math, os, sys, wave
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'fallline')
AUD = os.path.join(CART, 'audio')

SR = 22050                 # the console's rate
OS = 2                     # the music and one-shots are rendered at twice that, then filtered down
FS = SR * OS
BLK = 28                   # samples in an ADPCM block

# the console reverb
REVERB = 4                 # space
REV_WET = 150
REV_DECAY = 200            # its feedback x 200/256: a 2.3 s tail (RT60) instead of 6.3

# timing, in samples at SR (a bar must be whole blocks)
RUN_BEAT = 7700            # 171.82 bpm; bar 30,800 = 1,100 blocks
RUN_BARS = 32
RUN_INTRO = 2363 * BLK     # 66,164 samples, 3.0006 s: the countdown's three seconds
TITLE_BEAT = 9996          # 132.35 bpm; bar 39,984 = 1,428 blocks
TITLE_BARS = 8
TITLE_SWING = 0.16         # odd sixteenths late by this much of a sixteenth

MASTER_PEAK = 0.50         # the music's stereo mix peaks here (of full scale): room for the effects
STEM_PEAK = 0.97           # each stem is stored this loud; its channel volume brings it down


# ================================================================== DSP helpers

def tt(dur):
    return np.arange(int(round(dur * FS))) / FS


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69) / 12)


def rbj(f, q, mode):
    f = min(max(float(f), 10.0), FS * 0.45)
    w = 2 * math.pi * f / FS
    cw, sw = math.cos(w), math.sin(w)
    al = sw / (2 * q)
    if mode == 'lp':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    elif mode == 'hp':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    else:
        b = [al, 0.0, -al]                       # band-pass, 0 dB at the centre
    a = [1 + al, -2 * cw, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def filt(x, f, q=0.707, mode='lp'):
    b, a = rbj(f, q, mode)
    return signal.lfilter(b, a, x)


def tvf(x, fc, q=0.707, mode='lp', blk=64):
    """A biquad whose cutoff follows fc (per sample), updated every blk samples."""
    fc = np.broadcast_to(np.asarray(fc, dtype=float), x.shape)
    y = np.zeros_like(x)
    zi = np.zeros(2)
    for i in range(0, len(x), blk):
        seg = x[i:i + blk]
        if not seg.any() and abs(zi).max() < 1e-12:
            continue
        b, a = rbj(fc[i], q, mode)
        y[i:i + blk], zi = signal.lfilter(b, a, seg, zi=zi)
    return y


def onepole(x, f):
    p = math.exp(-2 * math.pi * f / FS)
    return signal.lfilter([1 - p], [1, -p], x)


def _blep(ph, dt):
    out = np.zeros_like(ph)
    m = ph < dt
    t = ph[m] / dt[m]
    out[m] = t + t - t * t - 1
    m = ph > 1 - dt
    t = (ph[m] - 1) / dt[m]
    out[m] = t * t + t + t + 1
    return out


def _phase(freq, ph0):
    dt = np.asarray(freq, dtype=float) / FS
    return (ph0 + np.cumsum(dt) - dt) % 1.0, dt


def saw(freq, ph0=0.0):
    """Band-limited (PolyBLEP) saw, freq per sample."""
    ph, dt = _phase(freq, ph0)
    return 2 * ph - 1 - _blep(ph, dt)


def pulse(freq, pw=0.5, ph0=0.0):
    ph, dt = _phase(freq, ph0)
    ph2 = (ph + pw) % 1.0
    return (2 * ph - 1 - _blep(ph, dt)) - (2 * ph2 - 1 - _blep(ph2, dt))


def sine(freq, ph0=0.0):
    return np.sin(2 * math.pi * (ph0 + np.cumsum(np.asarray(freq, dtype=float)) / FS))


def sat(x, drive):
    return np.tanh(drive * x) / math.tanh(drive)


def put(buf, pos, sig, g=1.0):
    pos = int(pos)
    if pos >= len(buf) or g == 0:
        return
    if pos < 0:
        sig = sig[-pos:]
        pos = 0
    n = min(len(sig), len(buf) - pos)
    if n > 0:
        buf[pos:pos + n] += g * sig[:n]


def comb(x, d, g):
    """y[n] = x[n] + g y[n - d], a block of d at a time."""
    y = x.copy()
    for i in range(d, len(y), d):
        k = min(d, len(y) - i)
        y[i:i + k] += g * y[i - d:i - d + k]
    return y


def pingpong(x, d, fb, damp):
    """Echoes of mono x alternating left (d, 3d, ...) and right (2d, 4d, ...), darkening."""
    x = onepole(x, damp)
    c = comb(x, 2 * d, fb * fb)
    left = np.zeros_like(x)
    right = np.zeros_like(x)
    left[d:] = fb * c[:-d]
    right[2 * d:] = fb * fb * c[:-2 * d]
    return left, right


def down(x, circular):
    """FS to SR; a circular signal is filtered across its own seam."""
    if circular:
        p = 4000
        e = np.concatenate([x[-p:], x, x[:p]])
        return signal.resample_poly(e, 1, OS)[p // OS:p // OS + len(x) // OS]
    return signal.resample_poly(x, 1, OS)[:len(x) // OS]


def hp_dc(x, f=25.0):
    return filt(x, f, 0.707, 'hp')


# ================================================================== drums

def kick_smp(rng, f0=170, f1=52, tp=0.03, dec=0.2, drive=2.2, click=0.3, dur=0.55):
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t / tp)
    body = sine(f) * np.exp(-t / dec) * np.clip(t / 0.0012, 0, 1)
    body *= np.clip((dur - t) / 0.03, 0, 1)
    ck = filt(rng.standard_normal(len(t)), 2500, 0.7, 'hp') * np.exp(-t / 0.003) * click
    return sat(body + ck, drive)


def snare_smp(rng, tone=192, dec_n=0.15, dec_t=0.06, crack=0.45, bright=9000, drive=1.6, dur=0.5):
    dur = max(dur, 6 * dec_n)
    t = tt(dur)
    f = tone * (1 + 0.3 * np.exp(-t / 0.008))
    tonal = (sine(f) + 0.45 * sine(f * 1.73)) * np.exp(-t / dec_t)
    nz = filt(rng.standard_normal(len(t)), 1500, 0.6, 'hp')
    nz = filt(nz, bright, 0.7, 'lp') * np.exp(-t / dec_n)
    ck = filt(rng.standard_normal(len(t)), 3500, 0.7, 'hp') * np.exp(-t / 0.004) * crack
    x = (0.7 * tonal + 1.1 * nz + ck) * np.clip(t / 0.0006, 0, 1) * np.clip((dur - t) / (dur / 3), 0, 1)
    return sat(x, drive)


def metal(base, n, rng):
    t = np.arange(n) / FS
    m = np.zeros(n)
    for r in (2.0, 3.0, 4.16, 5.43, 6.79, 8.21):
        m += np.sign(np.sin(2 * math.pi * base * r * t + rng.uniform(0, 6.28)))
    return m / 6


def hat_smp(rng, dec=0.032, dur=0.14, hp=6200, base=330):
    dur = max(dur, 6 * dec)
    t = tt(dur)
    x = 0.55 * metal(base, len(t), rng) + 0.7 * rng.standard_normal(len(t))
    x = filt(filt(x, hp, 0.8, 'hp'), hp * 0.9, 0.7, 'hp')
    env = np.exp(-t / dec) * np.clip(t / 0.0005, 0, 1) * np.clip((dur - t) / (dur / 3), 0, 1)
    return x * env / 0.6


def cymbal_smp(rng, dec=0.9, dur=2.6, hp=3200, base=300, bell=0.0):
    dur = max(dur, 4.5 * dec)
    t = tt(dur)
    x = 0.5 * metal(base, len(t), rng) + 0.8 * rng.standard_normal(len(t))
    x = filt(filt(x, hp, 0.7, 'hp'), 10500, 0.7, 'lp')
    burst = filt(rng.standard_normal(len(t)), 2000, 0.7, 'hp') * np.exp(-t / 0.02)
    env = np.exp(-t / dec) * np.clip(t / 0.001, 0, 1) * np.clip((dur - t) / (dur / 3), 0, 1)
    y = (x + 0.6 * burst) * env
    if bell:
        y += bell * (np.sin(2 * math.pi * 2350 * t) + 0.6 * np.sin(2 * math.pi * 3720 * t)) * np.exp(-t / (dec * 0.6))
    return y / 0.7


def shaker_smp(rng, dur=0.09):
    t = tt(dur)
    x = filt(filt(rng.standard_normal(len(t)), 5200, 0.9, 'hp'), 9500, 0.7, 'lp')
    env = np.clip(t / 0.008, 0, 1) * np.exp(-t / 0.03)
    return x * env


def tamb_smp(rng, dur=0.18):
    t = tt(dur)
    x = 0.6 * metal(520, len(t), rng) + rng.standard_normal(len(t))
    x = filt(x, 6500, 0.8, 'hp')
    return x * np.exp(-t / 0.05) * np.clip(t / 0.002, 0, 1)


def boom_smp(rng, dur=1.4):
    """A sub drop for a downbeat impact."""
    t = tt(dur)
    f = 38 + 70 * np.exp(-t / 0.09)
    x = sine(f) * np.exp(-t / 0.45) * np.clip(t / 0.002, 0, 1)
    x += 0.4 * filt(rng.standard_normal(len(t)), 300, 0.7, 'lp') * np.exp(-t / 0.08)
    return sat(x * np.clip((dur - t) / 0.2, 0, 1), 1.8)


class Kit:
    """A few takes of every drum, chosen at random per hit so repeats are not identical."""
    def __init__(self, seed, big=False):
        rng = np.random.default_rng(seed)
        self.rng = np.random.default_rng(seed + 1)
        if big:     # big beat: a fatter, longer, dirtier kit
            self.s = {
                'K': [kick_smp(rng, f0=155, f1=50, tp=0.04, dec=0.26, drive=3.2, click=0.4, dur=0.7) for _ in range(3)],
                'S': [snare_smp(rng, tone=180, dec_n=0.24, dec_t=0.08, crack=0.6, bright=8000, drive=2.6, dur=0.6) for _ in range(4)],
            }
        else:
            self.s = {
                'K': [kick_smp(rng) for _ in range(3)],
                'S': [snare_smp(rng) for _ in range(4)],
            }
        self.s['g'] = [filt(snare_smp(rng, dec_n=0.07, crack=0.25), 5000) for _ in range(4)]
        self.s['h'] = [hat_smp(rng) for _ in range(6)]
        self.s['o'] = [hat_smp(rng, dec=0.18, dur=0.5, hp=5500) for _ in range(3)]
        self.s['r'] = [cymbal_smp(rng, dec=0.45, dur=1.2, hp=2800, base=470, bell=0.35) for _ in range(3)]
        self.s['k'] = [shaker_smp(rng) for _ in range(6)]
        self.s['t'] = [tamb_smp(rng) for _ in range(4)]
        self.crash = [cymbal_smp(rng) for _ in range(4)]
        self.boom = boom_smp(rng)
        self.gain = {'K': 1.0, 'S': 0.8, 'g': 0.42, 'h': 0.24, 'o': 0.2, 'r': 0.2, 'k': 0.16, 't': 0.2}

    def hit(self, name):
        takes = self.s[name]
        return takes[self.rng.integers(len(takes))]


# ================================================================== instruments

def env_ar(n, att, rel, gate_n):
    """Attack, hold for gate_n samples, release; n samples long."""
    t = np.arange(n)
    a = np.clip(t / max(1, att * FS), 0, 1)
    r = np.clip(1 - (t - gate_n) / max(1, rel * FS), 0, 1)
    return a * np.where(t < gate_n, 1.0, r)


def supersaw(midi, n, rng, detunes=(-0.16, -0.07, 0.0, 0.07, 0.16)):
    f = mtof(midi)
    out = []
    for d in detunes:
        out.append(saw(np.full(n, f * 2 ** (d / 12)), rng.uniform()))
    return out


def stab_smp(notes, dur, rng, bright=1.0):
    n = int(dur * FS)
    x = np.zeros(n)
    for m in notes:
        for s in supersaw(m, n, rng, (-0.1, 0.0, 0.1)):
            x += s
        x += 0.5 * pulse(np.full(n, mtof(m - 12)), 0.5, rng.uniform())
    x /= len(notes) * 2.0
    t = np.arange(n) / FS
    fc = 500 + 4200 * bright * np.exp(-t / 0.07)
    y = tvf(x, fc, 1.6, 'lp', 32)
    return sat(y * env_ar(n, 0.002, 0.05, n - int(0.05 * FS)) * np.exp(-t / 0.25), 1.3)


def bell_smp(midi, dur=0.9, ratio=3.5, index=2.2):
    """An FM bell: glassy, quick."""
    t = tt(dur)
    f = float(mtof(midi))
    mod = index * np.exp(-t / 0.12) * np.sin(2 * math.pi * f * ratio * t)
    x = np.sin(2 * math.pi * f * t + mod) + 0.25 * np.sin(2 * math.pi * f * 2 * t) * np.exp(-t / 0.08)
    return x * np.exp(-t / 0.28) * np.clip(t / 0.0015, 0, 1) * np.clip((dur - t) / 0.05, 0, 1)


def mono_line(notes, n, glide=0.035):
    """A monophonic line: notes are (start, end, midi, slide) in samples. Returns the pitch
    (midi, per sample), the gate, and the onsets that retrigger (not slid into)."""
    pitch = np.zeros(n)
    gate = np.zeros(n)
    onsets = []
    notes = sorted(notes)
    for i, (s, e, m, slide) in enumerate(notes):
        nxt = notes[i + 1][0] if i + 1 < len(notes) else n
        s, e = max(0, int(s)), min(n, int(e))
        if s >= n:
            continue
        pitch[s:min(n, int(nxt))] = m
        gate[s:e] = 1.0
        if slide and i > 0:
            pm = notes[i - 1][2]
            g = min(int(glide * FS), int(nxt) - s, n - s)
            if g > 0:
                pitch[s:s + g] = pm + (m - pm) * np.linspace(0, 1, g)
        else:
            onsets.append(s)
    # before the first note, hold its pitch
    if notes:
        pitch[:max(0, int(notes[0][0]))] = notes[0][2]
    return pitch, gate, onsets


def smooth_gate(gate, ms):
    return uniform_filter1d(gate, max(1, int(ms * FS / 1000)))


def decays(onsets, n, tau, weights=None):
    """A sum of decaying envelopes starting at the onsets (each restarts the decay)."""
    e = np.zeros(n)
    k = int(tau * 6 * FS)
    d = np.exp(-np.arange(k) / (tau * FS))
    for i, s in enumerate(onsets):
        w = weights[i] if weights is not None else 1.0
        end = min(n, s + k)
        e[s:end] = np.maximum(e[s:end], w * d[:end - s])
    return e


# ================================================================== a song

class Song:
    def __init__(self, beat, bars, swing=0.0):
        self.step = beat * OS / 4.0          # samples (FS) a sixteenth
        self.bar_len = beat * OS * 4
        self.bars = bars
        self.L = self.bar_len * bars         # the loop, samples at FS
        self.swing = swing

    def at(self, bar, step):
        s = step + (self.swing if int(math.floor(step)) % 2 == 1 and step == int(step) else 0.0)
        return int(round(bar * self.bar_len + s * self.step))


class Events:
    """What a timeline plays: everything in samples at FS from the timeline's start."""
    def __init__(self):
        self.hits = []        # (pos, drum, velocity, bus: 'kit' | 'lp')
        self.bass = []        # (start, end, midi, slide)
        self.sub = []         # (start, end, midi)
        self.acid = []        # (start, end, midi, slide, accent)
        self.lead = []        # (start, end, midi, slide)
        self.pads = []        # (start, end, notes, level)
        self.stabs = []       # (pos, notes, velocity, pan 0..1, length s)
        self.bells = []       # (pos, midi, velocity, pan)
        self.crashes = []     # (pos, gain)
        self.revcrash = []    # (end, gain, seconds)
        self.booms = []       # (pos, gain)
        self.risers = []      # (start, end, gain)
        self.scratches = []   # (pos, gain)

    def shifted(self, d):
        e = Events()
        for k, v in self.__dict__.items():
            out = []
            for item in v:
                item = list(item)
                item[0] += d
                if k in ('bass', 'sub', 'acid', 'lead', 'pads', 'risers'):
                    item[1] += d
                out.append(tuple(item))
            setattr(e, k, out)
        return e

    def extend(self, other):
        for k, v in other.__dict__.items():
            getattr(self, k).extend(v)


# the air parts' levels, against the beat stem
AIR = {'pad': 1.1, 'stab': 1.3, 'lead': 1.0, 'acid': 0.8, 'bell': 1.0, 'crash': 0.3, 'riser': 0.7, 'scratch': 0.9}


def render(ev, n, kit, auto, lead_delay, acid_delay, title=False, seed=7, air_scale=1.0):
    """Renders events into (beat, airL, airR) at FS, n samples. auto(name, idx) gives the
    automation curves (cutoffs) at timeline sample indices."""
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    beat = np.zeros(n)
    airL = np.zeros(n)
    airR = np.zeros(n)

    # ---- drums
    kitbus = np.zeros(n)
    lpbus = np.zeros(n)
    kick_on = []
    for pos, d, vel, bus in ev.hits:
        tgt = kitbus if bus == 'kit' else lpbus
        jitter = 0 if d in 'KS' else int(rng.normal(0, 0.0012) * FS)
        put(tgt, pos + jitter, kit.hit(d), kit.gain[d] * vel)
        if d == 'K' and bus == 'kit':
            kick_on.append(int(pos))
    room_t = tt(0.32)
    ir = filt(rng.standard_normal(len(room_t)), 6000) * np.exp(-room_t / (0.085 if title else 0.06))
    ir[0] = 0
    ir /= np.sqrt((ir ** 2).sum())
    room = signal.fftconvolve(kitbus, ir)[:n]
    kitbus = kitbus + (0.22 if title else 0.14) * room
    if lpbus.any():
        kitbus += tvf(lpbus, auto('drumlp', idx), 0.9)
    kitbus = sat(kitbus, 2.4 if title else 1.6) * (0.85 if title else 0.9)
    for pos, g in ev.booms:
        put(kitbus, pos, kit.boom, 0.45 * g)

    # sidechain: the bass ducks under each kick
    pump = 1 - 0.55 * decays(kick_on, n, 0.07)

    # ---- bass: a reese (two detuned saws, filtered, distorted) and a sine sub an octave down
    bassbus = np.zeros(n)
    if ev.bass:
        pitch, gate, _ = mono_line(ev.bass, n, 0.03)
        g = smooth_gate(gate, 4)
        f = mtof(pitch)
        lfo = 0.5 + 0.5 * np.sin(2 * math.pi * idx / (FS * 2.8))
        x = saw(f * 2 ** (-(0.10 + 0.08 * lfo) / 12)) + saw(f * 2 ** ((0.10 + 0.08 * lfo) / 12), 0.37) + 0.5 * saw(f * 2, 0.71)
        x = tvf(x, auto('reese', idx), 1.2)
        x = filt(sat(x * 0.6, 2.2), 70, 0.7, 'hp')
        sub = sine(f) * g
        bassbus += 0.5 * x * g + 0.32 * sub
    if ev.sub:
        pitch, gate, _ = mono_line([(s, e, m, False) for s, e, m in ev.sub], n)
        g = smooth_gate(gate, 12)
        bassbus += 0.4 * sine(mtof(pitch)) * g
    bassbus = sat(bassbus * pump, 1.3)
    beat = kitbus + bassbus

    # ---- pads: supersaw chords, every voice panned, swept by a low-pass
    if ev.pads:
        pl = np.zeros(n)
        pr = np.zeros(n)
        for s, e, notes, lvl in ev.pads:
            s, e = int(s), int(e)
            m = e - s + int(0.9 * FS)
            env = env_ar(m, 0.35, 0.9, e - s) * lvl
            vs = []
            for nt in notes:
                vs += supersaw(nt, m, rng)
            k = len(vs)
            for i, v in enumerate(vs):
                p = (i % 5) / 4.0 * 0.8 + 0.1
                if (i // 5) % 2:
                    p = 1 - p
                put(pl, s, v * env, math.cos(p * math.pi / 2) / math.sqrt(k))
                put(pr, s, v * env, math.sin(p * math.pi / 2) / math.sqrt(k))
        fc = auto('pad', idx)
        airL += AIR['pad'] * tvf(pl, fc, 0.8)
        airR += AIR['pad'] * tvf(pr, fc, 0.8)

    # ---- stabs, with a dotted-eighth ping-pong
    if ev.stabs:
        st = np.zeros(n)
        stl = np.zeros(n)
        str_ = np.zeros(n)
        for pos, notes, vel, pan, ln in ev.stabs:
            x = stab_smp(notes, ln, rng, 0.6 + 0.4 * vel)
            put(st, pos, x, vel)
            put(stl, pos, x, vel * math.cos(pan * math.pi / 2))
            put(str_, pos, x, vel * math.sin(pan * math.pi / 2))
        el, er = pingpong(st, lead_delay, 0.42, 3000)
        airL += AIR['stab'] * (stl + 0.45 * el)
        airR += AIR['stab'] * (str_ + 0.45 * er)

    # ---- lead: saw and pulse with glide and a late vibrato, octave double, ping-pong
    if ev.lead:
        pitch, gate, onsets = mono_line(ev.lead, n, 0.045)
        g = smooth_gate(gate, 6)
        age = np.zeros(n)
        on = sorted(onsets) + [n]
        for i in range(len(on) - 1):
            age[on[i]:on[i + 1]] = np.arange(on[i + 1] - on[i]) / FS
        vib = 0.22 * np.clip((age - 0.14) / 0.2, 0, 1) * np.sin(2 * math.pi * 5.6 * idx / FS)
        f = mtof(pitch + vib)
        x = saw(f) + 0.6 * pulse(f * 1.003, 0.32, 0.2) + 0.35 * saw(f * 2.004, 0.5)
        fenv = decays(onsets, n, 0.18)
        x = tvf(x, 1800 + 3800 * fenv + auto('lead', idx), 1.0)
        x = sat(x * g * 0.5, 1.4)
        el, er = pingpong(x, lead_delay, 0.45, 3500)
        airL += AIR['lead'] * (x + 0.5 * el)
        airR += AIR['lead'] * (x + 0.5 * er)

    # ---- acid: a 303-style line (saw, resonant low-pass with an envelope, accents, slides)
    if ev.acid:
        notes = [(s, e, m, sl) for s, e, m, sl, ac in ev.acid]
        pitch, gate, onsets = mono_line(notes, n, 0.06)
        acc = {int(s): ac for s, e, m, sl, ac in ev.acid}
        w = [1.0 + 0.8 * acc.get(o, 0) for o in onsets]
        fenv = decays(onsets, n, 0.11, w)
        g = smooth_gate(gate, 3) * (0.75 + 0.25 * np.minimum(fenv, 1.6))
        x = saw(mtof(pitch))
        fc = auto('acid', idx) * (1 + 3.2 * fenv)
        x = tvf(x, fc, 7.0)
        x = tvf(x, fc * 1.1, 0.7)
        x = sat(x * g * 1.6, 2.6) * 0.5
        if title:     # the title's acid is its bass: in the beat stem, centred
            beat += 0.62 * x
            el, er = pingpong(x, acid_delay, 0.3, 2500)
            airL += AIR['acid'] * 0.4 * el
            airR += AIR['acid'] * 0.4 * er
        else:
            el, er = pingpong(x, acid_delay, 0.35, 2500)
            airL += AIR['acid'] * (x + 0.4 * el)
            airR += AIR['acid'] * (x + 0.4 * er)

    # ---- bells (the breakdown's arpeggio)
    if ev.bells:
        bl = np.zeros(n)
        br = np.zeros(n)
        bm = np.zeros(n)
        for pos, m, vel, pan in ev.bells:
            x = bell_smp(m)
            put(bl, pos, x, vel * math.cos(pan * math.pi / 2))
            put(br, pos, x, vel * math.sin(pan * math.pi / 2))
            put(bm, pos, x, vel)
        el, er = pingpong(bm, lead_delay, 0.5, 4000)
        airL += AIR['bell'] * (bl + 0.6 * el)
        airR += AIR['bell'] * (br + 0.6 * er)

    # ---- cymbals, risers, scratches
    for pos, g in ev.crashes:
        put(airL, pos, kit.crash[0], AIR['crash'] * g)
        put(airR, pos, kit.crash[1], AIR['crash'] * g)
    for end, g, secs in ev.revcrash:
        c = kit.crash[2][:int(secs * FS)][::-1]
        c2 = kit.crash[3][:int(secs * FS)][::-1]
        put(airL, end - len(c), c, AIR['crash'] * 0.8 * g)
        put(airR, end - len(c2), c2, AIR['crash'] * 0.8 * g)
    for s, e, g in ev.risers:
        s, e = int(s), int(e)
        m = e - s
        t = np.arange(m) / m
        fc = 250 * (30 ** t)
        amp = (t ** 1.6) * g
        for side, ph in ((airL, 0.0), (airR, 0.5)):
            nz = rng.standard_normal(m)
            x = tvf(nz, fc, 2.0, 'bp')
            tone = saw(110 * 2 ** (2 * t) * (1.004 if ph else 0.996), ph)
            x = x + 0.25 * tvf(tone, fc * 1.5, 1.0)
            put(side, s, x * amp, AIR['riser'])
    if ev.scratches:
        src_t = tt(0.5)
        vowel = saw(np.full(len(src_t), 196.0)) + 0.6 * saw(np.full(len(src_t), 293.0))
        vowel = filt(vowel, 820, 4, 'bp') + 0.7 * filt(vowel, 1250, 5, 'bp') + 0.3 * filt(vowel, 2600, 6, 'bp')
        vowel *= np.clip(src_t / 0.01, 0, 1)
        for pos, g in ev.scratches:
            d = 0.36
            t = tt(d)
            # two strokes forward and back (a "chirp"), the fader cutting each stroke's end
            p = 0.13 * (0.5 - 0.5 * np.cos(2 * math.pi * 2 * t / d)) ** 1.3 * FS
            x = np.interp(p, np.arange(len(vowel)), vowel)
            fader = (np.sin(2 * math.pi * 4 * t / d) > -0.6).astype(float)
            x = sat(filt(x * smooth_gate(fader, 2), 300, 0.7, 'hp'), 1.5)
            put(airL, pos, x, AIR['scratch'] * g)
            put(airR, pos, x, AIR['scratch'] * g)

    beat = hp_dc(beat)
    return beat, hp_dc(airL) * air_scale, hp_dc(airR) * air_scale


# ================================================================== the run: "Fall Line"

# per chord: bass root, pad voicing, stab voicing
RUN_A = [(41, [53, 60, 68, 72], [65, 68, 72]),     # Fm
         (37, [49, 56, 65, 68], [65, 68, 73]),     # Db
         (39, [51, 58, 67, 70], [67, 70, 75]),     # Eb
         (36, [48, 55, 64, 67], [67, 72, 76])]     # C
# the breakdown: bass root, pad, the bell arpeggio's tones
RUN_C = [(37, [49, 56, 60, 65, 72], [61, 65, 68, 72, 77, 80]),   # Dbmaj7
         (44, [56, 60, 63, 70], [60, 63, 68, 70, 72, 75]),       # Ab add9
         (39, [51, 58, 65, 67], [63, 65, 67, 70, 75, 77]),       # Eb add9
         (36, [48, 55, 60, 65], [60, 65, 67, 72, 77, 79])]       # Csus4 (to C)
# the hook, two bars per chord: (step of 32, midi, sixteenths)
RUN_LEAD = [
    [(0, 72, 3), (3, 68, 3), (6, 72, 2), (8, 75, 4), (12, 77, 2), (14, 75, 2), (16, 72, 6), (22, 68, 2), (24, 70, 4), (28, 72, 4)],
    [(0, 77, 3), (3, 73, 3), (6, 77, 2), (8, 80, 4), (12, 79, 2), (14, 77, 2), (16, 75, 6), (22, 73, 2), (24, 72, 4), (28, 73, 4)],
    [(0, 79, 3), (3, 75, 3), (6, 79, 2), (8, 82, 4), (12, 80, 2), (14, 79, 2), (16, 77, 6), (22, 75, 2), (24, 74, 4), (28, 75, 4)],
    [(0, 76, 6), (6, 79, 2), (8, 84, 8), (16, 79, 4), (20, 76, 4), (24, 72, 2), (26, 76, 2), (28, 79, 4)],
]
# rolling bass, two bars: (step of 32, semitones from the root, sixteenths)
RUN_BASS = [(0, 0, 7), (10, 0, 3), (14, 12, 2), (16, 0, 6), (22, 0, 2), (26, -2, 2), (28, 0, 3)]
RUN_ACID = [(0, 0, 1, 0), (1, 0, 0, 0), (3, 12, 1, 0), (4, 0, 0, 1), (6, 7, 0, 0), (7, 10, 1, 0), (9, 0, 0, 0),
            (10, 12, 0, 1), (11, 15, 1, 0), (13, 0, 0, 0), (14, 7, 0, 1), (15, 12, 0, 0)]

HATS = [(s, 'h', 0.75 if s % 4 == 2 else (0.5 if s % 2 == 0 else 0.28)) for s in range(16)]
DNB_A = [(0, 'K', 1.0), (4, 'S', 1.0), (7, 'g', 0.5), (9, 'g', 0.4), (10, 'K', 0.9), (12, 'S', 1.0), (15, 'g', 0.55)]
DNB_B = [(0, 'K', 1.0), (2, 'K', 0.7), (4, 'S', 1.0), (7, 'g', 0.5), (10, 'K', 0.9), (11, 'g', 0.4), (12, 'S', 1.0),
         (13, 'g', 0.4), (14, 'S', 0.6), (6, 'o', 0.7)]
DNB_FILL = [(0, 'K', 1.0), (4, 'S', 1.0), (7, 'g', 0.5), (8, 'S', 0.55), (9, 'S', 0.45), (10, 'K', 0.9), (11, 'S', 0.6),
            (12, 'S', 0.85), (13, 'S', 0.7), (14, 'S', 0.9), (14.5, 'S', 0.8), (15, 'S', 1.0), (15.5, 'S', 0.9)]


def run_body(song):
    ev = Events()
    st = song.step
    for b in range(RUN_BARS):
        sec = b // 8
        inb = b % 8
        if sec == 2:
            root, padv, arp = RUN_C[inb // 2]
        else:
            root, padv, stabv = RUN_A[inb // 2]
        half = inb % 2           # first or second bar of the chord
        # drums
        if sec != 2:
            if inb == 7:
                pat = DNB_FILL
            elif sec == 0:
                pat = DNB_B if inb == 3 else DNB_A
            else:
                pat = DNB_B if inb % 2 else DNB_A
            for s, d, v in pat:
                ev.hits.append((song.at(b, s), d, v, 'kit'))
            for s, d, v in HATS:
                if inb == 7 and s >= 8:
                    continue
                if any(p[0] == s and p[1] == 'o' for p in pat):
                    continue
                ev.hits.append((song.at(b, s), d, v * (0.8 if sec == 3 else 1.0), 'kit'))
            if sec >= 1:
                for s in (2, 6, 10, 14):
                    ev.hits.append((song.at(b, s), 'r', 0.7 if sec == 3 else 0.45, 'kit'))
            if sec == 3:
                for s in range(16):
                    ev.hits.append((song.at(b, s), 'k', 0.8 if s % 2 else 0.45, 'kit'))
        else:
            if inb in (4, 5):        # half time, filtered
                for s, d, v in [(0, 'K', 1.0), (8, 'S', 0.9), (14, 'g', 0.5)] + [(s, 'h', 0.6) for s in range(0, 16, 2)]:
                    ev.hits.append((song.at(b, s), d, v, 'lp'))
                if inb == 5:
                    ev.hits.append((song.at(b, 10), 'K', 0.8, 'lp'))
            elif inb == 6:           # snare roll: eighths
                ev.hits.append((song.at(b, 0), 'K', 0.9, 'kit'))
                for i, s in enumerate(range(0, 16, 2)):
                    ev.hits.append((song.at(b, s), 'S', 0.3 + 0.04 * i, 'kit'))
            elif inb == 7:           # sixteenths, then thirty-seconds
                ev.hits.append((song.at(b, 0), 'K', 0.9, 'kit'))
                for s in range(12):
                    ev.hits.append((song.at(b, s), 'S', 0.6 + 0.025 * s, 'kit'))
                for s in range(8):
                    ev.hits.append((song.at(b, 12 + s / 2), 'S', 0.85 + 0.02 * s, 'kit'))
        # bass
        if sec != 2 and half == 0:
            for s, semi, ln in RUN_BASS:
                bb = b + s // 16
                ss = s % 16
                ev.bass.append((song.at(bb, ss), song.at(bb, ss) + ln * st - 0.012 * FS, root + semi, False))
        elif sec == 2 and half == 0 and inb >= 2:
            ev.sub.append((song.at(b, 0), song.at(b + 2, 0) - 0.05 * FS, root))
        # pads
        if half == 0:
            lvl = {0: 0.85, 1: 0.7, 2: 1.5, 3: 0.7}[sec]
            if sec == 2 and inb == 6:   # Csus4, then C
                ev.pads.append((song.at(b, 0), song.at(b + 1, 0), padv, lvl))
                ev.pads.append((song.at(b + 1, 0), song.at(b + 2, 0), [48, 55, 60, 64, 67], lvl))
            else:
                ev.pads.append((song.at(b, 0), song.at(b + 2, 0), padv, lvl))
        # stabs
        if sec != 2:
            steps = {0: (3, 10), 1: (3, 10, 14) if half else (3, 10), 3: (3, 6, 10, 13)}[sec]
            for i, s in enumerate(steps):
                ev.stabs.append((song.at(b, s), stabv, 0.85 if i == 0 else 0.7, 0.3 if i % 2 else 0.7, 0.26))
        # bells: the breakdown's arpeggio, quieter as the drums come back
        if sec == 2:
            order = [0, 2, 4, 1, 3, 5, 2, 4]
            if inb == 7:
                arp = [60, 64, 67, 72, 76, 79]     # the sus4 resolves to C
            for s in range(16):
                m = arp[order[(s + b * 16) % 8]]
                v = 0.75 if s % 4 == 0 else 0.5
                v *= 1.0 if inb < 6 else 0.6
                ev.bells.append((song.at(b, s), m, v, 0.2 if s % 2 else 0.8))
        # lead: the hook in B and D
        if sec in (1, 3) and half == 0:
            for s, m, ln in RUN_LEAD[inb // 2]:
                bb = b + s // 16
                ev.lead.append((song.at(bb, s % 16), song.at(bb, s % 16) + ln * st - 0.02 * FS, m, ln <= 2))
        # acid in D
        if sec == 3:
            for s, semi, ac, sl in RUN_ACID:
                p = song.at(b, s)
                ev.acid.append((p, p + st * (1.0 if sl else 0.6), root + 12 + semi, bool(sl), ac))
    # cymbals and impacts
    for b in (0, 8, 24):
        ev.crashes.append((song.at(b, 0), 1.0))
    for b in (0, 24):
        ev.booms.append((song.at(b, 0), 1.0))
    ev.crashes.append((song.at(16, 0), 0.8))
    ev.revcrash.append((song.at(24, 0), 1.0, 1.6))
    ev.risers.append((song.at(20, 0), song.at(24, 0), 1.0))
    return ev


def run_intro(song, n):
    """The countdown: a riser and a C major pad (the V of the drop) building for three seconds,
    a snare roll in the last two bars, everything cut at the drop."""
    ev = Events()
    st = song.step
    end = n
    ev.risers.append((0, end, 0.9))
    ev.revcrash.append((end, 1.0, 2.2))
    ev.pads.append((0, end, [48, 55, 60, 64, 67], 1.2))
    # 2 bars before the drop: quarters, eighths, sixteenths, thirty-seconds
    sched = [(i * 4, 0.25 + 0.03 * i) for i in range(4)] + [(16 + i * 2, 0.45 + 0.03 * i) for i in range(4)] + \
            [(24 + i, 0.6 + 0.03 * i) for i in range(4)] + [(28 + i / 2, 0.75 + 0.03 * i) for i in range(8)]
    start = end - 2 * song.bar_len
    for s, v in sched:
        ev.hits.append((int(start + s * st), 'S', v, 'kit'))
    ev.sub.append((start, end - int(0.02 * FS), 36))
    return ev


def run_auto(song, origin):
    """Automation curves for the run, indexed by timeline sample (origin: where body bar 0 is)."""
    L = song.L

    def auto(name, idx):
        pos = (idx - origin) % L
        bar = pos / song.bar_len
        if name == 'pad':
            # breakdown opens up; elsewhere a slow 8-bar sweep
            sweep = 0.5 - 0.5 * np.cos(2 * math.pi * bar / 8)
            fc = 900 + 1500 * sweep
            br = (bar >= 16) & (bar < 24)
            fc = np.where(br, 1200 + 3800 * np.clip((bar - 16) / 6, 0, 1), fc)
            if origin > 0:      # the intro (before the body) opens over its whole length
                pre = idx < origin
                fc = np.where(pre, 400 + 4000 * (idx / max(1, origin)) ** 2, fc)
            return fc
        if name == 'reese':
            return 520 + 900 * (0.5 - 0.5 * np.cos(2 * math.pi * bar / 2))
        if name == 'acid':
            return 300 + 900 * np.clip((bar - 24) / 8, 0, 1) ** 1.2 + 200 * (0.5 - 0.5 * np.cos(2 * math.pi * bar))
        if name == 'lead':
            return np.zeros_like(bar)
        if name == 'drumlp':
            return 500 + 2200 * np.clip((bar - 20) / 2, 0, 1) ** 2
        return np.zeros_like(bar)
    return auto


# ================================================================== the title: "Synergen"

TITLE_CHORDS = [41, 41, 37, 39, 41, 41, 37, 36]    # Fm Fm Db Eb Fm Fm Db C (bass roots)
TITLE_PADS = {41: [53, 60, 65, 68], 37: [49, 56, 61, 65], 39: [51, 58, 63, 67], 36: [48, 55, 60, 64]}
TITLE_STABS = {41: [65, 68, 72], 37: [65, 68, 73], 39: [67, 70, 75], 36: [67, 72, 76]}
BB_A = [(0, 'K', 1.0), (3, 'g', 0.35), (4, 'S', 1.0), (6, 'K', 0.6), (7, 'g', 0.4), (10, 'K', 0.95), (12, 'S', 1.0),
        (13, 'g', 0.35), (15, 'K', 0.5)]
BB_B = BB_A[:5] + [(8, 'S', 0.5), (10, 'S', 0.7), (11, 'S', 0.55), (12, 'S', 1.0), (13, 'K', 0.8), (14, 'S', 0.8), (15, 'S', 1.0)]
BB_FILL = [(0, 'K', 1.0), (4, 'S', 1.0), (6, 'K', 0.6), (8, 'S', 0.7), (9, 'S', 0.55), (10, 'K', 0.9), (10, 'S', 0.75),
           (11, 'S', 0.6), (12, 'S', 0.95), (13, 'S', 0.75), (14, 'S', 1.0), (14.5, 'S', 0.85), (15, 'S', 1.0), (15.5, 'S', 0.95)]
# acid per bar: (step, semitones from the root, accent, slide)
TITLE_ACID = [(0, 0, 1, 0), (2, 12, 0, 0), (3, 0, 0, 1), (5, 3, 0, 0), (6, 0, 1, 0), (8, 7, 0, 1), (9, 10, 0, 0),
              (11, 0, 1, 0), (12, 12, 0, 0), (14, 3, 0, 1), (15, 5, 0, 0)]


def title_bar(song, ev, b, chord_bar, fill=None, intro=False):
    root = TITLE_CHORDS[chord_bar]
    st = song.step
    pat = fill or BB_A
    for s, d, v in pat:
        ev.hits.append((song.at(b, s), d, v, 'lp' if intro else 'kit'))
    for s in range(16):
        if pat is not BB_A and s >= 8:
            break
        v = 0.7 if s % 2 == 0 else 0.35
        d = 'o' if s in (2, 10) and pat is BB_A else 'h'
        ev.hits.append((song.at(b, s), d, v, 'lp' if intro else 'kit'))
    if not intro:
        for s in (4, 12):
            ev.hits.append((song.at(b, s), 't', 0.7, 'kit'))
    for s, semi, ac, sl in TITLE_ACID:
        p = song.at(b, s)
        ev.acid.append((p, p + st * (1.0 if sl else 0.55), root + semi, bool(sl), ac))


def title_body(song):
    ev = Events()
    for b in range(TITLE_BARS):
        fill = BB_FILL if b == 7 else (BB_B if b == 3 else None)
        title_bar(song, ev, b, b, fill)
        root = TITLE_CHORDS[b]
        # pads, one per chord change
        if b in (0, 2, 3, 4, 6, 7):
            ln = 2 if b in (0, 4) else 1
            ev.pads.append((song.at(b, 0), song.at(b + ln, 0), TITLE_PADS[root], 0.8))
        # sub under the kicks
        for s, d, v in (fill or BB_A):
            if d == 'K':
                p = song.at(b, s)
                ev.sub.append((p, p + int(0.22 * FS), root))
    # brass stabs: a hit on the one, a dotted figure in the second half
    for b, steps in ((0, (0,)), (2, (0,)), (4, (0, 3, 6)), (6, (0, 3, 6)), (7, (0,))):
        for i, s in enumerate(steps):
            ev.stabs.append((song.at(b, s), TITLE_STABS[TITLE_CHORDS[b]], 1.0 if i == 0 else 0.8, 0.35 if i % 2 else 0.65, 0.4))
    ev.scratches.append((song.at(3, 8), 1.0))
    ev.scratches.append((song.at(7, 12), 1.0))
    ev.crashes.append((song.at(0, 0), 1.0))
    ev.crashes.append((song.at(4, 0), 0.7))
    ev.risers.append((song.at(6, 0), song.at(8, 0), 0.7))
    ev.revcrash.append((song.at(8, 0), 1.0, 1.4))
    return ev


def title_intro(song):
    ev = Events()
    title_bar(song, ev, 0, 7, None, intro=True)
    ev.revcrash.append((song.bar_len, 0.8, 1.2))
    ev.pads.append((0, song.bar_len, TITLE_PADS[41], 0.4))
    return ev


def title_auto(song, origin):
    L = song.L

    def auto(name, idx):
        pos = (idx - origin) % L
        bar = pos / song.bar_len
        if name == 'acid':
            fc = np.where(bar < 4, 380 + 500 * bar / 4, 700 + 900 * (bar - 4) / 4)
            if origin > 0:
                fc = np.where(idx < origin, 250 + 300 * idx / origin, fc)
            return fc
        if name == 'pad':
            return np.full(len(idx), 1300.0)
        if name == 'drumlp':     # the intro: the break opening up
            return np.where(idx < origin, 300 * 25 ** (idx / max(1, origin)), 9000.0)
        if name == 'reese':
            return np.full(len(idx), 600.0)
        return np.zeros(len(idx))
    return auto


# ================================================================== rendering a track

def render_track(song, body_ev, intro_ev, intro_len_sr, auto_fn, kit, title, delay_steps, air_scale):
    """Returns the three stems at SR (int arrays not yet scaled): intro + one loop."""
    L = song.L
    lead_delay = int(round(delay_steps * song.step))
    acid_delay = int(round(2 * song.step))
    tail = int(4 * FS)
    # the loop: two passes, keep the second (every tail from the end wraps into the start)
    ev = Events()
    ev.extend(body_ev)
    ev.extend(body_ev.shifted(L))
    n = 2 * L + tail
    stems = render(ev, n, kit, auto_fn(song, 0), lead_delay, acid_delay, title, air_scale=air_scale)
    body = [down(s[L:2 * L], True) for s in stems]
    # the intro: its own events, then cut where the loop begins
    ni = intro_len_sr * OS
    stems_i = render(intro_ev, ni, kit, auto_fn(song, ni), lead_delay, acid_delay, title, seed=11, air_scale=air_scale)
    intro = [down(s, False) for s in stems_i]
    return [np.concatenate([a, b]) for a, b in zip(intro, body)]


def mix_levels(stems):
    """Chooses each stem's storage gain and channel volumes so the console's mix
    (L = beat + airL, R = beat + airR) peaks at MASTER_PEAK."""
    beat, al, ar = stems
    peak = max(np.abs(beat + al).max(), np.abs(beat + ar).max())
    master = MASTER_PEAK / peak
    out = []
    for s in stems:
        g = STEM_PEAK / max(1e-9, np.abs(s).max())
        vol = int(round(256 * master / g))
        if vol > 255:
            vol = 255
            g = 256 * master / 255
        out.append((np.round(s * g * 32767).astype(np.int64), vol))
    return out


# ================================================================== sound effects

def circ_noise(n, shape, rng):
    f = np.fft.rfftfreq(n, 1 / SR)
    spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * shape(f)
    spec[0] = 0
    x = np.fft.irfft(spec, n)
    return x / x.std()


def periodic(n, cycles, phase=0.0):
    return np.sin(2 * math.pi * cycles * np.arange(n) / n + phase)


def wind_loop(n, seed, peaks):
    """Wind: a broad whoosh with gusts, and whistling resonances that come and go."""
    rng = np.random.default_rng(seed)

    def body(f):
        return 1 / (1 + (f / 650) ** 2) * (f / (f + 110)) ** 2

    def bright(f):
        return (f / (f + 900)) / (1 + (f / 3500) ** 2)

    def whistle(f):
        s = np.zeros_like(f)
        for c, bw, a in peaks:
            s += a * np.exp(-0.5 * ((f - c) / bw) ** 2)
        return s

    b = circ_noise(n, body, rng)
    h = circ_noise(n, bright, rng)
    w = circ_noise(n, whistle, rng)
    gust = 1 + 0.32 * periodic(n, 2, rng.uniform(0, 6)) + 0.16 * periodic(n, 5, rng.uniform(0, 6))
    air = np.clip(0.5 + 0.5 * periodic(n, 3, rng.uniform(0, 6)), 0, 1)
    whi = np.clip(0.3 + 0.7 * periodic(n, 4, rng.uniform(0, 6)), 0, 1) ** 2
    x = gust * (b + 0.45 * air * h) + 0.32 * whi * w
    return x / np.abs(x).max()


def hiss_loop(n, seed):
    """Snow under an edge: a bright granular hiss with sparser low crunches."""
    rng = np.random.default_rng(seed)

    def hi(f):
        return (f / (f + 2500)) ** 2 / (1 + (f / 7500) ** 4)

    def lo(f):
        return np.exp(-0.5 * ((f - 900) / 450) ** 2)

    a = circ_noise(n, hi, rng)
    b = circ_noise(n, lo, rng)
    ga = np.full(n, 0.55)
    gb = np.zeros(n)
    for count, tgt, lo_ms, hi_ms, amp in ((int(140 * n / SR), ga, 2, 9, 0.9), (int(35 * n / SR), gb, 6, 20, 1.0)):
        for _ in range(count):
            p = rng.integers(n)
            ln = int(rng.uniform(lo_ms, hi_ms) * SR / 1000)
            e = np.exp(-np.arange(ln) / (ln / 3)) * rng.uniform(0.3, 1.0) * amp
            i = (p + np.arange(ln)) % n
            tgt[i] += e
    x = a * ga + 0.6 * b * gb
    x = x + 0.25 * periodic(n, 2) * a * 0.3
    return x / np.abs(x).max()


def sfx_land():
    rng = np.random.default_rng(31)
    t = tt(0.55)
    f = 58 + 75 * np.exp(-t / 0.035)
    x = sine(f) * np.exp(-t / 0.09)
    x += 0.8 * filt(rng.standard_normal(len(t)), 500, 0.7) * np.exp(-t / 0.05)
    pff = filt(filt(rng.standard_normal(len(t)), 900, 0.7, 'hp'), 3500) * np.clip(t / 0.005, 0, 1) * np.exp(-t / 0.09)
    x = sat(filt(x, 1400) * 1.4, 1.6) + 0.6 * pff
    return x * np.clip((0.55 - t) / 0.05, 0, 1) * np.clip(t / 0.0008, 0, 1)


def sfx_gate():
    """Two bright bells a fourth apart (C6, F6) and a glassy shimmer."""
    t = tt(1.1)
    x = np.zeros(len(t))
    for when, m, a in ((0.0, 84, 0.8), (0.065, 89, 1.0)):
        s = bell_smp(m, 1.1 - when, ratio=2.0, index=1.6) * a
        put(x, int(when * FS), s)
        put(x, int(when * FS), bell_smp(m + 12, 0.5 - when / 2, ratio=3.5, index=1.0), 0.25 * a)
    return x


def sfx_miss():
    """A low double buzz, the second lower: 'eh-ehh'."""
    x = np.zeros(int(0.5 * FS))
    for when, f, ln in ((0.0, 104.0, 0.16), (0.21, 92.5, 0.25)):
        n = int(ln * FS)
        ff = np.full(n, f)
        s = pulse(ff, 0.5) + pulse(ff * 1.012, 0.3, 0.3) + 0.5 * saw(ff * 2)
        s = filt(s, 2400, 0.9) * env_ar(n, 0.004, 0.03, n - int(0.03 * FS))
        put(x, int(when * FS), sat(s * 0.6, 2.0))
    return x


def sfx_crash():
    """Impact, tumbling thumps and a snow scrape, plastic debris."""
    rng = np.random.default_rng(57)
    t = tt(1.5)
    n = len(t)
    x = np.zeros(n)
    hit = filt(rng.standard_normal(n), 6000) * np.exp(-t / 0.06)
    boom = sine(40 + 80 * np.exp(-t / 0.04)) * np.exp(-t / 0.22)
    x += 0.8 * hit + 1.0 * boom
    for when, a in ((0.24, 0.6), (0.43, 0.45), (0.58, 0.35), (0.80, 0.22)):
        k = int(0.25 * FS)
        tk = np.arange(k) / FS
        th = sine(50 + 50 * np.exp(-tk / 0.03)) * np.exp(-tk / 0.08) + 0.5 * filt(rng.standard_normal(k), 900) * np.exp(-tk / 0.04)
        put(x, int(when * FS), th, a)
    scrape = filt(filt(rng.standard_normal(n), 400, 0.7, 'hp'), 3000)
    jit = 0.6 + 0.4 * np.abs(filt(rng.standard_normal(n), 25))
    x += 0.5 * scrape * jit * np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.45)
    for when, m in ((0.02, 93.2), (0.07, 98.7), (0.31, 89.9), (0.5, 96.1)):
        k = int(0.18 * FS)
        tk = np.arange(k) / FS
        f = float(mtof(m))
        ping = np.sin(2 * math.pi * f * tk + 1.5 * np.exp(-tk / 0.02) * np.sin(2 * math.pi * f * 1.41 * tk)) * np.exp(-tk / 0.035)
        put(x, int(when * FS), ping, 0.18)
    return sat(x * np.clip((1.5 - t) / 0.2, 0, 1), 1.5)


def beep(m, dur, bright):
    t = tt(dur)
    f = float(mtof(m))
    x = np.sin(2 * math.pi * f * t) + bright * filt(pulse(np.full(len(t), f), 0.5), f * 3, 0.7) * 0.5
    return x * env_ar(len(t), 0.002, 0.04, len(t) - int(0.04 * FS)) * np.exp(-t / (dur * 1.5))


def sfx_beep():
    return beep(84, 0.2, 0.6)                    # C6


def sfx_go():
    x = beep(89, 0.75, 0.8) + 0.7 * beep(96, 0.75, 0.6) + 0.5 * beep(77, 0.75, 0.4)   # F6 C7 F5
    return x


def sfx_finish():
    """A rising F major arpeggio into a big supersaw chord, a crash and a sub drop."""
    rng = np.random.default_rng(77)
    n = int(2.8 * FS)
    x = np.zeros(n)
    for i, m in enumerate((65, 69, 72, 77, 81, 84)):
        put(x, int(i * 0.05 * FS), bell_smp(m, 0.6, ratio=2.0, index=1.2), 0.45)
    s0 = int(0.3 * FS)
    m = n - s0
    ch = np.zeros(m)
    notes = (53, 65, 69, 72, 77, 79)
    for nt in notes:
        for v in supersaw(nt, m, rng):
            ch += v
    ch /= math.sqrt(len(notes) * 5)
    tm = np.arange(m) / FS
    ch = tvf(ch, 600 + 6000 * np.exp(-tm / 0.5), 1.0) * env_ar(m, 0.004, 1.0, int(1.2 * FS))
    put(x, s0, sat(ch * 0.7, 1.3))
    kit_rng = np.random.default_rng(78)
    put(x, s0, cymbal_smp(kit_rng, dur=2.4), 0.3)
    put(x, s0, boom_smp(kit_rng, 1.6), 0.55)
    return x


def sfx_menu():
    t = tt(0.07)
    f = 1800 + 700 * np.clip(t / 0.02, 0, 1)
    return sine(f) * np.exp(-t / 0.022) * np.clip(t / 0.0008, 0, 1)


# per sound: name, render, its peak in the game (dB of full scale; the music peaks at -6), reverb send
ONE_SHOTS = [
    ('land', sfx_land, -7, 0),
    ('gate', sfx_gate, -10, 1),
    ('miss', sfx_miss, -15, 0),
    ('crash', sfx_crash, -7, 1),
    ('beep', sfx_beep, -12, 1),
    ('go', sfx_go, -9, 1),
    ('finish', sfx_finish, -6, 1),
    ('menu', sfx_menu, -15, 0),
]
WIND_A_LEN = 2362 * BLK      # 66,136 samples, 3.0 s
WIND_B_LEN = 2914 * BLK      # 81,592 samples, 3.7 s (the two never line up the same way twice running)
HISS_LEN = 1575 * BLK        # 44,100 samples, 2.0 s
# per loop: its RMS at full level (dB of full scale, on its louder side; the music is about -19)
LOOPS = [
    ('wind_a', lambda: wind_loop(WIND_A_LEN, 101, [(820, 50, 1.0), (1650, 80, 0.5), (2500, 140, 0.25)]), -26, 0),
    ('wind_b', lambda: wind_loop(WIND_B_LEN, 202, [(760, 45, 1.0), (1520, 90, 0.6), (2900, 160, 0.2)]), -26, 0),
    ('hiss', lambda: hiss_loop(HISS_LEN, 303), -26, 0),
]
LEAD_IN = 2 * BLK


# ================================================================== output

def _encode(args):
    x, loop = args
    return mei_adpcm.encode(x, loop)


def write_wav(path, ch):
    """ch: one or two int16-range arrays."""
    data = np.stack([np.clip(np.round(c), -32768, 32767).astype('<i2') for c in ch], axis=1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(len(ch))
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def akr_array(name, typ, vals, per_line):
    lines = []
    for i in range(0, len(vals), per_line):
        lines.append(', '.join(str(v) for v in vals[i:i + per_line]))
    return 'const %s: [%d]%s = [%s]\n' % (name, len(vals), typ, ',\n    '.join(lines))


def build(preview, quick=False):
    print('rendering the title...')
    t_song = Song(TITLE_BEAT, TITLE_BARS, TITLE_SWING)
    t_kit = Kit(5, big=True)
    t_stems = render_track(t_song, title_body(t_song), title_intro(t_song), TITLE_BEAT * 4, title_auto, t_kit, True, 3, 1.6)
    print('rendering the run...')
    r_song = Song(RUN_BEAT, RUN_BARS)
    r_kit = Kit(9)
    r_stems = render_track(r_song, run_body(r_song), run_intro(r_song, RUN_INTRO * OS), RUN_INTRO, run_auto, r_kit, False, 3, 1.1)

    tracks = []      # (name, channels, intro samples, total samples, [(int16 data, vol)])
    for name, stems, intro, chans in (('title', t_stems, TITLE_BEAT * 4, (3, 4, 5)),
                                      ('run', r_stems, RUN_INTRO, (0, 1, 2))):
        n = len(stems[0])
        assert n % BLK == 0 and intro % BLK == 0, (name, n, intro)
        tracks.append((name, chans, intro, n, mix_levels(stems)))

    print('rendering the sound effects...')
    sfx = []         # (name, int data, loop start or -1, volume, reverb)
    for name, fn, level, rev in ONE_SHOTS:
        x = down(fn(), False)
        x = x / np.abs(x).max() * STEM_PEAK
        vol = min(255, int(round(256 * 10 ** (level / 20) / STEM_PEAK)))
        x = np.concatenate([x, np.zeros(-len(x) % BLK)])
        sfx.append((name, np.round(x * 32767).astype(np.int64), -1, vol, rev))
    for name, fn, level, rev in LOOPS:
        x = fn() * STEM_PEAK
        vol = min(255, int(round(256 * 10 ** (level / 20) / np.sqrt((x ** 2).mean()))))
        x = np.concatenate([x[-LEAD_IN:], x])
        sfx.append((name, np.round(x * 32767).astype(np.int64), LEAD_IN, vol, rev))

    if quick:      # unencoded previews only, nothing written to the cart
        os.makedirs(preview, exist_ok=True)
        names = ('beat', 'airL', 'airR')
        for name, chans, intro, n, st in tracks:
            for si, (data, vol) in enumerate(st):
                write_wav(os.path.join(preview, '%s_%s.wav' % (name, names[si])), [data])
            beat, al, ar = [(d * v) >> 8 for d, v in st]
            two = lambda x: np.concatenate([x, x[intro:]])
            write_wav(os.path.join(preview, '%s.wav' % name), [two(beat + al), two(beat + ar)])
        for name, data, loop, vol, rev in sfx:
            write_wav(os.path.join(preview, 'sfx_%s.wav' % name), [data * vol >> 8])
        return

    print('encoding...')
    jobs = []
    for name, chans, intro, n, st in tracks:
        for data, vol in st:
            jobs.append((data, intro))
    for name, data, loop, vol, rev in sfx:
        jobs.append((data, loop if loop >= 0 else None))
    with ProcessPoolExecutor() as ex:
        enc = list(ex.map(_encode, jobs))

    os.makedirs(AUD, exist_ok=True)
    mbank = bytearray()
    stem_rows = []
    k = 0
    stem_names = ('beat', 'air L', 'air R')
    for ti, (name, chans, intro, n, st) in enumerate(tracks):
        for si, (data, vol) in enumerate(st):
            blob = enc[k]
            k += 1
            vl, vr = (vol, vol) if si == 0 else ((vol, 0) if si == 1 else (0, vol))
            stem_rows.append((chans[si], len(mbank), n, intro, vl, vr, 1 if si else 0, name, stem_names[si]))
            mbank += blob
    sbank = bytearray()
    sfx_rows = []
    for name, data, loop, vol, rev in sfx:
        blob = enc[k]
        k += 1
        sfx_rows.append((name, len(sbank), len(data), loop, vol, rev))
        sbank += blob
    with open(os.path.join(AUD, 'music.adp'), 'wb') as f:
        f.write(mbank)
    with open(os.path.join(AUD, 'sfx.adp'), 'wb') as f:
        f.write(sbank)

    # ---- mu_data.akr
    o = []
    o.append('// Generated by tools/gen_fallline_audio.py - do not edit.\n')
    o.append('// Fall Line\'s music stems and sound effects (audio/music.adp, audio/sfx.adp), read by music.akr\n')
    o.append('// and sfx.akr.\n\n')
    o.append('embed MU_BANK: u8 = "audio/music.adp"\n')
    o.append('embed SFX_BANK: u8 = "audio/sfx.adp"\n\n')
    o.append('const MU_REVERB = %d                // the console reverb preset (space)\n' % REVERB)
    o.append('const MU_WET = %d                  // its wet level, both sides\n' % REV_WET)
    o.append('const MU_REV_DECAY = %d           // its feedback x n / 256\n\n' % REV_DECAY)
    o.append('// The tracks: %s.\n' % ', '.join('%d %s (%.1f s intro, %.1f s loop)' % (i, t[0], t[2] / SR, (t[3] - t[2]) / SR)
                                               for i, t in enumerate(tracks)))
    o.append('const MU_TRACKS = %d\n' % len(tracks))
    o.append('const MU_STEMS = 3                  // per track: beat (mono, dry), air left, air right (to the reverb)\n')
    o.append('// per stem (track x MU_STEMS + stem): channel, byte offset in MU_BANK, samples, loop start,\n')
    o.append('// left volume, right volume, reverb send\n')
    vals = []
    for row in stem_rows:
        vals += list(row[:7])
    o.append(akr_array('MU_STEM', 's32', vals, 7))
    o.append('\n// Sound effects: an index into SFX for each.\n')
    for i, row in enumerate(sfx_rows):
        o.append('const SFX_%s = %d\n' % (row[0].upper(), i))
    o.append('const SFX_COUNT = %d\n' % len(sfx_rows))
    o.append('// per sound: byte offset in SFX_BANK, samples, loop start (-1: a one-shot), volume, reverb send\n')
    vals = []
    for row in sfx_rows:
        vals += list(row[1:6])
    o.append(akr_array('SFX', 's32', vals, 5))
    with open(os.path.join(CART, 'mu_data.akr'), 'w') as f:
        f.write(''.join(o))

    print('music.adp %d bytes, sfx.adp %d bytes' % (len(mbank), len(sbank)))
    for r in stem_rows:
        print('  %-6s %-6s ch %2d  %8d samples (%.2f s), loop at %d, vol %d/%d' % (r[7], r[8], r[0], r[2], r[2] / SR, r[3], r[4], r[5]))

    if preview:
        os.makedirs(preview, exist_ok=True)
        k = 0
        for name, chans, intro, n, st in tracks:
            dec = []
            for si, (data, vol) in enumerate(st):
                d = mei_adpcm.decode(enc[k], n).astype(np.int64)
                k += 1
                write_wav(os.path.join(preview, '%s_%s.wav' % (name, stem_names[si].replace(' ', ''))), [d])
                dec.append((d, vol))
            # as the console mixes it: (s x vol) >> 8 per channel, the loop twice
            beat, al, ar = [(d * v) >> 8 for d, v in dec]
            two = lambda x: np.concatenate([x, x[intro:]])
            write_wav(os.path.join(preview, '%s.wav' % name), [two(beat + al), two(beat + ar)])
        for name, data, loop, vol, rev in sfx:
            d = mei_adpcm.decode(enc[k], len(data)).astype(np.int64)
            k += 1
            if loop >= 0:
                d = np.concatenate([d, d[loop:], d[loop:]])
            write_wav(os.path.join(preview, 'sfx_%s.wav' % name), [d * vol >> 8])
        print('previews in', preview)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--preview', metavar='DIR', help='also write WAVs to listen to')
    a = ap.parse_args()
    build(a.preview, bool(os.environ.get('FL_QUICK')) and bool(a.preview))


if __name__ == '__main__':
    main()
