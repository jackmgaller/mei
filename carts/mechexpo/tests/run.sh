#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr and the fight), runs it and converts the last frame
# to PNG, through the shared runner tools/cart_scenario.sh (MEIC, RUN and SEQ as there).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SC_HEAD="$(printf 'cart "Mech Expo Fight Test", "MECHEXPO-TEST"\nconst SCENARIO = %s' "$1")"
SC_HEAD="$SC_HEAD" SC_APP="../fight.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
