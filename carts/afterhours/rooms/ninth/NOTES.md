# The tower, the ninth floor (9F): dressing notes

The floor the directory leaves out, the chairman's own, in 1990. Deep carpet with a key-pattern
border; the city's light through the windows at the front; a chandelier over the boardroom table;
walnut on the back wall with two paintings hung; paintings in crates by the office, one unwrapped
and leaning; the chairman's office in a wine carpet with a medallion. The lift core is walled up:
fresh plaster over the lift doors on its panelling, and in its 1 m cut the hall's plan.

## The core, matching the hall

Cut at 1 m like everything in play, showing the same plan as `../hall/dress_hall.py`'s core: three
lift shafts along its south side (x −4.4 … −0.2, z 0.65 … 1.75), a car far below in each (the
middle one lit, passing: the `lift_car` light), the fire stair's flights behind the shafts
(z 1.95 … 4.0) with its landing at the walled-up west door, and the risers and a duct at the east
end. The plaster patches on the core's south face sit at the hall's lift positions.

## Signature props (once in the stage)

- **The walled-up core** (above).
- **The boardroom**: the table, eight leather chairs with cut backs and two at the ends, its glass
  (cut at 1 m, closed), the chandelier's light, and on the table the model of the next tower.
- **The coat cupboard** with its coats, cut.
- **The chairman's office**: its wall and doorway, the desk with its tooled top, the chair, a golf
  bag and clubs.
- **The crated paintings**, stencilled, and one unwrapped (a fictional field) leaning on a crate.
- **Two paintings on the walnut** (fictional), and the private stair up beyond the east doorway.

No plant (the hall's ficus is the stage's one), no sofa, no reception lamp, no lift-hall brass.

## What stays as the plan says

The core solid where it is; the cupboard and its sides; the boardroom's glass closed; the office
wall, doorway and desk; the camera's place; both stair doorways open with the way on dressed
beyond (the service stair down, lit green; the private stair up toward the helipad's light); the
corridor between the core and the boardroom and the front strip clear; the front cut at 1 m.
`ninth.play.json` is untouched.

## How it is made

`dress_ninth.py [--no-placements]` writes the recipes, `art/` and `ninth.placements.json`, with
`../passage/diorama.py`'s light and painting. `../passage/capture.py ninth --build-dir B
[--verify]` writes `shots/` and `numbers.json`.

| Recipe | Triangles | What |
|---|---|---|
| `nf_floor` | 1,402 | everything but the boardroom's glass |
| `nf_glass` | 88 | the boardroom's glass and posts, corners only (`max_added` 0) |
| **room** | **1,490** | of the 2,500 allowed |
| `nf_floor_col` | | the floor, the walls without tops, the core, the cupboard's sides, the boardroom, the office wall, the desk, the crates |

Placements: `nf_floor` (collision `nf_floor_col`), `nf_glass` (collision `none`). Both pass the
Asset Checker in depth mode. Slots 16–31 (the assembler's set for this room); 118,476 bytes of
VRAM; one 8-bit palette.

Lights (11): `city_w`, `city_e`, `night`, `chandelier`, `lamp` (the office's), `service`,
`helipad` (through the east doorway), `lift_car` (in the middle shaft, below the floor),
`crates`, `exit_w`, `exit_e`.

At the game's camera (60°, three pans, 2026-10-15): full 998–1,030 triangles drawn, CPU
219,653–222,821, GPU 318,874–323,722 cycles; bare 830–860, CPU ~186–189k, GPU ~300–304k.

## What fought me

- The core's section: shaft walls, the shafts' back, the stair's walls and pit, the flights and
  their rail, the duct and the core's own faces kept meeting in one plane; depth mode found each.
  1 cm offsets, opened faces, and tops dropped below the cut.
- The flights' extrude profiles: repeated and collinear outline points (`simple()` removes them).
- Leather chairs whose backs faced the table (their materials were swapped).
