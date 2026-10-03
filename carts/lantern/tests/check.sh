#!/bin/sh
# The Lantern Lake scenarios that can pass or fail on their own; stops at the first failure.
# - Every scenario of the harness builds and runs 120 frames without a fault. (That is all
#   most of them can say: they make screenshots and measurements for a person to judge.)
# - The pause tests (60-64): from the moment the game is paused to the end of the pause,
#   nothing in the world moves (the SNAP lines "paused" and "held" agree, apart from the
#   music's fade and the menu's own frame count), and it moves on after the pause.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames
    "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.log" 2>&1 || { echo "FAILED scenario $1"; tail -5 "$O/s$1.log"; exit 1; }
}
for s in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 \
         31 32 33 34 35 36 37 40 41 42 43 44 45 46 47 48 49 50; do
    run $s 120
done
echo "lantern: 48 scenarios ran without a fault"
snap() {      # scenario label: that SNAP line without the fields a pause may change
    grep "^SNAP $2 " "$O/s$1.log" | sed -e 's/^SNAP [a-z]* //' -e 's/ screen_t [0-9-]*//' -e 's/ duck [0-9-]*//'
}
pause() {     # scenario frames
    run "$1" "$2"
    p="$(snap "$1" paused)"; h="$(snap "$1" held)"
    [ -n "$p" ] && [ "$p" = "$h" ] || { echo "FAILED pause scenario $1: the world moved while paused"; grep '^SNAP' "$O/s$1.log"; exit 1; }
    t0=$(snap "$1" held | cut -d' ' -f2); t1=$(snap "$1" resumed | cut -d' ' -f2)
    [ -n "$t1" ] && [ "$t1" -eq $((t0 + 1)) ] || { echo "FAILED pause scenario $1: no step after the pause"; grep '^SNAP' "$O/s$1.log"; exit 1; }
    echo "OK pause $1"
}
pause 60 900
pause 61 500
pause 62 500
pause 63 900
pause 64 600
echo "all Lantern Lake checks passed"
