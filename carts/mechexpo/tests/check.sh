#!/bin/sh
# The Mech Expo fight checks (tests/harness.akr lists the scenarios), run side by side (JOBS at a
# time, tests/pool.sh) and reported in this order; stops at the first failure (a fault, a failed
# assert, or no OK line). 1 a KO, 2 time up, 3 block and chip, 4 grab beats block, 5 grab breaks,
# 6 and 7 the chains, 8 the kinetic super, 9 the antimatter super and its debt, 10 CPU against
# CPU twice (the same match), 11 the separation limit and the walls, 12 the Parry and the
# anti-air, 13 the ladder's levels, 18 the Vault Throw, 19 the air attack, 15 training. The
# budget scenarios (14, 39, 49, 54, 69, 98, 99, 109, 147-149, 162, 168) are tests/budget.sh's.
# MEIC and RUN as in tools/cart_scenario.sh.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/check"
mkdir -p "$O"
POOL_DIR="$O"
. "$HERE/pool.sh"
pool_report() {
    grep -E '^(OK|Seraph|the (fists|jab|lunging|throw|super)|blurb|stats|Shadow.s (final|Claw)|fight [0-9]|  the (schedule|reveal|fights|cover|fight)|the novice|level 0|the run on|the version|cover|EASY levels|NORMAL levels|HARD levels|KO after|time up|chain|meter after|  round|run |rounds|apart|pushed|level|peak|Beam against|Hero health|thrown to|Tank|clinched|Hero thrown|anti-air|late|combine|split|jab and|twin|overlapping|Tag Toss|Binary|combined|Fusion|meter after|Twins|frames split|tread|stages|the |siphoned|refreshed|mine |armed|snared|tapped|held|Eclipse|open floor|cornered|Total|in debt|blocked|Phantom|Shadow|blurb)' "$O/$1.log"
}
run() {       # scenario frames: the scenarios through the whole game cost about 8 times a frame
    s="$1"; f="$2"; shift 2
    case "$s" in 5[0-4]|6[89]|8[0-9]|9[0-9]|11[2-5]|14[0-6]|150|16[3-7]) c=$((f * 8)) ;; 108) c=$((f * 40)) ;; *) c="$f" ;; esac
    pool_add "s$s" "$c" "$HERE/run.sh" "$s" "$f" "$O/s$s" "$@"
}
run 1 800
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
# Beam (mx-beam): 30 the chemical meter, 31 a spoiled prime, 32 the Volt Orb, 33 orb against
# wave, 34 Beam's chain, 35 its super, 36 the Shock Grip and the Thunder Pillar, 37 CPU against
# CPU with Beam (three pairings, the first twice), 38 the Void Step through the orb
run 30 760
run 31 200
run 32 500
run 33 640
run 34 210
run 35 440
run 36 340
run 37 2000
run 38 340
# Tank (mx-tank): 40 armour, 41 armour broken, 42 the Atomic Clinch, 43 the nuclear meter,
# 44 Chain Reaction, 45 the Scrap Heave, 46 Tank thrown, 47 the slam and the anti-air, 48 CPU
# against CPU
run 40 120
run 41 320
run 42 320
run 43 500
run 44 320
run 45 300
run 46 300
run 47 340
run 48 2000
# the Twins (mx-twins-fight): 60 combining and splitting, 61 the partner, 62 a hit on the
# partner, 63 throws on the Twins, 64 their throws, 65 the fusion meter, 66 the super, 67 CPU
# against CPU (four matches), 68 the unlock rule
run 60 210
run 61 310
run 62 310
run 63 450
run 64 300
run 65 470
run 66 270
run 67 2500
run 68 3
# the stages (mx-stages, tests/stages/harness.akr): 90 the hangar unchanged, 91 a knockdown rings
# out on the rooftop, 92 throws ring out, 93 a blocked hit, a hit, a walk and a jump stop at the
# lip, 94 the closed side is a wall, 95 the Twins near the edge, 96 the CPU on the rooftop (a mech
# at the lip, then CPU against CPU), 97 the stage select
run 90 270
run 91 480
run 92 170
run 93 410
run 94 470
run 95 130
run 96 1500
run 97 171
# 112-115: the rooftop's city seen from the fight's start, fully out, at the open edge and in a
# ring-out (the stage's pictures)
run 112 45
run 113 45
run 114 65
run 115 120
# 140-146, 150: the container port (tests/stages/harness.akr): the fight's start, fully out, near
# the container wall, near the quay edge, a throw off the quay (a ring-out), the wall stopping a
# knockdown, a throw and a walk, the stage select to the port, the camera drifting
run 140 45
run 141 45
run 142 45
run 143 65
run 144 80
run 145 470
run 146 171
run 150 112
run 50 330
run 51 210
run 52 210
run 53 390
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
# Shadow (mx-shadow-fight): 100 the Hex Bolt and the Siphon on every power source, 101 the curse's
# time and refresh, 102 the Rift Mine, 103 Shadow Sneak, 104 Eclipse Rise, 105 Phantom Grip,
# 106 Total Eclipse and its debt, 107 throws with Tank and the Twins, 108 CPU against CPU, 110
# the rooftop (109, the budget through the real game, is in budget.sh)
run 100 900
run 101 1100
run 102 700
run 103 900
run 104 300
run 105 600
run 106 900
run 107 1600
run 108 2500
run 110 900
# Seraph (mx-seraph, phase 1: Shadow's moves on its body): 160 against Shadow, 161 against the
# Hero (its numbers, the fists' reach, a throw, the kinetic super); through the whole game
# (tests/seraph/harness.akr): 163 the select with its card and spec sheet, 164-167 mid-fight
# against Shadow and the Hero in the hangar and on the rooftop (162 and 168, the budget, are
# budget.sh's)
run 160 1500
run 161 1500
run 163 61
run 164 301
run 165 301
run 166 301
run 167 301
# the arcade ladder (mx-ladder, tests/ladder/harness.akr, the whole game; VIEWs as listed there):
# 116 EASY against a scripted masher, 117-119 a whole run on each difficulty (EASY with the Hero,
# NORMAL with Shadow, HARD with Tank: the rivals drawn, a loss and a continue, the reveal, the
# final (Seraph's for Shadow, the test unit's for Tank), the cover, the unlock and the stamps),
# 120 the lot, 121 the save's migration from version 1 and the stamps on the select, 122 the
# difficulty select, 123 the schedule page, 124 the reveal (VIEWs 4 and 5: Seraph and its VS
# card), 125 the test unit in a fight, 126 the cover (a frozen pose per mech, the fanfare,
# the headline pick and every line's width), 127 a continue. 117-119 and 121 get a
# memory card each (out/check/ladder_card*.bin, made fresh)
lrun() {      # scenario view frames [mei-headless args]
    s="$1"; v="$2"; f="$3"; shift 3
    case "$s" in 116) c=$((f * 60)) ;; *) c=$((f * 8)) ;; esac
    pool_add "l${s}_$v" "$c" "$HERE/ladder/run.sh" "$s" "$v" "$f" "$O/l${s}_$v" "$@"
}
lcard() { rm -f "$O/ladder_card$1.bin"; echo "$O/ladder_card$1.bin"; }
lrun 116 0 3000
lrun 117 0 6500 --card1 "$(lcard 117)"
lrun 118 0 6500 --card1 "$(lcard 118)"
lrun 119 0 6500 --card1 "$(lcard 119)"
lrun 120 0 60
lrun 121 0 61 --card1 "$(lcard 121)"
lrun 121 1 61 --card1 "$(lcard 1211)"
lrun 122 0 81
lrun 123 0 61
lrun 123 1 61
lrun 123 2 61
lrun 124 0 121
lrun 124 1 241
lrun 124 2 241
lrun 124 3 241
lrun 124 4 241
lrun 124 5 141
lrun 125 0 601
lrun 125 1 601
lrun 126 0 151
lrun 126 1 151
lrun 126 2 151
lrun 126 3 151
lrun 126 4 151
lrun 126 5 151
lrun 126 6 151
lrun 126 7 401
lrun 127 0 61
lrun 127 1 141
lrun 127 2 121
pool_run
echo "all Mech Expo fight checks passed"
# 55-59: the menus (mx-menus), the whole game with scripted pads: tests/menus/check.sh
"$HERE/menus/check.sh"
