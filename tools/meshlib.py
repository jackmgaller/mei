"""Writes meshes in the Mei binary mesh format (docs/LANGUAGE.md, "Mesh format").

    m = Mesh()
    a = m.vertex(x, y, z)                         # floats, world units
    m.quad([a, b, c, d], colours, uvs, flags)     # strip order: a-b-c and b-c-d
    m.tri([a, b, c], colours, uvs, flags)
    w = m.window(u=(16, 32), v=(16, 64))          # a texture window: (size, origin) per axis
    m.quad([a, b, c, d], colours, uvs, slot=3, window=w)
    open('x.bin', 'wb').write(m.pack())

Front faces are counter-clockwise as seen by the viewer (for quads: the first triangle).
A mesh with no windows packs exactly as before windows existed (no table, header +12 zero)."""
import struct

GOURAUD, TEXTURED, QUAD, SEMI, DOUBLE = 1, 2, 4, 8, 16

def fx(v):
    return int(round(v * 65536))

class Mesh:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.windows = []        # window halfwords; a face's window is its index + 1

    def vertex(self, x, y, z):
        self.verts.append((x, y, z))
        return len(self.verts) - 1

    def window(self, u=None, v=None):
        """A texture window (docs/LANGUAGE.md, "Mesh format"): u and v are (size, origin) in
        texels, size 8, 16, 32, 64, 128 or 256 and origin a multiple of 8 below 256, or None for
        no window along that axis. Faces sample origin + (u mod size), likewise v. Returns the
        number to pass as face(window=...); a mesh has up to 7."""
        def axis(a):
            if a is None:
                return 0
            size, origin = a
            assert size in (8, 16, 32, 64, 128, 256), 'window size must be 8-256 and a power of two'
            assert origin % 8 == 0 and 0 <= origin < 256, 'window origin must be a multiple of 8 below 256'
            return (size.bit_length() - 3) | (origin // 8) << 3
        w = axis(u) | axis(v) << 8
        assert w, 'a window needs u or v'
        if w not in self.windows:
            assert len(self.windows) < 7, 'a mesh has at most 7 texture windows'
            self.windows.append(w)
        return self.windows.index(w) + 1

    def face(self, idx, colours, uvs=None, flags=0, slot=0, four_bit=False, palette=0, blend=0, window=0):
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
        assert 0 <= window <= len(self.windows), 'unknown window (see Mesh.window)'
        tex = (slot & 15) | (16 if four_bit else 0) | window << 5
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
        faces_at = 16 + 16 * len(self.verts)
        table, table_at = b'', 0
        if self.windows:
            table_at = faces_at + 36 * len(self.faces)
            table = struct.pack('<%dH' % len(self.windows), *self.windows)
            table += bytes(-len(table) % 4)
        head = struct.pack('<HHIII', len(self.verts), len(self.faces), 16, faces_at, table_at)
        verts = b''.join(struct.pack('<4i', fx(x), fx(y), fx(z), 65536) for x, y, z in self.verts)
        return head + verts + b''.join(self.faces) + table

def rgb(r, g, b):
    return (r & 255) | ((g & 255) << 8) | ((b & 255) << 16)
