#!/bin/sh
# Usage: tests/balance/run.sh A B FRAMES OUT [mei-headless args]
# One pairing of tests/balance/harness.akr: mechs A and B (Mech's indices: 0 Hero, 1 Double-blade,
# 2 Beam, 3 Tank, 4 Twins, 7 Shadow), CPU level 2 against level 2, through tools/cart_scenario.sh
# (MEIC, RUN and SEQ as there). The environment sets the rest: N matches (default 30), STAGE (0
# the hangar, 1 the rooftop), SEED (default 1) and TRACE (a match to trace, default -1: none).
# FRAMES is the frames to run; each runs 40 ticks of the fight (1 in the traced match).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SC_HEAD="$(printf 'cart "Mech Expo Balance", "MECHEXPO-BAL"\nconst MA = %s\nconst MB = %s\nconst NMATCH = %s\nconst STAGE = %s\nconst SEED = %s\nconst TRACE = %s' \
    "$1" "$2" "${N:-30}" "${STAGE:-0}" "${SEED:-1}" "${TRACE:--1}")"
a="$1"; b="$2"; shift 2
SC_HEAD="$SC_HEAD" SC_APP="../../fight.akr" exec "$HERE/../../../../tools/cart_scenario.sh" "$HERE" "$a$b" "$@"
