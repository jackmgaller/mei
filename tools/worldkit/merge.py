"""Merges small static props of a cell into one native mesh, placed at the cell centre.

The reader spends about 500 cycles on every placement it draws, beyond its vertices and faces
(WORLDPACK.md, "Costs"), so a hundred tiny props cost 50,000 cycles before a face is drawn. A
merged mesh is drawn once: ROM grows (each prop's vertices are stored again, turned and moved),
CPU falls. Faces keep their order, flags, colours and texture words, so palette faces stay
palette faces. The pack needs no new record: a merged mesh is an ordinary placement at the cell
centre with yaw 0, the way a terrain piece would be. Culling becomes coarser (one sphere for all
the props in a layer), so merge only what is small and close together.
"""
import math
import struct

import meshlib

MAX_VERTICES = 2048
MAX_FACES = 4000


def parts(binary):
    nv, nf, vo, fo, _ = struct.unpack_from('<HHIII', binary)
    verts = [struct.unpack_from('<3i', binary, vo + 16 * k) for k in range(nv)]
    faces = [bytearray(binary[fo + 36 * k:fo + 36 * k + 36]) for k in range(nf)]
    return verts, faces


def place(raw, position, yaw, centre):
    """A raw 16.16 model vertex turned by yaw (mesh_at's convention) and moved to the position,
    relative to centre, in units."""
    x, y, z = (c / 65536 for c in raw)
    if yaw % 90 == 0:
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][int(yaw // 90) % 4]
    else:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (x * c + z * s + position[0] - centre[0], y + position[1] - centre[1], -x * s + z * c + position[2] - centre[2])


def merge(items, centre):
    """items: [(mesh bytes, world position, yaw)] -> [mesh bytes], each within the mesh limits, in
    order, splitting between props (never inside one)."""
    out = []
    verts, faces = [], []

    def flush():
        if not faces: return
        head = struct.pack('<HHIII', len(verts), len(faces), 16, 16 + 16 * len(verts), 0)
        body = b''.join(struct.pack('<4i', *(meshlib.fx(c) for c in v), 65536) for v in verts)
        out.append(head + body + b''.join(bytes(f) for f in faces))
        verts.clear()
        faces.clear()

    for binary, position, yaw in items:
        pv, pf = parts(binary)
        if len(verts) + len(pv) > MAX_VERTICES or len(faces) + len(pf) > MAX_FACES:
            flush()
        base = len(verts)
        verts.extend(place(v, position, yaw, centre) for v in pv)
        for f in pf:
            idx = struct.unpack_from('<4H', f, 4)
            n = 4 if f[0] & 4 else 3
            struct.pack_into('<4H', f, 4, *[(i + base if k < n else 0) for k, i in enumerate(idx)])
            faces.append(f)
    flush()
    return out
