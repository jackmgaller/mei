#!/usr/bin/env python3
"""After Hours' music, sound effects and room ambiences, synthesised from nothing (no samples).

Music. "Shutters Down", one original stage track: late-90s Tokyo at night in style only
(Shibuya-kei and acid jazz: a soft swung break, an upright bass, a suitcase electric piano, a
nylon guitar's bossa comp, a vibraphone), 91.9 bpm in D minor, kept low and even so it stays out
of the way of the timing. A one-bar intro (the electric piano on the dominant, the bass's pickup)
then a 32-bar loop (83.5 s, longer than a room): A the groove (piano, bass, brushes and hats), B
the bossa (guitar, shaker, the vibraphone's tune), C the breakdown (strings, slow vibraphone
arpeggios, rim and shaker), D the groove again with the vibraphone answering, which runs back into
A without a fill or an ending, so a restart never lands on a cadence. Three ADPCM stems that the
console loops by itself: `beat` (drums and bass, mono, dry) and `air L`, `air R` (the rest, a
stereo pair sent to the reverb). A bar is a whole number of 28-sample blocks; the loop is
rendered twice and the second pass kept, so every tail that crosses the loop point wraps in.

Sound effects, one-shots: footsteps (a soft sole walking, a heel strike running), the caught
sting, hiding in and out, a train's horn from the tunnel, its brakes, its doors opening, the
door chime before they close, the doors closing, the staff door opening (the exit) and shutting
behind him (a room's entry), the transition's air, the menu's move, ok, back and deny, a stage
cleared, a guard's alert, a fragile thing knocked over, the pocket bell's beeps, the retry's
rewind, a keycard picked up and a staff door unlocked. Loops, played from their start and stopped by the cart: a train running (its pitch is
the cart's: the speed) and a stopped train idling, and the rooms' ambiences (level 1's: the
platform's hum, the ticket gates' standby, the passage's tubes, the lobby's air handling, the
aquarium's pumps; stage 2's: the cinema, the projection booth, the staff corridor, the shop floor,
the food hall), each rendered periodic (their filters run round the seam).

The reverb is the console's: preset 3 (hall), its decay set per room by dr_audio.akr.

Writes carts/afterhours/audio/music.adp, carts/afterhours/audio/sfx.adp and
carts/afterhours/au_data.akr (the tables carts/afterhours/dr_audio.akr reads).
    python3 tools/gen_afterhours_audio.py [--preview DIR]
--preview writes track.wav (the stems decoded and mixed as the console mixes them, without the
reverb: the intro, then the loop twice so its seam can be heard), the stems, every sound (a loop
three times over, decoded as the console wraps it) and play.wav (the track's first 25 seconds
with a room's ambience, steps, a train and a catch over it, for the balance). It prints sizes,
levels, clipping and the loops' seams. Needs NumPy and SciPy.
"""
import argparse, math, os, sys, wave
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'afterhours')
AUD = os.path.join(CART, 'audio')

SR = 22050                 # the console's rate
OS = 2                     # everything is rendered at twice that, then filtered down
FS = SR * OS
BLK = 28                   # samples in an ADPCM block

REVERB = 3                 # hall
REV_WET = 96               # its wet level, both sides

BEAT = 14392               # samples a beat at SR: 91.93 bpm; a bar (57,568) is 2,056 blocks
STEP = BEAT // 4           # a sixteenth, 3,598 samples
BARS = 32
INTRO_BARS = 1
SWING = 0.11               # odd sixteenths late by this much of a sixteenth

MASTER_PEAK = 0.38         # the track's stereo mix peaks here (-8.4 dBFS): room for the rest
SFX_TRIM = 3.0             # dB added to every sound's level below (ONE_SHOTS, LOOPS)
STEM_PEAK = 0.97           # each sound is stored this loud; its channel volume brings it down
AIR_GAIN = 3.0             # the air (piano, guitar, vibraphone, strings) against the beat
LEAD_IN = 2 * BLK          # a loop's lead-in: its last two blocks before its first (mei_adpcm.py)


# ================================================================== DSP

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
        b, a = rbj(fc[i], q, mode)
        y[i:i + blk], zi = signal.lfilter(b, a, x[i:i + blk], zi=zi)
    return y


def onepole(x, f):
    p = math.exp(-2 * math.pi * f / FS)
    return signal.lfilter([1 - p], [1, -p], x)


def sine(freq, ph0=0.0):
    return np.sin(2 * math.pi * (ph0 + np.cumsum(np.asarray(freq, dtype=float)) / FS))


def _blep(ph, dt):
    out = np.zeros_like(ph)
    m = ph < dt
    t = ph[m] / dt[m]
    out[m] = t + t - t * t - 1
    m = ph > 1 - dt
    t = (ph[m] - 1) / dt[m]
    out[m] = t * t + t + t + 1
    return out


def saw(freq, ph0=0.0):
    """Band-limited (PolyBLEP) saw, freq a number or per sample."""
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / FS, np.shape(freq)).copy()
    ph = (ph0 + np.cumsum(dt) - dt) % 1.0
    return 2 * ph - 1 - _blep(ph, dt)


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


def put_circ(buf, pos, sig, g=1.0):
    """sig added at pos, wrapping round the end of buf (a loop's events)."""
    n = len(buf)
    pos = int(pos) % n
    k = min(len(sig), n)
    end = pos + k
    if end <= n:
        buf[pos:end] += g * sig[:k]
    else:
        buf[pos:] += g * sig[:n - pos]
        buf[:end - n] += g * sig[n - pos:k]


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


def edges(x, att=0.0008, rel=0.03):
    """A click-free start and end."""
    n = len(x)
    t = np.arange(n) / FS
    return x * np.clip(t / att, 0, 1) * np.clip((n / FS - t) / rel, 0, 1)


def noise(rng, n):
    return rng.standard_normal(n)


def tile3(x):
    """Three copies end to end: a filter run over them and cut to the middle copy is circular
    (its state at the start is what the end leaves), for the loops."""
    return np.concatenate([x, x, x])


def mid3(y):
    n = len(y) // 3
    return y[n:2 * n]


def cfilt(x, f, q=0.707, mode='lp'):
    """filt, circular (for the loops)."""
    return mid3(filt(tile3(x), f, q, mode))


def loop_hz(f, n):
    """The nearest frequency with a whole number of cycles in n samples at FS (a loop's tones)."""
    return max(1, round(f * n / FS)) * FS / n


# ================================================================== instruments

def kick(rng, vel=1.0):
    t = tt(0.4)
    f = 48 + 70 * np.exp(-t / 0.022)
    body = sine(f) * np.exp(-t / 0.16) * np.clip(t / 0.0015, 0, 1)
    ck = filt(noise(rng, len(t)), 1800, 0.7, 'hp') * np.exp(-t / 0.003) * 0.12
    return sat(body + ck, 1.4) * vel * np.clip((0.4 - t) / 0.03, 0, 1)


def rim(rng, vel=1.0):
    """A sidestick: a woody click and a short ring."""
    t = tt(0.12)
    click = filt(noise(rng, len(t)), 1900, 2.2, 'bp') * np.exp(-t / 0.006)
    ring = np.sin(2 * math.pi * 410 * t) * np.exp(-t / 0.018) * 0.5
    return (click * 1.6 + ring) * vel


def brush(rng, vel=1.0, dur=0.22):
    """A brush on the snare: a soft swish."""
    t = tt(dur)
    x = filt(filt(noise(rng, len(t)), 5200, 0.6, 'lp'), 700, 0.7, 'hp')
    env = np.clip(t / 0.008, 0, 1) * np.exp(-t / (dur / 3))
    return x * env * 0.5 * vel


def hat(rng, vel=1.0, dec=0.022):
    t = tt(max(0.08, dec * 6))
    m = np.zeros(len(t))
    for r in (1.0, 1.342, 1.783, 2.217, 2.531, 3.11):       # inharmonic square partials
        m += np.sign(np.sin(2 * math.pi * 330 * r * t + rng.uniform(0, 6)))
    x = filt(m / 6 + 0.6 * noise(rng, len(t)), 7200, 0.7, 'hp')
    return x * np.exp(-t / dec) * 0.35 * vel


