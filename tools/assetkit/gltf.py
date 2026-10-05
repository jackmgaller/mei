"""Export a compiled asset as glTF 2.0 (`mei_assets.py export`): one self-contained `.glb` (or
`.gltf`) that an ordinary 3D viewer shows the way Mei draws the asset (docs/ASSETKIT.md, "Viewing
an asset elsewhere: export").

The export reads what the console reads, not the recipe: the native mesh exactly as `build`
writes it (`native_bytes`: the quantised vertices, the faces after modifiers, prototypes and
texture splits, the baked vertex colours and tints, the texture coordinates and windows) and the
texture area and palettes as the asset's loader fills them (the packing's slot images, the
texture palettes, the palette-backed swatch and its default colours). Each texel is looked up as
the GPU does (`shade()` in src/core/gpu.c): the window applied, the 4- or 8-bit index read, index
0 a hole, the 15-bit colour expanded `c << 3 | c >> 2`.

What becomes what:

- positions: the native vertices with Z negated. Mei's world is left-handed (the camera looks
  along +Z with +X to the right of the screen); glTF's is right-handed with +Z toward the viewer.
  Negating Z keeps every point where a viewer sees it (an asset's front, −Z in the kit, faces
  glTF's +Z), and the native faces' order (the kit reverses each face so that Mei's front faces
  are clockwise in its coordinates) is then glTF's counter-clockwise front.
- baked lighting: COLOR_0. An untextured face's colour is its vertex colour; a palette-backed
  face's is its swatch texel times its tint (as the GPU computes it); a textured face's is its
  tint / 128, which the viewer multiplies with the texture. Colours are converted from the
  display's sRGB to glTF's linear vertex colours, so a viewer that writes sRGB shows Mei's values.
- textures: each texture as its tile, decoded through its palette to an RGBA PNG; holes (texel
  0) are alpha 0 and make the material alphaMode MASK. A repeating tile (a texture window) is the
  window's rectangle with REPEAT wrapping and UV = texel coordinate / tile size; a tile drawn once
  is its rectangle with its gutter, CLAMP_TO_EDGE and UV = (coordinate - origin) / that size.
  Samplers are NEAREST for magnification and minification (no mipmaps).
- every material is KHR_materials_unlit (the lighting is in the vertex colours); double-sided
  faces give doubleSided materials; emissive materials also carry emissiveFactor and
  emissiveTexture, for viewers that do not implement the unlit extension.

Not carried: animated textures beyond frame 0 (reported in `dropped`), levels of detail beyond
level 0, palette changes made at run time, Mei's affine (non-perspective) texturing and colour
interpolation, ordering-table sorting without the depth buffer, and the 15-bit framebuffer.
Standard library only (zlib for PNG).
"""
import base64
import json
import struct
import zlib

from .geometry import AssetError

EXPAND5 = [(c << 3) | (c >> 2) for c in range(32)]
SLOT_BYTES = 32768
NEAREST, REPEAT, CLAMP = 9728, 10497, 33071
FLOAT, U16, U32 = 5126, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
UNLIT = 'KHR_materials_unlit'


def linear(c):
    """An sRGB channel (0-1) as linear light, as glTF vertex colours and factors are."""
    return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4


def rgb15(c15):
    return tuple(EXPAND5[(c15 >> s) & 31] for s in (0, 5, 10))


def png_rgba(width, height, pixels):
    """An RGBA PNG of width x height pixels (bytes, 4 a pixel, top row first)."""
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data) & 0xffffffff)
    stride = width*4
    rows = b''.join(b'\0'+pixels[y*stride:(y+1)*stride] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(rows, 9))+chunk(b'IEND', b''))


