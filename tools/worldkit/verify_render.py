"""Sampled views of a world pack on the real runtime, and the ordering reference.

The verification cart (generated here) opens the pack with stdlib/worldpack.akr and draws each
sampled view twice on the headless core: once from the pack as built, to measure CPU cycles,
GPU cycles, triangles and packet arena use, and once from an *identity pack*, a copy in which
every drawn face of every placement, stand-in and entity mesh within reach has its colour
replaced by a unique 15-bit triangle ID (dithering off), to capture which face the runtime put
on each pixel. tools/worldkit/scene_probe.c records both after each presented frame.

The reference that the ID picture is compared with is independent of the runtime's drawing
code: it takes the pack's meshes, placements, stand-ins and entities, selects what the reader
should draw (the 3 x 3 near cells, the far ring of stand-ins, layer masks, sphere culling),
clips every face to its pass's near plane in floating point, projects it with the camera matrix
the cart used, and picks the nearest face at each pixel by true view depth. Only pixels where
that choice cannot be changed by the runtime's rounding are compared: pixels at least
`edge_margin` pixels inside the winning face and at least that far from every other face that
could be nearer, with a depth difference larger than `depth_epsilon`. The two passes are kept
apart as the reader keeps them: wherever a near-pass face covers a pixel, the far pass's
stand-ins are behind it by construction (docs/WORLDPACK.md, "What a reader does").

See docs/WORLDCHECKER.md for what is and is not exact.
"""
from dataclasses import dataclass, field
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from .pack import ONE, mesh_info
from .verify_shared import numpy, id_colour, diagnostic_png

W, H = 320, 240
MAX_ID = 32767
FACE_GOURAUD, FACE_TEXTURED, FACE_QUAD, FACE_SEMI, FACE_DOUBLE, FACE_KEYED = 1, 2, 4, 8, 16, 32
VIEW_SIZE = 64          # bytes of a VView record in the cart
OUT_SIZE = 128          # bytes of the cart's VOut block
STATS_WORDS = 18
STATS_NAMES = ('tris', 'tris_empty', 'tris_dropped', 'px0', 'px1', 'px2', 'px3', 'px4', 'px5', 'px6',
               'px7', 'clears', 'lists', 'cpu_cycles', 'gpu_cycles', 'ticks', 'gpu_lag', 'zero')
ARENA_BYTES = 40960 * 4
ARENA_FULL = 52         # the face loops stop when fewer bytes than a quad's packet are left


class RenderError(RuntimeError):
    """The native tools failed (missing, did not compile, faulted)."""


# ---- meshes and what draws them

@dataclass
class MeshData:
    raw: list           # vertices (x, y, z) raw 16.16
    faces: list         # (flags, idx tuple, tex, palette, uv tuple)
    size: int           # bytes from the mesh's start to its end


def read_mesh(data, off):
    nv, nf, vo, fo = mesh_info(data[off:])
    raw = [struct.unpack_from('<3i', data, off + vo + 16 * k) for k in range(nv)]
    faces = []
    for k in range(nf):
        at = off + fo + 36 * k
        flags, blend, tex, pal = struct.unpack_from('<4B', data, at)
        idx = struct.unpack_from('<4H', data, at + 4)
        uv = struct.unpack_from('<4H', data, at + 28)
        n = 4 if flags & FACE_QUAD else 3
        faces.append((flags, idx[:n], tex, pal, uv[:n]))
    return MeshData(raw, faces, max(vo + 16 * nv, fo + 36 * nf))


def swatch_face(flags, tex, uv):
    """A palette swatch face (the Asset Kit's palette-backed materials): 4-bit textured, the same
    nonzero texel at every corner. It covers exactly the pixels of the untextured face."""
    return bool(flags & FACE_TEXTURED) and bool(tex & 16) and len(set(uv)) == 1 and 0 < (uv[0] & 255) < 16


def checkable(flags, tex, uv):
    """Whether the ID picture of a face shows exactly where the game's face is opaque."""
    if flags & FACE_SEMI:
        return False
    return not flags & FACE_TEXTURED or swatch_face(flags, tex, uv)


