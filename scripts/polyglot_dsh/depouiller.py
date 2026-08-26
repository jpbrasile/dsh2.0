#!/usr/bin/env python3
"""Depouille un run du pilote polyglot dsh.

Lit les `.dsh.results.json` d'un repertoire de run et rend le taux, la
repartition par tour et la table par langage. Meme forme que le depouillement
du run aider, pour que les deux se lisent cote a cote.

    python depouiller.py <nom-du-run>
"""
import glob
import json
import os
import sys
from collections import Counter

BENCH = r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"

nom = sys.argv[1] if len(sys.argv) > 1 else "dsh-polyglot-estim-p6"
run = nom if os.path.isabs(nom) else os.path.join(BENCH, nom)

fics = sorted(glob.glob(os.path.join(run, "*", "exercises", "practice", "*",
                                     ".dsh.results.json")))
if not fics:
    raise SystemExit("aucun resultat sous %s" % run)

lignes = []
for f in fics:
    r = json.loads(open(f, encoding="utf-8").read())
    p = os.path.normpath(f).split(os.sep)
    lang, ex = p[-5], p[-2]
    outc = r.get("tests_outcomes", [])
    lignes.append({
        "lang": lang, "ex": ex, "outc": outc,
        "ok": bool(outc) and outc[-1],
        "tours": len(outc),
        "s": r.get("duration", 0.0),
        "coupes": r.get("tours_coupes", 0),
        "exception": r.get("exception"),
    })

n = len(lignes)
ok = sum(1 for l in lignes if l["ok"])
print("run       : %s" % run)
print("exercices : %d" % n)
print("PASS      : %d/%d = %.1f %%" % (ok, n, 100.0 * ok / n))

par_tour = Counter()
for l in lignes:
    if l["ok"]:
        par_tour["passe au tour %d" % l["tours"]] += 1
    elif l["exception"]:
        par_tour["exception"] += 1
    else:
        par_tour["echoue apres %d tours" % l["tours"]] += 1
print("")
for k in sorted(par_tour):
    print("  %-24s %d" % (k, par_tour[k]))

print("")
print("%-12s %8s %10s %10s" % ("langage", "reussite", "temps med", "temps moy"))
langs = sorted({l["lang"] for l in lignes})
for lg in langs:
    sous = [l for l in lignes if l["lang"] == lg]
    t = sorted(l["s"] for l in sous)
    med = t[len(t) // 2] if len(t) % 2 else (t[len(t) // 2 - 1] + t[len(t) // 2]) / 2
    moy = sum(t) / len(t)
    print("%-12s %4d/%-3d %9.1fs %9.1fs"
          % (lg, sum(1 for l in sous if l["ok"]), len(sous), med, moy))

t = sorted(l["s"] for l in lignes)
med = t[len(t) // 2] if len(t) % 2 else (t[len(t) // 2 - 1] + t[len(t) // 2]) / 2
moy = sum(t) / len(t)
tours_moy = sum(l["tours"] for l in lignes) / float(n)
print("%-12s %4d/%-3d %9.1fs %9.1fs" % ("TOTAL", ok, n, med, moy))
print("")
print("tours moyens : %.2f    tours coupes par le delai : %d"
      % (tours_moy, sum(l["coupes"] for l in lignes)))
print("extrapolation 225 exercices : %.1f h (a temps moyen constant)"
      % (225 * moy / 3600.0))