def shaker(rng, vel=1.0):
    t = tt(0.1)
    x = filt(noise(rng, len(t)), 5200, 1.2, 'bp')
    return x * np.clip(t / 0.014, 0, 1) * np.exp(-t / 0.03) * 0.5 * vel


def bass_note(midi, dur, vel=1.0, rng=None):
    """An upright: a round finger pluck, a little slide into the note."""
    t = tt(dur + 0.12)
    f = mtof(midi) * 2 ** ((-0.25 * np.exp(-t / 0.025)) / 12)
    ph = np.cumsum(f) / FS
    x = np.sin(2 * math.pi * ph) + 0.32 * np.sin(4 * math.pi * ph) + 0.1 * np.sin(6 * math.pi * ph)
    env = (0.28 + 0.72 * np.exp(-t / 0.22)) * np.exp(-t / 1.6) * np.clip(t / 0.004, 0, 1)
    env *= env_ar(len(t), 0.0, 0.07, int(dur * FS))
    thump = filt(noise(rng, len(t)), 700, 0.8, 'lp') * np.exp(-t / 0.012) * 0.35
    return (x * env + thump) * vel


def epiano(midi, dur, vel=1.0):
    """A suitcase electric piano (FM): a soft tine over a round tone."""
    t = tt(dur + 0.5)
    f = float(mtof(midi))
    idx = (0.4 + 1.2 * vel) * np.exp(-t / 0.4) + 0.2
    x = np.sin(2 * math.pi * f * t + idx * np.sin(2 * math.pi * f * t))
    x += 0.18 * vel * np.sin(2 * math.pi * f * 14.0 * t) * np.exp(-t / 0.018)
    env = np.exp(-t / 1.8) * np.clip(t / 0.003, 0, 1) * env_ar(len(t), 0.0, 0.3, int(dur * FS))
    return x * env * vel


def vibes(midi, dur=2.0, vel=1.0, motor=5.4):
    """A vibraphone: the bar's partials (1, 3.9, 9.2), a mallet's tick, the motor's tremolo."""
    t = tt(dur)
    f = float(mtof(midi))
    x = np.sin(2 * math.pi * f * t) * np.exp(-t / 1.1)
    x += 0.22 * np.sin(2 * math.pi * f * 3.9 * t) * np.exp(-t / 0.18)
    x += 0.05 * np.sin(2 * math.pi * f * 9.2 * t) * np.exp(-t / 0.05)
    x *= 1 - 0.3 * (0.5 + 0.5 * np.sin(2 * math.pi * motor * t))
    return edges(x * np.clip(t / 0.0015, 0, 1), 0.0015, 0.08) * vel


def marimba(midi, dur=0.5, vel=1.0, bend=0.0):
    t = tt(dur)
    f = float(mtof(midi)) * 2 ** (bend * np.clip(t / 0.08, 0, 1) / 12)
    ph = np.cumsum(f) / FS
    x = np.sin(2 * math.pi * ph) * np.exp(-t / 0.16) + 0.3 * np.sin(2 * math.pi * 4 * ph) * np.exp(-t / 0.03)
    return edges(x, 0.001, 0.03) * vel


_GUITAR = {}


def guitar(midi, dur, vel=1.0):
    """A nylon string (Karplus-Strong), damped after dur; each pitch is plucked once and reused."""
    if midi not in _GUITAR:
        n = int(1.6 * FS)
        d = int(round(FS / float(mtof(midi)) - 0.5))      # the loop's averaging adds half a sample
        rng = np.random.default_rng(1000 + midi)
        exc = np.zeros(n)
        exc[:d + 1] = filt(rng.uniform(-1, 1, d + 1), 2600, 0.7, 'lp')
        # y[n] = x[n] + g (y[n-d] + y[n-d-1]) / 2
        g = 0.996
        a = np.zeros(d + 2)
        a[0] = 1
        a[d] = -g * 0.5
        a[d + 1] = -g * 0.5
        y = signal.lfilter([1.0], a, exc)
        y = filt(y, 3200, 0.7, 'lp')
        _GUITAR[midi] = y / max(1e-9, np.abs(y).max())
    y = _GUITAR[midi]
    k = min(len(y), int((dur + 0.08) * FS))
    return y[:k] * env_ar(k, 0.0, 0.08, int(dur * FS)) * vel


def strings(notes, dur, rng, vel=1.0):
    """A soft string pad: detuned saws, dark, slow."""
    n = int((dur + 1.0) * FS)
    t = np.arange(n) / FS
    x = np.zeros(n)
    for m in notes:
        for det in (-0.09, 0.0, 0.08):
            f = mtof(m + det) * (1 + 0.003 * np.sin(2 * math.pi * 0.4 * t + rng.uniform(0, 6)))
            x += saw(f, rng.uniform())
    x = filt(filt(x, 1400, 0.6, 'lp'), 180, 0.7, 'hp') / (3 * len(notes))
    return x * env_ar(n, 0.7, 0.9, int(dur * FS)) * vel


# ================================================================== the song

# chords: name -> (bass root, electric piano voicing (rootless), guitar voicing)
CH = {
    'Dm9':     (38, [65, 69, 72, 76], [53, 57, 60, 64]),
    'G13':     (43, [65, 69, 71, 76], [53, 59, 64]),
    'Cmaj9':   (36, [64, 67, 71, 74], [52, 55, 59, 62]),
    'Am9':     (33, [60, 64, 67, 71], [55, 60, 64, 67]),
    'Ebmaj7':  (39, [63, 67, 70, 74], [55, 58, 62]),
    'A7alt':   (33, [61, 65, 67, 72], [55, 61, 65]),
    'Bbmaj9':  (34, [62, 65, 69, 72], [53, 57, 60, 62]),
    'A9sus':   (33, [62, 64, 67, 71], [55, 59, 62, 64]),
    'A7b9':    (33, [61, 64, 67, 70], [55, 58, 61, 64]),
    'Dm9/C':   (36, [65, 69, 72, 76], [53, 57, 60, 64]),
    'Gm9':     (43, [65, 69, 70, 74], [53, 57, 58, 62]),
    'C13':     (36, [64, 69, 70, 74], [52, 57, 58]),
    'Fmaj9':   (41, [64, 67, 69, 72], [52, 55, 57, 60]),
    'E7#9':    (40, [62, 67, 68, 71], [56, 62, 67]),
    'A9b13':   (33, [61, 65, 67, 71], [55, 61, 65]),
}

# a bar's chords: one name, or two (half a bar each)
SECTION_A = ['Dm9', 'G13', 'Cmaj9', 'Am9', 'Dm9', 'G13', 'Ebmaj7', 'A7alt']
SECTION_B = ['Bbmaj9', ('A9sus', 'A7b9'), 'Dm9', 'Dm9/C', 'Gm9', 'C13', 'Fmaj9', ('E7#9', 'A9b13')]
SECTION_C = ['Dm9', 'Dm9', 'Bbmaj9', 'Bbmaj9', 'Gm9', 'Gm9', 'A9sus', 'A7b9']
FORM = [('A', c) for c in SECTION_A] + [('B', c) for c in SECTION_B] + \
       [('C', c) for c in SECTION_C] + [('D', c) for c in SECTION_A]

# the vibraphone's tune (B) and its answers (D): (bar, sixteenth, length in sixteenths, midi)
TUNE = [(8, 0, 6, 74), (8, 6, 2, 72), (8, 8, 8, 69),
        (9, 2, 4, 76), (9, 8, 6, 73),
        (10, 0, 4, 77), (10, 4, 4, 76), (10, 8, 8, 69),
        (11, 10, 2, 67), (11, 12, 4, 69),
        (12, 0, 6, 70), (12, 6, 2, 69), (12, 8, 8, 65),
        (13, 2, 4, 69), (13, 6, 2, 70), (13, 8, 8, 72),
        (14, 0, 8, 76), (14, 8, 4, 74), (14, 12, 4, 72),
        (15, 0, 4, 71), (15, 4, 4, 68), (15, 8, 4, 65), (15, 12, 4, 64),
        (24, 8, 4, 76), (24, 12, 4, 77), (25, 0, 8, 76),
        (26, 8, 4, 74), (26, 12, 4, 71), (27, 0, 8, 72),
        (28, 8, 4, 81), (28, 12, 4, 77), (29, 0, 8, 76),
        (30, 4, 4, 74), (30, 8, 8, 70),
        (31, 0, 6, 73), (31, 8, 4, 72), (31, 12, 4, 69)]

