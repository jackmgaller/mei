"""Point lights baked into vertex colours (docs/ASSETKIT.md, "Point lights").

A recipe's `lighting.lights` add coloured light on top of its directional or vertical shade. They
are evaluated at export, at each corner of each face, like the rest of the lighting: nothing is
lit at draw time. Two things make a corner-by-corner bake look like a pool of light:

- **Refinement.** A large face has corners only at its edges, so a pool in its middle would be
  lost. Faces where the light varies across them are bisected along their longest edge, worst
  and largest first, until the colour Gouraud interpolation draws is within `tolerance` of the
  light at the face's edge midpoints, its centroid and its point nearest each light, down to
  `min_edge`, and at most `max_added` triangles in all. Every face sharing a split edge is split
  there too (longest-edge bisection), so there are no T-junctions.
- **Shadows** (a light's `shadows`): a ray from the point to the light (or to 8 points on a sphere
  of the light's `radius`, for a soft edge) tested against the recipe's own opaque, non-emissive
  faces, each blocking only rays that reach its front.

The result is mesh.lit: per face, per corner, the (r, g, b) shade factor that native_bytes()
multiplies the face's colour (or tint, 128 = 1) by.
"""
from collections import defaultdict
import heapq
import math

from kitcore.vector import add, sub, mul, dot, cross, norm, quantize
from .geometry import AssetError

TOLERANCE = 16           # 8-bit colour steps; 8 is one step of Mei's 15-bit colour
MAX_ADDED = 512          # triangles refinement may add, default
TINT_MAX = 255/128       # a tint byte is at most 255, 128 being 1
SHADOW_OFFSET = 1e-3     # units: a shadow ray starts this far off its surface, toward the light
# A soft light's shadow samples: the corners of a cube in the sphere of its radius.
SOFT = tuple(norm((x, y, z)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1))


def check(lighting):
    """Errors the schema cannot express."""
    lights = lighting.get('lights')
    if not lights: return
    if lighting.get('bake', True) is False:
        raise AssetError('/lighting/lights', 'Point lights are baked into vertex colours, and bake: false draws plain '
                         'colours. Remove bake: false, or remove lights.')
    ids = set()
    for k, spec in enumerate(lights):
        name = spec.get('id', f'light_{k}')
        if name in ids:
            raise AssetError(f'/lighting/lights/{k}/id', f'Duplicate light id {name!r}.')
        ids.add(name)
        if spec.get('radius', 0) and not spec.get('shadows', False):
            raise AssetError(f'/lighting/lights/{k}/radius', 'radius softens a light\'s shadows. Set shadows: true, or '
                             'remove radius.')


class Light:
    def __init__(self, spec, k):
        self.id = spec.get('id', f'light_{k}')
        self.at = tuple(float(x) for x in spec['at'])
        self.range = float(spec['range'])
        self.range2 = self.range*self.range
        colour, intensity = spec.get('color', '#ffffff'), spec.get('intensity', 1)
        self.rgb = tuple(int(colour[i:i+2], 16)/255*intensity for i in (1, 3, 5))
        self.shadows = spec.get('shadows', False)
        radius = spec.get('radius', 0)
        self.samples = [self.at] if not radius else [add(self.at, mul(d, radius)) for d in SOFT]


