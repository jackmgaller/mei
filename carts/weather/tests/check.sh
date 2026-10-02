#!/bin/sh
# Runs every self-checking scenario against the recorded fixture; stops at the first failure.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames [env...]
    s="$1"; f="$2"; shift 2
    env "$@" "$HERE/run.sh" "$s" "$f" "$O/s$s" > "$O/s$s.log" 2>&1 || { echo "FAILED scenario $s"; cat "$O/s$s.log"; exit 1; }
    grep -E "^OK|^PERF" "$O/s$s.log" || { echo "scenario $s did not report"; exit 1; }
}
run 1 601
run 2 1501
run 3 1501
run 4 8001
run 5 8901
run 6 301
run 7 601
run 8 301
run 9 4600
run 10 1801 NOBC=1
run 11 601
run 12 4950
run 13 1801 NOISE=0.0005
run 15 3701
run 20 4800 P="5 4700"
run 20 4800 P="8 4700"
rm -f "$O/card.mcd"
run 19 2600 CARD="$O/card.mcd"
run 10 700 NOBC=1 P=1 CARD="$O/card.mcd"
echo "all Mei Weather scenarios passed"
