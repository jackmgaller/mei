# The Reference Renderer

The Reference Renderer checks Mei itself: it compares what the console draws for deterministic
stress scenes with what an independent renderer, written in Python from the documented rules,
says it must draw. The reference starts from a scene's mesh files, texture bytes, palettes and
camera matrices. It never reads Mei's rendered pixels or the packets Mei emits to decide what
the expected image is. Every comparison is exact: one pixel off is a failure.

It is one of three checkers ([DECISIONS.md](../../docs/DECISIONS.md), "The kits and the first
open-world game"): the Asset Checker judges one asset, the World Checker a level, and the
Reference Renderer the console (CPU, standard library, Prism Engine and Horizon Engine). It
models both of the Prism Engine's modes: the ordering-table mode of the v0.1 spec, and the depth
buffer with perspective-correct texturing ([RENDERING.md](../../docs/RENDERING.md)), including
the GPU cost table, cycle for cycle.

```sh
make rendercheck            # stress scene, subdivision, GPU fuzzing, plane compositor,
                            # depth scenes, depth fuzzing
make rendercheck-motion     # moving meshes, animated textures, moving planes, depth in motion
make B=build-mine rendercheck   # everything built into build-mine/ instead of build/
```

On an Apple M1 Pro, `make rendercheck` takes about 80 s with the native tools built (55 s
before the depth checks were added: the plane compositor is most of it, the depth fuzzer about
20 s, the fuzzer 12 s, the stress scene and the depth scenes 4 s each, subdivision 1 s) and
`make rendercheck-motion` about 41 s (6 s of it the depth scenes with 48 frames of motion).
Times vary with the machine's load. `make test` runs the stress scene and subdivision checks
(about 5 s) when NumPy and Pillow are installed, and writes their output to
`$(B)/reference_renderer/test.log`.

Each command exits 1 at the first check that fails. Everything a check makes is built into
`$(B)/reference_renderer/` on each run: its generated carts and their assets (`carts/NAME/`,
compiled to `NAME.mei` with the build directory's `meic`), the probes, and one folder of images
and a `report.json` per check. Nothing it generates is committed.

**Dependencies:** a C compiler, Python 3.9 or later, **NumPy** (1.17 or later) and **Pillow**
(9.1 or later; with WebP support for `plane_motion_check.py`'s animated preview). The checks also
import `tools/meshlib.py`, the native mesh writer.

## Files

| File | What it is |
|---|---|
| `oracle.py` | The independent renderer: mesh reading, transforms, clipping, culling, ordering-table sort, fog, and an exact pixel rasterizer. Run on its own, it checks the nine-view stress scene |
| `gen_scene.py` | Writes the stress scene: its cart, meshes, textures, palette and `scene.json` |
| `geometry_check.py` | Subdivision: twelve views of a wall at levels 0–3 |
| `fuzz.py` | 64 adversarial GPU scenes covering all 16 packet kinds, replayed through the GPU alone |
| `planes_check.py` | A separately written scalar plane compositor ([PLANES.md](../../docs/PLANES.md)) and 64 full-VRAM replays |
| `planes_feedback.py` | A diagnostic for a fixture whose atlas overlaps the pixels being drawn (not in `make rendercheck`) |
| `motion_check.py` | A moving, textured, subdivided and near-clipped mesh scene over a full 64-step loop |
| `texture_check.py` | Animated textures and palettes on sprites, mapped to presented frames |
| `plane_motion_check.py` | One Mei instance over 24 frames of moving, animated planes |
| `depth.py` | The depth and perspective mode from RENDERING.md: the vertex reciprocal, the key, the test, decal offsets, perspective spans, the cost table and the frame statistics, as a GPU state that takes register writes |
| `depth_check.py` | Twelve views in the depth mode, GPU only and end to end through a cart, with the cycle budget; `--motion N` adds frames of camera motion |
| `depth_fuzz.py` | Adversarial frames of packets with depth, compared in framebuffer, depth buffer and every cost counter, with four negative controls |
| `gpu_probe.c`, `planes_probe.c`, `plane_motion_probe.c`, `depth_probe.c` | Replay probes: load packets, VRAM and plane registers straight into the core (`libmeicore.a`) and dump the buffers (`depth_probe.c` also the depth buffer and the GPU's counters, after register writes made through the bus) |
| `common.py` | Paths and builds: the build directory (`MEI_BUILD`, which `make B=...` sets), compiling probes and carts |

Each script runs on its own from anywhere (`python3 tests/reference_renderer/fuzz.py --help`);
it builds the native tools it needs with `make` into the build directory `MEI_BUILD` names
(default `build`). `oracle.py` checks the scene `gen_scene.py` last wrote, so run that first.
The carts can be played: `build/mei build/reference_renderer/scene.mei` (A and B change the
view), `subdivision.mei` (A), `motion.mei` (A pauses), `textures.mei` (hold A to overload the
GPU) and `depth.mei` (the depth views in turn; A pauses).

## How the reference works

`oracle.py` reads the raw mesh files and the scene description and does the console's work
again, in its own code:

- **Geometry**: model and view matrices composed as the public `mat4_mul` does it (each of the
  four scaled rows rounded before they are added, unlike `vxfm`'s fused dot product, which
  rounds once), vertex transform, projection with its clamp, the near plane and the guard band
  (polygon clipping with Mei's documented rounding, then fan pairing into strips), back-face
  culling, the 1,024-bucket ordering table by average depth, fog per vertex.
- **Pixels**: exact integer barycentric weights at each pixel centre, evaluated directly from
  the three edge functions with NumPy, where Mei walks scanlines incrementally; the top-left
  fill rule; 4-bit and 8-bit texels, palettes, index-0 transparency, the slot 15 → 0 wrap,
  texture windows; tint, dithering, RGB555 quantization and the four blend modes, all as
  [DECISIONS.md](../../docs/DECISIONS.md) states them.

`depth.py` models packets with depth from [RENDERING.md](../../docs/RENDERING.md) alone,
not from `src/core/gpu.c` or the reference in `tests/test_gpu.c`:

- **Depth**: the vertex reciprocal 2⁴⁰ ÷ *w* (2²⁸ for *w* below 1/16, zero and negative
  included), the inverse depth `floor(Σ rᵢEᵢ ÷ area)` from the same exact weights as the
  colours, the 16-bit key (exponent found by comparison, not by a logarithm), the decal offset
  with its saturation, the test with ties to the later packet, opaque packets writing and
  semi-transparent ones not, and texel 0 neither drawing nor writing. `GPU_DEPTH` and
  `GPU_ZCLEAR` are register writes to a GPU state that lasts across lists and frames.
- **Perspective**: q*ᵢ* scaled to 16 bits, the affine case when they are equal, each row's span
  from its first to its last covered pixel, divides at the span's start, every 16th pixel and
  its end in Python's unbounded integers (no 128-bit splitting), truncated steps between them,
  then the old texture window, palette and index-0 rules.
- **Cost**: every term of the cost table (40 a triangle, 24 for the reciprocals, 1 a failing
  pixel, 1/2/2/4 a passing or untested one, 2 a divide, 38,400 a clear or depth clear) and the
  six new frame statistics, compared with Mei's exactly.
- **Golden values**: run on its own (and at the start of `depth_check.py`), `depth.py` checks
  itself against RENDERING.md's key table and every texel of its perspective table, with that
  receding floor's 5,437 divides and 163,484 cycles.

It shares `oracle.py`'s dither matrix and texture-window function and `planes_check.py`'s
compositor (for blends over holes and for the displayed picture), and its rasterizer is written
the same way as `oracle.render`'s, though separately.

The contract is the public mesh and clipping API and the rounding, fill, palette, tint, dither,
window and blending rules in DECISIONS.md, and RENDERING.md for packets with depth. Where the
reference matches Mei, Mei follows its own rules. That does not mean the rules look natural:
affine texture warp (and the drift between perspective divides), nearest-neighbour aliasing,
pixel snapping, average-depth ordering artefacts and depth-key ties appear in both images,
because the reference keeps them on purpose.

**What it does not share with Mei.** No Akari code, no C code, no packets and no pixels. The
expected inputs are authored in Python: meshes, matrices and animation formulas, subdivision
by bisection in object space, texture and palette state over time. What is shared, and where a
common mistake could hide: the input files themselves (written with `tools/meshlib.py`, the
same writer the carts use, but read back byte by byte by `oracle.py`); the clipping algorithm's
shape (which planes, in which order, how the pieces are paired), which `oracle.py` takes from
the documented API; and, inside the suite, the pixel stage: `geometry_check.py`,
`motion_check.py`, `texture_check.py` and `fuzz.py` draw with `oracle.py`'s rasterizer.
`planes_check.py` shares nothing with `oracle.py`; `planes_feedback.py` and
`plane_motion_check.py` use `planes_check.py`'s compositor.

## The checks

### Stress scene (`gen_scene.py`, `oracle.py`)

39 mesh instances: 30 textured and shaded boxes, five Gouraud spheres, a floor of 100 textured
tiles, four translucent panels (one per blend mode), four slanted triangles that cross the near
plane and the guard band, and five panels with texture windows. 653 source faces, 1,021–1,122
triangles per view. Nine views: overview, a camera offset by a fraction of a pixel, a side
camera, near clipping, guard-band clipping, dithering off, fog, near clipping with fog, and
rotated, non-uniformly scaled models.

The five textures cover 4-bit and 8-bit sampling, separate palettes, transparent index 0,
full-range coordinates, odd 8-bit slots and slot 15 wrapping into slot 0. The full-range,
high-frequency textures expose aliasing on purpose. Both windings, shared quad edges,
degenerate pole faces, flat and Gouraud tint, fog and dithering are present. The window panels
use both texture depths, one axis or both, and an origin plus size past 256; one of the clipping
triangles has a window too, so the pieces clipping makes must keep it (2,226 pixels of the
overview and 9,293 of the near view depend on the windows).

Each view is compared twice:

1. **End to end**: the cart runs on the real CPU, standard library and GPU in `mei-headless`;
   its displayed frame is compared with the reference.
2. **GPU only**: `gpu_probe.c` replays the reference's own packets and texture and palette
   memory through the GPU, and the result is compared with the same reference image.

A difference only in the first points at geometry or packet building (the standard library);
one in the second at the rasterizer or the pixel pipeline. The GPU-only path takes the
reference's geometry, so agreement there checks rasterization, not the geometry rules a second
time. The script also fails a view where Mei presents no frame or drops triangles.

### Subdivision (`geometry_check.py`)

A wall spanning view depths 1 to 5, drawn with constant flat tint, constant Gouraud tint and a
colour gradient, each at subdivision levels 0–3: twelve views. Its opposite depth-varying edges
split together, giving 1, 2, 4 and 7 quads. The reference bisects the wall in object space and
averages each channel itself. A white texture and dithering off make a one-step shading error
visible: every source channel is 65, which the white texel and tint turn into 129 (5-bit 16),
while a midpoint one too dark gives 127 (5-bit 15).

### GPU fuzzing (`fuzz.py`)

64 scenes of 16 packets each, one of every packet kind, through `gpu_probe.c`: full signed
16-bit positions, thin and degenerate triangles, both windings, both texture depths, every slot,
palette and blend mode, both dither settings, 200 triangles large enough for the rasterizer's
large-area path, and texture windows (every size code on each axis, any origin) on half the
textured packets. Each packet is also replayed alone, so that later opaque packets cannot hide
an error in an earlier one: 83,558,400 pixel comparisons. `--seed` and `--scenes` change the
run; failing scenes are saved as packet files with their images.

### Plane compositor (`planes_check.py`, `planes_feedback.py`)

64 cases, each a complete 1 MB VRAM image, the plane registers and optional polygon packets,
replayed by `planes_probe.c`, which captures both the polygon framebuffer and the displayed
composite after vsync. The reference is a scalar implementation of PLANES.md: it sorts explicit
candidate tuples and samples each atlas per pixel, where the Horizon Engine uses per-line tile
runs and incremental affine coordinates. Half the cases draw eight translucent quads (every
blend mode, both polygon layers) over the plane stack; the other half compose directly. They
cover 8×8 and 16×16 tiles, both atlas depths, flips, transparent texels, palette offsets and
bank wrap, 32/64/128 maps, addresses across the end of VRAM, all priority ties and orders, tile
priority bits, colour math, signed offsets, backdrop dithering, empty, one-pixel and oversized
windows, negative fractional affine coordinates and sums beyond 32 bits, every outside mode, and
eight line channels at once (conflicts, reserved targets, writes past the valid registers,
tables wrapping through VRAM). 9,830,400 pixel comparisons.

GPU-drawing cases keep line tables, maps, atlases and palettes outside the pixels being drawn;
compose-only cases may let them wrap into the framebuffer, where sampling depends only on the
finished input. When an atlas overlaps the pixels being drawn, the result depends on the order
pixels are written in, which a static-input reference cannot predict. `planes_feedback.py`
builds such a fixture (case 33 with BG2's atlas register rewritten line by line, as this
fixture first was): the static reference disagrees on 51 framebuffer pixels, and a pixel-live
reference that updates VRAM after every pixel, in the GPU's triangle, row and column order,
agrees on all of them. It shows where the difference comes from; it uses Mei's traversal order,
so it is not an independent contract for it.

### Motion (`motion_check.py`)

Ten cubes moving and turning on their own paths, a subdivided wall and a triangle moving
through the near plane, under a camera that yaws and moves by fractions of a pixel. Every mesh
uses a 256×256 4-bit texture with fine boundaries and transparent holes; cube corners have
different tints, so Gouraud colour and texture coordinates both change under motion. The
reference composes the authored fixed-point matrices for each step itself; the cart loads the
same matrices as inputs. Four steps deliberately overrun the CPU budget for two extra ticks, so
captures are matched to the headless runner's presented-frame log rather than to tick numbers,
and each held tick must still show the preceding frame. `make rendercheck-motion` checks 128
presented frames (two loops); consecutive frames' signed differences must match too.

### Animated textures (`texture_check.py`)

A real cart with 20 overlapping textured quads per frame (moving, sheared, clipped at the screen
edge, scrolling coordinates) and a 16-pixel binary frame marker. Full texture uploads every 8
or 12 frames and 32 bytes rewritten in place every frame; `palette_lerp` through both
endpoints, `palette_rotate` both ways; 4-bit pages in slot 8, 8-bit pages from the odd slot 3,
an 8-bit slot-15 page wrapping into slot 0, high palette bits ignored for 8-bit pages; index-0
transparency over a coloured palette entry and a black non-zero index that must draw; 1:1 and
scaled mirroring, changing tints, opaque and all four blend modes, dithering alternating. A
normal run of 96 frames, and an overload run of 64 ticks in which eight full-screen blended
layers make each frame take three ticks (22 presented). The reference state comes from the
animation formulas; two deliberately wrong states at frame 8 (a texture upload one frame stale,
a palette one frame late) must differ from it, to show the comparison is sensitive to both.

### Plane motion (`plane_motion_check.py`)

One persistent Mei instance over 24 frames (`--frames N` for more): both atlases (4-bit and
8-bit) and the palettes change every frame, the layers scroll, line tables move the backdrop,
an affine plane and the windows, and two translucent quads move over it all.
`plane_motion_probe.c` uploads each frame's resources, draws into the real back buffer and
captures three buffers per frame: the display before vsync (must still be the previous frame),
after vsync (must match the reference), and the new back buffer after auto-erase (must be all
holes). Frame-to-frame differences are compared too.

### Depth scenes (`depth_check.py`)

Twelve views in the depth mode, authored as faces in world space: `interpenetrate` (two boxes
through each other, a large triangle through both and the floor, two crossed quads),
`platform` (a single 80 × 80-unit floor face with a platform, boxes and a pillar on it: the case
an ordering table gets wrong), the same farthest first (`platform_far_first`) and with a far
limit (`platform_far_limit`, `GPU_ZCLEAR` 0x7400: nothing past 25.6 units), `decals` (posters on
a wall and markings on a grazing floor with offsets 0, 2 and 8, drawn before and after their
surface), `glass` (three translucent panes in three blend modes, one textured, over opaque
boxes, and an opaque box drawn after them), `corridor` (a grazing textured floor and walls 60
units long), `corridor_test_off` (the same back to front with `GPU_DEPTH` off: perspective
alone), `near_clip` (a box, a wall and a triangle through the near plane), `planes` (the plane
chip on: polygons with depth in both layers, intersecting, a blended pane over holes and an
upper one over lower pixels, a translucent water plane between the layers) and
`overload_near_first` / `overload_far_first` (14 textured layers: 1,259,289 cycles nearest first,
2,227,054 farthest first). Every view ends with an interface drawn untested with plain packets.

The script does the geometry itself (camera, near clipping at 0.5 with the clipped vertices at
*w* = 0.5, projection, the depth word, back-face culling, the order), so the packets are its
own; what it checks is the GPU. Each view is compared twice:

1. **GPU only**: `depth_probe.c` makes the view's register writes through Mei's bus and
   returns the framebuffer, the depth buffer, the displayed picture and the GPU's counters.
2. **End to end**: a cart (`depth.mei`) holds every view's register writes and packet lists,
   relocates the lists into RAM at start-up and plays one view a frame in `mei-headless`. Each
   presented picture and its `--gpu-stats` row (cycles and the six depth counters) must match a
   reference GPU that keeps its state across frames, and each frame must take the ticks the
   2,000,000-cycle budget gives it: `overload_far_first` takes 2, the others 1.

It also checks that the order changes the cost and not the picture: nearest first is cheaper
on the platform and fits the budget in the overload, where both orders give the same picture
(the platform's two orders differ in 2 pixels, ties where faces touch). `--motion N` (48 in
`make rendercheck-motion`) adds frames of a camera moving over the platform, every fourth
without `GPU_ZCLEAR`, so the depth buffer carries over from the frame before; drawing those
frames over a cleared buffer instead must change the picture (16,256 pixels over the 48).

### Depth fuzzing (`depth_fuzz.py`)

32 frames of 36 packets each: every kind with depth (`0x30`–`0x3F`) twice and four without,
in random order, in two lists with `GPU_DEPTH` switched between them (on, off, or changed for
the second list), after `GPU_ZCLEAR` with 0, 0xFFFF or a random far limit, both dither
settings, and reserved `GPU_DEPTH` bits set. View depths come in six styles: one *w* for all
vertices (the affine case), steep perspective (1/8 to 64 units), clamped (1/16 or nearer, zero,
negative, −2³¹), far (keys of 0, the largest *w*), reciprocals that differ but scale to equal q,
and anything in range. A third of the packets have a decal offset (1, 2, 8 or 31); positions
are on screen, overlapping in one block, off it, collinear and across the full signed 16-bit
range; half the textured packets have a texture window. Framebuffer, depth buffer and all eight
counters must agree. Each packet with depth is then replayed alone (1,024 more frames), over a
cleared buffer or over a far limit taken from the finished frame: 162,201,600 pixel comparisons.

Four negative controls run the reference with one rule changed against the first eight frames,
and must disagree with Mei: ties to the earlier packet (10,871 pixels), semi-transparent packets
writing the depth buffer (396,833), a divide every 8 pixels (17,310), and failing pixels charged
in full (the cycle count differs in 7 of the 8 frames).

## Reading a failure

Every check prints one JSON line per case and writes `report.json` in its folder under
`$(B)/reference_renderer/` (`scene/`, `subdivision/`, `fuzz/`, `planes/`, `planes_feedback/`,
`motion/`, `textures/`, `plane_motion/`, `depth/`, `depth_motion/`, `depth_fuzz/`).
`different_pixels` is the count that must be zero; `max_channel_error` and `bbox` say how far
off and where. The depth checks count `framebuffer`, `depth_buffer` and `display` pixels apart
and list each counter that differs as `[reference, Mei]` under `stats`. Beside each report:

- `NAME_oracle.png` (or `_reference.png`), `NAME_mei.png` and `NAME_diff.png` (differing pixels
  in pink), and a labelled side-by-side `NAME_comparison.png`, scaled with nearest-neighbour
  sampling only;
- for the stress scene, `NAME_gpu.png` (the GPU-only replay), the replay fixture
  `NAME.packets` and Mei's GPU statistics; for the fuzzer, each failing scene's packets as JSON
  and as a probe fixture, which `gpu_probe` replays on its own (`gpu_probe FIXTURE OUT.rgb555`);
- for the depth checks, each view's or failing frame's `depth_probe` fixture (`NAME.bin`,
  replayed with `depth_probe FIXTURE OUT`), `NAME_gpu.png` and `NAME_depth.png` (the reference's
  depth buffer, its keys' high bytes as grey: nearer is lighter);
- for the checks over time, contact sheets and animated GIF or WebP previews of reference, Mei
  and difference (the previews' colours are quantized: the PNGs and JSON are the evidence).

To decide who is wrong: a mismatch in the end-to-end image but not the GPU-only one is the
standard library's geometry (or the reference's model of it); one in both is the GPU or the
reference's pixel rules; a mismatch in a single fuzzed packet names the packet kind. Then check
the rule in DECISIONS.md, LANGUAGE.md, PLANES.md or RENDERING.md: if the reference departs from
the documented rule, fix the reference; if Mei does, it is a console or standard library
defect. The two defects below were found this way; so was one reference error (the `mat4_mul`
rounding above, which disagreed on two motion steps until the reference followed the documented
operator).

## What it found

Two standard library bugs, both fixed with regression tests in `tests/lang/`:

- **Subdivision darkened colours.** `__sub_mid` in `stdlib/subdiv.akr` cleared each endpoint
  colour's low bit before averaging, computing `floor(a/2) + floor(b/2)` per channel instead of
  `floor((a + b)/2)`: whenever both endpoints were odd, the midpoint was one darker, so a
  constant colour could turn into bands just by calling `subdivide()`. The nine original views
  could not see it, because they leave subdivision off; `geometry_check.py` was written for it.
  The fix averages with `clerp` at exactly 0.5, as the texture coordinates already did. Before
  the fix (pixels wrong, out of 76,800):

  | Case | Level 0 | Level 1 | Level 2 | Level 3 |
  |---|---:|---:|---:|---:|
  | Flat tint | 0 | 2,048 | 6,048 | 11,656 |
  | Gouraud tint | 0 | 27,409 | 27,409 | 27,417 |
  | Gradient | 0 | 5,094 | 5,524 | 8,966 |

  `tests/lang/subdiv_colour.akr` calls the midpoint helper itself and checks byte averages for
  identical odd values, mixed parity, 255, opposing gradients and reversed endpoints, which
  catches an error RGB555 quantization might hide in a picture. In the carts, Sun & Moon Orbs
  (which subdivides) draws some subdivided pixels one 5-bit step brighter with the fix.

- **Mirrored sprites at the atlas edge.** `sprite_ex` clamped `u + tw` and `v + th` at 255, but
  not the first texel of a mirrored axis: `u = 240, tw = -47` gave u = 286, which wrapped to 30
  in the packet's 8-bit field and carried a bit into v; a vertical overflow could carry into
  the texture page and sample another slot. The fix clamps it at 255. Before the fix,
  `texture_check.py` found 1,281,495 wrong pixels over the 96 normal frames and 300,567 over the
  22 overloaded ones. `tests/lang/sprite_mirror_edge.akr` samples horizontal, vertical and
  both-axis mirrors at the atlas edge (all three failed before the fix) and an ordinary mirror.
  No cart mirrors a sprite, so none draws differently.

Sensitivity was also shown on purpose, on 2026-10-02, with emulator builds that were changed
for the experiment only: moving the first dither offset from −4 to +4 made 990 pixels of the
overview differ, and letting BG0 win priority ties against the polygon layers made 39,016
pixels of plane case 0 differ.

## Results

On 2026-10-03 (the depth checks on 2026-10-04), against this tree, every check passes with no
differing pixel:

| Check | Compared | Result |
|---|---|---|
| Stress scene | 9 views × 2 paths, 1,382,400 pixels; packet triangle counts equal Mei's | 0 different; no triangle dropped; 157,737–571,815 GPU cycles per frame |
| Subdivision | 12 views | 0 different |
| GPU fuzzing | 64 scenes, 1,024 packets (250 with a window), each also alone: 83,558,400 pixels | 0 different |
| Plane compositor | 64 cases, framebuffer and display: 9,830,400 pixels | 0 different |
| Feedback diagnostic | case 33 aliased | static reference 51 framebuffer pixels off (expected), pixel-live 0 |
| Motion | 128 frames, 127 deltas, 90 frames with near clipping, 4–7 wall pieces, 16 held ticks | 0 different |
| Animated textures | 96 normal frames; 22 overloaded frames over 64 ticks (42 waiting for the GPU) | 0 different, 0 mapping or held-frame errors |
| Plane motion | 24 frames × 3 buffers: 5,529,600 pixels | 0 different, early-latch, auto-erase or delta errors |
| Depth scenes | 12 views: framebuffer, depth buffer, display and 8 counters GPU only; picture, counters and ticks end to end | 0 different; 150,365–2,227,054 GPU cycles a frame, `overload_far_first` 2 ticks |
| Depth motion | 48 frames end to end, 12 without `GPU_ZCLEAR` | 0 different; 179,561–295,193 GPU cycles a frame |
| Depth fuzzing | 32 frames of 36 packets, 1,024 packets with depth also alone: 162,201,600 pixels and every counter | 0 different |

The negative controls fire: a stale frame would show 1,805,872 wrong pixels across the motion
run; the stale texture and late palette at texture frame 8 give 17,991 and 16,713; and a
reference that ignores texture windows disagrees with Mei in the 32 fuzzed scenes that use them.
The depth fuzzer's four mutant references disagree with Mei (above), and the motion frames drawn
over a cleared depth buffer differ from the carried-over ones in 16,256 pixels.

The depth model agrees with RENDERING.md's golden values, and Mei with the spec everywhere the
checks looked. The spec's cost table leaves two things to inference, which the reference and
Mei read the same way: the 24-cycle reciprocal setup is charged for a triangle with no pixels
too (zero-area and off-screen, as the 40-cycle setup is), and a perspective triangle's divides
are charged for every span whatever its pixels' depth test results.

## Limits

These are sampled, targeted regressions, not a proof over every input. The subdivision check
exhausts its wall's split pattern, not every triangle worklist topology or clipping
configuration. The stress scene's near-plane cases are a handful of faces and cameras; the known
near-plane fault (a face crossing the near plane dropped from some camera positions,
[WORLDCHECKER.md](../../docs/WORLDCHECKER.md)) does not occur in them, nor in the motion check.
An exploratory sweep on 2026-10-03 (not part of the suite: a grid of ground tiles under 7,900
random low cameras, judged by `oracle.py`) matched exactly with 2-unit tiles but found 5 views
with 8- and 16-unit tiles where Mei drops a ground tile under the camera that the reference
draws, double-sided or not, textured or not. Not covered: custom depth
keys and bias, the plane compositor driven through the standard library's plane functions
(`tests/test_planes.c` covers much of that), and the SDL and web presentation paths.

The depth checks test the GPU, not the standard library: `depth_check.py` makes its own packets
(its geometry is its own, not a model of `mesh()`), and its cart plays them from data. The
standard library's depth API (`stdlib/depth.akr`) is not built yet; when it is, the views can be
drawn with `mesh*()` under `render_depth(true)` and `render_perspective(true)`, with
`oracle.py`'s geometry extended to the new face loops and order. The triangle limit and lists
that fault are not in the depth fuzzer (the old fuzzer and `tests/test_gpu.c` cover them).
