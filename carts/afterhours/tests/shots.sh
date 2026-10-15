#!/bin/sh
# The Gate 1 captures, on B's platform, into tests/shots/: a train passing (scenario 20), the
# camera's cone cut by a pillar (21) and the caught freeze (22), and the framing of each room of
# level 1 and the platform with the thief walked to its front row (50-55), and hiding (56), each 320 x 240 as the console
# draws it and scaled up three times, pixel for pixel (*_x3.png). MEIC, RUN and WORLDS as for
# tests/run.sh; needs sips (macOS, through tools/cart_scenario.sh) and Pillow.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/shots"
S="$HERE/shots"
mkdir -p "$O" "$S"
shot() {      # scenario frames name [SHOT]
    SHOT="${4:-1}" "$HERE/run.sh" "$1" "$2" "$O/$3" > "$O/$3.log" 2>&1 || { echo "FAILED scenario $1"; tail -5 "$O/$3.log"; exit 1; }
    cp "$O/$3.png" "$S/$3.png"
    python3 -c 'import sys; from PIL import Image; Image.open(sys.argv[1]).resize((960, 720), Image.NEAREST).save(sys.argv[2])' "$S/$3.png" "$S/$3_x3.png"
    echo "$S/$3.png"
}
shot 20 621 train_passing
shot 21 451 cone_cut_by_pillar
shot 22 91 caught_freeze
for k in 1 2 3 4 5; do shot 5$((k - 1)) 102 frame_level1_room$k; done
shot 55 102 frame_platform
# hiding, in level 1's gates (B's tape): going in, hidden, coming out. The frames follow that tape
# (scenario 56 prints NOTE frame when its moment comes); redo them if the tape changes.
shot 56 179 hiding_enter
shot 56 213 hiding
shot 56 1162 hiding_leave 2