def decode_native(binary):
    """(vertices, faces, windows) of a native mesh: vertices as floats in the kit's coordinates;
    faces as dicts of flags, tex, palette, indices, colours and uvs (3 or 4 corners); windows the
    halfword table (window n is entry n - 1)."""
    nverts, nfaces, verts_at, faces_at, table_at = struct.unpack_from('<HHIII', binary)
    vertices = [tuple(c/65536 for c in struct.unpack_from('<3i', binary, verts_at+16*i)) for i in range(nverts)]
    faces = []
    for i in range(nfaces):
        flags, _, tex, palette, *rest = struct.unpack_from('<BBBB4H4I4H', binary, faces_at+36*i)
        n = 4 if flags & 4 else 3
        faces.append({'flags': flags, 'tex': tex, 'palette': palette, 'indices': rest[0:4][:n],
                      'colours': rest[4:8][:n], 'uvs': [(t & 255, t >> 8) for t in rest[8:12][:n]]})
    windows = []
    if table_at:
        count = (len(binary)-table_at)//2
        windows = list(struct.unpack_from(f'<{count}H', binary, table_at))
    return vertices, faces, windows


class Vram:
    """The texture area and palette colours as the asset's loader leaves them."""

    def __init__(self, mesh):
        from .compiler import SWATCH
        self.slots, self.colours = {}, {}
        if mesh.textures:
            packing = mesh.textures['packing']
            for slot in packing.slots():
                first, data = packing.slot_image(slot)
                stride = 128 if packing.slot_bits[slot] == 4 else 256
                area = self.slots.setdefault(slot, bytearray(SLOT_BYTES))
                area[first*stride:first*stride+len(data)] = data
            for (bits, palette), colours in packing.palettes.items():
                base = palette*(16 if bits == 4 else 256)
                for i, c in enumerate(colours, 1):
                    self.colours[base+i] = c
        if mesh.palette:
            layout = mesh.palette['layout']
            area = self.slots.setdefault(layout['slot'], bytearray(SLOT_BYTES))
            area[layout['row']*128:layout['row']*128+len(SWATCH)] = SWATCH
            for entry in mesh.palette['entries']:
                self.colours[entry['colour']] = entry['rgb15']

    def texel(self, slot, four, palette, u, v):
        """The 15-bit colour the GPU reads at (u, v) of a slot (after any window), or None for
        index 0 (a hole)."""
        area = self.slots.get(slot, bytes(SLOT_BYTES))
        u, v = u & 255, v & 255
        if four:
            index = (area[v*128+(u >> 1)] >> ((u & 1)*4)) & 15
            base = palette*16
        else:
            index = area[(v*256+u) % SLOT_BYTES]
            base = (palette & 15)*256
        if index == 0:
            return None
        return self.colours.get(base+index, 0)


def window_of(halfword):
    """((u size, u origin), (v size, v origin)) of a window halfword; size 256 and origin 0 along
    an axis without one."""
    def axis(a):
        return (4 << (a & 7), (a >> 3 & 31)*8) if a & 7 else (256, 0)
    return axis(halfword & 255), axis(halfword >> 8)


