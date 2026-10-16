#!/bin/sh
# The transition's checks (agent H): every two rooms a way out joins have their textures in
# different slots (check_slots.py, on BUILD's reports: BUILD is the folder MEIC is in); scenario
# 90, the aquarium's doors on rooms' upper levels (upper/harness.akr); and scenario 95 for each
# stage of rooms (stages/harness.akr: the station, the tower, the aquarium, the store, run side by
# side), every transition handing over exactly and no transition frame within 15% of the budgets
# (release builds). E's front end scenarios (tests/front/check.sh) check the station's and the
# store's from the title. MEIC, RUN and WORLDS as for tests/front/run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
B="$(dirname "${MEIC:-build/meic}")"
O="$HERE/../out/trans-$(basename "$B")"
mkdir -p "$O"
python3 "$HERE/check_slots.py" "$B"
"$HERE/upper/run.sh" 400 "$O/s90" > "$O/s90.log" 2>&1 || { echo "FAILED scenario 90"; grep -E '^(FAIL|assertion|check failed|fault in)' "$O/s90.log"; tail -3 "$O/s90.log"; exit 1; }
grep -q "^DONE 90" "$O/s90.log" || { echo "FAILED scenario 90: it did not finish"; tail -5 "$O/s90.log"; exit 1; }
grep -h "^BUDGET\|^DONE" "$O/s90.log"
st() {        # stage frames
    TRAP=0 "$HERE/stages/run.sh" "$1" "$2" "$O/s95_$1" > "$O/s95_$1.log" 2>&1 || true
}
st STAGE_STATION 4000 & st STAGE_TOWER 10000 & st STAGE_AQUARIUM 11500 & st STAGE_STORE 12500 & wait
for s in STAGE_STATION STAGE_TOWER STAGE_AQUARIUM STAGE_STORE; do
    grep -q "^DONE 95" "$O/s95_$s.log" || { echo "FAILED scenario 95 ($s)"; grep -E '^(FAIL|assertion|check failed|fault in|BUDGET)' "$O/s95_$s.log"; tail -3 "$O/s95_$s.log"; exit 1; }
    printf '%s: ' "$s"; grep -h "^BUDGET" "$O/s95_$s.log"
done
