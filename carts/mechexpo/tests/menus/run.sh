#!/bin/sh
# Usage: tests/menus/run.sh SCENARIO VIEW FRAMES OUT_BASENAME [extra mei-headless args]
# Builds a menu scenario cart (tests/menus/harness.akr and the whole game, ../../game.akr), runs
# it and writes the last frame as OUT_BASENAME.png, through tools/cart_scenario.sh (MEIC, RUN,
# SEQ and TRAP as there). Where there is no sips, python3 with Pillow converts the pictures.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SCEN="$1"; VIEW="$2"; FRAMES="$3"; OUT="$4"
shift 4
SC_HEAD="$(printf 'cart "Mech Expo Menu Test", "MECHEXPO-TEST"\nconst SCENARIO = %s\nconst VIEW = %s' "$SCEN" "$VIEW")"
KEEP_PPM=1 SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" "$HERE/../../../../tools/cart_scenario.sh" \
    "$HERE" "${SCEN}_$VIEW" "$FRAMES" "$OUT" "$@"
for f in "$OUT".ppm "$OUT"_seq_*.ppm; do
    [ -f "$f" ] || continue
    if python3 -c 'import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])' \
        "$f" "${f%.ppm}.png" 2>/dev/null; then rm -f "$f"; fi
done
