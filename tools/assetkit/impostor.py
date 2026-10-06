"""Impostors: an asset's far level as a few cut-out pictures of itself (docs/ASSETKIT.md, "Impostors").

`render(recipe, base, view, ppu)` draws the asset's level 0 orthographically, as the console would
colour it (textures, palette-backed colours and the baked shade), from the front (looking along +Z),
the side (from +X, looking along -X) or above, `ppu` pixels a unit, onto a transparent picture
(texture holes stay holes). `impostor(...)` writes the front and side pictures as 4-bit PNGs (at
most 15 colours, median cut) beside the recipe and returns the materials and the level's nodes: a
box of four double-sided quads round the asset's bounds, the front picture on its front and back,
the side picture on its two ends, each mapped by world position (a picture seen from behind is the
projection seen through, mirrored), cutouts where the sky shows. The pictures are brightened by the
shade the box's walls get, so that baked twice they come out as drawn. Pillow and NumPy.

A recipe's generator calls it and puts the level in place of (or after) its coarsest one; the
impostor's textures are drawn only by that level, which the Asset Kit allows (compiler.
level_materials): level 0 loads and places them.
"""
import math

from .compiler import compile_recipe, shading
from .textures import rgb_of

VIEWS = {
    # view: (column axis, sign), row axis is -y (top row at the highest point), depth axis and sign
    # (smaller is nearer)
    'front': ((0, 1), (2, 1)),       # columns along +x; nearest is smallest z
    'side': ((2, 1), (0, -1)),       # columns along +z; nearest is largest x
}


