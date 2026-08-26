# LE BUDGET RECUPERE-T-IL LES FUYARDS, OU LES TUE-T-IL PROPREMENT ?
#
# C'est LA question qui decide du reglage, et elle ne se lit pas dans un taux
# global. Dans le bras illimite les appels qui n'ont jamais ferme leur pensee
# etaient justes 0 fois sur 5 : leur calcul etait entierement perdu. Si, sous
# budget, les appels COUPES repondent juste a un taux non nul, le dispositif
# convertit du calcul mort en mesure. S'ils repondent au hasard (25 % sur du
# QCM a 4 options), il ne fait que remplacer une non-mesure par du bruit -- ce
# qui est PIRE, parce que le bruit entre dans le score sans se signaler.
#
# On coupe la population en deux a un seuil, et on lit le taux de chaque cote.
# Seuil par defaut : 7800, sous le budget de 8192 et au-dessus de tout appel
# naturellement convergent observe.

import io
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8005"
SEUIL = int(sys.argv[2]) if len(sys.argv) > 2 else 7800


def n_jetons(txt):
    if not txt:
        return 0
    req = urllib.request.Request(
        BASE + "/tokenize", data=json.dumps({"content": txt}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return len(json.loads(r.read().decode("utf-8", "replace")).get("tokens") or [])


MARQUE = "thinking budget is now exhausted"

coupes, libres = [], []
for ligne in io.open(sys.argv[1], encoding="utf-8"):
    ligne = ligne.strip()
    if not ligne:
        continue
    d = json.loads(ligne)
    txt = d.get("reponse") or ""
    m = re.search(r"<think>(.*?)</think>", txt, re.S)
    pensee = m.group(1) if m else (txt.split("</think>")[0] if "</think>" in txt else "")
    # Deux temoins independants de la coupure : le message de transition, qui
    # n'apparait QUE quand le budget est epuise, et la longueur.
    n = n_jetons(pensee)
    if MARQUE in pensee or n >= SEUIL:
        coupes.append(d)
    else:
        libres.append(d)


def lire(nom, v):
    if not v:
        print("  %-24s n=0" % nom)
        return
    j = sum(1 for d in v if d.get("juste"))
    print("  %-24s n=%-3d  justes %5.1f %%" % (nom, len(v), 100.0 * j / len(v)))


print("fichier : %s   seuil : %d jetons de pensee" % (sys.argv[1], SEUIL))
print()
lire("pensee LIBRE", libres)
lire("pensee COUPEE au budget", coupes)
print()
print("REPERES : hasard sur QCM 4 options = 25,0 %.")
print("  Dans le bras illimite, la population equivalente (jamais fermee,")
print("  plafond mange) etait juste 0 fois sur 5 -- calcul entierement perdu.")
print("  Au-dessus de 25 %% la coupure recupere ; a 25 %% elle fabrique du")
print("  bruit qui entre dans le score sans se signaler.")
