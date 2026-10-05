# The goals' scenarios (goals_cases.akr), sourced by check.sh: one `run SCENARIO FRAMES` line each.
run 450 300
run 451 400
run 452 4600
run 453 5900
run 454 5400
for s in 460 461 462 463 464; do
    run $s 300
done
run 467 400
# 465 writes the progress to a memory card file, 466 reads it at start-up
rm -f "$O/card.bin"
SC_CARD="$O/card.bin" run 465 260
SC_CARD="$O/card.bin" run 466 4
SC_CARD=
