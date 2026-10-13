#!/bin/sh
# The balance matrix (mx-balance): every pairing of the six mechs, CPU level 2 against level 2,
# N matches each (default 30, the sides swapped every match), run side by side (JOBS at a time,
# tests/pool.sh), then tests/balance/table.py prints the win rates and each pairing's stats.
#   STAGE=1         on the rooftop (default 0, the hangar)
#   PAIRS="4-7 2-3" only these pairings (Mech's indices: 0 Hero, 1 Double-blade, 2 Beam, 3 Tank,
#                   4 Twins, 7 Shadow); MIRROR=1 adds the mirror matches
#   SEED, N         as tests/balance/run.sh; MEIC and RUN as tools/cart_scenario.sh
# The logs go to tests/out/balance-STAGE-SEED/. A measurement, not a check: it fails only when a
# pairing faults or does not finish.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/../out/balance-${STAGE:-0}-${SEED:-1}"
mkdir -p "$O"
rm -f "$O"/p*.log
POOL_DIR="$O"
. "$HERE/../pool.sh"
pool_report() { :; }
MECHS="0 1 2 3 4 7"
FRAMES="${FRAMES:-16000}"
want() {        # whether pairing $1-$2 is asked for
    [ -z "$PAIRS" ] && return 0
    for p in $PAIRS; do
        if [ "$p" = "$1-$2" ] || [ "$p" = "$2-$1" ]; then return 0; fi
    done
    return 1
}
for ma in $MECHS; do
    for mb in $MECHS; do
        if [ "$ma" -lt "$mb" ] || { [ "$ma" = "$mb" ] && [ -n "$MIRROR" ]; }; then
            want "$ma" "$mb" || continue
            pool_add "p${ma}_$mb" 1 "$HERE/run.sh" "$ma" "$mb" "$FRAMES" "$O/p${ma}_$mb"
        fi
    done
done
pool_run
python3 "$HERE/table.py" "$O"/p*.log
