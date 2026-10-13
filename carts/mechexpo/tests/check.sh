#!/bin/sh
# The Mech Expo fight checks (tests/harness.akr lists the scenarios); stops at the first failure
# (a fault, a failed assert, or no OK line). 1 a KO, 2 time up, 3 block and chip, 4 grab beats
# block, 5 grab breaks, 6 and 7 the chains, 8 the kinetic super, 9 the antimatter super and its
# debt, 10 CPU against CPU twice (the same match), 11 the separation limit and the walls, 12 the
# Parry and the anti-air, 13 the ladder's levels, 18 the Vault Throw, 15 training, 14 the budget
# with both mechs drawn; 50-54 the effects through the whole game (tests/fx/harness.akr: hits by
# weight, the kinetic super and a KO, the Void Step and the antimatter super, the waves, CPU
# against CPU), each with the effects' peak cost. MEIC and RUN as in tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames
    s="$1"; f="$2"; shift 2
    "$HERE/run.sh" "$s" "$f" "$O/s$s" "$@" > "$O/s$s.log" 2>&1 || { echo "FAILED scenario $s"; tail -8 "$O/s$s.log"; exit 1; }
    grep -q '^OK' "$O/s$s.log" || { echo "FAILED scenario $s: no OK"; tail -8 "$O/s$s.log"; exit 1; }
    grep -E '^(OK|KO after|time up|chain|meter after|  round|run |rounds|apart|pushed|level|peak)' "$O/s$s.log"
}
run 1 700
run 2 4000
run 3 420
run 4 160
run 5 210
run 6 210
run 7 210
run 8 150
run 9 420
run 10 1000
run 11 2200
run 12 340
run 13 3000
run 18 110
run 15 1500
run 14 1800
run 50 330
run 51 210
run 52 210
run 53 390
run 54 1810
echo "all Mech Expo fight checks passed"
