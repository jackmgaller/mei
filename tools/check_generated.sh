#!/bin/sh
# make check-generated: reruns the deterministic generators that need only Python's standard
# library into a temporary directory and compares their output with the committed files, so
# a hand edit to a generated file (or a generator change not rerun) shows up.
# tools/gen_adpcm_vectors.py needs numpy; it is checked when numpy is installed.
cd "$(dirname "$0")/.." || exit 1
tmp=$(mktemp -d "${TMPDIR:-/tmp}/meigen.XXXXXX") || exit 1
trap 'rm -rf "$tmp"' EXIT
fail=0
same() {      # committed generated
    if cmp -s "$1" "$2"; then echo "ok   $1"; else echo "DIFF $1 (rerun its generator, or undo the hand edit)"; fail=1; fi
}
python3 tools/gen_faces_asm.py "$tmp/faces.akr" >/dev/null || fail=1
same stdlib/faces.akr "$tmp/faces.akr"
python3 tools/gen_faces_asm.py --planes "$tmp/planes_faces.akr" >/dev/null || fail=1
same stdlib/planes_faces.akr "$tmp/planes_faces.akr"
python3 tools/gen_faces_asm.py --depth "$tmp/depth_faces.akr" >/dev/null || fail=1
same stdlib/depth_faces.akr "$tmp/depth_faces.akr"
python3 tools/gen_stdlib_data.py "$tmp" >/dev/null || fail=1
same stdlib/font_data.akr "$tmp/font_data.akr"
same stdlib/sin_table.akr "$tmp/sin_table.akr"
cp src/core/audio.c "$tmp/audio.c"
python3 tools/gen_reverb_tables.py "$tmp/audio.c" >/dev/null || fail=1
same src/core/audio.c "$tmp/audio.c"
if python3 -c 'import numpy' 2>/dev/null; then
    python3 tools/gen_adpcm_vectors.py "$tmp/adpcm_vectors.h" >/dev/null || fail=1
    same tests/adpcm_vectors.h "$tmp/adpcm_vectors.h"
else
    echo "skip tests/adpcm_vectors.h (tools/gen_adpcm_vectors.py needs numpy)"
fi
exit $fail
