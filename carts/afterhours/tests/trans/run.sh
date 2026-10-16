#!/bin/sh
# Usage: tests/trans/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# One of the front end's scenarios (tests/front/harness.akr, agent E's) with lines of Akari added
# to its head from $TR_HEAD, which can replace dr_trans.akr's weak settings for a capture:
#   fn tr_style() -> s32 { return TR_STEP }      (TR_PAN, the cart's; TR_STEP; TR_PAIR)
#   fn tr_split_off() -> bool { return true }    (draw as if the rooms' textures shared slots)
#   fn tr_log() -> bool { return true }          (print each frame's camera, triangles, cycles)
# MEIC, RUN, WORLDS, SEQ and TRAP as for tests/front/run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
F="$HERE/../front"
W="${WORLDS:-$HERE/../../../../build/cart-worlds/afterhours}"
IMP=
[ -d "$W" ] && IMP="$(cd "$W" && pwd)"
SC_HEAD="$(printf 'cart "After Hours Transition Test", "AFTERHOURS-TTEST"\nconst SCENARIO = %s\n%s' "$1" "$TR_HEAD")"
SC_HEAD="$SC_HEAD" SC_APP="../../dr_front.akr" SC_IMPORT="$IMP" exec "$HERE/../../../../tools/cart_scenario.sh" "$F" "$@"
