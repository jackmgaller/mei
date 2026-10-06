"""The World Checker's occlusion check (docs/WORLDCHECKER.md, "Occlusion").

A pack 1.5 says, per occlusion zone, which placements and stand-ins the reader skips while the
eye is in the zone. The World Kit decided that from the occluders the recipe declares; whether
those occluders are truly solid is the author's claim. This check tests the claim against what is
drawn: from sample points of each zone (its corners, a hair inside, its centre and the centres of
its faces) it casts a ray to sample points of each hidden thing (the vertices of each of its
levels and the centres of its faces, up to `rays_per_target`), and counts the rays that reach the
point without first crossing a face that is drawn there and hides what is behind it: a face of
a placement of the zone's near cells that the zone does not hide, present with the zone's layer
on and every other layer off, facing the eye (or double-sided), not semi-transparent, and either
untextured, a swatch, or textured with no texel 0 in its tile (a hole). Each placement is taken
at the finest and at the coarsest level the hysteresis band allows from that eye, and a ray must
be stopped in both. A ray that is not stopped is a leak: from that eye the hidden thing may be
in sight, and the reader would leave a hole there.

It is a sampled check (between the samples a gap can still show); the views' pixel comparison is
judged against what is in sight whatever the zones (verify_render.select(occlusion=False)), so a
zone that hides something a sampled view sees is found there too.
"""
import math
import struct

from .pack import ONE, ZONE_FAR, lod_level, lod_d2
from . import verify_render as RD
from .verify_shared import numpy

EPS_T = 1e-6            # a hit must be this much (of the ray) before the target point
EPS_BARY = 1e-6         # rays through a shared edge are stopped by either face


class _Meshes:
    """Each mesh's triangles (index triples, quads split as the GPU splits them) and per region
    which of them can stop a ray (opaque) and which are double-sided."""

    def __init__(self, pack, texels):
        self.pack, self.texels, self.cache, self.solid = pack, texels, {}, {}

    def get(self, off):
        if off not in self.cache:
            np = numpy()
            m = RD.read_mesh(self.pack.data, off)
            tris, face = [], []
            for k, (flags, idx, tex, pal, uv) in enumerate(m.faces):
                tris.append(idx[:3])
                face.append(k)
                if len(idx) == 4:
                    tris.append((idx[2], idx[1], idx[3]))
                    face.append(k)
            self.cache[off] = (m, np.array(m.raw, dtype=float).reshape(-1, 3) / ONE,
                               np.array(tris, dtype=int).reshape(-1, 3), np.array(face, dtype=int))
        return self.cache[off]

    def opaque(self, off, region):
        key = (off, region)
        if key not in self.solid:
            np = numpy()
            m, _, _, face = self.get(off)
            tx = self.texels.get(region) if self.texels else None
            ok, double = [], []
            for flags, idx, tex, pal, uv in m.faces:
                o = not flags & RD.FACE_SEMI
                if o and flags & RD.FACE_TEXTURED and not RD.swatch_face(flags, tex, uv):
                    o = tx is not None and tx.solid(flags, tex, uv, m.windows)
                ok.append(o)
                double.append(bool(flags & RD.FACE_DOUBLE))
            ok, double = np.array(ok, dtype=bool), np.array(double, dtype=bool)
            self.solid[key] = (ok[face] if len(face) else ok[:0], double[face] if len(face) else double[:0])
        return self.solid[key]


def _world(pack, cell, pos, cos, sin, verts):
    S = 1 << pack.cell_shift
    c, s = cos / ONE, sin / ONE
    px, py, pz = cell[0] * S + S / 2 + pos[0] / ONE, pos[1] / ONE, cell[1] * S + S / 2 + pos[2] / ONE
    np = numpy()
    return np.column_stack((c * verts[:, 0] + s * verts[:, 2] + px, verts[:, 1] + py,
                            -s * verts[:, 0] + c * verts[:, 2] + pz))


def _eyes(lo, hi):
    """Sample eyes of a zone box: its corners a hair inside, its centre, its faces' centres."""
    inset = [min(1e-3, (b - a) / 4) for a, b in zip(lo, hi)]
    a = [lo[k] + inset[k] for k in range(3)]
    b = [hi[k] - inset[k] for k in range(3)]
    m = [(lo[k] + hi[k]) / 2 for k in range(3)]
    out = [(b[0] if k & 1 else a[0], b[1] if k & 2 else a[1], b[2] if k & 4 else a[2]) for k in range(8)]
    out.append(tuple(m))
    for ax in range(3):
        for side in (a, b):
            p = list(m)
            p[ax] = side[ax]
            out.append(tuple(p))
    return out


