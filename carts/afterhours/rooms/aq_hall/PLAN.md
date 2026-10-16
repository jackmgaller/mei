# The aquarium, room 0: the entrance hall (floor plan)

Legs 0 and 9 of the aquarium (`levels/aquarium/ROUTE.md`). The aquarium's front of house after
closing, dark but for its tanks: the main doors from the street (west, front), the ticket gates
shut, the information desk, and in the middle **the welcome tank**, a cylinder of sea rising from
the floor through the mezzanine. Over the back of the hall runs the restaurant's **mezzanine**
(level 1, +3.2 m), round the tank's top, with two booths against the back wall, tables at its
railing, and a glass door at its west end out to the pedestrian deck: the stage's end.

- **Leg 0 (the floor, the stage's start)**: in by the main doors, across the welcome tank's light
  while the guard behind the information desk looks at the east door, then through the east door's
  blue spill while he looks back across the tank. Teaches the dark: his cone is harmless where no
  light falls.
- **Leg 9 (the mezzanine, the finale)**: in from the great tank's catwalk (east), behind the night
  guard with a torch as he walks west, across the tank's lit top while the camera by the east booth
  looks away, into the west booth while he turns at the end, and out by the deck door behind him.

## Must stay

- The floor's walls and doorways (main doors west z −3.0 … −1.8; the great tank's door east z
  −1.6 … −0.4), the front wall cut at 1 m; the back and end walls 5.6 m high, with the mezzanine's
  doorways (east to the catwalk, west to the deck, both z 2.2 … 3.4 at +3.2 m).
- The welcome tank's glass footprint x −1.2 … 1.6, z −0.6 … 2.2 (round it inside the box if you
  like, on a square plinth that fills it) and its top as water on the mezzanine; the gates' line
  (low), the desk (low), the two pillars (block, cut at 1 m).
- The mezzanine x −8 … 8, z 1.3 … 3.5 at +3.2 m, its front edge open air (a railing, cones see
  through it); its booths (the hiding places) and tables where they are.
- The lights: on the floor, the tank's glow (three boxes round it and down to the front wall) and
  the east door's blue; on the mezzanine, the tank top's glow (x −2.2 … 2.6). Nothing else lit.
- The floor under the mezzanine's front edge stays visible: keep the mezzanine's deck slatted or
  grated where it overhangs, and nothing tall under it.

## Free to dress

The main doors' glass and the street's night beyond, the ticket windows and fare pictograms, the
information desk's leaflets and a lit map (shapes, no words), the shop's shutter, posters of fish
as lit panels, the welcome tank's fish, the restaurant's tables and chairs, the deck beyond the
glass door (the city's lights).

## For the builder

- **The numbers** are `ROOM` in `make_aq_hall.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_hall.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_hall.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`ah_`) and not the greybox's own (`ah_shell`, `ah_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/ah_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_hall.placements.json` (format
  `after-hours-placements`, ids with the prefix).
- **Budget**: 2,500 triangles for everything placed. Textures: this room's region uses texture
  slots `13-9,16-19` (9 slots of 32 KB); keep its textures within about 250 KB, and never touch
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
