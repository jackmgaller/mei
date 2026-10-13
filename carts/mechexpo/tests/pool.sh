# Runs a check suite's scenarios JOBS at a time (default: the machine's CPU count), then reports
# them in the order they were added and stops at the first that failed (a fault, a failed
# assert, or no OK line). Sourced by check.sh, budget.sh and menus/check.sh, which set POOL_DIR
# (where each scenario's NAME.log goes) and define pool_report NAME (what a passing scenario
# prints from its log).
#   pool_add NAME COST CMD...   a scenario: CMD writes nothing itself; its output goes to
#                               POOL_DIR/NAME.log. COST is a rough run time: the costliest
#                               start first, so the long ones don't finish last
#   pool_run                    runs every scenario added, then reports
# Each scenario builds and runs its own cart (tools/cart_scenario.sh names its temporary files
# by process), so they can run side by side. JOBS=1 runs them one at a time.

POOL_JOBS="$POOL_DIR/.jobs"
rm -rf "$POOL_JOBS"
mkdir -p "$POOL_JOBS"
: > "$POOL_JOBS/order"
: > "$POOL_JOBS/cost"

# One argument, single-quoted for sh.
pool_q() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

pool_add() {    # NAME COST CMD...
    n="$1"; c="$2"; shift 2
    {
        for a in "$@"; do pool_q "$a"; printf ' '; done
        printf '> %s 2>&1\n' "$(pool_q "$POOL_DIR/$n.log")"
        printf 'echo $? > %s\n' "$(pool_q "$POOL_JOBS/$n.rc")"
    } > "$POOL_JOBS/$n.sh"
    echo "$n" >> "$POOL_JOBS/order"
    echo "$c $n" >> "$POOL_JOBS/cost"
}

pool_run() {
    j="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
    sort -rn "$POOL_JOBS/cost" | while read -r c n; do printf '%s\0' "$POOL_JOBS/$n.sh"; done \
        | xargs -0 -n 1 -P "$j" sh
    while read -r n; do
        rc="$(cat "$POOL_JOBS/$n.rc" 2>/dev/null || echo missing)"
        if [ "$rc" != 0 ]; then
            echo "FAILED $n"; tail -8 "$POOL_DIR/$n.log"; exit 1
        fi
        grep -q '^OK' "$POOL_DIR/$n.log" || { echo "FAILED $n: no OK"; tail -8 "$POOL_DIR/$n.log"; exit 1; }
        pool_report "$n"
    done < "$POOL_JOBS/order"
}
