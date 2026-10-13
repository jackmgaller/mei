"""Rigs (models/NAME/NAME.rig.json, written by the models' generators) and posing them.

A rig is a tree of rigid parts, each with its joint's offset from its parent's joint in the rest
pose, an optional rest rotation (the weapons'), its part recipe (origin at the joint) and the
ASSET_* name the cart's pack gives its mesh. Rotations are the Asset Kit's: degrees, applied X
then Y then Z (R = Rz Ry Rx) in the parent joint's frame. A part's matrix relative to the root
(the floor under the pelvis) is parent * T(offset) * R(rest) * R(pose); the pelvis also takes
the pose's offset (forward, up) in fight-local metres, forward being the model's -Z.
"""
import math
from pathlib import Path

from kitcore import jsonio
from kitcore.errors import KitError

# The runtime's part numbering (anim.akr's enum Part): the same for every mech of the cart, so a
# move's data is laid out alike. A rig may lack some (the Hero has no left weapon): those still
# get a joint (from the rig's mounts) but no mesh.
PARTS = ['pelvis', 'torso', 'head', 'pauldron_r', 'upper_arm_r', 'forearm_r', 'hand_r', 'weapon_r',
         'pauldron_l', 'upper_arm_l', 'forearm_l', 'hand_l', 'weapon_l', 'thigh_r', 'shin_r', 'foot_r',
         'thigh_l', 'shin_l', 'foot_l']


class AnimError(KitError):
    pass


# ---- 3 x 4 matrices: rows [r0, r1, r2] of (a, b, c, t)

IDENTITY = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0))


def rot_xyz(angles):
    """The rotation of Euler angles in degrees, X then Y then Z: Rz Ry Rx, as a 3 x 4 matrix."""
    a, b, c = (math.radians(v) for v in angles)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    # Rz Ry Rx with rx = [[1,0,0],[0,ca,-sa],[0,sa,ca]], ry = [[cb,0,sb],[0,1,0],[-sb,0,cb]],
    # rz = [[cc,-sc,0],[sc,cc,0],[0,0,1]]
    return ((cc*cb, cc*sb*sa-sc*ca, cc*sb*ca+sc*sa, 0.0),
            (sc*cb, sc*sb*sa+cc*ca, sc*sb*ca-cc*sa, 0.0),
            (-sb, cb*sa, cb*ca, 0.0))


def translate(t):
    return ((1.0, 0.0, 0.0, t[0]), (0.0, 1.0, 0.0, t[1]), (0.0, 0.0, 1.0, t[2]))


def mul(a, b):
    """a * b for 3 x 4 matrices (the implied fourth row 0 0 0 1)."""
    return tuple(tuple(a[i][0]*b[0][j]+a[i][1]*b[1][j]+a[i][2]*b[2][j]+(a[i][3] if j == 3 else 0.0)
                       for j in range(4)) for i in range(3))


def apply(m, p):
    return (m[0][0]*p[0]+m[0][1]*p[1]+m[0][2]*p[2]+m[0][3],
            m[1][0]*p[0]+m[1][1]*p[1]+m[1][2]*p[2]+m[1][3],
            m[2][0]*p[0]+m[2][1]*p[1]+m[2][2]*p[2]+m[2][3])


def fight_xy(p):
    """A root-relative model point in fight-local coordinates: x forward (the model's -Z), y up."""
    return (-p[2], p[1])


# ---- rigs

def vec(value, n, path):
    if not isinstance(value, list) or len(value) != n or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                                 for v in value):
        raise AnimError(path, f'Give {n} numbers.')
    return [float(v) for v in value]