@dataclass
class Instance:
    """Something the runtime (or the verification cart, for entities) draws: a placement, a
    stand-in or an entity's mesh."""
    key: tuple          # ('placement', i, j, k) | ('standin', i, j) | ('entity', number)
    cell: tuple
    mesh: int           # offset of the mesh in the pack
    field: int          # offset of the u32 that points at the mesh (patched in identity packs)
    pos: tuple          # cell-local raw position (stand-ins: 0)
    cos: int = ONE      # raw yaw rows; entities: yaw in radians as `yaw`
    sin: int = 0
    yaw: float = None
    mask: int = 0
    tag: int = None
    sphere: tuple = None


def instances(pack):
    """Every drawable instance in the pack, in a fixed order (cells by row then column)."""
    out = []
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        c = pack.cells[(i, j)]
        pl_off = None
        for k, p in enumerate(c.placements):
            if pl_off is None:
                pl_off = struct.unpack_from('<I', pack.data, c.off + 56)[0]
            out.append(Instance(('placement', i, j, k), (i, j), p['mesh'], pl_off + 48 * k + 40, p['pos'],
                                p['cos'], p['sin'], mask=p['mask'], tag=p['tag'], sphere=p['sphere']))
        if c.standin:
            out.append(Instance(('standin', i, j), (i, j), c.standin, c.off + 48, (0, 0, 0),
                                sphere=c.standin_bounds))
        for e in c.entities:
            if e['mesh']:
                out.append(Instance(('entity', e['number']), (i, j), e['mesh'], e['off'] + 28, e['pos'],
                                    yaw=e['yaw'] / ONE, mask=e['mask'], tag=e['type']))
    return out


def identity_mesh(data, off, mesh, first):
    """The mesh at `off` with face k drawn in ID first + k: untextured (swatch faces cover the
    same pixels untextured), opaque, colours replaced; FACE_KEYED faces keep their bucket."""
    out = bytearray(data[off:off + mesh.size])
    _, nf, _, fo, _ = struct.unpack_from('<HHIII', out)
    for k in range(nf):
        at = fo + 36 * k
        flags = out[at]
        flags &= ~(FACE_TEXTURED | FACE_SEMI)
        out[at] = flags
        out[at + 1] = out[at + 2] = out[at + 3] = 0
        c = id_colour(first + k)
        cols = [c, c, c, c]
        if flags & FACE_KEYED:
            cols[3] = struct.unpack_from('<I', out, at + 24)[0]
        struct.pack_into('<4I', out, at + 12, *cols)
        struct.pack_into('<4H', out, at + 28, 0, 0, 0, 0)
    return bytes(out)


def identity_pack(data, insts, first_ids, meshes):
    """A copy of the pack in which each instance in first_ids draws its own identity mesh,
    appended to the pack (the instance's mesh field points at it)."""
    out = bytearray(data)
    for inst in insts:
        if inst.key not in first_ids:
            continue
        while len(out) % 4:
            out.append(0)
        at = len(out)
        out += identity_mesh(data, inst.mesh, meshes[inst.mesh], first_ids[inst.key])
        struct.pack_into('<I', out, inst.field, at)
    while len(out) % 4:
        out.append(0)
    struct.pack_into('<I', out, 8, len(out))
    return bytes(out)


# ---- the verification cart

