#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart into the scratch dir, runs it and converts the dump to PNG
# (keeping the PPM). SHOT, SEED and BOT set the harness's constants of those names; SEQ is as
# in the shared runner, tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SC_HEAD="$(printf 'cart "Lantern Test"\nconst SCENARIO = %s\nconst SHOT = %s\nconst SEEDV = %s\nconst BOTV = %s' "$1" "${SHOT:-0}" "${SEED:-0}" "${BOT:-0}")"
SC_HEAD="$SC_HEAD" SC_APP="../game.akr" KEEP_PPM=1 exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$@"
