#!/bin/sh
# The movement garden's scenarios (carts/garden/tests/harness.akr) drawn in the ordering table's
# way or in depth mode, with per-frame GPU and CPU statistics: what docs/LANGUAGE.md's depth
# figures were measured with.
# Usage: tests/depth/garden.sh MODE SCENARIO FRAMES OUT_BASENAME
#   MODE ot      the garden as it is (the ordering table)
#        z       render_depth(true) and render_perspective(true): opaque faces nearest first
#        zb2f    the same with opaque faces back to front among the semi-transparent ones
#                (depth.akr's opaque table replaced by its back-to-front one: for comparison)
#        zonly   render_depth(true) alone (affine texturing)
# Writes OUT_BASENAME.csv (mei-headless --gpu-stats), .log and .png. MEIC, RUN and WORLDS as for
# carts/garden/tests/run.sh; summarise with tools/mei_gpustats.py.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/../.."
MODE="$1"; SCEN="$2"; FRAMES="$3"; OUT="$4"
WORLDS="$(cd "${WORLDS:-$ROOT/build/cart-worlds/garden}" && pwd)"
HEAD="$(printf 'cart "Movement Garden Test"\nconst SCENARIO = %s\nconst SHOT = 1' "$SCEN")"
case "$MODE" in
    ot) ;;
    z) HEAD="$HEAD
import \"depth.akr\"
var __dm: bool = __dm_start()
fn __dm_start() -> bool { render_depth(true); render_perspective(true); return true }" ;;
    zb2f) HEAD="$HEAD
import \"depth.akr\"
var __dm: bool = __dm_start()
fn __dm_start() -> bool { render_depth(true); render_perspective(true); __z_tab[0] = __z_tab[1]; return true }" ;;
    zonly) HEAD="$HEAD
import \"depth.akr\"
var __dm: bool = __dm_start()
fn __dm_start() -> bool { render_depth(true); return true }" ;;
    *) echo "unknown mode $MODE"; exit 1 ;;
esac
SC_HEAD="$HEAD" SC_APP="../game.akr" SC_IMPORT="$WORLDS" \
    "$ROOT/tools/cart_scenario.sh" "$ROOT/carts/garden/tests" "$SCEN" "$FRAMES" "$OUT" --gpu-stats "$OUT.csv" > "$OUT.log" 2>&1
