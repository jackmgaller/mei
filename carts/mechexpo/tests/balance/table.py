#!/usr/bin/env python3
"""The balance matrix's report (tests/balance/matrix.sh): reads the pairings' logs (the MATCHUP
and MECH lines tests/balance/harness.akr prints) and prints the win rates as a table, each
mech's overall rate, and per pairing the stats that explain the results."""
import sys

ORDER = ["Hero", "Doubleblade", "Beam", "Tank", "Twins", "Shadow"]
SHORT = {"Hero": "Hero", "Doubleblade": "DBlade", "Beam": "Beam", "Tank": "Tank",
         "Twins": "Twins", "Shadow": "Shadow"}


def kvs(line):
    out = {}
    for tok in line.split()[1:]:
        k, _, v = tok.partition("=")
        try:
            out[k] = int(v)
        except ValueError:
            out[k] = v
    return out


def read(paths):
    pairs = []
    for p in paths:
        mu, mechs = None, []
        with open(p) as f:
            for line in f:
                if line.startswith("MATCHUP "):
                    mu = kvs(line)
                elif line.startswith("MECH "):
                    mechs.append(kvs(line))
        if mu and len(mechs) == 2:
            pairs.append((mu, mechs))
    return pairs


def table(pairs):
    win = {}            # (row, col) -> (wins, matches)
    tot = {}
    for mu, (a, b) in pairs:
        n = mu["matches"]
        if a["name"] == b["name"]:
            continue
        win[(a["name"], b["name"])] = (a["wins"], n)
        win[(b["name"], a["name"])] = (b["wins"], n)
        for m in (a, b):
            w, t = tot.get(m["name"], (0, 0))
            tot[m["name"]] = (w + m["wins"], t + n)
    names = [m for m in ORDER if m in tot]
    print("Win rate of the row's mech against the column's (CPU level 2 both, %d matches a pairing)"
          % pairs[0][0]["matches"])
    print("%-8s" % "" + "".join("%8s" % SHORT[c] for c in names) + "%9s" % "overall")
    for r in names:
        row = "%-8s" % SHORT[r]
        for c in names:
            if (r, c) in win:
                w, n = win[(r, c)]
                pct = round(100 * w / n)
                row += "%6d%%%s" % (pct, "*" if pct < 35 or pct > 65 else " ")
            else:
                row += "%8s" % "-"
        w, t = tot[r]
        pct = round(100 * w / t)
        row += "%7d%%%s" % (pct, "*" if pct < 40 or pct > 60 else " ")
        print(row)
    print("(* outside 35-65 % for a pairing, 40-60 % overall)")


def details(pairs):
    print("Per pairing: matches won, rounds, average round (s), time-ups, ring-outs; for each mech")
    print("the damage it dealt by kind (N normals, S specials, P shots, T throws and command grabs,")
    print("X supers, C chip), supers used (landed), throws, its hits the other blocked, then its kit")
    key = lambda p: (ORDER.index(p[1][0]["name"]), ORDER.index(p[1][1]["name"]))
    for mu, (a, b) in sorted(pairs, key=key):
        r = max(mu["rounds"], 1)
        print("%s - %s: %d-%d%s, %d rounds, %.1f s, %d time-ups, %d ring-outs" % (
            SHORT[a["name"]], SHORT[b["name"]], a["wins"], b["wins"],
            (", %d draws" % mu["draws"]) if mu["draws"] else "", mu["rounds"],
            mu["round_frames"] / r / 60, mu["timeups"], mu["ringouts"]))
        ft = max(mu["fight_frames"], 1)
        for m in (a, b):
            o = a if m is b else b
            extra = []
            if m["parries"]:
                extra.append("parries %d" % m["parries"])
            if m["shots"]:
                extra.append("shots %d" % m["shots"])
            if m["absorbed"]:
                extra.append("armour absorbed %d" % m["absorbed"])
            if m["curses"] or m["mines"]:
                extra.append("curses %d, mines %d (snared %d, broken %d), siphoned %d" % (
                    m["curses"], m["mines"], m["snares"], o["mines_broken"], o["siphoned"]))
            if m["cursed_t"]:
                extra.append("cursed %d %%" % (100 * m["cursed_t"] // ft))
            if m["debt_t"]:
                extra.append("in debt %d %%" % (100 * m["debt_t"] // ft))
            if m["switches"]:
                extra.append("combined %d %% (cursed %d %% of that), %d switches" % (
                    100 * m["comb_t"] // ft, 100 * m["comb_curse_t"] // max(m["comb_t"], 1),
                    m["switches"]))
            d = [m["dmg" + k] for k in "NSPTXC"]
            print("  %-7s dmg %5d: N %5d S %5d P %5d T %5d X %5d C %4d | supers %d (%d), throws %d,"
                  " blocked %d%s" % (SHORT[m["name"]], sum(d), *d, m["supers"], m["supers_hit"],
                                     m["throws"], m["blocked"],
                                     ("; " + ", ".join(extra)) if extra else ""))


def main(paths):
    pairs = read(paths)
    if not pairs:
        print("no results")
        return 1
    table(pairs)
    print()
    details(pairs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
