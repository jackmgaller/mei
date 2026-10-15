#!/bin/sh
# After Hours' scenarios (tests/harness.akr), each run headless with a tape and checked: level 1's
# five rooms' solution tapes reach their exits unseen (41-45) and play the level as one run with
# its totals (46); Gate 1's platform (the second level) with its three solutions (1, 14, 15); the
# rules on agent A's stand-in platform (2-10): caught on the tick the drawn fan first covers the
# thief and back at the door, the same tape twice gives the same room on every tick, the trains'
# cone blocking lines up with where they are drawn, hearing, the tools, hiding, a train's doors,
# sight's walls, fragile things, the exit and the ghost; on B's platform, the catch, the same
# tape twice and the trains again (12, 13, 16), and the worst frame's budget (31). A scenario
# passes when it ends with its DONE line; stops at the first failure. MEIC, RUN and WORLDS are
# as for tests/run.sh (make test-carts passes the build directory's).
#
# PENDING lists solution scenarios whose tapes wait to be re-recorded after a rule change (B's
# job): they are run and reported, and do not stop the check; one that passes says so. None now.
PENDING="${PENDING-}"
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
n=0
pending() {   # scenario frames: a PENDING scenario is run and reported, never fatal
    case " $PENDING " in
        *" $1 "*)
            if "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.log" 2>&1 && grep -q "^DONE $1:" "$O/s$1.log"; then
                echo "PENDING scenario $1 passes now: take it off PENDING"
            else
                echo "PENDING scenario $1 (its tape waits to be re-recorded): $(grep -m1 -E '^FAIL' "$O/s$1.log")"
            fi
            return 0 ;;
    esac
    run "$1" "$2"
}
run() {       # scenario frames
    "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.log" 2>&1 || { echo "FAILED scenario $1"; grep -E '^(FAIL|assertion|check failed|fault in)' "$O/s$1.log"; tail -3 "$O/s$1.log"; exit 1; }
    grep -q "^DONE $1:" "$O/s$1.log" || { echo "FAILED scenario $1: it did not finish"; tail -5 "$O/s$1.log"; exit 1; }
    grep "^DONE" "$O/s$1.log"
    n=$((n + 1))
}
pending 1 2400
pending 14 2400
pending 15 2400
for s in 41 42 43 44 45; do run $s 1700; done
run 46 5200
run 47 10
grep -h '^RUN' "$O"/s46.log
run 2 400
run 3 3100
run 4 2402
run 5 600
run 6 600
run 7 900
run 8 1000
run 9 10
run 10 300
run 11 1800
run 12 900
run 13 3100
run 16 2402
run 17 700
run 31 2001
grep -h '^BUDGET' "$O"/s31.log
echo "all $n After Hours scenarios passed"
