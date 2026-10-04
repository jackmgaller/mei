"""The Prism Engine's depth buffer and perspective-correct texturing, modelled from
docs/RENDERING.md alone (no emulator code, no unit-test reference), with its cost table.

`Gpu` is the GPU's state: the back framebuffer, the depth buffer, `GPU_CTRL`, `GPU_DEPTH`, the
plane chip's registers, the cycle count and the frame statistics. `Gpu.write(offset, value)` is
a register write (an I/O offset); for `GPU_DRAW` the value is a list of packets (dicts, below)
instead of an address. `golden()` checks the model against RENDERING.md's golden values.
`fixture()` turns the same writes into the input of `depth_probe.c`, which makes them through
Mei's bus, and `replay()` runs it.

A packet is a dict: `flags` (bits 0-3 of the type: Gouraud, textured, quad, semi-transparent),
`depth` (bit 4: one 16.16 view depth per vertex in `w`), `decal` (0-31, the first colour word's
bits 27-31), `upper` (bit 26, the plane chip's layer bit), `blend`, `pos`, `cols`, `uv`, `slot`,
`four`, `pal` and `window`, as in oracle.py.

Pixels are evaluated as oracle.render evaluates them: exact barycentric weights at every pixel
centre with NumPy, the top-left rule from the three edge functions, rather than a scanline walk.
Spans (for the divides) are each row's first and last covered pixel.
"""
import struct
import subprocess
import numpy as np
import planes_check
from oracle import DM, windowed

W, H = 320, 240
TEXTURE, PALETTE = 0x80000, 0x4C000   # VRAM offsets (DECISIONS.md, the VRAM layout)
GPU_DRAW, GPU_CLEAR, GPU_CTRL, GPU_DEPTH, GPU_ZCLEAR = 0x00, 0x04, 0x08, 0x20, 0x24
TRIANGLE_LIMIT = 4000
# A deliberate departure from the spec, for the negative controls (depth_fuzz.py): None, or
# one of MUTANTS.
MUTANT = None
MUTANTS = ('ties_to_earlier', 'semi_writes_depth', 'divide_every_8', 'late_depth')

# The cost table (RENDERING.md, "Cost"; DECISIONS.md, "GPU budget").
TRI, RECIP, DIVIDE, ZFAIL, CLEAR = 40, 24, 2, 1, 38400
STAT_NAMES = ('gpu_cycles', 'tris', 'px_ztest', 'px_zfail', 'zclears', 'tris_recip', 'px_persp',
              'persp_divs')


def reciprocal(w):
    """The vertex reciprocal: 2^40 / w (16.16) rounded down; 2^28 for w below 1/16."""
    w = w - (1 << 32) if w >= 1 << 31 else w      # the depth word is signed
    return 1 << 28 if w < 4096 else (1 << 40) // w


def key(z):
    """The 16-bit float of inverse depth z (int64 array): 4-bit exponent, 12-bit mantissa."""
    z = np.asarray(z, dtype=np.int64)
    e = np.zeros_like(z)
    for k in range(1, 17):              # e = floor(log2 z) - 12, by comparison
        e += z >= (1 << (12 + k))
    mantissa = (z >> np.minimum(e, 15)) & 0xFFF
    return np.where(z < 4096, 0, np.where(e > 15, 0xFFFF, (e << 12) | mantissa))


def pixel_cost(gouraud, textured, semi):
    del gouraud                          # Gouraud shading costs nothing extra
    return (2 if textured else 1) * (2 if semi else 1)


