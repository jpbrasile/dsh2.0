# Le placement de la bonne reponse biaise-t-il le modele ?
#
# ENJEU PRATIQUE, pas academique : les 4 rotations existent pour neutraliser ce
# biais. Si le biais est absent, on peut depenser le meme nombre d'appels en
# 1 rotation x 198 questions -- soit le benchmark ENTIER -- au lieu de
# 4 rotations x 50 questions, soit un quart du benchmark. Pour une comparaison
# APPARIEE entre deux reglages, couvrir toutes les questions supprime la
# variance d'echantillonnage des questions, qui est la plus grosse.
#
# Deux biais distincts, souvent confondus :
#   (1) biais de POSITION -- le modele est-il moins bon quand la bonne reponse
#       est en D qu'en A ? On lit l'exactitude par lettre ATTENDUE.
#   (2) biais de PREFERENCE -- le modele sur-choisit-il une lettre,
#       indépendamment de la verite ? On lit la distribution des lettres
#       DONNEES, qui doit tomber a 25 % chacune par construction du protocole.
#
# Test : khi-deux d'ajustement a l'uniforme, 3 degres de liberte.
# Valeurs critiques : 7,81 a 5 % ; 11,34 a 1 %.
# Un khi-deux SOUS le seuil ne prouve pas l'absence de biais : il dit que
# l'echantillon ne suffit pas a en montrer un. On publie donc aussi la
# puissance grossiere -- l'ecart qu'on aurait pu detecter.

import io
import json
import sys

CHI5, CHI1 = 7.81, 11.34


def khi2(obs):
    n = sum(obs)
    if n == 0:
        return 0.0, 0
    att = n / 4.0
    return sum((o - att) ** 2 / att for o in obs), n


for chemin in sys.argv[1:]:
    v = [json.loads(l) for l in io.open(chemin, encoding="utf-8") if l.strip()]
    # Les appels tronques ne sont pas des mesures : hors analyse.
    v = [d for d in v if d.get("finish_reason") != "length" and d.get("donne")]
    L = "ABCD"

    donnees = [sum(1 for d in v if d.get("donne") == c) for c in L]
    x_pref, n = khi2(donnees)

    print("=" * 62)
    print("%s   %d appels notables" % (chemin.split("/")[-1], n))
    print()
    print("  PREFERENCE -- lettres DONNEES (25 %% attendus chacune)")
    print("     " + "  ".join("%s %5.1f %%" % (c, 100.0 * o / max(1, n))
                              for c, o in zip(L, donnees)))
    print("     khi2 = %.2f   %s"
          % (x_pref,
             "BIAIS a 1 %" if x_pref > CHI1 else
             ("biais a 5 %" if x_pref > CHI5 else "pas de biais detectable")))
    print()
    print("  POSITION -- exactitude selon la lettre ATTENDUE")
    lignes = []
    for c in L:
        s = [d for d in v if d.get("attendu") == c]
        j = sum(1 for d in s if d.get("juste"))
        lignes.append((c, len(s), 100.0 * j / max(1, len(s))))
        print("     %s  n=%-4d  %5.1f %% justes" % (c, len(s), lignes[-1][2]))
    ecart = max(x[2] for x in lignes) - min(x[2] for x in lignes)
    print("     etendue max-min : %.1f points" % ecart)
    print()
    # Puissance grossiere : l'ecart minimal detectable a 5 % sur une proportion
    # ~0,7 avec n/4 par cellule, deux cellules comparees.
    import math
    nc = max(1, n // 4)
    mde = 1.96 * math.sqrt(2 * 0.7 * 0.3 / nc) * 100
    print("  PUISSANCE : avec %d appels par lettre, on ne detecte un ecart" % nc)
    print("  d'exactitude entre deux positions qu'a partir de ~%.0f points." % mde)
    print("  En dessous, « pas de biais detecte » ne veut PAS dire « pas de biais ».")
