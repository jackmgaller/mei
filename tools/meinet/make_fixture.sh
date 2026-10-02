#!/bin/sh
# Regenerates the canned broadcast recording used by the tests (tests/lang/data/broadcast.bin):
# 80 seconds of the --fixture stream (canned data, no network).
cd "$(dirname "$0")/../.." || exit 1
exec python3 tools/meinet/meinet.py --fixture --no-serve --seconds 80 --record tests/lang/data/broadcast.bin
