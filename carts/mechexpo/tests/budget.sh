#!/bin/sh
# The Mech Expo budget checks: long CPU-against-CPU runs that measure each pairing's busiest
# frame against the CPU and GPU budgets (and assert them), run side by side as check.sh's
# scenarios are (tests/pool.sh). 14 both MVP mechs drawn, 39 Beam against each mech, 49 Tank
# against each, 54 the effects at their busiest, 69 three bodies (the split Twins against Tank),
# 98 and 99 the rooftop. make test-carts runs them after check.sh. MEIC and RUN as in
# tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
POOL_DIR="$O"
. "$HERE/pool.sh"
pool_report() {
    grep -E '^(OK|peak|late|Beam against|Tank and|Twins|frames split)' "$O/$1.log"
}
run() {       # scenario frames (all through drawn mechs: the cost is the frames)
    pool_add "s$1" "$2" "$HERE/run.sh" "$1" "$2" "$O/s$1"
}
run 14 1800
run 39 1800
run 49 1800
run 54 1810
run 69 1800
run 98 1801
run 99 1801
pool_run
echo "all Mech Expo budget checks passed"