BOSSA_GTR = [[0, 3, 6, 10, 12], [2, 6, 8, 12, 14]]       # the guitar's two-bar comp
BOSSA_RIM = [[0, 6, 12], [4, 10]]                        # the rim's clave


def chords_of(c):
    return [c, c] if isinstance(c, str) else list(c)


class Track:
    """Renders events into the three stems at FS: beat (mono), air left, air right."""

    def __init__(self, n, seed):
        self.n = n
        self.beat = np.zeros(n)
        self.al = np.zeros(n)
        self.ar = np.zeros(n)
        self.rng = np.random.default_rng(seed)

    def pos(self, bar, step):
        """The sample at FS of a sixteenth (swung) of a bar."""
        s = step + (SWING if int(step) % 2 == 1 else 0.0)
        return int(round((bar * 4 * BEAT + s * STEP) * OS))

    def mono(self, bar, step, sig, g):
        put(self.beat, self.pos(bar, step), sig, g)

    def air(self, bar, step, sig, g, pan=0.0):
        p = self.pos(bar, step)
        put(self.al, p, sig, AIR_GAIN * g * math.sqrt(0.5 - 0.5 * pan))
        put(self.ar, p, sig, AIR_GAIN * g * math.sqrt(0.5 + 0.5 * pan))

    def air_st(self, bar, step, left, right, g):
        p = self.pos(bar, step)
        put(self.al, p, left, AIR_GAIN * g)
        put(self.ar, p, right, AIR_GAIN * g)


def tremolo_pan(x, rate=3.1, depth=0.55, ph=0.0):
    """The suitcase piano's stereo vibrato: the sound moves between the speakers."""
    t = np.arange(len(x)) / FS
    s = np.sin(2 * math.pi * rate * t + ph)
    return x * np.sqrt(0.5 - 0.5 * depth * s), x * np.sqrt(0.5 + 0.5 * depth * s)


def drums(tr, bar, sec, rng):
    sl = STEP / FS * OS
    if sec in ('A', 'D'):
        for st, v in ((0, 1.0), (6, 0.35), (10, 0.8)):
            tr.mono(bar, st, kick(rng, v), 0.62)
        for st in (4, 12):
            tr.mono(bar, st, rim(rng, 1.0), 0.30)
            tr.mono(bar, st, brush(rng, 0.8), 0.30)
        for st, v in ((7, 0.3), (15, 0.22), (13, 0.15)):
            tr.mono(bar, st, brush(rng, v, 0.12), 0.30)
        for st in range(16):
            v = 0.75 if st % 4 == 2 else (0.5 if st % 2 == 0 else 0.26)
            v *= 0.92 + 0.16 * rng.uniform()
            dec = 0.11 if (sec == 'D' and st == 14 and bar % 2 == 1) else 0.022
            tr.mono(bar, st, hat(rng, v, dec), 0.20)
    elif sec == 'B':
        for st, v in ((0, 1.0), (6, 0.45), (8, 0.85), (14, 0.45)):
            tr.mono(bar, st, kick(rng, v), 0.55)
        for st in BOSSA_RIM[bar % 2]:
            tr.mono(bar, st, rim(rng, 0.75), 0.30)
        for st in range(16):
            v = 0.8 if st % 2 == 0 else 0.45
            tr.mono(bar, st, shaker(rng, v * (0.9 + 0.2 * rng.uniform())), 0.22)
            if st % 2 == 0:
                tr.mono(bar, st, hat(rng, 0.3 if st % 4 else 0.45), 0.16)
    else:   # C, the breakdown
        if bar % 2 == 0:
            tr.mono(bar, 0, kick(rng, 0.6), 0.55)
        tr.mono(bar, 12, rim(rng, 0.6), 0.28)
        for st in range(16):
            v = 0.55 if st % 2 == 0 else 0.3
            tr.mono(bar, st, shaker(rng, v * (0.9 + 0.2 * rng.uniform())), 0.20)


def bass(tr, bar, sec, chords, nxt, rng):
    r = [CH[c][0] for c in chords]
    nroot = CH[nxt][0]
    app = nroot - 1 if nroot - 1 != r[1] else nroot + 1      # the step into the next bar's root
    if sec in ('A', 'D'):
        notes = [(0, 5, r[0], 1.0), (6, 2, r[0] + 12, 0.55), (8, 4, r[1] + 7, 0.8), (14, 2, app, 0.75)]
        if r[0] != r[1]:
            notes[2] = (8, 4, r[1], 0.85)
    elif sec == 'B':
        notes = [(0, 5, r[0], 1.0), (6, 2, r[0] + 7, 0.7), (8, 5, r[1], 0.9), (14, 2, r[1] + 7, 0.7)]
    else:
        notes = [(0, 11, r[0], 0.9), (12, 4, r[1] + 7, 0.6)]
    for st, ln, m, v in notes:
        tr.mono(bar, st, bass_note(m, ln * STEP / SR * 0.92, v, rng), 0.55)


def keys(tr, bar, sec, chords, rng):
    sixteenth = STEP / SR
    if sec == 'A':
        hits = [(0, 6, 0.7, 0), (10, 4, 0.5, 1)]
    elif sec == 'D':
        hits = [(0, 3, 0.6, 0), (3, 4, 0.5, 0), (10, 5, 0.55, 1)]
    elif sec == 'B':
        hits = [(0, 15, 0.32, 0)]
    else:
        return
    for st, ln, v, half in hits:
        c = chords[1] if (half and st >= 8) else chords[0]
        x = np.zeros(int((ln * sixteenth + 0.6) * FS))
        for m in CH[c][1]:
            put(x, int(rng.uniform(0, 0.006) * FS), epiano(m, ln * sixteenth, v))
        left, right = tremolo_pan(x, ph=rng.uniform(0, 6))
        tr.air_st(bar, st, left, right, 0.11)


def nylon(tr, bar, chords):
    for st in BOSSA_GTR[bar % 2]:
        c = chords[1] if st >= 8 else chords[0]
        x = np.zeros(int(0.9 * FS))
        for i, m in enumerate(CH[c][2]):
            put(x, int(i * 0.007 * FS), guitar(m, 2 * STEP / SR, 0.85 if st % 4 else 1.0))
        tr.air(bar, st, x, 0.10, pan=-0.35)


def render_song(seed=3):
    """Returns the three stems at SR: the intro bar, then one loop."""
    L = BARS * 4 * BEAT * OS
    tail = int(4 * FS)
    tr = Track(2 * L + tail, seed)
    rng = tr.rng
    for p in range(2):                   # two passes; the second is kept
        for i, (sec, c) in enumerate(FORM):
            bar = p * BARS + i
            chords = chords_of(c)
            nxt = chords_of(FORM[(i + 1) % BARS][1])[0]
            drums(tr, bar, sec, rng)
            bass(tr, bar, sec, chords, nxt, rng)
            keys(tr, bar, sec, chords, rng)
            if sec == 'B':
                nylon(tr, bar, chords)
                if i % 4 == 0:
                    tr.air(bar, 0, strings(CH[chords[0]][1], 4 * 4 * BEAT / SR, rng, 0.6), 0.05)
            if sec == 'C':
                if i % 2 == 0:
                    tr.air(bar, 0, strings(CH[chords[0]][1], 2 * 4 * BEAT / SR, rng), 0.13)
                tones = sorted(CH[chords[0]][1])
                for k in range(4):
                    m = tones[k % len(tones)] + (12 if i % 2 else 0)
                    tr.air(bar, 4 * k, vibes(m, 2.2, 0.5), 0.1, pan=0.5 - 0.33 * k)
        for b, st, ln, m in TUNE:
            tr.air(p * BARS + b, st, vibes(m, max(1.2, ln * STEP / SR + 0.8)), 0.12, pan=0.3)
    body = [down(s[L:2 * L], True) for s in (tr.beat, tr.al, tr.ar)]

    # the intro: a bar on the dominant (A7alt), the bass's pickup into the loop's first bar
    ni = INTRO_BARS * 4 * BEAT * OS
    it = Track(ni, seed + 8)
    x = np.zeros(int(3.0 * FS))
    for m in CH['A7alt'][1]:
        put(x, 0, epiano(m, 2.4, 0.45))
    left, right = tremolo_pan(x)
    it.air_st(0, 0, left, right, 0.11)
    for st in range(8, 16, 2):
        it.mono(0, st, hat(it.rng, 0.25 + 0.04 * st), 0.2)
    it.mono(0, 12, bass_note(33, 2 * STEP / SR, 0.7, it.rng), 0.55)
    it.mono(0, 14, bass_note(37, 2 * STEP / SR, 0.8, it.rng), 0.55)
    it.air(0, 14, vibes(69, 1.4, 0.7), 0.12, pan=0.3)
    intro = [down(s, False) for s in (it.beat, it.al, it.ar)]
    return [np.concatenate([a, b]) for a, b in zip(intro, body)]


