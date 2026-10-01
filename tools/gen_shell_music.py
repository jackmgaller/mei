#!/usr/bin/env python3
"""The shell's ambient music (system/shell/music.akr): instrument samples, scores and the
tables the music engine reads, for three candidate styles (MUSIC_STYLE in music.akr):

  0 Glasshouse  a warm electric piano and pad on a voice-led progression, with a vibraphone
                theme that comes and goes (GameCube/Wii menu warmth)
  1 Airports    tape loops of different lengths (felt piano, a soft choir) drifting in and
                out of phase over a slow bass, after Eno's Music for Airports
  2 Crystal     quartal pad chords planing over a sub bass, a glass-bell arpeggio with echoes
                and high sparkles in a long space reverb (PS2 browser / PSP XMB)

Every style has a day and a night score (sky_day picks one at each section boundary).
All harmony stays inside the A major scale (A B C# D E F# G#), which contains the UI sounds'
A major pentatonic.

Samples are 4-bit ADPCM, rendered at the exact pitch they play (pitch 1.0, or 2.0 for an
octave up: the console resamples by nearest sample, so any other ratio would add grit).
Sustained sounds are loops of a whole number of cycles (tuned to within a cent by the loop
length); struck sounds are an attack that decays into such a loop, and the engine continues
the decay with VOL. The 'chorus' of the pads and choir is built into the loop: each harmonic
has quiet partners a whole number of cycles per loop away, so every pass is identical.

Writes system/shell/mu_<style>.adp (one bank per style) and system/shell/mu_data.akr.
    python3 tools/gen_shell_music.py [--preview DIR]   (DIR: a WAV of every sample)
"""
import math, os, sys
from itertools import combinations
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

SR = 22050
FRAME = SR / 60.0
LEAD = 56                 # samples before a sustained loop (see looped)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'system', 'shell')

PC = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
A_MAJOR = {9, 11, 1, 2, 4, 6, 8}


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def pcs(*names):
    return [PC[n] for n in names]


# ------------------------------------------------------------------ synthesis

