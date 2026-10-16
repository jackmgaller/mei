#!/bin/sh
# Usage: tests/trans/upper/run.sh FRAMES OUT_BASENAME [extra mei-headless args]
# Scenario 90 (upper/harness.akr) with the game and the front end, through tools/cart_scenario.sh
# (MEIC, RUN, SEQ, TRAP as there; WORLDS the cart's built worlds; TR_HEAD as for ../run.sh).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${WORLDS:-$HERE/../../../../../build/cart-worlds/afterhours}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
SC_HEAD="$(printf 'cart "After Hours Upper Test", "AFTERHOURS-UTEST"\nconst SCENARIO = 90\n%s' "$TR_HEAD")"
SC_HEAD="$SC_HEAD" SC_APP="../../../dr_front.akr" SC_IMPORT="$IMP" exec "$HERE/../../../../../tools/cart_scenario.sh" "$HERE" 90 "$@"