def mix_levels(stems):
    """Each stem's storage gain and channel volumes, so that the console's mix (L = beat + air L,
    R = beat + air R) peaks at MASTER_PEAK."""
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

def thud(t, f0, f1, tp, dec):
    f = f1 + (f0 - f1) * np.exp(-t / tp)
    return sine(f) * np.exp(-t / dec) * np.clip(t / 0.001, 0, 1)


def burst(rng, n, fc, q, dec, mode='bp', att=0.0005):
    t = np.arange(n) / FS
    return filt(noise(rng, n), fc, q, mode) * np.exp(-t / dec) * np.clip(t / max(att, 1e-5), 0, 1)


def at(n, start, sig, g=1.0):
    out = np.zeros(n)
    put(out, int(start * FS), sig, g)
    return out


def sfx_step_walk():
    rng = np.random.default_rng(11)
    t = tt(0.12)
    n = len(t)
    scuff = burst(rng, n, 900, 0.8, 0.022, att=0.004)
    body = thud(t, 150, 95, 0.01, 0.018) * 0.6
    tick = burst(rng, n, 3500, 1.5, 0.003) * 0.15
    return edges(scuff + body + tick, 0.0005, 0.02)


def sfx_step_run():
    rng = np.random.default_rng(12)
    t = tt(0.18)
    n = len(t)
    heel = burst(rng, n, 2600, 0.8, 0.002, 'hp') * 0.7
    body = thud(t, 190, 80, 0.008, 0.03)
    toe = at(n, 0.03, burst(rng, n, 1500, 0.9, 0.035, att=0.003), 0.45)
    return edges(heel + body + toe, 0.0003, 0.03)


def sfx_caught():
    """The sting: a mallet cluster struck hard (the tritone over D), a low drop under it."""
    rng = np.random.default_rng(13)
    t = tt(0.95)
    n = len(t)
    x = np.zeros(n)
    for m, g in ((74, 1.0), (80, 0.8), (85, 0.6), (62, 0.7)):
        f = float(mtof(m))
        mod = 1.6 * np.exp(-t / 0.05) * np.sin(2 * math.pi * f * 3.5 * t)
        x += g * np.sin(2 * math.pi * f * t + mod) * np.exp(-t / 0.32)
    x *= 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * math.pi * 9 * t))
    low = sine(55 + 20 * np.exp(-t / 0.15)) * np.exp(-t / 0.3) * 1.6
    hit = burst(rng, n, 3000, 0.6, 0.012) * 1.2
    return edges(x / 3 + low + hit, 0.0003, 0.12)


def rustle(rng, dur, f0, f1, grain=38.0):
    t = tt(dur)
    n = len(t)
    fc = f0 + (f1 - f0) * t / dur
    x = tvf(noise(rng, n), fc, 1.1, 'bp')
    g = np.repeat(rng.uniform(0.3, 1.0, int(dur * grain) + 2), int(FS / grain) + 1)[:n]
    g = filt(g, 120, 0.7, 'lp')
    return x * g * np.sin(math.pi * np.clip(t / dur, 0, 1)) ** 0.7


def sfx_hide_in():
    rng = np.random.default_rng(14)
    n = int(0.42 * FS)
    t = np.arange(n) / FS
    x = at(n, 0.0, rustle(rng, 0.3, 1400, 2600))
    x += at(n, 0.24, thud(t, 120, 70, 0.01, 0.04), 0.5)
    x += at(n, 0.25, burst(rng, n, 600, 0.8, 0.03), 0.3)
    return edges(x, 0.002, 0.04)


def sfx_hide_out():
    rng = np.random.default_rng(15)
    n = int(0.36 * FS)
    t = np.arange(n) / FS
    x = at(n, 0.0, rustle(rng, 0.26, 2200, 3400, 50.0))
    x += at(n, 0.2, burst(rng, n, 1200, 0.9, 0.025), 0.35)
    x += at(n, 0.2, thud(t, 170, 100, 0.008, 0.02), 0.3)
    return edges(x, 0.002, 0.04)


def sfx_train_horn():
    """An electric horn down the tunnel: two tones a major third apart, far and dark."""
    rng = np.random.default_rng(16)
    t = tt(1.5)
    env = env_ar(len(t), 0.06, 0.45, int(0.75 * FS))
    vib = 1 + 0.004 * np.sin(2 * math.pi * 5 * t)
    x = saw(311 * vib) + 0.8 * saw(392 * vib)
    x = filt(filt(x, 1300, 0.9, 'lp'), 250, 0.7, 'hp') * env
    x += filt(noise(rng, len(t)), 200, 0.7, 'lp') * env * 0.4      # the tunnel's air pushed ahead
    return edges(x, 0.01, 0.1)


def sfx_train_brake():
    """The brakes' squeal swelling and wavering as it stops."""
    rng = np.random.default_rng(17)
    t = tt(1.6)
    n = len(t)
    wob = np.cumsum(rng.standard_normal(n)) / FS
    wob = filt(wob - wob.mean(), 6, 0.7, 'lp')
    f = 2700 + 35 * np.sin(2 * math.pi * 6.5 * t) + 4000 * wob - 120 * t
    x = sine(f) + 0.35 * sine(f * 1.47) + 0.15 * sine(f * 0.5)
    env = np.clip(t / 0.5, 0, 1) ** 1.5 * np.clip((1.6 - t) / 0.35, 0, 1)
    env *= 0.75 + 0.25 * np.sin(2 * math.pi * 2.3 * t)
    grind = filt(noise(rng, n), 900, 0.7, 'bp') * np.clip(t / 0.3, 0, 1) * np.clip((1.4 - t) / 0.4, 0, 1)
    return edges(x * env * 0.5 + grind * 0.35, 0.02, 0.1)


def door_slide(rng, dur, f=420):
    t = tt(dur)
    n = len(t)
    x = filt(noise(rng, n), f, 1.2, 'bp')
    roll = 1 + 0.4 * np.sin(2 * math.pi * 23 * t)
    return x * roll * np.sin(math.pi * np.clip(t / dur, 0, 1)) ** 0.6


def sfx_doors_open():
    rng = np.random.default_rng(18)
    n = int(0.95 * FS)
    t = np.arange(n) / FS
    x = burst(rng, n, 3200, 0.7, 0.18, att=0.006) * 0.8          # the air
    x += at(n, 0.05, door_slide(rng, 0.55), 0.9)
    x += at(n, 0.6, thud(t, 140, 85, 0.01, 0.05), 0.8)
    x += at(n, 0.6, burst(rng, n, 1800, 1.0, 0.01), 0.4)
    return edges(x, 0.002, 0.05)


def sfx_door_chime():
    """The doors' warning: a soft two-tone chime, twice (high, low, high, low)."""
    t = tt(1.25)
    n = len(t)
    x = np.zeros(n)
    for i, m in enumerate((84, 79, 84, 79)):
        f = float(mtof(m))
        tn = tt(0.55)
        tone = np.sin(2 * math.pi * f * tn + 0.6 * np.exp(-tn / 0.06) * np.sin(2 * math.pi * 2 * f * tn))
        tone = tone * np.exp(-tn / 0.22) * np.clip(tn / 0.004, 0, 1)
        put(x, int(i * 0.24 * FS), tone)
    return edges(x, 0.001, 0.08)


