#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the game, dr_game.akr), runs it headless and
# converts the last frame to OUT_BASENAME.png, through the shared runner tools/cart_scenario.sh
# (MEIC, RUN, SEQ, SHOT and TRAP as there). WORLDS names the cart's built worlds (default
# build/cart-worlds/dorobo), passed to meic with -I when the folder exists.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${WORLDS:-$HERE/../../../build/cart-worlds/dorobo}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
SC_HEAD="$(printf 'cart "Dorobo Test", "MEI-DOROBO-TEST"\nconst SCENARIO = %s\nconst SHOT = %s' "$1" "${SHOT:-0}")"
SC_HEAD="$SC_HEAD" SC_APP="../dr_game.akr" SC_IMPORT="$IMP" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
