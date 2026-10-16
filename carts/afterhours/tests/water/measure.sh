#!/bin/sh
# Agent W's before and after (NOTES_W.md, "Numbers"): scenario 97 (harness.akr) for every stage of
# rooms, release builds, side by side: with BUILD's worlds and the water moving (after), and, when
# BASE_WORLDS names a copy of the worlds as they were before the water, with those worlds and the
# water still (before). Prints each stage's rooms in play, its transitions and water_tick()'s own
# cost. MEIC, RUN and WORLDS as for run.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
B="$(dirname "${MEIC:-build/meic}")"
O="$HERE/../out/water-$(basename "$B")"
mkdir -p "$O"
STAGES="STAGE_STATION:4000 STAGE_TOWER:10000 STAGE_AQUARIUM:11500 STAGE_STORE:12500"
for st in $STAGES; do
    n=${st%%:*}; fr=${st##*:}
    TRAP=0 "$HERE/run.sh" "$n" "$fr" "$O/after_$n" > "$O/after_$n.log" 2>&1 &
    if [ -n "$BASE_WORLDS" ]; then
        TRAP=0 WORLDS="$BASE_WORLDS" W_HEAD='fn water_enabled() -> bool { return false }' \
            "$HERE/run.sh" "$n" "$fr" "$O/before_$n" > "$O/before_$n.log" 2>&1 &
    fi
done
wait
for st in $STAGES; do
    n=${st%%:*}
    for w in before after; do
        [ -f "$O/${w}_$n.log" ] || continue
        grep -q "^DONE 97" "$O/${w}_$n.log" || { echo "FAILED $w $n"; tail -5 "$O/${w}_$n.log"; exit 1; }
        echo "== $n, $w"
        grep -E "^(ROOM|TRANS|WORST|WATER)" "$O/${w}_$n.log"
    done
done