class Writer:
    """Accumulates a glTF document and its single binary buffer."""

    def __init__(self):
        self.doc = {'asset': {'version': '2.0', 'generator': 'Mei Asset Kit (tools/mei_assets.py export)'},
                    'extensionsUsed': [UNLIT], 'scene': 0, 'scenes': [{'nodes': [0]}],
                    'buffers': [], 'bufferViews': [], 'accessors': [], 'samplers': [], 'images': [],
                    'textures': [], 'materials': [], 'meshes': [], 'nodes': []}
        self.blob = bytearray()

    def view(self, data, target=None):
        self.blob += bytes(-len(self.blob) % 4)
        view = {'buffer': 0, 'byteOffset': len(self.blob), 'byteLength': len(data)}
        if target:
            view['target'] = target
        self.blob += data
        self.doc['bufferViews'].append(view)
        return len(self.doc['bufferViews'])-1

    def accessor(self, values, kind, width, component=FLOAT, target=ARRAY_BUFFER, bounds=False):
        """values: flat list; kind: 'VEC3', 'VEC2' or 'SCALAR'."""
        code = {FLOAT: 'f', U16: 'H', U32: 'I'}[component]
        acc = {'bufferView': self.view(struct.pack(f'<{len(values)}{code}', *values), target),
               'componentType': component, 'count': len(values)//width, 'type': kind}
        if bounds:
            cols = [values[k::width] for k in range(width)]
            # the bounds of the values as stored (float32), as validators compare them
            f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
            acc['min'] = [f32(min(c)) for c in cols]
            acc['max'] = [f32(max(c)) for c in cols]
        self.doc['accessors'].append(acc)
        return len(self.doc['accessors'])-1

    def finish(self):
        self.blob += bytes(-len(self.blob) % 4)
        for key in [k for k, v in self.doc.items() if v == []]:
            del self.doc[key]
        return self.doc, bytes(self.blob)


def export(mesh, materials, recipe, name):
    """(glTF document, binary buffer, summary) of a compiled asset (compile_recipe's mesh and
    materials)."""
    from .compiler import native_bytes
    binary = native_bytes(mesh, materials, recipe.get('lighting', {}))
    vertices, faces, windows = decode_native(binary)
    if len(faces) != len(mesh.faces):
        raise AssetError('/export', 'The native mesh and the compiled mesh disagree on their faces.')
    vram = Vram(mesh)
    textures = mesh.textures['textures'] if mesh.textures else {}
    packing = mesh.textures['packing'] if mesh.textures else None
    palette_backed = mesh.palette['by_material'] if mesh.palette else {}

    groups, order = {}, []        # (material, image key, double-sided) -> corners
    images = {}                   # image key -> (width, height, rgba, wrap, cutout)
    hidden = 0
    for face, kit in zip(faces, mesh.faces):
        material = kit.material
        positions = [vertices[i] for i in face['indices']]
        double = bool(face['flags'] & 16)
        image, uvs, colours = None, None, []
        if face['flags'] & 2:
            slot, four, window = face['tex'] & 15, bool(face['tex'] & 16), face['tex'] >> 5
            tints = [((c & 255), (c >> 8) & 255, (c >> 16) & 255) for c in face['colours']]
            if material in palette_backed or material not in textures:
                # a swatch face: one texel everywhere, times the tint, as the GPU computes it
                u, v = face['uvs'][0]
                if window:
                    (su, ou), (sv, ov) = window_of(windows[window-1])
                    u, v = (u & (su-1))+ou, (v & (sv-1))+ov
                c15 = vram.texel(slot, four, face['palette'], u, v)
                if c15 is None:
                    hidden += 1
                    continue
                t = rgb15(c15)
                colours = [tuple(min(255, t[k]*tint[k] >> 7)/255 for k in range(3)) for tint in tints]
            else:
                tex = textures[material]
                if window:
                    (su, ou), (sv, ov) = window_of(windows[window-1])
                    rect, wrap = (ou, ov, su, sv), REPEAT
                    uvs = [(u/su, v/sv) for u, v in face['uvs']]
                else:
                    place = packing.placements[tex.tile.key]
                    w, h = tex.tile.alloc_width, tex.tile.alloc_height
                    rect, wrap = (place.x, place.y, w, h), CLAMP
                    uvs = [((u-place.x)/w, (v-place.y)/h) for u, v in face['uvs']]
                if len(set(face['uvs'])) == 1:
                    # every corner on one texel: sample its centre, not its edge
                    uvs = [(u+0.5/rect[2], v+0.5/rect[3]) for u, v in uvs]
                image = (slot, four, face['palette'], *rect, wrap)
                if image not in images:
                    x0, y0, w, h = rect
                    pixels, cutout = bytearray(), False
                    for y in range(h):
                        for x in range(w):
                            c15 = vram.texel(slot, four, face['palette'], x0+x, y0+y)
                            cutout |= c15 is None
                            pixels += bytes((0, 0, 0, 0)) if c15 is None else bytes((*rgb15(c15), 255))
                    images[image] = (w, h, bytes(pixels), wrap, cutout)
                # the tint as a factor (128 = 1); the bake never brightens, so above 1 is clamped
                colours = [tuple(min(c, 128)/128 for c in tint) for tint in tints]
        else:
            colours = [((c & 255)/255, ((c >> 8) & 255)/255, ((c >> 16) & 255)/255) for c in face['colours']]
        key = (material, image, double)
        if key not in groups:
            groups[key] = []
            order.append(key)
        tris = [(0, 1, 2)] if len(positions) == 3 else [(0, 1, 2), (1, 3, 2)]
        for tri in tris:
            for k in tri:
                x, y, z = positions[k]
                groups[key].append(((x, y, -z), tuple(linear(c) for c in colours[k]), uvs[k] if uvs else None))

    if not order:
        raise AssetError('/export', 'Every face is on a hole of its texture: Mei draws nothing, so there is nothing to export.')
    out = Writer()
    doc = out.doc
    sampler_of, texture_of, primitives, dropped = {}, {}, [], []
    for key in order:
        material, image, double = key
        mat = materials[material]
        corners = groups[key]
        index, verts = {}, []
        indices = []
        for corner in corners:
            if corner not in index:
                index[corner] = len(verts)
                verts.append(corner)
            indices.append(index[corner])
        attributes = {'POSITION': out.accessor([c for v in verts for c in v[0]], 'VEC3', 3, bounds=True),
                      'COLOR_0': out.accessor([c for v in verts for c in v[1]], 'VEC3', 3)}
        emissive = mat.get('class', 'surface') == 'emissive'
        entry = {'name': material,
                 'pbrMetallicRoughness': {'baseColorFactor': [1, 1, 1, 1], 'metallicFactor': 0, 'roughnessFactor': 1},
                 'extensions': {UNLIT: {}}}
        extras = {'class': mat.get('class', 'surface')}
        if image:
            attributes['TEXCOORD_0'] = out.accessor([c for v in verts for c in v[2]], 'VEC2', 2)
            w, h, pixels, wrap, cutout = images[image]
            if image not in texture_of:
                if wrap not in sampler_of:
                    doc['samplers'].append({'magFilter': NEAREST, 'minFilter': NEAREST, 'wrapS': wrap, 'wrapT': wrap})
                    sampler_of[wrap] = len(doc['samplers'])-1
                doc['images'].append({'name': material, 'mimeType': 'image/png', 'bufferView': out.view(png_rgba(w, h, pixels))})
                doc['textures'].append({'sampler': sampler_of[wrap], 'source': len(doc['images'])-1})
                texture_of[image] = len(doc['textures'])-1
            entry['pbrMetallicRoughness']['baseColorTexture'] = {'index': texture_of[image]}
            if cutout:
                entry['alphaMode'] = 'MASK'
                entry['alphaCutoff'] = 0.5
            if emissive:
                entry['emissiveTexture'] = {'index': texture_of[image]}
                entry['emissiveFactor'] = [1, 1, 1]
            tex = textures[material]
            extras.update(texture={'width': tex.width, 'height': tex.height, 'bits': tex.bits,
                                   'projection': tex.projection, 'repeat': tex.repeat})
            if len(tex.tile.frames) > 1:
                extras['frames'] = {'count': len(tex.tile.frames), 'ticks': tex.ticks, 'exported': 0}
                if material not in [d['material'] for d in dropped]:
                    dropped.append({'material': material, 'frames': len(tex.tile.frames), 'exported': 0,
                                    'dropped': len(tex.tile.frames)-1})
        elif emissive and corners:
            # an untextured emissive face is unshaded: its colour is the same at every corner
            entry['emissiveFactor'] = [round(c, 6) for c in corners[0][1]]
        if material in palette_backed:
            extras['palette_colour'] = palette_backed[material]['colour']
        if double:
            entry['doubleSided'] = True
        entry['extras'] = {'mei': extras}
        doc['materials'].append(entry)
        big = len(verts) > 65535
        primitives.append({'attributes': attributes, 'mode': 4, 'material': len(doc['materials'])-1,
                           'indices': out.accessor(indices, 'SCALAR', 1, U32 if big else U16, ELEMENT_ARRAY_BUFFER)})
    doc['meshes'].append({'name': name, 'primitives': primitives})
    doc['nodes'].append({'name': name, 'mesh': 0})
    notes = ['Mei draws in a left-handed frame; positions have Z negated, so the asset\'s front (-Z in the kit) faces +Z.',
             'Lighting is baked into COLOR_0 (linear); every material is unlit.']
    if dropped:
        notes.append('Animated textures: frame 0 only.')
    if mesh.levels:
        notes.append(f'Level of detail 0 only ({len(mesh.levels)} coarser levels not exported).')
    doc['asset']['extras'] = {'mei': {'name': name, 'notes': notes}}
    document, blob = out.finish()
    document['buffers'] = [{'byteLength': len(blob)}]
    summary = {'triangles': sum(len(g) for g in groups.values())//3, 'faces': len(faces), 'hidden_faces': hidden,
               'primitives': len(primitives), 'images': len(images),
               'vertices': sum(len(p) for p in [set(g) for g in groups.values()]),
               'dropped_frames': dropped, 'lod_levels_not_exported': len(mesh.levels or [])}
    return document, blob, summary


def glb_bytes(document, blob):
    """A binary glTF: header, JSON chunk (space-padded), BIN chunk (zero-padded)."""
    text = json.dumps(document, separators=(',', ':')).encode()
    text += b' '*(-len(text) % 4)
    blob += bytes(-len(blob) % 4)
    length = 12+8+len(text)+(8+len(blob) if blob else 0)
    out = struct.pack('<4sII', b'glTF', 2, length)+struct.pack('<I4s', len(text), b'JSON')+text
    if blob:
        out += struct.pack('<I4s', len(blob), b'BIN\0')+blob
    return out


def gltf_bytes(document, blob):
    """A text glTF with its buffer embedded as a data URI."""
    document = json.loads(json.dumps(document))
    document['buffers'][0]['uri'] = 'data:application/octet-stream;base64,'+base64.b64encode(blob).decode()
    return (json.dumps(document, indent=1)+'\n').encode()


def read_glb(data):
    """(document, binary chunk) of a .glb; raises ValueError on a malformed file."""
    magic, version, length = struct.unpack_from('<4sII', data)
    if magic != b'glTF' or version != 2 or length != len(data):
        raise ValueError('not a glTF 2.0 binary')
    size, kind = struct.unpack_from('<I4s', data, 12)
    if kind != b'JSON':
        raise ValueError('first chunk is not JSON')
    document = json.loads(data[20:20+size])
    blob = b''
    at = 20+size
    if at < len(data):
        size2, kind2 = struct.unpack_from('<I4s', data, at)
        if kind2 != b'BIN\0':
            raise ValueError('second chunk is not BIN')
        blob = data[at+8:at+8+size2]
    return document, blob


def add_parser(sub):
    """The `export` subcommand (mei_assets.py)."""
    cmd = sub.add_parser('export', help='Write a glTF 2.0 file (.glb or .gltf) that an ordinary 3D viewer draws as Mei does: '
                                        'baked colours, paletted textures as nearest-sampled PNGs, cutouts, double-sided faces.')
    cmd.add_argument('recipe', help='Recipe JSON path, or - to read stdin.')
    cmd.add_argument('-o', '--output', required=True, help='Directory to write NAME.glb (or NAME.gltf) into.')
    cmd.add_argument('--format', choices=['glb', 'gltf'], default='glb')
    return cmd


def command(args, load, folder):
    """Runs `export`: returns the JSON result."""
    from pathlib import Path
    from kitcore import output as staged
    from .compiler import compile_recipe
    recipe = load(args.recipe)
    mesh, materials, report = compile_recipe(recipe, folder(args.recipe))
    name = recipe['name']
    document, blob, summary = export(mesh, materials, recipe, name)
    filename = f'{name}.{args.format}'
    data = glb_bytes(document, blob) if args.format == 'glb' else gltf_bytes(document, blob)
    directory = Path(args.output).resolve()
    staged.guard(directory, [filename], [args.recipe], error=AssetError)
    with staged.staging(directory, '.mei-assets-') as stage:
        (stage/filename).write_bytes(data)
        staged.commit(stage, directory)
    return {'ok': True, 'file': str(directory/filename), 'format': args.format, 'bytes': len(data),
            **summary, 'warnings': report['warnings']}
