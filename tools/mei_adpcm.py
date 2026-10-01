#!/usr/bin/env python3
"""Mei ADPCM: encoder, reference decoder and a quality report.

Format (docs/DECISIONS.md, "Audio upgrade"): 16-byte blocks of 28 samples.
  byte 0      header: bits 0-3 shift (0-12; 13-15 act as 9), bits 4-7 filter (0-4; 5-15 predict 0)
  byte 1      reserved, written as 0, ignored by the console
  bytes 2-15  28 signed 4-bit nibbles, low nibble first
Decoding sample n with history h1 (previous sample) and h2 (the one before):
  s = nibble * 2^(12 - shift) + floor((h1*K0[f] + h2*K1[f] + 32) / 64), clamped to int16
with the PS1 SPU coefficients K0 = 0, 60, 115, 98, 122 and K1 = 0, 0, -52, -55, -60.

As a module:
  encode(samples, loop_start=None, noise_shaping=0.0) -> bytes
  decode(data, count=None) -> np.int16 array
  load_wav(path, rate=22050, channel='mix') -> np.int16 array

Command line:
  mei_adpcm.py encode in.wav -o out.adp [--loop N] [--noise-shaping 0.5] [--channel mix|left|right]
  mei_adpcm.py decode in.adp -o out.wav [--count N]
  mei_adpcm.py report           SNR on test signals against 8-bit PCM at the same byte budget

The .adp file is the raw blocks, ready for `embed NAME: u8 = "out.adp"`; play it with
`play_adpcm(ch, NAME, samples, ...)`, where samples is printed by `encode` (len(NAME) / 16 * 28
plays the padding at the end of the last block too, which is silence).

Loops: make the loop start and the loop length whole numbers of 28-sample blocks (a loop that
ends inside a block shares that block with the silent padding, which coarsens it and clicks on
every pass), and start a looped sound with a lead-in of a block or two of the same waveform
rather than looping from sample 0 (the loop's first block is then entered with the same history
from the lead-in as from the loop's end; from sample 0 it is also entered from silence, which
forces a coarse block and a click every pass). tools/gen_shell_music.py follows both rules.
"""
import argparse, math, sys, wave
import numpy as np

SR = 22050
BLOCK_SAMPLES = 28
BLOCK_BYTES = 16
K0 = (0, 60, 115, 98, 122) + (0,) * 11
K1 = (0, 0, -52, -55, -60) + (0,) * 11


# ------------------------------------------------------------------ reference decoder

def decode_sample(header, nibble, h1, h2):
    """One decode step, written straight from the format definition. Returns the sample."""
    shift = header & 15
    if shift > 12:
        shift = 9
    f = header >> 4
    t = nibble - 16 if nibble & 8 else nibble
    s = t * (1 << (12 - shift)) + ((h1 * K0[f] + h2 * K1[f] + 32) >> 6)   # Python >> floors
    return max(-32768, min(32767, s))


