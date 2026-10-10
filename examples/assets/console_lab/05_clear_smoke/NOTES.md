# 05 Clear Smoke

**Idea.** A smoke-grey translucent case, a year before the translucent craze, with the insides on
show. Inside the console are a green board, a CPU under a finned heat sink, the Prism Engine
under a silver lid, the gold cartridge connector with the cart seated in it, and a power supply
with a yellow transformer, blue capacitors and a heat-sink plate. Inside the pad you see its
board, the contact pads and the cable's red, white and black wires. The kit has no
semi-transparency, so the plastic is drawn as a screen door, the way Saturn games drew
transparency: a cutout texture on double-sided faces where half the texels are holes. The flat
tops use a `fit` texture with a diagonal gloss streak; the streak is lighter and has fewer holes.

The body is a low wedge whose top rises 15 mm toward the back. A clear bridge at the back holds
the cart slot, and a charcoal cart with a dusk-sea label stands in it. The 明 MEI badge is on
the bridge's front face and a round 明 emblem is on the top. Power is a sun-orange slider with an
orange LED, and reset is a moon-blue button with a blue LED. The two controller ports sit in the
middle of the front, with a memory card slot outside each one. On the back are the AV out, the
DC in and the gold MeiNet aerial socket. The pad has two grips, a d-pad, A, B, X and Y in Super
Famicom red, yellow, blue and green, a centre analog stick between the grips, Start and Select,
and L and R. Its lower half is painted with the same stipple over a dark colour, which costs no
extra faces.

**Numbers.** Console: 1,014 triangles, 632 vertices. Controller: 782 triangles, 486 vertices.
Both pass the Asset Checker in depth mode with verification required (`"depth": true,
"perspective": true`): 0 wrong pixels and 0 coverage errors. The console is judged in 60 views
and the controller in 47, because cutout texels need extra views.

**Scale.** 1 unit = 1 m, at real size. The console is 0.30 × 0.13 (with the cart) × 0.22 m, and
the controller is 0.154 × 0.047 × 0.118 m. Its grips hang 8 mm below y = 0. Fixed point was no
problem at this scale.

**Files.** `make_art.py` draws `art/clear_smoke.png` and its cells. It needs Pillow and the macOS
Hiragino and Avenir Next fonts. `make_models.py` writes both recipes. The shells are explicit
meshes made from rounded outlines stacked in height.

**What the kit made hard.**
- There is no per-face semi-transparency in recipes (the GPU has it), so translucency is a
  cutout stipple. At the fitted preview size, a 1-texel checker shows moiré. Texels of 4 mm on
  the console and 2.5 mm on the pad were the smallest that read cleanly.
- Through a stipple, a plain backing looks like grey noise rather than plastic. What works is a
  dark liner behind the console's base, a low-contrast smoke there, and something with colour
  and shape behind the top (the board).
- `build-console/mei-asset-probe` was an empty file, 0 bytes. I compiled a private copy into
  the session's scratchpad (`cc … tools/assetkit_probe.c build-console/libmeicore.a`) and
  passed it with `--probe`. I did not run make.
