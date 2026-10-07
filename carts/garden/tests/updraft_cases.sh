# The shrine town's updraft scenarios (updraft_cases.akr), sourced by check.sh: one `run SCENARIO FRAMES` line each.
run 640 3000
run 641 3000
for s in 642 643 644 645; do
    run $s 4500
done
run 646 6000
run 647 900
run 648 380
