#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr and the fight), runs it and converts the last frame
# to PNG, through the shared runner tools/cart_scenario.sh (MEIC, RUN and SEQ as there).
# Scenarios 50-54 (the effects') are built from tests/fx/harness.akr and the whole game, 68 and
# 69 (the Twins') from tests/twins/harness.akr and the whole game.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SC_HEAD="$(printf 'cart "Mech Expo Fight Test", "MECHEXPO-TEST"\nconst SCENARIO = %s' "$1")"
case "$1" in
    5[0-4]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/fx" "$@" ;;
    6[89]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/twins" "$@" ;;
    9[0-9]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/stages" "$@" ;;
esac
SC_HEAD="$SC_HEAD" SC_APP="../fight.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