CART = '''// Generated by the Mei World Kit (tools/worldkit/verify_render.py): the verification cart.
// Each view is drawn twice: from PACK (measured) and from IDPACK (the triangle-ID picture).
cart "World verification"
import "worldpack.akr"

struct VView {{
    eye: vec4
    yaw: fixed
    pitch: fixed
    flags: u32          // bit 0: draw entity meshes
    reserved: u32
    on: [8]u32          // layers switched on (bit k of word k >> 5)
}}

struct VOut {{
    request: u32        // bit 0: record this frame, bit 1: and its picture (mei-scene-probe)
    view: s32
    draw_cycles: s32    // wp_draw()
    entity_cycles: s32  // the entities' meshes
    arena_bytes: s32
    arena_left: s32
    near_cells: s32
    placements: s32
    drawn: s32
    standins: s32
    entities: s32
    reserved: s32
    origin: vec4
    vp: mat4
}}

embed PACK: u8 = "pack.bin"
embed IDPACK: u8 = "idpack.bin"
embed VIEWS: VView = "views.bin"

var vout: VOut
var tick: s32

fn draw_entities(eye: vec3) -> s32 {{
    let ci = wp_cell_index(eye.x)
    let cj = wp_cell_index(eye.z)
    let o = wp_view_origin()
    var n = 0
    for dj in -1..2 {{
        for di in -1..2 {{
            let c = wp_cell(ci + di, cj + dj)
            if c == null {{ continue }}
            for k in 0..c.entity_count as s32 {{
                let e = wp_cell_entity(c, k)
                let m = wp_entity_mesh(e)
                if m != null && wp_entity_live(e) {{
                    mesh_at(m, wp_entity_pos(e) - o, e.yaw)
                    n += 1
                }}
            }}
        }}
    }}
    return n
}}

fn draw() {{
    vout.request = 0
    let k = tick - 1
    tick += 1
    if k < 0 || k >= 2 * (len(VIEWS) as s32) {{
        cls(0)
        return
    }}
    let v = &VIEWS[k >> 1]
    let ident = (k & 1) == 1
    if ident {{
        assert(wp_open(IDPACK))
        dither(false)
    }} else {{
        assert(wp_open(PACK))
        dither(true)
    }}
    wp_far_ring = {far_ring}
    wp_clip_near = {clip_near}
    wp_near_far = {near_far}
    let nl = wp_layer_count()
    for l in 0..nl {{ wp_layer_set(l, false) }}
    for l in 0..nl {{
        if (v.on[l >> 5] >> ((l & 31) as u32)) & 1 != 0 {{ wp_layer_set(l, true) }}
    }}
    cls(0)
    let eye = vec3(v.eye.x, v.eye.y, v.eye.z)
    let c0 = cycle_count()
    wp_draw(eye, v.yaw, v.pitch)
    let c1 = cycle_count()
    var ne = 0
    if v.flags & 1 != 0 {{ ne = draw_entities(eye) }}
    let c2 = cycle_count()
    vout.view = k >> 1
    vout.draw_cycles = c1 - c0
    vout.entity_cycles = c2 - c1
    vout.arena_bytes = (__arena_ptr as s32) - (&__arena[0] as s32)
    vout.arena_left = (__arena_end as s32) - (__arena_ptr as s32)
    vout.near_cells = wp_stats.near_cells
    vout.placements = wp_stats.placements
    vout.drawn = wp_stats.drawn
    vout.standins = wp_stats.standins
    vout.entities = ne
    let o = wp_view_origin()
    vout.origin = vec4(o.x, o.y, o.z, 0.0)
    vout.vp = __vp
    if ident {{ vout.request = 3 }} else {{ vout.request = 1 }}
}}
'''


def fixed_literal(v):
    return f'{v:.7f}'


def view_record(view, layer_ids, entities):
    on = [0] * 8
    for lid in layer_ids:
        on[lid >> 5] |= 1 << (lid & 31)
    eye = [round(c * ONE) for c in view['eye']]
    return struct.pack('<4i2iII8I', *eye, 0, round(view['yaw'] * ONE), round(view['pitch'] * ONE),
                       1 if entities else 0, 0, *on)


def _run(cmd, what, timeout=600):
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RenderError(f'{what}: {error}') from error
    if r.returncode:
        raise RenderError(f'{what} failed ({r.returncode}):\n' + (r.stderr + r.stdout).strip()[-3000:])
    return r


