#!/bin/sh
# The Mech Expo fight checks (tests/harness.akr lists the scenarios); stops at the first failure
# (a fault, a failed assert, or no OK line). 1 a KO, 2 time up, 3 block and chip, 4 grab beats
# block, 5 grab breaks, 6 and 7 the chains, 8 the kinetic super, 9 the antimatter super and its
# debt, 10 CPU against CPU twice (the same match), 11 the separation limit and the walls, 12 the
# Parry and the anti-air, 13 the ladder's levels, 18 the Vault Throw, 19 the air attack, 15
# training, 14 the budget with both mechs drawn. MEIC and RUN as in tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
run() {       # scenario frames
    s="$1"; f="$2"; shift 2
    "$HERE/run.sh" "$s" "$f" "$O/s$s" "$@" > "$O/s$s.log" 2>&1 || { echo "FAILED scenario $s"; tail -8 "$O/s$s.log"; exit 1; }
    grep -q '^OK' "$O/s$s.log" || { echo "FAILED scenario $s: no OK"; tail -8 "$O/s$s.log"; exit 1; }
    grep -E '^(OK|KO after|time up|chain|meter after|  round|run |rounds|apart|pushed|level|peak|Beam against|Hero health|thrown to|Tank|clinched|Hero thrown|anti-air|late|combine|split|jab and|twin|overlapping|Tag Toss|Binary|combined|Fusion|meter after|Twins|frames split|tread)' "$O/s$s.log"
}
run 1 700
run 2 4000
run 3 420
run 4 160
run 5 210
run 6 210
run 7 210
run 8 150
run 9 420
run 10 1000
run 11 2200
run 12 340
run 13 3000
run 18 110
run 19 260
run 15 1500
run 14 1800
# Beam (mx-beam): 30 the chemical meter, 31 a spoiled prime, 32 the Volt Orb, 33 orb against
# wave, 34 Beam's chain, 35 its super, 36 the Shock Grip and the Thunder Pillar, 37 CPU against
# CPU with Beam (three pairings, the first twice), 38 the Void Step through the orb, 39 the
# budget with Beam drawn against each mech
run 30 760
run 31 200
run 32 500
run 33 640
run 34 210
run 35 440
run 36 340
run 37 2000
run 38 340
run 39 1800
# Tank (mx-tank): 40 armour, 41 armour broken, 42 the Atomic Clinch, 43 the nuclear meter,
# 44 Chain Reaction, 45 the Scrap Heave, 46 Tank thrown, 47 the slam and the anti-air, 48 CPU
# against CPU, 49 the budget with Tank drawn
run 40 120
run 41 320
run 42 320
run 43 500
run 44 320
run 45 300
run 46 300
run 47 340
run 48 2000
run 49 1800
# the Twins (mx-twins-fight): 60 combining and splitting, 61 the partner, 62 a hit on the
# partner, 63 throws on the Twins, 64 their throws, 65 the fusion meter, 66 the super, 67 CPU
# against CPU (four matches), 68 the unlock rule, 69 the budget with three bodies (the split
# Twins against Tank, through the real game)
run 60 210
run 61 310
run 62 310
run 63 450
run 64 300
run 65 470
run 66 270
run 67 2500
run 68 3
run 69 1800
run 50 330
run 51 210
run 52 210
run 53 390
run 54 1810
# the sounds (mx-sfx), through the whole game: 80 Tank's armour and vent, 81 its treads and the
# Atomic Clinch, 82 Beam's charge, orbs and reaction, 83 its Shock Grip and discharges, 84 the
# Twins' coupling and swings, 85 the supers' charge-ups, 86 the KO and leaving the fight, 87 the
# Void Step, 88 the voices' priorities and the loops, 89 the menus
run 80 141
run 81 361
run 82 461
run 83 431
run 84 271
run 85 751
run 86 300
run 87 121
run 88 421
run 89 321
echo "all Mech Expo fight checks passed"
# 55-59: the menus (mx-menus), the whole game with scripted pads: tests/menus/check.sh
"$HERE/menus/check.sh"
