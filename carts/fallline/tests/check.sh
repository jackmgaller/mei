#!/bin/sh
# The Fall Line checks; stops at the first failure (a fault, a failed assert, or no OK line).
# 2: title, countdown, run. 3: a hazard knocks the sled down. 4: a missed gate adds 2.0 s.
# 5: pause freezes the world. 1: the bot's full run to the finish, with no late frame, under
# 4,000 triangles and within the CPU and GPU budgets (its time and peaks are printed); it writes
# its best run to a fresh memory card. 6: a boot with that card finds the best run and its ghost.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames [mei-headless args]
    s="$1"; f="$2"; shift 2
    "$HERE/run.sh" "$s" "$f" "$O/s$s" "$@" > "$O/s$s.log" 2>&1 || { echo "FAILED scenario $s"; tail -8 "$O/s$s.log"; exit 1; }
    grep -q '^OK' "$O/s$s.log" || { echo "FAILED scenario $s: no OK"; tail -8 "$O/s$s.log"; exit 1; }
    grep -E '^(OK|run time|gates|top speed|peak|late|best|ghost)' "$O/s$s.log"
}
run 2 360
run 3 90
run 4 130
run 5 200
rm -f "$O/card.bin"
run 1 4500 --card1 "$O/card.bin"
run 6 1100 --card1 "$O/card.bin"
echo "all Fall Line checks passed"
