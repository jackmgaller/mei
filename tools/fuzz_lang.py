#!/usr/bin/env python3
"""Differential fuzzer for meic: random programs of s32/u32/fixed expressions, locals,
helper calls and loops, evaluated here with the CPU's exact semantics and compared with
the compiled cart's debug output.  Usage: python3 tools/fuzz_lang.py [count] [seed]"""
import os, random, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEIC = os.environ.get('MEIC') or os.path.join(ROOT, 'build', 'meic')
RUN = os.environ.get('RUN') or os.path.join(ROOT, 'build', 'mei-headless')
M32 = 0xFFFFFFFF

def s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v

def u32(v):
    return v & M32

def tdiv(a, b):  # truncating division with the CPU's rules
    if b == 0: return 0
    if a == -2147483648 and b == -1: return a
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q

def trem(a, b):
    if b == 0: return 0
    if a == -2147483648 and b == -1: return 0
    return a - tdiv(a, b) * b

def fmul(a, b): return s32((a * b) >> 16)
def fdiv(a, b):
    if b == 0: return 0
    q = abs(a << 16) // abs(b)
    q = q if (a < 0) == (b < 0) else -q
    return s32(q)

class Gen:
    def __init__(self, rng, calls=True):
        self.r = rng
        self.depth = 0
        self.closures = {}   # name -> (multiplier, captured values): fn(q) => h_s(q) * K + c1 - c2 ...
        self.calls = calls

    def lit(self, ty):
        r = self.r
        if ty == 'fixed':
            v = r.choice([0, 65536, 32768, -98304, r.randint(-5 << 16, 5 << 16), r.randint(-300, 300)])
            whole, frac = divmod(abs(v), 65536)
            # print as a decimal literal that rounds back to v exactly
            txt = '%d.%s' % (whole, ('%.6f' % (frac / 65536))[2:])
            from fractions import Fraction
            back = int(Fraction(txt) * 65536 + Fraction(1, 2))
            if back != abs(v):
                v = back if v >= 0 else -back
            return 'fixed(%s%s)' % ('-' if v < 0 else '', txt), v
        v = r.choice([0, 1, 2, 3, 7, 8, 16, 31, 100, 255, 1000, 65535, 131071, 131072, 0x7FFFFFFF,
                      r.randint(-200, 200), r.randint(-70000, 70000), r.randint(-(1 << 31), (1 << 31) - 1)])
        if ty == 'u32':
            v = u32(v)
            return 'u32(%d)' % v, v
        return 's32(%d)' % s32(v), s32(v)

    def expr(self, env, ty, depth=0):
        r = self.r
        names = [n for n, t in env.items() if t == ty]
        if depth > 3 or r.random() < 0.25:
            if names and r.random() < 0.7:
                n = r.choice(names)
                return n, ('var', n)
            t, v = self.lit(ty)
            return t, ('lit', v)
        k = r.random()
        if k < 0.12 and ty != 'fixed':
            a = self.expr(env, ty, depth + 1)
            return '(-%s)' % a[0], ('neg', a[1], ty)
        if k < 0.2 and self.calls:
            a = self.expr(env, ty, depth + 1)
            fn = {'s32': 'h_s', 'u32': 'h_u', 'fixed': 'h_f'}[ty]
            how = r.random()
            if how < 0.3: src = 'v_%s(%s)' % (fn, a[0])          # through a function value (callr)
            elif how < 0.45 and ty == 's32': src = 'fn(q: s32) => h_s(q)'.join(['(', ')']) + '(%s)' % a[0]
            elif how < 0.7 and ty == 's32' and names:
                # a capturing literal, called at once or through apply_s (captures copied now)
                caps = [r.choice(names) for _ in range(r.randint(1, 3))]
                body = 'h_s(q)' + ''.join(' + ' + c for c in caps)
                lit = 'fn(q: s32) => %s' % body
                src = ('apply_s(%s, %s)' if r.random() < 0.5 else '(%s)(%s)') % (lit, a[0])
                return src, ('capcall', a[1], tuple(('var', c) for c in caps))
            elif how < 0.85 and ty == 's32' and self.closures:
                n = r.choice(list(self.closures))
                return '%s(%s)' % (n, a[0]), ('closure', n, a[1])
            else: src = '%s(%s)' % (fn, a[0])
            return src, ('call', fn, a[1])
        if k < 0.27 and self.calls:
            c = self.cond(env, depth + 1)
            a = self.expr(env, ty, depth + 1)
            b = self.expr(env, ty, depth + 1)
            fn = {'s32': 'sel_s', 'u32': 'sel_u', 'fixed': 'sel_f'}[ty]
            return '%s(%s, %s, %s)' % (fn, c[0], a[0], b[0]), ('sel', c[1], a[1], b[1])
        if k < 0.33 and ty != 'u32':
            a = self.expr(env, ty, depth + 1)
            b = self.expr(env, ty, depth + 1)
            f = r.choice(['min', 'max'])
            return '%s(%s, %s)' % (f, a[0], b[0]), (f, a[1], b[1])
        if ty == 'fixed':
            op = r.choice(['+', '-', '*', '/', '*i', '/i'])
            a = self.expr(env, ty, depth + 1)
            if op in ('*i', '/i'):
                b = self.expr(env, 's32', depth + 1)
                if op == '/i' and is_const(b[1]) and ev(b[1], {}) == 0:
                    b = ('s32(3)', ('lit', 3))
                return '(%s %s %s)' % (a[0], op[0], b[0]), ('f' + op, a[1], b[1])
            b = self.expr(env, ty, depth + 1)
            if op == '/' and is_const(b[1]) and ev(b[1], {}) == 0:
                b = ('fixed(1.5)', ('lit', 98304))
            return '(%s %s %s)' % (a[0], op, b[0]), ('f' + op, a[1], b[1])
        op = r.choice(['+', '-', '*', '/', '%', '&', '|', '^', '<<', '>>'])
        a = self.expr(env, ty, depth + 1)
        if op in ('<<', '>>'):
            sh = r.randint(0, 31)
            return '(%s %s %d)' % (a[0], op, sh), (ty + op, a[1], ('lit', sh))
        b = self.expr(env, ty, depth + 1)
        if op in ('/', '%') and is_const(b[1]) and ev(b[1], {}) == 0:
            b = ('s32(7)' if ty == 's32' else 'u32(7)', ('lit', 7))
        return '(%s %s %s)' % (a[0], op, b[0]), (ty + op, a[1], b[1])

    def cond(self, env, depth=0):
        r = self.r
        if depth < 2 and r.random() < 0.25:
            a = self.cond(env, depth + 1)
            b = self.cond(env, depth + 1)
            op = r.choice(['&&', '||'])
            return '(%s %s %s)' % (a[0], op, b[0]), (op, a[1], b[1])
        ty = r.choice(['s32', 'u32', 'fixed'])
        a = self.expr(env, ty, depth + 2)
        b = self.expr(env, ty, depth + 2)
        op = r.choice(['<', '<=', '>', '>=', '==', '!='])
        return '(%s %s %s)' % (a[0], op, b[0]), ('cmp', op, ty, a[1], b[1])

