# 10 Kodomo Toy

The machine as a lunchbox: a cream pillow sitting in a fat tomato-red bumper tub, a red carry
handle out of the back, and a yellow cart ("おひさま", Mr Sun) standing in a red slot mouth.
Power is a big red domed button with a cream sun and reset a cream one with a red crescent moon,
so the Sun & Moon idea turns up on the controls themselves. The 明 MEI badge (orange 日, pale-blue
月, white wordmark on a red sticker) sits between them. On the front are two numbered red
controller ports and two memory card slots. The controller matches it: a cream dogbone on a red
lower shell, with red palm bulbs under the grips, a red d-pad and A/B and cream X/Y in beige
wells, a red-capped stick, fat L/R bumpers and a short cream cord.

- Triangles: console 1,184 (606 vertices), controller 806 (447 vertices). Texture VRAM: 3,682
  and 2,500 bytes, all 4-bit.
- Scale: real metres, Y up, front −Z. The console is 0.32 × 0.178 (top of cart) × 0.30 m with
  the handle (0.24 m deep without it). The controller is 0.164 × 0.062 × 0.153 m with its cord
  (0.09 m deep without it). Fixed point was no trouble at this size.
- Verify: both pass the Asset Checker with verification required in depth mode
  (`"depth": true, "perspective": true`), with 0 wrong pixels, 0 coverage errors and no flush
  contacts.
- Files: `make_models.py` writes both recipes. `gen_art.py` draws `art/kodomo.png` and its
  `kodomo.sheet.json` with Pillow and the macOS fonts Hiragino Maru Gothic and Arial Rounded
  Bold. It draws each cell at 8× and snaps it down to a small palette by majority vote, so the
  kit keeps every colour exactly.

What was hard:
- `build-console/mei-asset-probe` was an empty file (0 bytes) during this run. I compiled
  `tools/assetkit_probe.c` against `build-console/libmeicore.a` into a private scratch folder
  and passed it with `--probe`. meic and mei-headless came from `build-console/`.
- The budgets decided the curves. The loft bodies use 24 points per section on the console and
  about 29 on the controller, buttons use 8–16 segments and the L/R bumpers are chamfered rather
  than rounded. Lofts can't leave out a single cap, so about 200 triangles of hidden caps (the
  cream bottoms inside the red shells) still count against the budget.
- A loft refuses collinear points. The controller outline is traced from a union of shapes and
  resampled, so its straight runs have to be thinned before lofting.
- Labels on raised parts use `planar` projection with `scale` set to the part's size and
  `offset` [0.5, 0.5]. That puts exactly one repeat on the top or front face, and the thin sides
  pick up only edge colours. The buttons use `disc` projection on their caps.
