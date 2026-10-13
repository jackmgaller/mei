#!/bin/sh
# The Mech Expo menu checks (tests/menus/harness.akr lists the scenarios 55-59 and their views):
# each renders a screen to tests/out/menus/mSCENARIO_VIEW.png, checks what it shows and that the
# frames stayed within the CPU and GPU budgets. Stops at the first failure. MEIC and RUN as in
# tools/cart_scenario.sh. Scenario 59's runs get a memory card (tests/out/menus/card*.bin, made fresh).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/../out/menus"
mkdir -p "$O"
run() {       # scenario view frames [mei-headless args]
    s="$1"; v="$2"; f="$3"; shift 3
    "$HERE/run.sh" "$s" "$v" "$f" "$O/m${s}_$v" "$@" > "$O/m${s}_$v.log" 2>&1 \
        || { echo "FAILED menu scenario $s.$v"; tail -8 "$O/m${s}_$v.log"; exit 1; }
    grep -q '^OK' "$O/m${s}_$v.log" || { echo "FAILED menu scenario $s.$v: no OK"; tail -8 "$O/m${s}_$v.log"; exit 1; }
    grep '^OK' "$O/m${s}_$v.log"
}
card() { rm -f "$O/card$1.bin"; echo "--card1 $O/card$1.bin"; }
run 55 0 91
run 55 1 91
run 56 0 61
run 56 1 61
run 56 2 61
run 57 0 151
run 57 1 61
run 57 2 91
run 57 3 151
run 58 0 61
run 58 1 61
run 58 2 61
run 58 3 61
run 59 0 131 $(card 0)
run 59 1 131 $(card 1)
run 59 2 131 $(card 2)
run 59 3 131 $(card 3)
run 59 4 131
echo "all Mech Expo menu checks passed"
