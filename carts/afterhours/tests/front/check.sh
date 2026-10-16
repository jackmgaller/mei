#!/bin/sh
# The front end's scenarios (tests/front/harness.akr; agent E): the station through the title,
# the select, its transitions and the end with the save (60, a release build: it measures the
# budgets), the select's lit rooms and locked silhouette (61), the save's round trip on one card
# across two boots (62, 63), skipping a transition (64), the platform stage (one room, the last)
# through the select, its end and its save (65), the stages of doors from the select through
# their legs, their transitions (back into lower rooms too), their ends and saves: the store (66),
# the aquarium (67), the tower (69), and every stage's select frames well within the budgets
# (68); 66-69 are release builds. The pause: a tape replays the same with a pause in the middle,
# the room's state and clock frozen while paused (70, a release build), each row does what it says
# and SELECT restarts at once (71), every paused frame on the aquarium within the budgets (72, a
# release build; the select's playtest unlock opens it). (73 is shots.sh's, not run here.) First, no world may take the fonts' texture slot or palettes
# (check_worlds.py; 60 and 65-69 then check the fonts in VRAM on every select, transition and
# end frame). A scenario passes when it ends with its DONE line; stops at the first failure.
# MEIC, RUN, WORLDS as for tests/run.sh; PENDING (default none) lists the scenarios run and
# reported but not fatal. tests/check.sh runs this at its end.
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
# first: no world takes the fonts' texture slot or palettes (the worlds' build reports)
W="${WORLDS:-$HERE/../../../../build/cart-worlds/afterhours}"
python3 "$HERE/check_worlds.py" "$W" || exit 1
C60="$(card 60)"
TRAP=0 run 60 6400 --card1 "$C60"
grep -h '^BUDGET\|^TRANSITION' "$O/s60.log"
run 61 120 --card1 "$(card 61)"
C62="$(card 62)"
run 62 50 --card1 "$C62"
run 63 5 --card1 "$C62"
run 64 1200 --card1 "$(card 64)"
run 65 3000 --card1 "$(card 65)"
TRAP=0 run 66 12500 --card1 "$(card 66)"
grep -h '^BUDGET\|^TRANSITION' "$O/s66.log"
# a scenario in PENDING (none now) is run and reported, not fatal (67 was, until J's tapes cleared
# in the cart)
TRAP=0 run 69 12000 --card1 "$(card 69)"
grep -h '^BUDGET\|^TRANSITION' "$O/s69.log"
TRAP=0 run 68 300 --card1 "$(card 68)"
grep -h '^SELECT\|^BUDGET' "$O/s68.log"
TRAP=0 run 70 1500 --card1 "$(card 70)"
run 71 6000 --card1 "$(card 71)"
TRAP=0 run 72 1500 --card1 "$(card 72)"
grep -h '^BUDGET' "$O/s72.log"
case " ${PENDING-} " in
    *" 67 "*)
        if TRAP=0 "$HERE/run.sh" 67 14000 "$O/s67" --card1 "$(card 67)" > "$O/s67.log" 2>&1 && grep -q "^DONE 67:" "$O/s67.log"; then
            echo "PENDING front scenario 67 passes now: take it off PENDING"
        else
            echo "PENDING front scenario 67 (the aquarium's tapes): $(grep -m1 -E '^FAIL' "$O/s67.log")"
        fi ;;
    *)
        TRAP=0 run 67 14000 --card1 "$(card 67)"
        grep -h '^BUDGET\|^TRANSITION' "$O/s67.log" ;;
esac
echo "all $n front end scenarios passed"
