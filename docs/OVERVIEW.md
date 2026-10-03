# Mei

A 3D fantasy console modelled on PlayStation-era hardware, implemented from
[`docs/spec-v0.1.pdf`](spec-v0.1.pdf)
(text copy in [`docs/spec-v0.1.txt`](spec-v0.1.txt)).

- 320×240 at 60 fps, 15-bit colour, 4×4 ordered dither
- 32-bit RISC CPU, 63 instructions, 500,000 cycles per frame
- A vector unit with eight 4-lane 16.16 registers (`vxfm`, `vproj`, …) and GTE-style geometry
  instructions (`vxp3`, `nclip`, `otz`, `clerp`; see [`DECISIONS.md`](DECISIONS.md#geometry-instructions))
- The **Prism Engine**, the 3D polygon processor (the spec's GPU), which only fills 2D
  triangles: affine textures, whole-pixel vertices, no depth buffer, an ordering table, four
  blend modes, and a budget of 1,000,000 GPU cycles and 4,000 triangles per frame
- The **Horizon Engine**, the scrolling plane processor: two tile planes, an affine (Mode 7)
  plane and a backdrop colour per line, composited with Prism's polygons at no CPU or GPU cost
  ([`PLANES.md`](PLANES.md))
- 22,050 Hz audio: 16 channels, ADPCM, reverb; two controllers, 2 MB RAM, up to 64 MB cart ROM
  (read in place), 1 MB VRAM

The look comes from those rules (texture warp, vertex wobble, sorting glitches, dither),
not from post-processing, and everything is deterministic fixed-point.

## Build

Needs a C compiler and SDL3 (`brew install sdl3`). Optional: libusb (`brew install libusb`)
for XInput pads on macOS (see [Run](#run)), and Emscripten (`brew install emscripten`) for the
browser build.

```bash
make            # emulator, tools, system ROM and carts in build/
```

```bash
make test       # C unit tests, language tests and, with python3, the Python test suites
```

```bash
make web        # WebAssembly build in build/web (serve it over HTTP)
```

`make test` runs the C unit tests (`tests/test_*.c`), the Akari language tests
(`tests/run_lang_tests.sh`) and, when `python3` is on the path, the MeiNet gateway's tests and
the Asset Kit, world pack, World Kit and World Checker suites (`tests/test_*.py`); tests that
need NumPy or a native tool that is missing are skipped. `make test-assets` and `make test-world`
run the Asset Kit and World Kit suites alone, verbosely. `make B=DIR` builds into `DIR` instead
of `build/`.

**Python.** The emulator, the compilers, the system ROM and the carts build and run without
Python: every generated file they use is committed. Python 3 runs the MeiNet gateway, the kits,
the asset generators and `make web`'s cart packer. The Asset Kit and World Kit build recipes with
the standard library alone (Python 3.10 or later); the Asset Checker and the World Checker need
NumPy. The asset generators in `tools/` need NumPy, those that draw pictures need Pillow, and
the Duet boot theme's and Sound Lab's need SciPy too; several use macOS system fonts.

## Run

```bash
./build/mei
```

This powers on the console: the system ROM (`system/`, see [`docs/SYSTEM.md`](SYSTEM.md))
plays a boot animation (two themes, Duet and Eclipse, chosen in Settings) and opens a small
shell to browse and launch the carts in `build/carts`, test controllers and sounds, and change
settings.
Settings persist between sessions. Home (gamepad Guide button or F2) returns to the shell.
Games save to two virtual memory cards (`card1.mcd`, `card2.mcd`, 128 KB each; see
[`docs/MEMCARD.md`](MEMCARD.md)), kept with the settings in
`~/Library/Application Support/gallerdude/Mei/` (browser storage on the web).
Carts can also tune in to **MeiNet**, a Teletext-style data broadcast of the time and US
weather ([`docs/BROADCAST.md`](BROADCAST.md)). The desktop player starts the gateway,
`tools/meinet/meinet.py`, by itself when none is running (it needs `python3`; `--no-gateway`
turns this off; the gateway logs to `meinet.log` beside the executable).
To run a cart, either directly or after the boot animation:

```bash
./build/mei build/carts/orbs.mei
```

```bash
./build/mei --no-boot build/carts/orbs.mei
```

`make` builds every cart except Mei Demo and Sound Lab, which are built on request
(`make build/carts/demo.mei build/carts/soundlab.mei`) and so are not in the shell's list.

Or drop a `.mei` file on the window. Keyboard: arrows = d-pad, WASD = analog stick,
J K U I = A B X Y, Q E = L R, Enter = Start, Backspace or right Shift = Select, F2 home,
F5 reset, F11 fullscreen, Esc quit.
Gamepads work too. On macOS, XInput-only controllers (Xbox 360-protocol pads such as an
8BitDo Ultimate 2C on a cable) have no system driver, so when libusb is installed
(`brew install libusb`) the desktop build reads them directly over USB
(`src/platform/xinput_usb.c`). The system menu's Controllers screen shows what the console
sees from each pad.

For the browser, serve `build/web` (for example `python3 -m http.server -d build/web`) and
open it. The page lists the bundled carts and accepts dropped or opened `.mei` files.

`build/mei-headless cart.mei --frames N --dump out.ppm [--pad1 HEX]` runs a cart without
a window, prints its debug console and saves the last frame. It's useful for tests.
`--dump-every N PREFIX` (optionally with `--dump-from F`) also saves every Nth frame as
`PREFIX_00012.ppm` and so on, for checking motion frame by frame.

## Write a cart

Carts are written in **Akari** (明かり, "light"), the console's own language ([`docs/LANGUAGE.md`](LANGUAGE.md)):

```
cart "Spinner"
embed CUBE: Mesh = "cube.bin"

var angle: fixed

fn update() {
    if btn(LEFT)  { angle -= 0.05 }
    if btn(RIGHT) { angle += 0.05 }
}

fn draw() {
    cls(rgb(20, 30, 60))
    camera(vec3(0.0, 1.0, -6.0), 0.0)
    mesh_at(CUBE, vec3(0.0, 0.0, 0.0), angle)
    text(8, 8, "HELLO", rgb(255, 255, 255))
}
```

```bash
./build/meic spinner.akr -o spinner.mei
```

Or in assembly ([`docs/ASSEMBLY.md`](ASSEMBLY.md)):

```bash
./build/meiasm hello.s -o hello.mei
```

`meiasm --disasm cart.mei` disassembles a cart. Put a cart in `carts/NAME/NAME.akr` or
`carts/asm/NAME.s` and `make` builds it into `build/carts/` (and `make web` bundles it).

## Layout

| Path | Contents |
|---|---|
| `src/core/` | The emulator core: plain C, no platform calls. `bus.c` (memory map, I/O, faults), `cpu.c`, `gpu.c` (Prism: packet lists and rasterizer), `planes.c` (Horizon, the plane chip), `audio.c`, `card.c` (memory cards), `broadcast.c` (the broadcast decoder), `mei.c` (public API in `mei.h`) |
| `src/platform/` | `sdl_main.c` (SDL3 desktop and browser), `sysboot.c` (loading the system ROM and its catalogue), `bcnet.c` (the desktop's broadcast tuner and gateway launcher), `xinput_usb.c` (XInput pads over libusb), `headless.c` |
| `src/asm/` | Assembler and disassembler library + `meiasm` |
| `src/lang/` | The compiler (`meic`): lexer, parser, type checker, code generator |
| `system/` | The system ROM: boot themes (`system/boot/`) and the shell, written in Akari |
| `stdlib/` | The standard library, compiled into every cart: input, maths, camera, `mesh`, ordering table, fog, text, sprites, audio, memory cards, broadcast. `planes.akr` and `worldpack.akr` (the world pack reader) only go into carts that import them |
| `carts/` | Example carts |
| `examples/` | Example recipes for the kits: assets (`examples/assets/`) and worlds (`examples/worlds/`) |
| `tests/` | C unit tests per module, language tests (`tests/lang/*.akr` with expected output) and the kits' Python suites |
| `tools/` | Asset generators (`gen_*.py`), the kits' entry points (`mei_assets.py`, `mei_world.py`), the language fuzzer, the web cart packer |
| `tools/assetkit/`, `tools/worldkit/`, `tools/kitcore/` | The [Asset Kit](ASSETKIT.md), the [World Kit](WORLDKIT.md) (with the [World Checker](WORLDCHECKER.md)) and the core they share |
| `tools/meinet/` | The broadcast gateway: Open-Meteo weather encoded into a looping page carousel, served over TCP |
| `tools/vscode-akari/` | Syntax highlighting for Akari in VS Code |
| `web/shell.html` | The browser page |
| `docs/` | Spec, [decisions](DECISIONS.md) on everything the spec leaves open, language and assembly references, [memory cards](MEMCARD.md), [broadcast](BROADCAST.md), [planes](PLANES.md), the kits and the [world pack format](WORLDPACK.md) |

## Names

If something has a name, it matters. These are the named things in the project.

**The console**

| Name | What it is | Where |
|---|---|---|
| **Mei** | The console. The name is the character 明, "bright" | `src/core/`, [the spec](spec-v0.1.txt) |
| **Akari** | The programming language (明かり, "light"); sources end in `.akr` | `src/lang/`, [LANGUAGE.md](LANGUAGE.md) |
| **Prism Engine** | The 3D polygon processor: the GPU that fills triangles | `src/core/gpu.c`, [the spec](spec-v0.1.txt), [GPU budget](DECISIONS.md#gpu-budget) |
| **Horizon Engine** | The scrolling plane processor: the second video chip, for background planes, skies, floors and backdrops (called "the plane chip" in older text) | `src/core/planes.c`, [PLANES.md](PLANES.md) |
| **MeiNet** | The one-way data broadcast (time and weather) and the gateway that sends it | [BROADCAST.md](BROADCAST.md), `tools/meinet/` |
| **Mei System** | The system ROM: boot animation and shell | [SYSTEM.md](SYSTEM.md), `system/` |
| **Duet**, **Eclipse** | The two boot themes | `system/boot/` |

**Tools**

| Name | What it is | Where |
|---|---|---|
| **Asset Kit** | Turns a JSON recipe into one native mesh. For things you could place twice | [ASSETKIT.md](ASSETKIT.md), `tools/mei_assets.py` |
| **Asset Checker** | The Asset Kit's `verify` command: proves one asset's faces draw in the right order from every side | [ASSETKIT.md](ASSETKIT.md), `mei_assets.py verify` |
| **World Kit** | Turns a world recipe into a level: cells, regions, layers, collision, game data. Built; terrain, textures, audio banks and backdrops are still to come | [WORLDKIT.md](WORLDKIT.md), `tools/mei_world.py` |
| **World Pack** | The binary level format the World Kit writes and the console reads in place | [WORLDPACK.md](WORLDPACK.md), `stdlib/worldpack.akr` |
| **Mochi** | The small language a game's schema for the World Kit is written in (its entity types and their fields, the player's body, the worlds); files end in `.mochi`. Translated into the JSON form, which is still accepted | [WORLDKIT.md](WORLDKIT.md), `tools/worldkit/mochi.py` |
| **World Checker** | The World Kit's in-level verification, run by every `mei_world.py build` and on its own: checks a level from where a player can stand, for budgets, drawing order and collision holes. Built | [WORLDCHECKER.md](WORLDCHECKER.md), `tools/worldkit/verify.py` |
| **Reference Renderer** | An independent renderer that Mei's output is compared against, to test the console itself: stress scenes, subdivision, GPU fuzzing, the plane compositor, and all of them in motion (`make rendercheck`, `make rendercheck-motion`) | [its README](../tests/reference_renderer/README.md), `tests/reference_renderer/` |

**Carts**

| Name | What it is | Where |
|---|---|---|
| **Lantern Lake** | A fishing game on a lake, day into night | `carts/lantern/` |
| **Sun & Moon Orbs** | A small 3D collect-a-thon in a courtyard | `carts/orbs/` |
| **Mei Weather** | A weather channel fed by MeiNet | `carts/weather/` |
| **Features** | Short screens showing what the machine can do | `carts/features/` |
| **Sound Lab**, **Mei Demo** | The audio hardware test and the smallest example; built on request | `carts/soundlab/`, `carts/demo/` |

**Retired names**, which still appear in history and in some measurements: **Tsumiki** (a 3D
toolkit in the stdlib), **Playroom** (its sample cart) and **Check-In!** (a hotel-building cart).

## Decisions on the open questions

The spec lists questions that are not yet decided. [`docs/DECISIONS.md`](DECISIONS.md)
records how this implementation answers each one, and every edge case the spec leaves
open: xorshift32 for `RAND`, how audio is mixed and clipped, the cart format (a raw ROM
image of up to 64 MB at `0x08000000`, with an optional `MEI1` title header), the standard
library compiled into each cart, and so on.
