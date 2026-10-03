#!/bin/sh
# The World Viewer's self-checking run (scenario 1 of tests/harness.akr): both example worlds,
# walking, a layer, a palette variant and a world switch; then two pictures (scenarios 2 and 3)
# that only have to run without a fault. Stops at the first failure.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames
    "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.log" 2>&1 || { echo "FAILED scenario $1"; tail -5 "$O/s$1.log"; exit 1; }
}
run 1 510
grep '^OK' "$O/s1.log"
grep -q '^OK worldview: 13 checks passed' "$O/s1.log" || { echo "FAILED scenario 1: no summary line"; exit 1; }
run 2 30
run 3 30
echo "all World Viewer checks passed"
