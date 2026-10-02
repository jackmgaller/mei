# The plane chip

**Status: proposal for review.** Nothing in this chapter is implemented. It adds a second video
chip beside the polygon GPU, and it assumes the polygon GPU gets a cycle budget (setup per
triangle plus cost per pixel, run in parallel with the CPU). That budget is specified in a
separate chapter. The numbers below use the candidate cost table in `tools/mei_gpustats.py`.

Mei becomes "PlayStation polygons plus SNES-heritage planes", the way the Saturn paired VDP1
(sprites and polygons into a framebuffer) with VDP2 (scrolling and rotating backgrounds). The
**plane chip** draws three tiled background planes and a per-line backdrop colour. At scan-out it
composites them with the polygon framebuffer in a priority order. The planes cost no CPU cycles
and no GPU budget, only the VRAM that holds their tiles, maps and line tables.

## Why

`mei-headless --gpu-stats` on the example carts shows where fill goes (screens of pixels per
frame, mean over each run; the "model" column is the candidate GPU cost in thousands of cycles:
40 per triangle, 1 per pixel, ×2 textured, ×2 blended, 0.5 per cleared pixel):

| Run | Fill | Blended | Of which a plane could take | Model |
|---|---|---|---|---|
| Lantern Lake, dusk | 3.54 | 1.26 | sky (1.00, Gouraud), water (0.63, blended textured) | 677k |
| Lantern Lake, night moon | 3.40 | 1.42 | the same | 682k |
| Check-In!, day to dusk | 4.14 | 1.04 | the clear (1.00), the haze over the floors below (1.00, blended) | 581k |
| System boot | 3.41 | 0.72 | the Gouraud backdrops (1.41) | 328k |
| Sun & Moon Orbs | 3.45 | 0.53 | the sky (1.00, Gouraud) | 518k |

A third to a half of each frame's fill is a screen-sized layer that is flat, a gradient, or a
textured plane seen in perspective. That is what the SNES and Saturn drew with background
hardware and not with sprites or polygons.

## Precedent

- **SNES PPU.** Up to four tiled BG layers (8×8 or 16×16 tiles, 2/4/8 bits per pixel, 32×32 to
  64×64 maps), each map entry a 16-bit word with tile number, palette, priority bit and flips.
  **Mode 7**: one 128×128 map of 8×8 tiles transformed by a 2×2 matrix, with a choice of what lies
  outside the map (wrap, transparent, tile 0). **HDMA**: eight channels that rewrite PPU
  registers on every scanline from tables. That gives perspective floors (F-Zero, Mario Kart),
  sky gradients and wavy water. **Colour math**: add, subtract, half.
- **Saturn VDP2.** Four normal scroll screens (NBG0–3) and two rotation screens (RBG0–1) whose
  rotation parameters and coefficient tables can change per line, for perspective floors.
  Line-scroll tables. A **back screen** whose colour can be set per line. **Colour calculation**
  between the top two layers. **Colour offset** per layer. The VDP1 framebuffer is one more layer
  ("sprite"), and its pixels carry priority bits, so polygons can sit between backgrounds. VDP1
  also **erases** its framebuffer automatically during display.

Mei takes a small, regular subset: three planes, one of them affine, eight HDMA-style line
channels, a per-line backdrop, the GPU's four blend modes as colour math, one colour offset, and a
priority bit on framebuffer pixels.

## Layers

From back to front at the default (all-zero) priorities:

| Layer | What it is | Opaque where |
|---|---|---|
| **BD** backdrop | one colour per line | always (it is the bottom) |
| **BG2** | affine plane: one map transformed per line (Mode 7) | the texel's palette index ≠ 0 |
| **BG1** | tile plane | the texel's palette index ≠ 0 |
| **BG0** | tile plane | the texel's palette index ≠ 0 |
| **PL** low polygons | framebuffer pixels with bit 15 clear | pixel ≠ hole |
| **PH** high polygons | framebuffer pixels with bit 15 set | pixel ≠ hole |

Each of BG0, BG1, BG2, PL and PH has a 4-bit priority (BG0–BG2 have two: one for normal tiles and
one for tiles with the priority bit). Any order is possible, so polygons can be split around a
plane: reflections under the water plane, the shore above it.

## Tile planes (BG0, BG1)

**Tiles come from an atlas, laid out like a texture.** A plane's tile set is a 256×256 image in
VRAM in exactly the texture format (spec p. 11). A 4-bit image fills one 32 KB **page** and an
8-bit image fills two. Tile *t* is a cell of that image:

| Tile size | Cells | Tile *t* is the cell at | Tiles |
|---|---|---|---|
| 8×8 | 32 × 32 | column *t* mod 32, row *t* div 32 | 1,024 |
| 16×16 | 16 × 16 | column *t* mod 16, row (*t* div 16) mod 16 | 256 (bits 8–9 of *t* ignored) |

