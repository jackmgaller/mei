#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart into the scratch dir, runs it and converts the dump to PNG.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$3"
FRAMES="$2"
S="$HERE/_scenario.akr"
printf 'cart "Lantern Test"\nconst SCENARIO = %s\nconst SHOT = %s\nconst SEEDV = %s\nconst BOTV = %s\nimport "harness.akr"\nimport "../game.akr"\n' "$1" "${SHOT:-0}" "${SEED:-0}" "${BOT:-0}" > "$S"
"$ROOT/build/meic" "$S" -o "$OUT.mei"
rm -f "$S"
shift 3
"$ROOT/build/mei-headless" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" "$@"
sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null
