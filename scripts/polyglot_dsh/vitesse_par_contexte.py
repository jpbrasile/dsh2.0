# VITESSE DE DECODAGE PAR TAILLE DE CONTEXTE -- mesure directe, sans regression.
#
# POURQUOI CE SCRIPT EXISTE. cout_du_prefixe.py a rendu un R2 de 0,86 et, avec
# lui, un cout NEGATIF au jeton cache. Un R2 eleve n'est pas un permis
# d'interpreter : les regresseurs (entree cachee, entree non cachee, sortie)
# sont colineaires, le terme dominant capte tout et les autres absorbent du
# bruit de signe libre. L'imputation a ete refusee.
#
# On mesure donc directement, sans modele : pour chaque appel, la vitesse de
# generation observee = jetons de sortie / duree. On la range par tranche de
# contexte d'entree. Si la vitesse chute quand le contexte grossit, l'effet
# est visible sans rien ajuster.
#
# CE QUE CETTE MESURE NE DIT PAS. La duree d'un appel contient le prefill, la
# file d'attente du fournisseur et la generation ; la « vitesse » calculee ici
# est donc une vitesse APPARENTE, bornee par le bas. Sur les appels a sortie
# courte la constante par appel domine et ecrase la vitesse -- c'est pourquoi
# les appels de moins de 200 jetons de sortie sont ecartes du calcul (et leur
# nombre publie). Enfin ces appels partagent une file avec d'autres clients du
# fournisseur : une tranche peu peuplee ne prouve rien.

import io
import json
import sys
import datetime

CHEMIN = sys.argv[1]
FENETRES = []
for a in sys.argv[2:]:
    nom, plage = a.split("=", 1)
    d, f = (plage.split(",") + [""])[:2]
    FENETRES.append((nom, d.strip(), f.strip()))

TRANCHES = [(0, 8000), (8000, 20000), (20000, 40000), (40000, 80000),
            (80000, 10 ** 9)]
MIN_SORTIE = 200


def hhmm(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M")


def med(x):
    x = sorted(x)
    return x[len(x) // 2] if x else 0.0


v = [json.loads(l) for l in io.open(CHEMIN, encoding="utf-8") if l.strip()]
v = [d for d in v if d.get("kind") == "call" and d.get("status") == 200]
v.sort(key=lambda d: d["t0"])

for nom, deb, fin in FENETRES:
    sel = [d for d in v
           if (not deb or hhmm(d["t0"]) >= deb) and (not fin or hhmm(d["t0"]) < fin)
           and (d.get("usage") or {}).get("prompt_tokens")]
    court = [d for d in sel
             if (d["usage"].get("completion_tokens") or 0) < MIN_SORTIE]
    utile = [d for d in sel
             if (d["usage"].get("completion_tokens") or 0) >= MIN_SORTIE]
    if not utile:
        print("%-4s : aucun appel de plus de %d jetons de sortie."
              % (nom, MIN_SORTIE))
        print()
        continue

    print("=== %s : %d appels retenus (%d ecartes, sortie < %d jetons) ==="
          % (nom, len(utile), len(court), MIN_SORTIE))
    print("  %-18s %5s  %11s  %10s  %9s"
          % ("contexte d'entree", "n", "sortie med", "duree med", "jet/s med"))
    for lo, hi in TRANCHES:
        t = [d for d in utile if lo <= d["usage"]["prompt_tokens"] < hi]
        if not t:
            continue
        vit = [(d["usage"]["completion_tokens"]) / (d["ms"] / 1000.0) for d in t]
        etq = "%d-%dk" % (lo // 1000, hi // 1000) if hi < 10 ** 9 \
            else "%dk et plus" % (lo // 1000)
        print("  %-18s %5d  %11.0f  %9.1f s  %9.1f"
              % (etq, len(t), med([d["usage"]["completion_tokens"] for d in t]),
                 med([d["ms"] / 1000.0 for d in t]), med(vit)))
    gv = med([(d["usage"]["completion_tokens"]) / (d["ms"] / 1000.0)
              for d in utile])
    print("  %-18s %5d %35.1f" % ("TOUTES TRANCHES", len(utile), gv))
    print()

print("LECTURE. Une vitesse qui chute d'une tranche a la suivante est l'effet")
print("attendu de l'attention sur un cache KV qui grossit : le meme modele")
print("decode plus lentement dans une conversation longue. Cet effet n'est PAS")
print("un defaut de harnais, mais la longueur de la conversation, elle, est un")
print("choix de l'agent.")
