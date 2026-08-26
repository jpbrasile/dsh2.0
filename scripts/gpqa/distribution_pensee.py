# Distribution des jetons de PENSEE (pas de sortie) d'un bras GPQA.
#
# La difference compte : `tokens_sortie` melange la pensee et la reponse. Le
# reglage du budget porte sur la pensee seule. On separe les appels CONVERGENTS
# (le modele a ferme son bloc tout seul) des NON CONVERGENTS (jamais ferme,
# plafond mange) -- c'est cette separation qui decide du budget, parce que la
# litterature montre qu'elle est presque synonyme de juste/faux.
#
# PIEGE DE STOCKAGE, decouvert le 26/08 et qui invalide une lecture naive :
# gpqa_diamond.py ne garde que la QUEUE de la reponse ([-4000:] avant le
# correctif, [-24000:] apres). Sur une reponse longue, la balise <think>
# OUVRANTE est donc absente du journal alors qu'elle existait bel et bien dans
# la generation. Compter uniquement les blocs <think>...</think> complets ne
# mesure donc QUE LES COURTS : l'echantillon est tronque par le haut, et la
# distribution qui en sort est fausse dans le sens qui arrange.
#
# On distingue quatre cas, et on le DIT :
#   complet      <think> et </think> presents      -> valeur EXACTE
#   ouverture    </think> seul (ouverture rognee)  -> BORNE INFERIEURE
#   non converge finish_reason == length            -> a mange le plafond
#   sans pensee  ni l'un ni l'autre, fin normale    -> pas de pensee
#
# Tokenisation par le /tokenize DU SERVEUR, pas par une regle chars/4 : ce texte
# telegraphique fait ~3 caracteres par jeton, et l'approximation a deja masque
# un mur a 512 pendant vingt heures.

import io
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8005"


def n_jetons(txt):
    if not txt:
        return 0
    req = urllib.request.Request(
        BASE + "/tokenize", data=json.dumps({"content": txt}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return len(json.loads(r.read().decode("utf-8", "replace")).get("tokens") or [])


def quantile(v, q):
    if not v:
        return 0
    v = sorted(v)
    return v[int(round(q * (len(v) - 1)))]


def resume(nom, v, note=""):
    if not v:
        print("  %-28s n=0" % nom)
        return
    print("  %-28s n=%-3d  min %-6d med %-6d p75 %-6d p90 %-6d MAX %-6d %s"
          % (nom, len(v), min(v), quantile(v, .5), quantile(v, .75),
             quantile(v, .9), max(v), note))


chemin = sys.argv[1]
exact, borne_inf, plafond = [], [], []
n_sans = 0
juste = {"exact": [0, 0], "borne": [0, 0], "plafond": [0, 0], "sans": [0, 0]}

for ligne in io.open(chemin, encoding="utf-8"):
    ligne = ligne.strip()
    if not ligne:
        continue
    d = json.loads(ligne)
    txt = d.get("reponse") or ""
    coupe_plafond = d.get("finish_reason") == "length"
    m = re.search(r"<think>(.*?)</think>", txt, re.S)
    if m and not coupe_plafond:
        exact.append(n_jetons(m.group(1)))
        cle = "exact"
    elif "</think>" in txt and not coupe_plafond:
        borne_inf.append(n_jetons(txt.split("</think>")[0]))
        cle = "borne"
    elif coupe_plafond:
        plafond.append(d.get("tokens_sortie") or 0)
        cle = "plafond"
    else:
        n_sans += 1
        cle = "sans"
    juste[cle][0] += 1 if d.get("juste") else 0
    juste[cle][1] += 1

tot = sum(v[1] for v in juste.values())
print("fichier : %s" % chemin)
print()
print("appels : %d" % tot)
for cle, nom in (("exact", "pensee complete (exacte)"),
                 ("borne", "ouverture rognee (borne inf)"),
                 ("plafond", "NON CONVERGENT (plafond)"),
                 ("sans", "sans pensee")):
    b, n = juste[cle]
    if n:
        print("  %-30s %3d (%5.1f %%)   justes %5.1f %%"
              % (nom, n, 100.0 * n / tot, 100.0 * b / n))
print()
print("jetons de PENSEE")
resume("mesure exacte", exact)
resume("borne inferieure", borne_inf, "(vraie valeur >=)")
print("jetons de SORTIE des non convergents")
resume("plafond mange", plafond)
print()
if exact and borne_inf:
    print("LECTURE : si la borne inferieure depasse deja le MAX des exacts,")
    print("l'echantillon exact est tronque par le haut -- ne pas s'en servir")
    print("seul pour choisir un budget.")
