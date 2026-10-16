#!/bin/sh
# Usage: tests/trans/stages/run.sh STAGE FRAMES OUT_BASENAME [extra mei-headless args]
# Scenario 95 (stages/harness.akr) for stage STAGE (a constant of dr_levels.akr, such as
# STAGE_AQUARIUM), with the game and the front end, through tools/cart_scenario.sh (MEIC, RUN,
# SEQ, TRAP as there; WORLDS the cart's built worlds; TR_HEAD as for ../run.sh).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${WORLDS:-$HERE/../../../../../build/cart-worlds/afterhours}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
ST=$1; shift
SC_HEAD="$(printf 'cart "After Hours Stage Test", "AFTERHOURS-STEST"\nconst SCENARIO = 95\nconst STAGE = %s\n%s' "$ST" "$TR_HEAD")"
SC_HEAD="$SC_HEAD" SC_APP="../../../dr_front.akr" SC_IMPORT="$IMP" exec "$HERE/../../../../../tools/cart_scenario.sh" "$HERE" 95 "$@"
