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
| | ground inversions over `ground_inversion_pixels` ([Ground](#ground)) |
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
| `thresholds.ground_inversion_pixels` | 0 | per view: pixels where ground truly hides what is drawn over it |
| `thresholds.gpu_cycles` | 800,000 | 80% of the GPU's budget |
| `thresholds.draw_cpu_cycles` | 600,000 | 60% of the CPU's: `wp_draw()` plus entity meshes |
| `thresholds.cell_triangles`, `cell_placements`, `standin_triangles` | 1,600, 100, 32 | every layer on |
| `sampling.floor_spacing` | 16 | grid spacing over each cell's floors (`null`: none) |
| `sampling.yaws`, `yaw_offset_degrees` | 4, 22.5 | directions per position |
| `sampling.eye_pitches_degrees` | [0] | |
| `sampling.follow` | distance 6, height 2.5 | a camera behind and above the eye, pulled in by walls (`null`: none) |
| `sampling.rooftops_per_cell`, `roof_pitches_degrees` | 2, [−20] | |
| `sampling.air` | height 4, reach 48 | between rooftops (`null`: none) |
| `sampling.seams` | spacing 32 | on cell seams (`null`: none) |
| `sampling.entities` | yaws 6, distances [1.5, 4, 8], pitches [−55, −30, −10], floor distances [2.5, 6] | cameras aimed at each entity with a mesh (`null`: none; [Entities](#entities)) |
| `sampling.layer_combinations` | true | |
| `sampling.max_views` | 600 | views after layer combinations; thinned evenly per kind; vantage points always kept |
| `vantage_points` | [] | `{"position": [x, y, z], "yaw": deg, "pitch": deg}` |
| `runtime` | far ring 3, near 0.1, near far 1.5 cells, entities drawn, ground first, entity drawing `object`, object bias 1.5, object squash 2 | what the game sets on the reader (`ground_first`: `wp_ground_first`; `entity_drawing`: `object`, through `wp_draw_entities()`, or `mesh_at`, each live entity's mesh by its own depth; `object_bias`, `object_squash`: `wp_object_bias`, `wp_object_squash`) |
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
- **Ground** (warnings; [Ground](#ground)): geometry that an upward ground face can hide
  (`ground_hides`), and ground faces that can overlap each other (`ground_over_ground`).
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
- **entity**: aimed at the middle of the mesh of each entity that has one: from each distance, pitch
  and yaw around it (from above, as a follow camera looks at what the player stands near; pulled
  in front of anything between, as a follow camera is), and from eye height on the floors at the
  floor distances around it, in the yaws' directions (from below a ledge it stands on, too). An
  entity in a layer is viewed only with layer sets that have its layer on ([Entities](#entities));
- **vantage**: as given.

Each view is repeated for each layer set: all off, each layer alone, and the largest set the
exclusive groups allow (in each group the layer with the most triangles, with every ungrouped
layer), where a cell with those layers is within reach of the camera.

A generated verification cart (`verify_render.py`) opens the pack with `stdlib/worldpack.akr`
and draws each view twice on the headless core: once from the pack as built, measured, and once
from an identity pack for the ordering check. It sets the reader's settings and layers, clears,
calls `wp_draw()`, then draws the live entities' meshes in the 3 × 3 near cells as a game would:
with `wp_draw_entities()` (runtime `entity_drawing` `object`, the default), or each with
`mesh_at(mesh, pos − wp_view_origin(), yaw)` (`mesh_at`, for a game that draws them so).
`mei-scene-probe` links the core, runs the cart and after each presented frame records the
frame's GPU statistics, a 128-byte block the cart fills (cycles around `wp_draw()` and the
entity loop, packet arena bytes used and left, the reader's `wp_stats`, the view origin and the
camera matrix) and, for identity frames, the picture. A frame over budget shows late; the probe
counts presented frames, so lag does not shift views. Per view the report has:

| `stats` | |
|---|---|
| `draw_cpu_cycles` | `wp_draw()` plus the entity meshes (`wp_draw_cycles`, `entity_cycles`) |
| `frame_cpu_cycles` | the whole frame |
| `gpu_cycles` | the frame's GPU cycles (including the clear, 38,400) |
| `triangles`, `triangles_dropped` | as the GPU counted them |
| `arena_bytes`, `arena_full` | full: fewer bytes left than a quad's packet (the face loops stop there) |
| `placements_drawn`, `ground_drawn`, `standins_drawn`, `entities_drawn` | `ground_drawn`: ground placements, in the ground pass |

The measured frame and the identity frame differ only in colours and texture flags, so they
submit the same triangles.

## Ordering (check 3)

The identity pack is a copy of the pack in which every placement, stand-in and entity mesh in
reach has its own copy appended, each face drawn in its own 15-bit ID (dithering off), untextured
and opaque (`FACE_KEYED` faces keep their bucket). The picture then says which face the runtime
left on each pixel.

The **reference** is independent of the runtime's drawing code. From the pack it selects what
the reader should draw: the near 3 × 3 cells with layers applied, each cell and placement culled
by its sphere against the near pass's six planes (ground placements into the ground pass), the
stand-ins of the far ring against the far pass's, and the entities. A sphere within 1/64 unit of
a plane is "unsure": its faces may cover pixels but are never expected. Every face is
transformed in floating point with the camera matrix the cart used, clipped to its pass's near
plane (0.1 near and ground, half a cell far), back-face culled, projected, and centred on the
runtime's rounding (`vproj` rounds down). At each pixel the reference keeps, per pass, the
nearest face by true view depth (from the face's plane), the nearest face that *may* cover it
and the second nearest. A pixel's expected face is decided only when the nearest face covers it
at least `edge_margin` (1) pixels inside, is the nearest of all faces that come within that
margin, and is nearer than the next by more than `depth_epsilon` plus the face's non-planarity.
The reader draws three passes, each over the one before (far stand-ins, ground, near), so a
pixel's expected face comes from the last pass that may cover it: wherever a near-pass face may
cover a pixel, the ground and the far pass are behind it by the reader's design, and wherever a
ground face may, the far pass is. A stand-in truly in front of ground or near geometry is
counted as a `pass_inversion`, not an error; ground truly in front of near geometry is a ground
inversion ([Ground](#ground)). Faces whose plane passes through the eye (edge-on), thin faces,
twisted quads, semi-transparent faces and textured faces that are not palette swatches may cover
pixels but are never expected (a swatch face covers exactly the pixels of its untextured face,
as in the Asset Checker).

Then, at every decided pixel:

- the runtime drew the expected face (or nothing where nothing was expected): correct;
- it drew a face that may cover the pixel and is farther than the expected one: **wrong order**;
- anything else (nothing, a face that cannot be there, a face of an earlier pass over a later
  pass's, such as a stand-in over a near face): a **coverage error**.

Wrong-order pixels are **near** when the visible surface is nearer than `near_band` or either
face belongs to an entity, otherwise **far**. Witnesses group them by (drawn face, expected face)
with the cell, placement number, tag (and name), face number, a sample pixel, the visible depth
and the largest depth error. Each view reports `tested_pixels`, `tested_background` and
`undecided_pixels`, so how much was checked is always visible, and, for entities,
`entity_pixels` (drawn with an entity's faces), `entity_pixels_tested` (of those, decided),
`entity_over_nearer_pixels` (wrong order: an entity drawn over a face truly in front of it) and
`over_entity_pixels` (something drawn over an entity truly in front of it). The summary's
`entity_views` adds these up over the views aimed at entities.

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
- The World Kit's example worlds built by `mei_world.py build` (palette swatch faces, regions,
  layers), checked through the build's gate in a trial merge: `test_room` 132 views (4.1
  million decided pixels) and `two_districts` 416 views (17 million), no coverage error. Before
  their ground was flagged, both had wrong-order pixels in the near band in about half their
  views (up to 24,000 pixels in one view): real mis-sorts, mostly between ground tiles and what
  stands on them and inside the shop asset, which report mode lists and strict mode would fail.
  See [Ground](#ground) for what ground-first drawing left.
- Coverage errors found three ways the runtime dropped faces that cross the near plane, all
  fixed (regression tests: `tests/lang/clip_near_drop.akr`, `tests/lang/vec_div_temp.akr` and
  `ViewTests.test_clipped_faces_are_not_dropped`):
  - the pieces of a clipped face were back-face culled again from their rounded screen
    corners; where clipping left two corners on one pixel, a quad piece's first triangle had no
    area and the whole quad was dropped (from eye (10.5278, 2.6406, 9.0798), yaw −2.9315597,
    pitch −0.8297644 in the demonstration world: a 5,179-pixel hole in the ground tile under
    the camera, closing when the camera moved 1/10,000 of a radian);
  - the clip-space back-face test overflowed 16.16 for large clip coordinates (the far pass,
    where the near plane is half a cell away, and large faces in the near pass), because the
    compiler returned `v / max(…)` unscaled when the divisor was a temporary (from
    (135.2339, 23.4188, 9.4824), yaw −131.8°, pitch −39.3°: a stand-in face missing at the
    screen's edge; a whole 32-unit floor from cameras low over it);
  - a quad whose fourth corner alone was behind the camera and whose other corners were outside
    the guard band was judged off the screen from that corner's mirrored projection.

  Random-camera sweeps (1,500 cameras a world, half of them within 3 units of the ground, over
  eight worlds: the demonstration, bench, plaza, near-plane, slope and ground worlds of the
  tests and the two example worlds; two seeds, 24,000 views, about 370 million decided pixels)
  found coverage errors in 253 views (1.1%) before the fixes: 231 from the overflow, 8 from
  the piece culling, 12 from the fourth corner, 1 needing two fixes. After them: one view,
  320 pixels in one row along the near-plane cut of a ground face seen from 0.07 units above it
  (`two_districts`, eye (68.5025, 0.0692, 9.7815), yaw 0.4216°, pitch −44.154°). With the eye
  closer to a surface than the near distance, that cut moves about 2,900 pixels per unit of
  the eye's height, so the 16.16 camera matrix and clipped corner put it a pixel or two off the
  reference's: a precision limit, not a dropped face. Coverage errors fail only in strict
  mode.

### Ground

A world pack 1.1 marks some placements as ground, and the reader draws them in a pass of their
own before the rest near the camera ([WORLDPACK.md](WORLDPACK.md), "Ground"). That order is the
design, not an error, so the reference reproduces it exactly: ground placements go into a ground
pass between the far and near passes, which keeps the same three per-pixel depths as the others.
A ground face is then the expected face only where no near-pass face may cover the pixel; where
one may, the near pass decides it alone, by true depth among its own faces, as the runtime does.
Among themselves, ground faces are judged by true depth like any other faces of one pass, so a
mis-sort inside the ground pass (a ground piece on the ground, the side of a ground slab over its
neighbour's top) is reported as wrong order. With the runtime setting `ground_first` false (a game
that turns `wp_ground_first` off) ground is ordinary near geometry, as in a 1.0 pack.

What the rule gets wrong is measured, not excused: a pixel drawn as the rule says (actual =
expected) where a ground face surely covers it at least `edge_margin` inside and is truly nearer
than the expected near-pass face by more than `depth_epsilon` plus the faces' non-planarity is a
**ground inversion**: the ground truly hides what was drawn over it (a crate sunk into the
ground, the feet of something beyond a crest). Like wrong-order pixels these are exact where they
are counted; pixels near outlines and depth ties are not. Each view reports
`ground_inversions` and, when there are any, `ground_issues`: witnesses grouped by (ground face,
the face drawn over it) with a sample pixel, the ground's depth and how far behind it the drawn
face lies. They count against `ground_inversion_pixels` (0 by default) in strict mode, and pick
diagnostic pictures like near wrong-order pixels.

The **static warnings** point at likely misuse before any view is drawn. A pair of instances
(placements and entity meshes within two cells of each other) is reported when a camera above an
upward ground face (its normal at least 10° above level) can see a face of the other through it:
part of the other face lies more than 1/64 unit behind the ground face's plane, part of the ground
face lies in front of the other face's plane, and those parts are within the near pass's reach of
each other. The camera then sits just above the ground face, on the line from the hidden point
through the ground, so such a camera always exists; whether the game ever puts one there is the
author's to judge, which is why these are warnings. `ground_hides` names geometry drawn after the
ground (what ground-first drawing would draw over it); `ground_over_ground` names ground that can
overlap ground (sorted inside the ground pass by average depth). Layers that can never be on
together are skipped. The sides and undersides of ground meshes are not counted as hiding: only
cameras below the ground's top see through them.

Evidence (`tests/test_worldverify.py`, `GroundStaticTests` and `GroundViewTests`):

- The planted mis-sort (strip over crate) with the strip flagged as ground: no wrong-order pixel,
  no coverage error and no ground inversion in strict mode; with `ground_first` false, the same
  pack is reported as before (strip over crate, near band).
- Not excused: the crate flagged as ground too (a raised ground piece) is reported as wrong order
  inside the ground pass and warned of as `ground_over_ground`; the crate sunk 0.3 units through
  the ground gives 188 ground inversions (ground strip over crate), a strict failure and a
  `ground_hides` warning.
- A valley (a flat and a ramp up from its edge, both ground, a building and a coin on the flat):
  76 sampled views, 2.7 million decided pixels, no wrong order, coverage error, ground inversion or
  warning. The same world with an upper floor past the ramp's crest and a box on it: ground
  inversions where the crest hides the box's bottom, and both warnings.

Measured on the example worlds (default settings; before: the same recipes without `ground`):

| | `test_room` before | after | `two_districts` before | after |
|---|---|---|---|---|
| views with wrong-order pixels in the near band | 69 of 132 | 9 | 160 of 416 | 111 |
| near-band wrong-order pixels | 153,444 | 2,775 | 365,309 | 318,722 |
| ... ground drawn over what stands on it | 150,459 | 0 | 45,739 | 0 |
| ... something drawn over the ground in front of it | 210 | 0 | 848 | 0 |
| ... ground over ground (slab sides at seams) | 0 | 0 | 10,018 | 10,018 |
| ... inside one asset (`canopy`; `shop`) | 2,775 | 2,775 | 308,704 | 308,704 |
| largest in one view | 13,715 | 575 | 24,008 | 24,008 |
| wrong-order pixels elsewhere (views) | 7,206 (30) | 0 | 20,154 (122) | 3,138 (68) |
| ground inversions, coverage errors | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| draw CPU cycles a view, mean (largest) | 27,413 (56,018) | 29,481 (58,086) | 35,706 (84,468) | 37,995 (86,763) |
| GPU cycles a view, mean (largest) | 116,229 (198,538) | the same | 138,636 (289,506) | the same |
| decided pixels | 4,120,595 | 4,113,056 | 17,054,981 | 17,041,425 |

The "before" column is the reader before ground existed; the 1.1 reader on the same packs
without ground measures 58 and 88 cycles a view more. Nothing got worse but the CPU cost of the
ground pass (about 2,000 cycles a view, 0.4% of the CPU's frame) and 0.1–0.2% fewer decided
pixels (a near-pass face that may cover a pixel now leaves it undecided even where the ground
under it is nearer, as the runtime draws it over the ground there). The `two_districts` largest
view is a mis-sort inside the shop (the body's top drawn over the roof slab sitting on it), which
no ground flag can change; its ground-over-ground pixels are the sides of the 0.5-unit ground
slabs, which the static check names as `ground_over_ground` and a ground tile modelled as a
surface would remove.

Both were then fixed in the examples' asset recipes (WORLDKIT.md, "Ground"): the ground tiles,
the room's floor and the far block's ground became upward quads; the shop became one shell whose
window, sign and roof edge are bands of its walls, with no faces inside it; the canopy's trim
became its roof's front and back edges. Measured the same way:

| | `test_room` with ground | remodelled | `two_districts` with ground | remodelled |
|---|---|---|---|---|
| views with wrong-order pixels in the near band | 9 of 132 | 0 | 111 of 416 | 19 |
| near-band wrong-order pixels | 2,775 | 0 | 318,722 | 348 |
| ... ground over ground; inside `shop`; inside `canopy` | 0; –; 2,775 | 0; –; 0 | 10,018; 308,346; – | 0; 0; – |
| ... inside `torii`; inside a merged mesh | – | – | 356; 2 | 346; 2 |
| largest in one view | 575 | 0 | 24,008 | 60 |
| wrong-order pixels elsewhere (views) | 0 | 0 | 3,138 (68) | 120 (10) |
| static warnings | none | none | `ground_over_ground` | none |
| draw CPU cycles a view, mean (largest) | 29,481 (58,086) | 25,041 (40,573) | 37,995 (86,763) | 30,938 (73,922) |
| GPU cycles a view, mean (largest) | 116,229 (198,538) | 115,964 (197,952) | 138,636 (289,506) | 133,183 (265,088) |
| decided pixels | 4,113,056 | 4,113,702 | 17,041,425 | 16,975,729 |

The shop and the canopy now pass the Asset Checker with no wrong pixel (`mei_assets.py verify`,
default profile; before: 39,143 and 7,493 wrong pixels and four coplanar overlaps each). What is
left in `two_districts` is inside the torii (its tie passes through its posts, which the Asset
Checker reports as surface intersections; not yet remodelled) and 2 pixels inside the merged
bollards.

### Entities

Cameras aimed at entities (`sampling.entities`) look at what the other kinds pass by: a coin on a
ledge is a few pixels from a camera at eye height 16 units away, and none of the sampled cameras
was close above it. The verification cart draws the entities as the game draws them, through
`wp_draw_entities()` ([WORLDPACK.md](WORLDPACK.md), "Objects"): each culled by the sphere of its
mesh's bounds, keyed at its nearest point and, from above its base, 1.5 units nearer. The
reference models what changes the picture's coverage exactly: an entity whose sphere is culled
is not drawn, and one within 1/64 unit of a plane is "unsure" (its faces may cover pixels but are
never expected), as for placements. The key and the bias change only the order, and the
reference's expected face is the truly nearest one, so the rule's intended effect (an object in
front of the platform under it) is correct by true depth and is not reported, while everything
it gets wrong is: an entity drawn over a face truly in front of it (a thin wall just in front)
and a face drawn over an entity (a platform top too large for the bias) are wrong-order pixels,
near by definition (either face is an entity's), and counted apart in each view.

Evidence (`tests/test_worldverify.py`, `EntityViewTests`; worlds in `tests/worldverify/worlds.py`):

- `ledge_world()`, test_room's ledge and coin alone, drawn with `mesh_at`: the default sampling
  without entity cameras (44 views) reports nothing; with them (66 cameras aimed at the coin), 8
  views and 3,808 pixels of the ledge's top over the coin. Drawn with `wp_draw_entities()`, the
  same cameras find nothing.
- `object_world()`: the cases WORLDPACK.md's "Objects" claims are handled come back clean (a coin
  on a 4 × 4 platform, two coins 0.5 apart, a coin under a slab), and the ones it does not handle
  are reported: a coin on a 12 × 12 platform still overdrawn (less than with `mesh_at`), a coin
  0.3 behind a thin wall drawn over it.

Measured on the example worlds, default settings, before (the sampling without entity cameras,
`test_room`'s coin as it was, entities drawn with `mesh_at()`) and after (the coin remodelled,
[WORLDKIT.md](WORLDKIT.md), and drawn with `wp_draw_entities()`):

| | `test_room` before | entity cameras, coin and drawing as before | after | `two_districts` before | after |
|---|---|---|---|---|---|
| views (of them aimed at entities) | 132 | 333 (201) | 333 (201) | 416 | 416 (0) |
| views with wrong-order pixels in the near band | 0 | 21 | 0 | 19 | 19 |
| near-band wrong-order pixels | 0 | 14,466 (all ledge over coin) | 0 | 348 | 348 |
| entity pixels drawn, decided | – | 203,244, 116,970 (57.5%) | 223,890, 134,394 (60.0%) | – | – |
| undecided pixels in the entity views | – | 619,473 | 616,218 | – | – |
| the check's time (seconds) | 1.4 | 4.7 | 4.3 | 6.3 | 6.6 |

`two_districts`' coins have no mesh, so it has no entity cameras; its 19 views are the torii and
the bollards, as before ([Ground](#ground)). The remodelled coin drawn with `mesh_at()` still
gives 24 views and 12,981 pixels: the coin's fault and the drawing's were separate.

**Undecided pixels.** The views aimed at entities leave about 3,100 pixels a view undecided,
against about 1,900 in the other kinds, and 40% of the entities' own pixels. At one camera that
sees the coin edge on (eye (23.17, 3.2, 38.83), yaw 135°, pitch −10°), 3,570 of the view's 4,364
undecided pixels are within `edge_margin` of a face's outline, 659 are where the nearest face is
a thin one (never expected) and 135 near another face's outline; none are depth ties. The coin
is small (15 to 200 pixels across), its 0.08-unit rim is a band of thin faces seen from the side,
and its old caps were fans from one rim vertex, all slivers: 24 of its 30 faces in view there
could not be expected, and 200 of its 522 pixels were decided. The remodelled coin's caps fan
from their centres (204 of 567 there; 57.5% to 60.0% over all the entity views).

Whether that hides errors: a mis-sort draws the wrong face over the whole overlap of the two
faces, so it is missed only when that overlap lies within about a pixel of outlines. Rerun with
`edge_margin` 0.5 (exploratory), the 201 entity views of `test_room` before give 27 views and
17,244 wrong pixels instead of 21 and 14,466, and 123 coverage errors that are the runtime's
rounding (the reason the margin is 1): about one erring view in five had its error only in
pixels the margin leaves undecided. The entity cameras at 1.5 units make the object large enough
on screen that a sort error there shows in decided pixels; a game whose objects are smaller than
the coin, or seen only from afar, has that much less checked.

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
| `test_room` / `two_districts` examples, default settings (333 / 416 views; before the cameras aimed at entities, 132 / 416: 1.4 / 6.3 on the same machine) | 4.3 / 6.6 |

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