def fit_loop(f, lo, hi):
    """The loop length in lo..hi holding a whole number of cycles closest to f. Returns
    (L, cycles, error in cents). L is a whole number of ADPCM blocks (28 samples): a loop
    that ends inside a block shares that block with padding, which costs it precision and
    clicks at every pass."""
    best = None
    for L in range(-(-lo // 28) * 28, hi + 1, 28):
        c = round(f * L / SR)
        if c < 1:
            continue
        err = abs(1200 * math.log2(c * SR / L / f))
        if best is None or err < best[2] - 1e-9:
            best = (L, c, err)
    return best


def raised(n, a):
    """0..1 raised-cosine ramp over the first a samples."""
    r = np.ones(n)
    a = min(a, n)
    r[:a] = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    return r


def lp_noise(n, fc, seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    a = math.exp(-2 * math.pi * fc / SR)
    y = np.zeros(n)
    acc = acc2 = 0.0
    for i in range(n):
        acc = (1 - a) * x[i] + a * acc
        acc2 = (1 - a) * acc + a * acc2
        y[i] = acc2
    return y / (np.std(y) + 1e-9)


def struck(f0, partials, attack_s, tail_tau, cutoff, noise=None, seed=0, att_ms=3.0, loop_s=(0.05, 0.14), am=None):
    """A struck tone that decays into a loop.

    partials: (ratio, amp, tau, persist). Persisting partials must be whole harmonics; they
    decay with their tau until the loop starts and stay level after it (the engine carries on
    the decay). The others fade to nothing just before the loop. am = (rate, depth): a
    tremolo (vibraphone motor) of exactly one cycle per loop, running from the start.
    Returns (x, loop_start)."""
    if am:
        loop_s = (0.985 / am[0], 1.015 / am[0])
    L, c, err = fit_loop(f0, int(loop_s[0] * SR), int(loop_s[1] * SR))
    assert err < 2.0, (f0, err)
    f = c * SR / L
    ls = int(math.ceil(attack_s * SR / 28.0)) * 28
    n = ls + L
    t = np.arange(n) / SR
    t_end = (ls - 40) / SR
    tf = min(0.25, t_end * 0.5)
    w = np.clip((t_end - t) / tf, 0, 1)
    w = 0.5 - 0.5 * np.cos(np.pi * w)
    rng = np.random.default_rng(seed)
    tl = np.minimum(t, ls / SR)
    x = np.zeros(n)
    for (ratio, amp, tau, persist) in partials:
        fr = ratio * f
        if fr > cutoff:
            continue
        ph = rng.uniform(0, 2 * np.pi)
        if persist:
            assert abs(ratio - round(ratio)) < 1e-9
            env = amp * np.exp(-tl / tau)
        else:
            env = amp * np.exp(-t / tau) * w
        x += env * np.sin(2 * np.pi * fr * t + ph)
    if noise:
        amp, dur, fc = noise
        m = int(dur * SR)
        nz = lp_noise(m, min(fc, cutoff * 0.7), seed + 99) * amp * np.exp(-np.arange(m) / (dur * SR / 4))
        nz *= raised(m, 20)
        x[:m] += nz
    x *= raised(n, int(att_ms * SR / 1000))
    if am:
        x *= 1 - am[1] * (0.5 - 0.5 * np.cos(2 * np.pi * (np.arange(n) - ls) / L))
    return x, ls


def looped(f0, loop_s, harm, cutoff, chorus, seed=0, vib=None):
    """A sustained loop. harm(k, f) gives harmonic k's amplitude; chorus(k, rng) gives
    [(cycle offset, weight)] for harmonic k (offset 0 is the harmonic itself). vib: list of
    (cycles per loop, depth) phase modulations, one per offset, for a choir-like vibrato.
    The loop starts after a lead-in of two blocks (the same waveform), so the ADPCM decoder
    reaches the loop's first block with the same history from the lead-in as from the loop's
    end; a loop from sample 0 would have to be entered from silence too, which forces a coarse
    first block and a click on every pass."""
    hi = 1.25
    L, c, err = fit_loop(f0, int(loop_s * 0.8 * SR), int(loop_s * hi * SR))
    while err > 0.8 and hi < 3:          # a longer loop when no short one is in tune
        hi += 0.25
        L, c, err = fit_loop(f0, int(loop_s * 0.8 * SR), int(loop_s * hi * SR))
    assert err < 1.0, (f0, err)
    f = c * SR / L
    n = np.arange(LEAD + L) - LEAD
    rng = np.random.default_rng(seed)
    x = np.zeros(LEAD + L)
    k = 1
    while k * f <= cutoff:
        a = harm(k, f)
        if a > 1e-4:
            for j, (d, wgt) in enumerate(chorus(k, rng)):
                ph = rng.uniform(0, 2 * np.pi)
                arg = 2 * np.pi * (k * c + d) * n / L + ph
                if vib:
                    m, depth = vib[j % len(vib)]
                    arg = arg + k * depth * c / m * np.sin(2 * np.pi * m * n / L + j * 1.7)
                x += a * wgt * np.sin(arg)
        k += 1
    return x, LEAD


# ------------------------------------------------------------------ instruments
# mode 1: struck (instant attack, hold, then decay per frame); mode 2: sustained (attack,
# sustain until the note's duration ends, then release).

class Inst:
    def __init__(self, name, mode, render, native, vol, attack_s=0.0, tail_tau=0.0, release_s=0.5,
                 reverb=True, trem=(0.0, 0.0), norm='peak'):
        self.name, self.mode, self.render, self.native = name, mode, render, sorted(native)
        self.vol, self.attack_s, self.tail_tau, self.release_s = vol, attack_s, tail_tau, release_s
        self.reverb, self.trem, self.norm = reverb, trem, norm
        self.used = set()

    def params(self):
        att = 32767 if self.mode == 1 or self.attack_s <= 0 else max(1, round(32767 / (self.attack_s * 60)))
        dec = 65536 if self.tail_tau <= 0 else round(65536 * math.exp(-1 / (self.tail_tau * 60)))
        rel = round(65536 * math.exp(-1 / (self.release_s * 60)))
        depth, rate = self.trem
        return [self.mode, att, min(dec, 65535), rel, self.vol, int(self.reverb), round(depth * 256),
                round(2 * math.pi * rate / 60 * 65536)]


def ep_render(m, shift):
    f = mtof(m)
    parts = [(1, 1.0, 2.4, True), (2, 0.26, 1.3, True), (3, 0.13, 0.55, False), (4, 0.07, 0.4, False),
             (5, 0.045, 0.28, False), (6, 0.02, 0.2, False), (14, 0.05, 0.07, False), (9.02, 0.025, 0.05, False)]
    # a little velocity 'bark' in the lower notes
    return struck(f, parts, 0.7, 2.4, 10000 / 2 ** shift, noise=(0.03, 0.012, 3000), seed=m, att_ms=2.5)


def vibes_render(m, shift):
    f = mtof(m)
    parts = [(1, 1.0, 3.2, True), (4.0, 0.32, 0.5, False), (10.0, 0.09, 0.14, False), (2.0, 0.04, 0.6, False)]
    return struck(f, parts, 0.42, 3.2, 10000 / 2 ** shift, noise=(0.07, 0.008, 4000), seed=m + 7, att_ms=1.5,
                  am=(3.6, 0.3))


def piano_render(m, shift):
    """A felt piano: soft hammer, stretched upper partials and a detuned second string that
    die away in the attack; the loop is the warm fundamental and octave."""
    f = mtof(m)
    B = 0.00018
    parts = [(1, 1.0, 2.6, True), (2, 0.34, 1.5, True)]
    for k in range(3, 16):
        r = k * math.sqrt(1 + B * k * k)
        a = k ** -1.5 / (1 + (k * f / 1500) ** 2)
        parts.append((r, a, 1.6 / (1 + 0.6 * (k - 1)), False))
    for k in range(1, 6):          # the second string, a cent or so sharp
        r = k * math.sqrt(1 + B * k * k) * (1 + 0.0008)
        parts.append((r, 0.45 * k ** -1.6, 1.4 / (1 + 0.5 * (k - 1)), False))
    x, ls = struck(f, parts, 0.85, 2.6, 10000 / 2 ** shift, noise=(0.035, 0.02, 1400), seed=m + 3, att_ms=5)
    # the prompt sound: the first half second is louder, then the aftersound
    t = np.arange(len(x)) / SR
    tl = np.minimum(t, ls / SR)
    x *= 1 + 0.8 * (np.exp(-tl / 0.3) - math.exp(-ls / SR / 0.3))
    return x, ls


def glass_render(m, shift):
    f = mtof(m)
    parts = [(1, 1.0, 0.9, True), (2, 0.12, 0.6, True), (2.32, 0.38, 0.45, False), (4.25, 0.2, 0.22, False),
             (6.63, 0.08, 0.1, False), (3.01, 0.06, 0.3, False)]
    return struck(f, parts, 0.42, 0.9, 10000 / 2 ** shift, noise=(0.02, 0.004, 6000), seed=m + 11, att_ms=1.0)


def sparkle_render(m, shift):
    f = mtof(m)
    parts = [(1, 1.0, 0.9, True), (2.32, 0.22, 0.18, False), (3.97, 0.07, 0.1, False)]
    return struck(f, parts, 0.25, 0.9, 10000 / 2 ** shift, seed=m + 13, att_ms=0.8, loop_s=(0.03, 0.08))


def chorus_soft(k, rng):
    if k == 1:
        return [(0, 1.0)]
    d = rng.choice([-1, 1])
    return [(0, 1.0), (d, 0.42), (-d, 0.28)]


def chorus_wide(k, rng):
    if k == 1:
        return [(0, 1.0), (1, 0.18)]
    d1, d2 = rng.choice([-2, -1, 1, 2], 2, replace=False)
    return [(0, 1.0), (int(d1), 0.55), (int(d2), 0.4)]


def warm_pad_render(m, shift):
    harm = lambda k, f: (1.0 / k) / math.sqrt(1 + (k * f / 900.0) ** 4)
    return looped(mtof(m), 0.46, harm, 7000 / 2 ** shift, chorus_soft, seed=m + 21)


def bass_render(m, shift):
    amps = {1: 1.0, 2: 0.34, 3: 0.12, 4: 0.045, 5: 0.02}
    return looped(mtof(m), 0.16, lambda k, f: amps.get(k, 0), 4000, lambda k, r: [(0, 1.0)], seed=m)


def choir_render(m, shift):
    """'Aah/ooh': a buzzy source shaped by vowel formants, three singers a cycle apart
    with their own vibrato."""
    F = [(620, 90, 1.0), (1050, 110, 0.45), (2600, 160, 0.16), (3300, 200, 0.06)]

    def harm(k, f):
        fr = k * f
        g = sum(a / (1 + ((fr - fc) / bw) ** 2) for fc, bw, a in F) + 0.02
        return k ** -0.9 * g
    def chorus(k, rng):
        # the other singers drift against each harmonic at their own slow rates, so the
        # beating never lines up into a pulse
        if k == 1:
            return [(0, 1.0), (1, 0.14), (-1, 0.1)]
        d1, d2 = rng.choice([-3, -2, -1, 1, 2, 3], 2, replace=False)
        return [(0, 1.0), (int(d1), 0.38), (int(d2), 0.28)]
    vib = [(6, 0.006), (5, 0.005), (7, 0.0045)]
    return looped(mtof(m), 1.2, harm, 6000 / 2 ** shift, chorus, seed=m + 31, vib=vib)


def low_pad_render(m, shift):
    harm = lambda k, f: {1: 1.0, 2: 0.45, 3: 0.22, 4: 0.1, 5: 0.05, 6: 0.025}.get(k, 0)
    return looped(mtof(m), 0.45, harm, 3000, lambda k, rng: [(0, 1.0), (1, 0.3)] if k > 1 else [(0, 1.0)], seed=m + 41)


def dark_pad_render(m, shift):
    harm = lambda k, f: (1.0 / k ** 1.4) / math.sqrt(1 + (k * f / 650.0) ** 4)
    return looped(mtof(m), 0.45, harm, 6000 / 2 ** shift, chorus_soft, seed=m + 51)


def bright_pad_render(m, shift):
    harm = lambda k, f: (1.0 / k) / math.sqrt(1 + (k * f / 3200.0) ** 2)
    return looped(mtof(m), 0.55, harm, 10000 / 2 ** shift, chorus_wide, seed=m + 61)


def sub_render(m, shift):
    amps = {1: 1.0, 2: 0.16, 3: 0.04}
    return looped(mtof(m), 0.16, lambda k, f: amps.get(k, 0), 4000, lambda k, r: [(0, 1.0)], seed=m)


# ------------------------------------------------------------------ score helpers

class Score:
    """Events for one section: (tick, inst, note, vel 0..127, pan 0..127, dur ticks)."""

    def __init__(self, length):
        self.length = length
        self.ev = []

    def add(self, t, inst, note, vel, pan=64, dur=0):
        t = int(round(t))
        assert 0 <= t < self.length, (t, self.length)
        vel = int(max(1, min(127, round(vel))))
        pan = int(max(0, min(127, round(pan))))
        dur = int(max(0, min(self.length * 2, round(dur))))
        self.ev.append([t, inst, note, vel, pan, dur])
        return self.ev[-1]


MISSING_W = 9


def voice_lead(chords, n, lo, hi, spacing=(2, 9), start=None):
    """Voicings of n notes for each chord (a list of pitch classes, most important first)
    that move as little as possible, cyclically."""
    def options(pc_list):
        pool = [m for m in range(lo, hi + 1) if m % 12 in pc_list]
        out = []
        for combo in combinations(pool, n):
            if len({m % 12 for m in combo}) < n:
                continue
            gaps = [b - a for a, b in zip(combo, combo[1:])]
            if any(g < spacing[0] or g > spacing[1] for g in gaps):
                continue
            missing = sum(1 for i, p in enumerate(pc_list[:n]) if p not in {m % 12 for m in combo})
            out.append((combo, missing))
        assert out, pc_list
        return out
    opts = [options(c) for c in chords]
    prev = start
    result = None
    for _ in range(3):
        result = []
        for o in opts:
            best = None
            for combo, missing in o:
                move = 0 if prev is None else sum(abs(a - b) for a, b in zip(combo, prev))
                centre = abs(sum(combo) / n - (lo + hi) / 2) * 0.15
                cost = move + MISSING_W * missing + centre
                if best is None or cost < best[0]:
                    best = (cost, combo)
            prev = best[1]
            result.append(list(best[1]))
    return result


# ------------------------------------------------------------------ style 0: Glasshouse

def style_glass():
    rng = np.random.default_rng(1001)
    EP, PAD, BASS, VIB = 0, 1, 2, 3
    insts = [
        Inst('ep', 1, ep_render, [56, 57, 59, 61, 62, 64, 66], vol=63, tail_tau=2.4, release_s=0.3),
        Inst('pad', 2, warm_pad_render, [], vol=42, attack_s=1.6, release_s=0.8, trem=(0.12, 0.09)),
        Inst('bass', 2, bass_render, [], vol=60, attack_s=0.25, release_s=0.45, reverb=False),
        Inst('vibes', 1, vibes_render, [69, 71, 73, 74, 76, 78, 80], vol=80, tail_tau=3.2, release_s=0.5),
    ]
    BEAT = 48
    CH = 8 * BEAT
    day = [  # bass, pitch classes (most important first)
        (33, pcs('C#', 'G#', 'B', 'E', 'A')),        # Amaj9
        (38, pcs('F#', 'C#', 'E', 'A', 'D')),        # Dmaj9
        (42, pcs('A', 'E', 'B', 'C#', 'F#')),        # F#m11
        (40, pcs('A', 'C#', 'F#', 'B', 'E')),        # E6sus4(9)
        (37, pcs('G#', 'B', 'E', 'A')),              # Amaj9/C#
        (38, pcs('F#', 'C#', 'G#', 'E', 'A')),       # Dmaj9#11
        (35, pcs('D', 'A', 'E', 'F#')),              # Bm11
        (40, pcs('D', 'A', 'F#', 'B')),              # E9sus4
    ]
    night = [
        (42, pcs('A', 'E', 'G#', 'C#')),             # F#m9
        (38, pcs('F#', 'C#', 'E', 'A')),             # Dmaj9
        (35, pcs('D', 'A', 'E', 'F#')),              # Bm11
        (37, pcs('E', 'B', 'F#', 'G#')),             # C#m11
        (42, pcs('A', 'E', 'B', 'C#')),              # F#m11
        (38, pcs('F#', 'C#', 'G#', 'A')),            # Dmaj7#11
        (40, pcs('G#', 'C#', 'B', 'A')),             # Amaj9/E
        (40, pcs('A', 'C#', 'F#', 'B')),             # E6sus4
    ]
    # B sections: a falling bass (D C# B A) to a lydian turn, back to the A section
    day_b = [
        (38, pcs('F#', 'C#', 'E', 'A')),             # Dmaj9
        (37, pcs('E', 'B', 'F#', 'G#')),             # C#m11
        (35, pcs('D', 'A', 'C#', 'F#')),             # Bm9
        (33, pcs('C#', 'G#', 'B', 'E')),             # Amaj9
        (42, pcs('A', 'E', 'B', 'C#')),              # F#m11
        (38, pcs('F#', 'C#', 'G#', 'A')),            # Dmaj7#11
        (40, pcs('A', 'C#', 'F#', 'B')),             # E6sus4
        (40, pcs('D', 'A', 'F#', 'B')),              # E9sus4
    ]
    night_b = [
        (35, pcs('D', 'A', 'C#', 'F#')),             # Bm9
        (37, pcs('E', 'B', 'F#', 'G#')),             # C#m11
        (38, pcs('F#', 'C#', 'E', 'A')),             # Dmaj9
        (37, pcs('G#', 'B', 'E', 'A')),              # Amaj9/C#
        (35, pcs('D', 'A', 'E', 'F#')),              # Bm11
        (38, pcs('F#', 'C#', 'G#', 'A')),            # Dmaj7#11
        (40, pcs('A', 'C#', 'F#', 'B')),             # E6sus4
        (40, pcs('D', 'A', 'F#', 'B')),              # E9sus4
    ]
    theme_day_b = [
        [(0, 81, 4), (4, 80, 4)],
        [(0, 76, 6), (6, 78, 2)],
        [(0, 73, 3), (3, 74, 1), (4, 78, 4)],
        [(0, 76, 8)],
        [(0, 81, 4), (4, 83, 2), (6, 81, 2)],
        [(0, 80, 6), (6, 78, 2)],
        [(0, 76, 4), (4, 73, 4)],
        [(0, 71, 4), (4, 74, 4)],
    ]
    theme_night_b = [
        [(0, 78, 6)],
        [(0, 80, 4), (4, 76, 4)],
        [(0, 81, 8)],
        [(0, 76, 8)],
        [(0, 74, 4), (4, 73, 4)],
        [(0, 80, 8)],
        [(0, 78, 4), (4, 76, 4)],
        [(0, 71, 8)],
    ]
    # the theme: per chord (beat, note, beats). The hook (E F# G# | A F# E) opens both.
    theme_day = [
        [(0, 76, 1.5), (1.5, 78, 0.5), (2, 80, 6)],
        [(0, 81, 3), (3, 78, 1), (4, 76, 4)],
        [(0, 73, 1), (1, 76, 1), (2, 83, 3), (5, 81, 3)],
        [(0, 78, 4), (4, 73, 4)],
        [(0, 76, 1.5), (1.5, 78, 0.5), (2, 80, 2), (4, 83, 4)],
        [(0, 85, 3), (3, 83, 1), (4, 81, 4)],
        [(0, 78, 1), (1, 76, 1), (2, 74, 3), (5, 73, 3)],
        [(0, 71, 4), (4, 69, 4)],
    ]
    theme_night = [
        [(0, 76, 1.5), (1.5, 78, 0.5), (2, 80, 6)],
        [(0, 81, 3), (3, 78, 1), (4, 76, 4)],
        [(0, 74, 1), (1, 78, 1), (2, 76, 6)],
        [(0, 80, 3), (3, 76, 1), (4, 73, 4)],
        [(0, 76, 1.5), (1.5, 78, 0.5), (2, 80, 2), (4, 81, 4)],
        [(0, 80, 3), (3, 78, 1), (4, 73, 4)],
        [(0, 76, 2), (2, 71, 2), (4, 73, 4)],
        [(0, 71, 8)],
    ]
    # EP patterns: (beat, voice index 0..4, accent); voice 4 is a chord tone above the voicing
    pats_day = [
        [(0, 0, 1), (0.1, 1, 1), (0.2, 2, 1), (0.3, 3, 1)],
        [(0, 0, 1), (0.1, 1, 1), (0.2, 2, 1), (0.3, 3, 1), (4, 3, 0), (4.5, 2, 0)],
        [(0, 0, 1), (0.5, 1, 0), (1, 2, 0), (1.5, 3, 0), (4, 2, 0), (5, 1, 0)],
        [(0, 0, 1), (0, 2, 1), (1, 1, 0), (1.5, 3, 0), (5, 2, 0)],
        [(0, 1, 1), (0.08, 3, 1), (3, 0, 0), (3.08, 2, 0), (6, 3, 0)],
        [(0, 0, 1), (0.15, 1, 1), (0.3, 2, 1), (0.45, 3, 1), (2.5, 4, 0), (5.5, 3, 0)],
        [(0, 0, 1), (0.12, 2, 1), (0.24, 3, 1), (2, 1, 0), (3, 4, 0), (4.5, 3, 0)],
    ]
    pats_night = [
        [(0, 0, 1), (0.15, 1, 1), (0.3, 2, 1), (0.45, 3, 1)],
        [(0, 0, 1), (0.15, 1, 1), (0.3, 2, 1), (0.45, 3, 1), (5, 3, 0)],
        [(0, 0, 1), (1, 1, 0), (2, 2, 0), (3, 3, 0)],
        [(0, 1, 1), (0.12, 3, 1), (4, 0, 0), (4.12, 2, 0)],
        [(0, 0, 1), (0.2, 2, 1), (3, 4, 0)],
    ]

    def harmony(chords, pats, n_var, vel_base, night_mode):
        pad_v = voice_lead([c[1] for c in chords], 3, 54, 69, spacing=(3, 9))
        ep_v = voice_lead([c[1] for c in chords], 4, 56, 74, spacing=(2, 7))
        out = []
        for v in range(n_var):
            s = Score(8 * CH)
            held = [None, None, None]
            bass_ev = None
            last_p = -1
            for ci, (bass, pc) in enumerate(chords):
                t0 = ci * CH
                # bass: re-struck on a new note, held through a repeated one
                if bass_ev is not None and bass_ev[2] == bass:
                    bass_ev[5] += CH
                else:
                    bass_ev = s.add(t0, BASS, bass, 96, 64, CH)
                # pad: three voices, a common tone is held over
                for i, note in enumerate(pad_v[ci]):
                    if held[i] is not None and held[i][2] == note:
                        held[i][5] += CH
                    else:
                        held[i] = s.add(t0 + i * 6, PAD, note, 100 - i * 8, 28 + i * 36, CH - i * 6)
                # electric piano
                ev = ep_v[ci]
                top = min(m for m in range(ev[-1] + 1, ev[-1] + 8) if m % 12 in pc)
                notes = ev + [top]
                if night_mode and v % 3 == 2 and ci % 2 == 1:
                    continue                     # leave some chords to the pad
                p = int(rng.integers(len(pats)))
                if p == last_p:
                    p = (p + 1) % len(pats)
                last_p = p
                for (b, idx, acc) in pats[p]:
                    t = t0 + b * BEAT + rng.integers(-1, 2) * (b > 0)
                    vel = vel_base * (1.0 if acc else 0.72) * (1 - 0.04 * idx) + rng.integers(-5, 6)
                    note = notes[idx]
                    s.add(t, EP, note, vel, 22 + (note - 56) * 4, (ci + 1) * CH - t)
            out.append(s)
        return out

    def melody(theme, vel, which, octave=0):
        s = Score(8 * CH)
        for ci, cell in enumerate(theme):
            if ci not in which:
                continue
            for j, (b, note, ln) in enumerate(cell):
                accent = 1.0 if b == 0 else 0.86
                s.add(ci * CH + b * BEAT, VIB, note + octave, vel * accent + rng.integers(-4, 5),
                      52 + rng.integers(-18, 19), ln * BEAT + 12)
        return s

    def melodies(theme, vel):
        allc = list(range(8))
        return [melody(theme, vel, allc),
                melody(theme, vel, [0, 1, 2, 3]),
                melody(theme, vel * 0.9, [4, 5, 6, 7]),
                melody(theme, vel * 0.85, [0, 1]),
                Score(8 * CH),
                melody(theme, vel, allc)]

    def melodies_b(theme, vel):
        return [melody(theme, vel, list(range(8))), melody(theme, vel * 0.9, [0, 1, 2, 3]), Score(8 * CH)]

    # form: A A B (2.6 minutes by day, 3.2 at night), each pass a fresh variant
    ha, hb = harmony(day, pats_day, 6, 74, False), harmony(day_b, pats_day, 4, 70, False)
    na, nb = harmony(night, pats_night, 6, 62, True), harmony(night_b, pats_night, 4, 58, True)
    ma, mb = melodies(theme_day, 70), melodies_b(theme_day_b, 66)
    nma, nmb = melodies(theme_night, 56), melodies_b(theme_night_b, 52)
    tracks = [
        {'day': [ha, ha, hb], 'night': [na, na, nb]},
        {'day': [ma, ma, mb], 'night': [nma, nma, nmb]},
    ]
    return dict(name='glass', insts=insts, tracks=tracks, reverb=3, wet=(176, 214), tempo=(1.0, 0.8),
                decay=(0, 0))


# ------------------------------------------------------------------ style 1: Airports

def style_tape():
    PIANO, CHOIR, LOW = 0, 1, 2
    insts = [
        Inst('piano', 1, piano_render, [59, 61, 64, 66, 69, 71, 73, 76, 78], vol=159, tail_tau=2.6,
             release_s=1.0),
        Inst('choir', 2, choir_render, [], vol=112, attack_s=2.2, release_s=1.4, trem=(0.1, 0.13)),
        Inst('low', 2, low_pad_render, [], vol=68, attack_s=2.5, release_s=1.6, reverb=True),
    ]

    def loop(length, notes):
        s = Score(length)
        for e in notes:
            s.add(*e)
        return [[s]]

    def bass_line(seq, vel=92):
        length = sum(d for _, d in seq)
        s = Score(length)
        t = 0
        for note, d in seq:
            s.add(t, LOW, note, vel, 64, d - 30)
            t += d
        return s

    # (tick, inst, note, vel, pan, dur): loops of 19.7 to 44.5 s at the day tempo
    day = [
        loop(1399, [(60, PIANO, 73, 70, 80), (150, PIANO, 76, 58, 86)]),
        loop(1181, [(400, PIANO, 69, 62, 44)]),
        loop(1901, [(700, PIANO, 78, 64, 70), (790, PIANO, 76, 56, 66), (880, PIANO, 73, 54, 60),
                    (1060, PIANO, 71, 46, 56)]),
        loop(1553, [(250, CHOIR, 64, 100, 92, 420)]),
        loop(1759, [(1000, CHOIR, 57, 100, 34, 480)]),
        loop(2047, [(1500, CHOIR, 61, 92, 70, 380)]),
        loop(2237, [(1200, PIANO, 59, 52, 40), (1214, PIANO, 66, 48, 52)]),
        loop(2671, [(1800, PIANO, 88, 34, 100)]),
    ]
    night = [
        loop(1399, [(60, PIANO, 69, 62, 78), (150, PIANO, 73, 52, 84)]),
        loop(1181, [(400, PIANO, 64, 56, 44)]),
        loop(1901, [(700, PIANO, 78, 56, 70), (790, PIANO, 76, 50, 66), (880, PIANO, 73, 48, 60),
                    (1060, PIANO, 71, 42, 56)]),
        loop(1553, [(250, CHOIR, 61, 100, 92, 440)]),
        loop(1759, [(1000, CHOIR, 54, 100, 34, 500)]),
        loop(2047, [(1500, CHOIR, 57, 92, 70, 400)]),
        loop(2237, [(1200, PIANO, 59, 46, 40), (1214, PIANO, 66, 42, 52)]),
        loop(2671, [(1800, PIANO, 61, 40, 100)]),
    ]
    tracks = [{'day': d, 'night': n} for d, n in zip(day, night)]
    # the bass: a slow progression that recolours whatever the loops are doing
    tracks.append({
        'day': [[bass_line([(38, 960), (33, 840), (35, 960), (40, 720)]),
                 bass_line([(38, 960), (35, 840), (42, 960), (40, 720)]),
                 bass_line([(33, 960), (38, 840), (35, 840), (40, 840)])]],
        'night': [[bass_line([(42, 960), (38, 960), (35, 840), (40, 720)], 88),
                   bass_line([(42, 960), (35, 840), (38, 960), (40, 720)], 88),
                   bass_line([(38, 960), (42, 960), (40, 840), (35, 720)], 88)]],
    })
    return dict(name='tape', insts=insts, tracks=tracks, reverb=4, wet=(190, 230), tempo=(1.0, 0.78),
                decay=(0, 0))


# ------------------------------------------------------------------ style 2: Crystal

def style_crystal():
    rng = np.random.default_rng(2002)
    DARK, BRIGHT, SUB, GLASS, SPARK = 0, 1, 2, 3, 4
    insts = [
        Inst('dark', 2, dark_pad_render, [], vol=74, attack_s=2.0, release_s=0.8, trem=(0.1, 0.07)),
        Inst('bright', 2, bright_pad_render, [62, 64, 66, 69, 71], vol=100, attack_s=5.0, release_s=1.6,
             trem=(0.25, 0.11)),
        Inst('sub', 2, sub_render, [], vol=63, attack_s=1.0, release_s=0.8, reverb=False),
        Inst('glass', 1, glass_render, [68, 69, 71, 73, 74, 76, 78, 80], vol=90, tail_tau=0.9, release_s=0.4),
        Inst('spark', 1, sparkle_render, [88, 90, 93, 95, 97], vol=70, tail_tau=0.9, release_s=0.3),
    ]
    BEAT = 40
    CH = 16 * BEAT
    day = [  # bass, quartal stack
        (38, [64, 69, 74]), (33, [61, 66, 71]), (42, [59, 64, 69]), (40, [61, 66, 71]),
        (35, [64, 69, 74]), (38, [61, 66, 71]), (37, [59, 64, 69]), (40, [66, 71, 76]),
    ]
    night = [
        (42, [59, 64, 69]), (38, [57, 62, 68]), (35, [64, 69, 74]), (40, [61, 66, 71]),
        (42, [61, 66, 71]), (38, [64, 69, 74]), (35, [61, 66, 71]), (37, [59, 64, 68]),
    ]

    day_b = [  # a rising bass, then home by step
        (35, [61, 66, 71]), (37, [59, 64, 68]), (38, [64, 69, 74]), (40, [66, 71, 76]),
        (42, [59, 64, 69]), (40, [61, 66, 71]), (38, [61, 66, 71]), (40, [59, 64, 69]),
    ]
    night_b = [
        (38, [57, 62, 68]), (40, [59, 64, 69]), (42, [61, 66, 71]), (37, [59, 64, 68]),
        (38, [64, 69, 74]), (35, [61, 66, 71]), (40, [59, 64, 69]), (37, [59, 64, 68]),
    ]

    def harmony(chords, n_var, night_mode):
        out = []
        for v in range(n_var):
            s = Score(8 * CH)
            held = [None] * 3
            swell = set(rng.choice(8, 2 if not night_mode else 1, replace=False).tolist())
            for ci, (bass, stack) in enumerate(chords):
                t0 = ci * CH
                s.add(t0, SUB, bass, 100, 64, CH - 20)
                for i, note in enumerate(stack):
                    if held[i] is not None and held[i][2] == note:
                        held[i][5] += CH
                    else:
                        held[i] = s.add(t0 + i * 10, DARK, note, 96 - 6 * i, 30 + 34 * i, CH - i * 10)
                if ci in swell:
                    mid = stack[1]
                    s.add(t0 + 2 * BEAT, BRIGHT, mid + 12, 100, 96 if ci % 2 else 32, CH - 2 * BEAT)
            out.append(s)
        return out

    def figure(stack):
        lo, mid, top = stack
        return [top, lo + 12, mid + 12, top + 12]

    def arps(chords, n_var, night_mode):
        out = []
        for v in range(n_var):
            s = Score(8 * CH)
            for ci, (bass, stack) in enumerate(chords):
                t0 = ci * CH
                fig = figure(stack)
                if night_mode:
                    starts = [2 * BEAT] if (v + ci) % 2 == 0 else []
                    step, reps = 20, 1
                else:
                    kind = (v + ci * 3) % 4
                    starts = [[2 * BEAT, 10 * BEAT], [2 * BEAT], [5 * BEAT], [3 * BEAT, 11 * BEAT]][kind]
                    step, reps = 10, 1
                    if v == 3 and ci % 2:
                        starts = []
                for st in starts:
                    order = fig if rng.random() < 0.7 else fig[::-1]
                    for j, note in enumerate(order):
                        t = t0 + st + j * step
                        base = (78 if j == 0 else 64) * (0.8 if night_mode else 1.0)
                        pan = 44 + rng.integers(-10, 11) if j % 2 == 0 else 84 + rng.integers(-10, 11)
                        s.add(t, GLASS, note, base, pan, 0)
                        for r in range(1, reps + 1):           # echoes, a dotted eighth apart
                            te = t + r * 3 * step
                            if te < s.length:
                                s.add(te, GLASS, note, base * 0.42 ** r, 127 - pan, 0)
            out.append(s)
        return out

    def sparkles(n_var, length, count, vel):
        notes = [88, 90, 93, 95, 97]
        out = []
        for v in range(n_var):
            s = Score(length)
            ts = sorted(rng.choice(length // 40 - 4, count, replace=False) * 40 + 40)
            for t in ts:
                note = notes[int(rng.integers(len(notes)))]
                pan = rng.integers(16, 112)
                s.add(t, SPARK, note, vel + rng.integers(-8, 9), pan, 0)
                if t + 30 < length:
                    s.add(t + 30, SPARK, note, (vel - 10) * 0.45, 127 - pan, 0)
            out.append(s)
        return out

    # form: A B (2.8 minutes by day, 3.8 at night)
    tracks = [
        {'day': [harmony(day, 4, False), harmony(day_b, 3, False)],
         'night': [harmony(night, 4, True), harmony(night_b, 3, True)]},
        {'day': [arps(day, 4, False), arps(day_b, 3, False)], 'night': [arps(night, 3, True), arps(night_b, 3, True)]},
        # sparkles use only the pentatonic notes, so they fit every chord and run on their own cycle
        {'day': [sparkles(3, 3720, 9, 60)], 'night': [sparkles(3, 3720, 4, 46)]},
    ]
    return dict(name='crystal', insts=insts, tracks=tracks, reverb=4, wet=(210, 250), tempo=(1.0, 0.75),
                decay=(0, 0))


# ------------------------------------------------------------------ build

STYLES = [style_glass, style_tape, style_crystal]


def check_scores(st):
    """Collects the notes each instrument needs and checks the music stays in A major."""
    for tr in st['tracks']:
        for mood in ('day', 'night'):
            for slot in tr[mood]:
                for sec in slot:
                    for (t, inst, note, vel, pan, dur) in sec.ev:
                        assert note % 12 in A_MAJOR, (st['name'], note)
                        st['insts'][inst].used.add(note)


def plan_samples(inst):
    """Native renders and the shift (octaves up) for each used note."""
    native = set(inst.native) if inst.native else set(inst.used)
    nmap = {}
    for m in sorted(inst.used):
        for sh in (0, 1, 2):
            if m - 12 * sh in native:
                nmap[m] = (m - 12 * sh, sh)
                break
        else:
            raise SystemExit('%s: no sample for note %d' % (inst.name, m))
    maxshift = {}
    for m, (src, sh) in nmap.items():
        maxshift[src] = max(maxshift.get(src, 0), sh)
    return nmap, maxshift


def to_int16(x, gain):
    return np.clip(np.round(x * gain * 32767), -32767, 32767).astype(np.int64)


def build(preview=None):
    tables = dict(style=[], inst=[], nmap=[], samp=[], track=[], slot=[], sec=[], ev=[])
    banks = []
    report = []
    for si, fn in enumerate(STYLES):
        st = fn()
        check_scores(st)
        bank = bytearray()
        inst_base = len(tables['inst']) // 12
        samp_base_style = len(tables['samp']) // 4
        sample_bytes = {}
        for inst in st['insts']:
            nmap, maxshift = plan_samples(inst)
            rendered = {}
            for src in sorted(maxshift):
                rendered[src] = inst.render(src, maxshift[src])
            # one gain for the instrument: peak (struck) or RMS (sustained) normalised
            if inst.mode == 1:
                ref = max(np.max(np.abs(x)) for x, _ in rendered.values())
                gain = 0.42 / ref
            else:
                ref = max(np.sqrt(np.mean(x ** 2)) for x, _ in rendered.values())
                gain = 0.11 / ref
            sid = {}
            for src, (x, ls) in rendered.items():
                pcm = to_int16(x, gain)
                if inst.mode == 1:   # level each struck note by its peak (an even keyboard)
                    pcm = to_int16(x, 0.42 / np.max(np.abs(x)))
                data = mei_adpcm.encode(pcm, loop_start=ls)
                sid[src] = len(tables['samp']) // 4
                hold = int(round(ls / FRAME)) if inst.mode == 1 else 0
                tables['samp'] += [len(bank), len(pcm), ls, hold]
                bank += data
                sample_bytes[inst.name] = sample_bytes.get(inst.name, 0) + len(data)
                if preview:
                    dec = mei_adpcm.decode(data, len(pcm)).astype(np.float64)
                    reps = int(math.ceil(1.5 * SR / max(1, len(pcm) - ls)))
                    y = np.concatenate([dec] + [dec[ls:]] * reps) / 32768
                    if inst.mode == 1:
                        tt = np.maximum(0, np.arange(len(y)) - ls) / SR
                        y *= np.exp(-tt / inst.tail_tau)
                    mei_adpcm.save_wav(os.path.join(preview, '%s_%s_%d.wav' % (st['name'], inst.name, src)),
                                       np.round(y * 32767).astype(np.int16))
            print('  %s %s: %s' % (st['name'], inst.name, ' '.join('%d%s' % (m, '' if sh == 0 else '^%d' % sh)
                                                            for m, (src, sh) in sorted(nmap.items()))))
            lo, hi = min(nmap), max(nmap)
            nm_base = len(tables['nmap'])
            for m in range(lo, hi + 1):
                if m in nmap:
                    src, sh = nmap[m]
                    tables['nmap'].append(sid[src] | (sh << 16))
                else:
                    tables['nmap'].append(-1)
            tables['inst'] += inst.params() + [nm_base, lo, hi, 0]
        assert len(st['tracks']) <= 12          # music.akr's track arrays
        track_base = len(tables['track']) // 4
        sec_cache = {}
        for tr in st['tracks']:
            row = []
            for mood in ('day', 'night'):
                slot_base = len(tables['slot']) // 2
                for slot in tr[mood]:
                    if id(slot) not in sec_cache:          # a slot repeated in the form is stored once
                        sec_cache[id(slot)] = len(tables['sec']) // 3
                        for sec in slot:
                            ev = sorted(sec.ev, key=lambda e: e[0])
                            ev_base = len(tables['ev']) // 2
                            for (t, inst, note, vel, pan, dur) in ev:
                                assert t < 65536 and dur < 32768
                                tables['ev'] += [t | (dur << 16), inst | (note << 4) | (vel << 11) | (pan << 18)]
                            tables['sec'] += [ev_base, len(ev), sec.length]
                    tables['slot'] += [sec_cache[id(slot)], len(slot)]
                row += [slot_base, len(tr[mood])]
            tables['track'] += row
        tempo = [round(256 * t) for t in st['tempo']]
        tables['style'] += [inst_base, track_base, len(st['tracks']), st['reverb'], st['wet'][0], st['wet'][1],
                            tempo[0], tempo[1], st['decay'][0], st['decay'][1]]
        fname = 'mu_%s.adp' % st['name']
        banks.append((fname, bytes(bank)))
        nev = sum(len(sec.ev) for tr in st['tracks'] for mood in ('day', 'night')
                  for slot in {id(sl): sl for sl in tr[mood]}.values() for sec in slot)
        report.append('%d %-8s bank %6d bytes (%s), %d events' % (
            si, st['name'], len(bank), ', '.join('%s %d' % kv for kv in sample_bytes.items()), nev))
    return tables, banks, report


def write(tables, banks):
    for fname, data in banks:
        with open(os.path.join(OUT, fname), 'wb') as f:
            f.write(data)
    L = ['// Generated by tools/gen_shell_music.py - do not edit.',
         '// The shell music\'s samples and scores, read by music.akr.', '']
    for i, (fname, _) in enumerate(banks):
        L.append('embed MU_BANK%d: u8 = "%s"' % (i, fname))
    L.append('')

    def arr(name, ty, vals, comment, per=16):
        L.append('// ' + comment)
        rows = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]%s = [%s]' % (name, len(vals), ty, (',\n    ').join(rows)))
    arr('MU_STYLE', 's32', tables['style'], 'per style: first instrument, first track, tracks, reverb preset, '
        'wet day, wet night, tempo day, tempo night (x256), reverb decay day, night', 10)
    arr('MU_INST', 's32', tables['inst'], 'per instrument: mode (1 struck, 2 sustained), attack per frame, '
        'decay and release per frame (x65536), volume, reverb send, tremolo depth (x256), tremolo rate, '
        'note map start, lowest note, highest note, 0', 12)
    arr('MU_NMAP', 's32', tables['nmap'], 'note map: sample | octaves up << 16, or -1')
    arr('MU_SAMP', 's32', tables['samp'], 'per sample: byte offset in the bank, length, loop start, frames before '
        'the loop (struck)', 8)
    arr('MU_TRACK', 's32', tables['track'], 'per track: day first slot, slots, night first slot, slots', 8)
    arr('MU_SLOT', 's32', tables['slot'], 'per slot: first section, sections (variants)', 16)
    arr('MU_SEC', 's32', tables['sec'], 'per section: first event, events, length (ticks)', 15)
    arr('MU_EV', 's32', tables['ev'], 'per event: tick | duration << 16 (ticks, 0: none), '
        'inst | note << 4 | velocity << 11 | pan << 18', 16)
    with open(os.path.join(OUT, 'mu_data.akr'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def main():
    preview = None
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        preview = sys.argv[2]
        os.makedirs(preview, exist_ok=True)
    tables, banks, report = build(preview)
    write(tables, banks)
    for line in report:
        print(line)
    print('tables: %d events, %d samples, %d bytes' % (len(tables['ev']) // 2, len(tables['samp']) // 4,
                                                   4 * sum(len(v) for v in tables.values())))


if __name__ == '__main__':
    main()
