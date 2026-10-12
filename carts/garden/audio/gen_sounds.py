#!/usr/bin/env python3
"""The movement garden's sounds: the wind-up robot, the goals, the shrine town's places.

Everything is synthesised here (no recordings) and written as one bank of 4-bit ADPCM,
carts/garden/audio/sounds.adp, with the tables carts/garden/audio/sound.akr reads in
carts/garden/audio/sound_data.akr:

- the robot: footsteps on seven materials (stone, gravel, wood, earth, metal, roof tile, water),
  its jumps, landings, kicks, the glider, poles, rails, the ground pound, the wind-up key;
- the goals: coins, red coins (one note, pitched up the scale by count), the star coming down and
  taken, a shortcut opened, the last train's clock, the stage bell (star 3);
- the places: looping beds (town, shotengai, precinct, woods, mountain wind, bamboo), positional
  loops (the falls, the stream and canal, the watermill, the shotengai's loudspeakers, the train),
  sounds on a timer at a place (the shishi-odoshi, the station chime, the temple's suzu, the
  town's five o'clock chime), and life heard now and then (crows, higurashi, a bulbul, a kite,
  pigeons, a bicycle bell);
- the zones of the shrine town: boxes that choose the bed, the music's mix, the reverb and the
  footstep material (the first box that holds the player wins).

Sounds that need no top end are rendered at 7,350, 11,025 or 16,000 Hz and played at the matching
pitch, which halves or thirds their bytes. Looping sounds are circular (whole cycles, FFT noise)
and start with a lead-in of their own last 56 samples, so ADPCM enters the loop the same way
every pass.

    python3 carts/garden/audio/gen_sounds.py [--preview DIR]    (DIR: a WAV of every sound)
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from garden_dsp import *  # noqa: F401,F403
from garden_dsp import mei_adpcm, HERE

OUT_BANK = os.path.join(HERE, 'sounds.adp')
OUT_AKR = os.path.join(HERE, 'sound_data.akr')

SOUNDS = []          # (name, sr, x, loop, vol, reverb)


def snd(name, sr, loop=False, vol=200, reverb=True):
    def deco(fn):
        SOUNDS.append((name, sr, fn, loop, vol, reverb))
        return fn
    return deco


# ================================================================== the robot

def tink(sr, f0=2300, amp=1.0, seed=0, tau=0.035):
    """The robot's tin foot: a small inharmonic ring."""
    n = secs(0.12, sr)
    return amp * modal(n, sr, [(f0, 1.0, tau), (f0 * 2.76, 0.45, tau * 0.6), (f0 * 5.4, 0.2, tau * 0.35),
                              (f0 * 0.51, 0.25, tau * 0.8)], seed)


def thud(sr, f=150, tau=0.025, amp=1.0, seed=0, dur=0.12):
    n = secs(dur, sr)
    t = tt(n, sr)
    x = np.sin(2 * np.pi * np.cumsum(f * (1 - 0.35 * t / (dur))) / sr) * np.exp(-t / tau)
    x += 0.4 * lp(noise(n, seed), 1200, sr) * np.exp(-t / (tau * 0.5))
    return amp * x


def step(sr, body, tink_amp, f0, seed):
    n = secs(0.26, sr)
    x = np.zeros(n)
    add(x, body, 0)
    add(x, tink(sr, f0, tink_amp, seed), secs(0.004, sr))
    return fade(x, sr, 0.0005, 0.04)


@snd('step_stone', SR, vol=150)
def _():
    sr = SR
    b = mix(thud(sr, 170, 0.02, 0.8, 1), 0.5 * burst(secs(0.05, sr), sr, 800, 4000, 0.008, 2))
    return step(sr, b, 0.55, 2400, 3)


@snd('step_gravel', SR, vol=150)
def _():
    sr = SR
    n = secs(0.2, sr)
    b = np.zeros(n)
    add(b, thud(sr, 140, 0.02, 0.5, 4), 0)
    b += 1.6 * grains(n, sr, 70, 0.11, 1400, 7500, 5, decay=0.05)
    return step(sr, b, 0.3, 2300, 6)


@snd('step_wood', SR, vol=160)
def _():
    sr = SR
    n = secs(0.2, sr)
    b = modal(n, sr, [(185, 1.0, 0.05), (420, 0.7, 0.035), (760, 0.45, 0.025), (1290, 0.25, 0.015)], 7)
    b += 0.3 * burst(n, sr, 500, 3000, 0.006, 8)
    return step(sr, b, 0.4, 2200, 9)


@snd('step_earth', SR, vol=150)
def _():
    sr = SR
    n = secs(0.22, sr)
    b = np.zeros(n)
    add(b, thud(sr, 110, 0.03, 0.7, 10), 0)
    b += 0.9 * grains(n, sr, 26, 0.14, 2200, 7000, 11, dur=(0.0008, 0.003))   # dry leaves
    return step(sr, b, 0.22, 2100, 12)


@snd('step_metal', SR, vol=150)
def _():
    sr = SR
    n = secs(0.3, sr)
    b = modal(n, sr, [(520, 1.0, 0.16), (527, 0.7, 0.15), (1290, 0.6, 0.11), (2140, 0.4, 0.08),
                      (3330, 0.25, 0.05), (4870, 0.15, 0.03)], 13)
    b += 0.6 * thud(sr, 120, 0.02, 1.0, 14, 0.3)[:n]
    return step(sr, b, 0.7, 2500, 15)


@snd('step_tile', SR, vol=150)
def _():
    sr = SR
    n = secs(0.2, sr)
    b = modal(n, sr, [(1150, 1.0, 0.03), (2610, 0.6, 0.02), (4100, 0.35, 0.012)], 16)
    add(b, 0.45 * modal(n, sr, [(1230, 1.0, 0.02), (2840, 0.5, 0.014)], 17), secs(0.028, sr))  # the tile rocks
    b += 0.5 * thud(sr, 150, 0.015, 1.0, 18, 0.2)[:n]
    return step(sr, b, 0.35, 2400, 19)


@snd('step_water', SR, vol=150)
def _():
    sr = SR
    n = secs(0.28, sr)
    x = bp(noise(n, 20), 400, 5000, sr) * expdec(n, sr, 0.05, 0.004) * 0.7
    rng = np.random.default_rng(21)
    for k in range(4):
        add(x, 0.5 * bubble(sr, rng.uniform(500, 1100), rng.uniform(0.02, 0.04)), secs(rng.uniform(0.01, 0.12), sr))
    add(x, tink(sr, 2100, 0.12, 22), 0)
    return fade(x, sr, 0.001, 0.05)


def twang(sr, f0, f1, dur, seed):
    """The robot's spring let go."""
    n = secs(dur, sr)
    t = tt(n, sr)
    f = f0 * (f1 / f0) ** np.minimum(t / (dur * 0.6), 1.0)
    f = f * (1 + 0.05 * np.sin(2 * np.pi * 26 * t) * np.exp(-t / 0.1))
    ph = 2 * np.pi * np.cumsum(f) / sr
    x = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * expdec(n, sr, dur * 0.35, 0.003)
    return x


def whirr(sr, f0, f1, dur, seed, lo=500, hi=4000):
    """A little clockwork motor: a buzzy saw sweep through a band."""
    n = secs(dur, sr)
    t = tt(n, sr)
    f = f0 * (f1 / f0) ** (t / dur)
    ph = np.cumsum(f) / sr
    saw = 2 * (ph % 1.0) - 1
    env = np.sin(np.pi * np.minimum(t / dur, 1.0)) ** 0.7
    return bp(saw, lo, hi, sr) * env


@snd('jump', SR, vol=170)
def _():
    sr = SR
    x = np.zeros(secs(0.36, sr))
    add(x, 0.9 * twang(sr, 250, 470, 0.32, 30), 0)
    add(x, 0.35 * whirr(sr, 900, 1500, 0.09, 31), 0)
    add(x, tink(sr, 2600, 0.35, 32), 0)
    return fade(x, sr, 0.0005, 0.05)


