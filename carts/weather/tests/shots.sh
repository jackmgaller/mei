#!/bin/sh
# Makes the screenshots in carts/weather/screenshots/ and their contact sheets.
# Most frames play the sample tape (TAPE=demo: the made-up weather of Meiville) through the
# console's decoder; the receiving states use the gateway fixture or no signal at all.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/out/shots"
DST="$HERE/../screenshots"
mkdir -p "$OUT" "$DST"
shot() {      # name scenario frames [env...]
    n="$1"; s="$2"; f="$3"; shift 3
    env SHOT=1 "$@" "$HERE/run.sh" "$s" "$f" "$OUT/$n" > /dev/null
    cp "$OUT/$n.png" "$DST/$n.png"
}
shot 01_now            1  400  TAPE=demo
shot 02_week           2  900  TAPE=demo
shot 03_hours          3  900  TAPE=demo
shot 04_map_painting   4  181  TAPE=demo
shot 05_map_home       4  900  TAPE=demo
shot 06_map_national   5  3800 TAPE=demo
shot 07_map_midwest   15  3800 TAPE=demo
shot 08_regions       18  1500 TAPE=demo
shot 09_clock         11  600  TAPE=demo
shot 10_remote        16  200  TAPE=demo
shot 11_settings      17  200  TAPE=demo
shot 12_transition    14  612  TAPE=demo
shot 13_tour           9  3790 TAPE=demo
shot 14_waiting        3  200
shot 15_no_signal     10  300  NOBC=1
rm -f "$OUT/card.mcd"
env SHOT=1 CARD="$OUT/card.mcd" "$HERE/run.sh" 19 2600 "$OUT/fill" > /dev/null
shot 16_saved_offline 10  700  NOBC=1 P=1 CARD="$OUT/card.mcd"
shot 17_noisy         13  900  NOISE=0.0005
cd "$DST"
python3 "$HERE/contact.py" contact_pages.png 3 2 \
    01_now.png="Current conditions (P400 1/4)" 02_week.png="Extended forecast (P400 2/4)" \
    03_hours.png="Next 24 hours (P400 3/4)" 05_map_home.png="Home map (P400 4/4)" \
    06_map_national.png="National map (P4FF)" 07_map_midwest.png="Midwest map (P403 4/4)" \
    08_regions.png="Regions directory (P101)" 09_clock.png="Clock from the time page (P100)" \
    13_tour.png="Idle tour: Local Forecast"
python3 "$HERE/contact.py" contact_reception.png 3 2 \
    14_waiting.png="Waiting for a page: rows assembling" 04_map_painting.png="A map painting in as rows arrive" \
    12_transition.png="Page transition (blinds)" 10_remote.png="The remote: typing P4--" \
    11_settings.png="Settings" 15_no_signal.png="No signal" \
    16_saved_offline.png="Saved pages from the memory card" 17_noisy.png="A noisy signal (BER 0.0005)"
