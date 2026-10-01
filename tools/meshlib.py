"""Writes meshes in the Mei binary mesh format (docs/LANGUAGE.md, "Mesh format").

    m = Mesh()
    a = m.vertex(x, y, z)                         # floats, world units
    m.quad([a, b, c, d], colours, uvs, flags)     # strip order: a-b-c and b-c-d
    m.tri([a, b, c], colours, uvs, flags)
    open('x.bin', 'wb').write(m.pack())

Front faces are counter-clockwise as seen by the viewer (for quads: the first triangle)."""
import struct

GOURAUD, TEXTURED, QUAD, SEMI, DOUBLE = 1, 2, 4, 8, 16

def fx(v):
    return int(round(v * 65536))

class Mesh:
    def __init__(self):
        self.verts = []
        self.faces = []

    def vertex(self, x, y, z):
        self.verts.append((x, y, z))
        return len(self.verts) - 1

    def face(self, idx, colours, uvs=None, flags=0, slot=0, four_bit=False, palette=0, blend=0):
        n = len(idx)
        if n == 4:
            flags |= QUAD
        if uvs:
            flags |= TEXTURED
        if len(set(colours)) > 1:
            flags |= GOURAUD
        colours = list(colours) + [colours[-1]] * (4 - len(colours))
        idx = list(idx) + [0] * (4 - n)
        uvs = list(uvs or []) + [(0, 0)] * (4 - len(uvs or []))
        tex = (slot & 15) | (16 if four_bit else 0)
        self.faces.append(struct.pack('<BBBB4H4I4H', flags, blend, tex, palette, *idx,
                                      *colours, *[(u & 255) | ((v & 255) << 8) for u, v in uvs]))

    def quad(self, idx, colours, uvs=None, flags=0, **kw):
        assert len(idx) == 4
        self.face(idx, colours, uvs, flags, **kw)

    def tri(self, idx, colours, uvs=None, flags=0, **kw):
        assert len(idx) == 3
        self.face(idx, colours, uvs, flags, **kw)

    def pack(self):
        assert len(self.verts) <= 2048
        head = struct.pack('<HHIII', len(self.verts), len(self.faces), 16, 16 + 16 * len(self.verts), 0)
        verts = b''.join(struct.pack('<4i', fx(x), fx(y), fx(z), 65536) for x, y, z in self.verts)
        return head + verts + b''.join(self.faces)

def rgb(r, g, b):
    return (r & 255) | ((g & 255) << 8) | ((b & 255) << 16)
