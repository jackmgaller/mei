# 06 Sunset Skeleton

The 日 half of the limited pair: a clear orange shell that shows the insides. The plastic shades
like a sunset: gold at the deck, through orange, to red at the base. On top, the 明 badge has the
日 lit in orange and only an outline of the 月, the half that belongs to 07 Moonlight. The front
carries a striped setting-sun mark between the ports. The cart in the slot has a sunset label. The
deck slopes 12 mm down toward the front.

The kit has no per-face alpha, so the plastic is faked the way 1990s hardware did it: a cutout
texture with holes, on double-sided shell faces, over a modelled inside. In the console that is
the board, CPU, RAM, a heat sink, the MeiNet tuner can and its coax, the transformer and
capacitors, the cart connector, the port sockets and the card slots. In the controller it is
the board, the membranes, the stick gimbal and two rumble motors.

Three tricks make it read as orange plastic:

- **Darker edges.** The bevels are opaque and more saturated, as thick plastic looks edge-on.
- **Warmed insides.** Every interior colour is filtered through orange (`through_orange()`).
- **Glowing floor.** The inside floor is an emissive orange, so the cavity seems lit through
  the shell.

Pale glare streaks on the clear faces mark them as glossy.

| | Triangles | Vertices | Size (m) |
|---|---|---|---|
| Console (with cart) | 910 | 560 | 0.270 W × 0.110 H × 0.221 D (body 0.205 D, 0.070 H at the back) |
| Controller | 790 | 469 | 0.154 W × 0.063 H × 0.132 D (with cable stub) |

- **Scale:** metres at real size, not scaled up; 16.16 fixed point was fine at that size.
- **Verify:** both recipes pass the Asset Checker with verification required, in depth mode with
  perspective. Nothing fails; only `surface_intersection` and `t_junction` findings are
  allowed.
- **Textures:** console 13.8 KB VRAM, controller 6.8 KB; 4-bit except the cart label (8-bit).
- **Generator:** everything is built by `make_sunset_skeleton.py`, which writes both recipes
  and `art/*.png`. `cameras_*.json` are world-scale views for `preview --cameras`.

What the kit made hard:

- **A regular dither aliases.** A Bayer screen-door at about 1.3 pixels a texel turned into
  moiré contours in the fitted previews. Hashed random flecks (about 25–40 % opaque) do not
  alias and read as clear plastic.
- **Clear faces need hand UVs.** The `fit` projection on a `mesh` node fits each polygon, so
  the sloped or curved shells needed hand UVs: a fitted image projected from above for the
  decks, and a repeating tile laid along the perimeter for the walls.
- **Near-planar quads.** The sloped bevel quads are planar in theory, but after rounding the
  kit rejected them as non-planar, so they are given as triangles.
- **Coplanar bottoms.** Parts standing on the board, such as a capacitor and the cart
  connector, had their bottoms at the same height and overlapped. The fix was to stagger them
  by a fraction of a millimetre.
- **Probe:** `build-console/mei-asset-probe` was an empty file, so `verify` failed with "Exec
  format error". A private copy was compiled from `tools/assetkit_probe.c` and
  `build-console/libmeicore.a` into `build-console/assets/06_sunset_skeleton/_tools/` and
  passed with `--probe`.