def _face_colour(face, mesh, materials, textures, shade_of):
    """(callable (b0, b1, b2) -> rgb or None, ...) for a face: its colour at barycentric coordinates."""
    import numpy as np
    mat = materials[face.material]
    a, b, c = (mesh.vertices[i] for i in face.indices[:3])
    n = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
         (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
         (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
    ln = math.sqrt(sum(x * x for x in n)) or 1
    n = [x / ln for x in n]
    emissive = mat.get('class', 'surface') == 'emissive'
    shade = 1.0 if emissive else shade_of(n)
    tex = textures.get(face.material)
    entry = mesh.palette['by_material'].get(face.material) if mesh.palette else None
    if tex is not None and face.texcoords:
        tile = tex.tile
        frame = tile.frames[0]
        uv = np.array(face.texcoords[:3], dtype=float)

        def colour(w):
            u = (w @ uv[:, 0]).astype(int)
            v = (w @ uv[:, 1]).astype(int)
            if tex.repeat:
                u, v = u % tile.width, v % tile.height
            else:
                u, v = np.clip(u, 0, tile.width - 1), np.clip(v, 0, tile.height - 1)
            out = np.zeros((len(u), 4))
            for k, (x, y) in enumerate(zip(u, v)):
                c = frame[y][x]
                if c is not None:
                    out[k, :3] = [ch * shade for ch in rgb_of(c)]
                    out[k, 3] = 1
            return out
        return colour
    colour_hex = entry['color'] if entry else mat['color']
    rgb = [int(colour_hex[k:k + 2], 16) * shade for k in (1, 3, 5)]

    def flat(w):
        out = np.zeros((len(w), 4))
        out[:, :3] = rgb
        out[:, 3] = 1
        return out
    return flat


def render(recipe, base, view, ppu, supersample=2):
    """An RGBA picture (numpy, rows x columns x 4, 0-255) of the recipe's level 0 seen orthographically
    from `view`, and the world rectangle it covers: (picture, (col0, col1, row0, row1) in units)."""
    import numpy as np
    mesh, materials, _ = compile_recipe(recipe, base)
    textures = mesh.textures['textures'] if mesh.textures else {}
    shade_of = shading(recipe.get('lighting', {}))
    (ca, cs), (da, ds) = VIEWS[view]
    vs = np.array(mesh.vertices, dtype=float)
    cols, rows, depth = vs[:, ca] * cs, -vs[:, 1], vs[:, da] * ds
    c0, c1, r0, r1 = cols.min(), cols.max(), rows.min(), rows.max()
    s = ppu * supersample
    W, H = max(1, math.ceil((c1 - c0) * s)), max(1, math.ceil((r1 - r0) * s))
    img = np.zeros((H, W, 4))
    zbuf = np.full((H, W), np.inf)
    px, py = (cols - c0) * s, (rows - r0) * s
    for face in mesh.faces:
        tri = face.indices[:3]
        x, y, z = px[list(tri)], py[list(tri)], depth[list(tri)]
        det = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(det) < 1e-9:
            continue
        xa, xb = max(0, int(math.floor(x.min()))), min(W - 1, int(math.ceil(x.max())))
        ya, yb = max(0, int(math.floor(y.min()))), min(H - 1, int(math.ceil(y.max())))
        if xa > xb or ya > yb:
            continue
        gx, gy = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        gx, gy = gx.ravel(), gy.ravel()
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / det
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / det
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        w = np.stack([w0, w1, w2], 1)[inside]
        gx, gy = gx[inside].astype(int), gy[inside].astype(int)
        zz = w @ z
        nearer = zz < zbuf[gy, gx]
        if not nearer.any():
            continue
        w, gx, gy, zz = w[nearer], gx[nearer], gy[nearer], zz[nearer]
        col = _face_colour(face, mesh, materials, textures, shade_of)(w)
        solid = col[:, 3] > 0
        gx, gy, zz, col = gx[solid], gy[solid], zz[solid], col[solid]
        zbuf[gy, gx] = zz
        img[gy, gx, :3] = col[:, :3]
        img[gy, gx, 3] = 255
    if supersample > 1:
        h, w_ = H // supersample, W // supersample
        img = img[:h * supersample, :w_ * supersample]
        blocks = img.reshape(h, supersample, w_, supersample, 4)
        cover = (blocks[..., 3] > 0).sum(axis=(1, 3))
        rgb = (blocks[..., :3] * (blocks[..., 3:] > 0)).sum(axis=(1, 3)) / np.maximum(cover, 1)[..., None]
        img = np.zeros((h, w_, 4))
        img[..., :3] = rgb
        img[..., 3] = np.where(cover * 2 >= supersample * supersample, 255, 0)
    return img, (c0, c1, r0, r1)


def save_png(img, path, colours=15, gain=1.0):
    """Writes an RGBA picture as at most `colours` opaque colours (median cut) and holes."""
    import numpy as np
    from PIL import Image
    rgb = np.clip(img[..., :3] * gain, 0, 255).astype('uint8')
    alpha = img[..., 3] > 0
    if not alpha.any():
        raise ValueError(f'{path}: nothing drawn')
    pal = Image.fromarray(rgb[alpha].reshape(1, -1, 3), 'RGB').quantize(colors=colours, method=Image.Quantize.MEDIANCUT,
                                                                           dither=Image.Dither.NONE)
    flat = np.array(pal.convert('RGB')).reshape(-1, 3)
    out = np.zeros(img.shape[:2] + (4,), dtype='uint8')
    out[alpha, :3] = flat
    out[alpha, 3] = 255
    Image.fromarray(out, 'RGBA').save(path)
    return out


def impostor(recipe, base, folder, name, ppu=2.0, image_prefix='art/'):
    """Renders the front and side pictures (folder/NAME_front.png, NAME_side.png) and returns
    (materials, nodes) of the impostor level: two materials impostor_front and impostor_side
    (4-bit, fit, double-sided) and one mesh node, the box round level 0's bounds."""
    import numpy as np
    from pathlib import Path
    lighting = recipe.get('lighting', {})
    wall = shading(lighting)([1.0, 0.0, 0.0])        # the box's walls' baked shade
    mats, means, rects = {}, {}, {}
    for view in ('front', 'side'):
        img, rect = render(recipe, base, view, ppu)
        path = Path(folder) / f'{name}_{view}.png'
        out = save_png(img, path, gain=1.0 / wall)
        opaque = out[..., 3] > 0
        mean = out[opaque, :3].mean(axis=0) * wall
        means[view] = '#' + ''.join(f'{int(round(v)):02x}' for v in mean)
        rects[view] = rect
        mats[f'impostor_{view}'] = {'color': means[view],
                                    'texture': {'image': f'{image_prefix}{name}_{view}.png', 'projection': 'fit'},
                                    'double_sided': True}
    (x0, x1, ya, yb), (z0, z1, _, _) = rects['front'], rects['side']
    top, bottom = -ya, -yb
    v, f, uv, fm = [], [], [], []

    def quad(corners, uvs, mat):
        k = len(v)
        v.extend([[round(float(c), 4) + 0.0 for c in p] for p in corners])
        uv.extend(uvs)
        f.append([k, k + 1, k + 2, k + 3])
        fm.append(mat)
    for z in (z0, z1):         # front and back: columns along +x
        quad([[x0, top, z], [x1, top, z], [x1, bottom, z], [x0, bottom, z]],
             [[0, 0], [1, 0], [1, 1], [0, 1]], 'impostor_front')
    for x in (x0, x1):         # the ends: columns along +z
        quad([[x, top, z0], [x, top, z1], [x, bottom, z1], [x, bottom, z0]],
             [[0, 0], [1, 0], [1, 1], [0, 1]], 'impostor_side')
    node = {'id': 'impostor', 'op': 'mesh', 'vertices': v, 'faces': f, 'face_materials': fm, 'uvs': uv}
    return mats, [node]


def with_impostor(recipe, base, name, ppu=2.0, level=-1, folder=None):
    """The recipe with its lod level `level` (default the coarsest) replaced by an impostor of its
    level 0 (pictures written to folder, default base/art). Rerunning gives the same recipe: an
    earlier impostor's materials are left out of what is drawn."""
    import copy
    from pathlib import Path
    plain = {k: copy.deepcopy(v) for k, v in recipe.items() if k != 'lod'}
    plain['materials'] = {m: v for m, v in plain['materials'].items() if not m.startswith('impostor_')}
    mats, nodes = impostor(plain, base, folder or Path(base) / 'art', name, ppu)
    out = copy.deepcopy(recipe)
    out['materials'] = {**plain['materials'], **mats}
    out['lod']['levels'][level]['nodes'] = nodes
    return out