def run_cart(pack_bytes, id_bytes, views, runtime, tools, work):
    """Compiles the verification cart for these views (dicts with eye, yaw, pitch, layers, a
    list of layer ids) and runs it on mei-scene-probe. Returns ([(stats, out, picture or None)]
    per frame, timings)."""
    np = numpy()
    work = Path(work)
    (work / 'pack.bin').write_bytes(pack_bytes)
    (work / 'idpack.bin').write_bytes(id_bytes)
    (work / 'views.bin').write_bytes(b''.join(view_record(v, v['layers'], runtime['draw_entities'])
                                              for v in views))
    near_far = runtime['near_far']
    (work / 'check.akr').write_text(CART.format(far_ring=int(runtime['far_ring']),
                                                clip_near=fixed_literal(runtime['clip_near']),
                                                near_far=fixed_literal(near_far)))
    t0 = time.perf_counter()
    _run([tools['compiler'], work / 'check.akr', '-o', work / 'check.mei', '--sym', work / 'check.sym'],
         'compiling the verification cart')
    t1 = time.perf_counter()
    symbols = {}
    for line in (work / 'check.sym').read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            symbols[parts[1]] = int(parts[0], 16)
    if 'G_vout' not in symbols:
        raise RenderError('the compiler did not emit the vout symbol')
    frames = 1 + 2 * len(views)
    _run([tools['probe'], work / 'check.mei', work / 'capture.bin', frames, symbols['G_vout'], OUT_SIZE],
         'running the verification cart')
    t2 = time.perf_counter()
    cap = (work / 'capture.bin').read_bytes()
    if cap[:4] != b'MSP1':
        raise RenderError('mei-scene-probe wrote no capture')
    count, size = struct.unpack_from('<II', cap, 4)
    if size != OUT_SIZE:
        raise RenderError('mei-scene-probe captured the wrong block size')
    at = 12
    records = []
    for _ in range(count):
        stats = dict(zip(STATS_NAMES, struct.unpack_from(f'<{STATS_WORDS}I', cap, at)))
        at += 4 * STATS_WORDS
        o = struct.unpack_from('<12i', cap, at)
        origin = struct.unpack_from('<4i', cap, at + 48)
        vp = struct.unpack_from('<16i', cap, at + 64)
        at += OUT_SIZE
        out = dict(request=o[0] & 0xFFFFFFFF, view=o[1], draw_cycles=o[2], entity_cycles=o[3],
                   arena_bytes=o[4], arena_left=o[5], near_cells=o[6], placements=o[7], drawn=o[8],
                   standins=o[9], entities=o[10], origin=[c / ONE for c in origin[:3]],
                   vp=np.array(vp, dtype=float).reshape(4, 4) / ONE)
        pic = None
        if out['request'] & 2:
            pic = np.frombuffer(cap, dtype='<u2', count=W * H, offset=at).astype(np.int32)
            at += 2 * W * H
        records.append((stats, out, pic))
    if len(records) != 2 * len(views):
        raise RenderError(f'the verification cart recorded {len(records)} frames, expected {2 * len(views)}')
    return records, {'compile_seconds': t1 - t0, 'run_seconds': t2 - t1}


# ---- the reference

def _planes(vp, near, far):
    """The six planes wp_draw() culls spheres with (__wp_frustum), from the camera matrix."""
    r0, r1, r3 = vp[0], vp[1], vp[3]
    fx = math.sqrt(r0[0] ** 2 + r0[1] ** 2 + r0[2] ** 2)
    fy = math.sqrt(r1[0] ** 2 + r1[1] ** 2 + r1[2] ** 2)
    kx, ky = 1 / math.sqrt(1 + fx * fx), 1 / math.sqrt(1 + fy * fy)
    return [(r3 + r0) * kx, (r3 - r0) * kx, (r3 + r1) * ky, (r3 - r1) * ky,
            r3 - [0, 0, 0, near], [0, 0, 0, far] - r3]


def _sphere(planes, c, r, tol=1 / 64):
    """True (in view), False (culled) or None (too close to a plane to say)."""
    unsure = False
    for p in planes:
        d = p[0] * c[0] + p[1] * c[1] + p[2] * c[2] + p[3] + r
        if d < -tol:
            return False
        if d < tol:
            unsure = True
    return None if unsure else True


def cell_mask(pack, cell, layers_on):
    return sum(1 << k for k, lid in enumerate(cell.layers) if lid in layers_on)


def select(pack, by_cell, eye, vp, layers_on, runtime):
    """What wp_draw() (and the cart's entity loop) draws from eye: a list of (instance, pass,
    certain), certain False where a culling sphere is too close to a plane to say."""
    S = 1 << pack.cell_shift
    half = S / 2
    ci, cj = math.floor(eye[0]) >> pack.cell_shift, math.floor(eye[2]) >> pack.cell_shift
    out = []
    ring = int(runtime['far_ring'])
    if ring >= 2:
        far = S * (2 * ring + 1) * 3 / 4
        planes = _planes(vp, half, far)
        for dj in range(-ring, ring + 1):
            for di in range(-ring, ring + 1):
                if max(abs(di), abs(dj)) < 2:
                    continue
                for inst in by_cell.get((ci + di, cj + dj), ()):
                    if inst.key[0] != 'standin':
                        continue
                    s = inst.sphere
                    v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                    if v is not False:
                        out.append((inst, 'far', v is True))
    planes = _planes(vp, runtime['clip_near'], runtime['near_far'])
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            c = pack.cells.get((ci + di, cj + dj))
            if c is None:
                continue
            mask = cell_mask(pack, c, layers_on)
            cv = True
            if c.placements:
                b = c.bounds
                cv = _sphere(planes, (b[0] / ONE + di * S, b[1] / ONE, b[2] / ONE + dj * S), b[3] / ONE)
            for inst in by_cell.get((ci + di, cj + dj), ()):
                kind = inst.key[0]
                if inst.mask and not inst.mask & mask:
                    continue
                if kind == 'entity':
                    if runtime['draw_entities']:
                        out.append((inst, 'near', True))
                elif kind == 'placement' and cv is not False:
                    s = inst.sphere
                    v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                    if v is not False:
                        out.append((inst, 'near', v is True and cv is True))
    return out


