# QUE COUTE LA DIVISION DU JEU FINAL ? -- reponse chiffree, pas d'opinion.
#
# LA QUESTION. La regle 6 du pre-enregistrement mesure le budget retenu sur
# 198 questions x 4 rotations = 792 appels. Diviser ce nombre est tentant :
# 4,1 h par bras mesurees le 26/08, et le jeu final coute 4x ca. Mais la regle
# 8 dit elle-meme que la rotation tournante (1 appel par question) est faite
# POUR LA COMPARAISON APPARIEE et « serait mauvaise pour une mesure absolue ».
# Les deux ne peuvent pas etre vraies en meme temps sans qu'on dise combien.
#
# CE QU'ON CALCULE. L'erreur-type groupee par question se decompose en deux
# termes, et un seul se paie en appels :
#
#   Var(moyennes par question) = Var(p)          <- vraie dispersion des
#                                                    difficultes, INCOMPRESSIBLE
#                              + E[p(1-p)] / k   <- bruit de generation, divise
#                                                    par le nombre de rotations
#
# Passer de k=4 a k=1 ne change RIEN au premier terme et multiplie le second
# par 4. Si la dispersion des difficultes domine, diviser coute presque rien ;
# si c'est le bruit de generation qui domine, diviser gonfle l'erreur.
#
# ON NE SUPPOSE PAS, ON ESTIME. Var(p) et E[p(1-p)] sont tires des bras a 4
# rotations reellement mesures, par methode des moments :
#     E[m(1-m)] = (1 - 1/k) E[p(1-p)]      pour m = X/k binomiale
#  => E[p(1-p)] = E[m(1-m)] / (1 - 1/k)
#  => Var(p)    = Var(m) - E[p(1-p)] / k
#
# RESERVE. L'estimation vient d'un bras donne ; un modele plus stable ou plus
# instable deplacerait le partage. Le calcul est refait pour chaque fichier
# fourni, et si les fichiers ne s'accordent pas, ca se voit.

import collections
import io
import json
import math
import os
import sys

if len(sys.argv) < 2:
    raise SystemExit("usage: python cout_de_diviser.py <fichier 4 rotations> ...")


def charger(chemin):
    q = collections.defaultdict(list)
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                d = json.loads(ligne)
            except Exception:
                continue
            if d.get("erreur"):
                continue
            # Regle 3b : la troncature au plafond est une non-mesure.
            if d.get("finish_reason") == "length":
                continue
            q[(d.get("id"), d.get("rotation"))] = d
    par = collections.defaultdict(list)
    for (ident, _rot), d in q.items():
        par[ident].append(bool(d.get("juste")))
    return par


for chemin in sys.argv[1:]:
    par = charger(chemin)
    complets = {k: v for k, v in par.items() if len(v) == 4}
    if len(complets) < 20:
        print("%s : %d questions completes a 4 rotations -- trop peu, ignore."
              % (os.path.basename(chemin), len(complets)))
        print()
        continue

    k = 4
    m = [sum(v) / float(k) for v in complets.values()]
    n = len(m)
    mbar = sum(m) / n
    varm = sum((x - mbar) ** 2 for x in m) / (n - 1)
    emm = sum(x * (1 - x) for x in m) / n
    epp = emm / (1.0 - 1.0 / k)
    varp = varm - epp / k
    varp_borne = max(0.0, varp)

    print("=" * 70)
    print("%s   %d questions completes a 4 rotations" % (os.path.basename(chemin), n))
    print("  exactitude groupee            : %.1f %%" % (100 * mbar))
    print("  Var(moyennes observees)       : %.5f" % varm)
    print("  E[p(1-p)]  bruit de generation: %.5f" % epp)
    print("  Var(p)     dispersion vraie   : %.5f%s"
          % (varp, "  (negative -> ramenee a 0)" if varp < 0 else ""))
    part = 100.0 * varp_borne / varm if varm > 0 else 0.0
    print("  -> la dispersion des difficultes fait %.0f %% de la variance"
          % part)
    print()
    print("  ERREUR-TYPE GROUPEE selon le protocole, a 198 questions :")
    print("  %-34s %10s %12s" % ("protocole", "appels", "+/- (1 sigma)"))
    for kk, etiq in ((4, "198 q x 4 rotations (regle 6)"),
                     (2, "198 q x 2 rotations"),
                     (1, "198 q x 1 rotation (tournante)")):
        se = math.sqrt((varp_borne + epp / kk) / 198.0)
        print("  %-34s %10d %11.1f pt" % (etiq, 198 * kk, 100 * se))
    se4 = math.sqrt((varp_borne + epp / 4) / 198.0)
    se1 = math.sqrt((varp_borne + epp / 1) / 198.0)
    print()
    print("  COUT DE DIVISER PAR 4 : l'erreur passe de %.1f a %.1f pt,"
          % (100 * se4, 100 * se1))
    print("  soit x%.2f, pour 4x moins d'appels." % (se1 / se4 if se4 > 0 else 0))
    # A budget d'appels EGAL, vaut-il mieux plus de questions ou plus de rotations ?
    print()
    print("  A BUDGET D'APPELS EGAL (792), ce que rendrait chaque partage :")
    print("  %-34s %10s %12s" % ("partage", "questions", "+/- (1 sigma)"))
    for kk in (1, 2, 4):
        nq = 792 // kk
        se = math.sqrt((varp_borne + epp / kk) / nq)
        print("  %-34s %10d %11.1f pt"
              % ("%d rotation(s) x %d questions" % (kk, nq), nq, 100 * se))
    print("  (au-dela de 198 questions il faudrait sortir du jeu Diamond :")
    print("   ces lignes disent seulement OU part le budget, pas un plan.)")
    print()
