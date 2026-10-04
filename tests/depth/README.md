# Depth mode measurements

`garden.sh` runs one of the Movement Garden's scripted scenarios (`carts/garden/tests/harness.akr`)
with `stdlib/depth.akr` in one of four modes and writes per-frame GPU and CPU statistics
(`mei-headless --gpu-stats`), the log and the last picture. The garden cart itself is not
changed: the mode is set from the scenario cart's head.

| Mode | What |
|---|---|
| `ot` | the garden as it is: the ordering table |
| `z` | `render_depth(true)` and `render_perspective(true)`: opaque faces nearest first |
| `zb2f` | the same with the opaque faces put in the back-to-front table, among the semi-transparent ones (the ordering table's order): for comparison only |
| `zonly` | `render_depth(true)` alone (the same packets as `z`: with the test on, textures are perspective-correct anyway) |

```sh
make build/carts/garden.mei                       # builds the garden's world into build/
tests/depth/garden.sh z 27 600 /tmp/z27           # the tour of the park
tests/depth/garden.sh ot 29 300 /tmp/ot29         # the kick alley
python3 tools/mei_gpustats.py /tmp/z27.csv /tmp/ot29.csv
```

`MEIC`, `RUN` and `WORLDS` select other builds, as for `carts/garden/tests/run.sh`. The figures in
[LANGUAGE.md](../../docs/LANGUAGE.md#the-depth-buffer-and-perspective-depthakr) and
[WORLDPACK.md](../../docs/WORLDPACK.md#the-console-reader-stdlibworldpackakr) come from scenarios
27 (600 frames), 29 (300) and 30 (510) in modes `ot`, `zb2f` and `z`; `mei_gpustats.py` skips each
run's first 30 frames.

The language tests `tests/lang/depth_*.akr` check the API, the order and the packets.
