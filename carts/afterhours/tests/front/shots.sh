#!/bin/sh
# The front end's captures (agent E), into tests/front/shots/: the title, the stage select (new,
# part cleared, cleared, the tower locked as a silhouette, the tower open, the store), three
# transitions (H's) as strips of every 6th frame over 60 frames (the station's room 1 to 2 and
# 2 to 3; in the store, back from the shop floor into the staff corridor), the stages' ends, and
# the pause in the store (its map with the rooms so far, then its controls; scenario 73).
# Each is a run of a scenario from tests/front/harness.akr stopped at its frame. Needs Pillow for
# the strips. MEIC, RUN and WORLDS as for tests/front/run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SH="$HERE/shots"
T="$HERE/../out/front-shots-$(basename "$(dirname "${MEIC:-build/meic}")")"
mkdir -p "$SH" "$T"
shot() {      # name scenario frames: the last frame of the run
    rm -f "$T/$1.mcd"
    TRAP=0 "$HERE/run.sh" "$2" "$3" "$T/$1" --card1 "$T/$1.mcd" > "$T/$1.log" 2>&1 || true
    cp "$T/$1.png" "$SH/$1.png"
}
strip() {     # name scenario from frames: every 6th frame from `from`, four to a row
    rm -f "$T/$1.mcd" "$T/$1"_seq_*
    SEQ="6 $3" TRAP=0 "$HERE/run.sh" "$2" "$4" "$T/$1" --card1 "$T/$1.mcd" > "$T/$1.log" 2>&1 || true
    python3 - "$T" "$1" "$SH/$1.png" <<'PY'
import glob, sys
from PIL import Image
d, n, out = sys.argv[1:4]
ims = [Image.open(f) for f in sorted(glob.glob('%s/%s_seq_*.png' % (d, n)))]
w, h = ims[0].size
rows = (len(ims) + 3) // 4
sheet = Image.new('RGB', (4 * w, rows * h))
for i, im in enumerate(ims):
    sheet.paste(im, ((i % 4) * w, (i // 4) * h))
sheet.save(out)
PY
}
shot title 60 39
shot select_new 60 58
strip transition_1_to_2 60 459 519
strip transition_2_to_3 60 2023 2083
shot end 60 3067
shot select_tower_open 60 3089
shot select_cleared 60 3099
shot select_part_cleared 61 41
shot select_locked 61 81
shot select_store 66 49
strip transition_store_back 66 4454 4514
shot end_store 66 10708
shot pause_map 73 4640
shot pause_controls 73 4700
echo "captures in $SH"
