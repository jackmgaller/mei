# Working on Mei

A guide for people and AI agents working in this repository. What Mei is, how to run it and
what its parts are called is in [docs/OVERVIEW.md](docs/OVERVIEW.md); the documents are listed
in [README.md](README.md#documentation).

## Folders

| Folder | What is in it |
|---|---|
| `src/` | The emulator core (`core/`), the platforms (`platform/`: SDL3, browser, headless), the assembler (`asm/`) and the Akari compiler (`lang/`: lexer, parser, type checker `check.c`, optimiser `opt.c`, code generator `gen.c`), in C |
| `stdlib/` | Akari's standard library, compiled into every cart |
| `system/` | The system ROM: boot themes (`boot/`) and the shell (`shell/`), in Akari |
| `carts/` | The carts, one folder each (`carts/NAME/NAME.akr`), with their binary assets in `art/` and `audio/`, their tests in `tests/`, and the worlds they use in `worlds.txt` |
| `examples/` | Example recipes for the kits: `assets/` (Asset Kit) and `worlds/` (World Kit) |
| `tests/` | C unit tests (`test_*.c`), language tests (`lang/`), the kits' Python suites (`test_*.py`) and their fixtures, the Reference Renderer (`reference_renderer/`), the depth mode's measurements (`depth/`) |
| `tools/` | Generators, the kits and their shared core, the MeiNet gateway, the workboard, the language fuzzer, the web cart packer, the VS Code extension |
| `web/` | The browser page (`shell.html`) |
| `docs/` | The documentation and the spec |

## Building and testing

```sh
make                              # emulator, tools, probes, system ROM and carts in build/
make test                         # C, language, (with python3) Python suites, check-generated
make check-generated              # the generated files match what their generators make now
make test-assets                  # the Asset Kit suite alone, verbose
make test-world                   # the World Kit and Mochi suites alone, verbose
make test-carts                   # the carts' self-checking scenarios, then test-world-carts
make test-world-carts             # World Viewer's scripted run and tests/world_carts.sh
make rendercheck                  # the Reference Renderer (about a minute; NumPy and Pillow)
make rendercheck-motion           # the Reference Renderer's checks over time
make web                          # the WebAssembly build in build/web (needs Emscripten)
tests/run_lang_tests.sh planes    # only the language tests whose name contains "planes"
```

`make test` runs the suites in this order: the C unit tests, `tests/run_lang_tests.sh`, the
MeiNet gateway's tests, then `test_assetkit.py`, `test_worldpack.py`, `test_worldkit.py`,
`test_mochi.py`, `test_worldverify.py`, `test_worldcache.py` and `test_workboard.py`, and last
`tools/check_generated.sh` (what `make check-generated` runs: the generators that need only the standard library, and
`gen_adpcm_vectors.py` when NumPy is there, into a temporary directory, compared with the
committed files). `make test-carts` runs `carts/lantern/tests/check.sh`,
`carts/weather/tests/check.sh` and `test-world-carts`, which builds World Viewer and the
movement garden (and so their worlds) first and runs both carts' `tests/check.sh`. A cart's scenarios are Akari files built by `tools/cart_scenario.sh` from
the cart's `tests/harness.akr` and its game; `carts/*/tests/run.sh SCENARIO FRAMES OUT` runs one
and writes `OUT.png`.

A single Python suite, with the native tools it needs:

```sh
make build/meic build/mei-headless build/mei-asset-probe build/mei-scene-probe
python3 -m unittest discover -s tests -p test_worldpack.py -v
python3 tools/meinet/test_meinet.py
```

The suites find the native tools in `build/` unless `MEIC`, `RUN`, `PROBE` (the asset probe) and
`SCENE_PROBE` point elsewhere; `tests/run_lang_tests.sh` reads `MEIC` and `RUN` the same way.
In the Python suites, tests that need a native tool that is not built, or NumPy, are skipped
rather than failed.

**Use a private build directory** when you are not the only one working in the checkout:
`make B=build-mine test` builds everything into `build-mine/` (ignored by git, like `build/`).
Pass the tools to scripts the same way, for example
`MEIC=build-mine/meic RUN=build-mine/mei-headless tests/run_lang_tests.sh planes`. The Asset
Kit's `verify`, `preview` and `build` take `--build-dir build-mine`, or read `B=build-mine` (or
`MEIC`, `RUN` and `PROBE`) from the environment
([ASSETKIT.md](docs/ASSETKIT.md#native-tools)):
`python3 tools/mei_assets.py preview model.asset.json -o build-mine/assets/model --build-dir build-mine --closeups`.

Mei Demo, Sound Lab and World Viewer are built only on request (`make build/carts/demo.mei
build/carts/soundlab.mei build/carts/worldview.mei`); `make` and `make web` leave them out. The
movement garden is built by `make`, which therefore needs NumPy for its worlds, and Pillow for
the shrine world's textures (`carts/garden/shrine`, whose assets read PNG sheets).
The Reference Renderer
([tests/reference_renderer/README.md](tests/reference_renderer/README.md)) builds its carts,
probes and reports into `$(B)/reference_renderer/` on each run; `make test` runs its two
quickest checks, the stress scene and subdivision, when NumPy and Pillow are installed.

**Carts that use worlds.** A cart lists World Kit recipes in `carts/NAME/worlds.txt`, one
repository path per line. make builds each recipe once into `build/worlds/<its folder>/`
(`tools/world_cart.py build`, which runs `mei_world.py build` with the full World Checker and
needs NumPy), links the cart's worlds and their games' `GAME.game.akr` into
`build/cart-worlds/NAME/` and compiles the cart with `meic -I build/cart-worlds/NAME`. `meic -I
DIR` (repeatable) names a directory searched for imports after the importing file's own folder
and before the standard library. [WORLDKIT.md](docs/WORLDKIT.md#using-a-world-in-a-cart) has the
details; `carts/worldview/` is the example.

**Quick feedback while placing assets in a world** (plain text; `--json` for JSON):

```sh
python3 tools/mei_assets.py info RECIPE [--at X,Y,Z --yaw DEG]     # bounds, LOD, texture bytes
python3 tools/mei_assets.py floors RECIPE [--step 0.25]             # collision floor heights
python3 tools/mei_world.py check WORLD --cells I,J --camera NAME=EX,EY,EZ@YAW,PITCH --build-dir build-mine
python3 tools/mei_world.py floors WORLD --area X0,Z0,X1,Z1 --build-dir build-mine
python3 tools/mei_world.py textures WORLD [--cells I,J] --build-dir build-mine
```

The world commands keep the compiled world in `BUILD_DIR/kit-cache/quick/` and reuse it while
nothing it read has changed ([WORLDKIT.md](docs/WORLDKIT.md#quick-tools)).

## Dependencies

- A C compiler and SDL3 (`brew install sdl3`). Optional: libusb (`brew install libusb`) for
  XInput pads on macOS, and Emscripten (`brew install emscripten`) for `make web`.
- Python 3 for the tools and the Python suites; the kits need 3.10 or later. With nothing but
  the standard library: the Asset Kit and World Kit (building recipes), the world pack encoder,
  the MeiNet gateway and its tests, the web cart packer, and the generators `gen_stdlib_data`,
  `gen_faces_asm`, `gen_reverb_tables`, `gen_demo_assets` and `gen_weather_tape`.
- **NumPy** for the Asset Checker (`mei_assets.py verify`) and the World Checker, and so for
  building a cart that uses worlds (Movement Garden, World Viewer), so for `make`, and for `make
  test-carts`; and for every other
  generator. **NumPy and Pillow** for the Reference Renderer. **Pillow** too for the generators
  that draw: `gen_boot_duet`, `gen_boot_eclipse`, `gen_shell_assets`, `gen_lantern_assets`,
  `gen_orbs_assets`, `gen_weather_assets` and `meifont`, and for the Asset Kit's textures read
  from PNG images and sheets (`examples/assets/stall`, the shrine world's assets, so `make`;
  recipes without images need it not).
  **SciPy** too for `gen_boot_duet`, `gen_soundlab_assets` and the garden's audio generators
  (`carts/garden/audio/gen_sounds.py`, `gen_music.py`).
- Several generators draw with macOS system fonts (Avenir Next, Hiragino, Georgia, Optima and
  others). Their outputs are committed, so building and running Mei needs none of this.

## Reporting status

Agents working in a worktree report to the workboard ([tools/workboard/README.md](tools/workboard/README.md);
`python3 tools/workboard/serve.py`, then http://127.0.0.1:8770/). It infers branches, commits,
uncommitted files and Asset Kit and World Kit reports by itself; what it cannot see is the
model, the current step, the items planned and the questions. The orchestrator creates the
record when it starts an agent and gives it the ID:

```sh
python3 tools/work_status.py new ID --title "Plaza props" --kind asset --model sonnet --lead LEAD --branch BRANCH
```

The agent, from its worktree (branch and worktree are filled in from there):

```sh
python3 tools/work_status.py set ID --state working --step "LOD pass" --percent 60   # at each step
python3 tools/work_status.py item ID bench --state done --size small                  # each item
python3 tools/work_status.py ask ID "Red or blue awning?"                             # then carry on
python3 tools/work_status.py done ID --note "3 assets, all verified"                  # or review, block ID "why", stop
```

Call `set` when the step changes, not on a timer; a card with nothing new for 20 minutes is
marked stale. `show ID` prints the record with any answers. Records live in `.git/mei-work/`
(or `$MEI_WORK_DIR`), never in the checkout.

## Rules

- **Never hand-edit a generated file.** Change its generator and run it. Generated files say so
  in their first line (`// Generated by tools/... - do not edit.`), and the table below lists
  them.
- **Existing cart ROMs must stay byte-identical** through a refactor of the compiler, the
  standard library or the tools. It is the standard regression check: build the untouched tree
  and your change into two build directories and `cmp` every `carts/*.mei` (and `system.mei`,
  unless you meant to change the system ROM).
- **Commit subjects are plain descriptions** of the change, optionally with the area first:
  "World Kit: run the World Checker from build", "Rename the spec PDF to docs/spec-v0.1.pdf".
- **Docs are plain and specific:** what exists, with its numbers, file names and commands; what
  is planned is marked as such. No marketing tone. Lines wrap at about 100 columns. Check a fact
  against the code before writing it down, and run a command before documenting it.
- **Build into a private directory** (`make B=...`) rather than `build/` when other people or
  agents may be building too.
- **Commit an asset's generator with the asset.** When a script writes a lab or example asset's
  recipe or draws its art (a recipe writer, a texture or sheet drawer), commit it in the asset's
  own folder beside what it writes, and add it to the Generators table below, so the asset can
  be regenerated. A recipe or PNG without its script cannot be changed except by hand.

## Where new things go

- **Python packages** in subfolders of `tools/` (`tools/assetkit/`, `tools/worldkit/`,
  `tools/kitcore/` for what the kits share, `tools/meinet/`).
- **A kit's entry point** at the top of `tools/` (`tools/mei_assets.py`, `tools/mei_world.py`).
- **Native probes** with their package (`tools/worldkit/scene_probe.c`), built by a `Makefile`
  rule into the build directory. (`tools/assetkit_probe.c` predates this.)
- **Standard library functions** in the `stdlib/` file for their topic, by the table at the top
  of [LANGUAGE.md's Standard library](docs/LANGUAGE.md#standard-library).
- **A test suite with its own scripts and probes** in a folder of `tests/`
  (`tests/reference_renderer/`), with one README; the carts and data it generates are built
  into the build directory, not committed.
- **Example worlds** in `examples/worlds/NAME/`, example assets in `examples/assets/`.
- **Generated world packs are built into `build/` and not committed.** The recipes, and each
  world's ID lock file (`NAME.ids.json`), are the source.
- **A cart that uses worlds** lists their recipes in `carts/NAME/worlds.txt` and imports
  `WORLD.akr` by name; make builds the worlds into `build/worlds/` and passes them to meic
  with `-I` ([WORLDKIT.md](docs/WORLDKIT.md#using-a-world-in-a-cart); `carts/worldview/` is
  the example).
- **A cart's assets:** binaries in the cart's `art/` (meshes, textures, palettes, icons) and
  `audio/` (sounds, music) folders, and generated `.akr` files at the top of the cart folder.
  Every cart is laid out this way, and the existing carts commit their generated assets.
- **A cart's tests** in `carts/NAME/tests/`: a `harness.akr` with the scenarios, a `run.sh` that
  calls `tools/cart_scenario.sh`, and a `check.sh` that `make test-carts` runs.
- **Machine constants** come from the core's headers, not from new numbers: the memory map
  (`MEI_ROM_BASE`, `MEI_RAM_SIZE`, `MEI_RAM_USER_BASE`, `MEI_IO_BASE`, `MEI_VRAM_BASE`,
  `MEI_VRAM_SIZE`), the cart header layout (`MEI_HDR_*`) and the frame budgets in
  `src/core/mei.h`; VRAM's layout (`TEXTURE_ADDR`, `TEXTURE_SLOTS`, `PALETTE_HI_ADDR`, ...) in
  `src/core/machine.h`; the 18-bit immediate range (`MEI_IMM_MIN`, `MEI_IMM_MAX`,
  `MEI_UIMM_MAX`) and the instruction encodings in `src/core/isa.h`.
- **Compiler passes:** the AST optimisations (inlining, let forwarding, induction pointers) are
  in `src/lang/opt.c`, run by `opt_program()` between type checking and code generation.

## Generators

Run each as `python3 tools/NAME.py`; they find the repository from their own path. Five take
`--preview DIR` to write pictures or WAVs for review (`gen_boot_eclipse`, `gen_shell_assets`,
`gen_shell_music`, `gen_weather_assets`, `gen_weather_audio`). The outputs are committed.

| Generator | Writes |
|---|---|
| `gen_stdlib_data.py` | `stdlib/font_data.akr` (the 8×8 font as a texture), `stdlib/sin_table.akr` |
| `gen_faces_asm.py` | `stdlib/faces.akr` (`mesh()`'s face loops); with `--planes`, `stdlib/planes_faces.akr`; with `--depth`, `stdlib/depth_faces.akr` |
| `meifont.py` | Proportional fonts: `stdlib/font_small.akr` (the command is in its first line); Mei Weather's fonts through `gen_weather_assets.py` |
| `gen_reverb_tables.py` | The reverb preset table in `src/core/audio.c`, between its `BEGIN`/`END generated` markers |
| `gen_adpcm_vectors.py` | `tests/adpcm_vectors.h`, reference vectors for `tests/test_audio.c` |
| `gen_boot_duet.py` | `system/boot/duet/`: the atlas, palette and audio stems of the Duet boot theme |
| `gen_boot_eclipse.py` | `system/boot/eclipse/`: textures, palette, sound, volumes and `gen.akr` for Eclipse |
| `gen_shell_assets.py` | `system/shell/`: font and art textures, palettes, glyph metrics, UI sounds (`snd_*.raw`), `wave.raw` and `assets.akr` |
| `gen_shell_music.py` | `system/shell/mu_crystal.adp` (samples) and `system/shell/mu_data.akr` (the score) |
| `gen_demo_assets.py` | `carts/demo/art/`: a cube, a ground mesh, a texture and its palette |
| `gen_lantern_assets.py` | `carts/lantern/art/` and `carts/lantern/assets.akr`; then runs `gen_lantern_audio.py` |
| `gen_lantern_audio.py` | `carts/lantern/audio/` |
| `gen_orbs_assets.py` | `carts/orbs/art/` (meshes, textures, palettes, the save icon), `carts/orbs/audio/` (sounds, music) and `carts/orbs/level_data.akr` |
| `gen_soundlab_assets.py` | `carts/soundlab/audio/` (clips, PCM and ADPCM) and `carts/soundlab/assets.akr` |
| `gen_weather_assets.py` | `carts/weather/art/` and `carts/weather/art.akr` |
| `gen_weather_audio.py` | `carts/weather/audio/` and `carts/weather/mu_data.akr` |
| `gen_weather_tape.py` | `carts/weather/demo_tape.bin`, Mei Weather's sample broadcast |
| `meinet/make_fixture.sh` | `tests/lang/data/broadcast.bin`, the canned broadcast the language tests replay (`meinet.py --fixture`) |
| `carts/garden/shrinetown/art/water/draw_water.py` | The shrine town's water textures in `art/water/`: `water.png`, `pond_water.png`, `falls.png`, `water_ramps.akr` |
| `carts/garden/shrinetown/art/backdrop/draw_backdrop.py` | The shrine town's backdrops in `art/backdrop/`: `town_backdrop.png`, `shrine_backdrop.png`, `backdrop.json` |
| `carts/garden/shrinetown/art/ground/draw_ground.py` | The shrine town's ground textures in `art/ground/` (`--preview DIR`: a contact sheet) |
| `carts/garden/shrinetown/art/plain/draw_plain.py` | The shrine town's far plain in `art/plain/`: `plain.png`, `plain_atlas.bin`, `plain_map.bin`, `plain_data.akr` |
| `carts/garden/shrinetown/assets/edge_neighbour/make_edge_neighbour.py` | The neighbours' backs: `art/facade_a.png`, `art/facade_b.png` and the `edge_neighbour_*` recipes |
| `carts/garden/shrinetown/assets/edge_hoarding/make_edge_hoarding.py` | The road-works hoarding: `art/panel.png`, `art/sign.png`, `edge_hoarding.asset.json`; the edge fences, `edge_fence_*.asset.json` |
| `carts/garden/shrinetown/assets/viaduct_end_wall/make_viaduct_end_wall.py` | The viaduct's end wall: `viaduct_end_wall.asset.json` |
| `carts/garden/shrinetown/assets/edge_rock/make_edge_rock.py` | The frame's rock walls on the rims: `edge_rock_*.asset.json` (their table from `tools/frame.py --rocks`) |
| `carts/garden/shrinetown/tools/frame.py --build-dir B --probes` | `carts/garden/tests/frame_probes.akr`, the frame scenarios' probes, from the built world (NumPy) |
| `carts/garden/audio/gen_sounds.py` | The movement garden's sounds (the robot, the goals, the shrine town's beds, emitters, timers and life) in `carts/garden/audio/sounds.adp`, and `sound_data.akr`: the sounds' table and the zones, emitters and timers (`--preview DIR`: a WAV of every sound) |
| `carts/garden/audio/gen_music.py` | "Momiji", the shrine town's music: `carts/garden/audio/music.adp` and `music_data.akr` (`--preview DIR`: a WAV of every sample) |

The last twelve are run by their path from the repository root, not as `tools/NAME.py`; the
garden's two audio generators share `carts/garden/audio/garden_dsp.py`, which writes nothing.

Helpers the generators import, which write nothing themselves: `boot_audio.py`, `mei_adpcm.py`,
`mei_icon.py` (memory card icons), `meshlib.py` (the native mesh format) and `weather_geo.py`.
The kits' outputs (`mei_assets.py build`, `mei_world.py build`) are not in this table: they go
wherever `-o` says (make's world rule: `build/worlds/`), and only the examples' recipes and the
worlds' ID lock files are committed. `make check-generated` reruns `gen_faces_asm.py` (all three
outputs), `gen_stdlib_data.py`, `gen_reverb_tables.py` and, with NumPy, `gen_adpcm_vectors.py`
and compares; the others are not rerun by any target.
