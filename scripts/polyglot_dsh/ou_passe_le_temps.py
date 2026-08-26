# OU PASSE LE TEMPS : dans le LLM, ou dans le harnais ?
#
# LA QUESTION. dsh met 537 s la ou pi met 141 s sur le meme exercice, avec le
# MEME modele, le MEME fournisseur et la MEME configuration de pilote (verifie
# sur _run_dev_*_fils.ps1 : seuls --agent et --conteneur different). « dsh est
# lent » ne dit pas POURQUOI, et les deux causes possibles appellent des
# corrections opposees :
#
#   (a) HARNAIS. Le temps se passe HORS des appels LLM -- demarrage de
#       conteneur, compilation, entrees/sorties, attentes. C'est de la plomberie
#       et ca se corrige sans toucher a l'agent.
#   (b) COMPORTEMENT. Le temps se passe DANS les appels : l'agent en fait plus,
#       ou les fait plus longs (plus de tours d'outil, contexte qui enfle,
#       raisonnement plus bavard). Le harnais n'y est alors pour rien.
#
# On ne peut pas trancher au chronometre global. Le proxy 8009 journalise chaque
# appel avec t0 et ms : la somme des ms est le temps LLM, l'empan est le temps
# total, et la difference est tout le reste.
#
# CE QUE CETTE MESURE NE DIT PAS. L'empan va du PREMIER au DERNIER appel : le
# temps avant le premier appel (demarrage du conteneur, copie du corpus) n'y
# est pas. La fraction hors-LLM est donc une BORNE INFERIEURE.
#
# Les appels sont attribues a un agent par fenetre temporelle, pas par
# etiquette : le proxy ne marque pas qui appelle. Les bornes sont donnees en
# argument et doivent venir des journaux de run, jamais devinees.

import io
import json
import sys
import datetime

CHEMIN = sys.argv[1]
# Fenetres : "nom=debut,fin" en heure locale HH:MM. fin vide = jusqu'au bout.
FENETRES = []
for a in sys.argv[2:]:
    nom, plage = a.split("=", 1)
    d, f = (plage.split(",") + [""])[:2]
    FENETRES.append((nom, d.strip(), f.strip()))


def hhmm(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M")


v = [json.loads(l) for l in io.open(CHEMIN, encoding="utf-8") if l.strip()]
v = [d for d in v if d.get("kind") == "call"]
v.sort(key=lambda d: d["t0"])
print("journal : %s   %d appels   de %s a %s"
      % (CHEMIN.split("/")[-1], len(v), hhmm(v[0]["t0"]), hhmm(v[-1]["t0"])))
print()

if not FENETRES:
    FENETRES = [("tous", "", "")]

for nom, deb, fin in FENETRES:
    sel = [d for d in v
           if (not deb or hhmm(d["t0"]) >= deb) and (not fin or hhmm(d["t0"]) < fin)]
    if not sel:
        print("%-6s : aucun appel dans la fenetre %s-%s" % (nom, deb, fin))
        continue
    empan = (max(d["t0"] + d["ms"] for d in sel) - min(d["t0"] for d in sel)) / 1000.0
    llm = sum(d["ms"] for d in sel) / 1000.0
    ent = sum((d.get("usage") or {}).get("prompt_tokens") or 0 for d in sel)
    sor = sum((d.get("usage") or {}).get("completion_tokens") or 0 for d in sel)
    cout = sum((d.get("usage") or {}).get("cost") or 0 for d in sel)
    msgs = [(d.get("sent") or {}).get("n_messages") or 0 for d in sel]
    err = [d for d in sel if d.get("status") != 200]
    ms = sorted(d["ms"] for d in sel)

    print("=== %s   (%s -> %s) ===" % (nom, hhmm(sel[0]["t0"]), hhmm(sel[-1]["t0"])))
    print("  appels            : %d   (%d hors 200)" % (len(sel), len(err)))
    print("  empan 1er->dernier: %8.0f s" % empan)
    print("  temps DANS le LLM : %8.0f s   = %.0f %% de l'empan" % (llm, 100.0 * llm / max(1, empan)))
    print("  temps HORS LLM    : %8.0f s   = %.0f %%  (BORNE INFERIEURE)"
          % (empan - llm, 100.0 * (empan - llm) / max(1, empan)))
    print("  duree d'appel     : med %.1f s   p90 %.1f s   max %.1f s"
          % (ms[len(ms) // 2] / 1000.0, ms[int(0.9 * (len(ms) - 1))] / 1000.0, ms[-1] / 1000.0))
    print("  jetons            : entree %d   sortie %d   (%.1f entree/sortie)"
          % (ent, sor, ent / max(1.0, sor)))
    print("  messages/appel    : med %d   max %d   (croissance du contexte)"
          % (sorted(msgs)[len(msgs) // 2], max(msgs)))
    print("  cout              : %.4f $" % cout)
    print()

print("LECTURE. Une fraction HORS LLM elevee accuse le harnais. Une fraction")
print("DANS le LLM elevee avec beaucoup d'appels accuse le comportement de")
print("l'agent (il en fait plus), et avec peu d'appels longs accuse le modele")
print("ou la longueur du contexte. Les trois se corrigent differemment.")
