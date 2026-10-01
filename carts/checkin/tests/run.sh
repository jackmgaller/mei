#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the game), runs it headless, converts the dump.
# SHOT=1 hides the debug counters (screenshots). SEQ="N [FROM]" also saves every Nth frame (from
# frame FROM) as OUT_BASENAME_seq_00012.png etc., for checking motion. P="a b c ..." sets the
# scenario parameters P1..P6 (default 0) that some scenarios read (see tests/scen_sim.akr).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$3"
FRAMES="$2"
S="$HERE/_scenario_$1_$$.akr"
PP="$(echo ${P:-} 0 0 0 0 0 0)"
printf 'cart "Check-In Test", "CHECK-IN"\nconst SCENARIO = %s\nconst SHOT = %s\n' "$1" "${SHOT:-0}" > "$S"
k=1
for v in $PP; do [ $k -le 6 ] && printf 'const P%s = %s\n' $k $v >> "$S"; k=$((k+1)); done
printf 'import "harness.akr"\nimport "../game.akr"\n' >> "$S"
"$ROOT/build/meic" "$S" -o "$OUT.mei" || { rm -f "$S"; exit 1; }
rm -f "$S"
shift 3
if [ -n "$SEQ" ]; then
    set -- --dump-every $(echo $SEQ | cut -d' ' -f1) "${OUT}_seq" --dump-from $(echo "$SEQ 0" | cut -d' ' -f2) "$@"
fi
"$ROOT/build/mei-headless" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" "$@"
if [ -n "$SEQ" ]; then
    for f in "${OUT}"_seq_*.ppm; do sips -s format png "$f" --out "${f%.ppm}.png" >/dev/null && rm -f "$f"; done
fi
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
