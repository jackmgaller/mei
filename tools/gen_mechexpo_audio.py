#!/usr/bin/env python3
"""Mech Expo 2000's music and sound effects, synthesised from nothing (no samples).

Music. Two original tracks in E minor, Y2K electronic for a mech fighter at a trade show:
  fight  "Live Demo": drum and bass with a big-beat section, 174.03 bpm, a 4-bar intro (5.5 s:
         a filtered break opening up, a riser and a snare roll into the drop), then a 48-bar loop
         (66.2 s, longer than a 60-second round): A the drop (rolling reese, chord stabs, metal
         clangs), B the hook (a hoover lead), C big beat (half-time, a fat dirty break, an acid
         bass, robot vowel chops, scratches), D the breakdown (glass arpeggio, vowel choir, a
         filtered build and a snare roll), E the second drop (the hook and the acid), F the
         finale (stabs, chops, ride, fills), which runs back into A.
  menu   "Showfloor": big beat, 128.05 bpm with swung sixteenths, a one-bar filtered intro and a
         16-bar loop (30.0 s): a fat swung break, an electric piano with an auto-pan, a plucked
         funk bass, then brass stabs, vowel chops, an acid line and scratches.
Each track is three ADPCM stems that the console loops by itself (the loop is in the samples, so
it never drifts and costs the CPU nothing): `beat`, the drums and bass in mono, dry, and `air L`
and `air R`, a stereo pair (pads, stabs, leads, chops, cymbals, risers) sent to the reverb. A
bar is a whole number of 28-sample ADPCM blocks; the loop is rendered twice and the second pass
kept, so every tail that crosses the loop point wraps into its start.

Sound effects, one-shots: four hits (light to crushing), the block's clang, chip, a swing for
each mech (the Hero's sword; the Double-blade Hero's antimatter blades), grab, throw (the slam),
grab break, landing, footstep, meter full, super, KO (impact, power-down, arcs, the crowd), round
(a PA chime and the horn), the three menu sounds and the unlock fanfare.

The reverb is the console's: preset 3 (hall) with its decay shortened a little, the demo hangar.

Writes carts/mechexpo/audio/music.adp, carts/mechexpo/audio/sfx.adp and carts/mechexpo/mu_data.akr
(the tables carts/mechexpo/music.akr and sfx.akr read).
    python3 tools/gen_mechexpo_audio.py [--preview DIR]
--preview writes fight.wav and menu.wav (the stems decoded and mixed as the console mixes them,
without the reverb; the intro, then the loop twice so its seam can be heard), the stems, every
sound effect, and fight_sfx.wav (the fight's first 20 seconds with a volley of effects over it,
for the balance). It prints levels, clipping and the loop seams. With MX_QUICK=1 in the
environment, --preview writes unencoded WAVs only and nothing in the cart. Needs NumPy and SciPy.
"""
import argparse, math, os, sys, wave
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'mechexpo')
AUD = os.path.join(CART, 'audio')

SR = 22050                 # the console's rate
OS = 2                     # everything is rendered at twice that, then filtered down
FS = SR * OS
BLK = 28                   # samples in an ADPCM block

# the console reverb
REVERB = 3                 # hall
REV_WET = 120
REV_DECAY = 220            # its feedback x 220/256: a little shorter than the hall's own

# timing, in samples at SR (a beat must be a multiple of 7, so a bar is whole blocks)
FIGHT_BEAT = 7602          # 174.03 bpm; bar 30,408 = 1,086 blocks
FIGHT_BARS = 48
FIGHT_INTRO_BARS = 4
MENU_BEAT = 10332          # 128.05 bpm; bar 41,328 = 1,476 blocks
MENU_BARS = 16
MENU_SWING = 0.14          # odd sixteenths late by this much of a sixteenth

MASTER_PEAK = 0.40         # the music's stereo mix peaks here (-8 dBFS): room for the effects
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
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / FS, np.shape(freq)).copy()
    return (ph0 + np.cumsum(dt) - dt) % 1.0, dt


def saw(freq, ph0=0.0):
    """Band-limited (PolyBLEP) saw, freq per sample."""
    ph, dt = _phase(freq, ph0)
    return 2 * ph - 1 - _blep(ph, dt)


def pulse(freq, pw=0.5, ph0=0.0):
    """Band-limited pulse; pw may follow the signal (an array)."""
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


def vdelay(x, delay):
    """x delayed by `delay` samples (per sample, fractional)."""
    i = np.arange(len(x)) - delay
    return np.interp(i, np.arange(len(x)), x, left=0.0, right=0.0)


def chorus(x, rate, depth_ms, base_ms, phase):
    lfo = np.sin(2 * math.pi * rate * np.arange(len(x)) / FS + phase)
    return vdelay(x, (base_ms + depth_ms * lfo) * FS / 1000)


