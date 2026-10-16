# The life-support plant (room 5): dressing notes

## Questions for J, answered (2026-10-15)

- **The sand filters**: whole, at full height (J's call: they stand against the back wall and hide
  only it; the play file has them blocking at 2.4 m). Done: domed heads at 2.37 m.
- **The walkway pumps' suction pipes** reaching 0.3 m over the sump: fine as they are.
- **AGENTS.md's Generators table**: J passes it to the coordinator.

## What it is

The basement under the galleries, the building's engine room: loud, wet, industrial and lit by
work lamps.

- **The water.** The four sumps and the front channel are open sea water, dark green, 0.3 m under
  the walkways. In them:
  - the clamp lamps' and overhead lamps' reflections, broken by the ripple;
  - the kerbs' shadow along every edge;
  - foam where the filters' returns pour in under the back walkway and round the pumps in the
    sumps;
  - the intakes' strainers under the surface.

  The concrete kerbs below the walkways are capped with a yellow steel edge.
- **The walkways.** They are galvanised grating in 1 m panels, with yellow and black edges and
  wet footprints along the engineer's round. Yellow railings (cutouts) run along every edge over
  the water. The back zone is concrete with a channel drain and the filters' plinths.
- **The three sand filters.** They are the stage's only ones: whole pressure vessels in machinery
  green, full height (the level lead's call: against the back wall they hide only the wall). Each
  has a domed head, two seam bands, a manway and a valve nest of two headers and four red
  handwheels. A gauge stands on a stalk, two risers climb the back wall, and a green manifold and
  a blue return line run along it.
- **Four pumps:**
  - two on the front walkway: blue motor, grey volute, outlet, suction pipe into the sump, green
    status lamp;
  - two standing on concrete plinths in the sumps: upright motors.
- **The lamps.**
  - cage lamps on the back wall between the filters;
  - clamp lamps on the front railing;
  - three lamps over the cross walkways, beyond the section, so not drawn.

  Their light is painted into the walkways (with the filters' and pumps' soft shadows) and the
  water, and baked into the machinery.
- **The back wall** is cream over a green dado. It has damp stains under the manifold,
  ear-defender pictograms by both doors and mid-wall, hazard triangles, and a clipboard on a hook.
- **The front wall's section** shows concrete over the floor line and earth under it: this is B1.
- **The stairs.** A flight goes up beyond the west door (to quarantine) and another beyond the
  east door (the service stair to the kitchen).

Every walkway, water edge, filter and pump is where the play file has it. The walkways are drawn
on a grid of cells cut at every walkway edge, so the edges meet end to end.

## Recipes and placements (`dressed/`, `aq_plant.placements.json`)

| Recipe | Triangles | What | Collision |
|---|---|---|---|
| `ap_room` | 471 | The shell: the walkways (7 painted textures, hand UVs), the water (2), the kerbs and edges, the walls with their doorways, the section, the stairs, the lamps | `ap_room_col` |
| `ap_machines` | 1,618 | The sand filters (whole) with their pipework, the manifold, the pumps | `none` |
| `ap_rails` | 34 | The railings: double-sided cutout quads on a 16-texel tile, a post every metre | `none` |
| **room** | **2,123** | of 2,500 | |
| `ap_room_col` | | The greybox's companion: the floor flat at 0 everywhere (the water is the play file's walls), the walls | |

The kit's stand-in holds the shell and the railings: 505 triangles, under the 700 cap. All three
recipes pass the Asset Checker in depth mode.

**Textures:** 177,643 bytes of VRAM, in 8 of the region's 10 slots. The
paintings share one 8-bit palette.

## How it is made

- `python3 carts/afterhours/rooms/aq_plant/dress_aq_plant.py` writes the recipes, `dressed/art/`
  and the placements (`--no-placements` leaves the placements alone). It is rerunnable.
- It reads `make_aq_plant.py`'s `ROOM` and imports `../aq_quar/aqdress.py`: `Cells` is the floor
  at two heights.
- Captures: `python3 carts/afterhours/rooms/aq_quar/capture.py aq_plant --build-dir build-ah-R3`.

## Checks

- **Asset Checker.** `verify` passes for `ap_room`, `ap_machines` and `ap_rails`, in depth mode.
- **World Checker.** It reports 0 hard failures and 0 over thresholds. This cell is 2,123
  triangles with a 505-triangle stand-in. Its views draw 737–1,072 triangles at
  154,705–176,160 GPU cycles.
- **Capture costs** at the game's camera, three pans (west −2.65, middle, east +2.65):

  | Frame | Triangles drawn | CPU cycles | GPU cycles |
  |---|---|---|---|
  | The room alone | 1,155–1,159 | about 225,600 | 334,353–339,721 |
  | With the thief, the engineer and two cones | 1,320–1,327 | 259,063–259,735 | 373,875–384,177 |

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_plant_60.png`, `_x3` | The middle of the pan: the thief by the east pump, the engineer on the middle cross walkway |
| `aq_plant_60_pan_x3.png` | The west, middle and east views side by side |
| `aq_plant_60_room_x3.png` | The room alone |

## What fought me

- **The greybox's water was hidden**: it lay inside the floor slab. Here the walkways are cells at
  0 and the water is cells at −0.3, with kerbs between them.
- **Flush faces:**
  - the pump plinths in the sumps against the cross walkways' kerbs: those faces are open;
  - the walkway pumps' bases against the kerbs' lip;
  - the motors on their casings.
- **The foam.** Scattered specks read as snow, so it is gathered round the inflows.
