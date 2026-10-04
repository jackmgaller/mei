"""Sampled views of a world pack on the real runtime, and the ordering reference.

The verification cart (generated here) opens the pack with stdlib/worldpack.akr and draws each
sampled view twice on the headless core: once from the pack as built, to measure CPU cycles,
GPU cycles, triangles and packet arena use, and once from an *identity pack*, a copy in which
every drawn face of every placement, stand-in and entity mesh within reach has its colour
replaced by a unique 15-bit triangle ID (dithering off), to capture which face the runtime put
on each pixel. tools/worldkit/scene_probe.c records both after each presented frame.

The reference that the ID picture is compared with is independent of the runtime's drawing
code: it takes the pack's meshes, placements, stand-ins and entities, selects what the reader
should draw (the 3 x 3 near cells, the far ring of stand-ins, layer masks, sphere culling, the
entities wp_draw_entities() culls), clips every face to its pass's near plane in floating point,
projects it with the camera matrix the cart used, and picks the nearest face at each pixel by
true view depth. Only pixels where that choice cannot be changed by the runtime's rounding are
compared: pixels at least `edge_margin` pixels inside the winning face and at least that far
from every other face that could be nearer, with a depth difference larger than
`depth_epsilon`. The reader's passes are
kept apart as the reader keeps them, each drawn over the one before: the far pass's stand-ins,
then the ground pass (ground placements, when the pack has them and the runtime draws ground
first), then the near pass (docs/WORLDPACK.md, "What a reader does"). Wherever a later pass's
face covers a pixel, the earlier passes are behind it by construction; where an earlier pass's
face is truly nearer, the pixel is an inversion of that design (a stand-in in front of near
geometry, or ground in front of what is drawn after it), counted apart from wrong order.

In depth mode (runtime depth: the game draws with the depth buffer, docs/RENDERING.md) the cart
draws as such a game does, and the reference keeps one pass: the depth test orders every face of
every pass by its own depth. A pixel is then decided only where the nearest face is nearer than
every other by more than the depth key's precision and half a pixel of each face's depth slope
(kitcore/depth.py), so the ordering check is a regression check that should find nothing.

See docs/WORLDCHECKER.md for what is and is not exact.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import time

from kitcore import depth as DEPTH
from .pack import ONE, mesh_info, lod_level, lod_d2
from .verify_shared import numpy, id_colour, diagnostic_png

W, H = 320, 240
MAX_ID = 32767
FACE_GOURAUD, FACE_TEXTURED, FACE_QUAD, FACE_SEMI, FACE_DOUBLE, FACE_KEYED = 1, 2, 4, 8, 16, 32
VIEW_SIZE = 64          # bytes of a VView record in the cart
OUT_SIZE = 136          # bytes of the cart's VOut block
STATS_WORDS = 24
DEPTH_STATS = ('px_ztest', 'px_zfail', 'zclears', 'tris_recip', 'px_persp', 'persp_divs')
STATS_NAMES = ('tris', 'tris_empty', 'tris_dropped', 'px0', 'px1', 'px2', 'px3', 'px4', 'px5', 'px6',
               'px7', 'clears', 'lists', 'cpu_cycles', 'gpu_cycles', 'ticks', 'gpu_lag', 'zero') + DEPTH_STATS
ARENA_BYTES = 40960 * 4
ARENA_FULL = 52         # the face loops stop when fewer bytes than a quad's packet are left
ARENA_FULL_DEPTH = 68   # ... a quad's packet with depth


class RenderError(RuntimeError):
    """The native tools failed (missing, did not compile, faulted)."""


# ---- meshes and what draws them

@dataclass
class MeshData:
    raw: list           # vertices (x, y, z) raw 16.16
    faces: list         # (flags, idx tuple, tex, palette, uv tuple)
    size: int           # bytes from the mesh's start to its end (its window table included)
    windows: list = field(default_factory=list)     # the texture window table's halfwords


def read_mesh(data, off):
    nv, nf, vo, fo = mesh_info(data[off:])
    wo = struct.unpack_from('<I', data, off + 12)[0]
    raw = [struct.unpack_from('<3i', data, off + vo + 16 * k) for k in range(nv)]
    faces = []
    for k in range(nf):
        at = off + fo + 36 * k
        flags, blend, tex, pal = struct.unpack_from('<4B', data, at)
        idx = struct.unpack_from('<4H', data, at + 4)
        uv = struct.unpack_from('<4H', data, at + 28)
        n = 4 if flags & FACE_QUAD else 3
        faces.append((flags, idx[:n], tex, pal, uv[:n]))
    size = max(vo + 16 * nv, fo + 36 * nf)
    windows = []
    if wo:
        used = max((tex >> 5 for flags, _, tex, _, _ in faces if flags & FACE_TEXTURED), default=0)
        windows = list(struct.unpack_from(f'<{used}H', data, off + wo)) if used else []
        if used:
            size = max(size, wo + 2 * used)
    return MeshData(raw, faces, size, windows)


# ---- region texture sets (world packs with textures: docs/WORLDCHECKER.md, "Textures")

class RegionTexels:
    """Which texels of a region's texture set are not 0 (texel 0 draws nothing: a hole), per
    slot as the GPU addresses it: 256 x 256 texels of a 4-bit slot, 256 x 128 of an 8-bit one."""

    def __init__(self, region):
        np = numpy()
        self.slots = {}
        for t in region.textures:
            raw = np.frombuffer(t.data, dtype=np.uint8)
            if t.four_bit:
                rows = np.zeros(256 * 128, dtype=np.uint8)
                rows[:min(len(raw), len(rows))] = raw[:len(rows)]
                texels = np.stack(((rows & 15) != 0, (rows >> 4) != 0), axis=1).reshape(256, 256)
            else:
                rows = np.zeros(128 * 256, dtype=np.uint8)
                rows[:min(len(raw), len(rows))] = raw[:len(rows)]
                texels = (rows != 0).reshape(128, 256)
            self.slots[t.slot] = texels
            if not t.four_bit and len(raw) > 32768:
                pass                    # an 8-bit texture running into the next slot: not written by the kit

    def tile(self, tex, uv, windows):
        """(texel array, window (su, sv) or None) a textured face samples: its window's tile, or
        the slot (a texture drawn once: coordinates are slot texels)."""
        np = numpy()
        slot = self.slots.get(tex & 15)
        if slot is None:
            return np.zeros((1, 1), dtype=bool), None
        k = tex >> 5
        if k and k <= len(windows):
            hw = windows[k - 1]
            su, ou = 4 << (hw & 7), (hw >> 3 & 31) * 8
            sv, ov = 4 << (hw >> 8 & 7), (hw >> 11 & 31) * 8
            return slot[ov:ov + sv, ou:ou + su], (su, sv)
        return slot, None

    def solid(self, tex, uv, windows):
        """Whether a face can never sample texel 0: every texel of its window's tile, or of its
        corners' texel box, is set. Such a face covers exactly its outline's pixels."""
        arr, win = self.tile(tex, uv, windows)
        if win:
            return bool(arr.all())
        us, vs = [c & 255 for c in uv], [c >> 8 for c in uv]
        box = arr[min(vs):max(vs) + 1, min(us):max(us) + 1]
        return box.size > 0 and bool(box.all())


def pack_texels(pack):
    """{region number: RegionTexels} of the regions with texture sets (empty for other packs)."""
    return {k: RegionTexels(r) for k, r in enumerate(pack.regions) if r.textures}


def cell_region(pack, eye):
    """The region of the cell holding eye, or None where there is no cell."""
    (i, j), _, _ = pack.cell_of(round(eye[0] * ONE), round(eye[2] * ONE))
    c = pack.cells.get((i, j))
    return c.region if c else None


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
    ground: bool = False    # a ground placement (pack 1.1): drawn in the ground pass
    level: int = 0          # (pack 1.3) the level of detail this instance is of its placement
    lod: dict = None        # the placement's decoded LOD set, when it has one
    lod_field: int = None   # the offset of the placement's entry in its cell's LOD table


def instances(pack):
    """Every drawable instance in the pack, in a fixed order (cells by row then column)."""
    out = []
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        c = pack.cells[(i, j)]
        pl_off = None
        for k, p in enumerate(c.placements):
            if pl_off is None:
                pl_off = struct.unpack_from('<I', pack.data, c.off + 56)[0]
            lod = p.get('lod')
            out.append(Instance(('placement', i, j, k), (i, j), p['mesh'], pl_off + 48 * k + 40, p['pos'],
                                p['cos'], p['sin'], mask=p['mask'], tag=p['tag'], sphere=p['sphere'],
                                ground=p.get('ground', False), lod=lod, lod_field=p.get('lod_field')))
            # each coarser level of detail is an instance of its own (the cull mark draws nothing)
            for level, row in enumerate(lod['rows'] if lod else (), 1):
                if row[3]:
                    out.append(Instance(('placement', i, j, k, level), (i, j), row[3],
                                        lod['off'] + 8 + 16 * (level - 1) + 12, p['pos'], p['cos'], p['sin'],
                                        mask=p['mask'], tag=p['tag'], sphere=p['sphere'],
                                        ground=p.get('ground', False), level=level, lod=lod,
                                        lod_field=p['lod_field']))
        if c.standin:
            out.append(Instance(('standin', i, j), (i, j), c.standin, c.off + 48, (0, 0, 0),
                                sphere=c.standin_bounds))
        for e in c.entities:
            if e['mesh']:
                r = mesh_bounds(pack.data, e['mesh'])[0]
                p = e['pos']
                out.append(Instance(('entity', e['number']), (i, j), e['mesh'], e['off'] + 28, p,
                                    yaw=e['yaw'] / ONE, mask=e['mask'], tag=e['type'],
                                    sphere=(p[0], p[1], p[2], round(r * ONE))))
    return out


def mesh_bounds(data, off):
    """wp_mesh_bounds(): the radius of the sphere around the mesh's origin that holds its vertices
    (with the reader's 1/128 margin) and its lowest vertex's height, in units."""
    nv, _, vo, _ = mesh_info(data[off:])
    r2, low = 0.0, None
    for k in range(nv):
        x, y, z = (c / ONE for c in struct.unpack_from('<3i', data, off + vo + 16 * k))
        r2 = max(r2, x * x + y * y + z * z)
        low = y if low is None else min(low, y)
    return math.sqrt(r2) + 1 / 128, low or 0.0


def id_tint(n):
    """The tint word with which a white texel shows triangle ID n exactly: a texel of colour c
    tinted t shows c t >> 7 per channel, so t = ceil(1024 k / 255) shows 5-bit value k
    (tools/assetkit/visibility.py)."""
    return sum(-(-1024 * ((n >> (5 * c)) & 31) // 255) << (8 * c) for c in range(3))


def identity_mesh(data, off, mesh, first, cutouts=()):
    """The mesh at `off` with face k drawn in ID first + k: untextured (swatch faces and faces of
    textures without holes cover the same pixels untextured), opaque, colours replaced;
    FACE_KEYED faces keep their bucket. Faces in cutouts (textures with holes) stay textured,
    through palette 0, their tint carrying the ID: the verification cart loads the region's
    texture set as a mask (every texel that is not 0 made 1) and colour 1 white."""
    out = bytearray(data[off:off + mesh.size])
    _, nf, _, fo, _ = struct.unpack_from('<HHIII', out)
    for k in range(nf):
        at = fo + 36 * k
        flags = out[at]
        if k in cutouts:
            out[at] = flags & ~FACE_SEMI
            out[at + 1] = 0
            out[at + 3] = 0
            struct.pack_into('<4I', out, at + 12, *([id_tint(first + k)] * 4))
            continue
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


def cutout_faces(texels, inst, mesh, pack):
    """The faces of an instance whose textures have holes in its cell's region's texture set."""
    tx = texels.get(pack.cells[inst.cell].region) if texels else None
    if tx is None:
        return set()
    return {k for k, (flags, _, tex, _, uv) in enumerate(mesh.faces)
            if flags & FACE_TEXTURED and not swatch_face(flags, tex, uv) and not tx.solid(tex, uv, mesh.windows)}


def mask_bytes(data, four_bit):
    """A texture's bytes with every texel that is not 0 made 1."""
    np = numpy()
    raw = np.frombuffer(data, dtype=np.uint8)
    if four_bit:
        return (((raw & 15) != 0).astype(np.uint8) | (((raw >> 4) != 0).astype(np.uint8) << 4)).tobytes()
    return (raw != 0).astype(np.uint8).tobytes()


def identity_pack(data, insts, first_ids, meshes, pack=None, texels=None):
    """A copy of the pack in which each instance in first_ids draws its own identity mesh,
    appended to the pack (the instance's mesh field points at it). With texels (a textured
    pack), faces with holes stay textured (identity_mesh()) and every region's texture records
    point at masks of their textures, appended too."""
    out = bytearray(data)
    if texels:
        reg_off = struct.unpack_from('<I', data, 40)[0]
        for k, r in enumerate(pack.regions):
            ntex, to = struct.unpack_from('<H', data, reg_off + 32 * k + 4)[0], struct.unpack_from('<I', data, reg_off + 32 * k + 8)[0]
            for t in range(ntex):
                while len(out) % 4:
                    out.append(0)
                at = len(out)
                out += mask_bytes(r.textures[t].data, r.textures[t].four_bit)
                struct.pack_into('<I', out, to + 12 * t + 4, at)
    copies = {}             # a placement's own copy of its (shared) LOD set
    for inst in insts:
        if inst.key not in first_ids:
            continue
        field = inst.field
        if inst.level:
            if inst.lod_field not in copies:
                so, n = inst.lod['off'], len(inst.lod['rows'])
                while len(out) % 4:
                    out.append(0)
                copies[inst.lod_field] = len(out)
                out += data[so:so + 8 + 16 * n]
                struct.pack_into('<I', out, inst.lod_field, copies[inst.lod_field])
            field = copies[inst.lod_field] + 8 + 16 * (inst.level - 1) + 12
        while len(out) % 4:
            out.append(0)
        at = len(out)
        cut = cutout_faces(texels, inst, meshes[inst.mesh], pack) if texels else ()
        args = (data, inst.mesh, meshes[inst.mesh], first_ids[inst.key])
        out += identity_mesh(*args, cut) if cut else identity_mesh(*args)
        struct.pack_into('<I', out, field, at)
    while len(out) % 4:
        out.append(0)
    struct.pack_into('<I', out, 8, len(out))
    return bytes(out)


# ---- the verification cart

CART = '''// Generated by the Mei World Kit (tools/worldkit/verify_render.py): the verification cart.
// Each view is drawn twice: from PACK (measured) and from IDPACK (the triangle-ID picture).
cart "World verification"
import "worldpack.akr"
{depth_import}
struct VView {{
    eye: vec4
    yaw: fixed
    pitch: fixed
    flags: u32          // bit 0: draw entity meshes{flag_note}
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
    ground: s32         // ground placements drawn
    coarse: s32         // placements drawn at a level of detail other than 0
    lod_culled: s32     // placements in view not drawn: past their LOD cull distance
    origin: vec4
    vp: mat4
}}

embed PACK: u8 = "pack.bin"
embed IDPACK: u8 = "idpack.bin"
embed VIEWS: VView = "views.bin"

var vout: VOut
var tick: s32
{region_vars}
// The entities' meshes by their own depth alone (runtime entity_drawing "mesh_at"); the default
// draws them with wp_draw_entities() (docs/WORLDPACK.md, "Objects").
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
    if k < 0 || k >= {frames} {{
        cls(0)
        return
    }}
    let v = &VIEWS[{view_of_k}]
    let ident = {ident}
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
    wp_ground_first = {ground_first}
    wp_object_bias = {object_bias}
    wp_object_squash = {object_squash}
    wp_lod = {lod}
    wp_lod_fine = {lod_fine}
    let nl = wp_layer_count()
    for l in 0..nl {{ wp_layer_set(l, false) }}
    for l in 0..nl {{
        if (v.on[l >> 5] >> ((l & 31) as u32)) & 1 != 0 {{ wp_layer_set(l, true) }}
    }}
{region_lines}    cls(0)
{depth_lines}    let eye = vec3(v.eye.x, v.eye.y, v.eye.z)
    let c0 = cycle_count()
    wp_draw(eye, v.yaw, v.pitch)
    let c1 = cycle_count()
    var ne = 0
    if v.flags & 1 != 0 {{
        if {objects} {{ ne = wp_draw_entities() }} else {{ ne = draw_entities(eye) }}
    }}
    let c2 = cycle_count()
    vout.view = {view_of_k}
    vout.draw_cycles = c1 - c0
    vout.entity_cycles = c2 - c1
    vout.arena_bytes = (__arena_ptr as s32) - (&__arena[0] as s32)
    vout.arena_left = (__arena_end as s32) - (__arena_ptr as s32)
    vout.near_cells = wp_stats.near_cells
    vout.placements = wp_stats.placements
    vout.drawn = wp_stats.drawn
    vout.standins = wp_stats.standins
    vout.entities = ne
    vout.ground = wp_stats.ground
    vout.coarse = wp_stats.coarse
    vout.lod_culled = wp_stats.lod_culled
    let o = wp_view_origin()
    vout.origin = vec4(o.x, o.y, o.z, 0.0)
    vout.vp = __vp
    if ident {{ vout.request = 3 }} else {{ vout.request = 1 }}
}}
{depth_init}'''


def fixed_literal(v):
    return f'{v:.7f}'


def view_record(view, layer_ids, entities, ident=False):
    on = [0] * 8
    for lid in layer_ids:
        on[lid >> 5] |= 1 << (lid & 31)
    eye = [round(c * ONE) for c in view['eye']]
    region = view.get('region')
    return struct.pack('<4i2iII8I', *eye, 0, round(view['yaw'] * ONE), round(view['pitch'] * ONE),
                       (1 if entities else 0) | (2 if ident else 0), 0 if region is None else region + 1, *on)


# How the cart walks its VIEWS records: in pairs (each view's measured frame, then its identity
# frame: run_cart()), or one frame a record, the record's flags bit 1 choosing the identity pack
# (run_frames(), depth mode's schedule).
PAIRED = dict(frames='2 * (len(VIEWS) as s32)', view_of_k='k >> 1', ident='(k & 1) == 1', flag_note='')
SINGLE = dict(frames='len(VIEWS) as s32', view_of_k='k', ident='v.flags & 2 != 0',
              flag_note=', bit 1: draw from IDPACK')


def _run(cmd, what, timeout=600):
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RenderError(f'{what}: {error}') from error
    if r.returncode:
        raise RenderError(f'{what} failed ({r.returncode}):\n' + (r.stderr + r.stdout).strip()[-3000:])
    return r


def swatch_rows(meshes):
    """The (texture slot, row) of every palette swatch face's texel in these meshes."""
    return sorted({(tex & 15, uv[0] >> 8) for m in meshes for flags, _, tex, _, uv in m.faces
                   if swatch_face(flags, tex, uv)})


def depth_init(rows):
    """Depth mode's init(): the swatch rows the measured frame's faces read filled with texel 1.
    The cart has the pack, not the world's swatch (NAME.swatch, which a game copies to VRAM), so
    those texels are otherwise 0, transparent: drawn but never depth-written, and no pixel behind
    them would fail the test as it does in the game. Their colour does not matter here."""
    if not rows:
        return ''
    return 'fn init() {\n' + ''.join(
        f'    mem_fill((VRAM_TEXTURES + {slot} * TEXTURE_SLOT_SIZE + {row * 128}) as *u8, 0x11, 128)\n'
        for slot, row in rows) + '}\n'


# A textured pack (runtime 'textured'): each view enters its camera cell's region (VView.reserved
# is the region + 1), as a game does with wp_region_enter(); identity frames load the identity
# pack's mask textures and make colour 1 white. The region is entered again only when it or the
# pack changes.
REGION_VARS = 'var entered: s32 = -1\nvar white: [2]u16\n'
REGION_LINES = '''    if v.reserved != 0 {{
        var want = (v.reserved as s32) * 2
        if ident {{ want += 1 }}
        if want != entered {{
            wp_region_enter((v.reserved - 1) as s32, 0)
            entered = want
        }}
        wp_region_loaded = (v.reserved - 1) as s32
        if ident {{
            white[1] = 0x7FFF
            load_palette(0, &white[0], 2)
        }}
    }}
'''


def _cart_source(runtime, rows, walk):
    near_far = runtime['near_far']
    depth, persp = runtime.get('depth', False), runtime.get('perspective', False)
    textured = runtime.get('textured', False)
    return CART.format(region_vars=REGION_VARS if textured else '',
                       region_lines=REGION_LINES.format() if textured else '',depth_import=DEPTH.cart_import(depth, persp),
                       depth_lines=DEPTH.cart_lines(depth, persp),
                       depth_init=depth_init(rows) if depth or persp else '',
                       far_ring=int(runtime['far_ring']),
                       clip_near=fixed_literal(runtime['clip_near']),
                       near_far=fixed_literal(near_far),
                       ground_first='true' if runtime['ground_first'] else 'false',
                       objects='true' if runtime['entity_drawing'] == 'object' else 'false',
                       object_bias=fixed_literal(runtime['object_bias']),
                       object_squash=int(runtime['object_squash']),
                       lod='true' if runtime['lod'] else 'false',
                       lod_fine='true' if runtime['lod_fine'] else 'false', **walk)


def _compile_and_run(pack_bytes, id_bytes, records, source, frames, tools, work):
    """Writes the cart's files into work, compiles the cart and runs it until `frames` frames
    after the first are presented. Returns (the capture's bytes, compile seconds, run seconds)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    (work / 'pack.bin').write_bytes(pack_bytes)
    (work / 'idpack.bin').write_bytes(id_bytes)
    (work / 'views.bin').write_bytes(records)
    (work / 'check.akr').write_text(source)
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
    _run([tools['probe'], work / 'check.mei', work / 'capture.bin', 1 + frames, symbols['G_vout'], OUT_SIZE],
         'running the verification cart')
    t2 = time.perf_counter()
    return (work / 'capture.bin').read_bytes(), t1 - t0, t2 - t1


def _records(cap, expected):
    """The recorded frames of a capture: [(stats, out, picture or None)]."""
    np = numpy()
    if cap[:4] != b'MSP2':
        raise RenderError('mei-scene-probe wrote no capture')
    count, size = struct.unpack_from('<II', cap, 4)
    if size != OUT_SIZE:
        raise RenderError('mei-scene-probe captured the wrong block size')
    at = 12
    records = []
    for _ in range(count):
        stats = dict(zip(STATS_NAMES, struct.unpack_from(f'<{STATS_WORDS}I', cap, at)))
        at += 4 * STATS_WORDS
        o = struct.unpack_from('<14i', cap, at)
        origin = struct.unpack_from('<4i', cap, at + 56)
        vp = struct.unpack_from('<16i', cap, at + 72)
        at += OUT_SIZE
        out = dict(request=o[0] & 0xFFFFFFFF, view=o[1], draw_cycles=o[2], entity_cycles=o[3],
                   arena_bytes=o[4], arena_left=o[5], near_cells=o[6], placements=o[7], drawn=o[8],
                   standins=o[9], entities=o[10], ground=o[11], coarse=o[12], lod_culled=o[13],
                   origin=[c / ONE for c in origin[:3]],
                   vp=np.array(vp, dtype=float).reshape(4, 4) / ONE)
        pic = None
        if out['request'] & 2:
            pic = np.frombuffer(cap, dtype='<u2', count=W * H, offset=at).astype(np.int32)
            at += 2 * W * H
        records.append((stats, out, pic))
    if len(records) != expected:
        raise RenderError(f'the verification cart recorded {len(records)} frames, expected {expected}')
    return records


def run_cart(pack_bytes, id_bytes, views, runtime, tools, work, rows=()):
    """Compiles the verification cart for these views (dicts with eye, yaw, pitch, layers, a
    list of layer ids) and runs it on mei-scene-probe. Returns ([(stats, out, picture or None)]
    per frame, timings). rows (depth mode): swatch_rows() of the meshes drawn."""
    records = b''.join(view_record(v, v['layers'], runtime['draw_entities']) for v in views)
    cap, tc, tr = _compile_and_run(pack_bytes, id_bytes, records, _cart_source(runtime, rows, PAIRED),
                                   2 * len(views), tools, work)
    return _records(cap, 2 * len(views)), {'compile_seconds': tc, 'run_seconds': tr}


def run_frames(pack_bytes, id_bytes, frames, runtime, tools, work, rows=(), jobs=1):
    """Depth mode's schedule: one recorded frame for each (view, ident) of frames, from IDPACK
    with its picture where ident is true, else from PACK (measured). With jobs > 1 the frames
    are cut into up to that many runs of the probe, side by side, each with its own cart: every
    frame opens the pack afresh and clears, so what a frame records does not depend on the frames
    before it. Returns ([(stats, out, picture or None)] per frame, in order, and the timings
    summed over the runs)."""
    if not frames:
        return [], {'compile_seconds': 0.0, 'run_seconds': 0.0}
    source = _cart_source(runtime, rows, SINGLE)
    n = max(1, min(jobs, len(frames) // 16))
    cuts = [len(frames) * k // n for k in range(n + 1)]

    def one(k):
        part = frames[cuts[k]:cuts[k + 1]]
        records = b''.join(view_record(v, v['layers'], runtime['draw_entities'], ident) for v, ident in part)
        cap, tc, tr = _compile_and_run(pack_bytes, id_bytes, records, source, len(part), tools,
                                       Path(work) / f'run{k}')
        return _records(cap, len(part)), tc, tr
    if n == 1:
        done = [one(0)]
    else:
        with ThreadPoolExecutor(n) as pool:
            done = list(pool.map(one, range(n)))
    return ([r for recs, _, _ in done for r in recs],
            {'compile_seconds': sum(d[1] for d in done), 'run_seconds': sum(d[2] for d in done)})


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


def select(pack, by_cell, eye, vp, layers_on, runtime, region=None):
    """What wp_draw() (and the cart's entity loop) draws from eye: a list of (instance, pass,
    certain), certain False where a culling sphere is too close to a plane to say. The pass is
    'far', 'ground' (a ground placement, when the runtime draws ground first) or 'near'."""
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
    # levels of detail, as the reader chooses them: from a fresh frame (the cart opens the pack for
    # every view), by the plain distances, or the finest the band allows (runtime lod_fine)
    eye_raw = [round(c * ONE) for c in eye]
    eye_local = (eye_raw[0] - ((ci << pack.cell_shift) * ONE + round(half * ONE)), eye_raw[1],
                 eye_raw[2] - ((cj << pack.cell_shift) * ONE + round(half * ONE)))
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            c = pack.cells.get((ci + di, cj + dj))
            if c is None:
                continue
            mask = cell_mask(pack, c, layers_on)
            if region is not None and c.region != region:
                # wp_region_loaded: a near cell of another region draws its stand-in, near
                for inst in by_cell.get((ci + di, cj + dj), ()):
                    if inst.key[0] == 'standin':
                        s = inst.sphere
                        v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                        if v is not False:
                            out.append((inst, 'near', v is True))
                    elif inst.key[0] == 'entity' and runtime['draw_entities']:
                        v = True
                        if runtime['entity_drawing'] == 'object':
                            s = inst.sphere
                            v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                        if v is not False:
                            out.append((inst, 'near', v is True))
                continue
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
                        v = True
                        if runtime['entity_drawing'] == 'object':      # wp_draw_entities() culls
                            s = inst.sphere
                            v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                        if v is not False:
                            out.append((inst, 'near', v is True))
                elif kind == 'placement' and cv is not False:
                    s = inst.sphere
                    if inst.lod is not None:
                        level = 0
                        if runtime['lod']:
                            d2 = lod_d2(s, eye_local, (di * S * ONE, 0, dj * S * ONE))
                            level = lod_level(inst.lod['rows'], d2, fine=runtime['lod_fine'])
                        if level != inst.level:
                            continue
                    v = _sphere(planes, (s[0] / ONE + di * S, s[1] / ONE, s[2] / ONE + dj * S), s[3] / ONE)
                    if v is not False:
                        pas = 'ground' if inst.ground and runtime['ground_first'] else 'near'
                        out.append((inst, pas, v is True and cv is True))
    return out


@dataclass
class Face:
    id: int
    inst: object
    index: int          # the face's number in its mesh
    pass_: str          # 'far', 'ground' or 'near' (PASSES)
    poly: object        # screen polygon (k, 2), centred on the runtime's rounding
    plane: tuple        # (N, D): depth w = D / (N . (u, v, 1))
    definite: bool      # drawn for certain and checkable: may be the expected face
    tol: float
    texel: object = None    # a face with holes: (clip corners, texture coordinates, tile, window)


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


def _next(a):
    """np.roll(a, -1) of a short 1-D array, without its overhead."""
    return numpy().concatenate((a[1:], a[:1]))


def _cross(a, b):
    """np.cross() of two 3-vectors, with the same operations, without its overhead."""
    return numpy().array((a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]))


def view_faces(pack, meshes, view_insts, vp, origin, first_ids, near_planes, texels=None, region=None):
    """Faces (screen polygons with depth planes) of the instances a view draws. view_insts is a
    list of (instance, pass, certain). texels: pack_texels() of a textured pack, and region the
    region the view entered: a textured face is checked whole when its texture has no holes,
    per texel when it has (Face.texel), and not at all in a cell of another region."""
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
        tx = texels.get(pack.cells[inst.cell].region) if texels and pack.cells[inst.cell].region == region else None
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
            xs1, ys1 = _next(xs), _next(ys)
            area = 0.5 * float(np.sum(xs * ys1 - xs1 * ys))
            perim = float(np.sum(np.hypot(xs1 - xs, ys1 - ys)))
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
            nrm = _cross(a1 - a0, a2 - a0)
            d = float(nrm @ a0)
            tol = 0.0
            if len(idx) == 4:
                w3 = world[idx[3], :3]
                w0, w1, w2 = (world[i, :3] for i in idx[:3])
                wn = _cross(w1 - w0, w2 - w0)
                ln = float(np.linalg.norm(wn))
                if ln > 0:
                    tol = abs(float((w3 - w0) @ wn)) / ln
            ok = checkable(flags, tex, uv)
            texel = None
            if not ok and tx is not None and not flags & FACE_SEMI and len(idx) == 3:
                ok = True
                if not tx.solid(tex, uv, mesh.windows):
                    tile, win = tx.tile(tex, uv, mesh.windows)
                    texel = (np.array([cxyw[i] for i in idx]), np.array([(c & 255, c >> 8) for c in uv], dtype=float),
                             tile, win)
            faces.append(Face(first + k, inst, k, pas, scr, (nrm, d),
                              certain and not thin and convex and abs(d) > 1e-12 and ok, tol, texel))
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
    area = float(np.sum(xs * _next(ys) - _next(xs) * ys))
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
    def __init__(self, depth=None):
        """depth: (key tolerance, snap pixels) in depth mode (kitcore/depth.py), else None."""
        np = numpy()
        self.depth = depth
        if depth:
            # the two nearest depths each face may have at a pixel (its depth less half a
            # pixel's worth of its slope), the nearest one's face, and the expected face's
            # farthest (its depth plus the key's tolerance and its own slope allowance)
            self.lo1 = np.full(W * H, np.inf)
            self.loid = np.zeros(W * H, dtype=np.int32)
            self.lo2 = np.full(W * H, np.inf)
            self.hi = np.full(W * H, np.inf)
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
        sure = None
        if f.texel is not None:
            full, empty = texel_classes(f.texel, pix)
            keep = ~empty
            pix, inside, z, sure = pix[keep], inside[keep], z[keep], full[keep]
        # maybe-coverage: nearest and second nearest depth
        nearer = z < self.m1[pix]
        p2 = pix[nearer]
        if not self.depth:          # depth mode decides by the lo depths below instead
            self.m2[p2] = self.m1[p2]
        self.m1[p2] = z[nearer]
        self.mid[p2] = f.id
        if not self.depth:
            rest = ~nearer & (z < self.m2[pix])
            self.m2[pix[rest]] = z[rest]
        if self.depth:
            key, snap = self.depth
            nrm, d = f.plane
            # 1/w = (N . (u, v, 1)) / D, u = (x - 159.5) / 160, v = (119.5 - y) / 120: its change a pixel
            # (an edge-on face, d = 0, has no depth: _face_pixels() counts it nearest, and the
            # pixel is undecided by the nearest-face test below)
            slope = (abs(nrm[0]) / 160 + abs(nrm[1]) / 120) / abs(d) if d else 0.0
            spread = z * z * snap * slope
            lo = z - spread
            nearer = lo < self.lo1[pix]
            p2 = pix[nearer]
            self.lo2[p2] = self.lo1[p2]
            self.lo1[p2] = lo[nearer]
            self.loid[p2] = f.id
            rest = ~nearer & (lo < self.lo2[pix])
            self.lo2[pix[rest]] = lo[rest]
        if f.definite:
            rob = (inside >= margin) & (z < self.r1[pix])
            if sure is not None:
                rob &= sure
            pr = pix[rob]
            self.r1[pr] = z[rob]
            self.rid[pr] = f.id
            self.tol[pr] = f.tol
            if self.depth:
                self.hi[pr] = z[rob] * (1 + key) + spread[rob]

    def expected(self, eps):
        """(expected ID per pixel, -1 where undecided; covered: some face may cover it)."""
        np = numpy()
        covered = np.isfinite(self.m1)
        if self.depth:
            other = np.where(self.loid == self.rid, self.lo2, self.lo1)
            decided = np.isfinite(self.r1) & (self.mid == self.rid) & (other > self.hi + eps + self.tol)
        else:
            decided = np.isfinite(self.r1) & (self.mid == self.rid) & (self.m2 > self.r1 + eps + self.tol)
        exp = np.where(decided, self.rid, -1)
        exp = np.where(covered, exp, 0)
        return exp.astype(np.int32), covered


def _alpha(corners, a, b):
    """Barycentric weights (n, 3), true in 3D (so perspective-correct), of the points of the
    triangle with clip corners (x, y, w) seen at NDC (a, b)."""
    np = numpy()
    A = corners[None, :, 0] - a[:, None] * corners[None, :, 2]
    B = corners[None, :, 1] - b[:, None] * corners[None, :, 2]
    c = np.stack((A[:, 1] * B[:, 2] - A[:, 2] * B[:, 1], A[:, 2] * B[:, 0] - A[:, 0] * B[:, 2],
                  A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0]), axis=1)
    s = c.sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        return c / s[:, None]


def texel_classes(texel, pix):
    """For pixels of a face with holes: (sure to sample a set texel, sure to sample texel 0).
    The texel the GPU samples is taken as anywhere within one texel plus one and a half pixels'
    worth of texture coordinates of the true (perspective-correct) coordinate at the pixel's
    centre: the GPU's spans divide every 16th pixel and step between, and its vertices are whole
    pixels. A pixel whose box holds both kinds is neither."""
    np = numpy()
    corners, uv, tile, win = texel
    px, py = pix % W, pix // W
    a, b = (px + 0.5 - 160) / 160, (120 - py - 0.5) / 120
    t0 = _alpha(corners, a, b) @ uv
    tx = _alpha(corners, a + 2 / W, b) @ uv
    ty = _alpha(corners, a, b - 2 / H) @ uv
    reach = 1 + 1.5 * np.nan_to_num(np.maximum(np.abs(tx - t0).max(axis=1), np.abs(ty - t0).max(axis=1)), nan=1e9)
    reach = np.minimum(reach, 1e6)
    t0 = np.nan_to_num(t0, nan=0.0)
    h, w = tile.shape
    if win:
        su, sv = win
        big = np.tile(tile, (3, 3))
        ou, ov = np.floor(t0[:, 0]) // su * su - su, np.floor(t0[:, 1]) // sv * sv - sv
        u0, u1 = np.floor(t0[:, 0] - reach) - ou, np.floor(t0[:, 0] + reach) - ou
        v0, v1 = np.floor(t0[:, 1] - reach) - ov, np.floor(t0[:, 1] + reach) - ov
        wide = (u1 - u0 + 1 > su) | (v1 - v0 + 1 > sv)
        src = big
    else:
        u0, u1 = np.floor(t0[:, 0] - reach), np.floor(t0[:, 0] + reach)
        v0, v1 = np.floor(t0[:, 1] - reach), np.floor(t0[:, 1] + reach)
        wide = np.zeros(len(pix), dtype=bool)
        src = tile
    sh, sw = src.shape
    sat = np.zeros((sh + 1, sw + 1), dtype=np.int64)
    sat[1:, 1:] = src.astype(np.int64).cumsum(0).cumsum(1)
    cu0, cu1 = np.clip(u0, 0, sw - 1).astype(np.int64), np.clip(u1, 0, sw - 1).astype(np.int64)
    cv0, cv1 = np.clip(v0, 0, sh - 1).astype(np.int64), np.clip(v1, 0, sh - 1).astype(np.int64)
    count = sat[cv1 + 1, cu1 + 1] - sat[cv0, cu1 + 1] - sat[cv1 + 1, cu0] + sat[cv0, cu0]
    area = (cu1 - cu0 + 1) * (cv1 - cv0 + 1)
    full = (count == area) & ~wide
    empty = (count == 0) & ~wide
    return full, empty


PASSES = ('far', 'ground', 'near')     # the reader's passes in drawing order, each over the last


def compare_view(faces, actual, settings):
    """The ordering check of one view: actual is the ID picture (0 = nothing drawn). With
    settings['depth'] (depth mode) every face is judged in one pass, the near pass, by its depth
    with the depth key's tolerance."""
    np = numpy()
    margin = settings['edge_margin']
    eps = settings['depth_epsilon']
    tol_extra = max((f.tol for f in faces), default=0.0)
    depth = (DEPTH.KEY_TOLERANCE, DEPTH.SNAP_PIXELS) if settings.get('depth') else None
    if depth:
        # one pass: the far and ground passes, and the inversions between passes, do not exist
        passes = {'near': _Pass(depth)}
        faces = [Face(f.id, f.inst, f.index, 'near', f.poly, f.plane, f.definite, f.tol, f.texel) for f in faces]
    else:
        passes = {name: _Pass() for name in PASSES}
    for f in faces:
        passes[f.pass_].add(f, margin)
    # each pixel's expected face comes from the last pass that may cover it (its top pass)
    expected = np.zeros(W * H, dtype=np.int32)
    depth_e = np.full(W * H, np.inf)
    top = np.full(W * H, -1, dtype=np.int32)
    for rank, name in enumerate(PASSES):
        if name not in passes:
            continue
        exp_p, cov_p = passes[name].expected(eps + tol_extra)
        expected = np.where(cov_p, exp_p, expected)
        depth_e = np.where(cov_p, passes[name].r1, depth_e)
        top = np.where(cov_p, rank, top)
    rank_of = {name: rank for rank, name in enumerate(PASSES)}
    by_id = {f.id: f for f in faces}
    tested = expected >= 0
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
            if z is None or e == 0 or rank_of[f.pass_] < top[p]:
                coverage[p] = True          # an earlier pass's face over a later pass's
            elif z > depth_e[p] + eps + tol_extra:
                wrong[p] = True
                drawn_depth[p] = z
            else:
                coverage[p] = True
    # Inversions of the pass design, at pixels drawn as designed: a face of an earlier pass that
    # surely covers the pixel and is truly nearer than the later pass's expected face. Stand-ins
    # in front of ground or near geometry; ground in front of the near pass (ground-first drawing
    # puts what stands on the ground over it, so whatever the ground truly hides shows through).
    if depth:
        none = np.zeros(W * H, dtype=bool)
        inversion = ground_inv = none
        ground_id, ground_depth = np.zeros(W * H, dtype=np.int32), np.full(W * H, np.inf)
    else:
        sure = tested & (actual == expected) & (expected > 0)
        far, ground = passes['far'], passes['ground']
        inversion = sure & (top > rank_of['far']) & (far.r1 < depth_e - eps - tol_extra)
        ground_inv = sure & (top == rank_of['near']) & (ground.r1 < depth_e - eps - tol_extra)
        ground_id, ground_depth = ground.rid, ground.r1
    covered = top >= 0
    return dict(expected=expected, tested=tested, wrong=wrong, coverage=coverage, depth=depth_e,
                drawn_depth=drawn_depth, inversion=inversion, ground_inversion=ground_inv,
                ground_id=ground_id, ground_depth=ground_depth, ambiguous=(~tested) & covered,
                by_id=by_id, covered=covered)


def entity_pixels(faces, cmp, actual):
    """Entity faces in one view: the pixels the runtime drew with them and how many of those the
    check decided; wrong-order pixels where an entity was drawn over a face truly in front of it,
    and where something was drawn over an entity truly in front of it."""
    np = numpy()
    ids = np.array(sorted(f.id for f in faces if f.inst.key[0] == 'entity'), dtype=np.int32)
    drawn = np.isin(actual, ids)
    wrong = cmp['wrong']
    return {'entity_pixels': int(drawn.sum()), 'entity_pixels_tested': int((drawn & cmp['tested']).sum()),
            'entity_over_nearer_pixels': int((wrong & drawn).sum()),
            'over_entity_pixels': int((wrong & ~drawn & np.isin(cmp['expected'], ids)).sum())}


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


def ground_witnesses(cmp, describe, limit):
    """Ground inversions grouped by (ground face, the face drawn over it), largest first."""
    np = numpy()
    inv = cmp['ground_inversion']
    if not inv.any():
        return []
    pairs = {}
    for p in np.flatnonzero(inv).tolist():
        g, e = int(cmp['ground_id'][p]), int(cmp['expected'][p])
        rec = pairs.setdefault((g, e), dict(count=0, sample=p, gap=0.0, depth=float('inf')))
        rec['count'] += 1
        rec['gap'] = max(rec['gap'], float(cmp['depth'][p] - cmp['ground_depth'][p]))
        rec['depth'] = min(rec['depth'], float(cmp['ground_depth'][p]))
    out = []
    for (g, e), rec in sorted(pairs.items(), key=lambda kv: (-kv[1]['count'], kv[0]))[:limit]:
        p = rec['sample']
        out.append({'code': 'ground_inversion', 'pixels': rec['count'], 'ground': describe(cmp['by_id'][g]),
                    'drawn': describe(cmp['by_id'][e]), 'sample_pixel': [p % W, p // W],
                    'ground_depth': round(rec['depth'], 4), 'max_depth_behind': round(rec['gap'], 4)})
    return out


def diagnostic_image(cmp, actual):
    np = numpy()
    exp = np.where(cmp['tested'], cmp['expected'], 0) - 1
    act = actual.astype(np.int64) - 1
    return diagnostic_png(exp.astype(np.int64), act, cmp['wrong'] | cmp['coverage'] | cmp['ground_inversion'])
