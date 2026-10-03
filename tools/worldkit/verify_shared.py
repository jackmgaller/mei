"""Everything the World Checker takes from the Asset Kit, in one place.

These are the shared-core pieces docs/WORLDKIT.md says both kits should import (NumPy loading,
PNG writing, the triangle-ID colour code, the ID-buffer diagnostic picture). They live in
tools/assetkit/ today and are expected to move to tools/kitcore/; when they do, only this
module changes.
"""
from assetkit.geometry_audit import numpy            # noqa: F401  (NumPy, or a clear error)
from assetkit.preview import png_bytes              # noqa: F401
from assetkit.visibility import diagnostic_png      # noqa: F401


def id_colour(n):
    """The GPU colour word that draws triangle ID n (1-32767) as the 15-bit pixel value n, with
    dithering off: the Asset Kit's identity_mesh() code (tools/assetkit/visibility.py)."""
    return ((n & 31) << 3) | (((n >> 5) & 31) << 11) | (((n >> 10) & 31) << 19)
