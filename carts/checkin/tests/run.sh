#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the game), runs it headless, converts the dump.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$3"
FRAMES="$2"
S="$HERE/_scenario_$1_$$.akr"
printf 'cart "Check-In Test", "CHECK-IN"\nconst SCENARIO = %s\nconst SHOT = %s\nimport "harness.akr"\nimport "../game.akr"\n' "$1" "${SHOT:-0}" > "$S"
"$ROOT/build/meic" "$S" -o "$OUT.mei" || { rm -f "$S"; exit 1; }
rm -f "$S"
shift 3
"$ROOT/build/mei-headless" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" "$@"
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