def sfx_doors_close():
    rng = np.random.default_rng(19)
    n = int(0.8 * FS)
    t = np.arange(n) / FS
    x = door_slide(rng, 0.45, 480)
    x = np.concatenate([x, np.zeros(n - len(x))])
    x += at(n, 0.44, thud(t, 120, 70, 0.012, 0.07), 1.2)
    x += at(n, 0.44, burst(rng, n, 900, 0.9, 0.02), 0.6)
    x += at(n, 0.47, burst(rng, n, 3000, 0.7, 0.12, att=0.01), 0.35)
    return edges(x, 0.002, 0.05)


def sfx_door_open():
    """The staff door: the push bar's latch, the clunk, a short creak."""
    rng = np.random.default_rng(20)
    n = int(0.65 * FS)
    t = np.arange(n) / FS
    latch = burst(rng, n, 3500, 0.8, 0.003, 'hp') * 0.6 + np.sin(2 * math.pi * 1900 * t) * np.exp(-t / 0.02) * 0.25
    clunk = (np.sin(2 * math.pi * 220 * t) + 0.6 * np.sin(2 * math.pi * 640 * t)) * np.exp(-t / 0.05) * np.clip(t / 0.001, 0, 1)
    tc = tt(0.35)
    f = 150 + 30 * np.sin(2 * math.pi * 3 * tc)
    creak = filt(saw(f), 1100, 3.0, 'bp') * np.sin(math.pi * tc / 0.35) * (0.7 + 0.3 * np.sign(np.sin(2 * math.pi * 31 * tc)))
    x = latch + at(n, 0.07, clunk, 0.9) + at(n, 0.16, creak, 0.25)
    return edges(x, 0.0005, 0.05)


def sfx_door_shut():
    """A heavy door closing behind him: the air, the thud, the latch."""
    rng = np.random.default_rng(21)
    n = int(0.55 * FS)
    t = np.arange(n) / FS
    air = filt(noise(rng, n), 220, 0.7, 'lp') * np.clip(t / 0.06, 0, 1) * np.exp(-t / 0.06) * 0.8
    x = air + at(n, 0.07, thud(t, 110, 62, 0.012, 0.12), 1.0)
    x += at(n, 0.07, burst(rng, n, 1400, 0.8, 0.01), 0.35)
    x += at(n, 0.1, burst(rng, n, 4000, 1.5, 0.004), 0.3)
    return edges(x, 0.002, 0.06)


def sfx_transition():
    """The pull-back: a slow air rising and settling, a low breath under it."""
    rng = np.random.default_rng(22)
    dur = 1.6
    t = tt(dur)
    n = len(t)
    shape = np.sin(math.pi * np.clip(t / dur, 0, 1)) ** 1.6
    peak = 0.55
    fc = 350 + 1800 * np.where(t < peak, t / peak, np.clip(1 - (t - peak) / (dur - peak), 0, 1)) ** 1.5
    x = tvf(noise(rng, n), fc, 1.4, 'bp', 128) * shape
    x += sine(55 + 8 * t) * shape * 0.35
    x += vibes(81, dur, 0.06)[:n] * np.clip(t / 0.3, 0, 1)
    return edges(x, 0.01, 0.1)


def sfx_menu_move():
    t = tt(0.08)
    f = 1500 * (1 + 0.5 * np.exp(-t / 0.004))
    return edges(sine(f) * np.exp(-t / 0.018) + 0.3 * sine(f * 2.7) * np.exp(-t / 0.006), 0.0004, 0.01)


def sfx_menu_ok():
    n = int(0.8 * FS)
    x = at(n, 0.0, vibes(69, 0.8, 0.9), 1.0) + at(n, 0.075, vibes(76, 0.7, 1.0), 1.0)
    return edges(x, 0.001, 0.08)


def sfx_menu_back():
    n = int(0.5 * FS)
    x = at(n, 0.0, vibes(76, 0.5, 0.7), 0.9) + at(n, 0.06, vibes(69, 0.44, 0.7), 0.9)
    return edges(x, 0.001, 0.08)


def sfx_menu_deny():
    t = tt(0.26)
    n = len(t)
    one = filt(np.sign(np.sin(2 * math.pi * 110 * tt(0.07))), 900, 0.7, 'lp') * np.exp(-tt(0.07) / 0.03)
    x = at(n, 0.0, one) + at(n, 0.11, one, 0.85)
    return edges(x, 0.0005, 0.03)


def sfx_clear():
    """A stage cleared: the vibraphone up a D major ninth over a soft piano chord."""
    n = int(2.0 * FS)
    x = np.zeros(n)
    for i, m in enumerate((74, 78, 81, 85, 88)):
        x += at(n, i * 0.07, vibes(m, 1.6, 0.8), 0.7)
    for m in (62, 66, 69, 73):
        x += at(n, 0.0, epiano(m, 1.2, 0.5), 0.25)
    return edges(x, 0.001, 0.15)


def sfx_alert():
    """A guard hears something: two quick marimba notes rising, bent like a question."""
    n = int(0.45 * FS)
    x = at(n, 0.0, marimba(67, 0.3, 0.9)) + at(n, 0.09, marimba(70, 0.36, 1.0, bend=0.6))
    return edges(x, 0.001, 0.04)


def sfx_knock():
    """A fragile thing over: cans and boxes clattering down."""
    rng = np.random.default_rng(23)
    n = int(0.9 * FS)
    x = np.zeros(n)
    when = 0.0
    for k in range(6):
        tn = tt(0.25)
        m = np.zeros(len(tn))
        base = rng.uniform(520, 900)
        for r in (1.0, 2.32, 4.1, 6.3):
            m += np.sin(2 * math.pi * base * r * tn + rng.uniform(0, 6)) * np.exp(-tn / (0.07 / r ** 0.5))
        m += burst(rng, len(tn), 1800, 0.7, 0.01) * 0.8
        m += thud(tn, 160, 90, 0.01, 0.03) * 0.6
        put(x, int(when * FS), m, 0.9 * 0.72 ** k)
        when += rng.uniform(0.06, 0.15)
    return edges(x, 0.0005, 0.06)


def sfx_bell():
    """The pocket bell: a late-90s pager's beeps, three and three."""
    n = int(0.9 * FS)
    x = np.zeros(n)
    tb = tt(0.075)
    beep = filt(np.sign(np.sin(2 * math.pi * 2350 * tb)), 5000, 0.7, 'lp')
    beep = edges(beep, 0.002, 0.004)
    for k in range(6):
        put(x, int((k * 0.12 + (0.14 if k >= 3 else 0.0)) * FS), beep)
    return x


def sfx_retry():
    """START's restart: a short tape rewind."""
    rng = np.random.default_rng(24)
    t = tt(0.28)
    f = 2400 * np.exp(-t / 0.12) + 500 + 120 * np.sin(2 * math.pi * 40 * t)
    x = filt(saw(f), 1800, 1.2, 'bp') + 0.3 * filt(noise(rng, len(t)), 3000, 1.0, 'bp')
    return edges(x * np.sin(math.pi * t / 0.28) ** 0.5, 0.002, 0.03)


def sfx_card():
    """A keycard picked up: the plastic's snap and a small confirming pip, a fourth up."""
    rng = np.random.default_rng(25)
    n = int(0.4 * FS)
    t = np.arange(n) / FS
    snap = burst(rng, n, 2400, 1.0, 0.006) * 0.8 + burst(rng, n, 5200, 1.2, 0.002) * 0.4
    pip = np.zeros(n)
    for i, f in enumerate((1568.0, 2093.0)):
        tp = tt(0.06)
        put(pip, int((0.07 + i * 0.075) * FS), edges(np.sin(2 * math.pi * f * tp) * np.exp(-tp / 0.04), 0.002, 0.01))
    return edges(snap + 0.45 * pip, 0.0003, 0.04)


