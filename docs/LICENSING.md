# Licensing inventory

What has to be replaced, removed or decided before Mei (the repository, the app or any cart) is
released publicly. Taken on 2026-10-10 from the working tree, untracked files included, and the
git history. Of what is listed, the licences (section 1) are chosen and the system fonts in
shipped art (section 3) are fixed.

## 1. Licences (decided 2026-10-10)

- Code, the standard library, the system ROM, the tools and the docs: MIT ([LICENSE](../LICENSE)).
  Carts compiled with `meic` may be distributed without the notice
  ([LICENSE-ASSETS.md](../LICENSE-ASSETS.md) has the exception).
- The carts' art and audio, the movement garden's worlds and `examples/`: CC BY 4.0
  ([LICENSE-ASSETS.md](../LICENSE-ASSETS.md)). A flagship game sold on its own may keep its
  assets under a different licence; that is not decided.
- The fonts in `tools/fonts/`: OFL 1.1, each with its licence file.
- Still open: `tools/vscode-akari/package.json` says `UNLICENSED`, and the extension's npm
  dependencies (MIT, BSD, Apache-2.0, Artistic-2.0) need their notices in a packaged build.
- The copyright line says `jackmgaller`; a legal name may be wanted there before release.

## 2. Eyewitness (`carts/eyewitness/`, untracked)

A port of the BBC / Dorling Kindersley title sequence (see its README's Provenance section).

- `rooms/*/pictures/*.png` (about 55 pictures): cropped from frames of a YouTube upload.
- `tools/gen_eyewitness_music.py` and its outputs (`music.akr`, `mu_data.akr`, `audio/`): a
  transcription of the theme.
- The name, the eye logo and the shot-by-shot camera flight belong to the original too.
- `tools/gen_eyewitness_assets.py` draws text in Palatino (see 3).

It has never been committed. Keep it out of any public repository (or make it an original
museum flight with its own name, logo, pictures and music).

## 3. macOS system fonts baked into committed art

Apple's licence for its bundled fonts does not cover redistributing them, so art rasterised from
them cannot ship. The generators of shipped art now read SIL Open Font License fonts from
`tools/fonts/`, made by `tools/fonts/make_fonts.py` from the google/fonts repository (static
weights, cut to Latin, kana and the kanji the generators draw), each family's licence beside
them as `OFL-<family>.txt`. The OFL allows bundling, embedding and selling them with software;
it needs the licence to travel with the font files, which it does in `tools/fonts/`. The
outputs were regenerated on 2026-10-10:

| Generator | Was | Now | Output |
|---|---|---|---|
| `tools/gen_shell_assets.py` | Avenir Next, Hiragino Kaku Gothic W6 | Figtree, Noto Sans JP Bold | `system/shell/` |
| `tools/gen_boot_duet.py` | Arial Rounded Bold, Hiragino Sans GB W6 | M PLUS Rounded 1c Bold, Noto Sans JP Bold | `system/boot/duet/` |
| `tools/gen_boot_eclipse.py` | Optima, Hiragino Mincho ProN | Belleza, Noto Serif JP | `system/boot/eclipse/` |
| `tools/gen_lantern_assets.py` | Arial Rounded Bold, Georgia Bold Italic, Hiragino Maru Gothic W4 | M PLUS Rounded 1c Bold, Gelasio Bold Italic, Zen Maru Gothic Medium | `carts/lantern/art/` |
| `tools/gen_weather_assets.py` | Avenir Next, Avenir Next Condensed | Figtree, Sofia Sans Condensed | `carts/weather/art/`, `art.akr` |
| `carts/garden/shrine/assets/art/draw_street_sheet.py` | Hiragino Kaku Gothic W6 | Noto Sans JP Bold | `street_sheet.png` |

Clean: the standard library's fonts (`src/core/font8x8.h`, after the public-domain
font8x8_basic shapes; `stdlib/font_small.akr`, a pixel font drawn by `meifont.py --pixel`),
Orbs, Sound Lab, Mei Demo, the movement garden's other textures.

Still open: `tools/gen_eyewitness_assets.py` draws in Palatino (see 2), and the examples and
development scripts below.

**Examples:**

- `examples/assets/lab/`, scripts that use system fonts: `ramen_shop`, `overpass`,
  `pachinko_parlour` (STHeiti), `schoolhouse`, `coin_laundry`, `newsstand`, `koban`.
- `examples/assets/lab/`, texture sheets with **no committed script** (the drawing scripts were
  not kept), several with Japanese or Latin text in an unknown font (for example
  `fire_tower/art/hinoyojin.png`): `dagashi_shop`, `danchi`, `fire_tower`, `kei_truck`,
  `recordshop`, `tobacco_shop`. These have to be redrawn by a committed script.

Development-only (draw sketches and contact sheets, not shipped): `carts/garden/electric/layout.py`,
`carts/weather/tests/contact.py`. They use Avenir Next; they need a fallback font, not a
replacement.

## 4. MeiNet's weather source

`tools/meinet/weather.py` reads Open-Meteo's free API. Open-Meteo's terms limit the free API to
non-commercial use, and its data is CC BY 4.0 (needs attribution). A paid product would need
their commercial plan, or a switch to the US National Weather Service API (`api.weather.gov`,
public domain), which covers what MeiNet broadcasts (US weather). Check their current terms
before deciding. The map outlines in `tools/weather_geo.py` are hand-drawn and clean; the city
list in `tools/meinet/cities.py` uses 2020 census figures (public domain).

## 5. Untracked files to look at before committing

- `docs/audio/` (8 WAVs, 81 MB): `os_music_crystal_day.wav`, `os_music_crystal_night.wav` and
  six `checkin_*.wav` of unknown origin.
- `docs/shots/`, `architecture-site/` (a generated site; no outside assets found).

## Checked and clean

- No third-party C code in `src/` or `web/`.
- No real brand names in the lab models, carts or recipes (searched for drink, convenience
  store, electronics, game and car brands). "PlayStation" appears only as a description in
  `docs/` and comments.
- The music of the shell, the boot themes, Lantern, Orbs, Mei Weather and Sound Lab is
  synthesised by its generators; nothing in them is described as a transcription.
- The git history has never held Eyewitness, video frames, MP3s or Apple's font files.
