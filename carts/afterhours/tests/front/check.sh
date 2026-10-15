#!/bin/sh
# The front end's scenarios (tests/front/harness.akr; agent E): stage 1 through the title, the
# select, four transitions and the end with the save (60, a release build: it measures the
# budgets), the select's lit rooms and locked silhouette (61), the save's round trip on one card
# across two boots (62, 63), skipping a transition (64), and stage 2 (one room, the platform)
# through the select, its end and its save (65). A scenario passes when it ends with its DONE
# line; stops at the first failure. MEIC, RUN and WORLDS as for tests/run.sh. tests/check.sh
# runs this at its end.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
# the logs and cards go into ../out/front-BUILD (BUILD: the folder MEIC is in), as check.sh does
O="$HERE/../out/front-$(basename "$(dirname "${MEIC:-build/meic}")")"
mkdir -p "$O"
n=0
run() {       # scenario frames [mei-headless args]
    s=$1; fr=$2; shift 2
    "$HERE/run.sh" "$s" "$fr" "$O/s$s" "$@" > "$O/s$s.log" 2>&1 || { echo "FAILED front scenario $s"; grep -E '^(FAIL|assertion|check failed|fault in)' "$O/s$s.log"; tail -3 "$O/s$s.log"; exit 1; }
    grep -q "^DONE $s:" "$O/s$s.log" || { echo "FAILED front scenario $s: it did not finish"; tail -5 "$O/s$s.log"; exit 1; }
    grep "^DONE" "$O/s$s.log"
    n=$((n + 1))
}
card() { rm -f "$O/card$1.mcd"; echo "$O/card$1.mcd"; }
C60="$(card 60)"
TRAP=0 run 60 6400 --card1 "$C60"
grep -h '^BUDGET\|^TRANSITION' "$O/s60.log"
run 61 120 --card1 "$(card 61)"
C62="$(card 62)"
run 62 50 --card1 "$C62"
run 63 5 --card1 "$C62"
run 64 1200 --card1 "$(card 64)"
run 65 3000 --card1 "$(card 65)"
echo "all $n front end scenarios passed"