def sfx_unlock():
    """A staff door unlocked by its card: the reader's beep, the magnetic lock letting go."""
    rng = np.random.default_rng(26)
    n = int(0.7 * FS)
    t = np.arange(n) / FS
    tb = tt(0.12)
    beep = edges(filt(np.sign(np.sin(2 * math.pi * 1760 * tb)), 4000, 0.7, 'lp'), 0.002, 0.01) * 0.35
    clunk = (np.sin(2 * math.pi * 180 * t) + 0.5 * np.sin(2 * math.pi * 510 * t)) * np.exp(-t / 0.05) * np.clip(t / 0.001, 0, 1)
    x = at(n, 0.0, beep) + at(n, 0.16, clunk, 0.9) + at(n, 0.16, burst(rng, n, 3000, 0.9, 0.004), 0.5)
    x += at(n, 0.3, burst(rng, n, 1500, 0.8, 0.02), 0.25)          # the door eased off its seal
    return edges(x, 0.0005, 0.06)


# ---- loops: n samples at FS, periodic

def loop_train_run(n):
    """A train moving at full speed (the cart sets its pitch by the speed): the motors' whine,
    the wheels' roar, the body's rumble, and a bogie pair over a rail joint twice a loop."""
    rng = np.random.default_rng(31)
    t = np.arange(n) / FS
    x = cfilt(cfilt(noise(rng, n), 170, 0.7, 'lp'), 30, 0.7, 'hp') * 1.4
    x += cfilt(noise(rng, n), 900, 0.6, 'bp') * 0.35
    for f, g in ((520, 0.10), (1040, 0.05), (1560, 0.02)):
        x += g * np.sin(2 * math.pi * loop_hz(f, n) * t)
    joint = np.zeros(n)
    tn = tt(0.12)
    knock = thud(tn, 120, 60, 0.01, 0.05) + burst(rng, len(tn), 1100, 0.8, 0.012) * 0.6
    for start in (0.25, 0.37, 1.25, 1.37):
        put_circ(joint, int(start * FS * n / (2.0 * FS)), knock, 0.9)
    return x + joint


def loop_train_idle(n):
    """A stopped train: its air conditioning's fans and its converter's whine."""
    rng = np.random.default_rng(32)
    t = np.arange(n) / FS
    x = cfilt(cfilt(noise(rng, n), 600, 0.6, 'lp'), 80, 0.7, 'hp')
    x += 0.15 * np.sin(2 * math.pi * loop_hz(100, n) * t) + 0.04 * np.sin(2 * math.pi * loop_hz(1220, n) * t)
    return x


def hum(n, base, harm, buzz=0.0):
    t = np.arange(n) / FS
    x = np.zeros(n)
    for k, g in enumerate(harm, 1):
        x += g * np.sin(2 * math.pi * loop_hz(base * k, n) * t)
    if buzz:
        x = x + buzz * np.sign(x) * x ** 2
    return x


def slow(n, cycles, depth, ph=0.0):
    t = np.arange(n) / n
    return 1 - depth * (0.5 + 0.5 * np.sin(2 * math.pi * cycles * t + ph))


def amb_platform(n):
    rng = np.random.default_rng(41)
    air = cfilt(cfilt(noise(rng, n), 350, 0.6, 'lp'), 40, 0.7, 'hp') * 0.5
    wind = cfilt(noise(rng, n), 70, 0.7, 'lp') * 1.2 * slow(n, 2, 0.6)
    tubes = hum(n, 100, (1.0, 0.5, 0.3, 0.15), 0.6) * 0.03
    return air + wind + tubes


def amb_gates(n):
    rng = np.random.default_rng(42)
    t = np.arange(n) / FS
    air = cfilt(cfilt(noise(rng, n), 480, 0.6, 'lp'), 50, 0.7, 'hp') * 0.35
    standby = 0.012 * np.sin(2 * math.pi * loop_hz(760, n) * t) + 0.008 * np.sin(2 * math.pi * loop_hz(1140, n) * t)
    standby *= slow(n, 3, 0.4)
    whine = 0.003 * np.sin(2 * math.pi * loop_hz(5400, n) * t)
    return air + hum(n, 100, (1.0, 0.4, 0.2)) * 0.02 + standby + whine


def amb_passage(n):
    rng = np.random.default_rng(43)
    air = cfilt(cfilt(noise(rng, n), 260, 0.6, 'lp'), 35, 0.7, 'hp') * 0.55 * slow(n, 1, 0.35)
    buzz = cfilt(hum(n, 100, (1.0, 0.7, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1), 1.5), 2000, 0.7, 'lp') * 0.035
    flick = np.zeros(n)                           # one tube near its end, ticking now and then
    for c in (0.8, 3.1, 6.7):
        for k in range(rng.integers(3, 7)):
            tn = tt(0.02)
            put_circ(flick, int((c + k * rng.uniform(0.03, 0.09)) * FS), burst(rng, len(tn), 2400, 1.2, 0.003), rng.uniform(0.02, 0.05))
    return air + buzz + flick


def amb_lobby(n):
    rng = np.random.default_rng(44)
    hvac = cfilt(cfilt(noise(rng, n), 1100, 0.5, 'lp'), 60, 0.7, 'hp') * 0.32
    city = cfilt(noise(rng, n), 110, 0.7, 'lp') * 0.8 * slow(n, 3, 0.5, 1.0)
    return hvac + city + hum(n, 50, (0.0, 1.0, 0.3)) * 0.01


def amb_aquarium(n):
    rng = np.random.default_rng(45)
    t = np.arange(n) / FS
    pump = hum(n, 47, (1.0, 0.6, 0.35, 0.2, 0.1)) * 0.05 * (1 + 0.1 * np.sin(2 * math.pi * loop_hz(1.6, n) * t))
    water = cfilt(noise(rng, n), 2200, 0.8, 'bp') * 0.08
    water *= 1 + 0.6 * cfilt(rng.uniform(-1, 1, n), 9, 0.7, 'lp') * 8
    bubbles = np.zeros(n)
    k = int(n / FS * 14)
    for _ in range(k):
        d = rng.uniform(0.012, 0.035)
        tb = tt(d)
        f0 = rng.uniform(450, 1300)
        b = np.sin(2 * math.pi * np.cumsum(f0 * (1 + 0.8 * tb / d)) / FS) * np.exp(-tb / (d / 3))
        put_circ(bubbles, rng.integers(0, n), b, rng.uniform(0.01, 0.04))
    low = cfilt(noise(rng, n), 150, 0.7, 'lp') * 0.4
    return pump + water + bubbles + low


def amb_cinema(n):
    """The auditorium: dead, soft air, the projector clattering behind the wall."""
    rng = np.random.default_rng(46)
    air = cfilt(cfilt(noise(rng, n), 300, 0.6, 'lp'), 40, 0.7, 'hp') * 0.35
    gate = np.zeros(n)
    k = max(1, round(n / FS * 24))
    for i in range(k):
        tn = tt(0.02)
        put_circ(gate, int(i * n / k), burst(rng, len(tn), 900, 1.0, 0.004) + thud(tn, 220, 140, 0.004, 0.006) * 0.5,
                 0.5 * rng.uniform(0.8, 1.0))
    gate = cfilt(gate, 500, 0.7, 'lp') * 0.5
    return air + gate + hum(n, 100, (1.0, 0.3)) * 0.008


def amb_booth(n):
    """The projection booth: the projector's intermittent at 24 frames a second, its motor, the
    lamp house's fan."""
    rng = np.random.default_rng(47)
    gate = np.zeros(n)
    k = max(1, round(n / FS * 24))
    for i in range(k):
        tn = tt(0.025)
        c = burst(rng, len(tn), 1800, 1.2, 0.003) + thud(tn, 320, 200, 0.003, 0.006) * 0.6
        put_circ(gate, int(i * n / k), c, rng.uniform(0.75, 1.0))
    fan = cfilt(cfilt(noise(rng, n), 1500, 0.5, 'lp'), 120, 0.7, 'hp') * 0.25
    motor = hum(n, 50, (0.6, 1.0, 0.4, 0.3, 0.15), 0.5) * 0.06
    return gate * 0.6 + fan + motor


def amb_corridor(n):
    """The staff corridor: the tubes, a duct's rush, a vending machine's compressor."""
    rng = np.random.default_rng(48)
    duct = cfilt(cfilt(noise(rng, n), 700, 0.5, 'lp'), 70, 0.7, 'hp') * 0.3 * slow(n, 1, 0.25)
    tubes = cfilt(hum(n, 100, (1.0, 0.6, 0.4, 0.25, 0.15), 1.0), 1500, 0.7, 'lp') * 0.025
    comp = hum(n, 49, (1.0, 0.5, 0.2)) * 0.04 * slow(n, 4, 0.2)
    return duct + tubes + comp


