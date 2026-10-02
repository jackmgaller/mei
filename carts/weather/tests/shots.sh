#!/bin/sh
# Makes the screenshots in carts/weather/screenshots/ and their contact sheets.
# Most frames play the sample tape (TAPE=demo: the made-up weather of Meiville) through the
# console's decoder; the placeholders run with no signal at all, as on the web.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/out/shots"
DST="$HERE/../screenshots"
mkdir -p "$OUT" "$DST"
rm -f "$DST"/*.png
shot() {      # name scenario frames [env...]
    n="$1"; s="$2"; f="$3"; shift 3
    env SHOT=1 "$@" "$HERE/run.sh" "$s" "$f" "$OUT/$n" > /dev/null
    cp "$OUT/$n.png" "$DST/$n.png"
}
shot 01_now            1  400  TAPE=demo
shot 02_week           2  900  TAPE=demo
shot 03_hours          3  900  TAPE=demo
shot 04_map_home       4  900  TAPE=demo
shot 05_map_national   5  4400 TAPE=demo
shot 06_map_midwest   15  3800 TAPE=demo
shot 07_map_mountain  20  3000 TAPE=demo P="5"
shot 08_map_pacific   20  4000 TAPE=demo P="8"
shot 09_regions       18  1500 TAPE=demo
shot 10_clock         11  600  TAPE=demo
shot 11_tour           9  3790 TAPE=demo
shot 12_remote        16  200  TAPE=demo
shot 13_settings      17  200  TAPE=demo
shot 14_transition    14  612  TAPE=demo
shot 15_waiting       10  300  NOBC=1
shot 16_map_waiting    4  300  NOBC=1
cd "$DST"
python3 "$HERE/contact.py" contact_pages.png 3 2 \
    01_now.png="Current conditions" 02_week.png="Extended forecast" \
    03_hours.png="Next 24 hours" 04_map_home.png="Home map and its cities" \
    05_map_national.png="National map" 06_map_midwest.png="Midwest map" \
    09_regions.png="Regions directory (P101)" 10_clock.png="Clock from the time page (P100)" \
    11_tour.png="Idle tour: Local Forecast"
python3 "$HERE/contact.py" contact_more.png 3 2 \
    07_map_mountain.png="Mountain map" 08_map_pacific.png="Pacific NW map" \
    14_transition.png="Page transition (blinds)" 12_remote.png="The remote: typing a page number" \
    13_settings.png="Settings" 15_waiting.png="No weather yet (no signal, as on the web)" \
    16_map_waiting.png="A map not received yet"