@dataclass
class Face:
    id: int
    inst: object
    index: int          # the face's number in its mesh
    pass_: str          # 'near' or 'far'
    poly: object        # screen polygon (k, 2), centred on the runtime's rounding
    plane: tuple        # (N, D): depth w = D / (N . (u, v, 1))
    definite: bool      # drawn for certain and checkable: may be the expected face
    tol: float


def _clip_near(cs, near):
    """Sutherland-Hodgman against w >= near on clip-space (x, y, w) rows."""
    out = []
    n = len(cs)
    for i in range(n):
        a, b = cs[i - 1], cs[i]
        da, db = a[2] - near, b[2] - near
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near))
        if db >= 0:
            out.append(b)
    return out


def view_faces(pack, meshes, view_insts, vp, origin, first_ids, near_planes):
    """Faces (screen polygons with depth planes) of the instances a view draws. view_insts is a
    list of (instance, pass, certain)."""
    np = numpy()
    S = 1 << pack.cell_shift
    half = S / 2
    faces = []
    for inst, pas, certain in view_insts:
        mesh = meshes[inst.mesh]
        if inst.key not in first_ids:
            raise RenderError(f'{inst.key} is drawn but has no triangle IDs in this group')
        first = first_ids[inst.key]
        ci, cj = inst.cell
        cx, cz = ci * S + half - origin[0], cj * S + half - origin[2]
        v = np.array(mesh.raw, dtype=float) / ONE
        if inst.yaw is not None:
            c, s = math.cos(inst.yaw), math.sin(inst.yaw)
        else:
            c, s = inst.cos / ONE, inst.sin / ONE
        p = [inst.pos[0] / ONE + cx, inst.pos[1] / ONE, inst.pos[2] / ONE + cz]
        world = np.column_stack((c * v[:, 0] + s * v[:, 2] + p[0], v[:, 1] + p[1],
                                 -s * v[:, 0] + c * v[:, 2] + p[2], np.ones(len(v))))
        clip = world @ vp.T                    # x, y, z, w
        cxyw = clip[:, [0, 1, 3]]
        near = near_planes[pas]
        for k, (flags, idx, tex, pal, uv) in enumerate(mesh.faces):
            order = (idx[0], idx[1], idx[3], idx[2]) if len(idx) == 4 else idx
            cs = [tuple(cxyw[i]) for i in order]
            if all(q[2] < near for q in cs):
                continue
            poly = _clip_near(cs, near) if any(q[2] < near for q in cs) else cs
            if len(poly) < 3:
                continue
            scr = np.array([(160 + 160 * q[0] / q[2] - 0.5, 120 - 120 * q[1] / q[2] - 0.5) for q in poly])
            xs, ys = scr[:, 0], scr[:, 1]
            area = 0.5 * float(np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys))
            perim = float(np.sum(np.hypot(np.roll(xs, -1) - xs, np.roll(ys, -1) - ys)))
            thin = perim == 0 or 2 * abs(area) / perim < 1.5
            if not thin and area > 0 and not flags & FACE_DOUBLE:
                continue                       # a back face (the runtime culls nclip >= 0)
            if not thin and len(poly) > 3:
                # a non-convex polygon (a twisted quad) is not drawn as its outline
                cr = [(xs[(i + 1) % len(xs)] - xs[i]) * (ys[(i + 2) % len(xs)] - ys[(i + 1) % len(xs)]) -
                      (ys[(i + 1) % len(xs)] - ys[i]) * (xs[(i + 2) % len(xs)] - xs[(i + 1) % len(xs)])
                      for i in range(len(xs))]
                convex = all(x <= 1e-9 for x in cr) or all(x >= -1e-9 for x in cr)
            else:
                convex = True
            a0, a1, a2 = (np.array(cxyw[i]) for i in idx[:3])
            nrm = np.cross(a1 - a0, a2 - a0)
            d = float(nrm @ a0)
            tol = 0.0
            if len(idx) == 4:
                w3 = world[idx[3], :3]
                w0, w1, w2 = (world[i, :3] for i in idx[:3])
                wn = np.cross(w1 - w0, w2 - w0)
                ln = float(np.linalg.norm(wn))
                if ln > 0:
                    tol = abs(float((w3 - w0) @ wn)) / ln
            faces.append(Face(first + k, inst, k, pas, scr, (nrm, d),
                              certain and not thin and convex and abs(d) > 1e-12 and checkable(flags, tex, uv),
                              tol))
    return faces


