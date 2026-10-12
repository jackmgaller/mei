# Rendering: the depth buffer and perspective-correct texturing

The Prism Engine's second rendering mode, decided by the project owner on 2026-10-03 (the why,
the prototypes' measurements and the alternatives are in
[DECISIONS.md](DECISIONS.md#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu)).
This document is the interface: the registers, the packets, the depth format and test, the
perspective rule and the cost table, exactly as `src/core/gpu.c` implements them and
`tests/test_gpu.c` checks them. It is frozen: the standard library, the Reference Renderer and
the checkers are built against it. It supersedes the two prototype write-ups (`DEPTH.md` and
`PERSPECTIVE.md` on the prototype branches) and, where they differ, the v0.1 spec, which is left
as published.

**Status.** The emulator, the web build and the unit tests implement all of it. The standard
library's face loops, the cart API, the World Kit reader and the Reference Renderer's model of
it are not built yet (planned; see [What is not here](#what-is-not-here)).

## Summary

- **Opt-in, per polygon.** Packet types `0x30`–`0x3F` are the polygon packets `0x20`–`0x2F`
  followed by one word per vertex: the vertex's view depth *w*. Nothing else changes for the
  old types: a cart that never draws a `0x3X` packet draws exactly as before.
- **One depth word serves both features.** The GPU takes one reciprocal per vertex,
  2⁴⁰ ÷ *w*, and uses it for the depth test and for perspective.
- **Depth buffer:** 320 × 240 16-bit keys on the GPU (not in VRAM). The test is switched on by
  `GPU_DEPTH` bit 0 and applies to packets with depth only. A pixel passes when its key is at
  least the stored one. Opaque packets write the key; semi-transparent ones test but do not
  write.
- **Early depth:** a pixel that fails the test costs 1 GPU cycle, whatever its kind; one that
  passes costs what it always did. So opaque faces should be submitted nearest first, and
  semi-transparent ones after them, back to front.
- **Perspective:** every textured packet with depth has perspective-correct texture
  coordinates (the test on or off), with one divide every 16 pixels and steps between them.
  Textures stay unfiltered (nearest texel), and texture windows still apply.
- **Budget:** the Prism Engine runs at 120 MHz: **2,000,000 GPU cycles a tick**
  (`MEI_GPU_CYCLES_PER_FRAME`), twice the old 1,000,000, for every cart, whichever mode it uses.

## Packets with depth

A polygon packet's type is `0x20` plus four flags (spec p. 15): bit 0 Gouraud, bit 1 textured,
bit 2 quad, bit 3 semi-transparent. **Bit 4 is the depth flag**: types `0x30`–`0x3F` are the
same sixteen layouts with depth. After the header, the words are exactly those of the type
without bit 4 (colour, position and texture coordinate for each vertex, as in the spec), and
then **one depth word per vertex, in vertex order** (three for a triangle, four for a quad).

| Shape | Flat | Gouraud | Flat textured | Gouraud textured |
|---|---|---|---|---|
| Triangle with depth (`0x30`, `0x31`, `0x32`, `0x33`; semi-transparent `+8`) | 32 bytes | 40 bytes | 44 bytes | 52 bytes |
| Quad with depth (`0x34`, `0x35`, `0x36`, `0x37`; semi-transparent `+8`) | 40 bytes | 52 bytes | 56 bytes | 68 bytes |

Each is the plain packet's size plus 12 bytes (a triangle) or 16 (a quad); the largest packet,
`0x3F`, is 17 words. Every word is read and checked as for any packet: a depth word outside RAM
and the ROM window faults *Unmapped address* at that word. Types `0x40`–`0xFF` (and
`0x01`–`0x1F`) are still skipped as unknown.

**The depth word** is a signed 32-bit 16.16 number: the vertex's view depth *w*, the distance
in front of the camera along its axis. It is what `vproj` divides by and what `vxp3` leaves in
lane w (`DECISIONS.md`, "Geometry instructions"), so a face loop stores that lane as it is. It
is not clipped or checked: any value is accepted (see [the reciprocal](#the-vertex-reciprocal)
for *w* ≤ 1/16).

**The first colour word** keeps its meaning (bits 0–23 the colour, 24–25 the blend mode, 26 the
plane chip's layer bit, [PLANES.md](PLANES.md)). In a packet with depth, **bits 27–31 are the
decal offset** ([below](#the-decal-offset)). In packets without depth they are ignored, as
before.

## Registers

| Address | Name | Access | Purpose |
|---|---|---|---|
| `0xFF0020` | `GPU_DEPTH` | read/write | bit 0: test packets with depth against the depth buffer. Bits 1–31 are reserved: written values are ignored and they read 0 |
| `0xFF0024` | `GPU_ZCLEAR` | write | fill the whole depth buffer with bits 0–15 of the value (bits 16–31 ignored). Reads 0, like `GPU_DRAW` and `GPU_CLEAR` |

Both are word registers like the other GPU registers (a byte or halfword access faults *Bad
I/O width*). `0xFF0028`–`0xFF00FF` stay unmapped. At reset `GPU_DEPTH` is 0 and the depth
buffer holds 0 everywhere. The standard library names them `GPU_DEPTH` and `GPU_ZCLEAR` in
`stdlib/io.akr`.

The GPU draws when `GPU_DRAW` is written, so `GPU_DEPTH` applies to the packets of the lists
drawn while it is set: it may change between two `GPU_DRAW` writes in a frame (to draw a 3D
scene tested and an interface untested, say), and the change applies from the next list.

## The depth buffer

320 × 240 16-bit keys, one per pixel, in the GPU's own memory: not in VRAM, not addressable by
the CPU, and not double-buffered. Only three things change it: an opaque packet with depth
drawn while `GPU_DEPTH` bit 0 is set, `GPU_ZCLEAR`, and a reset. `GPU_CLEAR`, `vsync`, the
plane chip's auto-erase and `GPU_CTRL` do not touch it, so a cart that tests depth writes
`GPU_ZCLEAR` once a frame, before its scene (the standard library will do this for it).

A key is a 16-bit float of the inverse depth; **larger is nearer, and 0 is the farthest**
(everything at *w* ≥ 4,096 units). `GPU_ZCLEAR` with 0 makes every pixel pass the first
time; a larger value is a far limit (nothing whose key is below it draws).

## The vertex reciprocal

For each vertex of a packet with depth the GPU computes

    r = floor(2^40 / w)   when w >= 4096 (1/16 of a unit, in 16.16)
    r = 2^28              when w < 4096 (including w <= 0)

so r runs from 512 (*w* = 2³¹ − 1, the largest) to 2²⁸ (*w* = 1/16 or nearer). A quad's two
triangles (vertices 0-1-2 and 1-2-3) use their own three vertices' reciprocals. The same three
numbers serve the depth test and perspective, and the cost table charges for computing them
once a triangle.

## The depth test

**Inverse depth at a pixel.** 1/*w* is linear in screen space, so the GPU interpolates the
reciprocals exactly as it does colours (DECISIONS.md, "Rasterization"):

    z(p) = floor( (r0·E0(p) + r1·E1(p) + r2·E2(p)) / area )

where E*i*(p) is the edge function opposite vertex *i* (the weight of vertex *i*) and area
their sum, over the pixels the triangle covers by the usual top-left rule. Inside the triangle
every E*i* ≥ 0, so z lies between the smallest and the largest r: 512 ≤ z ≤ 2²⁸. The arithmetic
is exact integer arithmetic in 64 bits; coverage is unchanged.

**The key** of z is a 16-bit float with a 4-bit exponent and a 12-bit mantissa:

    z < 4096:        key = 0
    otherwise:       e = floor(log2 z) - 12            (0 to 16)
                     key = 0xFFFF                      if e > 15 (z = 2^28)
                     key = e << 12 | (z >> e) & 0xFFF  otherwise

It is monotonic in z. One step is 1/4,096 to 1/8,192 of the depth at any *w* from 1/16 to
4,096 units; beyond 4,096 units every key is 0. Golden values (`test_depth_key`):

| *w* (units) | 16.16 | r | key |
|---|---|---|---|
| 1/16 or nearer, 0, negative | ≤ `0x1000` | 2²⁸ | `0xFFFF` |
| 0.5 | `0x8000` | 2²⁵ | `0xD000` |
| 1 | `0x10000` | 2²⁴ | `0xC000` |
| 1.5 | `0x18000` | 11,184,810 | `0xB555` |
| 2 | `0x20000` | 2²³ | `0xB000` |
| 3 | `0x30000` | 5,592,405 | `0xA555` |
| 100 | `0x640000` | 167,772 | `0x547A` |
| 128 | `0x800000` | 2¹⁷ | `0x5000` |
| 4,095 | `0xFFF0000` | 4,097 | `0x0001` |
| 4,096 or farther | ≥ `0x10000000` | ≤ 4,096 | `0x0000` |

**The test.** When `GPU_DEPTH` bit 0 is set, every pixel of a packet with depth is tested
before anything else is done for it:

    key' = min(0xFFFF, key + decal offset)
    pass  when key' >= the stored key

- A pixel that **passes** goes through the pixel pipeline as always (texel, index 0, tint,
  dither, blend, write). If it is written (a textured pixel whose texel is index 0 is not)
  and the packet is **opaque** (type bit 3 clear), key' is stored at that pixel.
- A pixel that **fails** is not drawn and changes nothing; its texel is not read.
- A **semi-transparent** packet tests and never writes the depth buffer: what is behind a
  pane of glass drawn first still draws (and blends under nothing: draw it before the glass),
  and the glass does not hide what is drawn after it.
- **Ties go to the later packet** (≥), as polygons in one ordering-table bucket did.

When `GPU_DEPTH` bit 0 is clear, packets with depth are neither tested nor written: an
untextured one draws exactly as the packet without bit 4, at the same cost; a textured one is
still perspective-correct ([below](#perspective-correct-texturing)) and charged for it.

**Packets without depth** (`0x20`–`0x2F`) are never tested and never write the buffer,
whatever `GPU_DEPTH` says. They draw over whatever is in the framebuffer, in list order, as in
the spec: interface, text and sprites drawn after the scene are on top of it.

**Drawing order.** The test makes the order of opaque faces irrelevant to the picture (but for
ties and decals), not to the cost: a hidden pixel drawn first costs its full price and is then
drawn over. With early depth, opaque faces submitted **nearest first** cost least.
Semi-transparent faces still need the old order: after the opaque ones, **back to front**.

## The decal offset

Bits 27–31 of a packet with depth's first colour word, 0–31: the number of key steps added to
the packet's keys, for the test and for what it writes. A decal (a sign, a poster, a road
marking) drawn with offset 2 on a coplanar wall wins whichever is drawn first: drawn after the
wall it passes the tie with room to spare; drawn before, it writes its keys plus 2, so the
wall's pixels fail there. A key step is relative (1/4,096 of the depth), so the same offset
works at any distance; it is not a distance in units. 2 is enough for a facing surface; a
surface seen at a grazing angle needs more (see [Precision](#precision)). The sum saturates
at `0xFFFF`.

## Perspective-correct texturing

Every **textured packet with depth** is mapped perspective-correct, whether or not the depth
test is on. Untextured packets have nothing to correct: their colours are interpolated
affinely (as are a textured packet's), exactly as in packets without depth.

**Per triangle**, from the vertex reciprocals r*i*:

    s = the smallest shift >= 0 such that max(r0, r1, r2) >> s < 65536
    q_i = max(1, r_i >> s)                                   (1 to 65,535)

If q0 = q1 = q2 the triangle is **affine**: u and v are interpolated exactly as in a packet
without depth (`floor(sum u_i·E_i / area)`), and no divides are made or charged. A face
parallel to the screen, a billboard or a sprite with one *w* for all its corners therefore
draws exactly as it would without depth. Otherwise three planes are interpolated across the
triangle:

    U(p) = sum q_i·u_i·E_i(p)     V(p) = sum q_i·v_i·E_i(p)     Q(p) = sum q_i·E_i(p)

**Per span.** A span is a row's pixels inside the triangle, x0 to x1 (the same pixels as
without depth, clipped to the screen). The span walker **divides** at x0, at every 16th pixel
after it (x0 + 16, x0 + 32, …) while that is before x1, and at x1:

    S(x) = floor(U(x) · 65536 / Q(x))        (u in 16.16; likewise T(x) for v)

At a divide point the pixel uses S(x) itself. A pixel x between two neighbouring divide points
a < x < b uses

    S(a) + (x - a) · trunc((S(b) - S(a)) / (b - a))

where trunc rounds toward zero (C's integer division). The texel coordinate is **u = S >> 16**
(and v = T >> 16): the nearest texel, no filtering. U and Q are both positive inside the
triangle and S is a convex combination of the vertices' u (times 65,536), so u never leaves
0–255 and equals u*i* at vertex *i*; the stepped values lie between their two ends. A span of
n pixels makes **1 + ⌈(n − 1) ÷ 16⌉ divides** (1 for one pixel, 2 for 2–17, 3 for 18–33, …).

Then the texel is looked up as always: the **texture window** (DECISIONS.md, "Texture
windows") maps the corrected u, v; 4-bit and 8-bit textures, palettes, slot wrapping and index
0 (transparent) are unchanged. The divide-every-16 rule gives the slight drift of a 1997 span
renderer between divide points (about a fifth of the pixels of a receding floor are one texel
off the exact picture, [DECISIONS.md](DECISIONS.md#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu)),
and none at the divide points.

**Golden values** (`test_perspective`): a full-screen quad, type `0x36`, corners (0, 0),
(319, 0), (0, 239), (319, 239) with u, v (0, 0), (255, 0), (0, 255), (255, 255) and *w* 4, 4,
1, 1 (a floor receding upward). The texel u, v at some pixels:

| Pixel | u, v | Pixel | u, v | Pixel | u, v |
|---|---|---|---|---|---|
| (0, 0) | 0, 0 | (0, 60) | 0, 146 | (0, 120) | 0, 204 |
| (15, 0) | 11, 0 | (16, 60) | 7, 146 | (160, 120) | 52, 204 |
| (16, 0) | 12, 0 | (17, 60) | 7, 146 | (318, 120) | 253, 204 |
| (17, 0) | 13, 0 | (200, 60) | 91, 146 | (17, 180) | 4, 235 |
| (160, 0) | 127, 0 | (0, 119) | 0, 203 | (200, 180) | 138, 235 |
| (318, 0) | 254, 0 | (160, 119) | 51, 203 | (16, 238) | 12, 254 |
| | | | | (318, 238) | 254, 254 |

Rows 0–119 belong to the triangle 0-1-2, rows 120–238 to 1-2-3 (each with its own spans).

## The Horizon Engine and the framebuffer

Depth orders polygons among themselves only. The plane chip ([PLANES.md](PLANES.md)) composites
at `vsync` exactly as before: a polygon pixel's layer bit (colour bit 26) still puts it in front
of or behind the planes, holes (`0x8000`) are still holes, and a blended packet over a hole
still blends with the layers behind it. A pixel that fails the depth test leaves the
framebuffer pixel as it was, hole or not. The planes have no depth and cost nothing, as before.
The depth buffer is not erased by the plane chip's auto-erase.

## Texture slots and palette banks (VRAM at 2 MB)

Added on 2026-10-05 with the second megabyte of VRAM ([DECISIONS.md](DECISIONS.md#vram-at-2-mb)),
for every textured packet, with depth or without. Bits 16–31 of a packet's first texture
coordinate:

| Bits | Field |
|---|---|
| 16–19 | slot within its bank of 16 |
| 20 | 4-bit texture |
| 21 | **slot bank**: 0 slots 0–15 (`0x480000`), 1 slots 16–31 (`0x500000`) |
| 22 | **palette bank**: 0 colours 0–4095 (`0x44C000`), 1 colours 4096–8191 (`0x580000`) |
| 23 | reserved (ignored) |
| 24–31 | palette within its bank: 0–255 for 4-bit, 0–15 for 8-bit (bits 28–31 ignored) |

So slot *n* is at `0x480000 + n × 0x8000` for *n* 0–31, and 4-bit palette *p* 0–511 is bank
*p* ÷ 256, palette *p* mod 256 (8-bit palette *q* 0–31: bank *q* ÷ 16, palette *q* mod 16). An
8-bit texture's second slot wraps within its bank: slot 15 into slot 0 (as before), slot 31 into
slot 16. A packet with bits 21–22 clear draws exactly as before. Neither field costs a GPU cycle.
The plane chip reads palette bank 0 only.

## Cost

The cost table (DECISIONS.md, "GPU budget") with the new terms; constants `GPU_CYCLES_*` in
`src/core/machine.h`, applied in `draw_poly()` and `gpu_zclear()` in `src/core/gpu.c`.

| Work | GPU cycles | Constant |
|---|---|---|
| a triangle's setup (every triangle counted against the limit, empty and off-screen ones too) | 40 | `GPU_CYCLES_TRI` |
| a pixel that passes the depth test, or is not tested: flat or Gouraud / textured / semi-transparent / both | 1 / 2 / 2 / 4 | `GPU_CYCLES_PX`, `_TEX_X`, `_SEMI_X` |
| a pixel that **fails** the depth test, of any kind | **1** | `GPU_CYCLES_ZFAIL` |
| the vertex reciprocals: each triangle of a packet with depth that is depth-tested (`GPU_DEPTH` on) **or** textured, once even when both | **24** | `GPU_CYCLES_RECIP` |
| each perspective divide (a span's first pixel, every 16th, its last: 1 + ⌈(n − 1) ÷ 16⌉ a span of n pixels), triangles that are not affine only | **2** | `GPU_CYCLES_DIVIDE` |
| `GPU_ZCLEAR` (76,800 keys at half a cycle, as `GPU_CLEAR`) | **38,400** | `GPU_CYCLES_ZCLEAR` |
| `GPU_CLEAR` | 38,400 | `GPU_CYCLES_CLEAR` |
| an untextured packet with depth while `GPU_DEPTH` is off: as without depth | +0 | |
| writing `GPU_DEPTH`, the depth words, the key, the decal offset, triangles over the limit | 0 | |

A pixel counts when it is inside the triangle, as before: a passing textured pixel whose texel
is 0 costs 2 (it was read), a failing one 1 (it was not). The budget is **2,000,000 GPU cycles
a tick** (`MEI_GPU_CYCLES_PER_FRAME`, `GPU_BUDGET` in `stdlib/runtime.akr`); a frame over it is
presented at the first tick end at which its cycles are at most 2,000,000 × the ticks since the
last present (DECISIONS.md, "Lag", with the new figure). The triangle limit stays 4,000.

Examples, each checked in `tests/test_gpu.c`:

| Drawn | GPU cycles |
|---|---|
| a flat quad with depth, 20 × 20, tested over a cleared buffer | 2 × (40 + 24) + 400 = 528 |
| then a flat quad, 20 × 20, behind it and overlapping 10 × 10 | 2 × (40 + 24) + 300 + 100 × 1 = 528 |
| a textured triangle with depth (55 pixels), tested, all failing | 40 + 24 + 55 = 119 (a plain one: 150) |
| the same, textured and semi-transparent, all passing | 40 + 24 + 220 = 284 |
| a textured triangle with depth, test off, one *w* for all corners | 40 + 24 + 110 = 174 |
| the receding floor of the golden values (76,241 pixels, 5,437 divides, test off) | 2 × (40 + 24) + 152,482 + 2 × 5,437 = 163,484 (affine: 152,562, so +7.2 %) |

## Frame statistics

`MeiGpuStats` (`mei_gpu_stats()`, `src/core/mei.h`) counts, besides the old fields, for the last
presented frame:

| Field | `--gpu-stats` column | What |
|---|---|---|
| `px_ztest` | `px_ztest` | pixels of depth-tested triangles, passed or failed (they are in `px[]` too) |
| `px_zfail` | `px_zfail` | of those, pixels that failed (charged 1 each) |
| `zclears` | `zclears` | `GPU_ZCLEAR` writes |
| `tris_recip` | `tris_recip` | triangles charged the reciprocal setup |
| `px_persp` | `px_persp` | pixels of triangles drawn perspective-correct (not affine; in `px[]` too) |
| `persp_divs` | `persp_divs` | perspective divides |

`mei-headless --gpu-stats out.csv` writes them after `gpu_lag`, and `tools/mei_gpustats.py`
adds a table of them for runs that use either feature.

## Precision

Measured on the depth prototype (`tests/depth/precision.c` on its branch, with the same key):
the smallest separation at which nothing of a face behind shows through a face drawn before it.

| Distance (units) | Wall, facing | Floor at 11° | With offset 2 |
|---|---|---|---|
| 8 | 2.3 mm | 2.7 cm | coplanar |
| 128 | 3.3 cm | 39 cm | coplanar |
| 1,024 | 31 cm | 3.6 m | coplanar |

The facing wall needs one key step; the floor needs about ten, because vertex positions are
whole pixels, so a face's plane is off by up to half a pixel's worth of depth. That limit is
the same whatever the buffer's format.

## Implementation notes

- Everything is integer and exact: `zkey()` and `persp_div()` (U · 65,536 ÷ Q by two 8-bit
  long-division steps, so no 128-bit arithmetic) in `src/core/gpu.c`. The products stay
  within 63 bits for any vertex coordinates (−32,768–32,767): r ≤ 2²⁸, q < 2¹⁶ and the area
  is below 2³⁴. A reference independent of that code (`ref_tri_z` in `tests/test_gpu.c`, with
  128-bit division) agrees on 400 random packets of every kind, including huge and degenerate
  ones, and a Python version of the rule gives the golden values above.
- Fast paths: `span_ext()` is specialised at compile time for every combination of the depth
  test, perspective and the old flags (56 functions), stepping the colours with the same
  fixed-point accumulators as `span_fixed()` and the inverse depth with an exact
  quotient/remainder DDA. The old types still take the old spans, unchanged. On the unit
  tests' benchmark (2,000 textured Gouraud triangles of about 35 × 36 pixels, M1 Pro):
  4.5 ms a frame plain, 5.5 ms depth-tested, 7.0 ms depth-tested and perspective.

## What is not here

Planned for the next phase, against this document:

- **Standard library:** face loops that write packets with depth (the prototypes generated them
  from `tools/gen_faces_asm.py`), with the ordering table putting opaque faces in nearest
  first and semi-transparent ones after them back to front; `GPU_ZCLEAR` each frame; a cart
  API to turn the mode on, set the decal offset, and draw sprites and billboards with depth;
  the combination with `planes.akr`.
- **World Kit reader** (`stdlib/worldpack.akr`) drawing worlds in the new mode, and what that
  makes unnecessary (object keys and biases, the ground pass).
- **Reference Renderer:** packets with depth, the key, the test and the perspective rule in the
  independent renderer, and their fuzzing.
- **Checkers:** the Asset and World Checkers in the new mode.
