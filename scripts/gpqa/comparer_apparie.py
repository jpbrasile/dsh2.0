# Comparaison APPARIEE de deux bras GPQA, couple (Record ID, rotation) par
# couple (Record ID, rotation).
#
# POURQUOI APPARIE. Comparer deux scores globaux, c'est comparer deux
# echantillons de questions differents : la variance de difficulte des
# questions domine et noie l'effet cherche. Sur les couples COMMUNS, cette
# variance disparait -- une question que les deux bras reussissent n'apporte
# rien, seules les DISCORDANCES portent de l'information. C'est le test de
# McNemar.
#
# McNemar : sur les n01 + n10 couples discordants, la statistique
#   chi2 = (|n01 - n10| - 1)^2 / (n01 + n10)   (correction de continuite)
# suit un khi-deux a 1 ddl. Seuils : 3,84 a 5 % ; 6,63 a 1 %.
#
# LES NON-MESURES SORTENT DES DEUX BRAS ENSEMBLE. Un couple tronque d'un cote
# est retire des deux, sinon on comparerait un bras ampute a un bras entier.
# Le compte des couples ainsi retires est PUBLIE : un ecart de troncature entre
# bras est lui-meme un resultat, il ne doit pas disparaitre dans le filtre.

import io
import json
import sys


def charger(chemin):
    d = {}
    tronques = set()
    for ligne in io.open(chemin, encoding="utf-8"):
        ligne = ligne.strip()
        if not ligne:
            continue
        r = json.loads(ligne)
        cle = (r.get("id"), r.get("rotation"))
        if r.get("finish_reason") == "length" or not r.get("donne"):
            tronques.add(cle)
        else:
            d[cle] = bool(r.get("juste"))
    return d, tronques


a, ta = charger(sys.argv[1])
b, tb = charger(sys.argv[2])
nom_a, nom_b = sys.argv[1].split("/")[-1], sys.argv[2].split("/")[-1]

exclus = (ta | tb) & (set(a) | set(b) | ta | tb)
communs = sorted(set(a) & set(b))

print("A = %s   (%d notables, %d non-mesures)" % (nom_a, len(a), len(ta)))
print("B = %s   (%d notables, %d non-mesures)" % (nom_b, len(b), len(tb)))
print()
if not communs:
    print("AUCUN couple commun : les deux bras ne portent pas sur les memes")
    print("questions/rotations. Une comparaison appariee est IMPOSSIBLE ici ;")
    print("comparer les scores globaux serait comparer deux echantillons.")
    raise SystemExit(0)

print("couples COMMUNS et notables des deux cotes : %d" % len(communs))
perdus = len((ta | tb) & (set(a) | set(b)))
if perdus:
    print("couples retires car non-mesure d'AU MOINS un cote : %d" % perdus)
    print("  (dont %d tronques cote A, %d cote B)"
          % (len(ta & (set(b) | tb)), len(tb & (set(a) | ta))))
print()

n11 = sum(1 for c in communs if a[c] and b[c])
n00 = sum(1 for c in communs if not a[c] and not b[c])
n10 = sum(1 for c in communs if a[c] and not b[c])   # A juste, B faux
n01 = sum(1 for c in communs if not a[c] and b[c])   # A faux, B juste

print("               B juste   B faux")
print("  A juste      %6d   %6d" % (n11, n10))
print("  A faux       %6d   %6d" % (n01, n00))
print()
pa = 100.0 * (n11 + n10) / len(communs)
pb = 100.0 * (n11 + n01) / len(communs)
print("exactitude sur les couples communs :  A %.1f %%   B %.1f %%   ecart %+.1f pt"
      % (pa, pb, pa - pb))
print()
disc = n10 + n01
if disc == 0:
    print("ZERO discordance : les deux bras repondent identiquement partout.")
    raise SystemExit(0)
chi2 = (abs(n10 - n01) - 1) ** 2 / float(disc) if disc > 0 else 0.0
print("discordances : %d  (A seul juste %d, B seul juste %d)" % (disc, n10, n01))
print("McNemar chi2 = %.2f  (1 ddl ; 3,84 a 5 %% ; 6,63 a 1 %%)" % chi2)
if chi2 > 6.63:
    print("=> ECART SIGNIFICATIF a 1 %.")
elif chi2 > 3.84:
    print("=> ecart significatif a 5 %.")
else:
    print("=> NON DEPARTAGES. Ce n'est PAS « equivalents » : avec %d" % disc)
    print("   discordances, on ne detecte qu'un desequilibre d'environ")
    print("   %.0f contre %.0f ou plus." % (disc / 2.0 + 0.98 * disc ** 0.5,
                                            disc / 2.0 - 0.98 * disc ** 0.5))
