#!/usr/bin/env python3
"""Fair Skies' music and sounds: "Fair Skies Theme", a smooth-jazz lounge piece in F major for the
weather channel, and the interface sounds.

The band: a Rhodes-style electric piano comping lush 9th chords, a fretless bass, a soft string
pad, a vibraphone carrying the tune (its motor is the engine's tremolo), and brushes and a
cross-stick: kick, rim, closed hat, shaker and ride. 90 bpm, straight sixteenths, in four
8-bar sections (A A B A); every section of every track has a few variants and the engine picks
one at random each time round (never the same twice running), so the 1.4-minute form rarely
repeats exactly. The melody uses the chord tones and the F major scale; the interface sounds use
only F, G, A, C and D, which sit well over every chord.

Samples follow tools/gen_shell_music.py (whose helpers this uses): pitched notes are rendered at
the exact pitch they play (or an octave below, played at pitch 2.0), struck notes decay into a
short loop of whole harmonics and the engine continues the decay; drums are one-shots.

Writes carts/weather/audio/music.adp, carts/weather/audio/sfx_*.adp and
carts/weather/mu_data.akr (the tables carts/weather/music.akr reads).
    python3 tools/gen_weather_audio.py [--preview DIR]
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm
from gen_shell_music import (SR, FRAME, LEAD, mtof, fit_loop, struck, looped, raised, lp_noise,
                             Inst, Score, plan_samples, to_int16)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CART = os.path.join(ROOT, 'carts', 'weather')
AUD = os.path.join(CART, 'audio')

F_MAJOR = {5, 7, 9, 10, 0, 2, 4}


# ================================================================== instruments

def rhodes_render(m, shift):
    """Electric piano: a strong fundamental and second harmonic that persist, a bell-like tine
    partial and a soft 'bark' that fade before the loop."""
    f = mtof(m)
    bright = max(0.0, min(1.0, (m - 48) / 30))
    parts = [(1, 1.0, 1.6, True), (2, 0.45, 0.9, True), (3, 0.18, 0.5, True), (4, 0.09, 0.4, True),
             (5, 0.04, 0.25, True), (7.02, 0.16 + 0.08 * bright, 0.10, False), (14.1, 0.07, 0.04, False),
             (2.01, 0.14, 0.25, False)]
    return struck(f, parts, 0.55, 1.6, 9000 / 2 ** shift, noise=(0.015, 0.006, 3000), seed=m + 7, att_ms=2.0,
                  loop_s=(0.06, 0.32))


def vibes_render(m, shift):
    """Vibraphone bar: fundamental, the 4th-harmonic overtone (tuned bars ring at 4x), a soft
    10x partial and the mallet."""
    f = mtof(m)
    parts = [(1, 1.0, 2.4, True), (4, 0.30, 0.55, True), (10.0, 0.07, 0.08, False), (2.76, 0.04, 0.1, False)]
    return struck(f, parts, 0.42, 2.4, 11000 / 2 ** shift, noise=(0.03, 0.004, 5000), seed=m + 31, att_ms=1.2,
                  loop_s=(0.05, 0.3))


def bass_render(m, shift):
    """Fretless bass: round, a slow-ish attack, the upper harmonics fading first."""
    f = mtof(m)
    parts = [(1, 1.0, 1.4, True), (2, 0.55, 0.9, True), (3, 0.22, 0.5, True), (4, 0.1, 0.3, True),
             (5, 0.05, 0.2, False), (6, 0.03, 0.15, False)]
    return struck(f, parts, 0.40, 1.4, 2400, seed=m + 3, att_ms=14.0, loop_s=(0.1, 0.9))


def chorus_soft(k, rng):
    if k == 1:
        return [(0, 1.0)]
    d = rng.choice([-1, 1])
    return [(0, 1.0), (d, 0.45), (-d, 0.3)]


def pad_render(m, shift):
    harm = lambda k, f: (1.0 / k ** 1.25) / math.sqrt(1 + (k * f / 1800.0) ** 4)
    return looped(mtof(m), 0.5, harm, 7000, chorus_soft, seed=m + 71)


# ---- drums (one-shots)

def kick():
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    f = 46 + 70 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.13)
    x += 0.25 * lp_noise(n, 1500, 5) * np.exp(-t / 0.004)
    return x * raised(n, 20)


def rim():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = (0.6 * np.sin(2 * np.pi * 520 * t) * np.exp(-t / 0.018) +
         0.35 * np.sin(2 * np.pi * 1690 * t) * np.exp(-t / 0.012) +
         0.25 * lp_noise(n, 4000, 9) * np.exp(-t / 0.008))
    return x * raised(n, 6)


def hat():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    w = np.random.default_rng(13).standard_normal(n)
    w = w - np.concatenate([[0], w[:-1]])               # a first difference: bright
    x = w * np.exp(-t / 0.018)
    return x * raised(n, 4) * 0.5


def shaker():
    n = int(0.11 * SR)
    t = np.arange(n) / SR
    w = np.random.default_rng(17).standard_normal(n)
    w = w - np.concatenate([[0], w[:-1]])
    env = np.minimum(t / 0.025, 1.0) * np.exp(-np.maximum(0, t - 0.025) / 0.025)
    return w * env * 0.4


def ride():
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(21)
    x = np.zeros(n)
    for fr, a, tau in [(3120, 0.3, 0.7), (4470, 0.22, 0.55), (5230, 0.18, 0.4), (6900, 0.12, 0.3),
                       (2410, 0.15, 0.6), (8010, 0.08, 0.25)]:
        x += a * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    w = rng.standard_normal(n)
    x += 0.12 * (w - np.concatenate([[0], w[:-1]])) * np.exp(-t / 0.05)
    return x * raised(n, 8) * 0.6


DRUMS = {36: kick, 37: rim, 42: hat, 70: shaker, 51: ride}


def drum_render(m, shift):
    x = DRUMS[m]()
    return x, len(x)


class OneShot(Inst):
    """mode 3: played once without a loop (the drums)."""

    def params(self):
        p = super().params()
        p[0] = 3
        return p


# ================================================================== the score

BEAT = 40                   # ticks; the engine moves one tick a frame: 90 bpm
BAR = 4 * BEAT
SEC = 8 * BAR

# Rhodes voicings and bass roots, a chord or two per bar
A_CHORDS = [
    [('Fmaj9', 41, [57, 60, 64, 67])],
    [('Em7', 40, [55, 59, 62, 64]), ('A7', 33, [55, 61, 64, 69])],
    [('Dm9', 38, [53, 57, 60, 64])],
    [('Cm9', 36, [51, 55, 58, 62]), ('F13', 41, [51, 57, 62, 63])],
    [('Bbmaj9', 34, [57, 60, 62, 65])],
    [('Am7', 33, [55, 60, 64, 67]), ('D9', 38, [54, 60, 64, 66])],
    [('Gm9', 31, [58, 62, 65, 69])],
    [('C9sus', 36, [58, 62, 65, 67]), ('C7', 36, [58, 64, 67, 70])],
]
B_CHORDS = [
    [('Bbmaj7', 34, [57, 62, 65, 69])],
    [('Bbm6', 34, [56, 61, 65, 67]), ('Eb9', 39, [55, 61, 65, 67])],
    [('Am7', 33, [55, 60, 64, 67])],
    [('Abmaj7', 32, [55, 60, 63, 67])],
    [('Gm9', 31, [58, 62, 65, 69])],
    [('Am7', 33, [55, 60, 64, 67]), ('D7', 38, [54, 60, 63, 66])],
    [('Gm9', 31, [58, 62, 65, 69]), ('Gm9/C', 36, [58, 62, 65, 69])],
    [('C9sus', 36, [58, 62, 65, 67])],
]

# melodies: (beat in the bar, note, beats)
A_TUNE = [
    [(1.0, 69, 0.5), (1.5, 72, 0.5), (2.0, 76, 0.5), (2.5, 79, 1.5)],
    [(0.5, 74, 0.5), (1.0, 76, 1.0), (2.0, 73, 0.5), (2.5, 76, 0.5), (3.0, 79, 1.0)],
    [(0.0, 77, 2.0), (2.5, 76, 0.5), (3.0, 74, 0.5), (3.5, 72, 0.5)],
    [(0.0, 70, 1.5), (1.5, 74, 0.5), (2.0, 75, 1.0), (3.0, 74, 1.0)],
    [(0.0, 69, 1.0), (1.0, 72, 0.5), (1.5, 74, 0.5), (2.0, 77, 1.5), (3.5, 76, 0.5)],
    [(0.0, 76, 1.0), (1.0, 72, 1.0), (2.0, 78, 1.0), (3.0, 76, 1.0)],
    [(0.0, 74, 0.5), (0.5, 77, 0.5), (1.0, 81, 2.0), (3.0, 79, 0.5), (3.5, 77, 0.5)],
    [(0.0, 74, 1.0), (1.0, 72, 1.0), (2.0, 76, 2.0)],
]
B_TUNE = [
    [(0.0, 81, 2.0), (2.0, 77, 1.0), (3.0, 74, 1.0)],
    [(0.0, 73, 2.0), (2.0, 77, 1.0), (3.0, 79, 1.0)],
    [(0.0, 76, 2.5), (2.5, 72, 0.5), (3.0, 74, 0.5), (3.5, 76, 0.5)],
    [(0.0, 75, 2.0), (2.0, 79, 2.0)],
    [(0.0, 81, 1.0), (1.0, 77, 1.0), (2.0, 74, 2.0)],
    [(0.0, 76, 1.0), (1.0, 79, 1.0), (2.0, 84, 2.0)],
    [(0.0, 81, 3.0), (3.0, 77, 1.0)],
    [(0.0, 79, 2.0), (2.0, 74, 1.0), (3.0, 72, 1.0)],
]

# chord tones (pitch classes) of every chord, for the harmony a third below the tune
CHORD_PC = {
    'Fmaj9': {5, 9, 0, 4, 7}, 'Em7': {4, 7, 11, 2}, 'A7': {9, 1, 4, 7}, 'Dm9': {2, 5, 9, 0, 4},
    'Cm9': {0, 3, 7, 10, 2}, 'F13': {5, 9, 0, 3, 2}, 'Bbmaj9': {10, 2, 5, 9, 0}, 'Am7': {9, 0, 4, 7},
    'D9': {2, 6, 9, 0, 4}, 'Gm9': {7, 10, 2, 5, 9}, 'C9sus': {0, 5, 7, 10, 2}, 'C7': {0, 4, 7, 10},
    'Bbmaj7': {10, 2, 5, 9}, 'Bbm6': {10, 1, 5, 7}, 'Eb9': {3, 7, 10, 1, 5}, 'Abmaj7': {8, 0, 3, 7},
    'D7': {2, 6, 9, 0}, 'Gm9/C': {7, 10, 2, 5, 9, 0},
}

EP, VIB, BASS, PAD, DRUM = 0, 1, 2, 3, 4
KICK, RIM, HAT, SHAKER, RIDE = 36, 37, 42, 70, 51


def chord_at(chords, bar, beat):
    row = chords[bar]
    if len(row) == 1 or beat < 2:
        return row[0]
    return row[1]


def smooth():
    rng = np.random.default_rng(1998)
    insts = [
        Inst('rhodes', 1, rhodes_render, [], vol=92, tail_tau=1.6, release_s=0.35, trem=(0.16, 4.2)),
        Inst('vibes', 1, vibes_render, list(range(65, 77)), vol=104, tail_tau=2.2, release_s=0.6,
             trem=(0.32, 5.4)),
        Inst('bass', 1, bass_render, [], vol=102, tail_tau=1.3, release_s=0.12, reverb=False),
        Inst('pad', 2, pad_render, [], vol=46, attack_s=1.2, release_s=1.0, trem=(0.06, 0.2)),
        OneShot('drums', 3, drum_render, [], vol=104, reverb=True),
    ]

    def hum(t, amt=2):
        return max(0, min(SEC - 1, t + int(rng.integers(-amt, amt + 1))))

    # ---- the rhythm section: piano, bass and pad
    def comp(chords, variant, pad_on):
        s = Score(SEC)
        prev_root = None
        for bar in range(8):
            t0 = bar * BAR
            row = chords[bar]
            for ci, (name, root, voicing) in enumerate(row):
                cs = t0 + ci * 2 * BEAT
                span = BAR // len(row)
                # piano rhythms
                if variant == 0:          # on the beat, then a push on the and of 2
                    hits = [(0, 1.4), (1.5, 0.9)] if len(row) == 1 else [(0, 1.4)]
                elif variant == 1:        # long chords, a light restrike
                    hits = [(0, 2.8), (2.5, 1.2)] if len(row) == 1 else [(0, 1.8)]
                else:                     # syncopated
                    hits = [(0.5, 1.0), (2.0, 0.6), (3.5, 0.5)] if len(row) == 1 else [(0.5, 1.2)]
                for k, (b, d) in enumerate(hits):
                    t = cs + int(b * BEAT)
                    if t >= SEC or t >= cs + span:
                        continue
                    vel = 78 if k == 0 else 62
                    for j, note in enumerate(voicing):
                        s.add(hum(t + j * 2, 1), EP, note, vel - 4 * j + rng.integers(-5, 6), 40 + 15 * j, int(d * BEAT))
                # bass
                r = root
                if variant == 1:          # half notes
                    s.add(hum(cs), BASS, r, 104, 64, span - 6)
                    if len(row) == 1:
                        s.add(hum(cs + 2 * BEAT), BASS, r + 7 if r + 7 <= 45 else r - 5, 86, 64, 2 * BEAT - 6)
                else:
                    s.add(hum(cs), BASS, r, 108, 64, int(1.4 * BEAT))
                    if len(row) == 1:
                        fifth = r + 7 if r + 7 <= 45 else r - 5
                        s.add(hum(cs + int(1.5 * BEAT)), BASS, fifth, 80, 64, int(0.4 * BEAT))
                        s.add(hum(cs + 2 * BEAT), BASS, r + 12 if r + 12 <= 47 else r, 88, 64, int(0.9 * BEAT))
                    # a pickup into the next chord
                    nxt = chords[(bar + 1) % 8][0][1] if ci == len(row) - 1 else row[ci + 1][1]
                    app = nxt - 1 if rng.random() < 0.6 else nxt + 2
                    s.add(hum(cs + span - BEAT // 2), BASS, max(28, min(47, app)), 76, 64, int(0.4 * BEAT))
                prev_root = root
            # pad: the 3rd and 7th of the bar's first chord, high and soft
            if pad_on:
                name, root, voicing = row[0]
                tones = sorted(voicing)[1:3]
                for j, note in enumerate(tones):
                    n = note + 12
                    while n > 79:
                        n -= 12
                    s.add(t0 + 6 * j, PAD, n, 92 - 8 * j, 24 + 80 * j, BAR - 12)
        return s

    # ---- drums
    def groove(variant, fill, ride_on):
        s = Score(SEC)
        for bar in range(8):
            t0 = bar * BAR
            last = bar == 7 and fill
            # kick: 1 and the and of 2 (and 3 sometimes)
            s.add(hum(t0), DRUM, KICK, 100, 64)
            if variant != 2:
                s.add(hum(t0 + int(1.5 * BEAT)), DRUM, KICK, 70, 64)
            if variant == 1 and bar % 2 == 1:
                s.add(hum(t0 + 2 * BEAT), DRUM, KICK, 82, 64)
            # cross-stick on 2 and 4
            s.add(hum(t0 + BEAT), DRUM, RIM, 92, 70)
            if not last:
                s.add(hum(t0 + 3 * BEAT), DRUM, RIM, 96, 70)
            # hats or ride: eighths; the shaker: sixteenths, soft, off the beat
            for e in range(8):
                t = t0 + e * BEAT // 2
                if last and e >= 6:
                    continue
                if ride_on:
                    s.add(hum(t, 1), DRUM, RIDE, 76 if e % 2 else 92, 80)
                else:
                    s.add(hum(t, 1), DRUM, HAT, 68 if e % 2 else 84, 84)
            for k in range(16):
                if k % 2 == 1:
                    s.add(hum(t0 + k * BEAT // 4, 1), DRUM, SHAKER, 52 + 12 * (k % 4 == 3), 44)
            if last:     # a soft fill: rim and kick on the last beat
                for k, (b, d) in enumerate([(3.0, RIM), (3.25, RIM), (3.5, KICK), (3.75, RIM)]):
                    s.add(t0 + int(b * BEAT), DRUM, d, 70 + 8 * k, 64)
        return s

    # ---- melody
    def tune(lines, chords, style):
        s = Score(SEC)
        for bar, line in enumerate(lines):
            if style == 'sparse' and bar % 4 >= 2:
                continue
            for (b, note, d) in line:
                t = bar * BAR + int(b * BEAT)
                vel = 92 + rng.integers(-8, 9)
                pan = 64 + rng.integers(-14, 15)
                s.add(hum(t, 1), VIB, note, vel, pan, int(d * BEAT))
                if style == 'thirds':
                    name = chord_at(chords, bar, b)[0]
                    pcs = CHORD_PC[name]
                    for drop in (3, 4, 5, 2):
                        h = note - drop
                        if h % 12 in pcs:
                            s.add(hum(t, 1), VIB, h, vel - 22, 128 - pan, int(d * BEAT))
                            break
                if style == 'echo' and d >= 1.0:
                    te = t + int(0.75 * BEAT)
                    if te < SEC:
                        s.add(te, VIB, note, vel * 0.35, 128 - pan, int(0.5 * BEAT))
        return s

    def rest():
        return Score(SEC)

    a_comp = [comp(A_CHORDS, v, pad_on=(v != 2)) for v in range(3)]
    b_comp = [comp(B_CHORDS, v, pad_on=True) for v in range(3)]
    tracks = [
        {'slots': [a_comp, a_comp, b_comp, a_comp]},
        {'slots': [[groove(0, False, False), groove(1, False, False)],
                   [groove(0, True, False), groove(1, True, False), groove(2, True, False)],
                   [groove(2, False, True), groove(0, False, True)],
                   [groove(1, True, False), groove(0, True, False)]]},
        {'slots': [[tune(A_TUNE, A_CHORDS, 'plain'), tune(A_TUNE, A_CHORDS, 'sparse')],
                   [tune(A_TUNE, A_CHORDS, 'thirds'), tune(A_TUNE, A_CHORDS, 'echo'), rest()],
                   [tune(B_TUNE, B_CHORDS, 'plain'), tune(B_TUNE, B_CHORDS, 'thirds')],
                   [tune(A_TUNE, A_CHORDS, 'echo'), tune(A_TUNE, A_CHORDS, 'plain'), tune(A_TUNE, A_CHORDS, 'sparse')]]},
    ]
    return dict(insts=insts, tracks=tracks, reverb=3, wet=150, tempo=1.0)


# ================================================================== interface sounds

def chime(notes, gap, tau=0.6, amp=0.6, bright=0.25):
    """A soft vibraphone-like chime: notes `gap` seconds apart."""
    n = int((gap * (len(notes) - 1) + tau * 3) * SR)
    x = np.zeros(n)
    for i, m in enumerate(notes):
        f = mtof(m)
        s0 = int(i * gap * SR)
        t = np.arange(n - s0) / SR
        y = np.sin(2 * np.pi * f * t) * np.exp(-t / tau) + bright * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t / (tau / 4))
        y *= raised(len(y), 30)
        x[s0:] += y * amp * (0.85 ** i)
    return x


def whoosh(dur, amp):
    n = int(dur * SR)
    t = np.arange(n) / SR
    w = lp_noise(n, 2500, 41)
    env = np.sin(np.pi * np.minimum(t / dur, 1.0)) ** 2
    return w * env * amp


def click(amp=0.5, f=2200):
    n = int(0.035 * SR)
    t = np.arange(n) / SR
    return amp * (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.006) + 0.4 * lp_noise(n, 5000, 3) * np.exp(-t / 0.003))


def beep(f, dur=0.07, amp=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.minimum(t / 0.004, 1) * np.exp(-t / (dur / 3))
    return amp * np.sin(2 * np.pi * f * t) * env


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


SFX = {
    'page': lambda: mix(whoosh(0.32, 0.18), chime([84, 89], 0.07, tau=0.35, amp=0.32)),
    'tick': lambda: click(0.45, 2600),
    'key': lambda: mix(click(0.3, 1800), beep(1396.9, 0.06, 0.25)),
    'open': lambda: chime([77, 81, 84], 0.06, tau=0.4, amp=0.42),
    'close': lambda: chime([84, 81, 77], 0.06, tau=0.35, amp=0.36),
    'arrive': lambda: chime([72, 77, 81, 84], 0.09, tau=0.7, amp=0.38),
}


# ================================================================== build

def check(st):
    for tr in st['tracks']:
        for slot in tr['slots']:
            for sec in slot:
                for (t, inst, note, vel, pan, dur) in sec.ev:
                    st['insts'][inst].used.add(note)


def build(preview=None):
    st = smooth()
    check(st)
    tables = dict(inst=[], nmap=[], samp=[], track=[], slot=[], sec=[], ev=[])
    bank = bytearray()
    sizes = {}
    for inst in st['insts']:
        nmap, maxshift = plan_samples(inst)
        rendered = {src: inst.render(src, maxshift[src]) for src in sorted(maxshift)}
        if inst.mode == 2:
            gain = 0.11 / max(np.sqrt(np.mean(x ** 2)) for x, _ in rendered.values())
        sid = {}
        for src, (x, ls) in rendered.items():
            pcm = to_int16(x, gain if inst.mode == 2 else 0.42 / np.max(np.abs(x)))
            if inst.mode == 3:
                data = mei_adpcm.encode(pcm)
                ls = len(pcm)
            else:
                data = mei_adpcm.encode(pcm, loop_start=ls)
            sid[src] = len(tables['samp']) // 4
            hold = int(round(ls / FRAME)) if inst.mode == 1 else 0
            tables['samp'] += [len(bank), len(pcm), ls, hold]
            bank += data
            sizes[inst.name] = sizes.get(inst.name, 0) + len(data)
            if preview:
                dec = mei_adpcm.decode(data, len(pcm)).astype(np.float64) / 32768
                if inst.mode != 3:
                    reps = int(math.ceil(1.5 * SR / max(1, len(pcm) - ls)))
                    y = np.concatenate([dec] + [dec[ls:]] * reps)
                    if inst.mode == 1:
                        y *= np.exp(-np.maximum(0, np.arange(len(y)) - ls) / SR / inst.tail_tau)
                else:
                    y = dec
                mei_adpcm.save_wav(os.path.join(preview, '%s_%d.wav' % (inst.name, src)),
                                   np.round(y * 32767).astype(np.int16))
        lo, hi = min(nmap), max(nmap)
        base = len(tables['nmap'])
        for m in range(lo, hi + 1):
            if m in nmap:
                src, sh = nmap[m]
                tables['nmap'].append(sid[src] | (sh << 16))
            else:
                tables['nmap'].append(-1)
        tables['inst'] += inst.params() + [base, lo, hi, 0]
    for tr in st['tracks']:
        slot_base = len(tables['slot']) // 2
        for slot in tr['slots']:
            sec_base = len(tables['sec']) // 3
            for sec in slot:
                ev = sorted(sec.ev, key=lambda e: e[0])
                ev_base = len(tables['ev']) // 2
                for (t, inst, note, vel, pan, dur) in ev:
                    assert 0 <= t < 65536 and dur < 32768
                    tables['ev'] += [t | (dur << 16), inst | (note << 4) | (vel << 11) | (pan << 18)]
                tables['sec'] += [ev_base, len(ev), sec.length]
            tables['slot'] += [sec_base, len(slot)]
        tables['track'] += [slot_base, len(tr['slots'])]
    return st, tables, bytes(bank), sizes


def write(st, tables, bank, sfx):
    os.makedirs(AUD, exist_ok=True)
    with open(os.path.join(AUD, 'music.adp'), 'wb') as f:
        f.write(bank)
    L = ['// Generated by tools/gen_weather_audio.py - do not edit.',
         '// The music\'s samples and score and the interface sounds, read by music.akr.', '',
         'embed MU_BANK: u8 = "audio/music.adp"', '',
         'const MU_TRACKS = %d' % len(st['tracks']),
         'const MU_REVERB = %d               // preset' % st['reverb'],
         'const MU_WET = %d                  // reverb wet level' % st['wet'],
         'const MU_TEMPO = %d                // ticks x 256 per frame' % round(256 * st['tempo']), '']

    def arr(name, vals, comment, per=16):
        L.append('// ' + comment)
        rows = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]s32 = [%s]' % (name, len(vals), (',\n    ').join(rows)))
    arr('MU_INST', tables['inst'], 'per instrument: mode (1 struck, 2 sustained, 3 one-shot), attack per frame, '
        'decay and release per frame (x65536), volume, reverb send, tremolo depth (x256), tremolo rate, '
        'note map start, lowest note, highest note, 0', 12)
    arr('MU_NMAP', tables['nmap'], 'note map: sample | octaves up << 16, or -1')
    arr('MU_SAMP', tables['samp'], 'per sample: byte offset in the bank, length, loop start, frames before '
        'the loop (struck)', 8)
    arr('MU_TRACK', tables['track'], 'per track: first slot, slots', 8)
    arr('MU_SLOT', tables['slot'], 'per slot: first section, sections (variants)', 16)
    arr('MU_SEC', tables['sec'], 'per section: first event, events, length (ticks)', 15)
    arr('MU_EV', tables['ev'], 'per event: tick | duration << 16 (ticks, 0: none), '
        'inst | note << 4 | velocity << 11 | pan << 18', 16)
    L.append('')
    L.append('// interface sounds (4-bit ADPCM, played once)')
    for name, (data, n) in sfx.items():
        L.append('embed SFX_%s: u8 = "audio/sfx_%s.adp"' % (name.upper(), name))
        L.append('const SFX_%s_LEN = %d' % (name.upper(), n))
    with open(os.path.join(CART, 'mu_data.akr'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def main():
    preview = None
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        preview = sys.argv[2]
        os.makedirs(preview, exist_ok=True)
    st, tables, bank, sizes = build(preview)
    os.makedirs(AUD, exist_ok=True)
    sfx = {}
    for name, fn in SFX.items():
        x = fn()
        pcm = to_int16(x, 0.5 / max(1e-9, np.max(np.abs(x))))
        data = mei_adpcm.encode(pcm)
        with open(os.path.join(AUD, 'sfx_%s.adp' % name), 'wb') as f:
            f.write(data)
        sfx[name] = (data, len(pcm))
        if preview:
            mei_adpcm.save_wav(os.path.join(preview, 'sfx_%s.wav' % name), mei_adpcm.decode(data, len(pcm)))
    write(st, tables, bank, sfx)
    print('bank %d bytes (%s); %d events; sounds %d bytes' % (
        len(bank), ', '.join('%s %d' % kv for kv in sizes.items()), len(tables['ev']) // 2,
        sum(len(d) for d, n in sfx.values())))


if __name__ == '__main__':
    main()
