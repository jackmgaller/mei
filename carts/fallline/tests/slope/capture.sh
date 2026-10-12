#!/bin/sh
# Gate 1: the slope engine's captured run over the crests and run-outs.
# Usage: carts/fallline/tests/slope/capture.sh [OUT_DIR]   (default build-fl-slope/gate1)
# Builds tests/slope/slope_test.akr, runs it headless over the whole course (printing the CPU
# cycles slope_frame() takes, a second at a time), then captures every 2nd frame of a window
# around each crest and run-out and makes a contact sheet (PNG) and an animated GIF of each
# (sheet.py; needs Pillow). MEIC and RUN name the compiler and player (default build-fl-slope/).
set -e
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
MEIC="${MEIC:-$ROOT/build-fl-slope/meic}"
RUN="${RUN:-$ROOT/build-fl-slope/mei-headless}"
OUT="${1:-$ROOT/build-fl-slope/gate1}"
HERE="$ROOT/carts/fallline/tests/slope"
mkdir -p "$OUT"
"$MEIC" "$HERE/slope_test.akr" -o "$OUT/slope_test.mei"
"$RUN" "$OUT/slope_test.mei" --frames 3900 > "$OUT/run.log"
grep '^t ' "$OUT/run.log" | awk '{ if ($9 > m) m = $9; if ($11 > x) x = $11; s += $9; n++ }
    END { printf "slope_frame cycles: mean %d, peak %d (over %d seconds)\n", s / n, x, n }'
# windows (ticks): the rider passes crest 1 at about 823, the run-out at 1040, crest 2 at 1795,
# crest 3 at 2312 and its run-out at 2511 (run.log's "point" lines)
for w in "crest1 740 960" "runout1 990 1110" "crest2 1720 1940" "crest3 2230 2450" "runout3 2470 2590" "finish 3560 3700"; do
    set -- $w
    rm -rf "$OUT/$1" && mkdir -p "$OUT/$1"
    "$RUN" "$OUT/slope_test.mei" --frames "$3" --dump-every 2 "$OUT/$1/f" --dump-from "$2" > /dev/null
    python3 "$HERE/sheet.py" "$OUT/$1" "$OUT/$1"
done
