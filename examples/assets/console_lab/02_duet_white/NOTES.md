# 02 Duet White

The Duet boot stage made into plastic. The console is a soft pearl pebble (28 × 20.8 × 7.8 cm,
14 cm to the top of the cart), with a lilac-grey underside that makes it seem to float on the
table. Power and reset are the boot's two drops: a domed orange sun-drop and a blue moon-drop
on the top's front corners, tips turned toward each other. From each drop a printed dotted
bounce trail arcs up to a stadium-shaped cart collar. The "Duet line" runs around the waist,
sun orange on the left fading through pearl to moon blue on the right. A raised pill
nameplate carries 明 (日 orange, 月 blue) and MEI, set in Hiragino Maru Gothic. The front
has two oval controller ports below two memory card slots, with an orange and a blue dot
between them. The back has DC IN, AV OUT and the MeiNet antenna socket, with printed vents.
A pale lilac cart stands in the slot; its label shows the two drops.

The controller (16 × 10.3 cm without the cord) is the same pearl, has the same Duet line
round its waist and soft bulbs under the grips. The d-pad is on the upper left with the stick
inboard of it. A B X Y form a diamond, with the warm buttons on the top and right (X peach,
A sun orange) and the cool ones on the bottom and left (B moon blue, Y sky). Start and
Select sit in the middle under a small 明. L and R are soft lilac pads that follow the far
edge.

| | Triangles | Vertices | Texture VRAM |
|---|---|---|---|
| `console.asset.json` | 1,188 | 656 | 19,585 bytes (5 tiles, 8-bit, slot 13) |
| `controller.asset.json` | 814 | 463 | 790 bytes (2 tiles) |

- **Scale:** real size in metres, 1 unit = 1 m. Fixed point caused no problems at this
  size, so nothing is scaled up.
- **Verify:** both recipes require the Asset Checker in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Both pass:
  0 wrong pixels, 0 coverage errors, 0 flush contacts. The crossings (`surface_intersection`)
  and T-junctions are allowed in depth mode.
- **Source:** `make_duet_white.py` writes both recipes and `art/duet_sheet.png` with its
  `.sheet.json`, which needs Pillow and the macOS font Hiragino Maru Gothic. The bodies are
  `mesh` nodes built from rings (rounded rectangles for the console, a Chaikin-smoothed and
  inset outline for the controller). They carry hand UVs so that one 32 × 4 gradient spans
  the waist line from left to right, and on the console a 128 × 86 print covers the flat top.

What the kit made hard:

- `build-console/mei-asset-probe` was an empty file, so `verify` failed with "Exec format
  error". I compiled `tools/assetkit_probe.c` against `build-console/libmeicore.a` into a
  scratch directory and passed it with `--probe`. Nothing in `build-console/` was rebuilt.
- `--closeups` places the eye 1.6 m up, so a 30 cm console is a speck. I used `--camera`
  views at 0.3–0.5 m instead.
- A `loft` has caps at both ends or at neither, and smoothing averages a flat cap into its
  walls. For those two reasons the bodies are explicit meshes: the flat top has a material of
  its own, so it shades flat while the shoulders shade smooth.
- `rounded_rect` with the corner radius equal to the half-depth (a true stadium) makes
  duplicate points, which the kit rejects. The collar and the badge use a radius a little
  smaller than the half-depth.