def amb_shopfloor(n):
    """The shop floor after closing: a large quiet, the air handling far off."""
    rng = np.random.default_rng(49)
    air = cfilt(cfilt(noise(rng, n), 450, 0.5, 'lp'), 45, 0.7, 'hp') * 0.3 * slow(n, 2, 0.3, 2.0)
    low = cfilt(noise(rng, n), 90, 0.7, 'lp') * 0.5
    return air + low + hum(n, 100, (1.0, 0.3)) * 0.006


def amb_foodhall(n):
    """The food hall: the cold cases' compressors (two, beating) and their fans."""
    rng = np.random.default_rng(50)
    comp = hum(n, 50, (0.5, 1.0, 0.5, 0.25), 0.4) * 0.05 + hum(n, 50.6, (0.4, 0.8, 0.3)) * 0.035
    fans = cfilt(cfilt(noise(rng, n), 1200, 0.6, 'lp'), 150, 0.7, 'hp') * 0.22
    t = np.arange(n) / FS
    buzz = 0.006 * np.sin(2 * math.pi * loop_hz(1250, n) * t) * slow(n, 3, 0.5)
    return comp + fans + buzz


# name, render, peak level in the game (dBFS), reverb send
ONE_SHOTS = [
    ('step_walk', sfx_step_walk, -22, 1),
    ('step_run', sfx_step_run, -15, 1),
    ('caught', sfx_caught, -8, 1),
    ('hide_in', sfx_hide_in, -18, 1),
    ('hide_out', sfx_hide_out, -19, 1),
    ('train_horn', sfx_train_horn, -15, 1),
    ('train_brake', sfx_train_brake, -19, 1),
    ('doors_open', sfx_doors_open, -16, 1),
    ('door_chime', sfx_door_chime, -16, 1),
    ('doors_close', sfx_doors_close, -14, 1),
    ('door_open', sfx_door_open, -15, 1),
    ('door_shut', sfx_door_shut, -15, 1),
    ('transition', sfx_transition, -17, 1),
    ('menu_move', sfx_menu_move, -21, 0),
    ('menu_ok', sfx_menu_ok, -14, 1),
    ('menu_back', sfx_menu_back, -17, 1),
    ('menu_deny', sfx_menu_deny, -17, 0),
    ('clear', sfx_clear, -11, 1),
    ('alert', sfx_alert, -15, 1),
    ('knock', sfx_knock, -12, 1),
    ('bell', sfx_bell, -15, 1),
    ('retry', sfx_retry, -20, 0),
    # stage 2
    ('card', sfx_card, -15, 1),
    ('unlock', sfx_unlock, -14, 1),
]

# the loops (started with their loop at 0, stopped by the cart): name, render (n samples at FS,
# periodic), seconds, peak in the game (dBFS), reverb send
LOOPS = [
    ('train_run', loop_train_run, 2.0, -12, 1),
    ('train_idle', loop_train_idle, 1.5, -27, 1),
    ('amb_platform', amb_platform, 9.0, -24, 0),
    ('amb_gates', amb_gates, 9.0, -27, 0),
    ('amb_passage', amb_passage, 9.0, -24, 0),
    ('amb_lobby', amb_lobby, 9.0, -25, 0),
    ('amb_aquarium', amb_aquarium, 9.0, -24, 0),
    ('amb_cinema', amb_cinema, 9.0, -26, 0),
    ('amb_booth', amb_booth, 9.0, -22, 0),
    ('amb_corridor', amb_corridor, 9.0, -25, 0),
    ('amb_shopfloor', amb_shopfloor, 9.0, -28, 0),
    ('amb_foodhall', amb_foodhall, 9.0, -25, 0),
]

