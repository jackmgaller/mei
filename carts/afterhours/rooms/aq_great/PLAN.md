# The aquarium, room 1: the great tank (floor plan)

Legs 1 and 8 (`levels/aquarium/ROUTE.md`). The aquarium's main gallery: a long dark room whose
back wall is **one acrylic window** into the great tank, the floor's only light a blue band in
front of it. Benches face the window; a column holds up the roof. Behind and above the window,
over the tank's open water, run **the keepers' catwalks** (level 1, +3.2 m): the rim along the
tank's front edge, a walk along its back, two bridges between them and a feeding platform with a
hopper.

- **Leg 1 (the floor)**: in from the entrance hall (west), behind the night guard with a torch as
  he walks the front of the gallery, out to the jellyfish gallery (east) when he has turned up
  the far end. A camera on the window's east pier watches the blue band. Teaches the torch.
- **Leg 8 (the catwalk)**: in from the tank tops (east, level 1), west along the rim over the
  window, timing a keeper with a torch who looks over the water from the back walk and a camera
  that sees only the rim's two lamps, out to the hall's mezzanine (west). The gallery of leg 1 is
  below, its guard still walking his round.

## Must stay

- The floor x −10 … 10, z −4 … 1.0; the window (glass, the whole width) at z 1.0 … 1.3, floor to
  catwalk; the back and end walls 5.6 m; doorways: west z −1.4 … −0.2 (hall), east z −3.2 … −2.0
  (jellyfish), and at +3.2 m east and west z 1.4 … 2.6 (the tank tops, the hall's mezzanine).
- The benches (low), the column (blocks, cut at 1 m) where they are.
- Level 1: the rim z 1.3 … 2.6, the back walk z 4.0 … 5.0, the bridges x −6 … −4.8 and 4.8 … 6, the
  feeding platform x −1 … 1, z 2.6 … 3.3 with its hopper (blocks); water everywhere else behind
  the window; open air over the gallery in front of the rim (a railing).
- The lights: the window's band on the floor (z −0.7 … 1.0); the rim's two lamps
  (x −8.6 … −6.6 and −2.2 … 2.2). Nothing else lit.
- The rim's deck and railing stay narrow and grated over the window: at 60° the rim hides the
  floor 1.85 m behind it, which is the tank (no play there).

## Free to dress

The great tank's life seen through the window and from above (a ray, a school, kelp, light from
the surface), the window's frame and its seams, the benches' shapes, the keepers' gear on the
catwalk (hoses, a net, a feed bucket), the lamps on their arms over the rim.

## For the builder

- **The numbers** are `ROOM` in `make_aq_great.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_great.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_great.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`ag_`) and not the greybox's own (`ag_shell`, `ag_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/ag_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_great.placements.json` (format
  `after-hours-placements`, ids with the prefix).
- **Budget**: 2,500 triangles for everything placed. Textures: this room's region uses texture
  slots `8,6-3,20-24` (10 slots of 32 KB); keep its textures within about 280 KB, and never touch
  slot 7 or 4-bit palettes 250-251 (the front end's fonts).
- **The section cut**: everything in the play area is cut at 1 m above its own level with a light
  cut top; only the back and end walls stand full height. Doorways stay open and framed, with a
  way on beyond them (the next room's stair, landing or corridor).
- **Light is the puzzle in a dark room**: the lit floor is the play file's `light` boxes. Paint
  the glow on the floor (as `rooms/aquarium/make_aquarium.py`'s `paint_floor()` does) where they
  are and keep the rest dark: what looks lit is lit. Round a box's corners in the paint, never
  move it. A light on a cycle (`period`, `on`, `offset` ticks) is drawn by A's runtime as a wash
  when on; paint its patch as the lamp's colour at half strength, so it reads lit or unlit by the
  wash. A lit room is lit as you like.
- **Fonts** from `tools/fonts/` only. No readable words: signs are lit shapes and pictograms.
- **Signature props once per stage** (the welcome tank, the great window, the jellyfish columns,
  the ocean window, the sand filters, the turtle, the shark): only in the room this plan gives
  them.
- **Checks**: `python3 tools/mei_assets.py verify RECIPE --build-dir YOUR_BUILD_DIR`;
  `python3 carts/afterhours/levels/aquarium/make_aquarium.py` then
  `make B=YOUR_BUILD_DIR YOUR_BUILD_DIR/carts/afterhours.mei` builds the stage's world with the
  World Checker (0 hard failures, 0 over thresholds); captures at the game's camera with a copy
  of `rooms/corridor/capture.py` adapted to this room (until the stage plays in the cart: J will
  say when, and which scenario plays the room's legs). Put your notes and captures in `NOTES.md`
  and `shots/`.
