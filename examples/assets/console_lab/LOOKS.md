# Console lab: sixteen looks for the Mei console and its controller

Each look is one folder here, `NN_slug/`, with two Asset Kit recipes: `console.asset.json` and
`controller.asset.json`, their `art/` sheets if any, the two contact sheets
(`preview_console.png`, `preview_controller.png`) and a short `NOTES.md`. Built previews go to
`build-console/assets/NN_slug/`; the native tools are in `build-console/`.

## What every look shares

What the docs fix about the machine:

- **Mei**, 明 ("bright"), the **Sun & Moon System**: 日 (sun) and 月 (moon) make 明. The logo
  is 明 with the 日 in warm orange and the 月 in pale blue, beside a white "MEI" wordmark
  (`docs/logo.png`). The boot themes are Duet (a sun-drop and a moon-drop on a white stage) and
  Eclipse (sun and moon unite into 明).
- **The 1997 slot**: a Japanese machine from just after the N64 and before the Dreamcast.
- **The console**: games on cartridges (up to 64 MB), two controller ports, two memory card
  slots, power and reset. It also receives **MeiNet**, a Teletext-style broadcast of the time
  and the weather.
- **The controller**: a d-pad, one analog stick, A B X Y, L and R, Start and Select (the spec's
  eleven buttons plus Select, [DECISIONS.md](../../../docs/DECISIONS.md)). No Home button.
- Real size in metres: the console roughly 0.25–0.35 m wide, the controller roughly 0.15 m.

## The looks

| # | Look | Mood |
|---|---|---|
| 01 | Hinomaru Grey | The launch model: warm light-grey plastic, the sober 1997 default |
| 02 | Duet White | Pearl white and soft, like the Duet boot stage; friendly and rounded |
| 03 | Eclipse Black | Matte charcoal with a thin gold ring; the serious, premium sibling |
| 04 | Sun & Moon Twin | The body itself reads as two forms, a round sun and a crescent moon, joined |
| 05 | Clear Smoke | Translucent smoke-grey shell with the insides hinted; the translucent craze a year early |
| 06 | Sunset Skeleton | Translucent orange limited edition: the 日 half |
| 07 | Moonlight Skeleton | Translucent indigo limited edition: the 月 half |
| 08 | Akihabara Silver | Metallic silver and gunmetal, vents and ribs; the spec-sheet machine of electric-town shop windows |
| 09 | Hi-Fi Deck | A 90s Japanese mini-component: slim, horizontal, sits under the TV beside the VCR |
| 10 | Kodomo Toy | Chunky and rounded, cream and tomato red, built to survive a seven-year-old |
| 11 | MeiNet Receiver | Leans into the broadcast: half games machine, half TV tuner |
| 12 | Moon-viewing Lacquer | Black and vermilion, urushi-feel collector's edition; the hanafuda moon over susuki grass |
| 13 | Sakura Pastel | Soft sakura pink and mint, like the Japan-only colour runs of the 90s |
| 14 | Prism Wedge | Angular and faceted, named for the Prism Engine; dark grey with a spectrum stripe |
| 15 | Pocket Cube | The compact one: nearly a cube, small footprint, the cart stands up out of the top |
| 16 | Arcade Heritage | From a maker of arcade boards: candy cream with pink and mint, arcade-style buttons |

## Results

All 32 recipes pass `verify` in depth mode with verification required (rerun together with the
tools in `build-console/` on 2026-10-09). `lineup.png` puts every look's console (isometric) and
controller (top) side by side; `python3 examples/assets/console_lab/make_lineup.py
examples/assets/console_lab examples/assets/console_lab/lineup.png` remakes it from the preview
sheets.

| # | Console triangles | Controller triangles |
|---|---|---|
| 01 | 748 | 778 |
| 02 | 1,188 | 814 |
| 03 | 1,174 | 798 |
| 04 | 1,130 | 798 |
| 05 | 1,014 | 782 |
| 06 | 910 | 790 |
| 07 | 1,006 | 786 |
| 08 | 500 | 720 |
| 09 | 806 | 652 |
| 10 | 1,184 | 806 |
| 11 | 856 | 772 |
| 12 | 848 | 776 |
| 13 | 1,158 | 794 |
| 14 | 884 | 562 |
| 15 | 1,180 | 782 |
| 16 | 892 | 866 |

The kit has no transparency and no holes. The see-through looks fake it in two ways: 07 paints
the insides onto a solid shell, while 05 and 06 cut a pattern of holes over modelled insides.
Ports and slots are printed sockets in raised frames throughout.
