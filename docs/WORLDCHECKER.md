# The World Checker

The World Checker is the World Kit's in-level verification ([WORLDKIT.md](WORLDKIT.md),
"Verification"): the level-scale counterpart of the Asset Kit's Asset Checker
([ASSETKIT.md](ASSETKIT.md), "Automated visibility gate"). The Asset Checker looks at one object
from outside. The World Checker looks at a level from inside, from where a player can stand,
glide and look, on the real runtime (`stdlib/worldpack.akr`) and the real console core.

It needs only a built pack ([WORLDPACK.md](WORLDPACK.md)) and a settings object, so it runs on a
pack from `tools/worldkit/pack.py` as well as on one from `mei_world.py build`.

```sh
make build/meic build/mei-scene-probe
python3 tools/worldkit/verify.py city.world.bin -o build/city-check            # report mode
python3 tools/worldkit/verify.py city.world.bin -o build/city-check --strict   # enforce thresholds
```

The command prints the report as JSON and exits 1 when the check fails. With `-o` it also writes
`world-check.json` and diagnostic pictures of the worst views. From Python:

```python
from worldkit.verify import verify, check_world
report = verify(pack_bytes, settings, names=None, out_dir=None, tools=None)
report = check_world(context)     # what worldkit.build.run_gate() calls
```

| Part | File |
|---|---|
| Settings, sampling, outcome, command line, `check_world` | `tools/worldkit/verify.py` |
| Static checks (collision, references, counts) | `tools/worldkit/verify_static.py` |
| Verification cart, identity packs, the ordering reference | `tools/worldkit/verify_render.py` |
| What it takes from the Asset Kit (one place, to move to `tools/kitcore/`) | `tools/worldkit/verify_shared.py` |
| The probe: runs the cart, records each frame | `tools/worldkit/scene_probe.c` (`make build/mei-scene-probe`) |
| Tests | `tests/test_worldverify.py`, worlds in `tests/worldverify/worlds.py` |

## Outcome

