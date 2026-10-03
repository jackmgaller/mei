#!/bin/sh
# The shared cart scenario runner behind carts/*/tests/run.sh.
# Usage: tools/cart_scenario.sh TESTS_DIR SCENARIO FRAMES OUT_BASENAME [mei-headless args]
# Builds a scenario cart in TESTS_DIR: the lines in $SC_HEAD (the cart line and its
# constants, written by the cart's run.sh), then `import "harness.akr"` and
# `import "$SC_APP"` (the game, relative to TESTS_DIR). Runs it headless for FRAMES ticks and
# converts the last frame to OUT_BASENAME.png (with sips, where there is one). The exit
# status is mei-headless's: 2 when the cart faults or an assert fails.
#   SHOT=1          (read by the harnesses) hide the test overlay
#   SEQ="N [FROM]"  also save every Nth frame (from frame FROM) as OUT_BASENAME_seq_*.png
#   KEEP_PPM=1      keep OUT_BASENAME.ppm next to the PNG
#   MEIC, RUN       the compiler and player (default build/meic, build/mei-headless)
#   SC_IMPORT=DIR   an import directory for meic (-I), such as a cart's built worlds
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MEIC="${MEIC:-$ROOT/build/meic}"
RUN="${RUN:-$ROOT/build/mei-headless}"
TESTS="$1"; SCEN="$2"; FRAMES="$3"; OUT="$4"
shift 4
S="$TESTS/_scenario_${SCEN}_$$.akr"
printf '%s\nimport "harness.akr"\nimport "%s"\n' "$SC_HEAD" "$SC_APP" > "$S"
"$MEIC" ${SC_IMPORT:+-I "$SC_IMPORT"} "$S" -o "$OUT.mei" || { rm -f "$S"; exit 1; }
rm -f "$S"
if [ -n "$SEQ" ]; then
    set -- --dump-every $(echo $SEQ | cut -d' ' -f1) "${OUT}_seq" --dump-from $(echo "$SEQ 0" | cut -d' ' -f2) "$@"
fi
"$RUN" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" "$@"
command -v sips >/dev/null 2>&1 || exit 0
if [ -n "$SEQ" ]; then
    for f in "${OUT}"_seq_*.ppm; do sips -s format png "$f" --out "${f%.ppm}.png" >/dev/null && rm -f "$f"; done
fi
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
if [ -z "$KEEP_PPM" ]; then rm -f "$OUT.ppm"; fi
