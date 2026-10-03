#!/bin/sh
# Usage: tests/run.sh SCENARIO FRAMES OUT_BASENAME [extra mei-headless args]
# Builds the scenario cart (tests/harness.akr + the app), runs it headless against the
# recorded broadcast (tests/fixture.bin, from the gateway's --fixture data) and converts the
# last frame to OUT_BASENAME.png. A failed assert makes mei-headless exit with status 2.
# The shared runner is tools/cart_scenario.sh.
# The recording is remade with
#   python3 tools/meinet/meinet.py --fixture --no-serve --seconds 150 --record carts/weather/tests/fixture.bin
#   SHOT=1          hide the test overlay (for screenshots)
#   NOBC=1          no broadcast (no carrier, as on the web)
#   TAPE=demo       play the sample tape (demo_tape.bin) through the decoder instead
#   CARD=FILE       memory card 1 (kept between runs: tests of the saved pages)
#   NOISE=BER       add bit errors to the broadcast
#   SEQ="N [FROM]"  also save every Nth frame (from frame FROM) as OUT_BASENAME_seq_*.png
#   P="a b c"       scenario parameters P1..P3 (default 0)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PP="$(echo ${P:-} 0 0 0)"
TD=0
if [ "$TAPE" = demo ]; then TD=1; fi
SC_HEAD="$(printf 'cart "Mei Weather Test", "MEI-WEATHER-TEST"\nconst SCENARIO = %s\nconst SHOT = %s\nconst TAPE_DEMO = %s' "$1" "${SHOT:-0}" "$TD")"
k=1
for v in $PP; do [ $k -le 3 ] && SC_HEAD="$SC_HEAD$(printf '\nconst P%s = %s' $k $v)"; k=$((k+1)); done
SCEN="$1"; FRAMES="$2"; OUT="$3"
shift 3
BC="$HERE/fixture.bin"
if [ "$TAPE" = demo ]; then BC="$HERE/../demo_tape.bin"; fi
if [ -z "$NOBC" ]; then set -- --broadcast "$BC" "$@"; fi
if [ -n "$CARD" ]; then set -- --card1 "$CARD" "$@"; fi
if [ -n "$NOISE" ]; then set -- --broadcast-noise "$NOISE" "$@"; fi
SC_HEAD="$SC_HEAD" SC_APP="../app.akr" exec "$HERE/../../../tools/cart_scenario.sh" "$HERE" "$SCEN" "$FRAMES" "$OUT" \
    --time 13:00:00 --date 2026-09-30 "$@"