A check **fails** on a hard failure in any mode, and on a threshold failure in strict mode
(`"mode": "strict"`; the World Kit recipe's `"enforce"`). The default is report mode: thresholds
are measured and listed, and nothing fails on them.

| Hard failures (every mode) | Threshold failures (strict mode only) |
|---|---|
| a pack that does not decode | a view over `gpu_cycles` or `draw_cpu_cycles` |
| a view with dropped triangles (over the GPU's 4,000) | wrong-order pixels in the near band over `near_wrong_pixels` |
| a view that filled the packet arena | wrong-order pixels elsewhere over `far_wrong_fraction` of the screen |
| a collision crack or mismatched floor edge | coverage errors over `coverage_pixels` |
| an entity origin inside solid collision | a cell over `cell_triangles`, `cell_placements`, `standin_triangles` |
| a face index outside its mesh | a cell without a stand-in that other cells can see |

The report (`"format": "mei-world-check"`) holds `ok`, `mode`, the full `settings`, the lists
`hard_failures` and `threshold_failures` (each entry names the check, the code, the cell or the
view with its camera and layers, the value and the limit, and a witness), the `static` results,
one row per view, a `summary` of the worst views, `images`, `scope` and `timing`. Everything but
`timing` is deterministic: the same pack and settings give the same report.

## Settings

Settings are a JSON object merged over these defaults; unknown keys are errors. The thresholds
are WORLDKIT.md's placeholders.

| Setting | Default | |
|---|---|---|
| `mode` | `report` | or `strict` |
| `probe` | radius 0.3, height 1.6, step 0.32 | the game schema's body |
| `eye_height` | 1.5 | above the floor |
| `thresholds.near_band` | 16 | units of view depth |
| `thresholds.near_wrong_pixels` | 0 | per view, nearer than the band or on an entity |
| `thresholds.far_wrong_fraction` | 0.005 | of the screen (384 pixels), per view |
| `thresholds.coverage_pixels` | 0 | per view |
| `thresholds.gpu_cycles` | 800,000 | 80% of the GPU's budget |
| `thresholds.draw_cpu_cycles` | 300,000 | 60% of the CPU's: `wp_draw()` plus entity meshes |
| `thresholds.cell_triangles`, `cell_placements`, `standin_triangles` | 1,600, 100, 32 | every layer on |
| `sampling.floor_spacing` | 16 | grid spacing over each cell's floors (`null`: none) |
| `sampling.yaws`, `yaw_offset_degrees` | 4, 22.5 | directions per position |
| `sampling.eye_pitches_degrees` | [0] | |
| `sampling.follow` | distance 6, height 2.5 | a camera behind and above the eye, pulled in by walls (`null`: none) |
| `sampling.rooftops_per_cell`, `roof_pitches_degrees` | 2, [−20] | |
| `sampling.air` | height 4, reach 48 | between rooftops (`null`: none) |
| `sampling.seams` | spacing 32 | on cell seams (`null`: none) |
| `sampling.layer_combinations` | true | |
| `sampling.max_views` | 600 | views after layer combinations; thinned evenly per kind; vantage points always kept |
| `vantage_points` | [] | `{"position": [x, y, z], "yaw": deg, "pitch": deg}` |
| `runtime` | far ring 3, near 0.1, near far 1.5 cells, entities drawn | what the game sets on the reader |
| `ordering` | on; edge margin 1 px; depth epsilon 0.001 | see [Ordering](#ordering-check-3) |
| `collision` | 4 samples a unit, rays of 32 units, 50 findings | |
| `images` | 6 | diagnostic pictures of the worst views |

`names` (optional) labels witnesses: `{"placements": {"TAG": "id"}, "entities": {"N": "id"}}`.

## Static checks (check 1)

Collision is read back from the pack as the console reads it: every cell's floor, wall and
ceiling records, translated into world rows (exactly: cell centres are whole units) and merged
across the cells a triangle was copied into. Floor queries are the reader's own, bit for bit: the
same lookup bucket, the same integer edge tests and height row. So a hole found here is a hole
the console has. Each check runs with every layer off and with each layer on alone.

- **Cracks.** From points along every boundary edge of a floor (an edge no other floor shares,
  row and ends), the checker steps outward up to the probe radius, at 1, 2, 4 and 16 raw units,
  1/256 and 1/64 of a unit, then every 1/16. A point with no floor within the probe step of the
  edge's height followed by one with a floor again is a crack: a gap narrower than the radius
  that a point query falls through. The witness names the cell, both floors' tags, a point and
  the gap. Points are sampled (4 a unit along each edge), so a sliver thinner than one raw unit
  between samples can be missed; T-junctions are caught structurally instead:
- **Mismatched floor edges.** Two boundary edges on one line (within 1/1024 unit), facing each
  other, overlapping, at heights within the probe step, that do not share rows: a T-junction or
  corners that disagree, inside a cell or across a seam (`on_seam`). WORLDPACK.md, "Floor and
  ceiling records", says these leave cracks; the checker rejects them.
- **Entities inside solid.** 14 rays from the entity's origin (axes and diagonals, slightly
  skewed off edges, 32 units): if every one first meets a triangle from behind, the origin is
  inside a closed solid. An origin on a surface is not inside. An entity's own collision block
  is not included.
- **References.** Face indices within their meshes (`decode()` checks the rest), stand-ins for
  cells within 2 to `far_ring` cells of another cell (a policy: strict mode), unused layers and
  faces the ordering check cannot judge (warnings).
- **Counts** per cell and region: placements, triangles (with and without layers), vertices,
  stand-in and entity triangles, collision triangles.

Sloped floors are judged by the encoder's kinds; the checker does not know `floor_max_degrees`
(the pack stores kinds, not the angle).

## Sampled views (check 2)

Cameras come from the pack's floors:

- **eye** and **follow**: a grid over each cell, every distinct floor with room for the body
  (`probe.height` clear above, no wall within `probe.radius`); the eye at `eye_height`; the follow
  camera behind and above it looking at the head, pulled in front of anything between them;
- **rooftop**: each cell's highest floors with room to stand, at distinct placements;
- **air**: midway between rooftops 4 to 48 units apart, 4 units above the higher, looking along,
  across and back (the glider);
- **seam**: on both sides of each seam between cells, looking along and across it;
- **vantage**: as given.

Each view is repeated for each layer set: all off, each layer alone, and the largest set the
exclusive groups allow (in each group the layer with the most triangles, with every ungrouped
layer), where a cell with those layers is within reach of the camera.

A generated verification cart (`verify_render.py`) opens the pack with `stdlib/worldpack.akr`
and draws each view twice on the headless core: once from the pack as built, measured, and once
from an identity pack for the ordering check. It sets the reader's settings and layers, clears,
calls `wp_draw()`, then draws the live entities' meshes in the 3 × 3 near cells as a game would
(`mesh_at(mesh, pos − wp_view_origin(), yaw)`). `mei-scene-probe` links the core, runs the cart
and after each presented frame records the frame's GPU statistics, a 128-byte block the cart
fills (cycles around `wp_draw()` and the entity loop, packet arena bytes used and left, the
reader's `wp_stats`, the view origin and the camera matrix) and, for identity frames, the
picture. A frame over budget shows late; the probe counts presented frames, so lag does not
shift views. Per view the report has:

| `stats` | |
|---|---|
| `draw_cpu_cycles` | `wp_draw()` plus the entity meshes (`wp_draw_cycles`, `entity_cycles`) |
| `frame_cpu_cycles` | the whole frame |
| `gpu_cycles` | the frame's GPU cycles (including the clear, 38,400) |
| `triangles`, `triangles_dropped` | as the GPU counted them |
| `arena_bytes`, `arena_full` | full: fewer bytes left than a quad's packet (the face loops stop there) |
| `placements_drawn`, `standins_drawn`, `entities_drawn` | |

The measured frame and the identity frame differ only in colours and texture flags, so they
submit the same triangles.

## Ordering (check 3)

The identity pack is a copy of the pack in which every placement, stand-in and entity mesh in
reach has its own copy appended, each face drawn in its own 15-bit ID (dithering off), untextured
and opaque (`FACE_KEYED` faces keep their bucket). The picture then says which face the runtime
left on each pixel.

The **reference** is independent of the runtime's drawing code. From the pack it selects what
the reader should draw: the near 3 × 3 cells with layers applied, each cell and placement
culled by its sphere against the near pass's six planes, the stand-ins of the far ring against
the far pass's, and the entities. A sphere within 1/64 unit of a plane is "unsure": its faces may
cover pixels but are never expected. Every face is transformed in floating point with the camera
matrix the cart used, clipped to its pass's near plane (0.1 near, half a cell far), back-face
culled, projected, and centred on the runtime's rounding (`vproj` rounds down). At each pixel the
reference keeps, per pass, the nearest face by true view depth (from the face's plane), the
nearest face that *may* cover it and the second nearest. A pixel's expected face is decided only
when the nearest face covers it at least `edge_margin` (1) pixels inside, is the nearest of all
faces that come within that margin, and is nearer than the next by more than `depth_epsilon`
plus the face's non-planarity. Wherever a near-pass face may cover a pixel, the far pass is
behind it by the reader's design; a stand-in truly in front of near geometry is counted as a
`pass_inversion`, not an error. Faces whose plane passes through the eye (edge-on), thin faces,
twisted quads, semi-transparent faces and textured faces that are not palette swatches may cover
pixels but are never expected (a swatch face covers exactly the pixels of its untextured face, as
in the Asset Checker).

Then, at every decided pixel:

- the runtime drew the expected face (or nothing where nothing was expected): correct;
- it drew a face that may cover the pixel and is farther than the expected one: **wrong order**;
- anything else (nothing, a face that cannot be there, a stand-in over a near face): a
  **coverage error**.

Wrong-order pixels are **near** when the visible surface is nearer than `near_band` or either
face belongs to an entity, otherwise **far**. Witnesses group them by (drawn face, expected face)
with the cell, placement number, tag (and name), face number, a sample pixel, the visible depth
and the largest depth error. Each view reports `tested_pixels`, `tested_background` and
`undecided_pixels`, so how much was checked is always visible.

### What is exact, and the evidence

Every pixel the reference decides is judged exactly, for every class of view: cameras anywhere
(on floors, in the air, against walls), several meshes per view, faces crossing the near plane
or the guard band, both passes, layers, entities and swatch faces. What is not judged: pixels
within `edge_margin` of a face's outline, depth ties (coplanar overlaps: reported as undecided,
not as z-fighting), and faces of the kinds listed above. A mis-sort confined to those pixels
(two faces closer than 0.001 units in depth, or overlapping by less than about two pixels) is
not reported.

Evidence (the tests and the sweeps behind them):

- A deliberately mis-sorted pair (a runway strip drawn over the crate standing on it) is caught:
  223 wrong pixels in the near band, witnessed as strip over crate, from the right camera.
- The known-good plaza comes back clean in strict mode from 60 sampled views (1.9 million
  decided pixels): no wrong-order pixel, no coverage error.
- Faces crossing the near plane: a floor and a wall seen from 0.05 units are neither dropped nor
  invented; a camera whose whole view is nearer than the near plane expects and gets an empty
  screen.
- Sweeps with no coverage error: the world pack demonstration world, 3,005 sampled views
  (129 million decided pixels, stand-ins, layers, entities); the dense bench world (yawed
  props), 600 random cameras.
- 1,500 random cameras over the demonstration world (many inside geometry or against it) found 4
  views with coverage errors. All four are faces the runtime drops, not reference errors: for
  example from eye (10.5278, 2.6406, 9.0798), yaw −2.9315597, pitch −0.8297644 (under the roof
  in cell (0, 0), looking down at the ground) a plain cart calling only `wp_draw()` leaves a
  5,179-pixel hole in the ground tile under the camera, which crosses the near plane, and the
  hole closes when the camera moves 1/10,000 of a radian; from (135.2339, 23.4188, 9.4824), yaw
  −131.8°, pitch −39.3° a stand-in face crossing the far pass's near plane at the screen's edge
  is missing. Both point at the near-plane path of the face loops and `stdlib/clip.akr`. This is
  what coverage errors are for; they fail only in strict mode.

## Timing

Measured on an Apple-silicon Mac with `make` defaults:

| | Seconds |
|---|---|
| compiling a verification cart | 0.02–0.03 (one per run, or one per camera cell in large worlds) |
| emulating a view (two frames) | 0.004 |
| the ordering reference, per view | 0.015–0.03 (more faces, more time) |
| a whole view | 0.02–0.036 |
| static checks: plaza / demonstration world / bench world | 0.01 / 0.13 / 1.4 |
| the plaza with default sampling (60 views) | 1.5 |
| the demonstration world, every sampled view (3,005: 601 cameras × layer sets) | 67 |

Hence `max_views` 600 (about 15–20 seconds a world). The reference dominates; NumPy work per
face is the cost, so dense views cost more. Sampling and static checks are pure Python and grow
with the number of floors.

## Limits

- **IDs.** A view's faces need distinct 15-bit IDs. A world with at most 32,767 faces in all
  gets one identity pack and one cart; a larger one gets one per camera cell, holding the
  instances within the far ring. A camera cell with more than that in reach is reported as
  skipped for ordering.
- **ROM.** The cart embeds the pack twice (as built and as identity pack): a pack over about
  31 MB does not fit a 64 MB cart.
- **Sampling** is finite: views the sampler never makes are not checked; positions are where a
  body can stand by the pack's collision.
- **Not checked yet:** the seam rule for region textures (no region texture drawn while slots
  are swapped) and the overhang limit (the encoder enforces it); fog and the game's own drawing
  beyond entity meshes.

## Where it plugs in

`worldkit.build.run_gate(context)` calls `check_world(context)`: `context['pack']` (the staged
pack's path), `mode` (`report` or `enforce`), `thresholds` (the recipe's
`verification.thresholds`, any key of `thresholds` above), `probe` (the game's; radius, height
and step are used), `stage` (the report and pictures go to `verification/` in it) and `compiler`
(`mei-scene-probe` is looked for beside it, else `build/` or `SCENE_PROBE`). It returns the
report, which has `ok`, or `{"ok": false, "errors": [...]}` when the check could not run.
