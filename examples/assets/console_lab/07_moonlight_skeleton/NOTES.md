# 07 Moonlight Skeleton

The 月 half of the skeleton pair: a limited edition (front print 月光, "No. 0707" in spirit) in
translucent indigo. The signature is the **moon window**, a round domed lens on the top right
that shows the Prism chip (明 on its lid) under pale-blue glass, held by a silver crescent
bezel, with a dotted orbit printed around it. The cart (a pale grey "GARDEN" cart with a night
label) stands in a raised slot at the back left; power, reset and a blue power light at the
front left; two controller ports with their memory card slots above them on the front; MeiNet
antenna (F connector), AV out and DC in on the back. The controller has a silver d-pad, A B X Y
in four moonlight tints (harvest gold, blue, lavender, white), and its one analog stick is the
**full moon**: a cratered cream cap in a dotted orbit, centred between the grips.

**Translucency.** The kit draws opaque faces only (per-texel cutouts, no blending), and a
dithered "screen door" shell aliases at these sizes, so the see-through look is painted:
every shell face's texture shows the insides as they would read through indigo plastic (the
board, chips, cart connector, RF shield, screw bosses, port housings, the controller's
contact pads, stick gimbal and coloured cable wires), with soft sheen streaks, deeper edges
where the wall is seen edge on, and lighter bevels where light comes through thin plastic.
Only the moon window shows the chip "directly".

| Model | Triangles | Vertices | Textures (VRAM) | Size |
|---|---|---|---|---|
| `console.asset.json` | 1,006 | 565 | 10 images, 46,718 bytes | 0.290 × 0.115 (with the cart; body top 0.066) × 0.227 m |
| `controller.asset.json` | 786 | 446 | 8 images, 25,635 bytes | 0.159 × 0.046 × 0.115 m |

Scale: metres at real size, no scaling; 16.16 fixed point was fine at this size. Both face −Z
(console: ports; controller: grips toward the player, shoulders and cable toward +Z). Lighting
is directional (ambient 0.55), as for an object seen from a fixed side. Both pass `verify`
with verification required, depth and perspective (of 144 views, 35 judged for the console
and 16 for the controller; 0 wrong pixels, 0 coverage errors; crossings and T-junctions allowed
in depth mode).

**Files.** `make_console.py` and `make_controller.py` paint `art/` (Pillow, Hiragino W8 for 明
and 月光) and write the recipes; `mlib.py` is their shared painter, 3×5 pixel font and mesh
builder. Rerun them after any change rather than editing the JSON.

**What the kit made hard.**
- No transparency, as above. A cutout dither shell over real internal parts was considered
  and rejected: at 320 × 240 its texels are smaller than a pixel in the fitted views.
- Painted faces need hand UVs: the shell is built as `mesh` nodes (top, four flat walls, the
  controller's wall band along its outline) so each gets one fitted image; `fit` on a box or
  loft would put the whole image on every side.
- A mesh face's winding is easy to get backwards on a concave polygon (the d-pad cross) when
  it is judged from its first three corners; `mlib.py` uses Newell's normal.
- `build-console/mei-asset-probe` was an empty file (0 bytes) when this was made, so
  `verify` and `preview` were run with `--probe` pointing at a copy compiled by hand
  (`cc ... tools/assetkit_probe.c build-console/libmeicore.a`) in a private scratch folder;
  no make was run.
- The controller is at its 800-triangle budget (786): the outline has 34 points, the grip
  bulbs and buttons use 8 segments.