def divides(n):
    """Divides in a span of n pixels: its first, every 16th after it, its last."""
    return 1 + -(-(n - 1) // 16)


class Gpu:
    def __init__(self, vram=None, regs=None, ctrl=0):
        self.vram = bytearray(vram if vram is not None else bytes(1 << 20))
        self.regs = list(regs) if regs is not None else [0] * 64
        self.texture = np.frombuffer(bytes(self.vram[TEXTURE:TEXTURE + 524288]), dtype=np.uint8)
        self.palette = np.frombuffer(bytes(self.vram[PALETTE:PALETTE + 8192]),
                                     dtype='<u2').astype(np.int64)
        self.fb = np.frombuffer(bytes(self.vram[:W * H * 2]), dtype='<u2').astype(np.int64).reshape(H, W)
        self.zbuf = np.zeros((H, W), dtype=np.int64)
        self.ctrl, self.ztest = ctrl, False
        self.stats = dict.fromkeys(STAT_NAMES, 0)
        self.trace = None       # a list: each textured triangle's (x, y, u, v) before windows

    @property
    def planes_on(self):
        return bool(self.regs[0] & 1)

    def write(self, offset, value):
        if offset == GPU_CTRL:
            self.ctrl = value
        elif offset == GPU_DEPTH:
            self.ztest = bool(value & 1)
        elif offset == GPU_ZCLEAR:
            self.zbuf[:] = value & 0xFFFF
            self.stats['gpu_cycles'] += CLEAR
            self.stats['zclears'] += 1
        elif offset == GPU_CLEAR:
            self.fb[:] = value & (0xFFFF if self.planes_on else 0x7FFF)
            self.stats['gpu_cycles'] += CLEAR
        elif offset == GPU_DRAW:
            for packet in value:
                self.packet(packet)
        elif 0x700 <= offset < 0x800 and offset % 4 == 0:      # the plane chip's registers
            self.regs[(offset - 0x700) // 4] = value
        else:
            raise ValueError(f'not a GPU register: {offset:#x}')

    def packet(self, p):
        for ids in ([0, 1, 2], [1, 2, 3]) if p['flags'] & 4 else ([0, 1, 2],):
            if self.stats['tris'] >= TRIANGLE_LIMIT:
                raise RuntimeError('the scene is over the triangle limit')
            self.triangle(p, ids)

    def triangle(self, p, ids):
        gouraud, textured, semi = (bool(p['flags'] & b) for b in (1, 2, 8))
        depth = bool(p.get('depth'))
        tested = depth and self.ztest
        st = self.stats
        st['tris'] += 1
        st['gpu_cycles'] += TRI
        if depth and (tested or textured):
            st['gpu_cycles'] += RECIP
            st['tris_recip'] += 1
        v = np.array([p['pos'][i] for i in ids], dtype=np.int64)
        cols = np.array([p['cols'][i if gouraud else 0] for i in ids], dtype=np.int64)
        uv = np.array([p['uv'][i] if textured else [0, 0] for i in ids], dtype=np.int64)
        r = [reciprocal(p['w'][i]) if depth else 0 for i in ids]
        area = int((v[1, 0] - v[0, 0]) * (v[2, 1] - v[0, 1]) - (v[1, 1] - v[0, 1]) * (v[2, 0] - v[0, 0]))
        if area == 0:
            return
        if area < 0:                       # both windings: swap vertices 1 and 2
            area = -area
            for arr in (v, cols, uv):
                arr[[1, 2]] = arr[[2, 1]]
            r[1], r[2] = r[2], r[1]
        low = np.maximum(v.min(axis=0), [0, 0])
        high = np.minimum(v.max(axis=0), [W - 1, H - 1])
        if np.any(low > high):
            return
        yy, xx = np.mgrid[low[1]:high[1] + 1, low[0]:high[0] + 1]

        def edges(x, y):
            """Each vertex's weight: the edge function of the opposite edge."""
            out = []
            for i in range(3):
                a, b = v[(i + 1) % 3], v[(i + 2) % 3]
                out.append((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]))
            return out

        weights = edges(xx, yy)
        inside = np.ones(xx.shape, dtype=bool)
        for i in range(3):
            a, b = v[(i + 1) % 3], v[(i + 2) % 3]
            dx, dy = b - a
            inside &= weights[i] >= 0 if dy < 0 or (dy == 0 and dx > 0) else weights[i] > 0
        if not inside.any():
            return
        y, x = yy[inside], xx[inside]
        e = np.stack([wt[inside] for wt in weights], axis=1)
        n = len(x)

        # Perspective: q_i = r_i scaled to 16 bits; affine when they are equal.
        persp = False
        if depth and textured:
            s = 0
            while max(r) >> s >= 65536:
                s += 1
            q = [max(1, ri >> s) for ri in r]
            persp = len(set(q)) > 1
        if persp:
            row0 = np.zeros(H, dtype=np.int64)          # each row's span, x0 to x1
            row1 = np.zeros(H, dtype=np.int64)
            np.maximum.at(row1, y, x)
            row0[:] = W
            np.minimum.at(row0, y, x)
            x0, x1 = row0[y], row1[y]
            every = 8 if MUTANT == 'divide_every_8' else 16
            a = x0 + (x - x0) // every * every
            b = np.minimum(a + every, x1)
            rows = np.unique(y)
            st['persp_divs'] += int(sum(divides(int(row1[k] - row0[k] + 1)) for k in rows))
            st['px_persp'] += n
            qv = np.array(q, dtype=np.int64)

            def corrected(px):
                """S and T (16.16) at the pixels px of row y: U * 65536 / Q, exactly."""
                wts = np.stack(edges(px, y), axis=1)
                Q = (wts * qv).sum(axis=1).astype(object)
                U = (wts * (qv * uv[:, 0])).sum(axis=1).astype(object)
                V = (wts * (qv * uv[:, 1])).sum(axis=1).astype(object)
                return (np.array(U * 65536 // Q, dtype=np.int64),
                        np.array(V * 65536 // Q, dtype=np.int64))

            sa, ta = corrected(a)
            sb, tb = corrected(b)
            span = np.maximum(b - a, 1)

            def step(fa, fb_):
                d = fb_ - fa
                quotient = np.sign(d) * (np.abs(d) // span)        # trunc toward zero
                return np.where(x == x1, fb_, fa + (x - a) * quotient)
            S, T = step(sa, sb), step(ta, tb)
            u, tv = S >> 16, T >> 16
        else:
            u = (e @ uv[:, 0]) // area
            tv = (e @ uv[:, 1]) // area
        colours = (e @ cols) // area if gouraud else np.tile(cols[0], (n, 1))
        if self.trace is not None and textured:
            self.trace.append((x, y, u, tv))

        # The depth test, before anything else is done for the pixel.
        passed = np.ones(n, dtype=bool)
        if tested:
            z = (e @ np.array(r, dtype=np.int64)) // area
            k = np.minimum(0xFFFF, key(z) + p.get('decal', 0))
            passed = k > self.zbuf[y, x] if MUTANT == 'ties_to_earlier' else k >= self.zbuf[y, x]
            st['px_ztest'] += n
            st['px_zfail'] += int((~passed).sum())
        st['gpu_cycles'] += int(passed.sum()) * pixel_cost(gouraud, textured, semi)
        fail_cost = pixel_cost(gouraud, textured, semi) if MUTANT == 'late_depth' else ZFAIL
        st['gpu_cycles'] += int((~passed).sum()) * fail_cost
        if persp:
            st['gpu_cycles'] += DIVIDE * int(sum(divides(int(row1[k] - row0[k] + 1)) for k in rows))

        keep = passed
        if textured:
            window = p.get('window', 0)
            uu, vv = windowed(u, window), windowed(tv, window >> 8)
            if p['four']:
                idx = (self.texture[(p['slot'] * 32768 + vv * 128 + uu // 2) % 524288] >> (uu % 2 * 4)) & 15
                base = p['pal'] * 16
            else:
                idx = self.texture[(p['slot'] * 32768 + vv * 256 + uu) % 524288]
                base = (p['pal'] & 15) * 256
            keep = keep & (idx != 0)
        y, x, colours = y[keep], x[keep], colours[keep]
        if textured:
            texel = self.palette[base + idx[keep].astype(np.int64)]
            ch = (texel[:, None] >> np.array([0, 5, 10])) & 31
            ch = (ch << 3) | (ch >> 2)
            colours = np.minimum(255, (ch * colours) // 128)
        if self.ctrl & 1:
            colours = np.clip(colours + DM[y % 4, x % 4, None], 0, 255)
        colours = colours >> 3
        upper = bool(p.get('upper')) and self.planes_on
        if semi:
            bg = self.fb[y, x]
            under = (bg[:, None] >> np.array([0, 5, 10])) & 31
            if self.planes_on:      # over a hole, or upper over lower: the layers behind
                for i in np.nonzero((bg == 0x8000) | (upper & ((bg & 0x8000) == 0)))[0]:
                    lr = planes_check.line(self.regs, self.vram, int(y[i]))
                    c = planes_check.stack(self.vram, lr, int(x[i]), int(y[i]), int(bg[i]),
                                           4 if upper else 3)
                    under[i] = [(c >> s) & 31 for s in (0, 5, 10)]
            m = p['blend']
            colours = ((under + colours) // 2 if m == 0 else np.minimum(31, under + colours) if m == 1
                       else np.maximum(0, under - colours) if m == 2 else np.minimum(31, under + colours // 4))
        out = colours @ np.array([1, 32, 1024])
        if upper:
            out = out | 0x8000
            out[out == 0x8000] = 0x8400
        self.fb[y, x] = out
        if tested and (not semi or MUTANT == 'semi_writes_depth'):
            self.zbuf[y, x] = k[keep]

    def display(self):
        """The picture after vsync: the framebuffer, or the plane chip's composite of it."""
        if not self.planes_on:
            return self.fb & 0x7FFF
        v = bytearray(self.vram)
        v[:W * H * 2] = self.fb.astype('<u2').tobytes()
        out = np.empty((H, W), dtype=np.int64)
        for y in range(H):
            lr = planes_check.line(self.regs, v, y)
            for x in range(W):
                out[y, x] = planes_check.stack(v, lr, x, y, int(self.fb[y, x]))
        return out


def words(p):
    """A packet's words after the header, as RENDERING.md lays them out."""
    out = []
    for i, pos in enumerate(p['pos']):
        if i == 0 or p['flags'] & 1:
            c = sum(ch << (8 * k) for k, ch in enumerate(p['cols'][i]))
            if i == 0:
                c |= p['blend'] << 24 | int(bool(p.get('upper'))) << 26 | p.get('decal', 0) << 27
            out.append(c)
        out.append((pos[0] & 0xFFFF) | (pos[1] & 0xFFFF) << 16)
        if p['flags'] & 2:
            t = p['uv'][i][0] | p['uv'][i][1] << 8
            if i == 0:
                t |= p['slot'] << 16 | int(p['four']) << 20 | p['pal'] << 24
            if i == 1:
                t |= p.get('window', 0) << 16
            out.append(t)
    if p.get('depth'):
        out.extend(w & 0xFFFFFFFF for w in p['w'])
    return out


def fixture(vram, regs, writes):
    """depth_probe.c's input for these register writes (GPU_DRAW with a list of packets)."""
    ram, pairs, address = [], [], 0x1000
    for offset, value in writes:
        if offset != GPU_DRAW:
            pairs.append((offset, value))
            continue
        if not value:
            pairs.append((offset, 0xFFFFFF))
            continue
        pairs.append((offset, address))
        for i, p in enumerate(value):
            body = words(p)
            address += 4 * (len(body) + 1)
            nxt = address if i + 1 < len(value) else 0xFFFFFF
            ram.append(((0x20 | (p['flags'] & 15) | (16 if p.get('depth') else 0)) << 24) | nxt)
            ram.extend(body)
    regs = list(regs) if regs is not None else [0] * 64
    return (struct.pack('<64I', *regs) + bytes(vram) + struct.pack('<I', 4 * len(ram)) +
            struct.pack(f'<{len(ram)}I', *ram) + struct.pack('<I', len(pairs)) +
            b''.join(struct.pack('<II', o, v & 0xFFFFFFFF) for o, v in pairs))


def replay(probe, path, vram, regs, writes):
    """Runs the writes through Mei's GPU: (framebuffer, depth buffer, display, stats)."""
    path.write_bytes(fixture(vram, regs, writes))
    raw = path.with_suffix('.out')
    subprocess.run([str(probe), str(path), str(raw)], check=True)
    data = raw.read_bytes()
    size = W * H * 2
    images = [np.frombuffer(data[i * size:(i + 1) * size], dtype='<u2').astype(np.int64).reshape(H, W)
              for i in range(3)]
    stats = dict(zip(STAT_NAMES, struct.unpack('<8I', data[3 * size:])))
    return images[0], images[1], images[2], stats


def model(vram, regs, writes):
    """The reference's (framebuffer, depth buffer, display, stats) for the same writes."""
    gpu = Gpu(vram, regs)
    for offset, value in writes:
        gpu.write(offset, value)
    return gpu.fb, gpu.zbuf, gpu.display(), gpu.stats


# RENDERING.md's golden values: the key table, and the receding floor's texels and cost.
GOLDEN_KEYS = {0x1000: 0xFFFF, 0: 0xFFFF, -5: 0xFFFF, 0x8000: 0xD000, 0x10000: 0xC000, 0x18000: 0xB555,
               0x20000: 0xB000, 0x30000: 0xA555, 0x640000: 0x547A, 0x800000: 0x5000, 0xFFF0000: 0x0001,
               0x10000000: 0x0000, 0x7FFFFFFF: 0x0000}
GOLDEN_TEXELS = {(0, 0): (0, 0), (15, 0): (11, 0), (16, 0): (12, 0), (17, 0): (13, 0), (160, 0): (127, 0),
                 (318, 0): (254, 0), (0, 60): (0, 146), (16, 60): (7, 146), (17, 60): (7, 146),
                 (200, 60): (91, 146), (0, 119): (0, 203), (160, 119): (51, 203), (0, 120): (0, 204),
                 (160, 120): (52, 204), (318, 120): (253, 204), (17, 180): (4, 235), (200, 180): (138, 235),
                 (16, 238): (12, 254), (318, 238): (254, 254)}


def golden():
    """A list of the golden values the model gets wrong (empty when it agrees)."""
    wrong = [('key', w) for w, k in GOLDEN_KEYS.items() if int(key(reciprocal(w & 0xFFFFFFFF))) != k]
    gpu = Gpu()
    gpu.trace = []
    gpu.write(GPU_DRAW, [{'flags': 6, 'depth': True, 'blend': 0, 'cols': [[128, 128, 128]] * 4,
                          'pos': [[0, 0], [319, 0], [0, 239], [319, 239]],
                          'uv': [[0, 0], [255, 0], [0, 255], [255, 255]], 'slot': 0, 'four': False, 'pal': 0,
                          'w': [4 << 16, 4 << 16, 1 << 16, 1 << 16]}])
    texels = {}
    for xs, ys, us, vs in gpu.trace:
        texels.update({(int(x), int(y)): (int(u), int(v)) for x, y, u, v in zip(xs, ys, us, vs)})
    wrong += [('texel', p) for p, t in GOLDEN_TEXELS.items() if texels.get(p) != t]
    want = {'gpu_cycles': 163484, 'tris_recip': 2, 'px_persp': 76241, 'persp_divs': 5437}
    wrong += [('stat', k) for k, v in want.items() if gpu.stats[k] != v]
    return wrong


if __name__ == '__main__':
    problems = golden()
    print('golden values:', problems or 'all agree')
    raise SystemExit(bool(problems))
