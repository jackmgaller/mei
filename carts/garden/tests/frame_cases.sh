# The shrine town's frame (DESIGN.md 12.9), sourced by check.sh: the frame's rule over every point
# of the edges (carts/garden/shrinetown/tools/frame.py, on the built world: NumPy), then the
# scenarios (frame_cases.akr): the review's leaks, then every 8 m of each edge (frame_probes.akr,
# from tools/frame.py --probes).
FRAME_B="$(cd "${WORLDS:-$HERE/../../../build/cart-worlds/garden}/../.." && pwd)"
python3 "$HERE/../shrinetown/tools/frame.py" --build-dir "$FRAME_B" > "$O/frame.txt" 2>&1 || {
    echo "FAILED the frame's rule (carts/garden/shrinetown/tools/frame.py)"; tail -12 "$O/frame.txt"; exit 1; }
tail -2 "$O/frame.txt"
run 580 2100
run 581 8000
run 582 8000
run 583 9600
run 584 9600
