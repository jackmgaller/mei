"""Small vector helpers on tuples, and the console's conventions for yaw and 16.16 fixed point."""
import math

ONE = 65536


def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    length = math.sqrt(dot(a, a))
    return mul(a, 1 / length) if length else (0, 0, 0)


def yaw(v, degrees):
    """v turned about +Y as mesh_at() turns a model point: +Z toward +X,
    x' = x cos + z sin, z' = -x sin + z cos."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    # Exact for the quarter turns a level is mostly built from.
    if degrees % 90 == 0:
        c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][int(degrees // 90) % 4]
    return (v[0]*c + v[2]*s, v[1], -v[0]*s + v[2]*c)


def quantize(x):
    """A coordinate rounded to the nearest 16.16 value, as the Asset Kit exports vertices."""
    return round(x*ONE)/ONE
