#!/bin/sh
# The Animation Kit's test cart: one scene of anim_test.akr.
# Usage: carts/mechexpo/tests/anim/run.sh SCENE FRAMES OUT [mei-headless args]
# Exports the cart's moves with this folder's test moves (anims/) and a copy of anim.akr into
# $DATA (default BUILD/anim-test), builds anim_test.akr with const SCENE = SCENE (and ANIM_F,
# the frame scenes 1-3 hold: $ANIM_F, default 13), runs it FRAMES ticks and writes OUT.png
# (with sips), OUT.csv (--gpu-stats) and OUT.log (the cart's output).
#   B=DIR        the build directory (default build), or MEIC and RUN for the tools
#   SEQ=N        also save every Nth frame as OUT_seq_*.png
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
BUILD="$ROOT/${B:-build}"
MEIC="${MEIC:-$BUILD/meic}"
RUN="${RUN:-$BUILD/mei-headless}"
DATA="${DATA:-$BUILD/anim-test}"
SCENE="$1"; FRAMES="$2"; OUT="$3"
shift 3
mkdir -p "$(dirname "$OUT")"
python3 "$ROOT/tools/mei_anim.py" export -o "$DATA" --extra "$HERE/anims" --runtime > "$DATA.export.json" 2>&1 ||
    { cat "$DATA.export.json"; exit 1; }
S="$DATA/scene_$SCENE.akr"
printf 'cart "Anim test", "MXANIMTEST"\nconst SCENE = %s\nconst ANIM_F = %s\nimport "anim_test.akr"\n' "$SCENE" "${ANIM_F:-13}" > "$S"
"$MEIC" -I "$HERE" -I "$DATA" -I "$ROOT/carts/mechexpo" "$S" -o "$OUT.mei"
if [ -n "$SEQ" ]; then set -- --dump-every "$SEQ" "${OUT}_seq" "$@"; fi
st=0
"$RUN" "$OUT.mei" --frames "$FRAMES" --dump "$OUT.ppm" --gpu-stats "$OUT.csv" "$@" > "$OUT.log" 2>&1 || st=$?
cat "$OUT.log"
command -v sips >/dev/null 2>&1 && {
    sips -s format png "$OUT.ppm" --out "$OUT.png" >/dev/null && rm -f "$OUT.ppm"
    for f in "${OUT}"_seq_*.ppm; do [ -f "$f" ] && sips -s format png "$f" --out "${f%.ppm}.png" >/dev/null && rm -f "$f"; done
}
exit "$st"
