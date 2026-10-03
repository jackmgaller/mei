#!/bin/sh
# make's handling of carts that use worlds (docs/WORLDKIT.md, "Using a world in a cart"), checked
# on World Viewer (carts/worldview/worlds.txt). make test-carts runs it once it has built
# $B/carts/worldview.mei. Nothing in the repository changes: make -W pretends a file was edited,
# and the recipes edited below are copies in $B/world-carts-test/.
# - With nothing edited, the cart and its worlds are up to date.
# - An edit to a world's recipe, cell file, game schema, ID lock file or asset recipe rebuilds
#   that world only, and the cart; an edit to the kit rebuilds both worlds; an edit to the cart's
#   own source rebuilds the cart only; an unrelated edit rebuilds nothing.
# - An invalid recipe fails with the kit's error, readably.
# - Two worlds of one game share one GAME.game.akr and a cart compiles against both; two worlds
#   of one game name built from different schemas are refused.
# Usage: tests/world_carts.sh   (B=DIR for another build directory, MAKE for another make)
set -e
cd "$(dirname "$0")/.." || exit 1
B="${B:-build}"
MAKE="${MAKE:-make}"
CART="$B/carts/worldview.mei"
ROOM=examples/worlds/test_room
CITY=examples/worlds/two_districts
fail() { echo "FAILED: $*"; exit 1; }

"$MAKE" -s -q B="$B" "$CART" || fail "$CART is not up to date (build it first)"
echo "ok   up to date"

# what make would run if FILE were edited: which worlds it builds and whether it compiles the cart
plan() { "$MAKE" -n B="$B" -W "$1" "$CART" 2>/dev/null; }
expect() {      # file worlds(room|city|both|none) cart(yes|no)
    out="$(plan "$1")"
    room=no; city=no; cart=no
    echo "$out" | grep -q "world_cart.py build $ROOM/" && room=yes
    echo "$out" | grep -q "world_cart.py build $CITY/" && city=yes
    echo "$out" | grep -q "meic carts/worldview/worldview.akr" && cart=yes
    case "$2" in
        room) [ $room = yes ] && [ $city = no ] ;;
        city) [ $room = no ] && [ $city = yes ] ;;
        both) [ $room = yes ] && [ $city = yes ] ;;
        none) [ $room = no ] && [ $city = no ] ;;
    esac || fail "editing $1: expected worlds '$2', make would build test_room: $room, two_districts: $city"
    [ $cart = "$3" ] || fail "editing $1: expected the cart to rebuild: $3, make would: $cart"
    echo "ok   $1: worlds $2, cart $3"
}
expect $ROOM/test_room.world.json room yes
expect $ROOM/garden.game.mochi room yes
expect $ROOM/test_room.ids.json room yes
expect $ROOM/assets/ramp.asset.json room yes
expect $CITY/cells/shrine_gate.cell.json city yes
expect $CITY/cells city yes
expect $CITY/assets/torii.asset.json city yes
expect tools/worldkit/pack.py both yes
expect carts/worldview/viewer.akr none yes
expect carts/worldview/worlds.txt none yes
expect README.md none no
expect carts/orbs/orbs.akr none no

T="$B/world-carts-test"
rm -rf "$T"
mkdir -p "$T"
cp -R $ROOM "$T/bad"
python3 -c "
import json, sys
p = sys.argv[1]; w = json.load(open(p))
w['cells'][0]['placements'][1]['asset'] = 'no_such_asset'
json.dump(w, open(p, 'w'), indent=2)" "$T/bad/test_room.world.json"
if python3 tools/world_cart.py build "$T/bad/test_room.world.json" "$B" > "$T/bad.log" 2>&1; then
    fail "an invalid recipe built"
fi
grep -q "the World Kit refused it" "$T/bad.log" && grep -q "/cells/0/placements/1/asset" "$T/bad.log" \
    || { cat "$T/bad.log"; fail "an invalid recipe's error is not reported"; }
echo "ok   an invalid recipe fails:"
sed 's/^/       /' "$T/bad.log"

# Two worlds of the game "garden": test_room and a copy named test_room_b.
cp -R $ROOM "$T/a"
cp -R $ROOM "$T/b"
rm "$T/b/test_room.ids.json"
mv "$T/b/test_room.world.json" "$T/b/test_room_b.world.json"
python3 -c "
import json, sys
p = sys.argv[1]; w = json.load(open(p))
w['name'] = 'test_room_b'
json.dump(w, open(p, 'w'), indent=2)" "$T/b/test_room_b.world.json"
python3 tools/world_cart.py build "$T/a/test_room.world.json" "$B" > /dev/null || fail "building $T/a"
python3 tools/world_cart.py build "$T/b/test_room_b.world.json" "$B" > /dev/null || fail "building $T/b"
python3 tools/world_cart.py link "$T/import" "$B" "$T/a/test_room.world.json" "$T/b/test_room_b.world.json" \
    || fail "linking two worlds of one game"
printf '%s\n' 'import "test_room.akr"' 'import "test_room_b.akr"' \
    'fn init() {' '    assert(world_test_room_load())' '    assert(world_test_room_b_load())' \
    '    print_int(GARDEN_TYPES)' '    println(" types")' '}' > "$T/two.akr"
"$B/meic" -I "$T/import" "$T/two.akr" -o "$T/two.mei" || fail "a cart importing two worlds of one game"
"$B/mei-headless" "$T/two.mei" --frames 2 2>/dev/null | grep -q "^2 types" || fail "running a cart with two worlds of one game"
echo "ok   two worlds of one game share $T/import/garden.game.akr"

printf '\ntype extra\n' >> "$T/b/garden.game.mochi"
python3 tools/world_cart.py build "$T/b/test_room_b.world.json" "$B" > /dev/null || fail "rebuilding $T/b"
if python3 tools/world_cart.py link "$T/import" "$B" "$T/a/test_room.world.json" "$T/b/test_room_b.world.json" \
    > "$T/link.log" 2>&1; then
    fail "two worlds of game garden with different schemas were linked"
fi
grep -q "different game schemas" "$T/link.log" || { cat "$T/link.log"; fail "the schema mismatch is not reported"; }
echo "ok   two different schemas of one game are refused: $(cat "$T/link.log")"
rm -rf "$T" "$B/worlds/$T"
echo "all world cart checks passed"