@snd('jump_spin', SR, vol=170)        # the third jump, the side flip and backflip: a wind-up spin
def _():
    sr = SR
    x = np.zeros(secs(0.5, sr))
    add(x, 0.8 * twang(sr, 300, 620, 0.4, 33), 0)
    add(x, 0.5 * whirr(sr, 700, 2200, 0.38, 34), secs(0.02, sr))
    rng = np.random.default_rng(35)
    for k in range(7):
        add(x, tink(sr, rng.uniform(2400, 3400), 0.18, 36 + k, 0.012), secs(0.03 + 0.045 * k, sr))
    return fade(x, sr, 0.0005, 0.08)


@snd('land', SR, vol=170)
def _():
    sr = SR
    x = np.zeros(secs(0.28, sr))
    add(x, thud(sr, 110, 0.05, 1.0, 40, 0.25), 0)
    rng = np.random.default_rng(41)
    for k, at in enumerate((0.0, 0.021, 0.047)):
        add(x, tink(sr, rng.uniform(1700, 2700), 0.45 * 0.6 ** k, 42 + k, 0.025), secs(at, sr))
    return fade(x, sr, 0.0005, 0.05)


@snd('land_hard', SR, vol=180)        # the ground pound landing
def _():
    sr = SR
    n = secs(0.8, sr)
    t = tt(n, sr)
    x = np.sin(2 * np.pi * np.cumsum(85 * (1 - 0.45 * np.minimum(t / 0.3, 1))) / sr) * np.exp(-t / 0.16)
    x += 0.6 * lp(noise(n, 50), 700, sr) * np.exp(-t / 0.05)
    x += 0.45 * modal(n, sr, [(310, 1.0, 0.3), (316, 0.7, 0.28), (760, 0.6, 0.2), (1290, 0.4, 0.14),
                              (2030, 0.25, 0.09)], 51)
    x += 0.8 * grains(n, sr, 90, 0.35, 900, 6000, 52, decay=0.12)
    return fade(x, sr, 0.0005, 0.1)


@snd('pound_spin', SR, vol=170)
def _():
    sr = SR
    n = secs(0.36, sr)
    x = 0.6 * whirr(sr, 280, 1100, 0.34, 60, 300, 3000)[:n]
    x = np.concatenate([x, np.zeros(n - len(x))])
    t = 0.0
    k = 0
    while t < 0.3:                        # the ratchet speeding up
        add(x, tink(sr, 3000, 0.3, 61 + k, 0.006), secs(t, sr))
        t += 1 / (18 + 90 * t)
        k += 1
    return fade(x, sr, 0.0005, 0.04)


@snd('kick', SR, vol=180)
def _():
    sr = SR
    n = secs(0.4, sr)
    x = 0.9 * modal(n, sr, [(690, 1.0, 0.1), (1720, 0.6, 0.07), (2900, 0.35, 0.04), (697, 0.6, 0.1)], 70)
    add(x, 0.6 * twang(sr, 330, 560, 0.26, 71), secs(0.01, sr))
    x += 0.4 * thud(sr, 140, 0.02, 1.0, 72, 0.4)[:n]
    return fade(x, sr, 0.0005, 0.06)


@snd('wall_slide', 11025, loop=True, vol=120)
def _():
    sr = 11025
    n = blocks(0.5 * sr)
    x = circ_noise(n, sr, band_shape(1300, 4500), 80)
    rng = np.random.default_rng(81)
    g = np.zeros(n)
    for _ in range(140):                      # grit catching
        m = rng.integers(10, 40)
        circ_add(g, rng.standard_normal(m) * np.hanning(m) * rng.uniform(0.5, 2.0), int(rng.integers(0, n)))
    x = x * (0.6 + 0.4 * circ_env(n, 82, ((3, 0.6), (7, 0.4)))) + circ_filter(g, sr, band_shape(1500, 5000))
    return x


@snd('ledge_grab', SR, vol=170)
def _():
    sr = SR
    x = np.zeros(secs(0.24, sr))
    add(x, tink(sr, 2200, 0.8, 90), 0)
    add(x, tink(sr, 2650, 0.6, 91), secs(0.035, sr))
    add(x, thud(sr, 160, 0.02, 0.4, 92), 0)
    return fade(x, sr, 0.0005, 0.04)


@snd('ledge_climb', SR, vol=150)
def _():
    sr = SR
    x = np.zeros(secs(0.32, sr))
    for k in range(4):
        add(x, tink(sr, 2900 + 120 * k, 0.4, 100 + k, 0.008), secs(0.05 * k, sr))
    add(x, 0.4 * whirr(sr, 600, 950, 0.22, 105), secs(0.02, sr))
    return fade(x, sr, 0.0005, 0.04)


@snd('dive', SR, vol=150)
def _():
    sr = SR
    n = secs(0.38, sr)
    t = tt(n, sr)
    w = noise(n, 110)
    # a band that sweeps up then down: two passes of fixed bands crossfaded
    a = bp(w, 500, 1400, sr) * np.sin(np.pi * np.minimum(t / 0.2, 1)) ** 2 * (t < 0.2)
    b = bp(w, 1200, 3200, sr) * np.sin(np.pi * np.clip((t - 0.06) / 0.3, 0, 1)) ** 2
    x = a + b
    add(x, 0.5 * twang(sr, 220, 300, 0.2, 111), 0)
    return fade(x, sr, 0.001, 0.05)


@snd('glide_open', SR, vol=160)
def _():
    sr = SR
    x = np.zeros(secs(0.3, sr))
    for k, at in enumerate((0.0, 0.055)):
        add(x, bp(noise(secs(0.08, sr), 120 + k), 180, 2600, sr) * expdec(secs(0.08, sr), sr, 0.02, 0.001) * (1 - 0.3 * k), secs(at, sr))
    add(x, 0.3 * whirr(sr, 400, 700, 0.2, 122, 200, 2000), secs(0.05, sr))
    return fade(x, sr, 0.0005, 0.05)


@snd('glide', 11025, loop=True, vol=120)
def _():
    sr = 11025
    n = blocks(0.5 * sr)
    i = np.arange(n) / n
    w = circ_noise(n, sr, band_shape(150, 1300), 130)
    blades = 9                                    # the propeller's beat: whole cycles in the loop
    am = 0.55 + 0.45 * np.abs(np.sin(np.pi * blades * 2 * i)) ** 1.5
    hum = sum(a * np.sin(2 * np.pi * k * 70 * i) for k, a in ((1, 1.0), (2, 0.4), (3, 0.2)))
    return w * am * 0.8 + 0.25 * hum


@snd('pole_grab', SR, vol=170)
def _():
    sr = SR
    n = secs(0.7, sr)
    x = modal(n, sr, [(880, 1.0, 0.32), (884, 0.7, 0.3), (2410, 0.5, 0.18), (4300, 0.2, 0.07)], 140)
    x += 0.5 * thud(sr, 180, 0.015, 1.0, 141, 0.7)[:n]
    return fade(x, sr, 0.0005, 0.1)


@snd('pole_climb', SR, vol=110)
def _():
    sr = SR
    x = np.zeros(secs(0.1, sr))
    add(x, 0.6 * burst(secs(0.02, sr), sr, 1500, 6000, 0.003, 150), 0)
    add(x, tink(sr, 3100, 0.4, 151, 0.01), 0)
    return fade(x, sr, 0.0005, 0.02)


@snd('rail_grind', SR, loop=True, vol=120)
def _():
    sr = SR
    n = blocks(0.5 * sr)
    x = circ_noise(n, sr, lambda f: band_shape(2400, 9000)(f) * (1 + 3 * np.exp(-((f - 1850) / 120) ** 2)
                                                                 + 2.5 * np.exp(-((f - 3120) / 150) ** 2)
                                                                 + 2 * np.exp(-((f - 4700) / 200) ** 2)), 160)
    rng = np.random.default_rng(161)
    c = np.zeros(n)
    for _ in range(220):                      # sparks crackling
        m = int(rng.integers(6, 24))
        circ_add(c, rng.standard_normal(m) * rng.uniform(0.5, 3.0), int(rng.integers(0, n)))
    return x * (0.75 + 0.25 * circ_env(n, 162, ((5, 0.5), (11, 0.5)))) + circ_filter(c, sr, band_shape(3000, 9000))


