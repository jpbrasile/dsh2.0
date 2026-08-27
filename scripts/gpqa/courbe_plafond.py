"""Quel plafond fermerait l'encadrement ? -- analyse SANS carte.

Le plan prevoyait B2 « rattrapage a 32768 ». Le bras EST a 32768 et tronque
quand meme. La question n'est donc plus « rattraper » mais « a quel plafond ».
Deux facons de repondre, toutes deux dans les fichiers deja produits :

  1. la COURBE de troncature en fonction du plafond, sur les bras deja joues ;
  2. la QUEUE de la distribution des appels LIBRES du bras 32768 -- si les
     libres s'arretent tres en dessous de 32768, les tronques ne sont pas des
     appels « un peu trop longs », c'est une population a part (fugue), et
     AUCUN plafond raisonnable ne les recupere.
"""
import json, os, statistics as st

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")

BRAS = [
    ("budget 512",      "local_q4_t1_budget512.jsonl"),
    ("budget 8192",     "local_q4_t1_b8192_tournant.jsonl"),
    ("budget 8192 (4rot)", "local_q4_t1_b8192_4rot_partiel.jsonl"),
    ("illimite",        "local_q4_t1_illimite.jsonl"),
    ("budget illimite", "local_q4_t1_budget_illimite.jsonl"),
    ("LIBRE 32768",     "local_q4_t1_libre_tournant.jsonl"),
]

def charger(nom):
    c = os.path.join(BASE, nom)
    if not os.path.exists(c):
        return None
    out = []
    with open(c, encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out

print("=== 1. COURBE DE TRONCATURE PAR BRAS ===")
print("%-22s %5s %9s %8s %9s" % ("bras", "n", "plafond", "tronq", "part"))
for nom, fich in BRAS:
    recs = charger(fich)
    if not recs:
        print("%-22s   (absent)" % nom)
        continue
    plaf = st.mode([r.get("max_tokens") for r in recs if r.get("max_tokens")]) \
        if any(r.get("max_tokens") for r in recs) else None
    t = sum(1 for r in recs if r.get("finish_reason") == "length")
    print("%-22s %5d %9s %8d %8.1f %%"
          % (nom, len(recs), plaf if plaf else "?", t, 100.0 * t / len(recs)))

print()
print("=== 2. LA QUEUE DES LIBRES DU BRAS 32768 ===")
recs = charger("local_q4_t1_libre_tournant.jsonl")
libres = sorted(r["tokens_sortie"] for r in recs
                if r.get("finish_reason") != "length" and r.get("tokens_sortie"))
n = len(libres)
print("n libres = %d" % n)
for q in (50, 75, 90, 95, 99, 100):
    i = min(n - 1, int(round(q / 100.0 * n)) - 1 if q < 100 else n - 1)
    print("  p%-3d : %6d jetons" % (q, libres[i]))
print("  max  : %6d jetons  (plafond 32768)" % libres[-1])
print()
marge = 32768 - libres[-1]
print("Le libre le plus long s'arrete %d jetons SOUS le plafond (%.0f %% du plafond)."
      % (marge, 100.0 * libres[-1] / 32768))
print()
print("LECTURE. Si le plus long des libres est tres en dessous du plafond, les")
print("tronques ne sont pas des appels « un peu trop longs » qu'un plafond un cran")
print("plus haut recupererait : c'est une population a part -- une FUGUE, le meme")
print("regime deja vu sur dsh (4 tirages sur 9 morts a 16 384 pile). Monter le")
print("plafond n'achete alors que du temps de carte, pas des mesures.")
