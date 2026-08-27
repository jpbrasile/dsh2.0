# -*- coding: utf-8 -*-
"""COMPARE deux runs sur les memes exercices, appariement par exercice.

Usage prevu : mesurer ce que vaut le SEMIS des signatures cpp.

    python comparer_semis.py pi_D_t1_dflash2 pi_cpp_sans_semis --langage cpp

CE QUE LA COMPARAISON PEUT ET NE PEUT PAS DIRE. Le banc echantillonne
(temperature 1.0, top_k 20, graine tiree a chaque appel) : deux runs de la MEME
configuration divergent deja. Un basculement isole ne prouve donc rien. Ce qui
porte de l'information est le BILAN des basculements dans les deux sens :
b = seme PASS / nu FAIL, c = seme FAIL / nu PASS. Le semis n'aide que si b
depasse c NETTEMENT ; b ~ c, c'est le bruit du banc.

Le p exact de McNemar est calcule sur b et c (loi binomiale, p=0.5). Il ne
corrige pas le fait qu'on compare DEUX tirages d'un banc bruite : lu comme un
ordre de grandeur, pas comme une preuve.

Sortie : les deux taux (tour 1 et final), la table 2x2, le p, et les durees.
"""

import io
import json
import os
import sys

AIDER_HOTE = os.path.join(os.path.expanduser("~"), "tools", "aider-bench", "aider")
BENCH_HOTE = os.path.join(AIDER_HOTE, "tmp.benchmarks")


def resultats(run, langage):
    """{exercice: (pass_final, pass_tour1, duree, n_tours, coupe2)}"""
    base = os.path.join(BENCH_HOTE, run, langage, "exercises", "practice")
    out = {}
    if not os.path.isdir(base):
        return out
    for ex in sorted(os.listdir(base)):
        f = os.path.join(base, ex, ".dsh.results.json")
        if not os.path.exists(f):
            continue
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        issues = d.get("tests_outcomes") or []
        tours = d.get("turns") or []
        if not tours:                      # exercice ampute, jamais joue
            continue
        out[ex] = (bool(issues and issues[-1]),
                   bool(issues and issues[0]),
                   float(d.get("duration") or 0.0),
                   len(tours),
                   bool(tours[-1].get("coupe")) if len(tours) > 1 else False)
    return out


def binom_bilateral(b, c):
    """p exact de McNemar : P(|X - n/2| >= |b - n/2|) pour X ~ Bin(n, 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    seuil = min(b, c)
    q = sum(comb(n, k) for k in range(0, seuil + 1))
    p = 2.0 * q / float(2 ** n)
    return min(1.0, p)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    langage = "cpp"
    if "--langage" in sys.argv:
        langage = sys.argv[sys.argv.index("--langage") + 1]
    if len(args) < 2:
        print(__doc__)
        return 2
    ra, rb = args[0], args[1]

    a = resultats(ra, langage)
    b = resultats(rb, langage)
    communs = sorted(set(a) & set(b))
    if not communs:
        print("aucun exercice %s juge dans LES DEUX runs." % langage)
        print("  %s : %d juge(s)   %s : %d juge(s)" % (ra, len(a), rb, len(b)))
        return 1

    print("=== %s : %s (A) contre %s (B) -- %d exercices apparies ===\n"
          % (langage, ra, rb, len(communs)))
    print("%-26s %-14s %-14s" % ("exercice", "A", "B"))
    n_bb = n_bc = n_cb = n_cc = 0
    for ex in communs:
        fa, p1a, da, ta, ka = a[ex]
        fb, p1b, db, tb, kb = b[ex]
        marque = ""
        if fa and not fb:
            n_bc += 1
            marque = "  <- A seul"
        elif fb and not fa:
            n_cb += 1
            marque = "  -> B seul"
        elif fa and fb:
            n_bb += 1
        else:
            n_cc += 1
        print("%-26s %-4s %6.1fs%s %-4s %6.1fs%s%s"
              % (ex,
                 "PASS" if fa else "FAIL", da, "*" if ka else " ",
                 "PASS" if fb else "FAIL", db, "*" if kb else " ",
                 marque))

    na, nb = len(communs), len(communs)
    pa = sum(1 for e in communs if a[e][0])
    pb = sum(1 for e in communs if b[e][0])
    p1a = sum(1 for e in communs if a[e][1])
    p1b = sum(1 for e in communs if b[e][1])
    ta = sum(a[e][2] for e in communs)
    tb = sum(b[e][2] for e in communs)

    print("\n%-22s %12s %12s" % ("", "A (" + ra + ")", "B (" + rb + ")"))
    print("%-22s %11d%% %11d%%" % ("taux tour 1", 100 * p1a // na, 100 * p1b // nb))
    print("%-22s %11d%% %11d%%" % ("taux final", 100 * pa // na, 100 * pb // nb))
    print("%-22s %10.1f h %10.1f h" % ("temps total", ta / 3600.0, tb / 3600.0))
    print("%-22s %10.1f s %10.1f s" % ("moyenne/exercice", ta / na, tb / nb))

    print("\ntable des basculements (verdict final)")
    print("  A PASS et B PASS : %3d" % n_bb)
    print("  A PASS et B FAIL : %3d   <- ce que A gagne" % n_bc)
    print("  A FAIL et B PASS : %3d   <- ce que B gagne" % n_cb)
    print("  A FAIL et B FAIL : %3d" % n_cc)
    p = binom_bilateral(n_bc, n_cb)
    print("\n  McNemar exact, p = %.3f" % p)
    if n_bc + n_cb == 0:
        print("  Aucun basculement : les deux protocoles sont indistinguables ici.")
    elif p > 0.05:
        print("  p > 0,05 : l'ecart ne se distingue pas du bruit d'echantillonnage")
        print("  du banc. NE PAS conclure que le semis aide.")
    else:
        print("  p <= 0,05 : ecart peu compatible avec le seul bruit -- a lire")
        print("  quand meme comme un indice, le banc etant lui-meme stochastique.")
    print("\n  (* = tour 2 coupe a la laisse)")
    return 0


sys.exit(main())
