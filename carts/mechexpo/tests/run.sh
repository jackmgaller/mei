#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr and the fight), runs it and converts the last frame
# to PNG, through the shared runner tools/cart_scenario.sh (MEIC, RUN and SEQ as there).
# Scenarios 50-54 (the effects') are built from tests/fx/harness.akr and the whole game, 68 and
# 69 (the Twins') from tests/twins/harness.akr and the whole game, 80-89 (the sounds') from
# tests/sfx/harness.akr and the whole game, 90-99, 112-115 and 140-150 (the stages') from
# tests/stages/harness.akr and the whole game, 116-127 (the arcade ladder's) through
# tests/ladder/run.sh (VIEW 0; that script takes a VIEW).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SC_HEAD="$(printf 'cart "Mech Expo Fight Test", "MECHEXPO-TEST"\nconst SCENARIO = %s' "$1")"
case "$1" in
    5[0-4]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/fx" "$@" ;;
    6[89]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/twins" "$@" ;;
    8[0-9]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/sfx" "$@" ;;
    109) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/shadow" "$@" ;;
    16[2-8]) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/seraph" "$@" ;;
    11[6-9]|12[0-7]) S="$1"; shift; exec "$HERE/ladder/run.sh" "$S" 0 "$@" ;;   # mx-ladder: VIEW 0
    9[0-9]|11[2-5]|14[0-9]|150) SC_HEAD="$SC_HEAD" SC_APP="../../game.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE/stages" "$@" ;;
esac
SC_HEAD="$SC_HEAD" SC_APP="../fight.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
