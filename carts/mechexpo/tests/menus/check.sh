#!/bin/sh
# The Mech Expo menu checks (tests/menus/harness.akr lists the scenarios 55-59 and their views):
# each renders a screen to tests/out/menus/mSCENARIO_VIEW.png, checks what it shows and that the
# frames stayed within the CPU and GPU budgets. Run side by side (JOBS at a time, ../pool.sh) and
# reported in this order; stops at the first failure. MEIC and RUN as in tools/cart_scenario.sh.
# Scenario 59's runs get a memory card each (tests/out/menus/card*.bin, made fresh).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/../out/menus"
mkdir -p "$O"
POOL_DIR="$O"
. "$HERE/../pool.sh"
pool_report() { grep '^OK' "$O/$1.log"; }
run() {       # scenario view frames [mei-headless args]
    s="$1"; v="$2"; f="$3"; shift 3
    pool_add "m${s}_$v" "$f" "$HERE/run.sh" "$s" "$v" "$f" "$O/m${s}_$v" "$@"
}
card() { rm -f "$O/card$1.bin"; echo "$O/card$1.bin"; }
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
run 59 0 131 --card1 "$(card 0)"
run 59 1 131 --card1 "$(card 1)"
run 59 2 131 --card1 "$(card 2)"
run 59 3 131 --card1 "$(card 3)"
run 59 4 131
pool_run
echo "all Mech Expo menu checks passed"