def closest(p, a, b, c):
    """Barycentric weights of the point of triangle abc nearest p (Ericson, Real-Time Collision
    Detection, 5.1.5)."""
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0: return (1.0, 0.0, 0.0)
    bp = sub(p, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3: return (0.0, 1.0, 0.0)
    vc = d1*d4-d3*d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1/(d1-d3)
        return (1-v, v, 0.0)
    cp = sub(p, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6: return (0.0, 0.0, 1.0)
    vb = d5*d2-d1*d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2/(d2-d6)
        return (1-w, 0.0, w)
    va = d3*d6-d5*d4
    if va <= 0 and d4-d3 >= 0 and d5-d6 >= 0:
        w = (d4-d3)/((d4-d3)+(d5-d6))
        return (0.0, 1-w, w)
    denom = 1/(va+vb+vc)
    v, w = vb*denom, vc*denom
    return (1-v-w, v, w)


def at(w, a, b, c):
    return tuple(w[0]*a[k]+w[1]*b[k]+w[2]*c[k] for k in range(3))


class Occluders:
    """The faces that cast shadows, in a bounding volume hierarchy, for segment tests. A face
    casts a shadow only toward its front, as Mei draws it only from the front (a double-sided
    one both ways): so a point under or inside a closed part (a floor's corner beneath a wall
    standing on it) is not shadowed by that part, and its colour does not darken the floor
    around the wall."""
    LEAF = 4

    def __init__(self, triangles):
        self.tris = []
        for a, b, c, double in triangles:
            lo = tuple(min(a[k], b[k], c[k]) for k in range(3))
            hi = tuple(max(a[k], b[k], c[k]) for k in range(3))
            self.tris.append((a, sub(b, a), sub(c, a), lo, hi, double))
        self.nodes = []          # [lo, hi, left, right, first, count]
        self.order = list(range(len(self.tris)))
        if self.tris: self.build(0, len(self.order))

    def build(self, first, count):
        tris = self.tris
        items = self.order[first:first+count]
        lo = tuple(min(tris[i][3][k] for i in items) for k in range(3))
        hi = tuple(max(tris[i][4][k] for i in items) for k in range(3))
        index = len(self.nodes)
        self.nodes.append([lo, hi, -1, -1, first, count])
        if count <= self.LEAF: return index
        axis = max(range(3), key=lambda k: hi[k]-lo[k])
        items.sort(key=lambda i: (tris[i][3][axis]+tris[i][4][axis], i))
        self.order[first:first+count] = items
        half = count//2
        left = self.build(first, half)
        right = self.build(first+half, count-half)
        self.nodes[index][2:4] = [left, right]
        return index

    def blocked(self, o, d):
        """Whether a shadow-casting face crosses the segment o + t d, 0 < t < 1 (ends excluded)."""
        if not self.nodes: return False
        ox, oy, oz = o
        dx, dy, dz = d
        nodes, tris, order = self.nodes, self.tris, self.order
        stack = [0]
        while stack:
            lo, hi, left, right, first, count = nodes[stack.pop()]
            t0, t1 = 0.0, 1.0
            miss = False
            for oc, dc, l, h in ((ox, dx, lo[0], hi[0]), (oy, dy, lo[1], hi[1]), (oz, dz, lo[2], hi[2])):
                if dc == 0:
                    if oc < l or oc > h:
                        miss = True
                        break
                    continue
                a, b = (l-oc)/dc, (h-oc)/dc
                if a > b: a, b = b, a
                if a > t0: t0 = a
                if b < t1: t1 = b
                if t0 > t1:
                    miss = True
                    break
            if miss: continue
            if left >= 0:
                stack.append(right)
                stack.append(left)
                continue
            for i in order[first:first+count]:
                (vx, vy, vz), (ax, ay, az), (bx, by, bz), _, _, double = tris[i]
                # Moller-Trumbore
                px, py, pz = dy*bz-dz*by, dz*bx-dx*bz, dx*by-dy*bx
                det = ax*px+ay*py+az*pz
                # det = -(d . outward normal): positive when the ray meets the face's front
                if det < 1e-15 and (not double or det > -1e-15): continue
                inv = 1/det
                tx, ty, tz = ox-vx, oy-vy, oz-vz
                u = (tx*px+ty*py+tz*pz)*inv
                if u < 0 or u > 1: continue
                qx, qy, qz = ty*az-tz*ay, tz*ax-tx*az, tx*ay-ty*ax
                v = (dx*qx+dy*qy+dz*qz)*inv
                if v < 0 or u+v > 1: continue
                t = (bx*qx+by*qy+bz*qz)*inv
                if 1e-6 < t < 1-1e-6: return True
        return False


class Baker:
    def __init__(self, mesh, materials, lighting, shade_of, textures, palette_backed):
        self.mesh = mesh
        self.lights = [Light(spec, k) for k, spec in enumerate(lighting['lights'])]
        self.shade_of = shade_of
        refine = lighting.get('refine', {})
        self.tolerance = refine.get('tolerance', TOLERANCE)
        self.min_edge = refine.get('min_edge', min(l.range for l in self.lights)/8)
        self.max_added = refine.get('max_added', MAX_ADDED)
        # per material: (lit, tinted, colour 0-255, double-sided)
        self.kind = {}
        for name, mat in materials.items():
            tinted = name in textures or palette_backed(mat)
            self.kind[name] = (mat.get('class', 'surface') != 'emissive', tinted,
                               tuple(int(mat['color'][k:k+2], 16) for k in (1, 3, 5)), mat.get('double_sided', False))
        self.rays = 0
        self.occluders = None
        if any(l.shadows for l in self.lights):
            tris = []
            for face in mesh.faces:
                mat, tex = materials[face.material], textures.get(face.material)
                # semi-transparent and cutout faces let light through; emissive faces are where it
                # comes from (a bulb inside its lantern's paper still lights the room)
                if 'blend' in mat or (tex is not None and tex.cutout) or mat.get('class') == 'emissive': continue
                tris.append((*(mesh.vertices[i] for i in face.indices), mat.get('double_sided', False)))
            self.occluders = Occluders(tris)
        self.cache = {}

    def visible(self, p, n, light):
        """The fraction of the light's samples the point sees."""
        lift = SHADOW_OFFSET if dot(n, sub(light.at, p)) >= 0 else -SHADOW_OFFSET
        o = add(p, mul(n, lift))
        seen = 0
        for s in light.samples:
            self.rays += 1
            if not self.occluders.blocked(o, sub(s, o)): seen += 1
        return seen/len(light.samples)

    def value(self, p, n, double):
        """The (r, g, b) shade factor at point p with unit normal n: the recipe's directional or
        vertical shade plus every light's colour x intensity x Lambert x falloff x visibility."""
        s = self.shade_of(n)
        r = g = b = s
        for light in self.lights:
            dx, dy, dz = light.at[0]-p[0], light.at[1]-p[1], light.at[2]-p[2]
            d2 = dx*dx+dy*dy+dz*dz
            if d2 >= light.range2: continue
            d = math.sqrt(d2)
            c = (n[0]*dx+n[1]*dy+n[2]*dz)/d if d > 0 else 1.0
            if double: c = abs(c)
            if c <= 0: continue
            x = 1-d2/light.range2
            f = c*x*x
            if light.shadows:
                f *= self.visible(p, n, light)
                if not f: continue
            r += light.rgb[0]*f
            g += light.rgb[1]*f
            b += light.rgb[2]*f
        return (r, g, b)

    def corner(self, i, n, double):
        key = (i, n, double)
        if key not in self.cache:
            self.cache[key] = self.value(self.mesh.vertices[i], n, double)
        return self.cache[key]

    def shown(self, value, kind):
        """What the GPU shows (0-255 a channel) for a shade factor on a face of this kind,
        a textured or palette-backed face judged by its material's colour."""
        _, tinted, colour, _ = kind
        if tinted: return tuple(c*min(s, TINT_MAX) for c, s in zip(colour, value))
        return tuple(min(255.0, c*s) for c, s in zip(colour, value))

    def reaches(self, a, b, c):
        """The lights whose range reaches triangle abc, each with the barycentric weights of the
        triangle's point nearest it."""
        out = []
        for light in self.lights:
            w = closest(light.at, a, b, c)
            q = at(w, a, b, c)
            if dot(sub(q, light.at), sub(q, light.at)) < light.range2: out.append(w)
        return out

    def error(self, face, normals):
        """How far (8-bit steps, the largest channel) the colour Gouraud draws across the face
        is from the light at its edge midpoints, centroid and nearest points to the lights."""
        kind = self.kind[face.material]
        if not kind[0]: return 0.0
        vs = self.mesh.vertices
        a, b, c = (vs[i] for i in face.indices)
        near = self.reaches(a, b, c)
        if not near: return 0.0
        double = kind[3]
        corners = [self.shown(self.corner(i, n, double), kind) for i, n in zip(face.indices, normals)]
        third = 1/3
        points = [(0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5), (third, third, third)]
        points += [w for w in near if max(w) < 1]
        worst = 0.0
        for w in points:
            p = at(w, a, b, c)
            n = norm(at(w, *normals))
            true = self.shown(self.value(p, n, double), kind)
            for k in range(3):
                e = abs(true[k]-(w[0]*corners[0][k]+w[1]*corners[1][k]+w[2]*corners[2][k]))
                if e > worst: worst = e
        return worst


def corner_normals(mesh, materials):
    """Per face, each corner's unit normal as native_bytes() shades it: the face's, or for a
    smooth material the area-weighted normal of the part's faces of that material at the vertex."""
    flat, smooth = [], defaultdict(lambda: (0, 0, 0))
    for face in mesh.faces:
        a, b, c = (mesh.vertices[i] for i in face.indices)
        normal = cross(sub(b, a), sub(c, a))
        flat.append(norm(normal))
        for i in face.indices:
            key = (face.part, face.material, i)
            smooth[key] = add(smooth[key], normal)
    out = []
    for face, normal in zip(mesh.faces, flat):
        if materials[face.material].get('smooth', False):
            out.append(tuple(norm(smooth[face.part, face.material, i]) for i in face.indices))
        else:
            out.append((normal,)*3)
    return out


def edge(i, j):
    return (i, j) if i < j else (j, i)


def bake(mesh, materials, lighting, shade_of, textures, palette_backed):
    """Refine the mesh where its lights vary across faces, then set mesh.lit. Returns the
    report's `lights` section and its warnings.

    Refinement is greedy: the face whose drawn colour is farthest from the light, weighted by its
    longest edge, has that edge bisected, with the longest edge of every face that then has a
    split edge (so the split propagates to longer neighbours, and every face along a split edge
    gets its midpoint: no T-junctions), until no face over tolerance has an edge of at least
    twice min_edge and a width of min_edge, or the next split would pass max_added."""
    baker = Baker(mesh, materials, lighting, shade_of, textures, palette_backed)
    vs = mesh.vertices
    smooth = {name: mat.get('smooth', False) for name, mat in materials.items()}
    table = {tuple(round(x*65536) for x in v): k for k, v in enumerate(vs)}
    start_faces, start_vertices = len(mesh.faces), len(vs)
    min2 = (2*baker.min_edge)**2
    # faces by serial number (creation order), so that every choice is deterministic
    faces, normals, errors, users, children = {}, {}, {}, defaultdict(set), {}
    heap, splits, added, capped = [], 0, 0, False

    def length2(e):
        d = sub(vs[e[0]], vs[e[1]])
        return dot(d, d)

    def edges(face):
        a, b, c = face.indices
        return (edge(a, b), edge(b, c), edge(c, a))

    def longest(face):
        return max(edges(face), key=lambda e: (length2(e), e))

    def width(face):
        a, b, c = (vs[i] for i in face.indices)
        n = cross(sub(b, a), sub(c, a))
        return math.sqrt(dot(n, n)/length2(longest(face)))

    def enter(face, corner_normals):
        s = len(normals)
        faces[s], normals[s] = face, corner_normals
        for e in edges(face): users[e].add(s)
        errors[s] = baker.error(face, corner_normals)
        # faces narrower than min_edge (a rope, a rail) are left whole: they are a pixel or two wide
        if errors[s] > baker.tolerance and length2(longest(face)) >= min2 and width(face) >= baker.min_edge:
            # larger faces first: a pool of light across a floor before the dark line along a wall
            heapq.heappush(heap, (-errors[s]*math.sqrt(length2(longest(face))), s))
        return s

    def middle(e):
        p = tuple(quantize((x+y)/2) for x, y in zip(vs[e[0]], vs[e[1]]))
        key = tuple(round(x*65536) for x in p)
        if key not in table:
            table[key] = len(vs)
            vs.append(p)
        return table[key]

    def split(s, marked, mid):
        """Face s cut at the midpoints of its marked edges, longest first; its pieces enter."""
        face = faces.pop(s)
        for e in edges(face): users[e].discard(s)
        uvs = face.uvf or (None,)*3
        flat = None if smooth[face.material] else normals[s][0]
        work, out = [list(zip(face.indices, uvs, normals[s]))], []
        while work:
            cs = work.pop(0)
            best = None
            for k in range(3):
                e = edge(cs[k][0], cs[(k+1) % 3][0])
                if e in marked and (best is None or (length2(e), e) > best[0]): best = ((length2(e), e), k)
            if best is None:
                f = face.copy(tuple(i for i, _, _ in cs))
                f.local = None
                f.uvf = tuple(uv for _, uv, _ in cs) if face.uvf else None
                out.append(enter(f, tuple(n for _, _, n in cs)))
                continue
            (_, e), k = best
            if e not in mid: mid[e] = middle(e)
            P, Q, R = cs[k], cs[(k+1) % 3], cs[(k+2) % 3]
            uv = tuple((x+y)/2 for x, y in zip(P[1], Q[1])) if P[1] is not None else None
            M = (mid[e], uv, flat or norm(add(P[2], Q[2])))
            work[:0] = [[P, M, R], [M, Q, R]]
        children[s] = out

    order = [enter(face, n) for face, n in zip(mesh.faces, corner_normals(mesh, materials))]
    while heap and baker.max_added:
        _, s = heapq.heappop(heap)
        if s not in faces: continue          # split already, as a neighbour
        marked, stack = set(), [longest(faces[s])]
        while stack:
            e = stack.pop()
            if e in marked: continue
            marked.add(e)
            for t in sorted(users[e]): stack.append(longest(faces[t]))
        cut = sorted({t for e in marked for t in users[e]})
        cost = sum(len(users[e]) for e in marked)       # a face gains a triangle per split edge
        if added+cost > baker.max_added:
            capped = True
            break
        added += cost
        splits += 1
        mid = {}
        for t in cut: split(t, marked, mid)

    def final(s):
        return [s] if s not in children else [u for c in children[s] for u in final(c)]
    kept = [u for s in order for u in final(s)]
    mesh.faces = [faces[s] for s in kept]
    worst = max((errors[s] for s in kept), default=0.0)
    left = sum(errors[s] > baker.tolerance for s in kept)
    lit = []
    for s in kept:
        face, kind = faces[s], baker.kind[faces[s].material]
        if not kind[0]:
            lit.append(((1.0, 1.0, 1.0),)*3)
            continue
        lit.append(tuple(baker.corner(i, n, kind[3]) for i, n in zip(face.indices, normals[s])))
    mesh.lit = lit
    reached = []
    for light in baker.lights:
        count = 0
        for face in mesh.faces:
            if not baker.kind[face.material][0]: continue
            a, b, c = (vs[i] for i in face.indices)
            q = at(closest(light.at, a, b, c), a, b, c)
            if dot(sub(q, light.at), sub(q, light.at)) < light.range2: count += 1
        reached.append(count)
    section = {'count': len(baker.lights),
               'lights': [{'id': l.id, 'at': list(l.at), 'range': l.range, 'shadows': l.shadows,
                           'shadow_samples': len(l.samples) if l.shadows else 0, 'triangles_reached': n}
                          for l, n in zip(baker.lights, reached)],
               'refine': {'tolerance': baker.tolerance, 'min_edge': baker.min_edge, 'max_added': baker.max_added,
                          'added_triangles': len(mesh.faces)-start_faces, 'added_vertices': len(vs)-start_vertices,
                          'splits': splits, 'capped': capped, 'max_error': round(worst, 1),
                          'over_tolerance': left},
               'shadow_rays': baker.rays}
    warnings = []
    if capped:
        warnings.append({'code': 'light_refine_capped', 'count': len(mesh.faces)-start_faces,
                         'message': f'Refinement for the point lights stopped at lighting.refine.max_added '
                                    f'({baker.max_added} triangles) with faces still {round(worst, 1)} 8-bit steps from the '
                                    f'light (tolerance {baker.tolerance}): pools of light there are coarser than they '
                                    'should be. Raise max_added or tolerance, or raise min_edge.'})
    for l, n in zip(baker.lights, reached):
        if not n:
            warnings.append({'code': 'light_unused', 'light': l.id,
                             'message': f'Light {l.id!r} at {list(l.at)} reaches no lit face within its range '
                                        f'({l.range}). Move it, or raise its range.'})
    return section, warnings
