# 11 MeiNet Receiver

The console as a 1990s Japanese BS tuner that also plays carts. It is a low MeiNet-blue box
with a smoked-black fascia and a pale grey control deck. The fascia has a VFD window showing
teletext page P100, the time and the weather, and a rotary tuning dial labelled TUNE. A strip
of TV colour bars runs along the back edge of the deck, and a signal/carrier/data LED strip
sits on the step behind it. The deck's four page keys are red, green, yellow and cyan, the
Teletext Fastext colours. Power is a sun-orange button and reset a moon-blue one (日 and 月).
A Mei Weather cart stands in the top slot, a telescopic antenna with a sun-orange tip rises
from the rear corner, and the back has ANT IN / RF OUT F-connectors.

The controller looks like a TV remote crossed with a gamepad. It is a blue dogbone with a grey
centre panel to match the deck, a small smoked window with the 明 MEI logo over a strip of
colour bars, and A B X Y in the same Fastext colours as the console's page keys. It has a
d-pad, one stick lower left, Select and Start, and L and R.

| | Console | Controller |
|---|---|---|
| Triangles | 856 | 772 |
| Vertices | 504 | 420 |
| Size (m) | 0.30 × 0.072 × 0.22 body; 0.22 tall to the antenna tip | 0.154 × 0.04 × 0.12 |
| Texture VRAM | 69,303 bytes | 24,181 bytes |
| Asset Checker | PASS, depth mode | PASS, depth mode |

- **Scale:** metres at real size, 1:1. The 16.16 coordinates had no trouble at this size. All
  details sink 1–2 mm into the surface they sit on, so there are no flush contacts.
- **Files:** `make_art.py` draws `art/sheet.png` and `art/sheet.sheet.json` (needs Pillow and the
  macOS fonts Hiragino Sans GB and Avenir Next; the 8×8 VFD digits come from
  `src/core/font8x8.h`). `make_models.py` writes both recipes. Edit the scripts, not the JSON.
- **How it is built:** each shell is an explicit `mesh` with `face_materials`, so every face of
  the console's side profile (fascia, deck, riser, lid, rear) gets its own `fit` panel from the
  sheet. The VFD and the riser LED strip are `emissive`. The port and slot bezels are open
  frames whose sides run into the body, which makes the printed dark sockets read as recesses.
- **What the kit made hard:** there are no holes or booleans, so every recess is a printed
  socket inside a raised bezel. Offsetting a loft outline inward gives non-planar quads, which
  the `mesh` op refuses, so the controller's bevel bands are written as triangles. In the
  fitted contact sheet the console is small, because the antenna sets the bounds. A 0.38 m
  antenna made the body tiny, so it is shown half-extended at 0.16 m. The world-scale camera
  views (`cameras.png` in the build folder) show the printed detail far better than the contact
  sheet does.
- **Build note:** `build-console/mei-asset-probe` was briefly an empty file while another agent
  rebuilt it. The previews were made with copies of the three tools in
  `build-console/assets/11_meinet_receiver/_tools/` (`pv.sh` there runs a preview).