def is_const(t):
    if t[0] == 'lit': return True
    if t[0] in ('var', 'call', 'capcall', 'closure'): return False
    return all(is_const(x) for x in t[1:] if isinstance(x, tuple))

def ev(t, env):
    k = t[0]
    if k == 'lit': return t[1]
    if k == 'var': return env[t[1]]
    if k == 'neg': return (u32 if t[2] == 'u32' else s32)(-ev(t[1], env))
    if k == 'call':
        v = ev(t[2], env)
        return {'h_s': lambda x: s32(x * 3 + 1), 'h_u': lambda x: u32(x ^ 0x5A5A5A5A), 'h_f': lambda x: s32(x // 2)}[t[1]](v)
    if k == 'capcall':
        v = s32(ev(t[1], env) * 3 + 1)
        for c in t[2]: v = s32(v + ev(c, env))
        return v
    if k == 'closure':
        mul, vals = env['$closures'][t[1]]
        v = s32(s32(ev(t[2], env) * 3 + 1) * mul)
        for c in vals: v = s32(v - c)
        return v
    if k == 'sel': return ev(t[2], env) if ev(t[1], env) else ev(t[3], env)
    if k == 'min': return min(ev(t[1], env), ev(t[2], env))
    if k == 'max': return max(ev(t[1], env), ev(t[2], env))
    if k in ('&&', '||'):
        a = ev(t[1], env)
        if k == '&&': return a and ev(t[2], env)
        return a or ev(t[2], env)
    if k == 'cmp':
        a, b = ev(t[3], env), ev(t[4], env)
        return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b, '==': a == b, '!=': a != b}[t[1]]
    a, b = ev(t[1], env), ev(t[2], env)
    if k.startswith('s32') or k.startswith('u32'):
        ty, op = k[:3], k[3:]
        fix = s32 if ty == 's32' else u32
        if op == '+': return fix(a + b)
        if op == '-': return fix(a - b)
        if op == '*': return fix(a * b)
        if op == '/':
            if ty == 'u32': return 0 if b == 0 else a // b
            return tdiv(a, b)
        if op == '%':
            if ty == 'u32': return 0 if b == 0 else a % b
            return trem(a, b)
        if op == '&': return fix(a & b)
        if op == '|': return fix(a | b)
        if op == '^': return fix(a ^ b)
        if op == '<<': return fix(a << b)
        if op == '>>': return fix(a >> b) if ty == 's32' else (a >> b)
    if k == 'f+': return s32(a + b)
    if k == 'f-': return s32(a - b)
    if k == 'f*': return fmul(a, b)
    if k == 'f/': return fdiv(a, b)
    if k == 'f*i': return s32(a * b)
    if k == 'f/i': return tdiv(a, b)
    raise ValueError(k)

PRELUDE = '''fn h_s(x: s32) -> s32 { return x * 3 + 1 }
fn h_u(x: u32) -> u32 { return x ^ 0x5A5A5A5A }
fn h_f(x: fixed) -> fixed { return from_bits(bits(x) >> 1) }
fn sel_s(c: bool, a: s32, b: s32) -> s32 { if c { return a } return b }
fn sel_u(c: bool, a: u32, b: u32) -> u32 { if c { return a } return b }
fn sel_f(c: bool, a: fixed, b: fixed) -> fixed { if c { return a } return b }
fn out(n: s32) { print_int(n); print_char('\\n') }
fn apply_s(f: fn(s32) -> s32, x: s32) -> s32 { return f(x) }
var v_h_s: fn(s32) -> s32 = h_s
var v_h_u: fn(u32) -> u32 = h_u
var v_h_f: fn(fixed) -> fixed = h_f
'''

def program(rng, nstmts=25):
    leaf = rng.random() < 0.5          # a function without calls, results folded into a checksum
    g = Gen(rng, calls=not leaf)
    env_t, env_v = {}, {'$closures': g.closures}
    lines, expected = [], []
    acc = 0
    addr_taken = set()
    def emit_out(name):
        nonlocal acc
        ty = env_t[name]
        val = name if ty == 's32' else 'bits(%s)' % name if ty == 'fixed' else '%s as s32' % name
        if name in addr_taken and rng.random() < 0.5:
            val = '*p_%s' % name if ty == 's32' else val
        if leaf:
            lines.append('    acc = acc * 31 + %s' % val)
            acc = s32(acc * 31 + s32(env_v[name]))
        else:
            lines.append('    out(%s)' % val)
            expected.append(s32(env_v[name]))
    for i in range(nstmts):
        k = rng.random()
        if k < 0.45 or not env_t:
            ty = rng.choice(['s32', 's32', 'u32', 'fixed'])
            name = 'v%d' % i
            src, tree = g.expr(env_t, ty)
            lines.append('    var %s: %s = %s' % (name, ty, src))
            env_v[name] = ev(tree, env_v)
            env_t[name] = ty
            if ty == 's32' and rng.random() < 0.15:
                lines.append('    let p_%s = &%s' % (name, name))
                addr_taken.add(name)
        elif k < 0.7:
            name = rng.choice(list(env_t))
            ty = env_t[name]
            src, tree = g.expr(env_t, ty)
            if name in addr_taken and rng.random() < 0.5:
                lines.append('    *p_%s = %s' % (name, src))
            else:
                lines.append('    %s = %s' % (name, src))
            env_v[name] = ev(tree, env_v)
        elif k < 0.8:
            name = rng.choice(list(env_t))
            ty = env_t[name]
            c = g.cond(env_t)
            src, tree = g.expr(env_t, ty)
            lines.append('    if %s { %s = %s }' % (c[0], name, src))
            if ev(c[1], env_v):
                env_v[name] = ev(tree, env_v)
        elif k < 0.85 and not leaf and len(g.closures) < 3 and any(t == 's32' for t in env_t.values()):
            # a closure kept in a local and called later: it sees the values at creation
            names = [n for n, t in env_t.items() if t == 's32']
            caps = [rng.choice(names) for _ in range(rng.randint(0, 3))]
            mul = rng.randint(-5, 9)
            name = 'cf%d' % i
            body = '%s(q) * %d' % ('h_s', mul) + ''.join(' - ' + c for c in caps)
            lines.append('    let %s: fn(s32) -> s32 = fn(q) => %s' % (name, body))
            g.closures[name] = (mul, [s32(env_v[c]) for c in caps])
        elif k < 0.9:
            names = [n for n, t in env_t.items() if t == 's32']
            if not names: continue
            name = rng.choice(names)
            n = rng.randint(0, 5)
            src, tree = g.expr(env_t, 's32')
            lines.append('    for j%d in 0..%d { %s = %s + j%d }' % (i, n, name, src, i))
            for j in range(n):
                env_v[name] = s32(ev(tree, env_v) + j)
        name = rng.choice(list(env_t)) if env_t else None
        if name and rng.random() < 0.6:
            emit_out(name)
    if leaf:
        src = PRELUDE + 'fn body() -> s32 {\n    var acc = 0\n' + '\n'.join(lines) + '\n    return acc\n}\nfn init() { out(body()) }\n'
        expected = [acc]
    else:
        src = PRELUDE + 'fn init() {\n' + '\n'.join(lines) + '\n}\n'
    return src, expected

def run_one(seed, tmp):
    rng = random.Random(seed)
    src, expected = program(rng)
    path = os.path.join(tmp, 'f%d.mls' % seed)
    open(path, 'w').write(src)
    cart = path[:-4] + '.mei'
    env = dict(os.environ, MEI_STDLIB=os.path.join(ROOT, 'stdlib'))
    c = subprocess.run([MEIC, path, '-o', cart], capture_output=True, text=True, env=env)
    if c.returncode:
        return 'compile error:\n' + c.stderr, src
    r = subprocess.run([RUN, cart, '--frames', '2'], capture_output=True, text=True)
    got = r.stdout.split()
    want = [str(v) for v in expected]
    if r.returncode or got != want:
        return 'mismatch (exit %d)\nwant %s\ngot  %s' % (r.returncode, want, got), src
    return None, src

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    base = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    tmp = tempfile.mkdtemp(prefix='meifuzz')
    bad = 0
    for s in range(base, base + count):
        err, src = run_one(s, tmp)
        if err:
            bad += 1
            print('seed %d: %s' % (s, err))
            open(os.path.join(tmp, 'fail%d.mls' % s), 'w').write(src)
            if bad >= 5: break
    print('%d programs, %d failures (sources in %s)' % (count, bad, tmp))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
