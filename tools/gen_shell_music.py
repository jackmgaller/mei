#!/usr/bin/env python3
"""The shell's ambient music (system/shell/music.akr): instrument samples, a score and the
tables the music engine reads.

Crystal: quartal pad chords planing over a sub bass, a glass-bell arpeggio with echoes and high
sparkles in a long space reverb (PS2 browser / PSP XMB). Day and night have their own score
(sky_day picks one at each section boundary); night is slower, darker and wetter. All
harmony stays inside the A major scale (A B C# D E F# G#), which contains the UI sounds'
A major pentatonic.

Samples are 4-bit ADPCM, rendered at the exact pitch they play (pitch 1.0, or 2.0 for an
octave up: the console resamples by nearest sample, so any other ratio would add grit).
Sustained sounds are loops of a whole number of cycles (tuned to within a cent by the loop
length); struck sounds are an attack that decays into such a loop, and the engine continues
the decay with VOL. The 'chorus' of the pads is built into the loop: each harmonic has quiet
partners a whole number of cycles per loop away, so every pass is identical.

Writes system/shell/mu_crystal.adp (the sample bank) and system/shell/mu_data.akr.
    python3 tools/gen_shell_music.py [--preview DIR]   (DIR: a WAV of every sample)
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mei_adpcm

SR = 22050
FRAME = SR / 60.0
LEAD = 56                 # samples before a sustained loop (see looped)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'system', 'shell')

A_MAJOR = {9, 11, 1, 2, 4, 6, 8}


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


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


def struck(f0, partials, attack_s, tail_tau, cutoff, noise=None, seed=0, att_ms=3.0, loop_s=(0.05, 0.14)):
    """A struck tone that decays into a loop.

    partials: (ratio, amp, tau, persist). Persisting partials must be whole harmonics; they
    decay with their tau until the loop starts and stay level after it (the engine carries on
    the decay). The others fade to nothing just before the loop. Returns (x, loop_start)."""
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
    return x, ls


def looped(f0, loop_s, harm, cutoff, chorus, seed=0):
    """A sustained loop. harm(k, f) gives harmonic k's amplitude; chorus(k, rng) gives
    [(cycle offset, weight)] for harmonic k (offset 0 is the harmonic itself).
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
            for d, wgt in chorus(k, rng):
                ph = rng.uniform(0, 2 * np.pi)
                x += a * wgt * np.sin(2 * np.pi * (k * c + d) * n / L + ph)
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


# ------------------------------------------------------------------ the score

def crystal():
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
    return dict(insts=insts, tracks=tracks, reverb=4, wet=(210, 250), tempo=(1.0, 0.75))


# ------------------------------------------------------------------ build

def check_scores(st):
    """Collects the notes each instrument needs and checks the music stays in A major."""
    for tr in st['tracks']:
        for mood in ('day', 'night'):
            for slot in tr[mood]:
                for sec in slot:
                    for (t, inst, note, vel, pan, dur) in sec.ev:
                        assert note % 12 in A_MAJOR, note
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
    tables = dict(inst=[], nmap=[], samp=[], track=[], slot=[], sec=[], ev=[])
    st = crystal()
    check_scores(st)
    bank = bytearray()
    sample_bytes = {}
    for inst in st['insts']:
        nmap, maxshift = plan_samples(inst)
        rendered = {}
        for src in sorted(maxshift):
            rendered[src] = inst.render(src, maxshift[src])
        # struck notes are levelled by their peak (an even keyboard), sustained ones share
        # one gain per instrument, normalised by RMS
        if inst.mode == 2:
            gain = 0.11 / max(np.sqrt(np.mean(x ** 2)) for x, _ in rendered.values())
        sid = {}
        for src, (x, ls) in rendered.items():
            pcm = to_int16(x, 0.42 / np.max(np.abs(x)) if inst.mode == 1 else gain)
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
                mei_adpcm.save_wav(os.path.join(preview, '%s_%d.wav' % (inst.name, src)),
                                   np.round(y * 32767).astype(np.int16))
        print('  %s: %s' % (inst.name, ' '.join('%d%s' % (m, '' if sh == 0 else '^%d' % sh)
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
    report = 'bank %d bytes (%s), %d events' % (
        len(bank), ', '.join('%s %d' % kv for kv in sample_bytes.items()), len(tables['ev']) // 2)
    return st, tables, bytes(bank), report


def write(st, tables, bank):
    with open(os.path.join(OUT, 'mu_crystal.adp'), 'wb') as f:
        f.write(bank)
    L = ['// Generated by tools/gen_shell_music.py - do not edit.',
         '// The shell music\'s samples and score, read by music.akr.', '',
         'embed MU_BANK: u8 = "mu_crystal.adp"', '',
         'const MU_TRACKS = %d' % len(st['tracks']),
         'const MU_REVERB = %d               // preset' % st['reverb'],
         'const MU_WET: [2]s32 = [%d, %d]    // reverb wet level, day and night' % st['wet'],
         'const MU_TEMPO: [2]s32 = [%d, %d]  // ticks x 256 per frame, day and night' % tuple(
             round(256 * t) for t in st['tempo']), '']

    def arr(name, ty, vals, comment, per=16):
        L.append('// ' + comment)
        rows = [', '.join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per)]
        L.append('const %s: [%d]%s = [%s]' % (name, len(vals), ty, (',\n    ').join(rows)))
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
    st, tables, bank, report = build(preview)
    write(st, tables, bank)
    print(report)
    print('tables: %d samples, %d bytes' % (len(tables['samp']) // 4, 4 * sum(len(v) for v in tables.values())))


if __name__ == '__main__':
    main()