class Rig:
    """A loaded rig: joints by id (every id of PARTS, from parts and mounts), in parent-first order."""

    def __init__(self, data, path):
        self.path = Path(path)
        self.folder = self.path.parent
        if not isinstance(data, dict) or data.get('format') != 'mei-rig':
            raise AnimError('/rig', f'{path} is not a rig (format "mei-rig").')
        self.name = data.get('name', self.path.stem.split('.')[0])
        self.joints = {}            # id -> {parent, offset, rest, recipe, asset, bounds}
        order = []
        for k, part in enumerate(data.get('parts', [])):
            where = f'/rig/parts/{k}'
            pid = part.get('id')
            if pid in self.joints:
                raise AnimError(where+'/id', f'Two parts are called {pid!r}.')
            parent = part.get('parent')
            if parent is not None and parent not in self.joints:
                raise AnimError(where+'/parent', f'{pid}: its parent {parent!r} comes later or does not exist '
                                                 '(parts are listed parent first).')
            self.joints[pid] = {'parent': parent, 'offset': vec(part.get('offset', [0, 0, 0]), 3, where+'/offset'),
                                'rest': vec(part['rotate'], 3, where+'/rotate') if part.get('rotate') else None,
                                'recipe': part.get('recipe'), 'asset': part.get('asset'),
                                'bounds': part.get('bounds')}
            order.append(pid)
        if not order or self.joints[order[0]]['parent'] is not None:
            raise AnimError('/rig/parts', 'The first part is the root (parent null).')
        self.root = order[0]
        # mounts without a part still give a joint (anim_part() can follow an empty hand's mount)
        for k, mount in enumerate(data.get('mounts', [])):
            mid = mount.get('id')
            if mid in self.joints or mount.get('parent') not in self.joints:
                continue
            self.joints[mid] = {'parent': mount['parent'], 'offset': vec(mount.get('offset', [0, 0, 0]), 3, f'/rig/mounts/{k}'),
                                'rest': vec(mount['rotate'], 3, f'/rig/mounts/{k}/rotate') if mount.get('rotate') else None,
                                'recipe': None, 'asset': None, 'bounds': None}
            order.append(mid)
        self.order = order
        self.poses = {}
        for name, pose in (data.get('poses') or {}).items():
            self.poses[name] = {'rotate': {j: vec(r, 3, f'/rig/poses/{name}/rotate/{j}')
                                           for j, r in pose.get('rotate', {}).items() if j in self.joints},
                                'offset': [0.0, -float(pose.get('drop', 0.0))]}
        # pairs of parts every move of the rig may pass into each other (a move's "allow" adds more)
        self.allow = set()
        for k, pair in enumerate(data.get('allow', [])):
            if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(v, str) for v in pair)):
                raise AnimError(f'/rig/allow/{k}', 'allow lists pairs of parts ["forearm_r", "weapon_r"].')
            self.allow.add(frozenset(pair))
        self.data = data
        self._proxies = None

    def children(self, pid):
        return [j for j in self.order if self.joints[j]['parent'] == pid]

    def pose_matrices(self, rotate, offset=(0.0, 0.0)):
        """{id: 3 x 4 matrix relative to the root} for a pose: rotate {id: [x, y, z] degrees},
        offset (forward, up) of the pelvis in fight-local metres."""
        out = {}
        for pid in self.order:
            j = self.joints[pid]
            off = list(j['offset'])
            if j['parent'] is None:
                off = [off[0], off[1]+offset[1], off[2]-offset[0]]
            m = translate(off)
            if j['rest']:
                m = mul(m, rot_xyz(j['rest']))
            r = rotate.get(pid)
            if r and any(r):
                m = mul(m, rot_xyz(r))
            out[pid] = m if j['parent'] is None else mul(out[j['parent']], m)
        return out

    def proxies(self):
        """{id: {'boxes': [(node, min, max)], 'points': [vertices]}} in each part's own frame,
        from its recipe compiled by the Asset Kit: an axis-aligned box per top-level node (a
        mirrored side's nodes counted as theirs), and every vertex (for the floor check)."""
        if self._proxies is None:
            from assetkit.compiler import compile_recipe
            out = {}
            for pid in self.order:
                recipe = self.joints[pid]['recipe']
                if not recipe:
                    continue
                path = self.folder/recipe
                try:
                    mesh, _, _ = compile_recipe(jsonio.load(str(path), AnimError), path.parent)
                except (OSError, KitError) as error:
                    raise AnimError('/rig', f'{pid}: its recipe {path} does not compile: {error}') from error
                nodes = {}
                for face in mesh.faces:
                    name = face.part.split('/')
                    if name[0] == 'mirrored' and len(name) > 1:
                        name = name[1:]
                    key = name[0]
                    lo, hi = nodes.setdefault(key, ([math.inf]*3, [-math.inf]*3))
                    for i in face.indices:
                        v = mesh.vertices[i]
                        for a in range(3):
                            lo[a] = min(lo[a], v[a])
                            hi[a] = max(hi[a], v[a])
                out[pid] = {'boxes': [(k, tuple(lo), tuple(hi)) for k, (lo, hi) in nodes.items()],
                            'points': [tuple(v) for v in mesh.vertices]}
            self._proxies = out
        return self._proxies

    def bounds(self, pid):
        """The part's bounds in its own frame (the rig's, else its recipe's), or None."""
        b = self.joints[pid].get('bounds')
        if b:
            return tuple(b['min']), tuple(b['max'])
        prox = self.proxies().get(pid)
        if not prox:
            return None
        lo = tuple(min(v[a] for v in prox['points']) for a in range(3))
        hi = tuple(max(v[a] for v in prox['points']) for a in range(3))
        return lo, hi


_RIGS = {}


def load_rig(path):
    path = Path(path).resolve()
    if path not in _RIGS:
        if not path.is_file():
            raise AnimError('/rig', f'No rig at {path}.')
        _RIGS[path] = Rig(jsonio.load(str(path), AnimError), path)
    return _RIGS[path]