def decode(data, count=None, h1=0, h2=0):
    """Decodes blocks to int16 samples (all of them, or the first `count`)."""
    nblocks = len(data) // BLOCK_BYTES
    if count is None:
        count = nblocks * BLOCK_SAMPLES
    out = np.zeros(count, dtype=np.int16)
    for n in range(count):
        b = (n // BLOCK_SAMPLES) * BLOCK_BYTES
        j = n % BLOCK_SAMPLES
        byte = data[b + 2 + j // 2]
        s = decode_sample(data[b], (byte >> 4) if j & 1 else (byte & 15), h1, h2)
        h2, h1 = h1, s
        out[n] = s
    return out


# ------------------------------------------------------------------ encoder

def _encode_block(x, h1, h2, filters, ns, e1):
    """Closed-loop search over (filter, shift) for one block of 28 int samples.
    Returns (header, nibbles, h1, h2, e1)."""
    cands = []
    for f in filters:
        # open-loop residual against the true signal sets the starting shift
        p1, p2 = h1, h2
        peak = 0
        for v in x:
            r = v - ((p1 * K0[f] + p2 * K1[f] + 32) >> 6)
            peak = max(peak, abs(r))
            p2, p1 = p1, v
        need = 12 - max(0, math.ceil(math.log2(max(peak, 1) / 7.0)))
        for s in range(need - 2, need + 2):
            if 0 <= s <= 12:
                cands.append((f, s))
    C = len(cands)
    fs = np.array([c[0] for c in cands])
    k0 = np.array([K0[f] for f in fs], dtype=np.int64)
    k1 = np.array([K1[f] for f in fs], dtype=np.int64)
    step = np.array([1 << (12 - c[1]) for c in cands], dtype=np.int64)
    a1 = np.full(C, h1, dtype=np.int64)
    a2 = np.full(C, h2, dtype=np.int64)
    ee = np.full(C, e1, dtype=np.float64)
    err = np.zeros(C)
    nib = np.zeros((C, BLOCK_SAMPLES), dtype=np.int64)
    for i, v in enumerate(x):
        pred = (a1 * k0 + a2 * k1 + 32) >> 6
        target = v - ns * ee
        q = np.clip(np.rint((target - pred) / step), -8, 7).astype(np.int64)
        y = np.clip(q * step + pred, -32768, 32767)
        ee = y - target
        err += (y - v) ** 2
        nib[:, i] = q
        a2, a1 = a1, y
    b = int(np.argmin(err))
    f, s = cands[b]
    return (f << 4) | s, nib[b], int(a1[b]), int(a2[b]), float(ee[b])


def _encode_block_joint(x, hists):
    """One block that must decode well from several entry histories (a loop start, entered
    from the intro and from the loop's end): the summed error over all of them is minimised,
    nibble by nibble. Returns (header, nibbles, [end history per entry])."""
    cands = set()
    for h1, h2 in hists:
        for f in range(5):
            p1, p2, peak = h1, h2, 0
            for v in x:
                peak = max(peak, abs(v - ((p1 * K0[f] + p2 * K1[f] + 32) >> 6)))
                p2, p1 = p1, v
            need = 12 - max(0, math.ceil(math.log2(max(peak, 1) / 7.0)))
            cands.update((f, s) for s in range(need - 2, need + 2) if 0 <= s <= 12)
    cands = sorted(cands)
    C, H = len(cands), len(hists)
    k0 = np.array([K0[f] for f, _ in cands], dtype=np.int64)[:, None, None]
    k1 = np.array([K1[f] for f, _ in cands], dtype=np.int64)[:, None, None]
    step = np.array([1 << (12 - s) for _, s in cands], dtype=np.int64)[:, None, None]
    a1 = np.array([h[0] for h in hists], dtype=np.int64)[None, :].repeat(C, 0)
    a2 = np.array([h[1] for h in hists], dtype=np.int64)[None, :].repeat(C, 0)
    qs = np.arange(-8, 8, dtype=np.int64)[None, None, :]
    err = np.zeros(C)
    nib = np.zeros((C, BLOCK_SAMPLES), dtype=np.int64)
    rows = np.arange(C)
    for i, v in enumerate(x):
        pred = (a1[:, :, None] * k0 + a2[:, :, None] * k1 + 32) >> 6
        y = np.clip(qs * step + pred, -32768, 32767)            # (C, H, 16)
        e = ((y - v) ** 2).sum(axis=1)                          # (C, 16)
        q = np.argmin(e, axis=1)
        err += e[rows, q]
        nib[:, i] = q - 8
        a2, a1 = a1, y[rows, :, q]
    b = int(np.argmin(err))
    f, s = cands[b]
    return (f << 4) | s, nib[b], [(int(a1[b, k]), int(a2[b, k])) for k in range(H)]


def _pack(header, nib):
    out = bytearray([header, 0])
    for j in range(0, BLOCK_SAMPLES, 2):
        out.append((int(nib[j]) & 15) | ((int(nib[j + 1]) & 15) << 4))
    return out


def _encode_blocks(x, b0, b1, h1, h2, ns, first_filters=None):
    out = bytearray()
    e1 = 0.0
    for b in range(b0, b1):
        blk = [int(v) for v in x[b * BLOCK_SAMPLES:(b + 1) * BLOCK_SAMPLES]]
        filters = first_filters if (b == b0 and first_filters) else (0, 1, 2, 3, 4)
        header, nib, h1, h2, e1 = _encode_block(blk, h1, h2, filters, ns, e1)
        out += _pack(header, nib)
    return out, h1, h2


def encode(samples, loop_start=None, noise_shaping=0.0):
    """Encodes int16 samples (any int array) to Mei ADPCM blocks; the last block is padded
    with silence. Play it with LEN = len(samples).

    With loop_start the console wraps from sample LEN - 1 to loop_start and keeps its
    history, so the loop's first block is entered with two different histories: the intro's
    (first pass) and the loop end's (every later pass). That block is encoded to minimise the
    error from both, and the rest of the loop for the wrap; the loop end's history is found by
    encoding, decoding and encoding again until it no longer changes, so every pass after the
    first decodes identically (a very short loop may not settle exactly; it then stays close). A loop_start that is not a multiple of 28 falls back to filter
    0 (no prediction) for its block, which is exact for both entries but coarser."""
    x = np.clip(np.asarray(samples, dtype=np.int64), -32768, 32767)
    n = len(x)
    nblocks = max(1, -(-n // BLOCK_SAMPLES))
    x = np.concatenate([x, np.zeros(nblocks * BLOCK_SAMPLES - n, dtype=np.int64)])
    ns = noise_shaping
    if loop_start is None or not 0 <= loop_start < n:
        return bytes(_encode_blocks(x, 0, nblocks, 0, 0, ns)[0])
    lb = loop_start // BLOCK_SAMPLES
    intro, h1, h2 = _encode_blocks(x, 0, lb, 0, 0, ns)
    if loop_start % BLOCK_SAMPLES:
        return bytes(intro + _encode_blocks(x, lb, nblocks, h1, h2, ns, (0,))[0])
    guess, best = (h1, h2), None
    blk = [int(v) for v in x[lb * BLOCK_SAMPLES:(lb + 1) * BLOCK_SAMPLES]]
    for _ in range(12):
        header, nib, ends = _encode_block_joint(blk, [(h1, h2), guess])
        sec = _pack(header, nib) + _encode_blocks(x, lb + 1, nblocks, ends[1][0], ends[1][1], ns)[0]
        dec = decode(bytes(sec), n - loop_start, guess[0], guess[1])
        end = (int(dec[-1]), int(dec[-2] if len(dec) > 1 else guess[0]))
        miss = abs(end[0] - guess[0]) + abs(end[1] - guess[1])
        if best is None or miss < best[0]:
            best = (miss, sec)
        if miss == 0:
            break
        guess = end
    return bytes(intro + best[1])


# ------------------------------------------------------------------ WAV helpers

def load_wav(path, rate=SR, channel='mix'):
    with wave.open(path, 'rb') as w:
        nch, width, fr, nfr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nfr)
    if width == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) * 256
    elif width == 2:
        a = np.frombuffer(raw, dtype='<i2').astype(np.float64)
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        a = ((b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)) << 8 >> 8).astype(np.float64) / 256
    elif width == 4:
        a = np.frombuffer(raw, dtype='<i4').astype(np.float64) / 65536
    else:
        raise ValueError(f'{path}: unsupported sample width {width}')
    a = a.reshape(-1, nch)
    a = a.mean(axis=1) if channel == 'mix' else a[:, 0 if channel == 'left' or nch == 1 else 1]
    if fr != rate:
        from scipy import signal
        g = math.gcd(fr, rate)
        a = signal.resample_poly(a, rate // g, fr // g)
    return np.clip(np.rint(a), -32768, 32767).astype(np.int16)


def save_wav(path, samples, rate=SR):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.asarray(samples, dtype='<i2').tobytes())


# ------------------------------------------------------------------ quality report

def test_signals(seconds=4.0, seed=1):
    """Music-like, speech-like, noise and a sine sweep, peaking near -1 dBFS."""
    from scipy import signal
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    sig = {}

    m = np.zeros(n)                       # chords, bass, hats and kicks at 120 BPM
    chords = [(220, 277.2, 329.6), (196, 246.9, 293.7), (174.6, 220, 261.6), (196, 246.9, 311.1)]
    for i in range(int(seconds * 2)):
        t0 = i * 0.5
        i0 = int(t0 * SR)
        tt = t[:n - i0]
        env = np.exp(-tt / 0.6) * np.clip(tt / 0.01, 0, 1)
        for f in chords[(i // 2) % 4]:
            for h in range(1, 6):
                m[i0:] += 0.08 / h * np.sin(2 * np.pi * f * h * tt) * env
        m[i0:] += 0.25 * np.sin(2 * np.pi * chords[(i // 2) % 4][0] / 2 * tt) * np.exp(-tt / 0.3)
        k = np.sin(2 * np.pi * (50 + 120 * np.exp(-tt / 0.03)) * tt) * np.exp(-tt / 0.15)
        if i % 2 == 0:
            m[i0:] += 0.5 * k
        hat = rng.standard_normal(min(1500, n - i0)) * np.exp(-np.arange(min(1500, n - i0)) / 200)
        b, a = signal.butter(2, 6000 / (SR / 2), 'high')
        m[i0:i0 + len(hat)] += 0.15 * signal.lfilter(b, a, hat)
    sig['music'] = m

    f0 = 120 + 40 * np.sin(2 * np.pi * 0.7 * t) + 15 * np.sin(2 * np.pi * 3.1 * t)   # speech-like
    ph = np.cumsum(f0) / SR
    pulses = np.diff(np.floor(ph), prepend=0) * 1.0
    voiced = signal.lfilter([1], [1, -0.97], pulses)
    formants = [((730, 1090, 2440), (800, 1150, 2500)), ((270, 2290, 3010), (300, 2200, 3000)),
                ((570, 840, 2410), (500, 900, 2400)), ((440, 1020, 2240), (400, 1100, 2300))]
    sp = np.zeros(n)
    seg = int(0.25 * SR)
    for s0 in range(0, n, seg):
        F = formants[(s0 // seg) % 4][0]
        x = voiced[s0:s0 + seg]
        y = np.zeros_like(x)
        for fc, g in zip(F, (1.0, 0.5, 0.25)):
            r = math.exp(-math.pi * 80 / SR)
            y += g * signal.lfilter([1 - r], [1, -2 * r * math.cos(2 * math.pi * fc / SR), r * r], x)
        if (s0 // seg) % 5 == 4:          # fricative
            b, a = signal.butter(2, [2500 / (SR / 2), 7000 / (SR / 2)], 'band')
            y = 0.3 * signal.lfilter(b, a, rng.standard_normal(len(x)))
        if (s0 // seg) % 7 == 6:          # pause
            y *= 0.02
        w = np.clip(np.arange(len(x)) / 300, 0, 1) * np.clip((len(x) - np.arange(len(x))) / 300, 0, 1)
        sp[s0:s0 + seg] = y * w
    sig['speech'] = sp
    sig['noise'] = rng.standard_normal(n) * 0.25
    f1, f2 = 50, 10000
    sig['sweep'] = np.sin(2 * np.pi * f1 * seconds / math.log(f2 / f1) * (np.exp(t / seconds * math.log(f2 / f1)) - 1))
    for k in sig:
        sig[k] = np.rint(sig[k] / max(np.abs(sig[k]).max(), 1e-9) * 0.89 * 32767).astype(np.int64)
    return sig


def console_pcm8(x, rate):
    """8-bit PCM stored at `rate` and played the way the console does: pitch = rate/22050 as
    16.16, nearest sample, 8-bit samples shifted left 8."""
    from scipy import signal
    g = math.gcd(rate, SR)
    y = signal.resample_poly(x.astype(np.float64), rate // g, SR // g) if rate != SR else x.astype(np.float64)
    q = np.clip(np.rint(y / 256), -128, 127).astype(np.int64)
    pitch = round(rate * 65536 / SR)
    idx = (np.arange(len(x), dtype=np.int64) * pitch) >> 16
    idx = np.minimum(idx, len(q) - 1)
    return q[idx] * 256


def snr(x, y):
    x = x.astype(np.float64); y = y.astype(np.float64)
    return 10 * math.log10(np.sum(x ** 2) / max(np.sum((x - y) ** 2), 1e-9))


def seg_snr(x, y, win=441):
    x = x.astype(np.float64); y = y.astype(np.float64)
    vals = []
    for i in range(0, len(x) - win, win):
        sx = np.sum(x[i:i + win] ** 2)
        if sx < win * 100 ** 2:          # skip near-silent frames
            continue
        se = np.sum((x[i:i + win] - y[i:i + win]) ** 2)
        vals.append(min(60.0, max(-10.0, 10 * math.log10(sx / max(se, 1e-9)))))
    return float(np.mean(vals)) if vals else float('nan')


def report(seconds=4.0):
    same_rate = SR * BLOCK_BYTES // BLOCK_SAMPLES     # 12,600 bytes/s
    print(f"Mei ADPCM: {BLOCK_BYTES} bytes per {BLOCK_SAMPLES} samples = {8 * BLOCK_BYTES / BLOCK_SAMPLES:.3f} bits/sample, "
          f"{same_rate} bytes/s at 22,050 Hz ({2 * BLOCK_SAMPLES / BLOCK_BYTES:.2f}:1 vs 16-bit, "
          f"{BLOCK_SAMPLES / BLOCK_BYTES:.2f}:1 vs 8-bit)")
    print(f"8-bit PCM at the same byte budget is {same_rate} Hz (pitch {same_rate}/{SR}), "
          f"played by nearest sample as the console does.\n")
    print(f"{'signal':8s} | {'ADPCM':>13s} | {'ADPCM+NS0.5':>13s} | {'PCM8 12.6k':>13s} | {'PCM8 22k (1.75x)':>16s}")
    print(f"{'':8s} | {'SNR / segSNR':>13s} | {'SNR / segSNR':>13s} | {'SNR / segSNR':>13s} | {'SNR / segSNR':>16s}")
    rows = {}
    for name, x in test_signals(seconds).items():
        a = decode(encode(x), len(x))
        ns = decode(encode(x, noise_shaping=0.5), len(x))
        p1 = console_pcm8(x, same_rate)
        p2 = console_pcm8(x, SR)
        r = [(snr(x, y), seg_snr(x, y)) for y in (a, ns, p1, p2)]
        rows[name] = r
        cells = ' | '.join(f"{s:5.1f} / {g:5.1f}".rjust(13 if i < 3 else 16) for i, (s, g) in enumerate(r))
        print(f"{name:8s} | {cells}")
    return rows


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description='Mei ADPCM encoder/decoder')
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('encode', help='WAV (or raw s16le with --raw) to Mei ADPCM blocks')
    e.add_argument('input')
    e.add_argument('-o', '--output', required=True)
    e.add_argument('--loop', type=int, default=None, help='loop start sample (best a multiple of 28)')
    e.add_argument('--noise-shaping', type=float, default=0.0, help='error feedback 0..1 (0: off)')
    e.add_argument('--channel', choices=['mix', 'left', 'right'], default='mix')
    e.add_argument('--raw', action='store_true', help='input is raw signed 16-bit little-endian mono at 22,050 Hz')
    e.add_argument('--check', action='store_true', help='decode again and print the SNR')
    d = sub.add_parser('decode', help='Mei ADPCM blocks to a 22,050 Hz WAV')
    d.add_argument('input')
    d.add_argument('-o', '--output', required=True)
    d.add_argument('--count', type=int, default=None, help='samples to decode (default: all blocks)')
    r = sub.add_parser('report', help='SNR on test signals vs 8-bit PCM at the same byte budget')
    r.add_argument('--seconds', type=float, default=4.0)
    a = ap.parse_args(argv)
    if a.cmd == 'encode':
        x = np.fromfile(a.input, dtype='<i2') if a.raw else load_wav(a.input, channel=a.channel)
        data = encode(x, a.loop, a.noise_shaping)
        open(a.output, 'wb').write(data)
        print(f"{a.output}: {len(x)} samples, {len(data)} bytes ({len(data) // BLOCK_BYTES} blocks)")
        if a.check:
            print(f"SNR {snr(x, decode(data, len(x))):.1f} dB")
    elif a.cmd == 'decode':
        data = open(a.input, 'rb').read()
        save_wav(a.output, decode(data, a.count))
    else:
        report(a.seconds)


if __name__ == '__main__':
    main()