@snd('bounce', SR, vol=180)
def _():
    sr = SR
    n = secs(0.5, sr)
    t = tt(n, sr)
    f = 120 + 230 * (1 - np.exp(-t / 0.08))
    f *= 1 + 0.06 * np.sin(2 * np.pi * 14 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * expdec(n, sr, 0.15, 0.004)
    x += 0.8 * thud(sr, 75, 0.05, 1.0, 170, 0.5)[:n]
    x += 0.5 * bp(noise(n, 171), 200, 2500, sr) * expdec(n, sr, 0.03, 0.001)      # the canvas
    return fade(x, sr, 0.0005, 0.06)


@snd('splash', SR, vol=190)
def _():
    sr = SR
    n = secs(0.8, sr)
    t = tt(n, sr)
    x = bp(noise(n, 180), 300, 6500, sr) * np.minimum(t / 0.01, 1) * np.exp(-t / 0.13)
    x += 0.6 * lp(noise(n, 181), 400, sr) * np.exp(-t / 0.06)
    rng = np.random.default_rng(182)
    for k in range(26):
        at = rng.uniform(0.02, 0.6) ** 1.3
        add(x, 0.35 * math.exp(-at / 0.3) * bubble(sr, rng.uniform(450, 1500), rng.uniform(0.015, 0.045)), secs(at, sr))
    return fade(x, sr, 0.0005, 0.1)


@snd('bonk', SR, vol=170)
def _():
    sr = SR
    n = secs(0.4, sr)
    t = tt(n, sr)
    drop = 1 - 0.06 * np.minimum(t / 0.2, 1)
    x = np.zeros(n)
    for f, a, tau in ((420, 1.0, 0.12), (1010, 0.6, 0.08), (1780, 0.35, 0.05)):
        x += a * np.sin(2 * np.pi * np.cumsum(f * drop) / sr) * np.exp(-t / tau)
    x += 0.6 * thud(sr, 130, 0.03, 1.0, 190, 0.4)[:n]
    return fade(x, sr, 0.0005, 0.05)


@snd('skid', SR, vol=130)
def _():
    sr = SR
    n = secs(0.3, sr)
    t = tt(n, sr)
    x = bp(noise(n, 200), 700, 4000, sr) * np.sin(np.pi * np.minimum(t / 0.3, 1)) ** 0.6
    x *= 0.7 + 0.3 * np.sin(2 * np.pi * 37 * t)
    return fade(x, sr, 0.002, 0.05)


@snd('windup', SR, vol=170)            # back to the start (Y), a world opened: the key wound
def _():
    sr = SR
    x = np.zeros(secs(1.3, sr))
    t, k = 0.0, 0
    while t < 0.85:
        add(x, tink(sr, 2700 + 300 * (k % 2), 0.5, 210 + k, 0.01), secs(t, sr))
        add(x, 0.5 * burst(secs(0.015, sr), sr, 1500, 6000, 0.002, 230 + k), secs(t, sr))
        t += 1 / (6 + 18 * t)
        k += 1
    add(x, 0.5 * glock(secs(0.45, sr), sr, mtof(98), 0.3, 240), secs(0.9, sr))
    return fade(x, sr, 0.0005, 0.08)


# ================================================================== goals

D_YO = [62, 64, 67, 69, 71]                # D E G A B: the music's scale


def yo(i, base=62):
    """The i-th note of the D yo scale from D4."""
    return D_YO[i % 5] + 12 * (i // 5) + (base - 62)


@snd('coin', SR, vol=170)
def _():
    sr = SR
    x = np.zeros(secs(0.7, sr))
    add(x, glock(secs(0.6, sr), sr, mtof(93), 0.3, 300), 0)
    add(x, glock(secs(0.6, sr), sr, mtof(98), 0.4, 301), secs(0.075, sr))
    return fade(x, sr, 0.0005, 0.08)


@snd('red_coin', SR, vol=180)           # D5; sound.akr pitches it up the scale by the count
def _():
    sr = SR
    n = secs(0.9, sr)
    x = pluck(n, sr, mtof(74), 0.7, 0.9, 310) + 0.35 * glock(n, sr, mtof(86), 0.4, 311)
    return fade(x, sr, 0.0005, 0.1)


@snd('red_all', SR, vol=190)
def _():
    sr = SR
    x = np.zeros(secs(2.0, sr))
    for k in range(10):
        add(x, pluck(secs(0.9, sr), sr, mtof(yo(5 + k)), 0.7, 0.6, 320 + k) * 0.6, secs(0.06 * k, sr))
    for k, m in enumerate((86, 93, 98)):
        add(x, glock(secs(1.3, sr), sr, mtof(m), 0.6, 340 + k) * 0.5, secs(0.62, sr))
    return fade(x, sr, 0.0005, 0.2)


@snd('star_appear', SR, vol=200)
def _():
    sr = SR
    n = secs(2.2, sr)
    x = np.zeros(n)
    for k in range(12):
        add(x, glock(secs(0.8, sr), sr, mtof(yo(19 - k)), 0.45, 350 + k) * (0.5 + 0.03 * k), secs(0.07 * k, sr))
    t = tt(n, sr)
    x += 0.25 * hp(noise(n, 370), 5000, sr) * np.exp(-t / 0.5) * np.minimum(t / 0.05, 1)
    add(x, 0.6 * bell(secs(1.4, sr), sr, mtof(74), [1, 2.0, 3.0, 4.2], [1.0, 0.6, 0.3, 0.2], [1, .5, .3, .2], 0, 371), secs(0.85, sr))
    return fade(x, sr, 0.001, 0.3)


@snd('star_get', SR, vol=190, reverb=True)
def _():
    sr = SR
    n = secs(3.6, sr)
    x = np.zeros(n)
    # taiko and a koto strum
    add(x, thud(sr, 70, 0.25, 1.4, 380, 0.9), 0)
    for k, m in enumerate((50, 57, 62, 64, 69, 74)):
        add(x, 0.45 * pluck(secs(2.0, sr), sr, mtof(m), 0.6, 1.4, 381 + k), secs(0.018 * k, sr))
    # the flute: A B D (held)
    for (at, m, d) in ((0.25, 81, 0.22), (0.47, 83, 0.22), (0.69, 86, 1.9)):
        add(x, 0.4 * flute(secs(d, sr), sr, mtof(m), seed=390 + m), secs(at, sr))
    # a glockenspiel arpeggio and a small temple bell
    for k, m in enumerate((86, 88, 93, 98)):
        add(x, 0.35 * glock(secs(1.2, sr), sr, mtof(m), 0.6, 400 + k), secs(0.7 + 0.09 * k, sr))
    add(x, 0.4 * bell(secs(2.4, sr), sr, mtof(81), [1, 2.32, 4.25, 5.4], [1.6, 0.9, 0.4, 0.2], [1, .4, .25, .1], 1.5, 410), secs(1.15, sr))
    # sho: D E A, swelling under it all
    t = tt(n, sr)
    sho = sum(np.sin(2 * np.pi * mtof(m) * t) + 0.3 * np.sin(4 * np.pi * mtof(m) * t) for m in (62, 64, 69, 74))
    x += 0.07 * sho * np.minimum(t / 0.8, 1) * np.clip((3.6 - t) / 1.0, 0, 1)
    return fade(x, sr, 0.0005, 0.3)


@snd('shortcut', SR, vol=200)
def _():
    sr = SR
    x = np.zeros(secs(1.5, sr))
    # the bolt: wood and iron
    add(x, modal(secs(0.3, sr), sr, [(150, 1.0, 0.07), (390, 0.6, 0.05), (980, 0.4, 0.03)], 420), 0)
    add(x, 0.5 * modal(secs(0.3, sr), sr, [(1300, 1.0, 0.06), (3200, 0.5, 0.03)], 421), secs(0.012, sr))
    add(x, thud(sr, 90, 0.06, 0.8, 422, 0.3), 0)
    for k, m in enumerate((76, 81, 86)):
        add(x, 0.55 * pluck(secs(1.0, sr), sr, mtof(m), 0.7, 0.8, 430 + k), secs(0.28 + 0.14 * k, sr))
    return fade(x, sr, 0.0005, 0.2)


@snd('clock_tick', SR, vol=150, reverb=False)
def _():
    sr = SR
    x = burst(secs(0.04, sr), sr, 2000, 7000, 0.004, 440) + 0.6 * tink(sr, 3600, 1.0, 441, 0.006)[:secs(0.04, sr)]
    return fade(x, sr, 0.0003, 0.01)


@snd('won', SR, vol=200)
def _():
    sr = SR
    x = np.zeros(secs(2.0, sr))
    add(x, thud(sr, 75, 0.2, 1.0, 450, 0.7), 0)
    for k, m in enumerate((74, 76, 79, 81, 83, 86)):
        add(x, 0.5 * pluck(secs(1.0, sr), sr, mtof(m), 0.7, 0.7, 451 + k), secs(0.07 * k, sr))
    add(x, 0.5 * glock(secs(1.4, sr), sr, mtof(98), 0.6, 460), secs(0.45, sr))
    add(x, 0.4 * glock(secs(1.4, sr), sr, mtof(93), 0.6, 461), secs(0.45, sr))
    return fade(x, sr, 0.0005, 0.2)


@snd('lost', SR, vol=190)
def _():
    sr = SR
    x = np.zeros(secs(2.0, sr))
    at = 0.0
    for k, m in enumerate((81, 79, 76, 74, 71, 69)):
        add(x, 0.5 * pluck(secs(1.0, sr), sr, mtof(m), 0.4, 0.6, 470 + k), secs(at, sr))
        at += 0.09 + 0.035 * k
    add(x, 0.8 * modal(secs(0.5, sr), sr, [(110, 1.0, 0.12), (260, 0.5, 0.08)], 480), secs(at + 0.05, sr))
    return fade(x, sr, 0.0005, 0.2)


@snd('bell', 16000, vol=210)          # the stage's temple bell (star 3), heard everywhere
def _():
    sr = 16000
    n = secs(7.5, sr)
    f0 = 128.0
    ratios = [0.5, 1.0, 1.19, 1.51, 2.0, 2.74, 3.39, 4.18, 5.4, 6.9]
    taus = [6.0, 5.0, 3.5, 2.6, 2.2, 1.4, 1.0, 0.7, 0.45, 0.3]
    amps = [0.7, 1.0, 0.55, 0.5, 0.45, 0.35, 0.3, 0.2, 0.15, 0.08]
    x = bell(n, sr, f0, ratios, taus, amps, beat=0.9, seed=490)
    t = tt(n, sr)
    x += 0.8 * lp(noise(n, 491), 500, sr) * np.exp(-t / 0.05)            # the log striking it
    x += 0.5 * np.sin(2 * np.pi * 58 * t) * np.exp(-t / 0.1)
    return fade(x, sr, 0.0005, 0.5)


@snd('door', SR, vol=170)
def _():
    sr = SR
    n = secs(1.0, sr)
    t = tt(n, sr)
    x = bp(noise(n, 500), 300, 2600, sr) * np.sin(np.pi * np.minimum(t / 0.7, 1)) ** 2 * 0.8
    add(x, 0.4 * glock(secs(0.6, sr), sr, mtof(86), 0.35, 501), secs(0.3, sr))
    add(x, 0.4 * glock(secs(0.6, sr), sr, mtof(93), 0.35, 502), secs(0.42, sr))
    return fade(x, sr, 0.002, 0.1)


# ================================================================== life (heard now and then)

def voiced(n, sr, f, harm, seed, rough=0.0):
    """A harmonic source following frequency array f (birds, crows)."""
    ph = 2 * np.pi * np.cumsum(f) / sr
    x = sum(a * np.sin(k * ph) for k, a in harm)
    if rough:
        x *= 1 + rough * lp(noise(n, seed), 90, sr) / 2
    return x


@snd('crow', 16000, vol=170)
def _():
    sr = 16000
    x = np.zeros(secs(1.45, sr))
    rng = np.random.default_rng(510)
    for k, at in enumerate((0.0, 0.62)):
        n = secs(0.42, sr)
        t = tt(n, sr)
        f = (590 - 160 * (t / 0.42) ** 1.5) * (1 + 0.02 * rng.standard_normal(n).cumsum() / np.sqrt(n)) * (1 - 0.05 * k)
        src = voiced(n, sr, f, [(k_, 1 / k_ ** 0.7) for k_ in range(1, 12)], 511 + k, rough=1.2)
        y = peak(src, 1350, 3, sr) + 0.7 * peak(src, 2550, 4, sr) + 0.2 * src
        env = np.minimum(t / 0.03, 1) * np.clip((0.42 - t) / 0.12, 0, 1)
        add(x, y * env, secs(at, sr))
    return fade(x, sr, 0.002, 0.05)


@snd('higurashi', SR, vol=110)          # the evening cicada: "kana-kana-kana"
def _():
    sr = SR
    total = 3.4
    x = np.zeros(secs(total, sr))
    k = 0
    at = 0.0
    while at < 2.9:
        d = 0.16
        n = secs(d, sr)
        t = tt(n, sr)
        f = (4700 - 500 * t / d) * (1 - 0.03 * at)
        car = np.sin(2 * np.pi * np.cumsum(f) / sr)
        buzz = 0.5 + 0.5 * np.sin(2 * np.pi * 260 * t)
        env = np.minimum(t / 0.015, 1) * np.clip((d - t) / 0.05, 0, 1)
        add(x, car * buzz * env * (0.4 + 0.6 * math.exp(-at / 1.8)), secs(at, sr))
        at += 0.215 - 0.012 * min(k, 4)
        k += 1
    return fade(x, sr, 0.002, 0.2)


@snd('bulbul', SR, vol=110)             # hiyodori: "pii-yo!"
def _():
    sr = SR
    n = secs(0.75, sr)
    t = tt(n, sr)
    f = np.where(t < 0.18, 2500 + 1300 * (t / 0.18), 3400 - 1100 * np.clip((t - 0.25) / 0.25, 0, 1))
    x = voiced(n, sr, f, [(1, 1.0), (2, 0.18)], 520)
    env = np.where(t < 0.2, np.minimum(t / 0.02, 1), np.where(t < 0.25, 0.25, 1.0)) * np.clip((0.55 - t) / 0.1, 0, 1)
    return fade(x * env, sr, 0.002, 0.05)


@snd('kite', 16000, vol=110)            # tonbi circling over the town: "piii-hyororo"
def _():
    sr = 16000
    x = np.zeros(secs(2.3, sr))
    n = secs(0.7, sr)
    t = tt(n, sr)
    f = 2350 + 280 * np.sin(np.pi * t / 0.7)
    add(x, voiced(n, sr, f, [(1, 1.0), (2, 0.1)], 530) * np.minimum(t / 0.05, 1) * np.clip((0.7 - t) / 0.12, 0, 1), 0)
    at = 0.85
    for k in range(5):
        d = 0.22
        n = secs(d, sr)
        t = tt(n, sr)
        f = (2600 - 130 * k) - 300 * t / d + 140 * np.sin(2 * np.pi * 17 * t)
        add(x, 0.8 * (0.85 ** k) * voiced(n, sr, f, [(1, 1.0), (2, 0.1)], 531 + k)
            * np.minimum(t / 0.02, 1) * np.clip((d - t) / 0.06, 0, 1), secs(at, sr))
        at += 0.24
    return fade(x, sr, 0.002, 0.1)


@snd('pigeon', 11025, vol=120)
def _():
    sr = 11025
    x = np.zeros(secs(1.6, sr))
    for k, (at, d) in enumerate(((0.0, 0.32), (0.42, 0.5), (1.02, 0.36))):
        n = secs(d, sr)
        t = tt(n, sr)
        f = 400 + 50 * np.sin(np.pi * t / d)
        y = voiced(n, sr, f, [(1, 1.0), (2, 0.3), (3, 0.1)], 540 + k)
        y *= 0.75 + 0.25 * np.sin(2 * np.pi * 32 * t)
        add(x, y * np.sin(np.pi * np.minimum(t / d, 1)) ** 1.5, secs(at, sr))
    return fade(x, sr, 0.002, 0.05)


@snd('bicycle', SR, vol=110)
def _():
    sr = SR
    x = np.zeros(secs(1.1, sr))
    for r, at0 in enumerate((0.0, 0.32)):
        for h in range(3):
            add(x, (0.7 ** h) * bell(secs(0.6, sr), sr, 3380, [1, 1.5, 2.13, 2.9], [0.3, 0.2, 0.12, 0.08],
                                     [1, 0.5, 0.35, 0.2], 6.0, 550 + 3 * r + h), secs(at0 + 0.028 * h, sr))
    return fade(x, sr, 0.0005, 0.1)


# ================================================================== on a timer at a place

@snd('station_chime', 16000, vol=170)     # "pin-pon": an announcement on the platform
def _():
    sr = 16000
    x = np.zeros(secs(2.0, sr))
    for k, m in enumerate((88, 84)):
        add(x, bell(secs(1.3, sr), sr, mtof(m), [1, 2, 3, 4.1], [0.8, 0.35, 0.2, 0.1], [1, 0.25, 0.1, 0.05], 0, 560 + k), secs(0.45 * k, sr))
    return speaker(x, sr, 300, 5000, 1.2)


def melody(sr, notes, voice, beat):
    """notes: (beat, midi, beats) -> a line played by voice(n, sr, f, seed)."""
    end = max(b + d for b, m, d in notes) * beat + 1.5
    x = np.zeros(secs(end, sr))
    for i, (b, m, d) in enumerate(notes):
        add(x, voice(secs(d * beat + 1.0, sr), sr, mtof(m), 600 + i), secs(b * beat, sr))
    return x


@snd('departure', 11025, vol=170)        # the station's departure melody (the last train leaving)
def _():
    sr = 11025
    tune = [(0, 79, 0.5), (0.5, 83, 0.5), (1, 86, 0.5), (1.5, 91, 1), (2.5, 88, 0.5), (3, 86, 0.5),
            (3.5, 83, 0.5), (4, 84, 0.5), (4.5, 88, 0.5), (5, 91, 1), (6, 90, 0.5), (6.5, 86, 0.5), (7, 91, 1.5)]
    lead = melody(sr, tune, lambda n, sr_, f, s: glock(n, sr_, f, 0.4, s), 0.3)
    bass = melody(sr, [(0, 55, 2), (2, 52, 2), (4, 48, 2), (6, 50, 2)],
                  lambda n, sr_, f, s: pluck(n, sr_, f, 0.4, 0.8, s), 0.3)
    m = max(len(lead), len(bass))
    x = np.zeros(m)
    add(x, lead, 0)
    add(x, 0.5 * bass, 0)
    return speaker(fade(x, sr, 0.001, 0.4), sr)


@snd('town_chime', 11025, vol=200)       # the town's five o'clock chime from the loudspeakers
def _():
    sr = 11025
    tune = [(0, 67, 1), (1, 69, 1), (2, 71, 1), (3, 74, 1.5), (4.5, 71, 0.5), (5, 69, 2),
            (7, 71, 1), (8, 74, 1), (9, 76, 1), (10, 74, 1), (11, 71, 1), (12, 67, 3)]

    def organ(n, sr_, f, s):
        t = tt(n, sr_)
        ph = 2 * np.pi * f * t
        y = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.1 * np.sin(4 * ph)
        y += 0.5 * bell(n, sr_, f * 2, [1, 2.4], [0.9, 0.3], [1, 0.3], 0, s)
        return y * np.minimum(t / 0.03, 1) * np.exp(-t / 1.4)
    x = melody(sr, tune, organ, 0.55)
    x = speaker(x, sr, 350, 3300, 1.4)
    return fade(echoes(x, sr, [(0.42, 0.45), (1.05, 0.3), (1.7, 0.18), (2.5, 0.1)]), sr, 0.001, 0.8)


@snd('shishi_odoshi', SR, vol=170)
def _():
    sr = SR
    n = secs(1.3, sr)
    x = modal(n, sr, [(620, 1.0, 0.09), (1430, 0.55, 0.05), (2260, 0.3, 0.03), (3500, 0.12, 0.015)], 620)
    x += 0.4 * burst(n, sr, 1000, 6000, 0.004, 621)
    rng = np.random.default_rng(622)
    for k in range(14):                          # the water running back into the tube
        add(x, 0.12 * bubble(sr, rng.uniform(700, 1600), rng.uniform(0.015, 0.03)), secs(rng.uniform(0.25, 1.1), sr))
    return fade(x, sr, 0.0005, 0.15)


@snd('suzu', 16000, vol=150)             # someone praying: the shrine's bell rope, then two claps
def _():
    sr = 16000
    x = np.zeros(secs(2.7, sr))
    rng = np.random.default_rng(630)
    for k in range(34):
        at = rng.uniform(0, 0.95)
        f = rng.uniform(3600, 4600)
        add(x, 0.35 * bell(secs(0.25, sr), sr, f, [1, 1.32, 1.71], [0.08, 0.06, 0.04], [1, 0.5, 0.3], 0, 631 + k), secs(at, sr))
    for k, at in enumerate((1.45, 1.82)):
        c = bp(noise(secs(0.12, sr), 680 + k), 700, 3200, sr) * expdec(secs(0.12, sr), sr, 0.018, 0.0005)
        add(x, 1.2 * c, secs(at, sr))
    return fade(x, sr, 0.001, 0.2)


# ================================================================== beds (looped, played on two crossfading channels)

def babble(n, sr, seed, voices=10):
    """A shopping street's murmur: noise through moving vowel-like bands, gated at syllable rate."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for v in range(voices):
        centre = rng.uniform(350, 1700)
        band = circ_noise(n, sr, band_shape(centre * 0.7, centre * 1.4), seed + v)
        syl = circ_env(n, seed + 100 + v, [(int(rng.integers(20, 48)), 1.0), (int(rng.integers(5, 15)), 0.6)])
        talk = circ_env(n, seed + 200 + v, [(int(rng.integers(1, 3)), 1.0)])     # a voice pauses
        x += band * syl ** 3 * (talk > 0.35) * rng.uniform(0.5, 1.0)
    return circ_filter(x, sr, band_shape(200, 3000))


@snd('bed_town', 7350, loop=True, vol=110, reverb=False)
def _():
    sr = 7350
    n = blocks(8.0 * sr)
    rumble = circ_noise(n, sr, lambda f: band_shape(30, 220)(f) / np.sqrt(f), 700)
    cars = circ_noise(n, sr, band_shape(250, 1400), 701) * circ_env(n, 702, ((2, 1.0), (3, 0.6), (5, 0.3))) ** 2
    air = circ_noise(n, sr, band_shape(800, 3000), 703)
    return rumble * 0.9 + cars * 0.5 + air * 0.06


@snd('bed_street', 11025, loop=True, vol=100, reverb=False)
def _():
    sr = 11025
    n = blocks(8.0 * sr)
    x = babble(n, sr, 710) * 1.0
    x += 0.35 * circ_noise(n, sr, lambda f: band_shape(40, 300)(f) / np.sqrt(f), 711)
    rng = np.random.default_rng(712)
    for k in range(9):                          # a till, a shop door's bell, a dropped coin
        f = rng.uniform(1800, 3800)
        circ_add(x, 0.15 * bell(secs(0.4, sr), sr, f, [1, 2.7], [0.12, 0.06], [1, 0.3], 0, 713 + k), int(rng.integers(0, n)))
    return x


@snd('bed_precinct', 11025, loop=True, vol=110, reverb=False)
def _():
    sr = 11025
    n = blocks(8.0 * sr)
    gust = circ_env(n, 720, ((1, 1.0), (2, 0.5), (3, 0.3)), 0.15)
    breeze = circ_noise(n, sr, band_shape(150, 1600), 721) * gust
    rng = np.random.default_rng(722)
    leaves = np.zeros(n)
    for _ in range(900):                        # leaves skittering over the gravel with the gusts
        at = int(rng.integers(0, n))
        if rng.random() > gust[at] ** 2:
            continue
        m = int(rng.integers(8, 40))
        circ_add(leaves, rng.standard_normal(m) * np.hanning(m) * rng.uniform(0.3, 1.0), at)
    return breeze * 0.7 + circ_filter(leaves, sr, band_shape(1800, 5000)) * 0.9


@snd('bed_woods', 11025, loop=True, vol=140, reverb=False)
def _():
    sr = 11025
    n = blocks(8.0 * sr)
    swell = circ_env(n, 730, ((1, 1.0), (2, 0.7), (4, 0.3)), 0.2)
    wind = circ_noise(n, sr, band_shape(120, 900), 731) * swell
    high = circ_noise(n, sr, band_shape(1500, 4500), 732) * swell ** 2
    return wind + 0.18 * high


@snd('bed_mountain', 7350, loop=True, vol=120, reverb=False)
def _():
    sr = 7350
    n = blocks(8.0 * sr)
    gust = circ_env(n, 740, ((1, 1.0), (2, 0.8), (3, 0.5), (5, 0.3)), 0.1)
    wind = circ_noise(n, sr, band_shape(80, 1300), 741) * gust ** 1.5
    whistle = circ_noise(n, sr, lambda f: np.exp(-((f - 720) / 40) ** 2) + 0.6 * np.exp(-((f - 1130) / 50) ** 2), 742)
    return wind + 0.4 * whistle * gust ** 3


@snd('bed_bamboo', 11025, loop=True, vol=140, reverb=False)
def _():
    sr = 11025
    n = blocks(8.0 * sr)
    gust = circ_env(n, 750, ((1, 1.0), (2, 0.6), (3, 0.4)), 0.2)
    rustle = circ_noise(n, sr, band_shape(1200, 5000), 751) * gust
    rng = np.random.default_rng(752)
    x = rustle * 0.5 + 0.3 * circ_noise(n, sr, band_shape(100, 700), 753) * gust
    for k in range(16):                         # culms knocking together
        at = int(rng.integers(0, n))
        if rng.random() > gust[at]:
            continue
        f = rng.uniform(380, 900)
        for h in range(int(rng.integers(1, 4))):
            circ_add(x, 0.35 * modal(secs(0.15, sr), sr, [(f, 1.0, 0.04), (f * 2.3, 0.4, 0.02)], 760 + k * 4 + h),
                     at + secs(0.07 * h, sr))
    for k in range(2):                          # a creak
        m = secs(0.5, sr)
        t = tt(m, sr)
        fr = 38 + 18 * t / 0.5
        pulses = np.sin(2 * np.pi * np.cumsum(fr) / sr) > 0.97
        c = bp(pulses.astype(float), 300, 1200, sr) * np.sin(np.pi * t / 0.5)
        circ_add(x, 0.6 * c, int(rng.integers(0, n)))
    return x


# ================================================================== positional loops (emitters)

@snd('falls', 11025, loop=True, vol=180, reverb=True)
def _():
    sr = 11025
    n = blocks(3.0 * sr)
    roar = circ_noise(n, sr, lambda f: band_shape(60, 4000)(f) / f ** 0.35, 800)
    return roar * (0.85 + 0.15 * circ_env(n, 801, ((7, 1.0), (13, 0.5))))


@snd('stream', 11025, loop=True, vol=200, reverb=True)
def _():
    sr = 11025
    n = blocks(3.0 * sr)
    x = 0.25 * circ_noise(n, sr, band_shape(700, 3500), 810)
    rng = np.random.default_rng(811)
    for k in range(420):
        circ_add(x, 0.3 * rng.uniform(0.3, 1.0) * bubble(sr, rng.uniform(380, 1900), rng.uniform(0.012, 0.04)),
                 int(rng.integers(0, n)))
    return x


@snd('watermill', 11025, loop=True, vol=200, reverb=True)
def _():
    sr = 11025
    n = blocks(4.0 * sr)
    x = 0.15 * circ_noise(n, sr, band_shape(500, 3000), 820)
    rng = np.random.default_rng(821)
    for p in range(4):                           # four paddles a turn
        at = int(p * n / 4)
        circ_add(x, 0.8 * bp(noise(secs(0.3, sr), 822 + p), 300, 3500, sr) * expdec(secs(0.3, sr), sr, 0.07, 0.003), at)
        for k in range(12):
            circ_add(x, 0.25 * bubble(sr, rng.uniform(500, 1400), rng.uniform(0.015, 0.035)), at + secs(rng.uniform(0.05, 0.6), sr))
        if p % 2 == 0:
            circ_add(x, 0.5 * modal(secs(0.2, sr), sr, [(210, 1.0, 0.05), (530, 0.5, 0.03)], 830 + p), at + secs(0.5, sr))
        m = secs(0.35, sr)
        t = tt(m, sr)
        pulses = (np.sin(2 * np.pi * np.cumsum(40 + 25 * t / 0.35) / sr) > 0.96).astype(float)
        circ_add(x, 0.5 * bp(pulses, 350, 1300, sr) * np.sin(np.pi * t / 0.35), at + secs(0.7, sr))
    return x


@snd('shop_music', 11025, loop=True, vol=130, reverb=True)   # the shotengai's loudspeakers
def _():
    sr = 11025
    beat = 0.6                               # 100 bpm; 4 bars = 9.6 s
    n = blocks(16 * beat * sr)
    x = np.zeros(n)
    chords = [(60, [64, 67, 72]), (57, [64, 69, 72]), (53, [65, 69, 72]), (55, [62, 67, 71])]
    tune = [(0, 76, 0.5), (0.5, 79, 0.5), (1, 84, 1), (2, 83, 0.5), (2.5, 81, 0.5), (3, 79, 1),
            (4, 81, 0.5), (4.5, 84, 0.5), (5, 88, 1.5), (6.5, 86, 0.5), (7, 84, 1),
            (8, 77, 0.5), (8.5, 81, 0.5), (9, 84, 1), (10, 86, 0.5), (10.5, 84, 0.5), (11, 81, 1),
            (12, 79, 0.5), (12.5, 83, 0.5), (13, 86, 1), (14, 83, 1), (15, 79, 1)]

    def square(m, d, seed):
        k = secs(d * beat, sr)
        t = tt(k, sr)
        f = mtof(m) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t))
        ph = np.cumsum(f) / sr
        y = np.sign(np.sin(2 * np.pi * ph)) * 0.6 + np.sin(2 * np.pi * ph) * 0.4
        return lp(y, 3000, sr) * np.minimum(t / 0.01, 1) * np.clip((d * beat - t) / 0.05, 0, 1)
    for i, (b, m, d) in enumerate(tune):
        circ_add(x, 0.5 * square(m, d, 840 + i), secs(b * beat, sr))
    for bar, (root, tones) in enumerate(chords):
        for q in range(4):
            at = secs((bar * 4 + q) * beat, sr)
            circ_add(x, 0.5 * pluck(secs(0.5, sr), sr, mtof(root - 12 + (7 if q % 2 else 0)), 0.3, 0.5, 850 + q), at)
            if q % 2:
                for j, m in enumerate(tones):
                    circ_add(x, 0.16 * glock(secs(0.4, sr), sr, mtof(m), 0.2, 860 + j), at)
            circ_add(x, 0.12 * burst(secs(0.05, sr), sr, 3000, 5400, 0.01, 870 + q), at + secs(beat / 2, sr))
    return speaker(x, sr, 400, 3800, 1.8)


@snd('train', 11025, loop=True, vol=230, reverb=True)
def _():
    sr = 11025
    n = blocks(2.0 * sr)
    i = np.arange(n) / n
    rumble = circ_noise(n, sr, lambda f: band_shape(30, 400)(f) / np.sqrt(f), 880)
    hum = sum(a * np.sin(2 * np.pi * k * 190 * i) for k, a in ((1, 1.0), (2, 0.5), (3, 0.3)))    # 95 Hz
    whine = np.sin(2 * np.pi * 2100 * i)                                                        # 1,050 Hz
    x = rumble * 0.8 + hum * 0.15 + whine * 0.03
    for k, at in enumerate((0.0, 0.11, 1.0, 1.11)):                    # gatan-goton
        circ_add(x, 0.9 * modal(secs(0.12, sr), sr, [(180, 1.0, 0.04), (450, 0.6, 0.03), (1100, 0.4, 0.02)], 890 + k)
                 + 0.4 * burst(secs(0.12, sr), sr, 300, 3000, 0.01, 895 + k), secs(at, sr))
    return x


# ================================================================== zones, emitters, timers, life

MATS = ['stone', 'gravel', 'wood', 'earth', 'metal', 'tile', 'water']
MAT = {m: k for k, m in enumerate(MATS)}

# The music's mixes: the gain (0-256) of each of gen_music.py's tracks (koto, flute, sho, bass, drums)
MIXES = {
    'town':     [210, 190, 130, 200, 170],
    'street':   [80, 60, 50, 80, 50],        # under the shop music
    'precinct': [150, 210, 220, 70, 0],
    'woods':    [90, 200, 170, 0, 0],
    'mountain': [0, 170, 200, 0, 0],
    'summit':   [0, 0, 170, 0, 0],
    'quiet':    [60, 0, 150, 0, 0],          # the cemetery, the culvert, the cave
    'garden':   [190, 170, 150, 180, 140],
}
MIX = {k: i for i, k in enumerate(MIXES)}

# reverb presets (stdlib/audio.akr)
OFF, ROOM, STUDIO, HALL, SPACE, ECHO = 0, 1, 2, 3, 4, 5

# life: heard now and then in the zones that list it
LIFE = [  # name, sound, mean gap (s), volume, pitch spread (%)
    ('crow', 'crow', 22, 150, 8),
    ('higurashi', 'higurashi', 26, 120, 4),
    ('bulbul', 'bulbul', 20, 110, 6),
    ('kite', 'kite', 45, 110, 3),
    ('pigeon', 'pigeon', 18, 120, 6),
    ('bicycle', 'bicycle', 30, 100, 4),
]
LIFE_BIT = {l[0]: 1 << k for k, l in enumerate(LIFE)}

# The shrine town's zones (DESIGN.md sections 2.2 and 3; metres, x east, z north, y up). The
# first box holding the player's feet wins, so the small, special places come first.
# name, (x0, z0, x1, z1), (y0, y1), bed, bed volume, mix, reverb, wet, footstep material, life
Y_ANY = (-50, 200)
ZONES_TOWN = [
    ('cave behind the falls', (204, 322, 224, 338), (12, 19), None, 0, 'quiet', SPACE, 150, 'stone', []),
    ('culvert', (229, 103, 243, 119), (-3, 0.6), None, 0, 'quiet', SPACE, 130, 'water', []),
    ('station concourse', (134, 2, 186, 14), (-2, 8.0), 'bed_town', 90, 'town', HALL, 110, 'stone', []),
    ('platform and viaduct', (0, 0, 320, 16), (8.0, 30), 'bed_town', 120, 'town', ROOM, 25, 'stone', ['kite']),
    ('the stage', (120, 336, 204, 384), (50, 120), 'bed_mountain', 150, 'summit', ECHO, 110, 'wood', ['kite']),
    ('torii tunnel', (96, 300, 128, 350), (14, 60), 'bed_woods', 70, 'woods', STUDIO, 90, 'stone', ['higurashi']),
    ('falls and gorge', (196, 290, 256, 362), Y_ANY, 'bed_mountain', 70, 'mountain', HALL, 100, 'stone', ['higurashi']),
    ('back mountain', (0, 320, 320, 384), Y_ANY, 'bed_mountain', 140, 'mountain', HALL, 50, 'earth', ['crow', 'kite']),
    ("sacred cedar's basin", (140, 266, 192, 312), (5, 40), 'bed_woods', 120, 'woods', HALL, 85, 'earth', ['higurashi', 'crow']),
    ('fox grove', (64, 270, 140, 320), Y_ANY, 'bed_woods', 130, 'woods', HALL, 70, 'earth', ['higurashi', 'crow']),
    ('ridge and pagoda', (84, 236, 256, 290), Y_ANY, 'bed_woods', 110, 'woods', HALL, 60, 'stone', ['crow', 'kite']),
    ('treetop walkway', (60, 118, 116, 270), (7, 60), 'bed_woods', 150, 'woods', HALL, 45, 'wood', ['crow', 'bulbul']),
    ('west woods', (60, 118, 114, 270), Y_ANY, 'bed_woods', 140, 'woods', HALL, 55, 'earth', ['higurashi', 'crow', 'bulbul']),
    ('bamboo and the brewery', (0, 206, 60, 320), Y_ANY, 'bed_bamboo', 150, 'woods', HALL, 45, 'earth', ['bulbul']),
    ('park', (0, 118, 60, 206), Y_ANY, 'bed_precinct', 110, 'town', ROOM, 35, 'gravel', ['pigeon', 'bulbul', 'crow']),
    ('inner precinct', (114, 167, 214, 236), Y_ANY, 'bed_precinct', 120, 'precinct', HALL, 95, 'gravel', ['bulbul', 'crow']),
    ('outer courtyard', (106, 118, 214, 167), Y_ANY, 'bed_precinct', 120, 'precinct', HALL, 65, 'gravel', ['pigeon', 'bulbul']),
    ('pond and stream', (214, 118, 256, 290), Y_ANY, 'bed_woods', 90, 'precinct', HALL, 45, 'earth', ['higurashi', 'bulbul']),
    ('cemetery and shoulder', (256, 118, 320, 320), Y_ANY, 'bed_mountain', 70, 'quiet', ROOM, 30, 'stone', ['crow', 'kite']),
    ('shotengai arcade', (140, 62, 180, 94), (-2, 6.4), 'bed_street', 110, 'street', STUDIO, 95, 'stone', []),
    ('town roofs', (0, 0, 320, 118), (5.5, 60), 'bed_town', 110, 'town', ROOM, 20, 'tile', ['kite', 'crow']),
    ('shotengai', (140, 44, 180, 104), Y_ANY, 'bed_street', 100, 'street', ROOM, 55, 'stone', ['bicycle']),
    ('back alleys', (64, 44, 140, 104), Y_ANY, 'bed_town', 110, 'town', ROOM, 70, 'stone', ['bicycle', 'crow']),
    ('canal and machiya', (0, 0, 64, 118), Y_ANY, 'bed_town', 90, 'town', ROOM, 50, 'stone', ['bicycle', 'pigeon']),
    ('schoolyard', (210, 14, 320, 104), Y_ANY, 'bed_town', 110, 'town', ROOM, 40, 'earth', ['kite', 'crow']),
    ('front road', (0, 104, 320, 118), Y_ANY, 'bed_town', 130, 'town', ROOM, 30, 'stone', ['bicycle', 'crow']),
    ('station plaza', (0, 0, 320, 64), Y_ANY, 'bed_town', 130, 'town', ROOM, 40, 'stone', ['pigeon', 'bicycle']),
    ('the town', (-1000, -1000, 1000, 1000), (-1000, 1000), 'bed_town', 110, 'town', ROOM, 35, 'stone', []),
]
# The garden (a park block in a town) and the shrine slice: one zone each until they are designed.
ZONES_GARDEN = [('the garden', (-1000, -1000, 1000, 1000), (-1000, 1000), 'bed_precinct', 110, 'garden', ROOM, 35, 'stone', ['pigeon', 'bulbul', 'bicycle'])]
ZONES_SHRINE = [('the shrine', (-1000, -1000, 1000, 1000), (-1000, 1000), 'bed_woods', 120, 'precinct', HALL, 60, 'gravel', ['higurashi', 'crow', 'bulbul'])]
WORLDS = [ZONES_GARDEN, ZONES_SHRINE, ZONES_TOWN]      # garden.game.mochi's order: garden, shrine, shrinetown

# Positional loops: sound, segment end a and b (metres; a point when a == b), full volume
# within r_full, silent beyond r_zero, volume. 'moving' ones are placed by the cart each frame.
EMITTERS_TOWN = [
    ('falls', 'falls', (214, 46, 326), (214, 14, 323), 12, 115, 190, False),
    ('gorge stream', 'stream', (224, 12, 318), (236, 1, 186), 4, 32, 170, False),
    ('canal', 'stream', (48, -0.4, 2), (48, -0.4, 290), 3, 26, 120, False),
    ('culvert', 'stream', (236, -0.4, 104), (236, -0.4, 118), 2, 22, 190, False),
    ('watermill', 'watermill', (48, 1, 196), (48, 1, 196), 4, 42, 210, False),
    ('shop music', 'shop_music', (160, 7, 46), (160, 7, 102), 5, 36, 80, False),
    ('train', 'train', (160, 10, 8), (160, 10, 8), 10, 130, 190, True),
]
EMITTERS = [[], [], EMITTERS_TOWN]

# Sounds on a timer at a place: sound, position, r_full, r_zero, volume, period (s), jitter (s), first (s)
TIMERS_TOWN = [
    ('shishi-odoshi', 'shishi_odoshi', (226, 0.6, 172), 3, 50, 190, 9, 2, 3),
    ('station chime', 'station_chime', (160, 12, 8), 12, 110, 170, 45, 15, 12),
    ('suzu', 'suzu', (160, 8.6, 214), 4, 55, 160, 30, 20, 8),
    ('five o\'clock chime', 'town_chime', (160, 40, 200), 1000, 1001, 200, 360, 0, 300),
]
TIMERS = [[], [], TIMERS_TOWN]


# ================================================================== build

def render_all(preview=None):
    out = []
    for name, sr, fn, loop, vol, rev in SOUNDS:
        x = np.asarray(fn(), dtype=np.float64)
        if loop:
            assert len(x) % 28 == 0, (name, len(x))
            pcm = to_int16(x, 0.6 if name.startswith('bed_') else 0.75)
            data = mei_adpcm.encode(np.concatenate([pcm[-LEAD:], pcm]), loop_start=LEAD)
            samples, ls = len(pcm) + LEAD, LEAD
        else:
            pcm = to_int16(x, 0.85)
            data = mei_adpcm.encode(pcm)
            samples, ls = len(pcm), -1
        out.append(dict(name=name, sr=sr, data=data, samples=samples, loop=ls, vol=vol, reverb=rev))
        if preview:
            dec = mei_adpcm.decode(data, samples).astype(np.float64) / 32768
            if loop:
                reps = max(1, int(math.ceil(6.0 * sr / (samples - ls))))
                dec = np.concatenate([dec] + [dec[ls:]] * reps)
            save_preview(os.path.join(preview, '%s.wav' % name), dec, sr)
        print('  %-14s %5.2f s at %5d Hz %s %7d bytes' % (name, len(x) / sr, sr, 'loop' if loop else '    ', len(data)))
    return out


def write(sounds):
    idx = {s['name']: k for k, s in enumerate(sounds)}
    bank = bytearray()
    rows = []
    for s in sounds:
        rows.append([len(bank), s['samples'], s['loop'], round(s['sr'] / SR * 65536), s['vol'], int(s['reverb'])])
        bank += s['data']
    with open(OUT_BANK, 'wb') as f:
        f.write(bank)

    L = ['// Generated by carts/garden/audio/gen_sounds.py - do not edit.',
         '// The garden\'s sounds (one ADPCM bank), the shrine town\'s zones, emitters, timers and life,',
         '// read by sound.akr.', '',
         'embed GA_BANK: u8 = "sounds.adp"', '',
         '// sounds']
    for k, s in enumerate(sounds):
        L.append('const GA_S_%s = %d' % (s['name'].upper(), k))
    L.append('const GA_SOUNDS = %d' % len(sounds))
    L.append('')

    def arr(name, vals, comment, per=12, ty='s32'):
        L.append('// ' + comment)
        rows_ = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]%s = [%s]' % (name, len(vals), ty, (',\n    ').join(rows_)))
    arr('GA_SND', [v for r in rows for v in r],
        'per sound: byte offset in GA_BANK, samples, loop start (-1: once), pitch (16.16 bits: its rate / '
        '22,050), volume, reverb send', 6)
    L.append('')
    L.append('// footstep materials')
    for k, m in enumerate(MATS):
        L.append('const GA_MAT_%s = %d' % (m.upper(), k))
    arr('GA_STEP', [idx['step_' + m] for m in MATS], 'the footstep sound of each material', 8)
    L.append('')
    L.append('// the music\'s mixes: track gains (koto, flute, sho, bass, drums), 0-256')
    for k, m in enumerate(MIXES):
        L.append('const GA_MIX_%s = %d' % (m.upper(), k))
    arr('GA_MIXES', [v for m in MIXES.values() for v in m], 'per mix: five track gains', 5)
    L.append('')
    arr('GA_LIFE', [v for (nm, s, gap, vol, spread) in LIFE for v in (idx[s], int(gap * 60), vol, spread)],
        'life heard now and then: sound, mean gap (frames), volume, pitch spread (%)', 4)
    for k, l in enumerate(LIFE):
        L.append('const GA_LIFE_%s = %d' % (l[0].upper(), 1 << k))
    L.append('const GA_LIVES = %d' % len(LIFE))
    L.append('')

    zones, znames, zfirst = [], [], []
    for w in WORLDS:
        zfirst += [len(zones) // 13, len(w)]
        for (nm, (x0, z0, x1, z1), (y0, y1), bed, bvol, mix, rev, wet, mat, life) in w:
            mask = 0
            for l in life:
                mask |= LIFE_BIT[l]
            zones += [x0, z0, x1, z1, int(math.floor(y0 * 16)), int(math.ceil(y1 * 16)),
                      idx[bed] if bed else -1, bvol, MIX[mix], rev, wet, MAT[mat], mask]
            znames.append(nm)
    arr('GA_WORLD_ZONES', zfirst, 'per world (garden, shrine, shrinetown): first zone, zones', 6)
    arr('GA_ZONES', zones, 'per zone: x0, z0, x1, z1 (m), y0, y1 (m x 16), bed sound (-1: none), bed volume, '
        'mix, reverb preset, reverb wet, footstep material, life mask', 13)
    L.append('const GA_ZONE_NAMES: [%d]*u8 = [%s]' % (len(znames), ',\n    '.join('"%s"' % z for z in znames)))
    L.append('')

    ems, efirst, enames = [], [], []
    for w in EMITTERS:
        efirst += [len(ems) // 11, len(w)]
        for (nm, s, a, b, rf, rz, vol, moving) in w:
            ems += [idx[s]] + [int(round(v * 16)) for v in a + b] + [rf, rz, vol, int(moving)]
            enames.append(nm)
    arr('GA_WORLD_EMITTERS', efirst, 'per world: first emitter, emitters', 6)
    arr('GA_EMITTERS', ems, 'per emitter: sound, a (x, y, z), b (x, y, z) (m x 16), full volume within (m), '
        'silent beyond (m), volume, moving (placed by ga_emitter_move)', 11)
    L.append('const GA_EMITTER_NAMES: [%d]*u8 = [%s]' % (max(1, len(enames)), ', '.join('"%s"' % e for e in enames) or '""'))
    for k, (nm, *_r) in enumerate(EMITTERS_TOWN):
        L.append('const GA_EM_%s = %d          // shrinetown\'s' % (nm.upper().replace(' ', '_'), k))
    L.append('')

    tms, tfirst = [], []
    for w in TIMERS:
        tfirst += [len(tms) // 10, len(w)]
        for (nm, s, p, rf, rz, vol, per, jit, first) in w:
            tms += [idx[s]] + [int(round(v * 16)) for v in p] + [rf, rz, vol, int(per * 60), int(jit * 60), int(first * 60)]
    arr('GA_WORLD_TIMERS', tfirst, 'per world: first timer, timers', 6)
    arr('GA_TIMERS', tms, 'per timer: sound, position (m x 16), full volume within (m), silent beyond (m), volume, '
        'period, jitter, first (frames)', 10)
    with open(OUT_AKR, 'w') as f:
        f.write('\n'.join(L) + '\n')
    return len(bank)


def main():
    preview = None
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        preview = sys.argv[2]
        os.makedirs(preview, exist_ok=True)
    sounds = render_all(preview)
    size = write(sounds)
    by = {}
    for s in sounds:
        k = 'beds' if s['name'].startswith('bed_') else 'loops' if s['loop'] >= 0 else 'once'
        by[k] = by.get(k, 0) + len(s['data'])
    print('sounds.adp: %d bytes (%s), %d sounds' % (size, ', '.join('%s %d' % kv for kv in sorted(by.items())), len(sounds)))


if __name__ == '__main__':
    main()
