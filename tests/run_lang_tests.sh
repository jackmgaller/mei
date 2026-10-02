#!/bin/sh
# Akari language tests. Each tests/lang/*.akr is compiled with build/meic and run with
# build/mei-headless; its debug output must equal the `// expect: TEXT` lines, in order.
# Directives (anywhere in the file):
#   // frames: N        run N frames (default 2)
#   // pad1: HEX        hold these controller-1 buttons
#   // error: TEXT      compilation must fail with TEXT in the message
#   // cards: N         insert N (1 or 2) blank memory cards
#   // exit: N          the run must end with this exit status (2: a fault, e.g. a failed assert)
#   // flags: ARGS      extra meic arguments (e.g. --release)
#   // warning: TEXT    compilation must succeed with a warning containing TEXT (with one or
#                       more of these, the file must give exactly that many warnings)
# Usage: tests/run_lang_tests.sh [name-filter]   (MEIC=... RUN=... select other builds)
cd "$(dirname "$0")/.." || exit 1
MEIC=${MEIC:-build/meic}
RUN=${RUN:-build/mei-headless}
export MEI_STDLIB="$PWD/stdlib"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/meilang.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
pass=0
fail=0
for t in tests/lang/*.akr tests/lang/*.mls; do
    [ -e "$t" ] || continue
    name=$(basename "$t"); name=${name%.*}
    case "$name" in *"$1"*) ;; *) continue ;; esac
    frames=$(sed -n 's|.*// frames: *\([0-9]*\).*|\1|p' "$t" | head -1)
    pad=$(sed -n 's|.*// pad1: *\([0-9A-Fa-fx]*\).*|\1|p' "$t" | head -1)
    experr=$(sed -n 's|.*// error: *||p' "$t" | head -1)
    cards=$(sed -n 's|.*// cards: *\([12]\).*|\1|p' "$t" | head -1)
    wantrc=$(sed -n 's|.*// exit: *\([0-9]*\).*|\1|p' "$t" | head -1)
    flags=$(sed -n 's|.*// flags: *||p' "$t" | head -1)
    cardargs=""
    if [ -n "$cards" ]; then
        rm -f "$tmp/$name.card1" "$tmp/$name.card2"
        cardargs="--card1 $tmp/$name.card1"
        [ "$cards" = 2 ] && cardargs="$cardargs --card2 $tmp/$name.card2"
    fi
    sed -n 's|.*// expect: \{0,1\}||p' "$t" > "$tmp/expect"
    if [ -n "$experr" ]; then
        if $MEIC "$t" -o "$tmp/$name.mei" 2> "$tmp/err"; then
            echo "FAIL $name: compiled, but expected error: $experr"; fail=$((fail + 1)); continue
        fi
        if grep -qF -- "$experr" "$tmp/err"; then pass=$((pass + 1))
        else echo "FAIL $name: wrong error"; echo "  expected: $experr"; sed 's/^/  got: /' "$tmp/err" | head -3; fail=$((fail + 1)); fi
        continue
    fi
    if ! $MEIC $flags "$t" -o "$tmp/$name.mei" 2> "$tmp/err"; then
        echo "FAIL $name: compile error"; sed 's/^/  /' "$tmp/err" | head -5; fail=$((fail + 1)); continue
    fi
    sed -n 's|.*// warning: *||p' "$t" > "$tmp/expwarn"
    if [ -s "$tmp/expwarn" ]; then
        missing=""
        while IFS= read -r w; do grep -qF -- "$w" "$tmp/err" || missing="$w"; done < "$tmp/expwarn"
        if [ -n "$missing" ]; then
            echo "FAIL $name: missing warning: $missing"; grep 'warning:' "$tmp/err" | sed 's/^/  got: /' | head -5; fail=$((fail + 1)); continue
        fi
        nw=$(grep -c 'warning:' "$tmp/err"); ne=$(wc -l < "$tmp/expwarn")
        if [ "$nw" -ne "$ne" ]; then
            echo "FAIL $name: $nw warnings, expected $ne"; grep 'warning:' "$tmp/err" | sed 's/^/  got: /' | head -8; fail=$((fail + 1)); continue
        fi
    fi
    $RUN "$tmp/$name.mei" --frames "${frames:-2}" ${pad:+--pad1 "$pad"} $cardargs > "$tmp/out" 2> "$tmp/runerr"
    rc=$?
    if [ $rc -ne "${wantrc:-0}" ]; then
        echo "FAIL $name: exit $rc (expected ${wantrc:-0})"; sed 's/^/  /' "$tmp/runerr" | grep -v "^  ran" | head -3; fail=$((fail + 1)); continue
    fi
    if cmp -s "$tmp/expect" "$tmp/out"; then pass=$((pass + 1))
    else
        echo "FAIL $name: output differs (expected < > got)"
        diff "$tmp/expect" "$tmp/out" | head -20 | sed 's/^/  /'
        fail=$((fail + 1))
    fi
done
echo "lang tests: $pass passed, $fail failed"
[ $fail -eq 0 ]
