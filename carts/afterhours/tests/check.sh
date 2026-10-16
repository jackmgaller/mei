#!/bin/sh
# After Hours' scenarios (tests/harness.akr), each run headless with a tape and checked: the
# station's three rooms' solution tapes reach their exits unseen (41-43) and play the stage as
# one run with its totals (46); the tower's legs in order, alone and through transitions (91, 92); every room's framing
# (47); the state flow through a front end (48) and its events (49); Gate 1's platform with its
# three solutions (1, 14, 15); the rules on agent A's stand-in platform (2-11): caught on the tick
# the drawn fan first covers the thief and back at the door, the same tape twice gives the same
# room on every tick, the trains' cone blocking, hearing, the tools, hiding, a train's doors,
# sight's walls, fragile things, the exit and the ghost; on B's platform the catch, the same tape
# twice and the trains again (12, 13, 16), the worst frame's budget (31); the store's rules on
# A's stand-in rooms of doors: keycards, staff doors, re-entry, the run's state, caught at the
# entry door, and the same through a front end's transitions (60-62); B's store tapes, leg by leg,
# as one run (63) and through a front end's transitions (64); the aquarium's rules on A's stand-in
# rooms: the dark and its lights (80), two levels (81), their budget (82); J's aquarium world
# room by room (83); G's dash (70-76). A scenario passes when it ends with its DONE line; stops at
# the first failure. MEIC, RUN and WORLDS are as for tests/run.sh (make test-carts passes the
# build directory's).
#
# PENDING lists solution scenarios whose tapes wait to be re-recorded after a rule change (B's
# job): they are run and reported, and do not stop the check; one that passes says so. None now.
PENDING="${PENDING-}"
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
# the logs go into out/check-BUILD (BUILD: the folder MEIC is in), so that agents checking from
# their own build directories at the same time do not write over each other's
O="$HERE/out/check-$(basename "$(dirname "${MEIC:-build/meic}")")"
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
for s in 41 42 43; do run $s 2400; done
run 46 3400
run 91 9000
run 92 9800
run 47 32
run 48 3800
run 49 3001
grep -h '^RUN' "$O"/s46.log "$O"/s91.log
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
run 60 3000
run 61 3600
run 62 3600
run 63 10600
run 64 11400
run 80 1800
run 81 3400
grep -h '^FRAME two' "$O"/s81.log
run 82 1200
grep -h '^AQUA' "$O"/s82.log
run 83 2400
run 84 100
run 88 400
grep -h '^PREPARE' "$O"/s88.log
run 85 10000
run 86 11000
grep -h '^RUN aquarium' "$O"/s85.log
grep -h '^AQUARIUM' "$O"/s83.log
# agent G's dash (tests/g_dash.akr; NOTES_G.md): distance and timing, its noise, walls mid-dash,
# the same tape twice, sight at every substep, its cycles on B's platform, a dash route in level 1
run 70 200
run 71 200
run 72 200
run 73 1900
run 74 200
run 75 2001
run 76 500
grep -h '^BUDGET' "$O"/s31.log
grep -h '^RUN2' "$O"/s63.log
grep -h '^DASH' "$O"/s75.log
grep -h '^ROUTE' "$O"/s76.log
echo "all $n After Hours scenarios passed"
# E's front end has its own harness (it replaces the hooks this harness replaces too)
if [ -x "$HERE/front/check.sh" ]; then "$HERE/front/check.sh" || exit 1; fi
