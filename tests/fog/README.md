# Fog toward a colour: measurements

`shrinetown.py` measures the GPU's fog toward a colour ([DECISIONS.md](../../docs/DECISIONS.md#fog-toward-a-colour))
on the Movement Garden's shrine town. Each view is a small cart built on the fly: the world drawn
by the real reader in depth mode (`render_depth(true)`, `render_perspective(true)`, as the garden
draws it), its entities and the region's backdrop, in the day or night palette variant, once
without fog and once with `gpu_fog()`. The garden cart and the shrine town's recipe are not
changed.

```sh
make B=$B $B/carts/garden.mei                     # builds the shrine town's world into $B
B=$B python3 tests/fog/shrinetown.py              # the shots below, into $B/fog_shots
B=$B python3 tests/fog/shrinetown.py -o $B/fog_views views   # the World Checker's 21 worst views
```

It writes `NAME.png` (without fog on the left, with it on the right, at twice the size),
`NAME_off.png`, `NAME_on.png` and `table.md`: each view's triangles, CPU and GPU cycles of its
fourth frame both ways, and the fogged triangles and pixels (`mei-headless --gpu-stats` columns
`tris_fog`, `px_fog`). `--day` and `--night` take `COLOUR,NEAR,FAR` (defaults `#c8c8b4,40,220`
and `#141826,16,140`). Needs Pillow.

`shots/` holds the pictures the proposal was written from (the defaults, 2026-10-05).

The C unit tests in `tests/test_gpu.c` (`test_fog_*`) check the registers, the factor, the blend
and the cost against a reference; `tests/lang/gpu_fog.akr` the standard library's `gpu_fog()`;
`tests/test_worldkit.py` (`test_fog_per_variant_on_the_console`) a world's fog per variant.
