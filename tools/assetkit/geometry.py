"""Geometry uses conventional outward cross-product normals; export flips for Mei.

All operations retain face provenance and material names. No geometry library or
editor process is needed, which keeps recipes reproducible in agent sandboxes.
"""
from dataclasses import dataclass, field
import math

from kitcore.errors import KitError
from kitcore.vector import add, sub, mul, dot, cross, norm  # noqa: F401 (re-exported)


class AssetError(KitError):
    """A recipe error: a JSON Pointer path and an actionable message."""


@dataclass
class Face:
    indices: tuple
    material: str = "default"
    part: str = ""


@dataclass
class Mesh:
    vertices: list = field(default_factory=list)
    faces: list = field(default_factory=list)
    palette: dict = None   # set on the final mesh only: the palette entry assignment, if any

    def append(self, other):
        offset = len(self.vertices)
        self.vertices.extend(other.vertices)
        self.faces.extend(Face(tuple(i + offset for i in f.indices), f.material, f.part) for f in other.faces)
        # Bound intermediate expansion too: arrays of arrays must not exhaust memory.
        if len(self.vertices) > 65536 or len(self.faces) > 65536:
            raise AssetError("/nodes", "Intermediate geometry exceeds 65,536 vertices or triangles; reduce repetition/detail.")

    def mapped(self, fn, reverse=False):
        return Mesh([fn(v) for v in self.vertices], [
            Face(tuple(reversed(f.indices)) if reverse else f.indices, f.material, f.part) for f in self.faces])

    def bounds(self):
        return ([min(v[k] for v in self.vertices) for k in range(3)],
                [max(v[k] for v in self.vertices) for k in range(3)])


def area2(points):
    return sum(a[0]*b[1] - a[1]*b[0] for a, b in zip(points, points[1:] + points[:1]))