# the rooms' ambiences (dr_audio.akr's AMB_*): name, its loop, the reverb's decay there (x n / 256)
ROOMS = [
    ('none', None, 150),
    ('platform', 'amb_platform', 215),
    ('gates', 'amb_gates', 170),
    ('passage', 'amb_passage', 235),
    ('lobby', 'amb_lobby', 200),
    ('aquarium', 'amb_aquarium', 150),
    ('cinema', 'amb_cinema', 140),
    ('booth', 'amb_booth', 120),
    ('corridor', 'amb_corridor', 175),
    ('shopfloor', 'amb_shopfloor', 205),
    ('foodhall', 'amb_foodhall', 180),
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


def seam_text(d, cnt, loop):
    """A loop's wrap (decoded as the console plays it) against its typical step."""
    jump = abs(int(d[cnt]) - int(d[cnt - 1]))
    steps = np.abs(np.diff(d[loop:cnt]))
    return ', a loop (the wrap: %d, %.2f x the 99th percentile step; later passes differ by %d)' % (
        jump, jump / max(1.0, float(np.percentile(steps, 99))),
        int(np.abs(d[cnt:2 * cnt - loop] - d[2 * cnt - loop:3 * cnt - 2 * loop]).max()))


def render_sfx():
    """Every sound: [(name, int data at SR, volume, reverb, loop)]. A loop starts with a lead-in
    of LEAD_IN samples (its own end) and loops from there."""
    out = []
    for name, fn, level, rev in ONE_SHOTS:
        x = down(hp_dc(fn(), 28.0), False)
        x = np.concatenate([x, np.zeros(-len(x) % BLK)])
        out.append((name, x, level, rev, False))
    for name, fn, secs, level, rev in LOOPS:
        n = int(round(secs * SR / BLK)) * BLK
        x = down(mid3(hp_dc(tile3(fn(n * OS)), 28.0)), True)
        x = np.concatenate([x[-LEAD_IN:], x])       # the lead-in: the loop is entered as it wraps
        out.append((name, x, level, rev, True))
    sfx = []
    for name, x, level, rev, loop in out:
        x = x / np.abs(x).max() * STEM_PEAK
        vol = min(255, int(round(256 * 10 ** ((level + SFX_TRIM) / 20) / STEM_PEAK)))
        sfx.append((name, np.round(x * 32767).astype(np.int64), vol, rev, loop))
    return sfx


def build(preview):
    print('rendering the track...')
    stems = render_song()
    intro = INTRO_BARS * 4 * BEAT
    n = len(stems[0])
    assert n % BLK == 0 and intro % BLK == 0 and n == intro + BARS * 4 * BEAT, (n, intro)
    st = mix_levels(stems)
    print('rendering the sounds...')
    sfx = render_sfx()

    print('encoding...')
    jobs = [(data, intro) for data, vol in st] + [(data, LEAD_IN if loop else None) for _, data, _, _, loop in sfx]
    with ProcessPoolExecutor() as ex:
        enc = list(ex.map(_encode, jobs))

    os.makedirs(AUD, exist_ok=True)
    mbank = bytearray()
    stem_rows = []
    decoded = []
    stem_names = ('beat', 'airL', 'airR')
    for si, (data, vol) in enumerate(st):
        blob = enc[si]
        vl, vr = (vol, vol) if si == 0 else ((vol, 0) if si == 1 else (0, vol))
        stem_rows.append((si, len(mbank), n, intro, vl, vr, 1 if si else 0))
        mbank += blob
        decoded.append((blob, mei_adpcm.decode(blob, n).astype(np.int64), data))
    sbank = bytearray()
    sfx_rows = []
    sfx_dec = {}
    for k, (name, data, vol, rev, loop) in enumerate(sfx):
        blob = enc[3 + k]
        sfx_rows.append((name, len(sbank), len(data), vol, rev, LEAD_IN if loop else -1))
        sbank += blob
        dec = mei_adpcm.decode(blob, len(data)).astype(np.int64)
        if loop:            # three passes, each later one decoded with the history the last left
            passes = [dec]
            for _ in range(2):
                passes.append(mei_adpcm.decode(blob[LEAD_IN // BLK * 16:], len(data) - LEAD_IN,
                                               int(passes[-1][-1]), int(passes[-1][-2])).astype(np.int64))
            dec = np.concatenate(passes)
        sfx_dec[name] = (dec, vol)
    with open(os.path.join(AUD, 'music.adp'), 'wb') as f:
        f.write(mbank)
    with open(os.path.join(AUD, 'sfx.adp'), 'wb') as f:
        f.write(sbank)

    # ---- au_data.akr
    idx = {r[0]: i for i, r in enumerate(sfx_rows)}
    o = []
    o.append('// Generated by tools/gen_afterhours_audio.py - do not edit.\n')
    o.append('// After Hours\' music stems, sound effects and ambiences (audio/music.adp, audio/sfx.adp),\n')
    o.append('// read by dr_audio.akr.\n\n')
    o.append('embed AU_MUSIC: u8 = "audio/music.adp"\n')
    o.append('embed AU_SFX: u8 = "audio/sfx.adp"\n\n')
    o.append('const AU_REVERB = %d                 // the console reverb preset (hall)\n' % REVERB)
    o.append('const AU_WET = %d                   // its wet level, both sides\n\n' % REV_WET)
    o.append('// "Shutters Down": a %.1f s intro, then a %.1f s loop. Per stem (beat: mono, dry; air left;\n'
             % (intro / SR, (n - intro) / SR))
    o.append('// air right, to the reverb): channel, byte offset in AU_MUSIC, samples, loop start, left\n')
    o.append('// volume, right volume, reverb send\n')
    o.append('const MU_STEMS = 3\n')
    vals = []
    for row in stem_rows:
        vals += list(row)
    o.append(akr_array('MU_STEM', 's32', vals, 7))
    o.append('const MU_BEAT_SAMPLES = %d       // a beat (for anyone who wants the tempo)\n\n' % BEAT)
    o.append('// The sounds: an index into SFX for each. The loops (%s) start with a lead-in.\n'
             % ', '.join(r[0] for r in sfx_rows if r[5] >= 0))
    for i, row in enumerate(sfx_rows):
        o.append('const SFX_%s = %d\n' % (row[0].upper(), i))
    o.append('const SFX_COUNT = %d\n' % len(sfx_rows))
    o.append('// per sound: byte offset in AU_SFX, samples, volume, reverb send, loop start (-1: a one-shot)\n')
    vals = []
    for row in sfx_rows:
        vals += list(row[1:6])
    o.append(akr_array('SFX', 's32', vals, 5))
    o.append('// their names (for the tests\' logs)\n')
    o.append(akr_array('SFX_NAMES', '*u8', ['"%s"' % r[0] for r in sfx_rows], 6))
    o.append('\n// The rooms\' ambiences, for au_room(): their loop (SFX_*, -1 none) and the reverb\'s decay there\n')
    for i, (name, loop, dec) in enumerate(ROOMS):
        o.append('const AMB_%s = %d\n' % (name.upper(), i))
    o.append('const AMB_COUNT = %d\n' % len(ROOMS))
    o.append(akr_array('AMB_LOOP', 's32', [idx[l] if l else -1 for _, l, _ in ROOMS], 6))
    o.append(akr_array('AMB_DECAY', 's32', [d for _, _, d in ROOMS], 6))
    with open(os.path.join(CART, 'au_data.akr'), 'w') as f:
        f.write(''.join(o))

    # ---- the report: sizes, levels, the loops' seams
    print('music.adp %d bytes, sfx.adp %d bytes' % (len(mbank), len(sbank)))
    for r, (blob, d, src), nm in zip(stem_rows, decoded, stem_names):
        err = d - src
        snr = 10 * math.log10((src ** 2).mean() / max(1e-9, (err ** 2).mean()))
        diff, ratio = seam_check(blob, r[2], r[3], d)
        print('  %-4s ch %d  %8d samples (%.2f s), loop at %d, vol %3d/%3d, peak %.1f dB, ADPCM SNR %.1f dB, '
              'second pass differs by %d, wrap step %.2f x the 99th percentile'
              % (nm, r[0], r[2], r[2] / SR, r[3], r[4], r[5], db(np.abs(d).max() / 32768), snr, diff, ratio))
    (_, b, _), (_, al, _), (_, ar, _) = decoded
    vols = [v for _, v in st]
    L = (b * vols[0] >> 8) + (al * vols[1] >> 8)
    R = (b * vols[0] >> 8) + (ar * vols[2] >> 8)
    lp = np.abs(np.concatenate([L, R])).max()
    rms = math.sqrt(((L.astype(float) ** 2 + R.astype(float) ** 2) / 2).mean())
    print('  track mix: peak %.1f dBFS, RMS %.1f dBFS' % (db(lp / 32768), db(rms / 32768)))
    for name, off, cnt, vol, rev, loop in sfx_rows:
        d, v = sfx_dec[name]
        g = d * v >> 8
        print('  %-13s %6d samples (%.2f s) %6d bytes, vol %3d, peak %.1f dBFS, RMS %.1f dBFS%s%s'
              % (name, cnt, cnt / SR, (cnt + BLK - 1) // BLK * 16, vol, db(np.abs(g).max() / 32768),
                 db(math.sqrt((g.astype(float) ** 2).mean()) / 32768), ', to the reverb' if rev else '',
                 seam_text(d, cnt, loop) if loop >= 0 else ''))

    # the balance: the track's start with the platform's hum, steps, a train and a catch over it
    nn = int(25 * SR)
    two = np.concatenate([L, L[intro:]])[:nn], np.concatenate([R, R[intro:]])[:nn]
    VL, VR = two[0].copy(), two[1].copy()

    def mixin(name, when, gain=1.0, pitch=1.0, length=None):
        d, v = sfx_dec[name]
        if pitch != 1.0:
            d = d[np.minimum((np.arange(int(len(d) / pitch))) * pitch, len(d) - 1).astype(int)]
        if length is not None:          # a loop: its first pass, then its later ones
            cnt = (len(d) + 2 * LEAD_IN) // 3
            d = np.concatenate([d[:cnt], np.resize(d[cnt:2 * cnt - LEAD_IN], max(0, length - cnt))])[:length]
        p = int(when * SR)
        k = min(len(d), nn - p)
        g = int(v * gain)
        VL[p:p + k] += d[:k] * g >> 8
        VR[p:p + k] += d[:k] * g >> 8
    mixin('amb_platform', 0.0, length=nn)
    for k in range(20):
        mixin('step_walk', 2.0 + k * 0.33, pitch=[1.0, 0.95, 1.04, 0.98][k % 4])
    for k in range(12):
        mixin('step_run', 9.0 + k * 0.27, pitch=[1.0, 0.95, 1.04, 0.98][k % 4])
    mixin('train_horn', 5.0)
    mixin('train_run', 5.2, 0.9, 0.9, int(2.6 * SR))
    mixin('train_brake', 6.4)
    mixin('doors_open', 8.0)
    mixin('train_idle', 8.0, 1.0, 1.0, int(8 * SR))
    mixin('caught', 12.4)
    mixin('door_chime', 14.5)
    mixin('doors_close', 16.0)
    mixin('train_run', 16.2, 0.8, 0.7, int(3 * SR))
    mixin('hide_in', 18.0)
    mixin('hide_out', 19.5)
    mixin('door_open', 21.0)
    mixin('transition', 21.6)
    mixin('door_shut', 23.4)
    both = np.concatenate([VL, VR])
    print('  play mix: peak %.1f dBFS, %d of %d samples clipped'
          % (db(np.abs(both).max() / 32768), int((np.abs(both) > 32767).sum()), len(both)))

    if preview:
        os.makedirs(preview, exist_ok=True)
        for si in range(3):
            write_wav(os.path.join(preview, 'track_%s.wav' % stem_names[si]), [decoded[si][1]])
        write_wav(os.path.join(preview, 'track.wav'),
                  [np.concatenate([L, L[intro:]]), np.concatenate([R, R[intro:]])])
        for name, (d, v) in sfx_dec.items():
            write_wav(os.path.join(preview, '%s.wav' % name), [d * v >> 8])
        write_wav(os.path.join(preview, 'play.wav'), [VL, VR])
        print('previews in', preview)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--preview', metavar='DIR', help='also write WAVs to listen to')
    a = ap.parse_args()
    build(a.preview)


if __name__ == '__main__':
    main()
