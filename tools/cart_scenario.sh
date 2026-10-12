#!/bin/sh
# The shared cart scenario runner behind carts/*/tests/run.sh.
# Usage: tools/cart_scenario.sh TESTS_DIR SCENARIO FRAMES OUT_BASENAME [mei-headless args]
# Builds a scenario cart in TESTS_DIR: the lines in $SC_HEAD (the cart line and its
# constants, written by the cart's run.sh), then `import "harness.akr"` and
# `import "$SC_APP"` (the game, relative to TESTS_DIR). Runs it headless for FRAMES ticks and
# converts the last frame to OUT_BASENAME.png (with sips, where there is one). The exit
# status is mei-headless's: 2 when the cart faults, an assert fails or a check fails.
# The scenario is a debug build with fixed-point overflow traps (meic --trap-fmul: -g's bounds
# and stack checks, plus fixed * fixed and fixed * integer products that do not fit `fixed`);
# a failed check prints the source line. On another fault the function holding the faulting pc
# is printed, from the symbol file (OUT_BASENAME.sym, removed unless the run fails).
#   SHOT=1          (read by the harnesses) hide the test overlay
#   SEQ="N [FROM]"  also save every Nth frame (from frame FROM) as OUT_BASENAME_seq_*.png
#   KEEP_PPM=1      keep OUT_BASENAME.ppm next to the PNG
#   MEIC, RUN       the compiler and player (default build/meic, build/mei-headless)
#   SC_IMPORT=DIR   an import directory for meic (-I), such as a cart's built worlds
#   TRAP=0          build the scenario without the debug checks (as a release cart)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MEIC="${MEIC:-$ROOT/build/meic}"
RUN="${RUN:-$ROOT/build/mei-headless}"
TESTS="$1"; SCEN="$2"; FRAMES="$3"; OUT="$4"
shift 4
S="$TESTS/_scenario_${SCEN}_$$.akr"
printf '%s\nimport "harness.akr"\nimport "%s"\n' "$SC_HEAD" "$SC_APP" > "$S"
TRAPS=--trap-fmul
[ "${TRAP:-1}" = 0 ] && TRAPS=
"$MEIC" $TRAPS ${SC_IMPORT:+-I "$SC_IMPORT"} "$S" -o "$OUT.mei" --sym "$OUT.sym" || { rm -f "$S"; exit 1; }
rm -f "$S"
if [ -n "$SEQ" ]; then
    set -- --dump-every $(echo $SEQ | cut -d' ' -f1) "${OUT}_seq" --dump-from $(echo "$SEQ 0" | cut -d' ' -f2) "$@"
fi
st=0
"$RUN" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" "$@" 2> "$OUT.err" || st=$?
cat "$OUT.err" >&2
if [ "$st" -ne 0 ]; then
    # a fault other than a Break (asserts and checks break after printing their line): name
    # the function, the last F_ symbol at or below the pc
    pc="$(sed -n 's/^fault: .* at pc=0x\([0-9A-F]*\) .*/\1/p' "$OUT.err")"
    if [ -n "$pc" ] && ! grep -q '^fault: Break ' "$OUT.err"; then
        awk -v pc="$pc" 'function hex(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789ABCDEF", substr(s, i, 1)) - 1; return v }
            BEGIN { p = hex(pc) } $2 ~ /^F_/ && $2 !~ /\./ { a = hex($1); if (a <= p && a >= best) { best = a; fn = $2 } }
            END { if (fn != "") printf "fault in %s+0x%X (%s)\n", substr(fn, 3), p - best, FILENAME }' "$OUT.sym" >&2
    fi
    rm -f "$OUT.err"
    exit "$st"
fi
rm -f "$OUT.err" "$OUT.sym"
command -v sips >/dev/null 2>&1 || exit 0
if [ -n "$SEQ" ]; then
    for f in "${OUT}"_seq_*.ppm; do sips -s format png "$f" --out "${f%.ppm}.png" >/dev/null && rm -f "$f"; done
fi
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
if [ -z "$KEEP_PPM" ]; then rm -f "$OUT.ppm"; fi