def _ray_uv():
    np = numpy()
    py, px = np.mgrid[0:H, 0:W]
    return (px + 0.5 - 160) / 160, (120 - py - 0.5) / 120


def _face_pixels(f, margin):
    """Pixels within `margin` of face f (or inside it), with each pixel's signed distance from
    the face's outline (positive inside, in pixels) and the face's depth there."""
    np = numpy()
    xs, ys = f.poly[:, 0], f.poly[:, 1]
    x0, x1 = max(0, int(math.floor(xs.min() - margin))), min(W - 1, int(math.ceil(xs.max() + margin)))
    y0, y1 = max(0, int(math.floor(ys.min() - margin))), min(H - 1, int(math.ceil(ys.max() + margin)))
    if x0 > x1 or y0 > y1:
        return None
    yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    n = len(xs)
    area = float(np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys))
    sign = 1.0 if area >= 0 else -1.0
    inside = np.full(xx.shape, np.inf)
    for i in range(n):
        ax, ay, bx, by = xs[i], ys[i], xs[(i + 1) % n], ys[(i + 1) % n]
        ln = math.hypot(bx - ax, by - ay)
        if ln == 0:
            continue
        dist = sign * ((bx - ax) * (yy - ay) - (by - ay) * (xx - ax)) / ln
        inside = np.minimum(inside, dist)
    keep = inside > -margin
    if not keep.any():
        return None
    px, py = xx[keep], yy[keep]
    u, v = (px + 0.5 - 160) / 160, (120 - py - 0.5) / 120
    nrm, d = f.plane
    den = nrm[0] * u + nrm[1] * v + nrm[2]
    with np.errstate(divide='ignore', invalid='ignore'):
        z = np.where(den != 0, d / den, np.inf)
    # an edge-on face (its plane through the eye) or a pixel past the plane's horizon has no
    # depth: count it as nearest, so the pixel is left undecided rather than given to a face
    z = np.where(np.isfinite(z) & (z > 0), z, 0.0)
    return (py * W + px).astype(np.int64), inside[keep], z


class _Pass:
    def __init__(self):
        np = numpy()
        self.r1 = np.full(W * H, np.inf)
        self.rid = np.zeros(W * H, dtype=np.int32)
        self.m1 = np.full(W * H, np.inf)
        self.mid = np.zeros(W * H, dtype=np.int32)
        self.m2 = np.full(W * H, np.inf)
        self.tol = np.zeros(W * H)

    def add(self, f, margin):
        np = numpy()
        got = _face_pixels(f, margin)
        if got is None:
            return
        pix, inside, z = got
        # maybe-coverage: nearest and second nearest depth
        nearer = z < self.m1[pix]
        p2 = pix[nearer]
        self.m2[p2] = self.m1[p2]
        self.m1[p2] = z[nearer]
        self.mid[p2] = f.id
        rest = ~nearer & (z < self.m2[pix])
        self.m2[pix[rest]] = z[rest]
        if f.definite:
            rob = (inside >= margin) & (z < self.r1[pix])
            pr = pix[rob]
            self.r1[pr] = z[rob]
            self.rid[pr] = f.id
            self.tol[pr] = f.tol

    def expected(self, eps):
        """(expected ID per pixel, -1 where undecided; covered: some face may cover it)."""
        np = numpy()
        covered = np.isfinite(self.m1)
        decided = np.isfinite(self.r1) & (self.mid == self.rid) & (self.m2 > self.r1 + eps + self.tol)
        exp = np.where(decided, self.rid, -1)
        exp = np.where(covered, exp, 0)
        return exp.astype(np.int32), covered


