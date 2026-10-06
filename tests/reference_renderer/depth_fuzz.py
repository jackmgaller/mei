#!/usr/bin/env python3
"""Adversarial frames with depth (docs/RENDERING.md) through Mei's GPU alone, against depth.py.

Each scene is a random VRAM image and a frame of register writes: GPU_CTRL (dither),
GPU_ZCLEAR (0, a far limit, 0xFFFF), GPU_DEPTH on or off, and two packet lists with the test
switched between them. The lists hold every packet kind with depth (0x30-0x3F) twice and four
without, with view depths that make the affine case, steep perspective, reciprocals clamped at
w <= 1/16 (zero and negative), keys of 0 past 4,096 units, the largest w, and q values equal
after scaling though r differs; decal offsets 0-31; overlapping and interpenetrating faces;
positions on screen, partly off it, and across the full signed 16-bit range; texture windows.
The framebuffer, the depth buffer and the eight cycle and statistics counters must all agree.
Each packet is also replayed alone over a cleared or partly filled depth buffer.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
import common
import depth
import oracle


def view_depths(rng, n, style):
    """n 16.16 depth words of one style."""
    if style == 0:                                   # one w: the affine case
        return [int(rng.integers(4096, 1 << 26))] * n
    if style == 1:                                   # steep perspective, 1/8 to 64 units
        return [int(2 ** rng.uniform(13, 22)) for _ in range(n)]
    if style == 2:                                   # clamped: 1/16 or nearer, zero, negative
        return [int(rng.choice([4096, 4095, 1, 0, -1, -(1 << 31), int(rng.integers(4096, 1 << 20))]))
                for _ in range(n)]
    if style == 3:                                   # far: keys of 0 and the largest w
        return [int(rng.choice([(1 << 28) - 1, 1 << 28, (1 << 31) - 1, int(rng.integers(1 << 27, 1 << 31))]))
                for _ in range(n)]
    if style == 4:                                   # r differs, q equal after scaling
        base = int(rng.integers(4096, 1 << 14))
        return [base + int(rng.integers(0, 3)) for _ in range(n)]
    return [int(rng.integers(4096, 1 << 24)) for _ in range(n)]   # anything in range


def positions(rng, n, category):
    if category == 0:
        return rng.integers(-32768, 32768, (n, 2)).tolist()
    if category == 1:
        return rng.integers([-400, -300], [720, 540], (n, 2)).tolist()
    if category == 2:
        x, y = rng.integers([0, 0], [300, 220]).tolist()
        return [[x, y], [x + 1, y + 1], [x + 2, y + 2], [x + 3, y + 3]][:n]
    if category == 3:                                # a block where the faces overlap
        return rng.integers([40, 30], [280, 210], (n, 2)).tolist()
    return rng.integers([0, 0], [320, 240], (n, 2)).tolist()


def scene(rng, run):
    vram = bytearray(rng.integers(0, 256, 1 << 21, dtype=np.uint8).tobytes())      # 2 MB
    fb = rng.integers(0, 32768, 320 * 240).astype('<u2')
    vram[:320 * 240 * 2] = fb.tobytes()
    packets = []
    for i in range(36):
        kind = i % 16
        has_depth = i < 32
        flags = kind
        n = 4 if flags & 4 else 3
        p = {'flags': flags, 'depth': has_depth, 'blend': int(rng.integers(0, 4)),
             'slot': int(rng.integers(0, 32)), 'four': bool(rng.integers(0, 2)),
             'pal': int(rng.integers(0, 512)), 'pos': positions(rng, n, int(rng.integers(0, 5)) if i % 3 else 3),
             'cols': rng.integers(0, 256, (n, 3)).tolist(), 'uv': rng.integers(0, 256, (n, 2)).tolist(),
             'window': 0, 'decal': 0}
        if not p['four']:
            p['pal'] %= 32                           # 8-bit palettes are 0-31
        if flags & 2 and rng.integers(0, 2):
            p['window'] = int(rng.integers(0, 8)) | int(rng.integers(0, 32)) << 3
            p['window'] |= (int(rng.integers(0, 8)) | int(rng.integers(0, 32)) << 3) << 8
        if has_depth:
            p['w'] = view_depths(rng, n, (i + run) % 6)
            if rng.integers(0, 3) == 0:
                p['decal'] = int(rng.choice([1, 2, 8, 31]))
        packets.append(p)
    order = rng.permutation(len(packets)).tolist()
    packets = [packets[k] for k in order]
    on = run % 4 != 3
    writes = [(depth.GPU_CTRL, run % 2),
              (depth.GPU_ZCLEAR, int(rng.choice([0, 0, 0xFFFF, int(rng.integers(0, 0x10000))]))),
              (depth.GPU_DEPTH, int(on) | (int(rng.integers(0, 1 << 31)) & ~1)),   # bits 1-31 ignored
              (depth.GPU_DRAW, packets[:24]),
              (depth.GPU_DEPTH, int(not on) if run % 3 == 0 else int(on)),
              (depth.GPU_DRAW, packets[24:])]
    return vram, writes, packets


def compare(expected, actual):
    fb, zb, _, stats = expected
    fb2, zb2, _, stats2 = actual
    return {'framebuffer': int((fb != fb2).sum()), 'depth_buffer': int((zb != zb2).sum()),
            'stats': {k: [stats[k], stats2[k]] for k in stats if stats[k] != stats2[k]}}


def bad(result):
    return result['framebuffer'] or result['depth_buffer'] or result['stats']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20261004)
    parser.add_argument('--composed-only', action='store_true', help='Skip isolated packet checks')
    parser.add_argument('--out', type=Path, default=common.OUT / 'depth_fuzz')
    args = parser.parse_args()
    if args.scenes < 1:
        parser.error('--scenes must be positive')
    args.out.mkdir(parents=True, exist_ok=True)
    probe = common.probe('depth_probe').resolve()
    rng = np.random.default_rng(args.seed)
    fixture = args.out / 'current.bin'
    failures = []
    tally = {'scenes': args.scenes, 'seed': args.seed, 'packets': 0, 'triangles': 0,
             'isolated_packets': 0, 'pixel_comparisons': 0, 'px_ztest': 0, 'px_zfail': 0,
             'px_persp': 0, 'persp_divs': 0, 'gpu_cycles': 0}
    for run in range(args.scenes):
        vram, writes, packets = scene(rng, run)
        expected = depth.model(vram, None, writes)
        actual = depth.replay(probe, fixture, vram, None, writes)
        result = compare(expected, actual)
        tally['packets'] += len(packets)
        tally['pixel_comparisons'] += 2 * 76800
        for k in ('px_ztest', 'px_zfail', 'px_persp', 'persp_divs', 'gpu_cycles'):
            tally[k] += expected[3][k]
        tally['triangles'] += expected[3]['tris']
        if bad(result) or run == 0:
            prefix = args.out / f'case_{run:04d}'
            oracle.rgb_image(expected[0]).save(f'{prefix}_reference.png')
            oracle.rgb_image(actual[0]).save(f'{prefix}_mei.png')
            diff = np.zeros((240, 320, 3), dtype=np.uint8)
            diff[expected[0] != actual[0]] = [255, 40, 90]
            diff[(expected[1] != actual[1]) & (expected[0] == actual[0])] = [40, 200, 255]
            Image.fromarray(diff).save(f'{prefix}_diff.png')
            Path(f'{prefix}.bin').write_bytes(fixture.read_bytes())
        if bad(result):
            failures.append({'scene': run, **result})
        if not args.composed_only:
            # Alone, so later packets cannot hide an earlier one: over a cleared buffer with the
            # test on, then over this scene's finished depth buffer as the far limit.
            for i, p in enumerate(packets):
                if not p['depth']:
                    continue
                zclear = 0 if i % 2 else int(expected[1][120, 160])
                one = [(depth.GPU_CTRL, run % 2), (depth.GPU_ZCLEAR, zclear),
                       (depth.GPU_DEPTH, 1 if i % 5 else 0), (depth.GPU_DRAW, [p])]
                r = compare(depth.model(vram, None, one), depth.replay(probe, fixture, vram, None, one))
                tally['isolated_packets'] += 1
                tally['pixel_comparisons'] += 2 * 76800
                if bad(r):
                    failures.append({'scene': run, 'packet': i, 'type': hex(0x30 | p['flags']), **r})
                    Path(args.out / f'case_{run:04d}_packet_{i}.bin').write_bytes(fixture.read_bytes())
                    (args.out / f'case_{run:04d}_packet_{i}.json').write_text(json.dumps(p) + '\n')
        if run % 8 == 7:
            print(f'Compared {run + 1}/{args.scenes} scenes; {len(failures)} mismatches', flush=True)
    # Negative controls: a reference that departs from the spec in one rule must disagree with
    # Mei on these scenes (the composed frames of the first eight).
    controls = {}
    rng = np.random.default_rng(args.seed)
    frames = [scene(rng, run) for run in range(min(8, args.scenes))]
    for mutant in depth.MUTANTS:
        depth.MUTANT = mutant
        try:
            controls[mutant] = sum(
                (lambda r: r['framebuffer'] + r['depth_buffer'] + len(r['stats']))(
                    compare(depth.model(vram, None, writes), depth.replay(probe, fixture, vram, None, writes)))
                for vram, writes, _ in frames)
        finally:
            depth.MUTANT = None
        if not controls[mutant]:
            failures.append({'negative_control': mutant, 'detected': False})
    tally['negative_controls'] = controls
    tally['failures'] = failures
    (args.out / 'report.json').write_text(json.dumps(tally, indent=2) + '\n')
    print(json.dumps(tally), flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
