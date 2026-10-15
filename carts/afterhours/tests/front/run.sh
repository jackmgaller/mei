#!/bin/sh
# Usage: tests/front/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds one of the front end's scenarios (tests/front/harness.akr with the game and dr_front.akr)
# and runs it headless through tools/cart_scenario.sh (MEIC, RUN, SEQ, SHOT and TRAP as there).
# WORLDS names the cart's built worlds (default build/cart-worlds/afterhours).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${WORLDS:-$HERE/../../../../build/cart-worlds/afterhours}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
SC_HEAD="$(printf 'cart "After Hours Front Test", "AFTERHOURS-FTEST"\nconst SCENARIO = %s' "$1")"
SC_HEAD="$SC_HEAD" SC_APP="../../dr_front.akr" SC_IMPORT="$IMP" exec "$HERE/../../../../tools/cart_scenario.sh" "$HERE" "$@"
