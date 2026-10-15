#!/bin/sh
# The front end's captures (agent E), into tests/front/shots/: the title, the stage select (new,
# part cleared, cleared, stage 2 locked as a silhouette, stage 2 open), three transitions as
# strips of every 6th frame (room 1 to 2; the lobby up to the aquarium; in stage 2, back from the
# shop floor into the staff corridor), and the stages' ends. Each
# is a run of a scenario from tests/front/harness.akr stopped at its frame. Needs Pillow for the
# strips. MEIC, RUN and WORLDS as for tests/front/run.sh.
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
strip transition_1_to_2 60 456 552
strip transition_4_to_5 60 4357 4452
shot end 60 5270
shot select_stage2_open 60 5292
shot select_cleared 60 5302
shot select_part_cleared 61 41
shot select_locked 61 81
shot select_stage2 66 49
strip transition_stage2_back 66 4523 4619
shot end_stage2 66 10960
echo "captures in $SH"
