# 09 Hi-Fi Deck

The Mei as one more component in the rack under the TV. It has a brushed champagne fascia
between walnut cheeks, a gunmetal cover vented at the back, and gold insulator feet. The upper
band holds a black anodised 明 MEI nameplate and a cassette-style cartridge deck door, with a
LANTERN cart showing through its smoked window. Beside them are a fluorescent display (the
MeiNet clock, weather and a spectrum analyser) and a knurled multi-jog with a spun-aluminium
cap. The lower band, a shade darker, has POWER with its red LED, RESET, OPEN/CLOSE, the two
controller ports and the two memory card slots. The rear has AV OUT (RCA jacks as geometry),
MeiNet ANT IN, RF OUT and DC IN. The controller uses the same materials: a champagne top plate
over a gunmetal bevel and walnut sides. Its stick is a small volume knob with the same knurl
and spun cap. A is sun orange, B is moon blue, and X and Y are gunmetal.

- **Console:** 806 triangles, 521 vertices; 0.322 × 0.0905 × 0.275 m (w × h × d), feet included
  (0.289 m deep with the knob and the rear jacks).
- **Controller:** 652 triangles, 415 vertices; 0.156 × 0.093 m in plan, a 30 mm body and 43 mm to
  the top of the stick.
- **Scale:** metres at real size. 16.16 fixed point had no trouble at this size, so nothing is
  scaled up.
- **Verify:** both pass the Asset Checker with verification required, in depth and perspective
  mode. No geometry findings fail. The allowed findings are only surface intersections: parts
  sunk 1–3 mm into the fascia and body, never flush.
- **Textures:** console 64,449 bytes of VRAM (slots 12–14). Most of that is the two 4-bit
  255 × 130 fascia halves, needed so the labels land under their parts. Controller 19,319 bytes
  (slot 14). All textures are 4-bit. The display is an animated texture (4 frames of the
  spectrum, 9 ticks each), and the previews show frame 0.
- **Source:** `make_hifi_deck.py` (Pillow) draws `art/` and writes both recipes from one set of
  measurements, so the printing and the parts stay aligned. Run it after any change instead of
  editing the JSON by hand.

What the kit made hard:

- **No booleans.** The door, display, ports and card slots are bevelled plates standing 1–3 mm
  proud of the fascia, with their back faces sunk inside it. The grooves and recess rings are
  printed in the textures.
- **No decals.** A 0.3 mm decal ties in the depth buffer beyond about half a metre, so all the
  print is in each face's own `fit` texture.
- **Small print.** At 320 × 240, 3 × 5 pixel lettering reads as fine silk-screen speckle, not
  as words. The logo plate and the display carry the identity.
- **The probe.** `build-console/mei-asset-probe` was an empty file, so I compiled
  `tools/assetkit_probe.c` against `build-console/libmeicore.a` into my scratchpad and passed it
  with `--probe`. Nothing in the shared build directory was rebuilt.