def turn(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def polygon(points, path):
    """Validate a simple polygon and triangulate concave outlines by ear clipping.

    Indices refer to the original input; output triangles are CCW. Collinear or
    repeated boundary points are rejected so side walls cannot silently collapse.
    """
    n = len(points)
    extent = max(max(p[k] for p in points)-min(p[k] for p in points) for k in (0, 1))
    eps = max(1e-24, extent * extent * 1e-12)
    for i in range(n):
        if abs(turn(points[i-1], points[i], points[(i+1) % n])) <= eps:
            raise AssetError(path, f"Polygon has duplicate/collinear points near index {i}.")
    def on_segment(a, b, c):
        return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and
                min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))
    for i in range(n):
        a, b = points[i], points[(i+1) % n]
        for j in range(i+1, n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            c, d = points[j], points[(j+1) % n]
            t = (turn(a, b, c), turn(a, b, d), turn(c, d, a), turn(c, d, b))
            touching = any(abs(v) <= eps and on_segment(*args) for v, args in zip(t, ((a,b,c), (a,b,d), (c,d,a), (c,d,b))))
            if touching or (t[0]*t[1] < 0 and t[2]*t[3] < 0):
                raise AssetError(path, f"Polygon edges {i} and {j} intersect.")
    order = list(range(n))
    if area2(points) < 0:
        order.reverse()
    remaining, triangles = order[:], []
    while len(remaining) > 3:
        for k, b in enumerate(remaining):
            a, c = remaining[k-1], remaining[(k+1) % len(remaining)]
            if turn(points[a], points[b], points[c]) <= eps:
                continue
            if any(all(turn(points[u], points[v], points[p]) >= -eps for u,v in ((a,b),(b,c),(c,a)))
                   for p in remaining if p not in (a,b,c)):
                continue
            triangles.append((a, b, c))
            remaining.pop(k)
            break
        else:
            raise AssetError(path, "Could not triangulate polygon; check its outline.")
    triangles.append(tuple(remaining))
    return order, triangles


def extrude(points, depth, path):
    order, caps = polygon(points, path)
    n = len(points)
    mesh = Mesh([(x, y, z) for z in (-depth/2, depth/2) for x,y in points])
    for a,b,c in caps:
        mesh.faces.extend((Face((c,b,a)), Face((a+n,b+n,c+n))))
    for a,b in zip(order, order[1:]+order[:1]):
        mesh.faces.extend((Face((a,b,b+n)), Face((a,b+n,a+n))))
    return mesh


def lathe(profile, segments, caps, path):
    mesh, rings = Mesh(), []
    if any(b[1] <= a[1] for a,b in zip(profile, profile[1:])):
        raise AssetError(path, "Lathe profile must have strictly increasing heights (pairs are [radius, y]).")
    for k, (r, y) in enumerate(profile):
        if r == 0 and k not in (0, len(profile)-1):
            raise AssetError(path, "A zero-radius pole is only allowed at the first or last profile point.")
        ring = []
        for i in range(segments if r else 1):
            ring.append(len(mesh.vertices))
            mesh.vertices.append((r*math.cos(math.tau*i/segments), y, r*math.sin(math.tau*i/segments)))
        rings.append(ring)
    for lower, upper in zip(rings, rings[1:]):
        if len(lower) == len(upper) == 1:
            raise AssetError(path, "Adjacent lathe poles do not form a surface.")
        for i in range(segments):
            j = (i+1) % segments
            a,b = lower[i % len(lower)], lower[j % len(lower)]
            c,d = upper[i % len(upper)], upper[j % len(upper)]
            if a != b:
                mesh.faces.append(Face((a,c,b)))
            if c != d:
                mesh.faces.append(Face((b,c,d)))
    if caps:
        for ring, reverse in ((rings[0], False), (rings[-1], True)):
            for i in range(1, len(ring)-1):
                tri = (ring[0], ring[i], ring[i+1])
                mesh.faces.append(Face(tuple(reversed(tri)) if reverse else tri))
    return mesh


def loft(sections, caps, path):
    mesh, orders, cap_faces = Mesh(), [], []
    n = len(sections[0]['points'])
    for k, section in enumerate(sections):
        if len(section['points']) != n:
            raise AssetError(path, "Every loft section needs the same number of corresponding points.")
        if k and section['y'] <= sections[k-1]['y']:
            raise AssetError(path, "Loft sections must have strictly increasing y.")
        order, triangles = polygon(section['points'], f"{path}/{k}/points")
        if orders and order != orders[0]:
            raise AssetError(path, "Loft sections must use the same winding and point correspondence.")
        orders.append(order)
        cap_faces.append(triangles)
        mesh.vertices.extend((x, section['y'], z) for x,z in section['points'])
    for k in range(len(sections)-1):
        for a,b in zip(orders[0], orders[0][1:]+orders[0][:1]):
            a,b,c,d = a+k*n,b+k*n,a+(k+1)*n,b+(k+1)*n
            mesh.faces.extend((Face((a,c,b)), Face((b,c,d))))
    if caps:
        mesh.faces.extend(Face(t) for t in cap_faces[0])
        offset = (len(sections)-1)*n
        mesh.faces.extend(Face(tuple(i+offset for i in reversed(t))) for t in cap_faces[-1])
    return mesh


def explicit_mesh(vertices, faces, path, face_materials=None):
    mesh = Mesh([tuple(v) for v in vertices])
    for k, ids in enumerate(faces):
        at = f"{path}/faces/{k}"
        if any(i >= len(vertices) for i in ids) or len(set(ids)) != len(ids):
            raise AssetError(at, "Face indices must be distinct and within the vertex array.")
        points = [vertices[i] for i in ids]
        # Newell's normal also works when a polygon's first three points are concave.
        normal = (0,0,0)
        for a,b in zip(points, points[1:]+points[:1]):
            normal = add(normal, cross(a,b))
        normal = norm(normal)
        if dot(normal, normal) == 0:
            raise AssetError(at, "Face has no area.")
        extent = max(math.sqrt(dot(sub(v, points[0]), sub(v, points[0]))) for v in points)
        if any(abs(dot(normal, sub(v, points[0]))) > max(1e-10, extent*1e-6) for v in points):
            raise AssetError(at, "Polygon is not planar; provide triangles explicitly.")
        axis = max(range(3), key=lambda i: abs(normal[i]))
        dims = [i for i in range(3) if i != axis]
        _, tris = polygon([[p[dims[0]],p[dims[1]]] for p in points], at)
        for tri in tris:
            a,b,c = (points[i] for i in tri)
            if dot(cross(sub(b,a), sub(c,a)), normal) < 0:
                tri = tuple(reversed(tri))
            mesh.faces.append(Face(tuple(ids[i] for i in tri), face_materials[k] if face_materials else 'default'))
    return mesh


def rotate(p, angles):
    x,y,z = p
    a,b,c = (math.radians(v) for v in angles)
    y,z = y*math.cos(a)-z*math.sin(a), y*math.sin(a)+z*math.cos(a)
    x,z = x*math.cos(b)+z*math.sin(b), -x*math.sin(b)+z*math.cos(b)
    x,y = x*math.cos(c)-y*math.sin(c), x*math.sin(c)+y*math.cos(c)
    return x,y,z


def transform(mesh, spec, path):
    scale = spec.get('scale', [1,1,1])
    if any(s == 0 for s in scale):
        raise AssetError(path+'/scale', "Scale components must be nonzero.")
    pivot, angles, move = (spec.get(k, [0,0,0]) for k in ('pivot','rotate','translate'))
    def apply(p):
        p = tuple((x-o)*s for x,o,s in zip(p,pivot,scale))
        return add(add(rotate(p, angles), pivot), move)
    return mesh.mapped(apply, math.prod(scale) < 0)


def modify(mesh, spec, path):
    op = spec['op']
    if op == 'subdivide':
        for _ in range(spec['levels']):
            if len(mesh.faces)*4 > 65536:
                raise AssetError(path, 'Subdivision exceeds 65,536 intermediate triangles.')
            result, midpoints = Mesh(mesh.vertices[:]), {}
            def midpoint(a,b):
                key = tuple(sorted((a,b)))
                if key not in midpoints:
                    midpoints[key] = len(result.vertices)
                    result.vertices.append(mul(add(mesh.vertices[a],mesh.vertices[b]),0.5))
                return midpoints[key]
            for face in mesh.faces:
                a,b,c = face.indices
                ab,bc,ca = midpoint(a,b),midpoint(b,c),midpoint(c,a)
                result.faces.extend(Face(t,face.material,face.part) for t in
                                    ((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
            mesh = result
        return mesh
    if op in ('taper','twist'):
        lo,hi = mesh.bounds()
        height = hi[1]-lo[1]
        if height == 0:
            raise AssetError(path, f"{op} needs a nonzero height along Y.")
        def deform(p):
            t = (p[1]-lo[1])/height
            if op == 'twist':
                return rotate(p, (0,t*spec['degrees'],0))
            bottom,top = spec.get('bottom',1),spec['top']
            s = bottom+(top-bottom)*t
            return p[0]*s,p[1],p[2]*s
        return mesh.mapped(deform)
    result = Mesh()
    if op == 'mirror':
        axis, offset = 'xyz'.index(spec['axis']), spec.get('offset',0)
        if spec.get('keep_original',True):
            result.append(mesh)
        result.append(mesh.mapped(lambda p: tuple(2*offset-v if i == axis else v for i,v in enumerate(p)), True))
    elif op == 'array':
        for i in range(spec['count']):
            result.append(mesh.mapped(lambda p: add(p,mul(spec['step'],i))))
    elif op == 'radial':
        axis = 'xyz'.index(spec.get('axis','y'))
        for i in range(spec['count']):
            angles = [0,0,0]
            angles[axis] = i*spec.get('degrees',360)/spec['count']
            result.append(mesh.mapped(lambda p: rotate(p,angles)))
    return result