def _stopped(np, eye, pts, tri):
    """For each target point, whether the segment eye -> point crosses one of the triangles (n, 3, 3)
    before the point (Moller-Trumbore, every pair)."""
    if len(tri) == 0:
        return np.zeros(len(pts), dtype=bool)
    out = np.zeros(len(pts), dtype=bool)
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    s = eye - tri[:, 0]                                   # (n, 3)
    q = np.cross(s, e1)                                   # (n, 3)
    step = max(1, 400000 // len(tri))
    for k0 in range(0, len(pts), step):
        d = pts[k0:k0 + step] - eye                       # (r, 3)
        p = np.cross(d[:, None, :], e2[None, :, :])       # (r, n, 3)
        det = np.einsum('rnk,nk->rn', p, e1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        u = np.einsum('rnk,nk->rn', p, s) * inv
        v = np.einsum('rk,nk->rn', d, q) * inv
        t = np.einsum('nk,nk->n', e2, q)[None, :] * inv
        hit = ok & (u >= -EPS_BARY) & (v >= -EPS_BARY) & (u + v <= 1 + EPS_BARY) & (t > EPS_T) & (t < 1 - EPS_T)
        out[k0:k0 + step] = hit.any(axis=1)
    return out


def check(pack, settings, only=None, names=None):
    """The occlusion check of a pack 1.5's zones (only: the zones of these cells). Returns the
    report's static entry: zones, hidden things, rays, leaks and the first leaks found."""
    np = numpy()
    S = 1 << pack.cell_shift
    rays_per = settings.get('rays_per_target', 48)
    limit = settings.get('findings', 20)
    meshes = _Meshes(pack, RD.pack_texels(pack) if any(r.textures for r in pack.regions) else None)
    pl_names = (names or {}).get('placements', {})
    placed = {}                 # (cell, k, level) -> world triangles (n, 3, 3), opaque, double, box

    def tris_of(key, k, level):
        if (key, k, level) not in placed:
            c = pack.cells[key]
            p = c.placements[k]
            off = p['mesh'] if level == 0 else p['lod']['rows'][level - 1][3]
            if not off:
                placed[(key, k, level)] = None
                return None
            _, verts, tri, _ = meshes.get(off)
            w = _world(pack, key, p['pos'], p['cos'], p['sin'], verts)
            t = w[tri] if len(tri) else np.zeros((0, 3, 3))
            ok, double = meshes.opaque(off, c.region)
            placed[(key, k, level)] = (t[ok], double[ok])
        return placed[(key, k, level)]

    def targets(key, k):
        """Sample points of every level of placement k of cell key."""
        p = pack.cells[key].placements[k]
        offs = [p['mesh']] + [r[3] for r in (p['lod']['rows'] if p['lod'] else ()) if r[3]]
        pts = []
        for off in offs:
            _, verts, tri, _ = meshes.get(off)
            w = _world(pack, key, p['pos'], p['cos'], p['sin'], verts)
            pts.append(w)
            if len(tri):
                pts.append(w[tri].mean(axis=1))
        pts = np.unique(np.round(np.concatenate(pts), 6), axis=0)
        if len(pts) > rays_per:
            pts = pts[np.linspace(0, len(pts) - 1, rays_per).astype(int)]
        return pts

    def standin_targets(key):
        c = pack.cells[key]
        _, verts, _, _ = meshes.get(c.standin)
        w = _world(pack, key, (0, 0, 0), ONE, 0, verts)
        if len(w) > rays_per:
            w = w[np.linspace(0, len(w) - 1, rays_per).astype(int)]
        return w

    out = {'zones': 0, 'hidden_placements': 0, 'hidden_standins': 0, 'rays': 0, 'leaks': 0, 'findings': []}
    for key in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        if only is not None and key not in only:
            continue
        cell = pack.cells[key]
        for zn, z in enumerate(cell.zones):
            out['zones'] += 1
            lo = (key[0] * S + S / 2 + z['lo'][0] / ONE, z['lo'][1] / ONE, key[1] * S + S / 2 + z['lo'][2] / ONE)
            hi = (key[0] * S + S / 2 + z['hi'][0] / ONE, z['hi'][1] / ONE, key[1] * S + S / 2 + z['hi'][2] / ONE)
            things = [(('placement', hk, k), targets(hk, k)) for hk, ks in sorted(z['hidden'].items()) for k in sorted(ks)]
            side = 2 * ZONE_FAR + 1
            for b in range(side * side):
                if z['far'] >> b & 1:
                    sk = (key[0] + b % side - ZONE_FAR, key[1] + b // side - ZONE_FAR)
                    things.append((('standin', sk), standin_targets(sk)))
            out['hidden_placements'] += sum(len(ks) for ks in z['hidden'].values())
            out['hidden_standins'] += bin(z['far']).count('1')
            # the blockers: what the zone's near cells draw and the zone does not hide
            blockers = []
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    nk = (key[0] + di, key[1] + dj)
                    c = pack.cells.get(nk)
                    if c is None:
                        continue
                    hid = z['hidden'].get(nk, ())
                    for k, p in enumerate(c.placements):
                        if k in hid:
                            continue
                        if p['mask'] and (z['layer'] is None or c.layers[p['mask'].bit_length() - 1] != z['layer']):
                            continue
                        blockers.append((nk, k, p))
            for eye in _eyes(lo, hi):
                eye_np = np.array(eye)
                (ek, elx, elz) = pack.cell_of(round(eye[0] * ONE), round(eye[2] * ONE))
                sets = {}
                for mode in ('fine', 'coarse'):
                    ts, ds = [], []
                    for nk, k, p in blockers:
                        level = 0
                        if p['lod']:
                            eye_local = (elx, round(eye[1] * ONE), elz)
                            d2 = lod_d2(p['sphere'], eye_local, ((nk[0] - ek[0]) * S * ONE, 0, (nk[1] - ek[1]) * S * ONE))
                            level = lod_level(p['lod']['rows'], d2, fine=True) if mode == 'fine' else \
                                lod_level(p['lod']['rows'], d2, 99)
                        got = tris_of(nk, k, level)
                        if got is not None and len(got[0]):
                            ts.append(got[0])
                            ds.append(got[1])
                    t = np.concatenate(ts) if ts else np.zeros((0, 3, 3))
                    d = np.concatenate(ds) if ds else np.zeros(0, dtype=bool)
                    # facing the eye: the mesh winding's front side, (c - a) x (b - a)
                    n = np.cross(t[:, 2] - t[:, 0], t[:, 1] - t[:, 0])
                    front = d | (np.einsum('nk,nk->n', n, eye_np - t[:, 0]) > 0)
                    t = t[front]
                    sets[mode] = (t, t.min(axis=1), t.max(axis=1))
                for what, pts in things:
                    lo_b = np.minimum(pts.min(axis=0), eye_np) - 1e-3
                    hi_b = np.maximum(pts.max(axis=0), eye_np) + 1e-3
                    stopped = np.ones(len(pts), dtype=bool)
                    for t, tmin, tmax in sets.values():
                        sel = np.all(tmax >= lo_b, axis=1) & np.all(tmin <= hi_b, axis=1)
                        stopped &= _stopped(np, eye_np, pts, t[sel])
                    out['rays'] += len(pts)
                    leaks = int((~stopped).sum())
                    if leaks:
                        out['leaks'] += leaks
                        if len(out['findings']) < limit:
                            f = {'code': 'occlusion_leak', 'cell': list(key), 'zone': zn,
                                 'eye': [round(c, 3) for c in eye],
                                 'point': [round(float(c), 3) for c in pts[int(np.flatnonzero(~stopped)[0])]],
                                 'rays': len(pts), 'leaks': leaks}
                            if what[0] == 'placement':
                                p = pack.cells[what[1]].placements[what[2]]
                                f['hidden'] = {'kind': 'placement', 'cell': list(what[1]), 'placement': what[2],
                                               'tag': p['tag']}
                                if str(p['tag']) in pl_names:
                                    f['hidden']['name'] = pl_names[str(p['tag'])]
                            else:
                                f['hidden'] = {'kind': 'standin', 'cell': list(what[1])}
                            out['findings'].append(f)
    return out
