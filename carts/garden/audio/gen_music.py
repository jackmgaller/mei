#!/usr/bin/env python3
"""The shrine town's music: "Momiji" (autumn leaves), one piece in layers that the places mix.

A slow, open tune in D on the yo scale (D E G A B), 75 bpm, in four 8-bar sections (A A B A),
for five layers, each its own track so that sound.akr can turn it up or down by place
(gen_sounds.py's MIXES; the zones choose a mix):

  0 koto    plucked arpeggios and figures
  1 flute   a breathy bamboo flute with the tune
  2 sho     the mouth organ's held clusters (two notes a chord), the harmony on its own
  3 bass    a soft plucked bass on the roots
  4 drums   a taiko, a wood block and the shrine's suzu bells, lightly

In the town all five play; the precinct drops the drums and most of the bass; the woods keep the
flute, the sho and a little koto; the mountain the flute and the sho; the stage only the sho, under
the wind. Every section of every track has two or three variants and the engine picks one at
random each time round (never the same twice running), as in carts/weather/music.akr.

Samples follow tools/gen_shell_music.py (whose helpers this uses): struck notes decay into a loop
of whole harmonics and the engine continues the decay; held notes are loops of whole cycles;
drums play once. Notes play at pitch 1.0, 2.0 or 4.0 of a rendered note, never between.

Writes carts/garden/audio/music.adp and carts/garden/audio/music_data.akr.
    python3 carts/garden/audio/gen_music.py [--preview DIR]   (DIR: a WAV of every sample)
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from garden_dsp import HERE, ROOT, circ_noise, band_shape, mei_adpcm
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gen_shell_music import (SR, FRAME, mtof, struck, looped, raised, lp_noise, Inst, Score,  # noqa: E402
                             plan_samples, to_int16)

YO = {2, 4, 7, 9, 11}          # D E G A B


# ================================================================== instruments

def koto_render(m, shift):
    """A koto string: bright pluck, the upper harmonics dying first, a little pluck noise."""
    f = mtof(m)
    parts = [(1, 1.0, 1.1, True), (2, 0.55, 0.6, True), (3, 0.42, 0.35, True), (4, 0.22, 0.22, True),
             (5, 0.2, 0.12, False), (6, 0.13, 0.09, False), (7, 0.1, 0.06, False), (9, 0.05, 0.04, False),
             (3.01, 0.12, 0.2, False)]
    return struck(f, parts, 0.38, 1.1, 9000 / 2 ** shift, noise=(0.06, 0.006, 5000), seed=m + 5, att_ms=1.0,
                  loop_s=(0.04, 0.3))


def bass_render(m, shift):
    f = mtof(m)
    parts = [(1, 1.0, 1.2, True), (2, 0.5, 0.6, True), (3, 0.2, 0.3, True), (4, 0.08, 0.2, False),
             (5, 0.05, 0.12, False)]
    return struck(f, parts, 0.35, 1.2, 2000, noise=(0.03, 0.01, 1200), seed=m + 9, att_ms=6.0, loop_s=(0.1, 0.9))


def chorus_none(k, rng):
    return [(0, 1.0)]


def chorus_sho(k, rng):
    if k == 1:
        return [(0, 1.0)]
    d = rng.choice([-1, 1])
    return [(0, 1.0), (int(d), 0.3)]


def flute_render(m, shift):
    """A bamboo flute: a near-sine with a little second harmonic, and breath through the loop."""
    amps = {1: 1.0, 2: 0.2, 3: 0.07, 4: 0.03}
    x, ls = looped(mtof(m), 0.4, lambda k, f: amps.get(k, 0.0), 9000, chorus_none, seed=m + 21)
    L = len(x) - ls
    f0 = mtof(m)
    nz = circ_noise(L, SR, band_shape(f0 * 0.9, min(f0 * 5, 9000)), m + 22) * 0.05
    x[ls:] += nz
    x[:ls] += nz[-ls:]
    return x, ls


def sho_render(m, shift):
    """The sho: a reed organ, bright and even, with a slow beating."""
    harm = lambda k, f: (1.0 / k ** 0.85) / math.sqrt(1 + (k * f / 2600.0) ** 4)
    return looped(mtof(m), 0.5, harm, 8000, chorus_sho, seed=m + 41)


def taiko():
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    f = 62 + 38 * np.exp(-t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.24)
    x += 0.35 * np.sin(2 * np.pi * np.cumsum(f * 2.3) / SR) * np.exp(-t / 0.08)
    x += 0.3 * lp_noise(n, 900, 3) * np.exp(-t / 0.012)
    return x * raised(n, 30)


def woodblock():
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 1060 * t) * np.exp(-t / 0.035) + 0.5 * np.sin(2 * np.pi * 2650 * t) * np.exp(-t / 0.018)
         + 0.2 * lp_noise(n, 5000, 4) * np.exp(-t / 0.003))
    return x * raised(n, 8)


def suzu():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    x = np.zeros(n)
    for k in range(12):
        at = int(rng.uniform(0, 0.12) * SR)
        fr = rng.uniform(3800, 5200)
        m = n - at
        tt = np.arange(m) / SR
        x[at:] += rng.uniform(0.4, 1.0) * np.sin(2 * np.pi * fr * tt) * np.exp(-tt / 0.09)
    return x * raised(n, 10) * 0.6


def kane():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * 1180 * r * t) * np.exp(-t / tau)
            for r, a, tau in ((1, 1.0, 0.6), (2.32, 0.5, 0.3), (3.9, 0.3, 0.15), (1.007, 0.6, 0.55)))
    return x * raised(n, 10)


DRUMS = {36: taiko, 76: woodblock, 82: suzu, 81: kane}


def drum_render(m, shift):
    x = DRUMS[m]()
    return x, len(x)


class OneShot(Inst):
    def params(self):
        p = super().params()
        p[0] = 3
        return p


# ================================================================== the score

BEAT = 48                  # ticks (frames at tempo 1.0): 75 bpm
BAR = 4 * BEAT
SEC = 8 * BAR

KOTO, FLUTE, SHO, BASS, DRUM = 0, 1, 2, 3, 4
TAIKO, BLOCK, SUZU, KANE = 36, 76, 82, 81

# (bass root, sho dyad) a bar
A_CHORDS = [(38, (62, 69)), (47, (67, 74)), (40, (67, 71)), (45, (64, 69)),
            (47, (69, 74)), (43, (67, 71)), (40, (67, 74)), (45, (64, 69))]
A2_CHORDS = A_CHORDS[:7] + [(38, (62, 69))]
B_CHORDS = [(43, (67, 71)), (45, (64, 69)), (47, (69, 74)), (45, (69, 74)),
            (43, (67, 71)), (45, (64, 69)), (38, (62, 69)), (38, (64, 69))]

A_TUNE = [
    [(0, 81, 1.5), (1.5, 79, 0.5), (2, 76, 1), (3, 74, 1)],
    [(0, 76, 3), (3, 79, 1)],
    [(0, 81, 1), (1, 83, 1), (2, 81, 1), (3, 79, 0.5), (3.5, 76, 0.5)],
    [(0, 81, 4)],
    [(0, 86, 1.5), (1.5, 83, 0.5), (2, 81, 1), (3, 79, 1)],
    [(0, 81, 1), (1, 79, 1), (2, 76, 2)],
    [(0, 74, 1), (1, 76, 1), (2, 79, 1.5), (3.5, 76, 0.5)],
    [(0, 76, 4)],
]
A2_TUNE = A_TUNE[:7] + [[(0, 74, 4)]]
B_TUNE = [
    [(0, 83, 2), (2, 86, 1), (3, 83, 1)],
    [(0, 81, 3), (3, 76, 1)],
    [(0, 79, 1), (1, 81, 1), (2, 83, 2)],
    [(0, 81, 2), (2, 79, 2)],
    [(0, 76, 1), (1, 79, 1), (2, 81, 1), (3, 83, 1)],
    [(0, 86, 2), (2, 88, 2)],
    [(0, 86, 3), (3, 83, 1)],
    [(0, 81, 4)],
]


def tones(root, dyad):
    """The chord's notes in the koto's range (62-88), on the yo scale."""
    pcs = {root % 12} | {d % 12 for d in dyad}
    return [m for m in range(62, 89) if m % 12 in pcs]


def music():
    rng = np.random.default_rng(1993)
    insts = [
        Inst('koto', 1, koto_render, [62, 64, 67, 69, 71, 74, 76], vol=100, tail_tau=1.1, release_s=0.3),
        Inst('flute', 2, flute_render, [69, 71, 74, 76, 79, 81, 83], vol=104, attack_s=0.07, release_s=0.22,
             trem=(0.07, 5.0)),
        Inst('sho', 2, sho_render, [], vol=60, attack_s=1.1, release_s=0.9, trem=(0.05, 0.25)),
        Inst('bass', 1, bass_render, [], vol=104, tail_tau=1.0, release_s=0.15, reverb=False),
        OneShot('drums', 3, drum_render, [], vol=96),
    ]

    def hum(t, amt=1):
        return max(0, min(SEC - 1, t + int(rng.integers(-amt, amt + 1))))

    def koto(chords, style):
        s = Score(SEC)
        for bar, (root, dyad) in enumerate(chords):
            t0 = bar * BAR
            tn = tones(root, dyad)
            low = [m for m in tn if m < 76] or tn
            if style == 'flow':              # eighths rising and falling over the bar
                fig = low[:3] + [m for m in tn if m >= 76][:2]
                fig = fig + fig[-2:0:-1]
                for e in range(8):
                    m = fig[e % len(fig)]
                    s.add(hum(t0 + e * BEAT // 2), KOTO, m, 74 - 6 * (e % 2) + rng.integers(-5, 6), 40 + 6 * e)
            elif style == 'sparse':          # a two-note figure on 1 and the and of 2
                s.add(hum(t0), KOTO, low[0], 80, 50)
                s.add(hum(t0 + int(1.5 * BEAT)), KOTO, tn[min(len(tn) - 1, 3)], 66, 80)
                if bar % 2:
                    s.add(hum(t0 + 3 * BEAT), KOTO, tn[min(len(tn) - 1, 2)], 60, 70)
            else:                            # 'answer': a falling run after the flute's phrase
                if bar % 2 == 1:
                    run = sorted([m for m in tn if m >= 74], reverse=True)[:4]
                    for j, m in enumerate(run):
                        s.add(hum(t0 + 2 * BEAT + j * BEAT // 2), KOTO, m, 76 - 6 * j, 30 + 22 * j)
                else:
                    s.add(hum(t0), KOTO, low[0], 72, 64)
        return s

    def flute(lines, style):
        s = Score(SEC)
        for bar, line in enumerate(lines):
            if style == 'half' and bar % 4 >= 2:
                continue
            for (b, m, d) in line:
                t = bar * BAR + int(b * BEAT)
                if style == 'grace' and d >= 2 and t >= 6:
                    up = min(x for x in range(m + 1, m + 6) if x % 12 in YO)
                    s.add(t - 6, FLUTE, up, 70, 64, 5)
                s.add(hum(t), FLUTE, m, 92 + rng.integers(-6, 7), 64 + rng.integers(-10, 11), int(d * BEAT) - 4)
        return s

    def sho(chords, style):
        s = Score(SEC)
        held = [None, None]
        for bar, (root, dyad) in enumerate(chords):
            t0 = bar * BAR
            for i, m in enumerate(dyad):
                if style == 'held' and held[i] is not None and held[i][2] == m:
                    held[i][5] += BAR
                    continue
                held[i] = s.add(t0 + 8 * i, SHO, m, 96 - 8 * i, 36 + 56 * i, BAR - 8 * i - 2)
        return s

    def bass(chords, style):
        s = Score(SEC)
        for bar, (root, dyad) in enumerate(chords):
            t0 = bar * BAR
            if style == 'long':
                s.add(hum(t0), BASS, root, 104, 64, BAR - 10)
            else:
                s.add(hum(t0), BASS, root, 106, 64, int(1.5 * BEAT))
                fifth = root + 7 if root + 7 <= 50 else root - 5
                if fifth % 12 not in YO:
                    fifth = root + 5 if root + 5 <= 50 else root - 7
                s.add(hum(t0 + int(2.5 * BEAT)), BASS, fifth, 84, 64, BEAT)
        return s

    def drums(style, last_fill):
        s = Score(SEC)
        for bar in range(8):
            t0 = bar * BAR
            s.add(hum(t0), DRUM, TAIKO, 92 if bar % 4 == 0 else 74, 64)
            if style != 'light':
                s.add(hum(t0 + int(1.5 * BEAT)), DRUM, BLOCK, 60, 90)
                s.add(hum(t0 + int(3.5 * BEAT)), DRUM, BLOCK, 66, 38)
            if style == 'full' and bar % 2 == 1:
                s.add(hum(t0 + 2 * BEAT), DRUM, TAIKO, 66, 64)
            if bar % 2 == 1:
                s.add(hum(t0 + 3 * BEAT), DRUM, SUZU, 64, 96)
            if bar == 7 and last_fill:
                for j, b in enumerate((3.0, 3.25, 3.5, 3.75)):
                    s.add(t0 + int(b * BEAT), DRUM, TAIKO, 60 + 8 * j, 64)
            if bar == 0 and style == 'full':
                s.add(t0, DRUM, KANE, 60, 70)
        return s

    tracks = [
        {'slots': [[koto(A_CHORDS, 'flow'), koto(A_CHORDS, 'sparse')],
                   [koto(A2_CHORDS, 'answer'), koto(A2_CHORDS, 'flow'), koto(A2_CHORDS, 'sparse')],
                   [koto(B_CHORDS, 'flow'), koto(B_CHORDS, 'answer')],
                   [koto(A2_CHORDS, 'sparse'), koto(A2_CHORDS, 'answer')]]},
        {'slots': [[flute(A_TUNE, 'plain'), flute(A_TUNE, 'half')],
                   [flute(A2_TUNE, 'grace'), flute(A2_TUNE, 'plain')],
                   [flute(B_TUNE, 'plain'), flute(B_TUNE, 'grace')],
                   [flute(A2_TUNE, 'half'), flute(A2_TUNE, 'grace'), Score(SEC)]]},
        {'slots': [[sho(A_CHORDS, 'held'), sho(A_CHORDS, 'each')],
                   [sho(A2_CHORDS, 'held'), sho(A2_CHORDS, 'each')],
                   [sho(B_CHORDS, 'held'), sho(B_CHORDS, 'each')],
                   [sho(A2_CHORDS, 'each'), sho(A2_CHORDS, 'held')]]},
        {'slots': [[bass(A_CHORDS, 'walk'), bass(A_CHORDS, 'long')],
                   [bass(A2_CHORDS, 'walk'), bass(A2_CHORDS, 'long')],
                   [bass(B_CHORDS, 'walk'), bass(B_CHORDS, 'long')],
                   [bass(A2_CHORDS, 'long'), bass(A2_CHORDS, 'walk')]]},
        {'slots': [[drums('light', False), drums('mid', False)],
                   [drums('mid', True), drums('full', True)],
                   [drums('full', False), drums('mid', False)],
                   [drums('light', True), drums('mid', True)]]},
    ]
    return dict(insts=insts, tracks=tracks, tempo=1.0)


# ================================================================== build (as tools/gen_weather_audio.py)

def check(st):
    for tr in st['tracks']:
        for slot in tr['slots']:
            for sec in slot:
                for (t, inst, note, vel, pan, dur) in sec.ev:
                    if inst != DRUM:
                        assert note % 12 in YO, (inst, note)
                    st['insts'][inst].used.add(note)


def build(preview=None):
    st = music()
    check(st)
    tables = dict(inst=[], nmap=[], samp=[], track=[], slot=[], sec=[], ev=[])
    bank = bytearray()
    sizes = {}
    for inst in st['insts']:
        nmap, maxshift = plan_samples(inst)
        rendered = {src: inst.render(src, maxshift[src]) for src in sorted(maxshift)}
        if inst.mode == 2:
            gain = 0.2 / max(np.sqrt(np.mean(x ** 2)) for x, _ in rendered.values())
        sid = {}
        for src, (x, ls) in rendered.items():
            pcm = to_int16(x, gain if inst.mode == 2 else 0.8 / np.max(np.abs(x)))
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
                mei_adpcm.save_wav(os.path.join(preview, 'mu_%s_%d.wav' % (inst.name, src)),
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


def write(st, tables, bank):
    with open(os.path.join(HERE, 'music.adp'), 'wb') as f:
        f.write(bank)
    L = ['// Generated by carts/garden/audio/gen_music.py - do not edit.',
         '// "Momiji", the shrine town\'s music: its samples and score, read by sound.akr.', '',
         'embed GA_MU_BANK: u8 = "music.adp"', '',
         'const GA_MU_TRACKS = %d             // koto, flute, sho, bass, drums: one layer each' % len(st['tracks']),
         'const GA_MU_TEMPO = %d             // ticks x 256 per frame' % round(256 * st['tempo']), '']

    def arr(name, vals, comment, per=16):
        L.append('// ' + comment)
        rows = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]s32 = [%s]' % (name, len(vals), (',\n    ').join(rows)))
    arr('GA_MU_INST', tables['inst'], 'per instrument: mode (1 struck, 2 sustained, 3 one-shot), attack per frame, '
        'decay and release per frame (x65536), volume, reverb send, tremolo depth (x256), tremolo rate, '
        'note map start, lowest note, highest note, 0', 12)
    arr('GA_MU_NMAP', tables['nmap'], 'note map: sample | octaves up << 16, or -1')
    arr('GA_MU_SAMP', tables['samp'], 'per sample: byte offset in the bank, length, loop start, frames before '
        'the loop (struck)', 8)
    arr('GA_MU_TRACK', tables['track'], 'per track: first slot, slots', 8)
    arr('GA_MU_SLOT', tables['slot'], 'per slot: first section, sections (variants)', 16)
    arr('GA_MU_SEC', tables['sec'], 'per section: first event, events, length (ticks)', 15)
    arr('GA_MU_EV', tables['ev'], 'per event: tick | duration << 16 (ticks, 0: none), '
        'inst | note << 4 | velocity << 11 | pan << 18', 16)
    with open(os.path.join(HERE, 'music_data.akr'), 'w') as f:
        f.write('\n'.join(L) + '\n')


def main():
    preview = None
    if len(sys.argv) > 2 and sys.argv[1] == '--preview':
        preview = sys.argv[2]
        os.makedirs(preview, exist_ok=True)
    st, tables, bank, sizes = build(preview)
    write(st, tables, bank)
    print('music.adp: %d bytes (%s); %d events' % (len(bank), ', '.join('%s %d' % kv for kv in sizes.items()),
                                                   len(tables['ev']) // 2))


if __name__ == '__main__':
    main()
