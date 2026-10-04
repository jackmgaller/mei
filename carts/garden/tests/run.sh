#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the game), runs it headless and converts the
# last frame to OUT_BASENAME.png. The world must be built first: make does it for
# build/carts/garden.mei; WORLDS names another build's linked worlds (default
# build/cart-worlds/garden). SHOT and SEQ are as in the shared runner, tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
WORLDS="$(cd "${WORLDS:-$HERE/../../../build/cart-worlds/garden}" && pwd)"
SC_HEAD="$(printf 'cart "Movement Garden Test"\nconst SCENARIO = %s\nconst SHOT = %s' "$1" "${SHOT:-0}")"
SC_HEAD="$SC_HEAD" SC_APP="../game.akr" SC_IMPORT="$WORLDS" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
