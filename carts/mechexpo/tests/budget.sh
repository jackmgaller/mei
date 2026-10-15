#!/bin/sh
# The Mech Expo budget checks: long CPU-against-CPU runs that measure each pairing's busiest
# frame against the CPU and GPU budgets (and assert them), run side by side as check.sh's
# scenarios are (tests/pool.sh). 14 both MVP mechs drawn, 39 Beam against each mech, 49 Tank
# against each, 54 the effects at their busiest, 69 three bodies (the split Twins against Tank),
# 98 and 99 the rooftop, 109 Shadow with its mine, bolt, curse and super (against the split
# Twins, then Beam), 147-149 the container port (the Hero against the Double-blade Hero, the
# split Twins against Tank, Shadow against the split Twins), 162 Seraph with its bolt, the mark
# and Judgement kept out (against the split Twins on the rooftop, then Shadow in the hangar),
# 168 the same against the split Twins on the container port, 198 Seraph's effects at their
# heaviest (against the split Twins on the container port, both marked: a wave sent back by the
# ward and, while it flies, Judgement's flash, lock and column; tests/seraph/harness.akr), 202
# Gamma with a full Volt Orb out and its super (against the split Twins on the rooftop, then on
# the container port), 249 Gamma's effects at their heaviest (tests/gamma_fx/harness.akr: the
# ray held hot against Seraph's Wing Ward on the container port, then against the split Twins
# there with Ground Zero every 300 frames). make
# test-carts runs them after check.sh. MEIC and RUN as in tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
POOL_DIR="$O"
. "$HERE/pool.sh"
pool_report() {
    grep -E '^(OK|peak|late|Beam against|Tank and|Twins|frames split|Shadow against|Seraph against|Seraph.s effects|reflects|Gamma against|Gamma.s effects|Ground Zeros|supers|Total Eclipses|blurb)' "$O/$1.log"
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
run 109 1801
run 147 1801
run 148 1801
run 149 2400
run 162 1801
run 168 901
run 198 1001
run 202 1801
run 249 1801
pool_run
echo "all Mech Expo budget checks passed"
