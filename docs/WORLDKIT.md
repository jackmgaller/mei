# Mei World Kit

The World Kit is a command-line tool for AI agents, a sibling of the Asset Kit. An editable JSON
recipe places Asset Kit assets into cells and regions, attaches game data to them, and builds one
native world pack that a cart embeds. The World Checker samples cameras through the playable
space and reports budget overruns, face-ordering errors and holes in collision (report-only
unless the recipe says otherwise; see [Verification](WORLDKIT-REFERENCE.md#verification)). The Asset
Kit's own verification gate is the **Asset Checker** (`mei_assets.py verify`).

The entry point is `tools/mei_world.py`; the code is `tools/worldkit/`, with what it shares with
the Asset Kit in `tools/kitcore/`. Building recipes needs Python 3.10 or later and nothing else;
the Asset and World Checkers, which every build runs, need NumPy and the native tools (`meic`,
`mei-headless`, `mei-asset-probe`, `mei-scene-probe`, built by `make`).

This is the guide: what the kit does, its conventions, the edit, check and preview loop, the
commands and where to look next. The rest is in other files:

| Document | What is in it |
|---|---|
| [WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md) | The reference: every recipe field (regions, palettes, textures, backdrops, levels of detail, haze, quads, paths, ground, depth mode), terrain, stand-ins and occlusion, ROM and VRAM, the game schema (Mochi) and the ID lock file, collision, the outputs, verification, every command's options and using a world in a cart |
| [WORLDPACK.md](WORLDPACK.md) | The pack format (normative, version 1.5) and the console reader, `stdlib/worldpack.akr` |
| [WORLDCHECKER.md](WORLDCHECKER.md) | The World Checker: what fails in each mode, its settings and defaults, the static collision checks, how views are sampled |
| [WORLDKIT-DESIGN.md](WORLDKIT-DESIGN.md) | The project owner's decisions and their reasons, the proposals not built, open questions and the build order |
| [ASSETKIT.md](ASSETKIT.md) | The Asset Kit, which makes every asset a world places |

## Status

Built: the recipe format (cells, regions and palette variants, layers, ground, merged scatter,
paths, levels of detail, collision, game data in Mochi or JSON, the ID lock file); terrain
(ground heightfields with cliffs and water, profiles swept along paths, draped paths, things set
on the ground, scatter, textured terrain); textures per region with night variants and animated
textures; backdrops on the plane chip; stand-ins made by the kit, haze, quads and occlusion zones;
the World Checker, which every build runs; the quick tools; the pack format, version 1.5, with its
reference encoder `tools/worldkit/pack.py` and the console reader; five example worlds in
`examples/worlds/`; and make's rule for [a cart that uses worlds](#using-a-world-in-a-cart), with
World Viewer (`carts/worldview/`) as its example. The movement garden (`carts/garden/`) runs on a
World Kit world, the shrine town.

Not built yet: audio banks (a region's `audio` is reserved and rejected) and spreading a region
swap over a seam ([Region seams](WORLDKIT-REFERENCE.md#region-seams)). The proposals and open
questions are in [WORLDKIT-DESIGN.md](WORLDKIT-DESIGN.md#proposals-not-built).

## Concepts

| Thing | What it is | Owns |
|---|---|---|
| **World** | One pack: a set of cells and an index. A city, a mall, a test room, a course | regions, cells, the ID lock file |
| **Region** | A district whose cells share one set of resources | texture set, palette variants, audio bank (planned), backdrop |
| **Cell** | A self-contained square of the world | placements, layers, collision, entities, a stand-in |
| **Placement** | One asset at a position and yaw, with a stable ID | an asset reference, an optional layer |
| **Layer** | A named group of placements and entities in one cell that the game switches on and off | nothing else; the kit only knows it exists |
| **Entity** | Game data: a type, a stable ID, a position and parameters | an optional asset to draw, an optional layer |
| **Palette variant** | A named full set of a region's palette colours (`day`, `night`, …) | colours |
| **Stand-in** | A cheap low-detail mesh drawn for a cell when it is far away | an asset reference |

A discrete level is a world with one cell, or with every cell always active; an interior is a
world of its own, reached through a door, which is an entity whose game type carries a world
reference.

## Conventions

- **Could you place it twice?** Anything reusable (a staircase, a vending machine, a length of
  guard rail, a building) is an Asset Kit asset. Anything that exists once, at one place in the
  world, belongs to the world recipe: placements, game data, collision choices and terrain.
  World recipes do no other modelling: every triangle but terrain's comes from an asset recipe.
- **No game rules.** The kit does not know what a coin, a switch, a door or night is. The game
  defines its entity types and their parameters in a game schema; the kit validates against it,
  packs the data and checks that references resolve.
- **Recipes** follow the Asset Kit's conventions: `format` and `version`, names matching
  `^[a-z][a-z0-9_]{0,47}$`, unknown properties and duplicate keys are errors, and errors carry a
  JSON Pointer `path` and a `message` (with `file`, and `line` and `column` in a Mochi file). There
  are no expressions or random generation (scatter is seeded). Y is up, lengths are world units,
  one unit per metre by convention, and angles are degrees. `schema` is the authoritative
  contract.
- **Files.** A world is a world file (`NAME.world.json`), one file per cell (`*.cell.json` in
  `cell_dir`; a one-cell world may keep it inline), a game schema (`GAME.game.mochi`, or JSON) and
  one or more directories of Asset Kit recipes. An agent editing one cell edits one file.
- **Every placement says what it collides with**: `"collision": "self"` (the asset's own mesh),
  `"none"`, or a companion collision asset, usually simpler than what is drawn.
- **Stable IDs.** Entity IDs are world-wide and address a player's save. The kit keeps
  `NAME.ids.json` beside the world file, mapping each saved entity to its bit, append-only;
  commit it with the recipe. A rename keeps its bit with `"was": "old_id"`.
- **Assets are built from their recipes.** A world build compiles every asset it places and runs
  each one's required Asset Checker policy; a world never trusts a stale `.bin`.
- **Packs are build outputs.** World packs go into the build directory (`build/worlds/`) and are
  not committed; the recipes and the ID lock file are the source.
- **Depth mode.** A game that draws with the depth buffer says `"runtime": {"depth": true,
  "perspective": true}` in the world file, and its assets and the world are checked so
  ([Depth mode](WORLDKIT-REFERENCE.md#depth-mode)).

## A world and its cells

The world file of the two-district example (`examples/worlds/two_districts`, abridged):

```json
{
  "format": "mei-world", "version": 1, "name": "two_districts",
  "game": "city.game.mochi", "assets": "assets", "cell_dir": "cells",
  "grid": {"cell_size": 32},
  "collision": {"surfaces": {"default": 0, "tags": {"ground": 1, "wall": 3, "roof": 4}}},
  "regions": {
    "downtown": {"variants": {"day": {}, "night": {"surface": {"multiply": "#506090"},
                                                   "colors": {"shop.window": "#fff0b0"}}}},
    "shrine": {"variants": {"day": {}, "night": {"surface": {"multiply": "#405080"}}}}},
  "layers": {"festival": {}}
}
```

and one of its cells, `cells/downtown_b.cell.json`:

```json
{
  "format": "mei-world-cell", "version": 1,
  "id": "downtown_b", "at": [1, 0], "region": "downtown", "standin": "block_far",
  "placements": [
    {"id": "ground", "asset": "ground_tile", "position": [48, 0, 16], "ground": true,
     "collision": "self"},
    {"id": "shop_1", "asset": "shop", "position": [48, 0, 20], "yaw": 90, "collision": "shop_col"}
  ],
  "entities": [
    {"id": "coin_b", "type": "coin", "position": [40, 1, 8]},
    {"id": "night_switch", "type": "switch", "position": [56, 0, 8],
     "params": {"target": "coin_far", "time_window": "night"}}
  ]
}
```

Every property of both files is in [Recipe format](WORLDKIT-REFERENCE.md#recipe-format); the game
schema (`city.game.mochi`) is in [Game data and stable
IDs](WORLDKIT-REFERENCE.md#game-data-and-stable-ids).

## The loop: edit, check, preview

With a private build directory (`make B=build-mine build-mine/meic build-mine/mei-headless
build-mine/mei-asset-probe build-mine/mei-scene-probe` once):

```sh
python3 tools/mei_world.py schema --game examples/worlds/test_room/garden.game.mochi
python3 tools/mei_world.py init /tmp/room --example room           # or city, terrain
python3 tools/mei_world.py validate /tmp/room/test_room.world.json  # static checks, seconds
python3 tools/mei_world.py inspect /tmp/room/test_room.world.json   # the same, with every cost
python3 tools/mei_world.py preview /tmp/room/test_room.world.json -o build-mine/worlds/room \
    --compiler build-mine/meic --runner build-mine/mei-headless --probe build-mine/mei-asset-probe
```

1. **Edit** the world file, a cell file or an asset recipe. Build each new asset on its own with
   the Asset Kit first ([ASSETKIT.md](ASSETKIT.md)); `mei_assets.py info RECIPE --at X,Y,Z --yaw
   DEG` gives its bounds where you mean to place it, and `mei_assets.py floors RECIPE` its
   collision's floors.
2. **`validate`** until it passes: schemas, references, game data, IDs, palettes, that every
   asset compiles and that the pack can hold the world; it lists the ID changes a build would
   make. `inspect` adds the costs per cell and region.
3. **Place with the quick tools**, which work from a cached compile in seconds
   ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)): `floor` for the highest floor under a
   point, `floors` for the pack's floors over an area as the console finds them, `textures` for
   texture VRAM against a region's budget, `check` for the World Checker on a few cells and
   cameras, and `cracks` for every collision crack the game's floor query does not bridge.
4. **`build`** (or `preview`, which adds renders of a cell per region and palette variant). It
   runs every required Asset Checker policy and then the World Checker; read `report.json` and
   `verification/world-check.json` and the pictures of the worst views in `verification/`.
5. **Run it in a cart** ([below](#using-a-world-in-a-cart)), or fly through it in World Viewer.

[AGENTS.md](../AGENTS.md) lists the quick commands with `--build-dir`.

## Commands

Parallel to `mei_assets.py`: JSON on stdout for successes and failures (an error has `path`,
`message` and, as in [Recipe format](WORLDKIT-REFERENCE.md#recipe-format), `file`, `line` and
`column` where they apply), exit 0 or 1, `-` for stdin (relative paths then resolve from the
current directory), `--build-dir DIR` (or `--compiler`, `--runner` and `--probe`) to use other
builds, `--assets DIR` to use another asset directory, and for `build` and `preview`, `--cache DIR` to keep and reuse the
checkers' results ([Build outputs and the runtime
contract](WORLDKIT-REFERENCE.md#build-outputs-and-the-runtime-contract)). The quick tools
(`check`, `floors`, `textures`, `cracks`) print plain text; every command takes `--json`.

| Command | Result |
|---|---|
| `schema [--game FILE]` | The world recipe's JSON Schema (cell files and game schemas under `$defs`, Mochi under `$defs/game/x-mochi`), with the game's entity types (Mochi or JSON) folded in when given |
| `convert FILE [-o OUT] [--force]` | A game schema in the other form: JSON to canonical Mochi, or a `.mochi` file to JSON. Without `-o`, the result holds the `text` (Mochi) or `game` (JSON) |
| `init DIR [--example room\|city\|terrain] [--force]` | Copies an example world (world file, cells, game schema, asset recipes) into a new directory |
| `validate FILE` | Every static check: schemas, references, game data, IDs, palettes, that every asset compiles and that the pack can hold the world; the ID changes a build would make |
| `inspect FILE [--cell ID]` | The same, with the full report: per cell and per region costs, palettes and variants, entity numbers, asset hashes, warnings |
| `build FILE -o DIR [--locked] [--preview] [--world-checker full\|skip\|N] [--crack-baseline FILE\|none] [--build-dir DIR]` | The outputs ([Build outputs](WORLDKIT-REFERENCE.md#build-outputs-and-the-runtime-contract)); runs each asset's required Asset Checker policy, then the World Checker seam (with `NAME.cracks.json` beside the recipe as its crack baseline, when there is one) |
| `preview FILE -o DIR [--cell ID] [--locked] [--world-checker full\|skip\|N] [--build-dir DIR]` | `build`, plus native renders of a cell per region and palette variant (`--cell` picks the cell) |
| `check FILE [--cells I,J[;I,J...]] [--camera SPEC]... [--cameras FILE] [--max-views 200] [-o DIR]` | The World Checker on a few cells and cameras, in seconds ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `check FILE --full [--crack-baseline FILE\|none] [-o DIR]` | The World Checker on the whole world as `build` runs it, without building ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `check PACK.world.bin [--cells I,J] [--camera SPEC]... [--settings FILE] [--names FILE] [--strict] [-o DIR]` | The World Checker on a built pack, as `tools/worldkit/verify.py PACK` runs it ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `floors FILE --area X0,Z0,X1,Z1 [--step 1] [--layers A,B] [--below Y]` | The pack's floor heights over an area as `wp_floor()` finds them, what each belongs to, holes and cracks ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `floors FILE --at X,Z[;X,Z...]... [--layers A,B] [--below Y] [--kit]` | The pack's floor under each point and what it belongs to; with `--kit`, the kit's collision before packing ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `floor FILE X Z [X Z ...]` | Deprecated: `floors FILE --at X,Z --kit --json`, which prints the same JSON. Still works, with a note on stderr |
| `textures FILE [--region R] [--cells ...] [--add REGION:ASSET,...]` | Texture VRAM per region, by asset and by image, against the region's budget ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |
| `cracks FILE [--routes FILE] [--near 3] [--baseline [FILE]] [--write-baseline]` | Every collision crack the game's floor query does not bridge, on routes first, the widest first; compared with or written to the crack baseline ([Quick tools](WORLDKIT-REFERENCE.md#quick-tools)) |

The options of `build` (`--world-checker`, `--cache`, `--crack-baseline`) and of the quick tools
are in [Command line](WORLDKIT-REFERENCE.md#command-line).

## Using a world in a cart

A cart in `carts/NAME/` lists the recipes of the worlds it uses in `carts/NAME/worlds.txt`, one
repository path per line, and imports each world's generated file by name:

```
import "test_room.akr"        // also brings in worldpack.akr and garden.game.akr

fn init() { assert(world_test_room_load()) }

fn draw() {
    cls(rgb(40, 60, 120))
    wp_draw(vec3(32.0, 4.0, 8.0), 0.0, -0.2)
}
```

`make build/carts/NAME.mei` builds each world into `build/worlds/` (with the full World Checker),
links the generated files into `build/cart-worlds/NAME/` and compiles the cart with `meic -I
build/cart-worlds/NAME`. A world must not share its name with a file in the folder that imports
it. The details, what rebuilds when, World Viewer and a world with textures and a backdrop are in
[Using a world in a cart](WORLDKIT-REFERENCE.md#using-a-world-in-a-cart); the reader's functions
are in [WORLDPACK.md](WORLDPACK.md#the-console-reader-stdlibworldpackakr).

## Examples

| World | What it shows |
|---|---|
| [`test_room`](../examples/worlds/test_room) | One cell inline: a floor, a slope, a ledge, a wall, a canopy whose underside is a ceiling from a companion collision asset, a gate in an exclusive pair of layers, a collectible with a required Asset Checker policy and a trigger whose parameters use every kind of reference |
| [`two_districts`](../examples/worlds/two_districts) | Four cells in two regions with day and night variants, stand-ins, a far cell, merged scatter, a festival layer, a `share: false` material |
| [`night_market`](../examples/worlds/night_market) | Two regions with texture sets, night variants of textures, animated textures and backdrops |
| [`shrine_grounds`](../examples/worlds/shrine_grounds) | Terrain: a terraced hill, a pond, swept paths and stairs, in depth mode |
| [`forest_mountain`](../examples/worlds/forest_mountain) | A cliff band with an overhang, a pond, streams and a waterfall, draped trails, scatter, things set on the ground, in depth mode |

`init --example` copies `room` (`test_room`), `city` (`two_districts`) or `terrain`
(`shrine_grounds`). The largest world in the repository is the movement garden's shrine town
(`carts/garden/shrinetown/shrinetown.world.json`, 30 cells in two regions).

`make test-world` (also part of `make test`) runs `tests/test_worldkit.py`, which builds the
examples and runs them on the console, and `tests/test_mochi.py`; `tests/test_worldverify.py`,
`tests/test_worldpack.py` and `tests/test_worldcache.py` test the World Checker, the pack and the
checkers' cache. `test_worldkit.py`'s `SettingsFileTests` cover the settings
file: the runtime from it, a contradicting one refused, an asset folder's default policy and the
`settings_runtime` warning, the quick tools' cache noticing a new file, and the build directory.

## Where to look next

| To | Read |
|---|---|
| Look up a property of the world file or a cell | [Recipe format](WORLDKIT-REFERENCE.md#recipe-format) |
| Recolour a region by night, or add fog | [Palettes per region](WORLDKIT-REFERENCE.md#palettes-per-region) |
| Place textured assets and stay in VRAM | [Textures per region](WORLDKIT-REFERENCE.md#textures-per-region), [VRAM](WORLDKIT-REFERENCE.md#vram) |
| Add a sky and a skyline | [Backdrops](WORLDKIT-REFERENCE.md#backdrops) |
| Make hills, cliffs, water, paths and forests | [Terrain](WORLDKIT-REFERENCE.md#terrain) |
| Draw less far away | [Levels of detail](WORLDKIT-REFERENCE.md#levels-of-detail), [Stand-ins made by the kit](WORLDKIT-REFERENCE.md#stand-ins-made-by-the-kit), [Occlusion](WORLDKIT-REFERENCE.md#occlusion), [Quads](WORLDKIT-REFERENCE.md#quads) |
| Define entity types and the player's body | [Game data and stable IDs](WORLDKIT-REFERENCE.md#game-data-and-stable-ids) |
| Understand collision, cracks and steep ground | [Collision](WORLDKIT-REFERENCE.md#collision) |
| Read what `build` writes | [Build outputs and the runtime contract](WORLDKIT-REFERENCE.md#build-outputs-and-the-runtime-contract) |
| Understand a World Checker finding | [WORLDCHECKER.md](WORLDCHECKER.md) |
| Draw and collide with a world in a cart | [WORLDPACK.md](WORLDPACK.md#the-console-reader-stdlibworldpackakr) |
| Know why the kit is built this way | [WORLDKIT-DESIGN.md](WORLDKIT-DESIGN.md) |