Because the format is the texture format, **a texture slot is also a tile set**: the same art can
be drawn as polygons and as planes. A page is any 32 KB-aligned block of VRAM. Pages 16–31 are
texture slots 0–15, and pages 10–15 are the free VRAM above the palette (see [Memory
map](#memory-map)). Texel (u, v) of a 4-bit atlas is the low nibble (even u) or high nibble
(odd u) of byte `page + v × 128 + u ÷ 2`. For an 8-bit atlas it is byte `page + v × 256 + u`.
Addresses wrap within VRAM.

**Colour.** 4-bit or 8-bit indexed, from the existing palette memory. Index 0 is transparent.
The colour is the palette entry's low 15 bits:

- 4-bit: colour `((PAL + p) mod 256) × 16 + index`, one of the 256 sixteen-colour palettes;
- 8-bit: colour `((PAL + p) mod 16) × 256 + index`, one of the 16 256-colour palettes;

where PAL is the plane's palette base (`MODE` bits 8–15) and p the map entry's palette (0–7).
Planes and polygons share the 4,096 colours. A palette change, such as Lantern Lake's
time-of-day blend or its rotating water shimmer, shows on both.

**Map.** A row-major array of 16-bit entries, W × H tiles, where W and H are each 32, 64 or 128.
Entry (mx, my) is at `MAP + (my × W + mx) × 2`. The entry is the SNES BG map entry, bit for bit:

| Bits | Field |
|---|---|
| 0–9 | tile number *t* |
| 10–12 | palette p (0–7), added to the plane's palette base |
| 13 | priority: the tile uses the plane's high priority (`PLN_PRIO`) |
| 14 | flip horizontally |
| 15 | flip vertically |

Map sizes: 32×32 is 2 KB, 64×64 is 8 KB, and 128×128 is 32 KB. With 16×16 tiles a 128×128 map is
2,048 pixels square.

**Scroll and wrap.** `SCROLL` holds x (bits 0–15) and y (bits 16–31) in whole pixels. Screen
pixel (x, y) shows plane pixel `((x + SX) mod Wpx, (y + SY) mod Hpx)`, where Wpx = W × tile size
and Hpx = H × tile size. Tile planes always wrap. There is no sub-pixel scrolling (the SNES had
none).

**Window.** Each plane is shown only inside a rectangle given as insets from the screen edges
(`WINX`: left bits 0–8, right bits 16–24; `WINY`: top bits 0–7, bottom bits 8–15). The reset
value 0 means the whole screen. Outside the window the plane is transparent. Changing `WINX` per
line through a line channel gives shaped windows (an iris wipe, a spotlight), as HDMA windows did.

## The affine plane (BG2)

BG2 has the same tiles, map entries, colour, priorities and window as the tile planes. Instead of
a scroll it has a transform from screen pixels to plane pixels (texels):

```
u(x, y) = U0 + y·DUY + x·DUX
v(x, y) = V0 + y·DVY + x·DVX
```

The six parameters are **16.16 fixed point**, the CPU's `fixed`, in texels and texels per
pixel. The sums are taken exactly in 64 bits, and the texel is `(floor(u), floor(v))`
(arithmetic shift right by 16). Screen pixel centres are at integer (x, y), as in the rasterizer.
Then:

- the map entry is the one under texel (tu, tv), and the texel within the tile is (tu, tv) mod
  the tile size, flipped as the entry says;
- nearest texel, no filtering. Shimmer at the horizon is part of the look, as on the SNES.

With DUX = DVY = 1.0 and the rest 0 except U0 and V0, BG2 is a third ordinary scrolling plane.

**Outside the map** (`MODE` bits 16–17), when tu or tv falls outside 0 … Wpx − 1:

| Value | Behaviour | Use |
|---|---|---|
| 0 | wrap (both coordinates mod the map size) | endless water, endless floor |
| 1 | transparent | an island, a track, a level that ends |
| 2 | tile 0: as if the entry were `0x0000`, sampled at (tu mod size, tv mod size) | a bounded map in an endless sea, as in Mode 7 |
| 3 | as 1 | |

**Perspective.** A plane seen in perspective is not affine as a whole, but for a camera without
roll every screen row cuts the floor along a straight line at constant depth, so it is affine
along each row. A line channel ([below](#line-channels)) writes U0, V0, DUX and DVX for every
line, and the cart sets DUY = DVY = 0. That is the Mode 7 floor.

### Worked example: a floor at a given height and horizon

Camera at C = (Cx, Cy, Cz), yaw θ (0 looks along +z, as in `camera()`), pitch φ, no roll. The
floor is the plane y = y0, and h = Cy − y0 > 0. The focal length is F pixels (the standard
library's default 60° field of view gives F = 120 × 1.732 = 207.8 for both axes), and the screen
centre is (cx, cy) = (160, 120). S is the number of texels per world unit, and (Uoff, Voff) is
the texel where world (0, 0) lies. For screen row y:

```
sy  = (y − cy) / F
den = sy·cos φ − sin φ                 rows with den ≤ 0 are at or above the horizon: no floor
t   = h / den                          the view depth of the row
k   = t / F                            world units per screen pixel along the row
d   = t·(cos φ + sy·sin φ)             ground distance ahead of the camera
DUX = S·k·cos θ                        DVX = −S·k·sin θ
U0  = S·(Cx + d·sin θ − cx·k·cos θ) + Uoff
V0  = S·(Cz + d·cos θ + cx·k·sin θ) + Voff
```

The horizon is the row y_h = cy + F·tan φ. With φ = 0 the formula is the classic Mode 7 one,
t = h·F / (y − y_h).

Numbers for Lantern Lake's fishing view: eye height h = 2.2 above the water, pitch φ = −0.14,
θ = 0, C = (20, 2.2, 10), and S = 8 texels per unit (the water texture's existing scale). The
horizon is at y_h = 90.7. Keeping depths up to 64 units sets the plane's top inset to 98:

| Row y | Depth t | U0 | V0 | DUX | U0 (16.16) | V0 (16.16) | DUX (16.16) |
|---|---|---|---|---|---|---|---|
| 98 | 63.4 | −230.44 | 589.62 | 2.4403 | `0xFF198E69` | `0x024D9E71` | `0x000270B5` |
| 100 | 49.7 | −146.33 | 479.30 | 1.9146 | `0xFF6DABD9` | `0x01DF4B8F` | `0x0001EA20` |
| 120 | 15.8 | 62.89 | 204.89 | 0.6070 | `0x003EE2FF` | `0x00CCE452` | `0x00009B61` |
| 160 | 6.66 | 118.95 | 131.36 | 0.2565 | `0x0076F42F` | `0x00835AED` | `0x000041AC` |
| 239 | 3.11 | 140.82 | 102.67 | 0.1199 | `0x008CD25C` | `0x0066AC75` | `0x00001EAF` |

(DVX = 0 for θ = 0.) At the far edge one screen pixel steps 2.4 texels, so the water shimmers
toward the horizon, as Mode 7 does.

**CPU cost.** The standard library derives the same values from the view-projection matrix
(`__vp`): the floor's screen mapping is a 3×3 homography, its inverse is computed once (about
200 cycles), and then each row needs one `fdiv` for the reciprocal depth and four `fmul`s. That
is about **55 cycles a line**, or 8,000 cycles (1.6% of the frame) for Lantern Lake's 142 water
lines, and only on frames when the camera moves. Working from the matrix also covers
`camera_matrix()` users, such as Check-In!'s panned off-axis view, exactly. A camera with roll is
approximated: the helper takes each row's ends exactly and is linear between them.

## Line channels

Eight channels, like the SNES's HDMA, rewrite plane registers for each screen line from tables in
VRAM.

| Register | Bits | Field |
|---|---|---|
| `LCn_ADDR` | 2–19 | VRAM offset of the table (word-aligned; other bits ignored, read back as written) |
| `LCn_CTRL` | 0–7 | target: offset of the first register written, from `0xFF0700` (bits 0–1 ignored) |
| | 8–9 | words per line − 1 (1–4 consecutive registers) |
| | 15 | enable |

A table holds 240 lines × n words: line y's words are at `ADDR + (y × n + k) × 4`, little-endian.
Tables live in VRAM only, so the plane chip reads nothing but VRAM, as VDP2 did.

**Composing line y** starts from the register values the CPU last wrote. Channels 0–7 are applied
in order, so a later channel wins a conflict, and each writes its n words into consecutive
registers from its target. The result is used for that line only: the next line starts again
from the CPU's values. CPU reads always return what the CPU wrote. Valid targets are the plane
registers `0xFF0704`–`0xFF078C` (everything except `PLN_CTRL` and the line channels themselves).
A word that would land on any other offset, or on a reserved one, is dropped. A write to
`PLN_ERASE` changes nothing, because erasing is not part of composing a line. The plane chip
never faults.

What a cart typically drives per line:

| Effect | Target | Words |
|---|---|---|
| Sky gradient, horizon glow | `BD_COLOR` | 1 |
| Parallax bands, wavy water, heat haze | `BGn_SCROLL` | 1 |
| Mode 7 floor or water | `BG2_U0` (U0, V0, DUX, DVX) | 4 |
| Fog or fade toward the horizon | `PLN_OFS` | 1 |
| Split screen, a band with a plane switched off | `PLN_LAYERS` | 1 |
| Iris wipe, spotlight | `BGn_WINX` | 1 |
| Palette per band | `BGn_MODE` | 1 |

**Latching.** The picture is composed **at the vsync that presents it**, from the registers, line
tables, maps, tiles and palettes as they stand at that instant, together with the polygon frame
that the same vsync swaps to the front. Everything a cart writes during a frame therefore appears
together, and a cart may rewrite tables and maps at any point in the frame without tearing. A real
chip would fetch during the next frame's scan-out. Composing at vsync is a deliberate
idealisation, like the GPU drawing instantly.

## Backdrop, colour math and colour offset

**Backdrop.** `BD_COLOR` is 8 bits per channel in the GPU's colour-word format (`0xBBGGRR`, bits
24–31 ignored). It is reduced to the 15-bit output per pixel. When `PLN_CTRL` bit 2 is set it is
dithered with the GPU's 4×4 matrix and rule, `clamp255(c + m[y mod 4][x mod 4]) >> 3`. Otherwise
it is `c >> 3`. A line channel on `BD_COLOR` gives a smooth sky gradient at no fill cost.

**Colour math.** Each of BG0, BG1, BG2, PL and PH can be marked translucent. Where its pixel ends
up on top, the pixel is blended with the next opaque pixel below it, which is another layer or
the backdrop. The modes are the GPU's four blend modes on 5-bit channels, with "polygon" as the
top layer A and "background" as the layer below B:

| Mode | Result | Use |
|---|---|---|
| 0 | (B + A) >> 1 | water, glass, a ghosted layer |
| 1 | min(31, B + A) | glow layers, light shafts |
| 2 | max(0, B − A) | cloud shadows, darkening |
| 3 | min(31, B + (A >> 2)) | faint haze |

Only the top two layers take part, as on the Saturn. Three translucent layers stacked do not
blend three ways.

**Colour offset.** `PLN_OFS` holds a signed offset per 5-bit channel (red bits 0–7, green 8–15,
blue 16–23, each −128…127). It is added to the final pixel, clamped to 0–31, when the layer that
won the pixel has its offset bit set in `PLN_MATH`. The backdrop has its own bit. This is the
Saturn colour offset and the SNES fixed-colour add/subtract: fades, flashes, a dusk or underwater
tint, or a haze over one polygon group, at no fill cost.

**Left out:** ratio blends (the Saturn's 32 levels), three-way blending, two independent offsets,
shadow and highlight, mosaic, window logic (AND/OR of windows, sprite windows), line colour
screens, bitmap (direct-colour) planes, and per-pixel blending of semi-transparent polygons with
the planes (see below).

## The polygon layer and compositing

### The priority bit and holes

Today bit 15 of a framebuffer pixel is unused, and the GPU always writes it clear. With the
compositor on (`PLN_CTRL` bit 0), bit 15 becomes the polygon **priority bit**, as on the
PlayStation (its mask bit) and the Saturn (sprite priority bits in the framebuffer data):

- **Packets choose the layer.** Bit 26 of a polygon packet's first colour word, the bit after
  the blend mode, is **upper**. Every pixel the packet writes, blended or not, gets bit 15 =
  upper. The GPU reads only bits 0–14 of the background when blending. A blended pixel takes the
  layer of the packet that drew it.
- **Holes.** A framebuffer pixel equal to exactly `0x8000` is a **hole**: no polygon is there,
  and the layers behind show through. The GPU never writes `0x8000`. An upper pixel whose colour
  comes out as pure black is written as `0x8400` instead (blue 1 of 31, indistinguishable from
  black on output).
- **`GPU_CLEAR`** writes all 16 bits of its value, so `GPU_CLEAR = 0x8000` makes the whole back
  buffer holes.
- **Auto-erase** (`PLN_CTRL` bit 1): at each vsync, after composing, the new back buffer is
  filled with `PLN_ERASE` (16 bits; normally `0x8000`), as VDP1 erased its framebuffer during
  display. It costs neither CPU cycles nor GPU budget, so a cart using planes needs no
  `GPU_CLEAR`.

With the compositor off, the GPU ignores bit 26, writes bit 15 clear and `GPU_CLEAR` writes bits
0–14, exactly as today.

**Blending polygons over holes.** A semi-transparent polygon blends with the framebuffer only. On
a hole it blends with the hole's colour, black, not with the plane that will show there. This is
the Saturn's well-known VDP1 transparency gap, and it is kept. A cart that needs a translucent
layer over a plane uses plane colour math, or draws the blended polygons over opaque polygon
pixels.

### Order

At each pixel the candidates are the five layers that are enabled, inside their windows and
opaque there. At most one of PL and PH is present, since a pixel is one or the other. The
candidate with the highest priority is on top. Ties go to the fixed order **PH, PL, BG0, BG1,
BG2** (front to back). The backdrop is always behind everything. With every priority at its reset
value 0, the stack is backdrop, BG2, BG1, BG0, polygons, which is the right stack for most games.
A HUD plane in front of the polygons needs only a higher BG0 priority.

### Algorithm (normative)

```
at vsync, after the buffers swap (front = the frame just drawn):
  for y in 0..239:
    W = the CPU's register values, then line channels 0..7 applied for line y
    for x in 0..319:
      cands = []
      if !(W.LAYERS & 8):                                  // polygon layer shown
        f = front[y][x]
        if f != 0x8000: cands += (f & 0x8000 ? PH : PL, prio, f & 0x7FFF)
      for n in 0, 1, 2:
        if W.LAYERS bit n and (x, y) inside BGn's window:
          c = sample(n, x, y)                              // transparent if index 0
          if c: cands += (BGn, entry bit 13 ? hi : lo prio, c)
      A = best of cands by (priority, tie order); B = next best, else backdrop(x, y)
      out = A ? A.colour : backdrop(x, y)
      if A and W.MATH has A's blend bit: out = blend(B, A, mode)
      if offset bit of (A ? A.layer : BD): out = clamp31 per channel (out + OFS)
      composite[y][x] = out                                // 15-bit, bit 15 clear
  if PLN_CTRL bit 1: fill the new back buffer with PLN_ERASE
```

**Output.** The composite is 15-bit, like a framebuffer pixel. Polygon pixels were already
dithered by the GPU if `GPU_CTRL` bit 0 was set. Plane pixels are palette colours and are not
dithered (textures are not dithered either, except through tinting). The backdrop is dithered
from 8 bits if `PLN_CTRL` bit 2 is set. Colour math and the offset work on 5-bit channels and add
no dither.

## Memory map

### VRAM

The plane chip has no memory of its own. Everything is in the existing 1 MB of VRAM, and only the
two spare regions are newly used, which no cart or the system ROM touches today:

| Address | Contents | Size | |
|---|---|---|---|
| `0x400000`–`0x44AFFF` | framebuffers A and B | 300 KB | unchanged |
| `0x44B000`–`0x44BFFF` | spare | 4 KB | free; extra line tables if wanted |
| `0x44C000`–`0x44DFFF` | palette memory, shared by planes and polygons | 8 KB | unchanged |
| `0x44E000`–`0x44FFFF` | **line tables** (convention) | 8 KB | was spare |
| `0x450000`–`0x47FFFF` | **plane pages 10–15**: maps and tile atlases (convention) | 192 KB | was spare |
| `0x480000`–`0x4FFFFF` | texture slots 0–15 = pages 16–31, also usable as atlases | 512 KB | unchanged |

The hardware enforces none of this, since every address is a register, but the standard library
uses this layout:

| Address | Use | Size |
|---|---|---|
| `0x44E000` | backdrop table (1 word per line) | 960 B |
| `0x44E400` | BG0 scroll table | 960 B |
| `0x44E800` | BG1 scroll table | 960 B |
| `0x44EC00` | free (an offset or window table) | 1 KB |
| `0x44F000` | BG2 affine table (4 words per line) | 3,840 B |
| `0x450000` | BG0 map (up to 64×64) | 8 KB |
| `0x452000` | BG1 map (up to 64×64) | 8 KB |
| `0x454000` | free (a 64×64 BG2 map, or a second map to flip between) | 16 KB |
| `0x458000` | BG2 map (up to 128×128) | 32 KB |
| `0x460000`–`0x47FFFF` | pages 12–15: four 4-bit atlases or two 8-bit ones | 128 KB |

Every existing texture slot keeps its address and contents, so nothing moves for existing carts.
A cart that needs more than four plane atlases points planes at texture slots.

### I/O registers (`0xFF0700`)

The I/O region grows to `0xFF0000`–`0xFF07FF`, the same way the audio upgrade grew it
(`0xFF0600`–`0xFF06FF` is the broadcast decoder, docs/BROADCAST.md). All registers are 32-bit, read/write, keep and read back all 32 bits, and
reset to 0. Byte or halfword access is *Bad I/O width*. The reserved offsets listed, and
`0xFF0800` and up, are *Unmapped address*. These offsets faulted before, and no working cart can
depend on that.

| Address | Name | Bits |
|---|---|---|
| `0xFF0700` | `PLN_CTRL` | 0 compositor on · 1 auto-erase at vsync · 2 dither the backdrop |
| `0xFF0704` | `PLN_LAYERS` | 0 BG0 on · 1 BG1 on · 2 BG2 on · 3 polygon layer **hidden** (so reset shows it) |
| `0xFF0708` | `PLN_PRIO` | 4-bit priorities: 0–3 BG0 · 4–7 BG0 priority tiles · 8–11 BG1 · 12–15 BG1 priority tiles · 16–19 BG2 · 20–23 BG2 priority tiles · 24–27 PL · 28–31 PH |
| `0xFF070C` | `PLN_MATH` | colour math, 4 bits per layer (bits 0–1 mode, bit 2 on): 0–3 BG0 · 4–7 BG1 · 8–11 BG2 · 12–15 PL · 16–19 PH. Offset enables: 24 BG0 · 25 BG1 · 26 BG2 · 27 PL · 28 PH · 29 backdrop |
| `0xFF0710` | `PLN_OFS` | signed offsets in 5-bit units: 0–7 red · 8–15 green · 16–23 blue |
| `0xFF0714` | `BD_COLOR` | backdrop `0xBBGGRR` |
| `0xFF0718` | `PLN_ERASE` | bits 0–15: value written by auto-erase |
| `0xFF071C` | — | reserved |
| `0xFF0720` | `BG0_MODE` | 0–1 map width (0: 32, 1: 64, 2–3: 128) · 2–3 map height · 4 16×16 tiles · 5 8-bit colour · 8–15 palette base |
| `0xFF0724` | `BG0_TILES` | atlas page: bits 15–19 of the VRAM offset (e.g. `0x498000` = slot 3) |
| `0xFF0728` | `BG0_MAP` | map: bits 11–19 of the VRAM offset (2 KB-aligned) |
| `0xFF072C` | `BG0_SCROLL` | 0–15 x · 16–31 y, pixels |
| `0xFF0730` | `BG0_WINX` | 0–8 left inset · 16–24 right inset |
| `0xFF0734` | `BG0_WINY` | 0–7 top inset · 8–15 bottom inset |
| `0xFF0738`–`3C` | — | reserved |
| `0xFF0740`–`5C` | `BG1_*` | as BG0, at the same offsets |
| `0xFF0760` | `BG2_MODE` | as `BG0_MODE`, plus 16–17 outside the map (0 wrap, 1 transparent, 2 tile 0) |
| `0xFF0764` | `BG2_TILES` | as BG0 |
| `0xFF0768` | `BG2_MAP` | as BG0 |
| `0xFF076C` | — | reserved (BG2 has no scroll) |
| `0xFF0770` | `BG2_WINX` | as BG0 |
| `0xFF0774` | `BG2_WINY` | as BG0 |
| `0xFF0778` | `BG2_U0` | 16.16 |
| `0xFF077C` | `BG2_V0` | 16.16 |
| `0xFF0780` | `BG2_DUX` | 16.16 |
| `0xFF0784` | `BG2_DVX` | 16.16 |
| `0xFF0788` | `BG2_DUY` | 16.16 |
| `0xFF078C` | `BG2_DVY` | 16.16 |
| `0xFF0790`–`9C` | — | reserved |
| `0xFF07A0` + 8n | `LCn_ADDR` | line channel n = 0–7: table address |
| `0xFF07A4` + 8n | `LCn_CTRL` | target · words per line · enable |
| `0xFF07E0`–`FC` | — | reserved |

Unused bits are ignored and read back as written. Map sizes 2 and 3 both mean 128.

### GPU packet change

One bit is added to the polygon packet format (spec p. 15). Existing packets have it clear:

| Word | Bits | Field |
|---|---|---|
| Colour (first only) | 26 | Upper: the pixels drawn go to the PH layer (only while `PLN_CTRL` bit 0 is set) |

## Timing and costs

- **CPU: zero** for composing. A cart pays only for its own writes: registers (`sw`, 2 cycles),
  tables (a 240-word backdrop table is about 2,500 cycles to recompute, a Mode 7 floor about 55
  per line) and VRAM uploads (an 8 KB map is about 14,000 cycles, and a 32 KB atlas about 56,000,
  the same as loading a texture slot).
- **GPU budget: zero.** Planes, the backdrop, colour math, the colour offset and auto-erase draw
  no triangles and fill no pixels. They do not count against the triangle limit or any fill
  budget. `GPU_CLEAR` stays a GPU operation, costed as the GPU chapter decides.
- **Limits.** Three planes and the backdrop. One affine plane. Maps up to 128×128 entries (32 KB).
  Atlases of 1,024 8×8 or 256 16×16 tiles per plane. 4,096 palette colours shared with the
  polygons. Eight line channels of at most four words per line. One colour-math mode per layer and
  one colour offset. These, and VRAM, are the honest limits.
- **No per-line fetch limit.** A background chip fetches the same amount on every line: one map
  entry per tile and one texel per pixel for each enabled plane, whatever the picture. So,
  unlike sprites, there is no content-dependent overflow to model. The Saturn's VRAM
  access-cycle rules, which limit which layer and depth combinations can be enabled together,
  are left out.

### Polygon GPU and planes together

The two units divide the picture by kind, not by area. The **plane chip** takes whatever is
screen-sized and flat: skies and gradients, far backdrops and parallax, floors, water and ground
seen at one angle, HUD frames and text panels. The **polygon GPU** takes whatever has depth relief
or must sort: characters, props, buildings, terrain that is not a plane, particles, and effects
that blend with polygons. The GPU runs in parallel with the CPU and a frame takes max(CPU, GPU).
The plane chip runs beside both and never lengthens a frame.

Effect on the candidate cost model, from the measured runs (thousands of model cycles per frame,
mean / max over the run; the CPU column is the measured mean):

| Run | CPU | GPU today | GPU with planes | Moved to planes |
|---|---|---|---|---|
| Lantern Lake, day pier | 229k | 593k / 639k | 292k / 334k | sky, water |
| Lantern Lake, dusk | 252k | 677k / 735k | 401k / 452k | sky, water |
| Lantern Lake, night moon | 252k | 682k / 728k | 388k / 432k | sky, water |
| Lantern Lake, festival ending | 249k | 484k / 667k | 279k / 534k | sky, water |
| Check-In!, day to dusk | 256k | 581k / 591k | 389k / 399k | clear, haze |
| System boot | 43k | 328k / 528k | 214k / 413k | one screen of backdrop, clear |
| Sun & Moon Orbs | 253k | 518k / 573k | 441k / 496k | sky |

(Lantern Lake's "with planes" assumes the 8 sky triangles and up to 160 water-fan triangles go
away, along with 76,800 Gouraud pixels and all blended textured Gouraud pixels, which in that cart
are the water fan. Check-In!'s figure counts only the haze and the clear. Moving its floors and
ground would save more; see example (b).)

Under the candidate model, the polygon-heavy carts' GPU work today is two to three times their
CPU work, so a GPU budget would bind before the CPU budget. With planes, Lantern Lake's GPU work
falls by 40–50%, to 1.3–1.6× its CPU time. If the budget were set at the CPU's 500,000 cycles, Lantern
Lake today would exceed it in every measured run. With planes, every run's mean fits, and only the
festival ending's fireworks peaks go over.

The budget level, the per-pixel costs and whether to keep a triangle-cap backstop are open
questions (below), to be settled after a Lantern Lake prototype.

## Determinism and emulation notes

- The compositor is a pure function of VRAM and the plane registers at vsync, plus the front
  buffer. It is integer-only, with no floating point and no host-dependent rounding (the 64-bit
  affine sums use an arithmetic shift).
- **Nothing the compositor produces is visible to the CPU.** The composite is a host-side
  320×240 buffer in the core, like `error_screen`, not in VRAM. The only VRAM writes are
  auto-erase and the GPU's bit 15, both deterministic. A bug in composing could make a wrong
  picture but could never change a cart's execution.
- **Implementation.** `planes.c`, called from `mei_run_frame` right after `gpu_vsync`: compose,
  then auto-erase. `mei_display` returns the composite when the compositor was on at the last
  vsync, otherwise the front buffer as today (and the error screen after a fault). After an
  overrun no vsync happens, so the previous composite repeats, as the previous frame does today.
  Reset clears the registers (VRAM is already cleared).
- **Speed.** At most four layer fetches per pixel. That is comparable to rasterising one or two
  screens of textured fill, and the emulator already does three to four per frame. Skipping
  disabled and windowed layers per line, and decoding a tile row at a time, keeps it cheap. The
  target is under 1 ms per frame natively, to be measured natively and in WebAssembly like the
  reverb.
- **Tools.** `mei-headless --dump` and `--dump-every` write `mei_display`, so dumps include the
  planes. `--gpu-stats` is unaffected: it counts polygon work only, and planes do none. A later
  column could record whether the compositor was on.
- **Tests.** Unit tests per rule: map entry decoding and flips, both tile sizes and depths, wrap
  and the three outside modes, the 64-bit affine sums, line channel order and dropped targets,
  priority ties, the four blend modes, offset clamping, the hole rules (`0x8000`, `0x8400`) and
  auto-erase. Plus the bit-identity check described under backward compatibility.

## Standard library sketch

A new `stdlib/planes.akr`. Names and shapes only; the syntax is Akari.

```
reg PLN_CTRL: u32 @ 0xFF0700
reg PLN_LAYERS: u32 @ 0xFF0704
reg PLN_PRIO: u32 @ 0xFF0708
reg PLN_MATH: u32 @ 0xFF070C
reg PLN_OFS: u32 @ 0xFF0710
reg BD_COLOR: u32 @ 0xFF0714
reg PLN_ERASE: u32 @ 0xFF0718

const BG0 = 0
const BG1 = 1
const BG2 = 2
const LAYER_PL = 3
const LAYER_PH = 4
const HOLE = 0x8000
const PAGE_PLANES = 0x450000      // pages 10-15
const LINE_TABLES = 0x44E000

// Setup
fn planes_on()                    // compositor + auto-erase to HOLE + dithered backdrop; UI list goes to PH
fn planes_off()
fn plane(bg: s32, atlas: u32, map: u32, w: s32, h: s32, flags: s32, palette: s32)   // PLANE_16PX, PLANE_8BIT, PLANE_TRANSPARENT_OUT...
fn plane_show(bg: s32, on: bool)
fn plane_priority(bg: s32, normal: s32, front_tiles: s32)
fn poly_priority(low: s32, high: s32)
fn poly_upper(on: bool)           // packets built from now on (mesh*, sprite*, ui_*) draw into PH
fn layer_blend(layer: s32, mode: s32)          // BLEND_NONE or 0-3, as for polygons
fn layer_offset(mask: s32, r: s32, g: s32, b: s32)
fn plane_window(bg: s32, x0: s32, y0: s32, x1: s32, y1: s32)

// Maps and tiles
fn tile(t: s32, palette: s32, flags: s32) -> u32        // TILE_FLIPX, TILE_FLIPY, TILE_FRONT
fn map_set(bg: s32, x: s32, y: s32, entry: u32)
fn map_fill(bg: s32, x: s32, y: s32, w: s32, h: s32, entry: u32)
fn map_load(bg: s32, src: *u16)                          // a whole map from ROM
fn map_column(bg: s32, x: s32, src: *u16)               // streaming a scrolling level
fn atlas_load(page: u32, src: *u8, bytes: u32)          // like load_texture, for pages 10-15
fn plane_scroll(bg: s32, x: s32, y: s32)
fn plane_affine(u0: fixed, v0: fixed, dux: fixed, dvx: fixed, duy: fixed, dvy: fixed)

// Line tables
fn line_channel(ch: s32, target: u32, words: s32, table: u32)
fn line_off(ch: s32)
fn sky_gradient(stops: *u32, ys: *s32, n: s32)          // backdrop: linear between n (line, colour) stops
fn parallax_bands(bg: s32, ys: *s32, rates: *fixed, n: s32, x: fixed)   // per-band scroll speeds
fn plane_floor(y0: fixed, texels: fixed, uoff: fixed, voff: fixed, far: fixed)
```

`plane_floor` is the Mode 7 helper. It reads the current view-projection matrix, so it works with
`camera()`, `camera_look()` and `camera_matrix()`. It fills the BG2 affine table for every row
with depth up to `far`, sets BG2's top inset to the first such row, sets DUY = DVY = 0 and points
channel 7 at the table. The per-row arithmetic is the [worked example](#worked-example-a-floor-at-a-given-height-and-horizon).
In terms of camera parameters:

```
fn plane_floor_cam(c: vec3, yaw: fixed, pitch: fixed, y0: fixed, s: fixed, far: fixed) {
    let F: fixed = 207.8
    let h = c.y - y0
    let sp = sin(pitch)
    let cp = cos(pitch)
    let st = sin(yaw)
    let ct = cos(yaw)
    var top = 240
    for y in 0..240 {
        let sy = fixed(y - 120) / F
        let den = sy * cp - sp
        let e = (0x44F000 + y * 16) as *fixed
        if den <= 0.0 || h / den > far { continue }      // above the horizon or too far
        if top == 240 { top = y }
        let t = h / den
        let k = t / F
        let d = t * (cp + sy * sp)
        e[0] = s * (c.x + d * st - 160 * k * ct)          // U0
        e[1] = s * (c.z + d * ct + 160 * k * st)          // V0
        e[2] = s * k * ct                                 // DUX
        e[3] = -s * k * st                                // DVX
    }
    plane_window(BG2, 0, top, 320, 240)
}
```

A Mode 7 floor costs **zero** GPU budget, where Lantern Lake's water fan costs about 200k model
cycles. It costs about 1–2% of the CPU budget on frames when the camera moves.

## Worked examples

### (a) Lantern Lake: sky and water on planes

Today the frame is pass A (the sky as four Gouraud quads, 1.00 screen, then the reflection),
pass B (the water fan, 80 blended textured quads, about 0.63 screen, then shadows and glows on
it), pass C (the world above the water) and pass D (rod and hand).

With planes:

| Piece | Becomes |
|---|---|
| Sky above the horizon and its darker mirror below | **backdrop**: channel 0 → `BD_COLOR`, the existing top / mid / horizon colours and their mirror at 200/256, dithered |
| Pass A: reflection, sun, moon, stars, clouds | **PL** polygons, unchanged |
| Water fan | **BG2**: atlas = texture slot 3 (`SLOT_WATER`, 4-bit, already loaded), palette base `PAL_WATER` (its shimmer rotation keeps working), a 32×32 map of 8×8 tiles that tiles the texture (entry *i*), wrap, 8 texels per unit; `plane_floor` each frame the camera moves; **colour math mode 0** (half), as the fan blends today |
| Shadows, lantern pools, glitter, ripples | **PL**, drawn after the reflection at double strength (the water then halves them) |
| Pass C, pass D, interface | **PH**: `poly_upper(true)` before pass C |

Priorities: PL 0, BG2 1, PH 2, and auto-erase to holes. The water half-blends with the
reflection, or with the backdrop's mirrored sky where no reflection was drawn, which is exactly
what the fan does today. The shore, docks and village cover it from above.

**VRAM:** backdrop table 960 B + affine table 3,840 B + map 2,048 B = **6,848 bytes**. The atlas
reuses slot 3.

**Saving per frame** (measured runs, model as above): fill falls from 3.28–3.54 to 1.42–1.92
screens, blended fill by 0.4–0.7 screen, and GPU model cost by 40–50% (dusk: 677k → 401k mean).
The CPU cost stays about the same: `plane_floor` (about 8,000 cycles when the camera moves)
replaces `fan_build` and the fan's `mesh()`.

**What changes in the look:** the fan's travelling vertex-colour waves become the palette shimmer
plus a per-line wobble of U0 (a sine added to the table, for free). The sky's left-to-right warm
tint toward a low sun cannot be a per-line colour. It can be dropped, or done as BG1: a wide 4-bit
glow strip scrolled with the yaw and added with mode 1. The gentle camera roll while fighting a
fish cannot tilt a per-line backdrop or a per-line floor exactly, so the port drops the roll, or
keeps a small one and accepts the approximation. Blended effects over the mirrored sky blend
with black (see holes) before the water halves them, which loses a little of the sky's colour
under them.

### (b) Check-In!: the floors as a plane, the haze as a colour offset

Check-In! clears the screen, draws the floors below (seen through atriums) at 5/8 brightness,
then adds a full-screen grey (`GHOST_ADD` in `render.akr`, a blended flat quad: 1.00 screen),
then draws the viewed floor on top.

| Piece | Becomes |
|---|---|
| The clear (1.00 screen) | auto-erase to holes; the backdrop holds the sky colour |
| Floors below | **PL** polygons, unchanged |
| The haze | **colour offset** (+9, +9, +9), with the offset bits for PL and the backdrop. `GHOST_ADD`'s channels (75, 76, 79) >> 3 are 9 each, the same as the GPU's undithered add. The haze loses its dither pattern |
| Floor surfaces of the viewed floor, and on the ground floor the road, sidewalk, grass, sand and sea around the lot | **BG2**: a 128×128 map of 16×16 tiles, one tile per world unit (S = 16, world −40…88), one entry per floor or ground cell. Atrium cells use a transparent tile, so the floors below show through. The palettes are the art palettes, so time-of-day relighting still works |
| Walls, objects, people, glows, interface | **PH** |

Priorities: PL 0, BG2 1, PH 2. The camera is near-orthographic but not exactly: the depth changes
by about ±3–5% from the top of the screen to the bottom, so a single matrix would be off by
several pixels at the screen edges. The floor therefore uses `plane_floor`, with
pitch −35°, yaw 45° + k·90°, F = ppu × 300 (e.g. 5,091 pixels at zoom 1) and the screen centre
moved by the pan, (160 + pan_x, 120 + pan_y). Working from the matrix, as the standard library
does, handles the pan exactly. Rotating 90° or zooming only recomputes the table. Editing a floor
rewrites the changed map entries. Panning recomputes the table (about 13,000 cycles).

Polygon vertices snap to whole pixels and the plane does not, so a wall's foot can sit up to one
pixel off the tile seam beneath it. That is era-correct. Drawing wall bases a pixel lower hides
it.

**VRAM:** map 32 KB (page 11) + affine table 3,840 B. The floor tiles need no more if the floor
art sits on the 16×16 grid of its texture slot, which is a change to `tools/gen_checkin_art.py`.
Otherwise they need one 32 KB page.

**Saving per frame:** the haze and the clear alone take the day-to-dusk run from 581k to 389k
model cycles (−33%). Floors and ground are not measured separately. Textured fill is 1.7–2.0
screens, and if floors and ground are 0.5–0.8 of the screen, they are a further 77k–123k. The
floors below are still filled by the GPU even where the floor plane covers them. Culling them to
the atrium cells would save more.

### (c) A 2D platformer in the SNES style

| Layer | Content | Setup |
|---|---|---|
| Backdrop | sky gradient | channel 0 → `BD_COLOR` |
| BG1 | far hills and clouds, 4-bit 8×8 tiles, 64×32 map | channel 1 → `BG1_SCROLL`: five bands (clouds 1/8, far hills 1/4, near hills 1/2 of the camera x) from one plane |
| BG2 | the level, 4-bit 16×16 tiles, 128×32 map (2,048 × 512 pixels, streamed by columns), as a plain scrolling plane (DUX = DVY = 1) | priority 1, and 5 for tiles with the priority bit (grass tufts and pillars in front of the player) |
| PL | player, enemies, items, particles: textured quads | priority 4 |
| BG0 | HUD: score, hearts, a frame. 4-bit 8×8 tiles, 32×32 map, no scroll, transparent except the top 24 lines | priority 15 |

The camera writes `BG2_U0`, `BG2_V0` and the band table each frame (about 1,500 cycles) and copies
one 32-entry map column when it crosses a tile (about 200 cycles).

**VRAM:** one 4-bit atlas page shared by all three planes (32 KB), maps 4 + 8 + 2 KB, two line
tables 1.9 KB: about **48 KB**. The sprites' textures stay in texture slots.

**GPU:** only the characters. Twenty 32×32 sprites are 40 triangles and 20,480 textured pixels,
about 43k model cycles. Drawing the same picture with polygons (three layers of textured
screen-sized fill plus a gradient) would be about 500k.

## Backward compatibility and the system ROM

- **Off by default.** At reset every plane register is 0: the compositor is off, `mei_display` is
  the front buffer, the GPU ignores colour bit 26 and writes bit 15 clear, `GPU_CLEAR` writes 15
  bits, and line channels do nothing. Existing carts are untouched: their packets have bit 26
  clear (the standard library sets only bits 24–25), none uses the spare VRAM regions, none reads
  bit 15 of the framebuffer, and none accesses `0xFF0700`–`0xFF07FF`, which faulted.
- **Verification**, as for the audio upgrade: compare `--dump-every` frames, `--gpu-stats` and
  `--wav` from the old and new builds for the system ROM (every boot theme) and every cart. They
  must be bit-identical.
- **Standard library.** `planes.akr` is new. `poly_upper` adds an OR into the first colour word
  of each packet, which is free when it is off, because the value is 0. Nothing changes for carts
  that do not call it.
- **System ROM.** The shell and boot themes keep working unchanged. Launching a cart, and Home
  back to the shell, go through `mei_load_cart`, which resets, so a cart's plane state never
  leaks into the shell or the next cart. The boot themes are a natural first adopter: their
  Gouraud backdrops (1.41 screens on average) become backdrop tables and planes. Moving one
  screen of backdrop and the clear alone takes the GPU model from 328k to about 214k. The memory card icons and
  the shell's text are unaffected.

## Open questions

1. **GPU budget level, per-pixel costs and a triangle-cap backstop.** The candidate is 40 per
   triangle, ×2 textured, ×2 blended and 0.5 per cleared pixel. *Recommendation:* build the plane
   chip and port Lantern Lake (example a) first, then set the budget from the ported cart's
   measurements. Keep a raised triangle cap (for example 4,000) as a backstop, because the packet
   list must have a bound anyway.
2. **Hole encoding.** `0x8000` is a hole and upper pure black is written as `0x8400`. The
   alternative is a hidden coverage bitmap per framebuffer (9,600 bytes each), which avoids the
   black rewrite but adds invisible state. *Recommendation:* `0x8000`. It is one rule, it is all
   in VRAM, and the colour change is invisible.
3. **Blended polygons over holes** blend with black, as on the Saturn. An alternative is "colour
   calculation for polygons": a blended packet over a hole stores its blend mode for the
   compositor. That needs more framebuffer bits than there are. *Recommendation:* keep the gap,
   and revisit only if the Lantern Lake prototype looks wrong.
4. **Map entry layout.** The SNES layout (3-bit palette plus a priority bit) or 4-bit palettes with
   no priority bit. *Recommendation:* SNES, because the priority bit is what lets level tiles pass
   in front of characters.
5. **Plane count.** Two tile planes plus an affine plane that can also act as a tile plane, or three
   tile planes plus the affine one. *Recommendation:* three in all. Every example fits, and the
   VRAM pressure stays real.
6. **Composing at vsync** (no tearing, no mid-frame raster tricks other than line channels) or
   per line in time with the CPU. The CPU has no line timing or interrupts. *Recommendation:*
   vsync.
7. **Line tables in VRAM only**, or also in RAM like HDMA. *Recommendation:* VRAM only.
   There is enough of it, and the chip stays self-contained.
8. **Backdrop precision.** 8 bits per channel, dithered, or 15-bit. *Recommendation:* 8 bits per
   channel with dither (`PLN_CTRL` bit 2), so a sky gradient does not band.
9. **Free auto-erase.** It makes a cart that uses planes cheaper than one that calls `GPU_CLEAR`
   under the GPU budget. *Recommendation:* keep it free, as VDP1's erase was.
10. **Lantern Lake's camera roll and warm sky tint.** The port loses them, or approximates them
    (example a). *Recommendation:* drop the roll and do the warm tint with BG1, then judge in the
    prototype.
