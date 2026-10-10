# 03 Eclipse Black

**Idea.** The Eclipse boot theme made into an object. The console is a low matte-charcoal slab
whose top carries a total eclipse: a black moon disc ringed by one thin gold corona, with 明 (日
orange, 月 pale blue) at its centre. The power light is the eclipse's "diamond ring", a warm bead
on the corona toward the rear right. Everything else is held back: a dark shadow line separating
the lid from the lower body, a recessed black plinth so the slab seems to float, two controller
ports with memory card slits above them, a small gold spaced "M E I" on the front, power and
reset in black collars on the top's front corners (an orange pip by power, a blue one by reset),
slatted vents on the sides, and a cart in the rear slot whose label repeats the eclipse. The
controller uses the same charcoal and black wells; its single gold ring is around the stick, the
same corona as the console's. A is sun orange, B moon blue, X and Y graphite.

**Scale.** Metres at real size, no scaling: console 0.302 × 0.113 × 0.240 m (W × H × D, cart
included; the cart stands 44 mm proud), controller 0.158 × 0.044 × 0.133 m. Front faces −Z;
the controller's player side faces −Z, so L and R and the cord stub are on its +Z edge.

**Counts.** Console 1,174 triangles, 752 vertices (budget 1,200). Controller 798 triangles, 495
vertices (budget 800). Both pass `verify` with `"verification": {"required": true, "depth": true,
"perspective": true}`: 0 failures; the allowed findings are surface intersections and
T-junctions, as depth mode permits.

**Files.** `make_eclipse_black.py` writes both recipes and `art/eclipse_black.png` with its
`.sheet.json` (emblem, wordmark, port socket, cart label, vent; drawn with Pillow from the macOS
Hiragino W6 and Futura fonts). `cameras_*.json` are the close views behind
`preview_*_closeups.png`.

**What the kit made hard.**

- Fixed point was no trouble at real size: the thinnest parts (0.6–1 mm proud details, the
  emblem standing about 1 mm above the disc) build and verify cleanly.
- The ring is the whole look, and at 2 mm wide it broke into dashes in the fitted 320 × 240
  views; it had to be widened to a 4.5 mm top bevel to read as a line.
- Charcoal against the preview's near-black background nearly vanished; the body went up to
  `#4a4a52` and the contrast now comes from the black disc, plinth and wells.
- The budgets set the segment counts: the eclipse is 40 segments; the controller's buttons,
  wells and stick are 8–16, and the grip handles are 4-ring ellipsoids. One flat loft would
  have made the controller look like a slab, so the handles had to fit in the 800.
- A lathe cannot dish (its heights must rise), so the stick cap is a low dome, not a cup.
- `build-console/mei-asset-probe` was an empty file (0 bytes) during this work, so verification
  ran with a private copy compiled from `tools/assetkit_probe.c` and
  `build-console/libmeicore.a` (passed with `--probe`). Nothing in `build-console/` was changed.