def down(x, circular):
    """FS to SR; a circular signal is filtered across its own seam."""
    if circular:
        p = 4000
        e = np.concatenate([x[-p:], x, x[:p]])
        return signal.resample_poly(e, 1, OS)[p // OS:p // OS + len(x) // OS]
    return signal.resample_poly(x, 1, OS)[:len(x) // OS]


def hp_dc(x, f=25.0):
    return filt(x, f, 0.707, 'hp')


def env_ar(n, att, rel, gate_n):
    """Attack, hold for gate_n samples, release; n samples long."""
    t = np.arange(n)
    a = np.clip(t / max(1, att * FS), 0, 1)
    r = np.clip(1 - (t - gate_n) / max(1, rel * FS), 0, 1)
    return a * np.where(t < gate_n, 1.0, r)


def fade(x, att=0.0008, rel=0.03):
    """A click-free start and end."""
    n = len(x)
    t = np.arange(n) / FS
    return x * np.clip(t / att, 0, 1) * np.clip((n / FS - t) / rel, 0, 1)


def noise(rng, n):
    return rng.standard_normal(n)


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
    if notes:
        pitch[:max(0, int(notes[0][0]))] = notes[0][2]
    return pitch, gate, onsets


# ================================================================== drums

def kick_smp(rng, f0=170, f1=50, tp=0.03, dec=0.2, drive=2.2, click=0.3, dur=0.55):
    t = tt(dur)
    f = f1 + (f0 - f1) * np.exp(-t / tp)
    body = sine(f) * np.exp(-t / dec) * np.clip(t / 0.0012, 0, 1)
    body *= np.clip((dur - t) / 0.03, 0, 1)
    ck = filt(noise(rng, len(t)), 2500, 0.7, 'hp') * np.exp(-t / 0.003) * click
    return sat(body + ck, drive)


def snare_smp(rng, tone=190, dec_n=0.15, dec_t=0.06, crack=0.45, bright=9000, drive=1.6, dur=0.5):
    dur = max(dur, 6 * dec_n)
    t = tt(dur)
    f = tone * (1 + 0.3 * np.exp(-t / 0.008))
    tonal = (sine(f) + 0.45 * sine(f * 1.73)) * np.exp(-t / dec_t)
    nz = filt(noise(rng, len(t)), 1500, 0.6, 'hp')
    nz = filt(nz, bright, 0.7, 'lp') * np.exp(-t / dec_n)
    ck = filt(noise(rng, len(t)), 3500, 0.7, 'hp') * np.exp(-t / 0.004) * crack
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
    x = 0.55 * metal(base, len(t), rng) + 0.7 * noise(rng, len(t))
    x = filt(filt(x, hp, 0.8, 'hp'), hp * 0.9, 0.7, 'hp')
    env = np.exp(-t / dec) * np.clip(t / 0.0005, 0, 1) * np.clip((dur - t) / (dur / 3), 0, 1)
    return x * env / 0.6


def cymbal_smp(rng, dec=0.9, dur=2.6, hp=3200, base=300, bell=0.0):
    dur = max(dur, 4.5 * dec)
    t = tt(dur)
    x = 0.5 * metal(base, len(t), rng) + 0.8 * noise(rng, len(t))
    x = filt(filt(x, hp, 0.7, 'hp'), 10500, 0.7, 'lp')
    burst = filt(noise(rng, len(t)), 2000, 0.7, 'hp') * np.exp(-t / 0.02)
    env = np.exp(-t / dec) * np.clip(t / 0.001, 0, 1) * np.clip((dur - t) / (dur / 3), 0, 1)
    y = (x + 0.6 * burst) * env
    if bell:
        y += bell * (np.sin(2 * math.pi * 2350 * t) + 0.6 * np.sin(2 * math.pi * 3720 * t)) * np.exp(-t / (dec * 0.6))
    return y / 0.7


def shaker_smp(rng, dur=0.09):
    t = tt(dur)
    x = filt(filt(noise(rng, len(t)), 5200, 0.9, 'hp'), 9500, 0.7, 'lp')
    return x * np.clip(t / 0.008, 0, 1) * np.exp(-t / 0.03)


def psst_smp(rng, dur=0.22):
    """An open hat that is half a hydraulic hiss: the hangar's own percussion."""
    t = tt(dur)
    x = filt(filt(noise(rng, len(t)), 3800, 1.2, 'bp'), 2500, 0.7, 'hp') + 0.4 * hat_smp(rng, 0.08, dur)[:len(t)]
    return x * np.clip(t / 0.012, 0, 1) * np.exp(-t / 0.07) * np.clip((dur - t) / 0.04, 0, 1)


def boom_smp(rng, dur=1.4):
    """A sub drop for a downbeat impact."""
    t = tt(dur)
    f = 36 + 70 * np.exp(-t / 0.09)
    x = sine(f) * np.exp(-t / 0.45) * np.clip(t / 0.002, 0, 1)
    x += 0.4 * filt(noise(rng, len(t)), 300, 0.7, 'lp') * np.exp(-t / 0.08)
    return sat(x * np.clip((dur - t) / 0.2, 0, 1), 1.8)


class Kit:
    """A few takes of every drum, chosen at random per hit so repeats are not identical. K and S
    are the drum and bass kit; B and X the big-beat kick and snare (fatter, longer, dirtier)."""
    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        self.rng = np.random.default_rng(seed + 1)
        self.s = {
            'K': [kick_smp(rng, f0=175, f1=54) for _ in range(3)],
            'S': [snare_smp(rng) for _ in range(4)],
            'B': [kick_smp(rng, f0=150, f1=52, tp=0.045, dec=0.28, drive=3.4, click=0.45, dur=0.7) for _ in range(3)],
            'X': [snare_smp(rng, tone=175, dec_n=0.26, dec_t=0.09, crack=0.65, bright=7500, drive=2.8, dur=0.65) for _ in range(4)],
        }
        self.s['g'] = [filt(snare_smp(rng, dec_n=0.07, crack=0.25), 5000) for _ in range(4)]
        self.s['h'] = [hat_smp(rng) for _ in range(6)]
        self.s['o'] = [hat_smp(rng, dec=0.18, dur=0.5, hp=5500) for _ in range(3)]
        self.s['p'] = [psst_smp(rng) for _ in range(3)]
        self.s['r'] = [cymbal_smp(rng, dec=0.45, dur=1.2, hp=2800, base=470, bell=0.35) for _ in range(3)]
        self.s['k'] = [shaker_smp(rng) for _ in range(6)]
        self.crash = [cymbal_smp(rng) for _ in range(4)]
        self.boom = boom_smp(rng)
        self.gain = {'K': 1.0, 'S': 0.8, 'B': 1.0, 'X': 0.85, 'g': 0.42, 'h': 0.24, 'o': 0.2, 'p': 0.3,
                     'r': 0.2, 'k': 0.16}

    def hit(self, name):
        takes = self.s[name]
        return takes[self.rng.integers(len(takes))]


# ================================================================== instruments

def supersaw(midi, n, rng, detunes=(-0.16, -0.07, 0.0, 0.07, 0.16)):
    f = mtof(midi)
    return [saw(np.full(n, f * 2 ** (d / 12)), rng.uniform()) for d in detunes]


def stab_smp(notes, dur, rng, bright=1.0):
    n = int(dur * FS)
    x = np.zeros(n)
    for m in notes:
        for s in supersaw(m, n, rng, (-0.1, 0.0, 0.1)):
            x += s
        x += 0.5 * pulse(np.full(n, mtof(m - 12)), 0.5, rng.uniform())
    x /= len(notes) * 2.0
    t = np.arange(n) / FS
    fc = 800 + 6500 * bright * np.exp(-t / 0.09)
    y = tvf(x, fc, 1.6, 'lp', 32)
    return sat(y * env_ar(n, 0.002, 0.05, n - int(0.05 * FS)) * np.exp(-t / 0.25), 1.3)


def bell_smp(midi, dur=0.9, ratio=3.5, index=2.2):
    """An FM bell: glassy, quick."""
    t = tt(dur)
    f = float(mtof(midi))
    mod = index * np.exp(-t / 0.12) * np.sin(2 * math.pi * f * ratio * t)
    x = np.sin(2 * math.pi * f * t + mod) + 0.25 * np.sin(2 * math.pi * f * 2 * t) * np.exp(-t / 0.08)
    return x * np.exp(-t / 0.28) * np.clip(t / 0.0015, 0, 1) * np.clip((dur - t) / 0.05, 0, 1)


def epiano_smp(midi, dur, vel=1.0):
    """An FM electric piano: a soft tine attack over a round tone."""
    t = tt(dur + 0.4)
    f = float(mtof(midi))
    idx = (0.6 + 1.6 * vel) * np.exp(-t / 0.35) + 0.25
    x = np.sin(2 * math.pi * f * t + idx * np.sin(2 * math.pi * f * t))
    x += 0.25 * vel * np.sin(2 * math.pi * f * 14.0 * t) * np.exp(-t / 0.02)
    env = np.exp(-t / 1.4) * np.clip(t / 0.002, 0, 1) * env_ar(len(t), 0.0, 0.25, int(dur * FS))
    return x * env


VOWELS = {'a': ((800, 1.0), (1150, 0.6), (2900, 0.25)),
          'o': ((450, 1.0), (800, 0.55), (2830, 0.15)),
          'e': ((400, 1.0), (1700, 0.5), (2600, 0.3)),
          'u': ((325, 1.0), (700, 0.3), (2530, 0.1))}


def vox_smp(notes, dur, vowel, rng, to_vowel=None):
    """A robot choir chop: saws through three formants (sliding to another vowel if given)."""
    n = int(dur * FS)
    t = np.arange(n) / FS
    src = np.zeros(n)
    for m in notes:
        f = mtof(m) * (1 + 0.004 * np.sin(2 * math.pi * 5.2 * t + rng.uniform(0, 6)))
        src += saw(f, rng.uniform()) + 0.5 * pulse(f * 1.003, 0.4, rng.uniform())
    src /= len(notes)
    y = np.zeros(n)
    for k in range(3):
        f0, a0 = VOWELS[vowel][k]
        if to_vowel:
            f1 = VOWELS[to_vowel][k][0]
            fc = f0 + (f1 - f0) * np.clip(t / dur, 0, 1)
            y += a0 * tvf(src, fc, 6.0, 'bp', 32)
        else:
            y += a0 * filt(src, f0, 6.0, 'bp')
    y = sat(y * 2.0, 1.4)
    return y * env_ar(n, 0.006, 0.04, n - int(0.04 * FS))


def clang_smp(rng, f0=330.0, dur=1.2, dec=0.35, bright=1.0):
    """A struck steel plate: inharmonic modes, a hard transient."""
    t = tt(dur)
    x = np.zeros(len(t))
    for r, a, d in ((1.0, 1.0, 1.0), (1.47, 0.7, 0.8), (2.09, 0.55, 0.6), (2.76, 0.45, 0.5),
                    (3.53, 0.35 * bright, 0.4), (4.41, 0.3 * bright, 0.3), (5.97, 0.22 * bright, 0.22)):
        f = f0 * r * rng.uniform(0.99, 1.01)
        x += a * np.sin(2 * math.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / (dec * d))
    x += 0.8 * bright * filt(noise(rng, len(t)), 3000, 0.7, 'hp') * np.exp(-t / 0.004)
    return fade(x * np.clip(t / 0.0004, 0, 1), 0.0004, 0.1)


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


SPANS = ('bass', 'sub', 'acid', 'lead', 'pads', 'risers', 'pluck', 'epiano')


class Events:
    """What a timeline plays: everything in samples at FS from the timeline's start."""
    def __init__(self):
        self.hits = []        # (pos, drum, velocity, bus: 'kit' | 'lp')
        self.bass = []        # (start, end, midi, slide): the reese
        self.sub = []         # (start, end, midi)
        self.acid = []        # (start, end, midi, slide, accent)
        self.lead = []        # (start, end, midi, slide): the hoover
        self.pads = []        # (start, end, notes, level)
        self.pluck = []       # (start, end, midi, slide): the funk bass
        self.epiano = []      # (start, end, notes, velocity)
        self.stabs = []       # (pos, notes, velocity, pan 0..1, length s)
        self.vox = []         # (pos, notes, velocity, pan, length s, vowel, to vowel or None)
        self.bells = []       # (pos, midi, velocity, pan)
        self.clangs = []      # (pos, f0, velocity, pan)
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
                if k in SPANS:
                    item[1] += d
                out.append(tuple(item))
            setattr(e, k, out)
        return e

    def extend(self, other):
        for k, v in other.__dict__.items():
            getattr(self, k).extend(v)


# the air parts' levels, against the beat stem
AIR = {'pad': 1.0, 'stab': 1.3, 'lead': 0.9, 'acid': 0.8, 'bell': 0.9, 'vox': 1.0, 'clang': 0.5,
       'epiano': 1.1, 'crash': 0.3, 'riser': 0.7, 'scratch': 0.9}


def pan_lr(p):
    return math.cos(p * math.pi / 2), math.sin(p * math.pi / 2)


def render(ev, n, kit, auto, delay, beat_len, menu=False, seed=7):
    """Renders events into (beat, airL, airR) at FS, n samples. auto(name, idx) gives the
    automation curves (cutoffs) at timeline sample indices; delay is the ping-pong's time and
    beat_len a beat's (both samples at FS)."""
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    airL = np.zeros(n)
    airR = np.zeros(n)

    # ---- drums
    kitbus = np.zeros(n)
    lpbus = np.zeros(n)
    kick_on = []
    for pos, d, vel, bus in ev.hits:
        tgt = kitbus if bus == 'kit' else lpbus
        jitter = 0 if d in 'KSBX' else int(rng.normal(0, 0.0012) * FS)
        put(tgt, pos + jitter, kit.hit(d), kit.gain[d] * vel)
        if d in 'KB':
            kick_on.append(int(pos))
    room_t = tt(0.32)
    ir = filt(noise(rng, len(room_t)), 6000) * np.exp(-room_t / (0.085 if menu else 0.065))
    ir[0] = 0
    ir /= np.sqrt((ir ** 2).sum())
    room = signal.fftconvolve(kitbus, ir)[:n]
    kitbus = kitbus + (0.22 if menu else 0.15) * room
    if lpbus.any():
        kitbus += tvf(lpbus, auto('drumlp', idx), 0.9)
    kitbus = sat(kitbus, 2.4 if menu else 1.8) * 0.88
    for pos, g in ev.booms:
        put(kitbus, pos, kit.boom, 0.45 * g)

    # sidechain: the bass ducks under each kick
    pump = 1 - 0.55 * decays(kick_on, n, 0.07)

    # ---- bass: a reese (two detuned saws, filtered, distorted) and a sine sub
    bassbus = np.zeros(n)
    if ev.bass:
        pitch, gate, _ = mono_line(ev.bass, n, 0.03)
        g = smooth_gate(gate, 4)
        f = mtof(pitch)
        lfo = 0.5 + 0.5 * np.sin(2 * math.pi * idx / (FS * 2.8))
        x = saw(f * 2 ** (-(0.10 + 0.08 * lfo) / 12)) + saw(f * 2 ** ((0.10 + 0.08 * lfo) / 12), 0.37) + 0.5 * saw(f * 2, 0.71)
        x = tvf(x, auto('reese', idx), 1.3)
        x = filt(sat(x * 0.6, 2.4), 70, 0.7, 'hp')
        bassbus += 0.5 * x * g + 0.28 * sine(f) * g
    if ev.sub:
        pitch, gate, _ = mono_line([(s, e, m, False) for s, e, m in ev.sub], n)
        g = smooth_gate(gate, 12)
        bassbus += 0.4 * sine(mtof(pitch)) * g
    if ev.pluck:      # the menu's funk bass: saw and square, an enveloped low-pass, short
        pitch, gate, onsets = mono_line(ev.pluck, n, 0.04)
        g = smooth_gate(gate, 3)
        f = mtof(pitch)
        fenv = decays(onsets, n, 0.09)
        x = saw(f) + 0.7 * pulse(f, 0.35, 0.3)
        x = tvf(x, 180 + 2200 * fenv, 2.2)
        bassbus += 0.55 * sat(x * g * 0.9, 1.8) + 0.3 * sine(f) * g
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
                cl, cr = pan_lr(p)
                put(pl, s, v * env, cl / math.sqrt(k))
                put(pr, s, v * env, cr / math.sqrt(k))
        fc = auto('pad', idx)
        airL += AIR['pad'] * tvf(pl, fc, 0.8)
        airR += AIR['pad'] * tvf(pr, fc, 0.8)

    # ---- electric piano, auto-panned once a beat
    if ev.epiano:
        ep = np.zeros(n)
        for s, e, notes, vel in ev.epiano:
            for i, m in enumerate(notes):
                put(ep, s + int(i * 0.004 * FS), epiano_smp(m, (e - s) / FS, vel), vel / math.sqrt(len(notes)))
        ap = 0.5 + 0.38 * np.sin(2 * math.pi * idx / beat_len)
        airL += AIR['epiano'] * ep * np.cos(ap * math.pi / 2)
        airR += AIR['epiano'] * ep * np.sin(ap * math.pi / 2)

    # ---- stabs, with a ping-pong
    if ev.stabs:
        st = np.zeros(n)
        stl = np.zeros(n)
        str_ = np.zeros(n)
        for pos, notes, vel, pan, ln in ev.stabs:
            x = stab_smp(notes, ln, rng, 0.6 + 0.4 * vel)
            cl, cr = pan_lr(pan)
            put(st, pos, x, vel)
            put(stl, pos, x, vel * cl)
            put(str_, pos, x, vel * cr)
        el, er = pingpong(st, delay, 0.4, 3000)
        airL += AIR['stab'] * (stl + 0.45 * el)
        airR += AIR['stab'] * (str_ + 0.45 * er)

    # ---- vowel chops
    if ev.vox:
        vm = np.zeros(n)
        vl = np.zeros(n)
        vr = np.zeros(n)
        for pos, notes, vel, pan, ln, vw, vw2 in ev.vox:
            x = vox_smp(notes, ln, vw, rng, vw2)
            cl, cr = pan_lr(pan)
            put(vm, pos, x, vel)
            put(vl, pos, x, vel * cl)
            put(vr, pos, x, vel * cr)
        el, er = pingpong(vm, delay, 0.38, 2600)
        airL += AIR['vox'] * (vl + 0.4 * el)
        airR += AIR['vox'] * (vr + 0.4 * er)

    # ---- the hoover: detuned pulse-width-modulated saws with a scoop into every note, an
    # octave below, chorused wide
    if ev.lead:
        pitch, gate, onsets = mono_line(ev.lead, n, 0.07)
        g = smooth_gate(gate, 8)
        scoop = decays(onsets, n, 0.045)
        f = mtof(pitch - 2.0 * scoop)
        pw = 0.5 + 0.32 * np.sin(2 * math.pi * 0.9 * idx / FS)
        x = np.zeros(n)
        for d in (-0.23, -0.08, 0.08, 0.23):
            x += pulse(f * 2 ** (d / 12), pw, rng.uniform())
        x += 1.2 * saw(f * 0.5, 0.3) + 0.6 * saw(f * 0.5 * 1.006, 0.6)
        fenv = decays(onsets, n, 0.25)
        x = tvf(x, 2300 + 4000 * fenv + auto('lead', idx), 0.9)
        x = sat(x * g * 0.32, 1.6)
        cl = chorus(x, 0.6, 3.0, 9.0, 0.0)
        cr = chorus(x, 0.7, 3.0, 11.0, 1.7)
        el, er = pingpong(x, delay, 0.3, 2800)
        airL += AIR['lead'] * (0.6 * x + 0.6 * cl + 0.35 * el)
        airR += AIR['lead'] * (0.6 * x + 0.6 * cr + 0.35 * er)

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
        bass_on = auto('acidbass', idx)        # 1 where the acid is the bass (in the beat stem)
        beat += 0.6 * x * bass_on
        el, er = pingpong(x, int(2 * delay / 3), 0.32, 2500)
        top = 1 - bass_on
        echo = 0.4 * top + 0.15 * bass_on
        airL += AIR['acid'] * (x * top + echo * el)
        airR += AIR['acid'] * (x * top + echo * er)

    # ---- bells (an arpeggio), clangs
    if ev.bells:
        bl = np.zeros(n)
        br = np.zeros(n)
        bm = np.zeros(n)
        for pos, m, vel, pan in ev.bells:
            x = bell_smp(m)
            cl, cr = pan_lr(pan)
            put(bl, pos, x, vel * cl)
            put(br, pos, x, vel * cr)
            put(bm, pos, x, vel)
        el, er = pingpong(bm, delay, 0.5, 4000)
        airL += AIR['bell'] * (bl + 0.6 * el)
        airR += AIR['bell'] * (br + 0.6 * er)
    for pos, f0, vel, pan in ev.clangs:
        x = clang_smp(rng, f0, 1.2, 0.3)
        cl, cr = pan_lr(pan)
        put(airL, pos, x, AIR['clang'] * vel * cl)
        put(airR, pos, x, AIR['clang'] * vel * cr)

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
            x = tvf(noise(rng, m), fc, 2.0, 'bp')
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
            p = 0.13 * (0.5 - 0.5 * np.cos(2 * math.pi * 2 * t / d)) ** 1.3 * FS
            x = np.interp(p, np.arange(len(vowel)), vowel)
            fader = (np.sin(2 * math.pi * 4 * t / d) > -0.6).astype(float)
            x = sat(filt(x * smooth_gate(fader, 2), 300, 0.7, 'hp'), 1.5)
            put(airL, pos, x, AIR['scratch'] * g)
            put(airR, pos, x, AIR['scratch'] * g)

    return hp_dc(beat), hp_dc(airL), hp_dc(airR)


# ================================================================== the fight: "Live Demo"

# per chord: reese root, the step below it (in key), pad voicing, stab voicing
FIGHT_A = [(40, -2, [52, 59, 62, 67], [64, 67, 71]),      # Em
           (36, -1, [48, 55, 60, 64], [64, 67, 72]),      # C
           (38, -2, [50, 57, 62, 66], [66, 69, 74]),      # D
           (35, -2, [47, 54, 59, 63], [63, 66, 71])]      # B
# the breakdown: sub root, pad, the glass arpeggio's tones, the choir
FIGHT_D = [(36, [48, 55, 59, 64, 71], [60, 64, 67, 71, 76, 79], [55, 59, 64]),     # Cmaj7
           (38, [50, 57, 59, 66, 69], [62, 66, 69, 71, 74, 78], [57, 62, 66]),     # D6
           (40, [52, 59, 62, 66, 67], [64, 66, 67, 71, 74, 78], [59, 62, 67]),     # Em9
           (35, [47, 54, 59, 64, 69], [59, 64, 66, 69, 71, 76], [59, 64, 69])]     # B7sus4 (to B)
# the hook, two bars per chord: (step of 32, midi, sixteenths)
FIGHT_HOOK = [
    [(0, 64, 3), (3, 67, 3), (6, 71, 2), (8, 69, 4), (12, 67, 2), (14, 66, 2), (16, 64, 6), (22, 62, 2), (24, 64, 4), (28, 67, 4)],
    [(0, 67, 3), (3, 64, 3), (6, 67, 2), (8, 72, 4), (12, 71, 2), (14, 69, 2), (16, 67, 6), (22, 64, 2), (24, 67, 4), (28, 69, 4)],
    [(0, 69, 3), (3, 66, 3), (6, 69, 2), (8, 74, 4), (12, 72, 2), (14, 71, 2), (16, 69, 6), (22, 66, 2), (24, 69, 4), (28, 71, 4)],
    [(0, 71, 6), (6, 70, 2), (8, 66, 8), (16, 63, 4), (20, 66, 4), (24, 71, 2), (26, 70, 2), (28, 71, 4)],
]
# rolling bass, two bars: (step of 32, semitones from the root or 'b' for the step below, sixteenths)
FIGHT_BASS = [(0, 0, 7), (10, 0, 3), (14, 12, 2), (16, 0, 6), (22, 0, 2), (26, 'b', 2), (28, 0, 3)]
# acid, per bar at half time (eighths): (step, semitones, accent, slide)
FIGHT_ACID_C = [(0, 0, 1, 0), (2, 12, 0, 0), (4, 0, 0, 1), (6, 3, 0, 0), (8, 0, 1, 0), (10, 7, 0, 1), (12, 10, 0, 0), (14, 12, 1, 0)]
# acid over the second drop, sixteenths
FIGHT_ACID_E = [(0, 0, 1, 0), (1, 0, 0, 0), (3, 12, 1, 0), (4, 0, 0, 1), (6, 7, 0, 0), (7, 10, 1, 0), (9, 0, 0, 0),
                (10, 12, 0, 1), (11, 15, 1, 0), (13, 0, 0, 0), (14, 7, 0, 1), (15, 12, 0, 0)]

HATS = [(s, 'h', 0.75 if s % 4 == 2 else (0.5 if s % 2 == 0 else 0.28)) for s in range(16)]
DNB_A = [(0, 'K', 1.0), (4, 'S', 1.0), (7, 'g', 0.5), (9, 'g', 0.4), (10, 'K', 0.9), (12, 'S', 1.0), (15, 'g', 0.55)]
DNB_B = [(0, 'K', 1.0), (2, 'K', 0.7), (4, 'S', 1.0), (7, 'g', 0.5), (10, 'K', 0.9), (11, 'g', 0.4), (12, 'S', 1.0),
         (13, 'g', 0.4), (14, 'S', 0.6), (6, 'p', 0.8)]
DNB_AMEN = [(0, 'K', 1.0), (2, 'K', 0.8), (4, 'S', 1.0), (7, 'g', 0.55), (9, 'g', 0.45), (10, 'K', 0.9), (11, 'K', 0.6),
            (12, 'S', 1.0), (14, 'g', 0.5), (15, 'S', 0.7)]
DNB_FILL = [(0, 'K', 1.0), (4, 'S', 1.0), (7, 'g', 0.5), (8, 'S', 0.55), (9, 'S', 0.45), (10, 'K', 0.9), (11, 'S', 0.6),
            (12, 'S', 0.85), (13, 'S', 0.7), (14, 'S', 0.9), (14.5, 'S', 0.8), (15, 'S', 1.0), (15.5, 'S', 0.9)]
# big beat at half time: a bar of sixteen steps at 174 is half a bar at 87
BIG = [(0, 'B', 1.0), (3, 'g', 0.35), (6, 'B', 0.55), (8, 'X', 1.0), (10, 'B', 0.85), (11, 'g', 0.4), (14, 'g', 0.45),
       (15, 'B', 0.5)]
BIG_FILL = [(0, 'B', 1.0), (6, 'B', 0.6), (8, 'X', 1.0), (10, 'X', 0.7), (11, 'X', 0.55), (12, 'X', 0.85), (13, 'B', 0.8),
            (14, 'X', 0.9), (15, 'X', 1.0)]


def fight_body(song):
    ev = Events()
    st = song.step
    for b in range(FIGHT_BARS):
        sec = b // 8               # 0 A drop, 1 B hook, 2 C big beat, 3 D breakdown, 4 E drop, 5 F finale
        inb = b % 8
        half = inb % 2
        root, below, padv, stabv = FIGHT_A[inb // 2]
        # ---- drums
        if sec in (0, 1, 4, 5):
            if inb == 7 and sec != 5:
                pat = DNB_FILL
            elif sec == 5:
                pat = DNB_FILL if inb == 7 else (DNB_AMEN if half else DNB_B)
            elif sec == 0:
                pat = DNB_B if inb == 3 else DNB_A
            else:
                pat = DNB_B if half else DNB_A
            for s, d, v in pat:
                ev.hits.append((song.at(b, s), d, v, 'kit'))
            for s, d, v in HATS:
                if inb == 7 and s >= 8:
                    continue
                if any(p[0] == s and p[1] in 'op' for p in pat):
                    continue
                ev.hits.append((song.at(b, s), d, v * (0.8 if sec == 5 else 1.0), 'kit'))
            if sec in (1, 4, 5):
                for s in (2, 6, 10, 14):
                    ev.hits.append((song.at(b, s), 'r', 0.7 if sec == 5 else 0.45, 'kit'))
            if sec == 5:
                for s in range(16):
                    ev.hits.append((song.at(b, s), 'k', 0.8 if s % 2 else 0.45, 'kit'))
        elif sec == 2:
            pat = BIG_FILL if inb == 7 else BIG
            for s, d, v in pat:
                ev.hits.append((song.at(b, s), d, v, 'kit'))
            for s in range(0, 16, 2):
                if inb == 7 and s >= 8:
                    break
                d = 'o' if s in (6, 14) else 'h'
                ev.hits.append((song.at(b, s), d, 0.75 if s % 4 == 2 else 0.5, 'kit'))
                ev.hits.append((song.at(b, s + 1), 'h', 0.25, 'kit'))
            if inb % 2 == 1 and inb != 7:
                ev.hits.append((song.at(b, 12), 'p', 0.9, 'kit'))
        else:                      # the breakdown
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
        # ---- bass
        if sec in (0, 1, 4, 5) and half == 0:
            for s, semi, ln in FIGHT_BASS:
                bb = b + s // 16
                ss = s % 16
                m = root + (below if semi == 'b' else semi)
                ev.bass.append((song.at(bb, ss), song.at(bb, ss) + ln * st - 0.012 * FS, m, False))
        if sec == 2:               # the acid is the bass, a sine under it
            for s, semi, ac, sl in FIGHT_ACID_C:
                p = song.at(b, s)
                ev.acid.append((p, p + st * (2.0 if sl else 1.1), root + semi, bool(sl), ac))
            if half == 0:
                ev.sub.append((song.at(b, 0), song.at(b + 2, 0) - 0.03 * FS, root))
        if sec == 3 and half == 0 and inb < 6:
            ev.sub.append((song.at(b, 0), song.at(b + 2, 0) - 0.05 * FS, FIGHT_D[inb // 2][0]))
        if sec == 3 and inb == 6:
            ev.sub.append((song.at(b, 0), song.at(b + 2, 0) - 0.02 * FS, 35))
        # ---- pads
        if half == 0:
            lvl = {0: 0.7, 1: 0.6, 2: 0.5, 3: 1.1, 4: 0.6, 5: 0.7}[sec]
            if sec == 3:
                pv = FIGHT_D[inb // 2][1]
                if inb == 6:         # B7sus4, then B
                    ev.pads.append((song.at(b, 0), song.at(b + 1, 0), pv, lvl))
                    ev.pads.append((song.at(b + 1, 0), song.at(b + 2, 0), [47, 54, 59, 63, 66], lvl))
                else:
                    ev.pads.append((song.at(b, 0), song.at(b + 2, 0), pv, lvl))
            else:
                ev.pads.append((song.at(b, 0), song.at(b + 2, 0), padv, lvl))
        # ---- stabs
        if sec in (0, 1, 4, 5):
            steps = {0: (3, 10), 1: (3, 10, 14) if half else (3, 10), 4: (3, 10), 5: (0, 3, 6, 10, 13)}[sec]
            if inb == 7 and sec != 5:
                steps = (3,)
            for i, s in enumerate(steps):
                ev.stabs.append((song.at(b, s), stabv, 0.85 if i == 0 else 0.7, 0.3 if i % 2 else 0.7, 0.24))
        if sec == 2 and inb in (0, 4):
            ev.stabs.append((song.at(b, 0), stabv, 1.0, 0.5, 0.5))
        # ---- vowel chops: the robots in C and F, the choir in D
        if sec == 2:
            ev.vox.append((song.at(b, 6), [root + 24], 0.75, 0.25, 0.16, 'e', None))
            if half:
                ev.vox.append((song.at(b, 14), [root + 31], 0.7, 0.75, 0.22, 'a', 'o'))
        if sec == 5:
            ev.vox.append((song.at(b, 14), [stabv[0], stabv[2] - 12], 0.7, 0.2 if half else 0.8, 0.18, 'a', 'e'))
        if sec == 3 and inb < 6 and half == 0:
            ev.vox.append((song.at(b, 0), FIGHT_D[inb // 2][3], 0.4, 0.5, 2 * song.bar_len / FS - 0.1, 'o', 'a'))
        # ---- clangs: the hangar's steel
        if sec == 0 and half == 0:
            ev.clangs.append((song.at(b, 0), 329.6, 0.8, 0.3 if inb % 4 else 0.7))
        if sec == 2:
            ev.clangs.append((song.at(b, 0), 164.8, 1.0, 0.5))
            ev.clangs.append((song.at(b, 11), 329.6, 0.6, 0.25 if half else 0.75))
        if sec == 5 and half == 0:
            ev.clangs.append((song.at(b, 0), 246.9, 0.7, 0.4))
        # ---- the glass arpeggio over the breakdown, quieter as the drums come back
        if sec == 3:
            arp = FIGHT_D[inb // 2][2]
            if inb == 7:
                arp = [59, 63, 66, 71, 75, 78]     # the sus4 resolves to B
            order = [0, 2, 4, 1, 3, 5, 2, 4]
            for s in range(16):
                m = arp[order[(s + b * 16) % 8]]
                v = (0.75 if s % 4 == 0 else 0.5) * (1.0 if inb < 6 else 0.6)
                ev.bells.append((song.at(b, s), m, v, 0.2 if s % 2 else 0.8))
        # ---- the hook in B and E
        if sec in (1, 4) and half == 0:
            for s, m, ln in FIGHT_HOOK[inb // 2]:
                bb = b + s // 16
                ev.lead.append((song.at(bb, s % 16), song.at(bb, s % 16) + ln * st - 0.02 * FS, m, ln <= 2))
        # ---- acid over E
        if sec == 4:
            for s, semi, ac, sl in FIGHT_ACID_E:
                p = song.at(b, s)
                ev.acid.append((p, p + st * (1.0 if sl else 0.6), root + 12 + semi, bool(sl), ac))
    # cymbals and impacts
    for b in (0, 8, 16, 32, 40):
        ev.crashes.append((song.at(b, 0), 1.0))
    for b in (0, 16, 32):
        ev.booms.append((song.at(b, 0), 1.0))
    ev.crashes.append((song.at(24, 0), 0.8))
    ev.revcrash.append((song.at(32, 0), 1.0, 1.6))
    ev.revcrash.append((song.at(48, 0), 0.9, 1.2))
    ev.revcrash.append((song.at(16, 0), 0.7, 1.0))
    ev.risers.append((song.at(28, 0), song.at(32, 0), 1.0))
    ev.risers.append((song.at(46, 0), song.at(48, 0), 0.6))
    ev.scratches.append((song.at(19, 8), 1.0))
    ev.scratches.append((song.at(23, 4), 0.9))
    return ev


def fight_intro(song, n):
    """The machines power up: a filtered break opening, a sub pedal, clangs, then a riser and the
    B major pad (the V of the drop), a snare roll in the last bar, everything cut at the drop."""
    ev = Events()
    st = song.step
    for b in range(FIGHT_INTRO_BARS - 1):
        pat = DNB_B if b % 2 else DNB_A
        for s, d, v in pat + HATS:
            ev.hits.append((song.at(b, s), d, v, 'lp'))
    b = FIGHT_INTRO_BARS - 1
    ev.hits.append((song.at(b, 0), 'K', 1.0, 'kit'))
    sched = [(i * 2, 0.35 + 0.04 * i) for i in range(4)] + [(8 + i, 0.55 + 0.03 * i) for i in range(4)] + \
            [(12 + i / 2, 0.75 + 0.03 * i) for i in range(8)]
    for s, v in sched:
        ev.hits.append((song.at(b, s), 'S', v, 'kit'))
    ev.sub.append((0, song.at(2, 0) - int(0.03 * FS), 28 + 12))
    ev.sub.append((song.at(2, 0), n - int(0.02 * FS), 35))
    ev.clangs.append((song.at(0, 0), 164.8, 1.0, 0.5))
    ev.clangs.append((song.at(1, 0), 246.9, 0.8, 0.3))
    ev.clangs.append((song.at(2, 0), 329.6, 0.8, 0.7))
    ev.pads.append((song.at(2, 0), n, [47, 54, 59, 63, 66], 1.2))
    ev.risers.append((song.at(1, 0), n, 0.9))
    ev.revcrash.append((n, 1.0, 2.0))
    return ev


def fight_auto(song, origin):
    """Automation curves for the fight, indexed by timeline sample (origin: where body bar 0 is)."""
    L = song.L

    def auto(name, idx):
        pos = (idx - origin) % L
        bar = pos / song.bar_len
        pre = idx < origin
        if name == 'pad':
            sweep = 0.5 - 0.5 * np.cos(2 * math.pi * bar / 8)
            fc = 1400 + 2200 * sweep
            br = (bar >= 24) & (bar < 32)
            fc = np.where(br, 1200 + 3800 * np.clip((bar - 24) / 6, 0, 1), fc)
            if origin > 0:
                fc = np.where(pre, 500 + 3500 * np.clip((idx - song.bar_len * 2) / max(1, origin - song.bar_len * 2), 0, 1) ** 2, fc)
            return fc
        if name == 'reese':
            fc = 520 + 900 * (0.5 - 0.5 * np.cos(2 * math.pi * bar / 2))
            return np.where(bar >= 40, fc * 1.35, fc)
        if name == 'acid':
            c = 350 + 1000 * np.clip((bar - 16) / 8, 0, 1) ** 1.2
            e = 320 + 1100 * np.clip((bar - 32) / 8, 0, 1) ** 1.2
            return np.where(bar < 32, c, e) + 150 * (0.5 - 0.5 * np.cos(2 * math.pi * bar))
        if name == 'acidbass':
            return ((bar >= 16) & (bar < 24)).astype(float)
        if name == 'lead':
            return np.where(bar >= 32, 700.0, 0.0)
        if name == 'drumlp':
            fc = 500 + 2200 * np.clip((bar - 28) / 2, 0, 1) ** 2
            if origin > 0:
                fc = np.where(pre, 280 * 9 ** (idx / max(1, song.bar_len * (FIGHT_INTRO_BARS - 1))), fc)
            return fc
        return np.zeros(len(idx))
    return auto


# ================================================================== the menu: "Showfloor"

# per chord: bass root, e-piano voicing, brass stab voicing
MENU_CHORDS = [(43, [59, 62, 66, 69], [62, 66, 71]),     # Gmaj9
               (40, [55, 59, 62, 66], [62, 67, 71]),     # Em9
               (36, [52, 55, 59, 62], [64, 67, 71]),     # Cmaj9
               (38, [54, 57, 59, 64], [62, 66, 69])]     # D6/9
# the funk bass per bar: (step, semitones, sixteenths, slide)
MENU_BASS = [(0, 0, 3, 0), (3, 12, 1, 0), (4, 0, 2, 0), (6, 7, 1, 0), (8, 0, 3, 0), (11, 12, 1, 1), (12, 9, 1, 0), (14, 7, 2, 0)]
MENU_BB = [(0, 'B', 1.0), (3, 'g', 0.35), (4, 'X', 1.0), (6, 'B', 0.6), (7, 'g', 0.4), (10, 'B', 0.95), (12, 'X', 1.0),
           (13, 'g', 0.35), (15, 'B', 0.5)]
MENU_BB2 = MENU_BB[:5] + [(8, 'X', 0.5), (10, 'X', 0.7), (11, 'X', 0.55), (12, 'X', 1.0), (13, 'B', 0.8), (14, 'X', 0.8), (15, 'X', 1.0)]
MENU_FILL = [(0, 'B', 1.0), (4, 'X', 1.0), (6, 'B', 0.6), (8, 'X', 0.7), (9, 'X', 0.55), (10, 'B', 0.9), (10, 'X', 0.75),
             (11, 'X', 0.6), (12, 'X', 0.95), (13, 'X', 0.75), (14, 'X', 1.0), (14.5, 'X', 0.85), (15, 'X', 1.0), (15.5, 'X', 0.95)]
MENU_ACID = [(0, 0, 1, 0), (2, 12, 0, 0), (3, 0, 0, 1), (5, 7, 0, 0), (6, 0, 1, 0), (8, 12, 0, 1), (9, 14, 0, 0),
             (11, 0, 1, 0), (12, 12, 0, 0), (14, 7, 0, 1), (15, 9, 0, 0)]


def menu_drums(song, ev, b, pat, bus):
    for s, d, v in pat:
        ev.hits.append((song.at(b, s), d, v, bus))
    for s in range(16):
        if pat is not MENU_BB and s >= 8:
            break
        v = 0.7 if s % 2 == 0 else 0.35
        d = 'o' if s in (2, 10) and pat is MENU_BB else 'h'
        ev.hits.append((song.at(b, s), d, v, bus))
    if bus == 'kit':
        for s in (2, 6, 10, 14):
            ev.hits.append((song.at(b, s), 'k', 0.7, 'kit'))


def menu_body(song):
    ev = Events()
    st = song.step
    for b in range(MENU_BARS):
        sec = b // 8
        inb = b % 8
        root, epv, stabv = MENU_CHORDS[(inb // 2) % 4]
        pat = MENU_FILL if inb == 7 else (MENU_BB2 if inb == 3 else MENU_BB)
        menu_drums(song, ev, b, pat, 'kit')
        for s, semi, ln, sl in MENU_BASS:
            if inb == 7 and s >= 12:
                break
            p = song.at(b, s)
            ev.pluck.append((p, p + ln * st - 0.015 * FS, root + semi, bool(sl)))
        # e-piano: a held chord, two pushes
        for s, ln, v in ((0, 5, 0.9), (6, 3, 0.65), (10, 5, 0.75)):
            p = song.at(b, s)
            ev.epiano.append((p, p + ln * st, epv, v))
        if inb % 2 == 0:
            ev.pads.append((song.at(b, 0), song.at(b + 2, 0), [n - 12 for n in epv], 0.45 if sec == 0 else 0.6))
        if sec == 0 and inb >= 4:
            for s in range(0, 16, 2):
                ev.bells.append((song.at(b, s), epv[(s // 2) % 4] + 12, 0.35 if s % 4 else 0.5, 0.25 if s % 4 else 0.75))
        if sec == 1:
            steps = (0,) if inb % 2 == 0 else (0, 3, 6)
            for i, s in enumerate(steps):
                ev.stabs.append((song.at(b, s), stabv, 1.0 if i == 0 else 0.8, 0.35 if i % 2 else 0.65, 0.35))
            if inb % 2 == 1:
                ev.vox.append((song.at(b, 14), [stabv[1]], 0.8, 0.7, 0.2, 'e', 'a'))
            for s, semi, ac, sl in MENU_ACID:
                p = song.at(b, s)
                ev.acid.append((p, p + st * (1.0 if sl else 0.55), root + 12 + semi, bool(sl), ac))
    ev.scratches.append((song.at(3, 8), 1.0))
    ev.scratches.append((song.at(11, 8), 1.0))
    ev.scratches.append((song.at(15, 12), 0.9))
    ev.crashes.append((song.at(0, 0), 1.0))
    ev.crashes.append((song.at(8, 0), 1.0))
    ev.booms.append((song.at(8, 0), 0.8))
    ev.risers.append((song.at(14, 0), song.at(16, 0), 0.7))
    ev.revcrash.append((song.at(16, 0), 1.0, 1.4))
    ev.revcrash.append((song.at(8, 0), 0.6, 1.0))
    return ev


def menu_intro(song):
    ev = Events()
    menu_drums(song, ev, 0, MENU_BB, 'lp')
    ev.revcrash.append((song.bar_len, 0.8, 1.2))
    ev.pads.append((0, song.bar_len, [n - 12 for n in MENU_CHORDS[0][1]], 0.5))
    return ev


def menu_auto(song, origin):
    L = song.L

    def auto(name, idx):
        pos = (idx - origin) % L
        bar = pos / song.bar_len
        if name == 'acid':
            return 380 + 1000 * np.clip((bar - 8) / 8, 0, 1)
        if name == 'acidbass':
            return np.zeros(len(idx))
        if name == 'pad':
            return np.full(len(idx), 2600.0)
        if name == 'drumlp':
            return np.where(idx < origin, 300 * 25 ** (idx / max(1, origin)), 9000.0)
        if name == 'reese':
            return np.full(len(idx), 600.0)
        return np.zeros(len(idx))
    return auto


# ================================================================== rendering a track

def render_track(song, body_ev, intro_ev, intro_len_sr, auto_fn, kit, menu, delay_steps):
    """Returns the three stems at SR (float, not yet scaled): intro + one loop."""
    L = song.L
    delay = int(round(delay_steps * song.step))
    beat_len = int(round(4 * song.step))
    tail = int(4 * FS)
    # the loop: two passes, keep the second (every tail from the end wraps into the start)
    ev = Events()
    ev.extend(body_ev)
    ev.extend(body_ev.shifted(L))
    n = 2 * L + tail
    stems = render(ev, n, kit, auto_fn(song, 0), delay, beat_len, menu)
    body = [down(s[L:2 * L], True) for s in stems]
    # the intro: its own events, then cut where the loop begins
    ni = intro_len_sr * OS
    stems_i = render(intro_ev, ni, kit, auto_fn(song, ni), delay, beat_len, menu, seed=11)
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

def thump(t, f0, f1, tp, dec):
    """A body blow: a sine falling from f0 to f1."""
    f = f1 + (f0 - f1) * np.exp(-t / tp)
    return sine(f) * np.exp(-t / dec) * np.clip(t / 0.0008, 0, 1)


def crunch(rng, t, fc, dec, drive=3.0):
    """Metal crumpling: low-passed noise, decaying, driven hard."""
    return sat(filt(noise(rng, len(t)), fc, 0.8) * np.exp(-t / dec) * 2.5, drive)


def at(n, start, sig, g=1.0):
    """sig placed at start seconds in n samples."""
    x = np.zeros(n)
    put(x, int(start * FS), sig, g)
    return x


def hiss(rng, dur, fc=3800, q=0.9, att=0.015, dec=0.12, whistle=None):
    """A hydraulic hiss (air or fluid let out under pressure), with a falling whistle if given
    (f from, f to)."""
    t = tt(dur)
    x = filt(filt(noise(rng, len(t)), fc, q, 'bp'), 900, 0.7, 'hp')
    if whistle:
        f = whistle[0] + (whistle[1] - whistle[0]) * np.clip(t / dur, 0, 1)
        x += 0.25 * filt(sine(f) + 0.3 * noise(rng, len(t)) * 0.2, whistle[0], 2.0, 'bp')
    env = np.clip(t / att, 0, 1) * np.exp(-t / dec)
    return fade(x * env, 0.001, 0.03)


def servo(rng, dur, f0, f1, amp=1.0):
    """An electric servo's whine: a geared buzz sliding from f0 to f1."""
    t = tt(dur)
    f = f0 * (f1 / f0) ** np.clip(t / dur, 0, 1)
    x = saw(f) + 0.5 * pulse(f * 2.0, 0.3)
    teeth = 0.65 + 0.35 * np.sign(np.sin(2 * math.pi * np.cumsum(f / 7.0) / FS))
    x = filt(x * teeth, f0 * 2.2, 1.5, 'bp') + 0.3 * filt(x, 3500, 0.7, 'lp')
    env = np.clip(t / 0.02, 0, 1) * np.clip((dur - t) / 0.04, 0, 1)
    return x * env * amp


def sparks(rng, dur, density, dec):
    """Sparks and crackle: sparse bright clicks, thinning out."""
    t = tt(dur)
    n = len(t)
    clicks = np.zeros(n)
    count = int(density * dur)
    for _ in range(count):
        p = int(abs(rng.exponential(dec)) * FS)
        if p < n:
            clicks[p] += rng.uniform(-1, 1)
    x = filt(filt(clicks, 3000, 0.7, 'hp'), 9000, 0.7, 'lp')
    x = x + 0.5 * filt(clicks, 6500, 4.0, 'bp')
    return x * 6


def debris(rng, n, start, end, count, f_lo=900, f_hi=3200, amp=0.3):
    """Small parts bouncing: short metallic pings at random times, quieter later."""
    x = np.zeros(n)
    for i in range(count):
        when = start + (end - start) * (i + rng.uniform(0, 1)) / count
        f0 = rng.uniform(f_lo, f_hi)
        ping = clang_smp(rng, f0, 0.25, rng.uniform(0.03, 0.08), 0.6)
        put(x, int(when * FS), ping, amp * (1 - 0.7 * (when - start) / max(1e-6, end - start)) * rng.uniform(0.5, 1.0))
    return x


def whoosh(rng, dur, peak, width, f_lo, f_hi):
    """A heavy thing passing through the air: a band of noise that rises and falls."""
    t = tt(dur)
    w = np.exp(-0.5 * ((t - peak) / width) ** 2)
    x = tvf(noise(rng, len(t)), f_lo + (f_hi - f_lo) * w, 1.1, 'bp', 32)
    x += 0.7 * filt(noise(rng, len(t)), 220, 0.7) * 3.0
    return x * w, w


def crowd(rng, dur, rise=0.5, fall_at=2.4, fall=1.2):
    """An expo crowd cheering: many voices through vowel formants, claps, and the wash."""
    t = tt(dur)
    n = len(t)
    x = np.zeros(n)
    for v in range(36):
        f0 = rng.uniform(140, 330)
        start = rng.uniform(0.0, 0.5)
        lift = 1 + 0.25 * np.clip((t - start) / 0.4, 0, 1)
        wob = 1 + 0.03 * filt(noise(rng, n), 6, 0.7) * 4
        f = f0 * lift * wob
        src = saw(f, rng.uniform())
        vw = VOWELS[rng.choice(['a', 'e', 'o'])]
        y = filt(src, vw[0][0], 5.0, 'bp') + 0.6 * filt(src, vw[1][0], 6.0, 'bp')
        env = np.clip((t - start) / rng.uniform(0.15, 0.5), 0, 1)
        env *= 0.6 + 0.4 * np.abs(filt(noise(rng, n), 3, 0.7)) * 8
        x += y * np.clip(env, 0, 1.5)
    x /= 6
    claps = np.zeros(n)
    for _ in range(int(55 * dur)):
        p = int(rng.uniform(0.2, dur) * FS)
        claps[p] += rng.uniform(0.4, 1.0)
    clap = filt(filt(np.convolve(claps, np.exp(-np.arange(int(0.012 * FS)) / (0.003 * FS))), 1400, 1.2, 'bp'), 600, 0.7, 'hp')[:n]
    wash = filt(filt(noise(rng, n), 2500, 0.7), 300, 0.7, 'hp')
    x = x + 1.4 * clap + 0.25 * wash
    env = np.clip(t / rise, 0, 1) ** 1.5 * np.where(t < fall_at, 1.0, np.exp(-(t - fall_at) / fall))
    return fade(x * env, 0.01, 0.2)


def sfx_hit(p):
    """A hit, p 0 (light) to 3 (crushing): tonnes of metal."""
    rng = np.random.default_rng(100 + p)
    s = p / 3
    dur = 0.6 + 1.5 * s
    t = tt(dur)
    n = len(t)
    x = 1.1 * thump(t, 190 + 40 * s, 70 - 28 * s, 0.022 + 0.02 * s, 0.07 + 0.25 * s)
    x += 0.9 * crunch(rng, t, 1900 - 700 * s, 0.014 + 0.05 * s)
    x += 0.8 * filt(noise(rng, n), 2500, 0.7, 'hp') * np.exp(-t / 0.003)
    x += (0.35 + 0.15 * s) * clang_smp(rng, 560 - 250 * s, dur, 0.1 + 0.45 * s, 1 - 0.3 * s)
    if p >= 1:
        x += (0.08 + 0.1 * s) * at(n, 0.005, sparks(rng, 0.2 + 0.4 * s, 120 + 200 * s, 0.05 + 0.1 * s))
    if p >= 2:
        x += debris(rng, n, 0.12, 0.45 + 0.6 * s, 3 + 3 * p, amp=0.25)
    if p == 3:
        x += 0.7 * filt(noise(rng, n), 160, 0.7) * np.exp(-t / 0.6) * np.clip(t / 0.01, 0, 1) * 2.5
        g = np.exp(-0.5 * ((t - 0.6) / 0.3) ** 2)
        groan = sine(185 * (1 - 0.2 * np.clip(t / 1.2, 0, 1))) + 0.7 * sine(243 * (1 - 0.25 * np.clip(t / 1.2, 0, 1)))
        x += 0.18 * filt(groan * (1 + 0.3 * np.sin(2 * math.pi * 7 * t)), 400, 1.5, 'bp') * g * 3
    return fade(sat(x * (1.1 + 0.5 * s), 1.6 + 1.4 * s), 0.0004, 0.15)


def sfx_block():
    """Steel on steel: two plates ringing against each other, a buffer's hiss."""
    rng = np.random.default_rng(200)
    dur = 1.2
    t = tt(dur)
    n = len(t)
    x = clang_smp(rng, 880, dur, 0.28, 1.0) + 0.75 * clang_smp(rng, 1241, dur, 0.22, 1.0)
    x += 0.7 * thump(t, 150, 90, 0.02, 0.05)
    x += 0.6 * filt(noise(rng, n), 4000, 0.7, 'hp') * np.exp(-t / 0.004)
    x += 0.12 * at(n, 0.0, sparks(rng, 0.25, 160, 0.05))
    x += 0.35 * at(n, 0.05, hiss(rng, 0.35, 4200, 1.0, 0.02, 0.09))
    return fade(sat(x * 0.8, 1.4), 0.0004, 0.15)


def sfx_chip():
    """A blade grinding along a guard: a scrape and a spray of sparks."""
    rng = np.random.default_rng(210)
    dur = 0.4
    t = tt(dur)
    n = len(t)
    jit = 0.5 + 0.5 * np.abs(filt(noise(rng, n), 70, 0.7)) * 6
    x = filt(noise(rng, n), 2700, 3.0, 'bp') * jit * np.clip(t / 0.004, 0, 1) * np.exp(-t / 0.08) * 1.5
    x += 0.4 * clang_smp(rng, 2100, dur, 0.06, 0.8)
    x += 0.2 * sparks(rng, dur, 220, 0.06)
    return fade(sat(x, 1.3), 0.0004, 0.05)


def sfx_swing_hero():
    """The Hero's long sword: a heavy whoosh, the arm's servo, the blade's ring, the stop."""
    rng = np.random.default_rng(300)
    dur = 0.75
    t = tt(dur)
    n = len(t)
    wh, w = whoosh(rng, dur, 0.24, 0.09, 300, 1700)
    x = 1.2 * wh
    x += 0.45 * sine(np.full(n, 68.0)) * w
    x = x + 0.22 * at(n, 0.0, servo(rng, 0.22, 520, 950))
    shing = (np.sin(2 * math.pi * 2640 * t) + 0.6 * np.sin(2 * math.pi * 3960 * t * 1.003)) * w ** 3
    x += 0.08 * shing
    x += 0.3 * at(n, 0.4, hiss(rng, 0.3, 3500, 1.0, 0.01, 0.08))
    return fade(sat(x * 0.9, 1.3), 0.002, 0.05)


def sfx_swing_doubleblade():
    """The Double-blade Hero's antimatter blades: two passes, a ring-modulated hum that bends with
    the speed, static crackling round the edge."""
    rng = np.random.default_rng(310)
    dur = 0.85
    t = tt(dur)
    n = len(t)
    wh1, w1 = whoosh(rng, dur, 0.2, 0.07, 250, 1200)
    wh2, w2 = whoosh(rng, dur, 0.36, 0.08, 230, 1050)
    w = np.clip(w1 + 0.85 * w2, 0, 1.2)
    f = 98 * (1 + 0.14 * w)
    hum = sine(f) + 0.6 * sine(f * 1.5) + 0.3 * filt(saw(f * 2), 900, 0.7)
    hum *= 0.6 + 0.4 * np.sin(2 * math.pi * 37 * t)
    hum = hum + vdelay(hum, (2.0 + 1.5 * np.sin(2 * math.pi * 3 * t)) * FS / 1000)
    env = np.clip(0.15 + w, 0, 1.1) * np.clip(t / 0.03, 0, 1)
    x = 0.8 * wh1 + 0.7 * wh2 + 0.45 * hum * env
    x += 0.12 * sparks(rng, dur, 140, 0.25) * w
    return fade(sat(x, 1.4), 0.002, 0.08)


def sfx_grab():
    """The hand closes: a servo, the clamp's clunk and latch, the hydraulics taking the load."""
    rng = np.random.default_rng(400)
    dur = 0.85
    t = tt(dur)
    n = len(t)
    x = 0.35 * at(n, 0.0, servo(rng, 0.18, 420, 1100))
    clunk = clang_smp(rng, 300, 0.5, 0.08, 0.6) + thump(tt(0.5), 170, 80, 0.015, 0.06)
    x += at(n, 0.17, clunk, 0.9)
    x += at(n, 0.23, clang_smp(rng, 1200, 0.3, 0.04, 1.0), 0.5)
    x += at(n, 0.25, hiss(rng, 0.55, 4500, 1.0, 0.01, 0.16, whistle=(2400, 1600)), 0.45)
    return fade(sat(x, 1.4), 0.002, 0.05)


def sfx_throw():
    """A 12-metre mech meets the hangar floor: a sub slam, crumpling plate, concrete, clatter."""
    rng = np.random.default_rng(500)
    dur = 2.0
    t = tt(dur)
    n = len(t)
    x = 1.3 * thump(t, 120, 36, 0.04, 0.35)
    x += 1.0 * crunch(rng, t, 900, 0.12, 3.5)
    x += 0.7 * filt(noise(rng, n), 2500, 0.7, 'hp') * np.exp(-t / 0.004)
    x += 0.35 * clang_smp(rng, 240, dur, 0.5, 0.7)
    grains = np.zeros(n)
    for _ in range(90):
        p = int(abs(rng.exponential(0.25)) * FS)
        if p < n:
            grains[p] += rng.uniform(-1, 1)
    x += 0.5 * filt(np.convolve(grains, np.exp(-np.arange(200) / 40.0))[:n], 1500, 1.0, 'bp')
    x += debris(rng, n, 0.08, 1.3, 9, amp=0.3)
    x += 0.8 * filt(noise(rng, n), 150, 0.7) * np.exp(-t / 0.7) * np.clip(t / 0.01, 0, 1) * 2.5
    return fade(sat(x * 1.3, 2.6), 0.0004, 0.25)


def sfx_break():
    """A grab broken: the clamp springs open, a burst of hydraulic pressure, the shove."""
    rng = np.random.default_rng(600)
    dur = 0.9
    t = tt(dur)
    n = len(t)
    x = clang_smp(rng, 1400, dur, 0.12, 1.0) + 0.6 * clang_smp(rng, 700, dur, 0.1, 0.8)
    x += 0.8 * at(n, 0.008, hiss(rng, 0.6, 3000, 0.7, 0.004, 0.2, whistle=(3200, 1800)))
    wh, _ = whoosh(rng, dur, 0.18, 0.08, 200, 800)
    x += 0.6 * wh
    x += 0.6 * thump(t, 140, 70, 0.02, 0.06)
    return fade(sat(x * 0.9, 1.5), 0.0004, 0.08)


def sfx_land():
    """Tonnes coming down from a jump: the thud, the suspension's chunk and hiss, a rattle."""
    rng = np.random.default_rng(700)
    dur = 0.95
    t = tt(dur)
    n = len(t)
    x = 1.2 * thump(t, 130, 46, 0.03, 0.16)
    x += 0.7 * crunch(rng, t, 700, 0.04, 2.5)
    x += 0.6 * at(n, 0.07, clang_smp(rng, 190, 0.4, 0.06, 0.4))
    x += 0.35 * at(n, 0.09, hiss(rng, 0.3, 3500, 1.0, 0.01, 0.08))
    x += debris(rng, n, 0.05, 0.4, 3, 700, 1800, 0.15)
    return fade(sat(x * 1.1, 2.0), 0.0004, 0.1)


def sfx_step():
    """A footstep: a short heavy thud, the foot's plate, the knee's servo."""
    rng = np.random.default_rng(800)
    dur = 0.5
    t = tt(dur)
    n = len(t)
    x = 1.2 * thump(t, 115, 52, 0.02, 0.075)
    x += 0.4 * crunch(rng, t, 500, 0.025, 2.0)
    x += 0.35 * clang_smp(rng, 260, dur, 0.05, 0.5)
    x += 0.12 * at(n, 0.04, servo(rng, 0.15, 760, 600))
    return fade(sat(x, 1.8), 0.0004, 0.06)


def sfx_meter_full():
    """The power meter fills: a rising sweep into a bright E major chime, sparkles."""
    rng = np.random.default_rng(900)
    dur = 1.5
    t = tt(dur)
    n = len(t)
    ns = int(0.3 * FS)
    ts = np.arange(ns) / FS
    m = 64 + 12 * (ts / 0.3) ** 1.5
    sw = sum(saw(mtof(m + d), rng.uniform()) for d in (-0.12, 0, 0.12)) / 3
    sw = tvf(sw, 600 + 5000 * (ts / 0.3) ** 2, 1.5) * (ts / 0.3) ** 1.2
    x = at(n, 0.0, sw, 0.5)
    for i, mm in enumerate((88, 92, 95, 100)):
        x += at(n, 0.3 + 0.025 * i, bell_smp(mm, 1.1, 2.0, 1.4), 0.32)
    for _ in range(10):
        x += at(n, rng.uniform(0.35, 1.1), bell_smp(rng.choice([100, 104, 107, 112]), 0.3, 3.5, 1.0), 0.08)
    x += 0.35 * sine(np.full(n, 82.4)) * np.exp(-0.5 * ((t - 0.35) / 0.18) ** 2)
    return fade(x, 0.002, 0.2)


def sfx_super():
    """The super: a charge that screams up, then the flash: an impact, a chord, the choir."""
    rng = np.random.default_rng(1000)
    dur = 2.8
    t = tt(dur)
    n = len(t)
    c = 0.55
    nc = int(c * FS)
    tc = np.arange(nc) / FS
    f = 150 * (2000 / 150) ** (tc / c)
    whine = filt(sine(f) + 0.4 * saw(f * 1.01), 5000, 0.7) * (tc / c) ** 1.4
    rise = tvf(noise(rng, nc), 300 * 20 ** (tc / c), 2.0, 'bp') * (tc / c) ** 2
    swell = sine(np.full(nc, 41.2)) * (tc / c) ** 2
    x = at(n, 0.0, 0.35 * whine + 0.6 * rise + 0.5 * swell)
    x += at(n, c, boom_smp(rng, 1.8), 0.9)
    x += at(n, c, cymbal_smp(rng, dec=0.8, dur=2.2), 0.3)
    x += at(n, c, filt(noise(rng, int(0.2 * FS)), 3000, 0.7, 'hp') * np.exp(-np.arange(int(0.2 * FS)) / (0.04 * FS)), 0.6)
    m = int((dur - c) * FS)
    tm = np.arange(m) / FS
    ch = np.zeros(m)
    for nt in (52, 59, 64, 66, 67, 71):
        for v in supersaw(nt, m, rng):
            ch += v
    ch /= math.sqrt(30)
    ch = tvf(ch, 700 + 7000 * np.exp(-tm / 0.35), 1.0) * env_ar(m, 0.003, 1.0, int(0.9 * FS))
    x += at(n, c, sat(ch * 0.8, 1.3), 0.7)
    x += at(n, c + 0.02, vox_smp([64, 71, 76], 1.1, 'a', rng, 'o'), 0.35)
    return fade(x, 0.002, 0.3)


def sfx_ko():
    """The KO: the crushing hit, a turbine winding down, arcing wiring, the crowd going up."""
    rng = np.random.default_rng(1100)
    dur = 4.4
    t = tt(dur)
    n = len(t)
    x = at(n, 0.0, sfx_hit(3), 0.9)
    s0 = 0.12
    m = n - int(s0 * FS)
    tm = np.arange(m) / FS
    f = 38 + 1100 * np.exp(-tm / 0.55)
    tur = filt(saw(f) + 0.5 * pulse(f * 1.5, 0.3), 2400, 0.7)
    tur *= 0.75 + 0.25 * np.sign(np.sin(2 * math.pi * np.cumsum(f / 6.0) / FS))
    tur *= np.clip(tm / 0.02, 0, 1) * np.exp(-tm / 1.0)
    x += at(n, s0, tur, 0.3)
    for when, ln in ((0.3, 0.12), (0.52, 0.08), (0.85, 0.18), (1.3, 0.1), (1.7, 0.07)):
        k = int(ln * FS)
        tk = np.arange(k) / FS
        buzz = pulse(np.full(k, 120.0 * rng.uniform(0.9, 1.2)), 0.2) * filt(noise(rng, k), 2000, 0.7, 'hp')
        buzz = sat(buzz * 2 + 0.5 * noise(rng, k) * (rng.uniform(size=k) > 0.97), 1.5)
        x += at(n, when, fade(buzz * np.exp(-tk / (ln * 0.7)), 0.002, 0.01), 0.22)
    x += at(n, 0.3, crowd(rng, dur - 0.3, 0.7, 2.6, 0.9), 0.35)
    return fade(x, 0.0004, 0.3)


def sfx_round():
    """The round begins: the expo's PA chime, then the horn and a hit on the floor."""
    rng = np.random.default_rng(1200)
    dur = 2.3
    t = tt(dur)
    n = len(t)
    x = at(n, 0.0, bell_smp(83, 0.7, 2.0, 1.4), 0.5)
    x += at(n, 0.24, bell_smp(88, 1.0, 2.0, 1.4), 0.5)
    h0 = 0.72
    m = int(0.95 * FS)
    tm = np.arange(m) / FS
    horn = np.zeros(m)
    for nt in (52, 59, 64):
        fr = mtof(nt) * 2 ** (-0.4 * np.exp(-tm / 0.04) / 12)
        horn += saw(fr, rng.uniform()) + 0.5 * pulse(fr * 1.004, 0.35, rng.uniform())
    horn = sat(filt(horn / 3, 2800, 1.0) * env_ar(m, 0.01, 0.3, int(0.6 * FS)) * 1.5, 1.6)
    x += at(n, h0, horn, 0.55)
    x += at(n, h0, boom_smp(rng, 1.4), 0.7)
    x += at(n, h0, cymbal_smp(rng, dec=0.6, dur=1.5), 0.2)
    return fade(x, 0.002, 0.2)


def sfx_menu_move():
    t = tt(0.08)
    f = 2100 + 400 * np.clip(t / 0.015, 0, 1)
    x = sine(f) + 0.3 * sine(f * 2)
    return fade(x * np.exp(-t / 0.022), 0.0008, 0.01)


def sfx_menu_ok():
    rng = np.random.default_rng(1300)
    n = int(0.45 * FS)
    x = at(n, 0.0, bell_smp(83, 0.3, 2.0, 1.0), 0.6)
    x += at(n, 0.055, bell_smp(88, 0.39, 2.0, 1.0), 0.7)
    tw = tt(0.14)
    up = tvf(noise(rng, len(tw)), 1000 * 5 ** (tw / 0.14), 2.0, 'bp') * np.sin(math.pi * tw / 0.14)
    x += at(n, 0.0, up, 0.15)
    return fade(x, 0.0008, 0.05)


def sfx_menu_back():
    n = int(0.32 * FS)
    x = at(n, 0.0, bell_smp(88, 0.25, 2.0, 0.6), 0.5)
    x += at(n, 0.05, bell_smp(81, 0.27, 2.0, 0.6), 0.55)
    return fade(filt(x, 3500, 0.7), 0.0008, 0.05)


def sfx_unlock():
    """A new mech for the line-up: a rising arpeggio, a big E major chord, the choir, a boom."""
    rng = np.random.default_rng(1400)
    dur = 3.0
    t = tt(dur)
    n = len(t)
    x = np.zeros(n)
    for i, mm in enumerate((76, 80, 83, 88, 92, 95)):
        x += at(n, i * 0.06, bell_smp(mm, 0.6, 2.0, 1.2), 0.4)
    s0 = 0.4
    m = n - int(s0 * FS)
    tm = np.arange(m) / FS
    ch = np.zeros(m)
    notes = (52, 64, 68, 71, 76, 80)
    for nt in notes:
        for v in supersaw(nt, m, rng):
            ch += v
    ch /= math.sqrt(len(notes) * 5)
    ch = tvf(ch, 700 + 6000 * np.exp(-tm / 0.5), 1.0) * env_ar(m, 0.004, 1.0, int(1.3 * FS))
    x += at(n, s0, sat(ch * 0.7, 1.3))
    x += at(n, s0, vox_smp([64, 68, 71], 1.4, 'o', rng, 'a'), 0.3)
    x += at(n, s0, cymbal_smp(rng, dur=2.4), 0.3)
    x += at(n, s0, boom_smp(rng, 1.6), 0.6)
    for _ in range(12):
        x += at(n, rng.uniform(0.5, 2.2), bell_smp(rng.choice([100, 104, 107, 112]), 0.3, 3.5, 1.0), 0.07)
    return fade(x, 0.002, 0.3)


# per sound: name, render, its peak in the game (dB of full scale; the music peaks at -8),
# reverb send
ONE_SHOTS = [
    ('hit0', lambda: sfx_hit(0), -11, 1),
    ('hit1', lambda: sfx_hit(1), -9, 1),
    ('hit2', lambda: sfx_hit(2), -7.5, 1),
    ('hit3', lambda: sfx_hit(3), -6.5, 1),
    ('block', sfx_block, -9, 1),
    ('chip', sfx_chip, -16, 1),
    ('swing_hero', sfx_swing_hero, -13, 1),
    ('swing_dblade', sfx_swing_doubleblade, -13, 1),
    ('grab', sfx_grab, -11, 1),
    ('throw', sfx_throw, -6, 1),
    ('break', sfx_break, -10, 1),
    ('land', sfx_land, -10, 1),
    ('step', sfx_step, -15, 1),
    ('meter_full', sfx_meter_full, -13, 1),
    ('super', sfx_super, -7, 1),
    ('ko', sfx_ko, -6, 1),
    ('round', sfx_round, -8, 1),
    ('menu_move', sfx_menu_move, -18, 0),
    ('menu_ok', sfx_menu_ok, -13, 0),
    ('menu_back', sfx_menu_back, -15, 0),
    ('unlock', sfx_unlock, -6, 1),
]


# ================================================================== output

def _encode(args):
    x, loop = args
    return mei_adpcm.encode(x, loop)


def write_wav(path, ch):
    """ch: one or two int16-range arrays (clipped as the console clips)."""
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


def db(x):
    return 20 * math.log10(max(1e-9, x))


def seam_check(blob, n, loop, first):
    """The console's second pass over a loop, decoded with the history the first pass ends
    with, against the first pass: the largest difference (should be 0 or nearly), and the jump
    across the wrap against the stem's typical step (a click shows as a large ratio)."""
    h1, h2 = int(first[n - 1]), int(first[n - 2])
    lb = loop // BLK
    again = mei_adpcm.decode(blob[lb * 16:], n - lb * BLK, h1, h2).astype(np.int64)[loop - lb * BLK:]
    diff = int(np.abs(again - first[loop:n]).max())
    steps = np.abs(np.diff(first[loop:n]))
    jump = abs(int(first[loop]) - int(first[n - 1]))
    return diff, jump / max(1.0, float(np.percentile(steps, 99)))


# a volley of effects over the fight's start, for fight_sfx.wav: (seconds, sound, pan -1..1)
VOLLEY = [(0.4, 'round', 0), (3.2, 'step', -0.25), (3.7, 'step', 0.25), (4.2, 'step', -0.25),
          (4.6, 'swing_hero', -0.2), (4.85, 'hit1', 0.1), (5.6, 'swing_dblade', 0.2), (5.85, 'block', -0.1),
          (6.3, 'chip', -0.1), (7.0, 'hit0', 0.1), (7.25, 'hit0', 0.1), (7.6, 'hit2', 0.1), (8.4, 'land', 0.3),
          (9.0, 'grab', -0.1), (9.6, 'throw', 0.2), (10.8, 'meter_full', 0), (11.5, 'step', 0.2),
          (12.0, 'break', 0), (12.8, 'super', -0.2), (13.4, 'hit3', 0.1), (13.6, 'hit2', 0.1),
          (15.0, 'swing_hero', -0.2), (15.3, 'hit3', 0.15), (15.32, 'ko', 0.15)]


def build(preview, quick=False):
    print('rendering the menu...')
    m_song = Song(MENU_BEAT, MENU_BARS, MENU_SWING)
    m_stems = render_track(m_song, menu_body(m_song), menu_intro(m_song), MENU_BEAT * 4, menu_auto,
                           Kit(5), True, 3)
    print('rendering the fight...')
    f_song = Song(FIGHT_BEAT, FIGHT_BARS)
    f_intro = FIGHT_BEAT * 4 * FIGHT_INTRO_BARS
    f_stems = render_track(f_song, fight_body(f_song), fight_intro(f_song, f_intro * OS), f_intro,
                           fight_auto, Kit(9), False, 3)

    tracks = []      # (name, channels, intro samples, total samples, [(int data, vol)])
    for name, stems, intro, chans in (('fight', f_stems, f_intro, (0, 1, 2)),
                                      ('menu', m_stems, MENU_BEAT * 4, (3, 4, 5))):
        n = len(stems[0])
        assert n % BLK == 0 and intro % BLK == 0, (name, n, intro)
        tracks.append((name, chans, intro, n, mix_levels(stems)))

    print('rendering the sound effects...')
    sfx = []         # (name, int data, volume, reverb)
    for name, fn, level, rev in ONE_SHOTS:
        x = down(hp_dc(fn(), 28.0), False)
        x = x / np.abs(x).max() * STEM_PEAK
        vol = min(255, int(round(256 * 10 ** (level / 20) / STEM_PEAK)))
        x = np.concatenate([x, np.zeros(-len(x) % BLK)])
        sfx.append((name, np.round(x * 32767).astype(np.int64), vol, rev))

    stem_names = ('beat', 'airL', 'airR')
    if quick:      # unencoded previews only, nothing written to the cart
        os.makedirs(preview, exist_ok=True)
        for name, chans, intro, n, st in tracks:
            for si, (data, vol) in enumerate(st):
                write_wav(os.path.join(preview, '%s_%s.wav' % (name, stem_names[si])), [data])
            beat, al, ar = [(d * v) >> 8 for d, v in st]
            two = lambda x: np.concatenate([x, x[intro:]])
            write_wav(os.path.join(preview, '%s.wav' % name), [two(beat + al), two(beat + ar)])
        for name, data, vol, rev in sfx:
            write_wav(os.path.join(preview, 'sfx_%s.wav' % name), [data * vol >> 8])
        return

    print('encoding...')
    jobs = []
    for name, chans, intro, n, st in tracks:
        for data, vol in st:
            jobs.append((data, intro))
    for name, data, vol, rev in sfx:
        jobs.append((data, None))
    with ProcessPoolExecutor() as ex:
        enc = list(ex.map(_encode, jobs))

    os.makedirs(AUD, exist_ok=True)
    mbank = bytearray()
    stem_rows = []
    decoded = []
    k = 0
    for ti, (name, chans, intro, n, st) in enumerate(tracks):
        for si, (data, vol) in enumerate(st):
            blob = enc[k]
            k += 1
            vl, vr = (vol, vol) if si == 0 else ((vol, 0) if si == 1 else (0, vol))
            stem_rows.append((chans[si], len(mbank), n, intro, vl, vr, 1 if si else 0, name, stem_names[si]))
            mbank += blob
            decoded.append((blob, mei_adpcm.decode(blob, n).astype(np.int64), data))
    sbank = bytearray()
    sfx_rows = []
    sfx_dec = {}
    for name, data, vol, rev in sfx:
        blob = enc[k]
        k += 1
        sfx_rows.append((name, len(sbank), len(data), vol, rev))
        sbank += blob
        sfx_dec[name] = (mei_adpcm.decode(blob, len(data)).astype(np.int64), vol)
    with open(os.path.join(AUD, 'music.adp'), 'wb') as f:
        f.write(mbank)
    with open(os.path.join(AUD, 'sfx.adp'), 'wb') as f:
        f.write(sbank)

    # ---- mu_data.akr
    o = []
    o.append('// Generated by tools/gen_mechexpo_audio.py - do not edit.\n')
    o.append('// Mech Expo 2000\'s music stems and sound effects (audio/music.adp, audio/sfx.adp), read by\n')
    o.append('// music.akr and sfx.akr.\n\n')
    o.append('embed MU_BANK: u8 = "audio/music.adp"\n')
    o.append('embed SFX_BANK: u8 = "audio/sfx.adp"\n\n')
    o.append('const MU_REVERB = %d                // the console reverb preset (hall)\n' % REVERB)
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
    o.append('// per sound: byte offset in SFX_BANK, samples, volume, reverb send\n')
    vals = []
    for row in sfx_rows:
        vals += list(row[1:5])
    o.append(akr_array('SFX', 's32', vals, 4))
    with open(os.path.join(CART, 'mu_data.akr'), 'w') as f:
        f.write(''.join(o))

    # ---- the report: sizes, levels, the loops' seams
    print('music.adp %d bytes, sfx.adp %d bytes' % (len(mbank), len(sbank)))
    for r, (blob, d, src) in zip(stem_rows, decoded):
        err = d - src
        snr = 10 * math.log10((src ** 2).mean() / max(1e-9, (err ** 2).mean()))
        diff, ratio = seam_check(blob, r[2], r[3], d)
        print('  %-5s %-4s ch %d  %8d samples (%.2f s), loop at %d, vol %3d/%3d, peak %.1f dB, ADPCM SNR %.1f dB, '
              'second pass differs by %d, wrap step %.2f x the 99th percentile'
              % (r[7], r[8], r[0], r[2], r[2] / SR, r[3], r[4], r[5], db(np.abs(d).max() / 32768), snr, diff, ratio))
    mixes = {}
    for ti, (name, chans, intro, n, st) in enumerate(tracks):
        (_, b, _), (_, al, _), (_, ar, _) = decoded[3 * ti:3 * ti + 3]
        vols = [v for _, v in st]
        L = (b * vols[0] >> 8) + (al * vols[1] >> 8)
        R = (b * vols[0] >> 8) + (ar * vols[2] >> 8)
        mixes[name] = (L, R, intro)
        lp = np.abs(np.concatenate([L, R])).max()
        rms = math.sqrt(((L.astype(float) ** 2 + R.astype(float) ** 2) / 2).mean())
        clip = int((np.abs(np.concatenate([L, R])) > 32767).sum())
        print('  %-5s mix: peak %.1f dBFS, RMS %.1f dBFS, %d samples clipped' % (name, db(lp / 32768), db(rms / 32768), clip))
    for name, off, cnt, vol, rev in sfx_rows:
        d, v = sfx_dec[name]
        print('  sfx %-13s %6d samples (%.2f s) %6d bytes, vol %3d, peak %.1f dBFS%s'
              % (name, cnt, cnt / SR, (cnt + BLK - 1) // BLK * 16, vol, db(np.abs(d * v >> 8).max() / 32768),
                 ', to the reverb' if rev else ''))
    # the balance: the fight's opening with a volley of effects over it, mixed as the console does
    L, R, intro = mixes['fight']
    n = int(20 * SR)
    dip = np.zeros(int(20 * 60) + 1, dtype=np.int64)       # music.akr's dip, frame by frame
    for when, name, pan in VOLLEY:
        if name in ('super', 'ko'):
            f0 = int(when * 60)
            dip[f0:f0 + (90 if name == 'super' else 240)] = 1
    gain = np.zeros(len(dip), dtype=np.int64)
    g = 256
    for f in range(len(dip)):
        tgt = 120 if dip[f] else 256
        g = max(tgt, g - 24) if g > tgt else min(tgt, g + 6)
        gain[f] = g
    gs = gain[np.minimum(np.arange(n) * 60 // SR, len(gain) - 1)]
    VL, VR = L[:n] * gs >> 8, R[:n] * gs >> 8
    kos = [w for w, nm, _ in VOLLEY if nm == 'ko']
    for when, name, pan in VOLLEY:
        if name.startswith('hit') and any(abs(when - w) < 2 / 60 for w in kos):
            continue                  # sfx.akr: the KO's own impact replaces the hit
        d, v = sfx_dec[name]
        p = int(when * SR)
        k2 = min(len(d), n - p)
        vl = v * (256 - int(max(0.0, pan) * 160)) >> 8
        vr = v * (256 - int(max(0.0, -pan) * 160)) >> 8
        VL[p:p + k2] += d[:k2] * vl >> 8
        VR[p:p + k2] += d[:k2] * vr >> 8
    both = np.concatenate([VL, VR])
    print('  fight + volley: peak %.1f dBFS, %d of %d samples clipped'
          % (db(np.abs(both).max() / 32768), int((np.abs(both) > 32767).sum()), len(both)))

    if preview:
        os.makedirs(preview, exist_ok=True)
        k = 0
        for ti, (name, chans, intro, n, st) in enumerate(tracks):
            for si in range(3):
                write_wav(os.path.join(preview, '%s_%s.wav' % (name, stem_names[si])), [decoded[3 * ti + si][1]])
            L, R, intro = mixes[name]
            two = lambda x: np.concatenate([x, x[intro:]])
            write_wav(os.path.join(preview, '%s.wav' % name), [two(L), two(R)])
        for name, (d, v) in sfx_dec.items():
            write_wav(os.path.join(preview, 'sfx_%s.wav' % name), [d * v >> 8])
        write_wav(os.path.join(preview, 'fight_sfx.wav'), [VL, VR])
        print('previews in', preview)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--preview', metavar='DIR', help='also write WAVs to listen to')
    a = ap.parse_args()
    build(a.preview, bool(os.environ.get('MX_QUICK')) and bool(a.preview))


if __name__ == '__main__':
    main()
