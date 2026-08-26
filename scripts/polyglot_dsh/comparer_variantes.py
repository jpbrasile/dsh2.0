#!/usr/bin/env python3
"""Compare deux runs du pilote exercice par exercice — C contre B.

    python comparer_variantes.py dsh-polyglot-estim-p6 dsh-polyglot-B-p6

Le taux global ne suffit pas. Deux runs peuvent afficher le meme pourcentage en
reussissant des exercices differents : a temperature 1.0, une partie du
mouvement est du bruit et non l'effet du fichier de test masque. La table des
BASCULES (C passe / B echoue, et l'inverse) est ce qui se lit vraiment.

Un garde-fou : le script REFUSE de comparer si les variantes declarees dans les
resultats ne different pas comme attendu. Comparer C a C en croyant lire B est
exactement le genre d'erreur qu'un depouillement doit rendre impossible.
"""
import glob
import io
import json
import os
import sys

BENCH = r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"


def lire_run(nom):
    run = nom if os.path.isabs(nom) else os.path.join(BENCH, nom)
    out = {}
    for f in glob.glob(os.path.join(run, "*", "exercises", "practice", "*",
                                    ".dsh.results.json")):
        d = json.loads(io.open(f, encoding="utf-8", errors="replace").read())
        p = os.path.normpath(f).split(os.sep)
        outc = d.get("tests_outcomes", [])
        out["%s/%s" % (p[-5], p[-2])] = {
            "ok": bool(outc) and outc[-1],
            "tours": len(outc),
            "s": d.get("duration", 0.0),
            "variante": d.get("variante", "C (non etiquete)"),
            "sans_tests": d.get("sans_tests", False),
        }
    if not out:
        raise SystemExit("aucun resultat sous %s" % run)
    return run, out


def variantes(d):
    return sorted({v["variante"] for v in d.values()})


nom_c = sys.argv[1] if len(sys.argv) > 1 else "dsh-polyglot-estim-p6"
nom_b = sys.argv[2] if len(sys.argv) > 2 else "dsh-polyglot-B-p6"
run_c, C = lire_run(nom_c)
run_b, B = lire_run(nom_b)

print("C : %s   variante(s) %s   n=%d" % (nom_c, variantes(C), len(C)))
print("B : %s   variante(s) %s   n=%d" % (nom_b, variantes(B), len(B)))

if not any(v["sans_tests"] for v in B.values()):
    raise SystemExit("REFUS : le run B ne porte aucun resultat 'sans_tests'. "
                     "Ce serait comparer C a C.")
if any(v["sans_tests"] for v in C.values()):
    raise SystemExit("REFUS : le run C porte des resultats 'sans_tests'.")

communs = sorted(set(C) & set(B))
if not communs:
    raise SystemExit("REFUS : aucun exercice commun aux deux runs.")
print("exercices communs : %d" % len(communs))
manquants = sorted((set(C) | set(B)) - set(communs))
if manquants:
    print("hors comparaison (%d) : %s" % (len(manquants), ", ".join(manquants[:8])))

nc = sum(1 for e in communs if C[e]["ok"])
nb = sum(1 for e in communs if B[e]["ok"])
print("")
print("C (voit le test)     : %d/%d = %.1f %%" % (nc, len(communs), 100.0 * nc / len(communs)))
print("B (ne le voit pas)   : %d/%d = %.1f %%" % (nb, len(communs), 100.0 * nb / len(communs)))
print("ecart                : %+.1f points" % (100.0 * (nb - nc) / len(communs)))

perdus = [e for e in communs if C[e]["ok"] and not B[e]["ok"]]
gagnes = [e for e in communs if not C[e]["ok"] and B[e]["ok"]]
print("")
print("BASCULES -- c'est ici que se lit l'effet, pas dans les deux taux")
print("  C passe / B echoue : %d" % len(perdus))
for e in perdus:
    print("      %-34s C %d tour(s) %6.1fs -> B %d tour(s) %6.1fs"
          % (e, C[e]["tours"], C[e]["s"], B[e]["tours"], B[e]["s"]))
print("  C echoue / B passe : %d   %s" % (len(gagnes), ", ".join(gagnes)))
print("")
print("Un exercice qui bascule DANS LES DEUX SENS entre deux runs mesure du")
print("bruit de temperature, pas le masquage. Le %d de la seconde ligne est"
      % len(gagnes))
print("l'estimation la plus directe de ce bruit : masquer le test ne peut pas")
print("AIDER un agent. Lire l'ecart net en le gardant en tete.")

tc = sum(C[e]["tours"] for e in communs) / float(len(communs))
tb = sum(B[e]["tours"] for e in communs) / float(len(communs))
print("")
print("tours moyens : C %.2f   B %.2f" % (tc, tb))
