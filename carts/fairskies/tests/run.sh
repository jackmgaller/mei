#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the app), runs it headless against the
# recorded broadcast (tests/fixture.bin, from the gateway's --fixture data) and converts the
# last frame to OUT_BASENAME.png. A failed assert makes mei-headless exit with status 2.
#   SHOT=1          hide the test overlay (for screenshots)
#   NOBC=1          no broadcast (no carrier, as on the web)
#   CARD=FILE       memory card 1 (kept between runs: tests of the saved pages)
#   SEQ="N [FROM]"  also save every Nth frame (from frame FROM) as OUT_BASENAME_seq_*.png
#   P="a b c"       scenario parameters P1..P3 (default 0)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$3"
FRAMES="$2"
S="$HERE/_scenario_$1_$$.akr"
PP="$(echo ${P:-} 0 0 0)"
printf 'cart "Fair Skies Test", "FAIR-SKIES-TEST"\nconst SCENARIO = %s\nconst SHOT = %s\n' "$1" "${SHOT:-0}" > "$S"
k=1
for v in $PP; do [ $k -le 3 ] && printf 'const P%s = %s\n' $k $v >> "$S"; k=$((k+1)); done
printf 'import "harness.akr"\nimport "../app.akr"\n' >> "$S"
"$ROOT/build/meic" "$S" -o "$OUT.mei" || { rm -f "$S"; exit 1; }
rm -f "$S"
shift 3
if [ -z "$NOBC" ]; then set -- --broadcast "$HERE/fixture.bin" "$@"; fi
if [ -n "$CARD" ]; then set -- --card1 "$CARD" "$@"; fi
if [ -n "$SEQ" ]; then
    set -- --dump-every $(echo $SEQ | cut -d' ' -f1) "${OUT}_seq" --dump-from $(echo "$SEQ 0" | cut -d' ' -f2) "$@"
fi
"$ROOT/build/mei-headless" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" --time 13:00:00 --date 2026-09-30 "$@"
if [ -n "$SEQ" ]; then
    for f in "${OUT}"_seq_*.ppm; do sips -s format png "$f" --out "${f%.ppm}.png" >/dev/null && rm -f "$f"; done
fi
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
rm -f "$OUT.ppm"
