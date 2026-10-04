#!/bin/sh
# The movement garden's scenarios (tests/harness.akr): each move run headless with scripted
# input and checked against the tuning. A scenario passes when it ends with its DONE line;
# stops at the first failure. MEIC, RUN and WORLDS are as for tests/run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
n=0
run() {       # scenario frames
    "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.log" 2>&1 || { echo "FAILED scenario $1"; grep -E '^(FAIL|assertion)' "$O/s$1.log"; tail -3 "$O/s$1.log"; exit 1; }
    grep -q "^DONE $1:" "$O/s$1.log" || { echo "FAILED scenario $1: it did not finish"; tail -5 "$O/s$1.log"; exit 1; }
    grep "^DONE" "$O/s$1.log"
    n=$((n + 1))
}
for s in 1 2 3 5 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 28 29 31 32 33 34 35; do
    run $s 260
done
run 4 410
run 6 260
run 27 600
for s in 36 37 38; do
    run $s 100
done
. "$HERE/camera_cases.sh"
. "$HERE/attach_cases.sh"
. "$HERE/shrine_cases.sh"
run 30 510
grep -h '^NOTE' "$O"/s*.log
echo "all $n movement garden scenarios passed"
