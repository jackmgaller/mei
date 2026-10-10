# 04 Sun & Moon Twin

**Idea.** Seen from above, the body is 明's two halves as two objects: a round orange drum (the
sun, 日) with a sunburst top, cradled by a pale-blue crescent (the moon, 月) that is turned 20°
toward the back. A 1 cm gap separates them, and a dark navy plinth under both joins them and
shows at the bottom of the gap, like the shadow line of an eclipse. The moon is taller than the
sun in the middle (86 mm against 76 mm) and its horns sweep down to 28 mm at the tips, so the
two forms still read in the front view. The cart stands in the middle of the sun like a gnomon.
The sun carries the I/O on its front: two controller ports, each with a memory card slot above
it, and a small 明 mark between them. The moon carries power (orange), reset, the power light
and the 明 MEI badge on its top, louvres on its back half and the MeiNet aerial socket. AV out
and DC in are on the sun's back-left. The controller follows the same idea: the d-pad sits on an
orange sun puck, A B X Y run along the crescent from warm (A, front) to cool (Y, back), and the
stick, Select and Start sit on the dark bridge in the gap between them. L is orange on the
sun's back edge, R is blue on the moon's back horn. A short cable runs back and lies on the
table.

**Triangles.** Console 1,130 (668 vertices), controller 798 (476 vertices). Both pass `verify`
with verification required, in depth mode with perspective. Textures: one sheet
(`art/sheet.png`, drawn by `make_art.py`) for the sunburst, the badge, the cart label, the small
mark and the four button letters, plus a stripes pattern for the louvres. The console uses
6,136 bytes of VRAM for textures and the controller 2,757.

**Scale.** Metres at real size, with no scaling. Console 0.307 × 0.289 m, 0.086 m tall at the
moon (0.135 m to the top of the cart). Controller 0.145 × 0.136 m including the cable, 0.036 m
tall. Fixed-point precision was not a problem at this size.

**Files.** `make_models.py` (standard library) writes both recipes; `make_art.py` (Pillow,
Hiragino and Avenir Next from macOS) writes the sheet. Run `make_art.py`, then
`make_models.py`.

**What the kit made hard.**
- No primitive makes a crescent or a ring sector, and loft sections must be horizontal. So both
  bodies are `mesh` nodes built in Python, sampled on rays from the sun's centre.
- The kit has no Boolean or inset operation, so the ports and slots are bezels that stand out
  2–3 mm from the surface, with an opening modelled inside them, instead of being cut in.
- A polygon that is not exactly planar after 16.16 rounding is rejected. Any quad that is not
  in an axis plane therefore has to be split into triangles by the generator. A triangle fan
  from a corner on a collinear run gives zero-area faces ("Face has no area"), so the fan has
  to start at a better corner.
- A `fit` texture covers one source polygon. The sunburst therefore needs a flat top made of a
  single polygon, not a domed one.
- The 800-triangle budget is tight for a controller with round parts. The face buttons have 10
  sides and the stick 9.
