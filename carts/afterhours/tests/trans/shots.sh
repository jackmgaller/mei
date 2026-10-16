#!/bin/sh
# The transition's captures (agent H), into tests/trans/shots/: strips of every 4th frame, four
# to a row, from the frame before the exit: the station's last train up to the ticket gates
# (scenario 60's first transition), the store's shop floor back into the staff corridor (66's
# third), the corridor's stair up to the booth (66's fourth) and the shop floor's lift down to the
# food hall (66's seventh), as the cart draws them; then the first two as they were when the
# rooms' textures shared slots (*_shared: tr_split_off()), and the two alternatives to the pan
# (TR_STEP, TR_PAIR); and the aquarium's doors on upper levels (scenario 90: the entrance hall's
# mezzanine to the great tank's catwalk, the catwalk up to the tank tops). Each scenario is run
# once to find its transitions' frames. Needs Pillow.
# MEIC, RUN and WORLDS as for tests/front/run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SH="$HERE/shots"
T="$HERE/../out/trans-shots-$(basename "$(dirname "${MEIC:-build/meic}")")"
mkdir -p "$SH" "$T"
run() {       # scenario frames out [args]: the front end's scenarios, or 90 (upper/)
    s=$1; shift
    if [ "$s" = 90 ]; then "$HERE/upper/run.sh" "$@"; else "$HERE/run.sh" "$s" "$@"; fi
}
frames() {    # scenario n worlds head: the first frame of its nth transition
    rm -f "$T/f$1.mcd"
    WORLDS="$3" TR_HEAD="$4" TRAP=0 run "$1" 12500 "$T/f$1" --card1 "$T/f$1.mcd" > "$T/f$1.log" 2>&1 || true
    sed -n "s/^TRANSITION $2 into room [0-9]*: frames \([0-9]*\)-\([0-9]*\)$/\1 \2/p" "$T/f$1.log"
}
strip() {     # name scenario n worlds head
    set -- "$@" $(frames "$2" "$3" "$4" "$5")
    from=$(( $6 - 1 )); to=$(( $7 + 6 ))
    rm -f "$T/$1.mcd" "$T/$1"_seq_*
    WORLDS="$4" TR_HEAD="$5" SEQ="4 $from" TRAP=0 run "$2" "$to" "$T/$1" --card1 "$T/$1.mcd" > "$T/$1.log" 2>&1 || true
    python3 - "$T" "$1" "$SH/$1.png" <<'PY'
import glob, re, sys
from PIL import Image, ImageDraw
d, n, out = sys.argv[1:4]
fs = sorted(glob.glob('%s/%s_seq_*.png' % (d, n)), key=lambda f: int(re.findall(r'(\d+)\.png', f)[-1]))
ims = [Image.open(f) for f in fs]
w, h = ims[0].size
G = 4
rows = (len(ims) + 3) // 4
sheet = Image.new('RGB', (4 * w + 3 * G, rows * h + (rows - 1) * G), (200, 200, 200))
dr = ImageDraw.Draw(sheet)
for i, im in enumerate(ims):
    x, y = (i % 4) * (w + G), (i // 4) * (h + G)
    sheet.paste(im, (x, y))
    dr.text((x + 4, y + 226), str(i * 4), fill=(255, 255, 0))
sheet.save(out)
PY
    echo "$SH/$1.png"
}
W="${WORLDS:-$HERE/../../../../build/cart-worlds/afterhours}"
SHARED="fn tr_split_off() -> bool { return true }"
strip station_1_to_2 60 1 "$W" ""
strip store_back 66 3 "$W" ""
strip store_booth 66 4 "$W" ""
strip store_lift 66 7 "$W" ""
strip station_1_to_2_shared 60 1 "$W" "$SHARED"
strip store_back_shared 66 3 "$W" "$SHARED"
strip station_1_to_2_step 60 1 "$W" "fn tr_style() -> s32 { return TR_STEP }"
strip store_back_pair 66 3 "$W" "fn tr_style() -> s32 { return TR_PAIR }"
strip aquarium_hall_to_great_upper 90 1 "$W" ""
strip aquarium_great_to_tops_upper 90 2 "$W" ""
echo "captures in $SH"
