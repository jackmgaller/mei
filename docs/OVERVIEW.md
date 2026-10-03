# Mei

A 3D fantasy console modelled on PlayStation-era hardware, implemented from
[`docs/spec-v0.1.pdf`](spec-v0.1.pdf)
(text copy in [`docs/spec-v0.1.txt`](spec-v0.1.txt)).

- 320×240 at 60 fps, 15-bit colour, 4×4 ordered dither
- 32-bit RISC CPU, 63 instructions, 500,000 cycles per frame
- A vector unit with eight 4-lane 16.16 registers (`vxfm`, `vproj`, …) and GTE-style geometry
  instructions (`vxp3`, `nclip`, `otz`, `clerp`; see [`DECISIONS.md`](DECISIONS.md#geometry-instructions))
- A GPU that only fills 2D triangles: affine textures, whole-pixel vertices, no depth buffer,
  an ordering table, four blend modes, and a budget of 1,000,000 GPU cycles and 4,000
  triangles per frame
- 22,050 Hz audio: 16 channels, ADPCM, reverb; two controllers, 2 MB RAM, up to 64 MB cart ROM (read in place), 1 MB VRAM

The look comes from those rules (texture warp, vertex wobble, sorting glitches, dither),
not from post-processing, and everything is deterministic fixed-point.

## Build

Needs a C compiler and SDL3 (`brew install sdl3`); the browser build also needs
Emscripten (`brew install emscripten`).

```bash
make            # emulator, tools and carts in build/
```

```bash
make test       # CPU, GPU, audio, assembler and language tests
```

```bash
make web        # WebAssembly build in build/web (serve it over HTTP)
```

## Run

```bash
./build/mei
```

This powers on the console: the system ROM (`system/`, see [`docs/SYSTEM.md`](SYSTEM.md))
plays a boot animation (five themes, chosen in Settings) and opens a small shell to browse
and launch the carts in `build/carts`, test controllers and sounds, and change settings.
Settings persist between sessions. Home (gamepad Guide button or F2) returns to the shell.
Games save to two virtual memory cards (`card1.mcd`, `card2.mcd`, 128 KB each; see
[`docs/MEMCARD.md`](MEMCARD.md)), kept with the settings in
`~/Library/Application Support/gallerdude/Mei/` (browser storage on the web).
Carts can also tune in to **MeiNet**, a Teletext-style data broadcast of the time and US
weather ([`docs/BROADCAST.md`](BROADCAST.md)): run `python3 tools/meinet/meinet.py` and the
desktop player picks up its signal.
To run a cart, either directly or after the boot animation:

```bash
./build/mei build/carts/demo.mei
```

```bash
./build/mei --no-boot build/carts/demo.mei
```

Or drop a `.mei` file on the window. Keyboard: arrows = d-pad, WASD = analog stick,
J K U I = A B X Y, Q E = L R, Enter = Start, Backspace = Select, F2 home, F5 reset, F11 fullscreen, Esc quit.
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
| `src/core/` | The emulator core: plain C, no platform calls. `bus.c` (memory map, I/O, faults), `cpu.c`, `gpu.c` (packet lists and rasterizer), `audio.c`, `mei.c` (public API in `mei.h`) |
| `src/platform/` | `sdl_main.c` (SDL3 desktop and browser), `xinput_usb.c` (XInput pads over libusb), `headless.c` |
| `src/asm/` | Assembler and disassembler library + `meiasm` |
| `src/lang/` | The compiler (`meic`): lexer, parser, type checker, code generator |
| `system/` | The system ROM: boot themes (`system/boot/`) and the shell, written in Akari |
| `stdlib/` | The standard library, compiled into every cart: input, maths, camera, `mesh`, ordering table, fog, text, sprites, audio |
| `carts/` | Example carts |
| `tests/` | C unit tests per module and language tests (`tests/lang/*.akr` with expected output) |
| `tools/` | Asset generators, the language fuzzer, the web cart packer |
| `web/shell.html` | The browser page |
| `tools/meinet/` | The broadcast gateway: Open-Meteo weather encoded into a looping page carousel, served over TCP |
| `docs/` | Spec, [decisions](DECISIONS.md) on everything the spec leaves open, language and assembly references, [memory cards](MEMCARD.md), [broadcast](BROADCAST.md) |

## Names

If something has a name, it matters. These are the named things in the project.

**The console**

| Name | What it is | Where |
|---|---|---|
| **Mei** | The console. The name is the character 明, "bright" | `src/core/`, [the spec](spec-v0.1.txt) |
| **Akari** | The programming language (明かり, "light"); sources end in `.akr` | `src/lang/`, [LANGUAGE.md](LANGUAGE.md) |
| **Prism Engine** | The 3D polygon processor: the GPU that fills triangles | `src/core/gpu.c`, [the spec](spec-v0.1.txt) |
| **Horizon Engine** | The scrolling plane processor: the second video chip, for background planes, skies, floors and backdrops (called "the plane chip" in older text) | `src/core/planes.c`, [PLANES.md](PLANES.md) |
| **MeiNet** | The one-way data broadcast (time and weather) and the gateway that sends it | [BROADCAST.md](BROADCAST.md), `tools/meinet/` |
| **Mei System** | The system ROM: boot animation and shell | [SYSTEM.md](SYSTEM.md), `system/` |
| **Duet**, **Eclipse** | The two boot themes | `system/boot/` |

**Tools**

| Name | What it is | Where |
|---|---|---|
| **Asset Kit** | Turns a JSON recipe into one native mesh. For things you could place twice | [ASSETKIT.md](ASSETKIT.md), `tools/mei_assets.py` |
| **Asset Checker** | The Asset Kit's `verify`: proves one asset's faces draw in the right order from every side | [ASSETKIT.md](ASSETKIT.md) |
| **World Kit** | Turns a world recipe into a level: cells, regions, layers, collision, game data. In progress | [WORLDKIT.md](WORLDKIT.md) |
| **World Pack** | The binary level format the World Kit writes and the console reads in place | [WORLDPACK.md](WORLDPACK.md), `stdlib/worldpack.akr` |
| **World Checker** | The World Kit's `verify`: checks a level from where a player can stand, for budgets, drawing order and collision holes. In progress | [WORLDKIT.md](WORLDKIT.md) |
| **Reference Renderer** | An independent renderer that Mei's output is compared against, to test the console itself (`make rendercheck`). Not yet committed | |

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
image of up to 64 MB at `0x08000000`, with an optional `MEI1` title header), the standard library compiled into each cart,
and so on.
