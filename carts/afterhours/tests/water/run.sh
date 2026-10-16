#!/bin/sh
# Usage: tests/water/run.sh STAGE FRAMES OUT_BASENAME [extra mei-headless args]
# Agent W's measure (harness.akr): stage STAGE (a constant of dr_levels.akr) played through the
# front end's transitions on its solution tapes, the worst frame per room in play and per
# transition printed. Through tools/cart_scenario.sh (MEIC, RUN, SEQ, TRAP as there; WORLDS the
# cart's built worlds). W_HEAD adds lines to the scenario's head (W_OFF: the water still).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${WORLDS:-$HERE/../../../../build/cart-worlds/afterhours}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
ST=$1; shift
SC_HEAD="$(printf 'cart "After Hours Water Test", "AFTERHOURS-WTEST"\nconst SCENARIO = 97\nconst STAGE = %s\n%s' "$ST" "$W_HEAD")"
SC_HEAD="$SC_HEAD" SC_APP="../../dr_front.akr" SC_IMPORT="$IMP" exec "$HERE/../../../../tools/cart_scenario.sh" "$HERE" 97 "$@"