def compare_view(faces, actual, settings):
    """The ordering check of one view: actual is the ID picture (0 = nothing drawn)."""
    np = numpy()
    margin = settings['edge_margin']
    eps = settings['depth_epsilon']
    tol_extra = max((f.tol for f in faces), default=0.0)
    near, far = _Pass(), _Pass()
    for f in faces:
        (near if f.pass_ == 'near' else far).add(f, margin)
    exp_n, cov_n = near.expected(eps + tol_extra)
    exp_f, cov_f = far.expected(eps + tol_extra)
    expected = np.where(cov_n, exp_n, exp_f)
    by_id = {f.id: f for f in faces}
    tested = expected >= 0
    depth_e = np.where(cov_n, near.r1, far.r1)
    mism = tested & (actual != expected)
    wrong = np.zeros(W * H, dtype=bool)
    coverage = np.zeros(W * H, dtype=bool)
    drawn_depth = np.full(W * H, np.inf)
    # where they differ: was the face drawn there one that can cover the pixel, and behind?
    for a in np.unique(actual[mism]).tolist():
        pix = np.flatnonzero(mism & (actual == a))
        f = by_id.get(a)
        if a == 0 or f is None:
            coverage[pix] = True
            continue
        got = _face_pixels(f, margin)
        if got is None:
            coverage[pix] = True
            continue
        fp, _, fz = got
        zmap = dict(zip(fp.tolist(), fz.tolist()))
        for p in pix.tolist():
            z = zmap.get(p)
            e = expected[p]
            if z is None or e == 0 or (f.pass_ == 'far' and cov_n[p]):
                coverage[p] = True
            elif z > depth_e[p] + eps + tol_extra:
                wrong[p] = True
                drawn_depth[p] = z
            else:
                coverage[p] = True
    # stand-ins in front of the near pass (the two-pass design draws them behind)
    inversion = tested & cov_n & np.isfinite(far.r1) & (far.r1 < near.r1 - eps - tol_extra) & (actual == expected)
    return dict(expected=expected, tested=tested, wrong=wrong, coverage=coverage, depth=depth_e,
                drawn_depth=drawn_depth, inversion=inversion, ambiguous=(~tested) & (cov_n | cov_f),
                by_id=by_id, covered=cov_n | cov_f)


def witnesses(cmp, actual, settings, describe, limit):
    """Wrong-order pixels grouped by (drawn face, expected face), largest first."""
    np = numpy()
    wrong = cmp['wrong']
    out = []
    if not wrong.any():
        return out, 0, 0
    pairs = {}
    near_band = settings['near_band']
    depth = cmp['depth']
    near_pix = 0
    for p in np.flatnonzero(wrong).tolist():
        a, e = int(actual[p]), int(cmp['expected'][p])
        fa, fe = cmp['by_id'][a], cmp['by_id'][e]
        entity = fa.inst.key[0] == 'entity' or fe.inst.key[0] == 'entity'
        near = depth[p] < near_band
        cls = 'near' if near or entity else 'far'
        if cls == 'near':
            near_pix += 1
        rec = pairs.setdefault((a, e), dict(count=0, near=0, sample=p, err=0.0, entity=entity,
                                            min_depth=float('inf')))
        rec['count'] += 1
        rec['near'] += cls == 'near'
        rec['err'] = max(rec['err'], float(cmp['drawn_depth'][p] - depth[p]))
        rec['min_depth'] = min(rec['min_depth'], float(depth[p]))
    for (a, e), rec in sorted(pairs.items(), key=lambda kv: (-kv[1]['count'], kv[0]))[:limit]:
        p = rec['sample']
        out.append({'code': 'wrong_order', 'class': 'near' if rec['near'] else 'far',
                    'pixels': rec['count'], 'near_pixels': rec['near'],
                    'drawn': describe(cmp['by_id'][a]), 'expected': describe(cmp['by_id'][e]),
                    'sample_pixel': [p % W, p // W], 'visible_depth': round(rec['min_depth'], 4),
                    'max_depth_error': round(rec['err'], 4), 'involves_entity': rec['entity']})
    total = int(wrong.sum())
    return out, near_pix, total - near_pix


def diagnostic_image(cmp, actual):
    np = numpy()
    exp = np.where(cmp['tested'], cmp['expected'], 0) - 1
    act = actual.astype(np.int64) - 1
    return diagnostic_png(exp.astype(np.int64), act, cmp['wrong'] | cmp['coverage'])
