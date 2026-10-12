#!/bin/sh
# The Animation Kit's checks on Mech Expo 2000; stops at the first failure.
# 1. verify every move: the cart's (anims/), this folder's test moves and the kit's examples.
# 2. scene 5: the runtime's numbers (lengths, active frames, marks, root motion, loops).
# 3. scene 4: two posed mechs within the CPU budget (the worst anim_draw pair is printed).
# B=DIR: the build directory with meic and mei-headless (default build).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
O="$ROOT/${B:-build}/anim-test-out/check"
mkdir -p "$O"
python3 "$ROOT/tools/mei_anim.py" verify "$ROOT"/carts/mechexpo/anims/*/[!_]*.anim.json "$HERE"/anims/*/*.anim.json \
    "$HERE"/examples/*.anim.json > "$O/verify.txt" || { cat "$O/verify.txt"; echo "FAILED verify"; exit 1; }
grep -E ': (PASS|FAIL)' "$O/verify.txt"
run() {       # scene frames
    "$HERE/run.sh" "$1" "$2" "$O/s$1" > "$O/s$1.out" 2>&1 || { echo "FAILED scene $1"; tail -8 "$O/s$1.out"; exit 1; }
    grep -q '^OK' "$O/s$1.out" || { echo "FAILED scene $1: no OK"; tail -8 "$O/s$1.out"; exit 1; }
    grep -E '^(OK|anim_draw)' "$O/s$1.out"
}
run 5 3
run 4 76
worst=$(sed -n 's/^anim_draw x2 worst \([0-9]*\).*/\1/p' "$O/s4.out")
[ "$worst" -lt 500000 ] || { echo "FAILED: two mechs cost $worst CPU cycles (more than half the frame)"; exit 1; }
echo "all Animation Kit checks passed"
