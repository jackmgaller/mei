"""Writes meshes in the Mei binary mesh format (docs/LANGUAGE.md, "Mesh format").

    m = Mesh()
    a = m.vertex(x, y, z)                         # floats, world units
    m.quad([a, b, c, d], colours, uvs, flags)     # strip order: a-b-c and b-c-d
    m.tri([a, b, c], colours, uvs, flags)
    w = m.window(u=(16, 32), v=(16, 64))          # a texture window: (size, origin) per axis
    m.quad([a, b, c, d], colours, uvs, slot=3, window=w)
    open('x.bin', 'wb').write(m.pack())

Front faces are counter-clockwise as seen by the viewer (for quads: the first triangle).
A mesh with no windows packs exactly as before windows existed (no table, header +12 zero).

Slots are 0-31 and palettes 0-511 (4-bit) or 0-31 (8-bit) (VRAM at 2 MB, docs/DECISIONS.md):
slots 16-31 set flag bit 6 (SLOT_HI) and the slot's low 4 bits in the texture byte; palette
bank 1 sets flag bit 7 (PAL_HI) and the palette within the bank in the palette byte. A face in
slots 0-15 and palette bank 0 packs exactly as before."""
import struct

GOURAUD, TEXTURED, QUAD, SEMI, DOUBLE = 1, 2, 4, 8, 16
KEYED, SLOT_HI, PAL_HI = 32, 64, 128
SLOTS = 32                  # texture slots 0-31; 15 holds the fonts
PALETTES4, PALETTES8 = 512, 32
BANK_COLOURS = 4096         # palette bank 0 is colours 0-4095, bank 1 4096-8191

def tex_fields(slot, four_bit, palette, window=0):
    """(flag bits, texture byte, palette byte) of a face drawing slot 0-31 with palette 0-511
    (4-bit) or 0-31 (8-bit) and window 0-7."""
    assert 0 <= slot < SLOTS, 'texture slots are 0-31'
    assert 0 <= palette < (PALETTES4 if four_bit else PALETTES8), \
        'palettes are 0-511 for a 4-bit texture, 0-31 for an 8-bit one'
    per_bank = 256 if four_bit else 16
    flags = (SLOT_HI if slot >= 16 else 0) | (PAL_HI if palette >= per_bank else 0)
    return flags, (slot & 15) | (16 if four_bit else 0) | window << 5, palette % per_bank

def face_slot(flags, tex):
    """The slot 0-31 of a face's flags and texture byte."""
    return (tex & 15) | (16 if flags & SLOT_HI else 0)

def face_palette(flags, tex, palette):
    """The palette 0-511 (4-bit) or 0-31 (8-bit) of a face's flags, texture and palette bytes."""
    if tex & 16:
        return palette | (256 if flags & PAL_HI else 0)
    return (palette & 15) | (16 if flags & PAL_HI else 0)

def face_colour(flags, tex, palette, index):
    """The palette colour 0-8191 a face's texel `index` shows."""
    return face_palette(flags, tex, palette) * (16 if tex & 16 else 256) + index

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
        banks, tex, palette = tex_fields(slot, four_bit, palette, window)
        flags |= banks
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
