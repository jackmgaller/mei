#!/usr/bin/env python3
"""Differential integration fuzzing for slices, UFCS, bitfields, fixed16 and modules.
Usage: python3 tools/fuzz_language_round.py [count=200] [seed=20261002]
MEIC and RUN select compiler/player builds. Failing inputs remain in the printed directory.
"""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MEIC = os.environ.get("MEIC", str(ROOT / "build/meic"))
RUN = os.environ.get("RUN", str(ROOT / "build/mei-headless"))

MODULE = """struct Cell {
    amount: fixed16,
    flags: bits { a, b, c, d, e, f, g, h, i }
}
fn advance(cell: *Cell, delta: fixed) {
    cell.amount = fixed16(fixed(cell.amount) + delta)
    cell.flags.a = !cell.flags.a
    cell.flags.i = !cell.flags.i
}
"""


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def program(rng):
    n = rng.randint(1, 24)
    raws = [rng.choice([-32768, -1, 0, 1, 32767, rng.randint(-32768, 32767)]) for _ in range(n)]
    deltas = [rng.randint(-32768, 32767) for _ in range(n)]
    flags = [(rng.randrange(2), rng.randrange(2), rng.randrange(2)) for _ in range(n)]
    lines = ['import "cells.akr" as cells', f'var objects: [{n}]cells.Cell',
             f'var values: [{n}]fixed16', f'var output: [{n}]fixed16',
             'fn checksum(xs: []fixed16) -> s32 { return reduce(xs, 0, fn(a, x) => a + bits(x)) }',
             'fn out(x: s32) { print_int(x); print_char(\'\\n\') }', 'fn init() {']
    expected = []
    advanced = []
    for i, (raw, delta, (a, h, last)) in enumerate(zip(raws, deltas, flags)):
        lines.extend([f'    objects[{i}].amount = from_bits16({raw})',
                      f'    objects[{i}].flags.a = {str(bool(a)).lower()}',
                      f'    objects[{i}].flags.h = {str(bool(h)).lower()}',
                      f'    objects[{i}].flags.i = {str(bool(last)).lower()}',
                      f'    (&objects[{i}]).advance(from_bits({delta * 16}))',
                      f'    values[{i}] = objects[{i}].amount',
                      f'    out(bits(values[{i}]))',
                      f'    out(s32(objects[{i}].flags.a) + 2 * s32(objects[{i}].flags.h) + 4 * s32(objects[{i}].flags.i))'])
        v = signed16(raw + delta)
        advanced.append(v)
        expected.extend([v, (1 - a) + 2 * h + 4 * (1 - last)])
    lines.extend(['    let xs: []fixed16 = values', '    out(xs.len())', '    out(xs.checksum())',
                  '    let mapped = map(xs, fn(x) => fixed16(fixed(x) + 0.25), output)',
                  '    out(mapped.len())', '    out(mapped.checksum())',
                  '    let kept = filter(mapped, fn(x) => bits(x) >= 0)',
                  '    out(kept)', '    out(reduce(mapped, 0, fn(a, x) => a + bits(x), kept))', '}'])
    mapped = [signed16(v + 1024) for v in advanced]
    kept = [v for v in mapped if v >= 0]
    expected.extend([n, sum(advanced), n, sum(mapped), len(kept), sum(kept)])
    return '\n'.join(lines) + '\n', ''.join(f'{v}\n' for v in expected)


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261002
    rng = random.Random(seed)
    scratch = Path(tempfile.mkdtemp(prefix='akari-round-'))
    (scratch / 'cells.akr').write_text(MODULE)
    env = dict(os.environ, MEI_STDLIB=str(ROOT / 'stdlib'))
    for i in range(count):
        source, expected = program(rng)
        path = scratch / f'case-{i}.akr'
        image = path.with_suffix('.mei')
        path.write_text(source)
        flags = ['-g'] if i % 2 else []
        result = subprocess.run([MEIC, *flags, str(path), '-o', str(image)], capture_output=True, text=True, env=env, timeout=30)
        if result.returncode:
            print(f'FAIL case {i}, seed {seed}: compile\n{result.stderr}\nInputs: {scratch}')
            return 1
        result = subprocess.run([RUN, str(image), '--frames', '2'], capture_output=True, text=True, timeout=30)
        if result.returncode or result.stdout != expected:
            (scratch / f'case-{i}.expected').write_text(expected)
            print(f'FAIL case {i}, seed {seed}: exit {result.returncode}\nexpected:\n{expected}got:\n{result.stdout}\n{result.stderr}\nInputs: {scratch}')
            return 1
        path.unlink()
        image.unlink()
    (scratch / 'cells.akr').unlink()
    scratch.rmdir()
    print(f'language round: {count} programs, 0 failures (seed {seed}; release/debug alternated)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
