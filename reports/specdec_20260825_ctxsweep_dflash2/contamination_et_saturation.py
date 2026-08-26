# -*- coding: utf-8 -*-
"""Deux controles calculables sur les donnees DEJA sur disque, sans GPU.

A. SATURATION MARGINALE (aider, 4 tours). Le gain apporte par la tentative
   n+1. C'est le graphique qui teste directement la these "plus de cycles
   utiles" : si la courbe sature a 3 tentatives, la these tombe.

B. SIGNAL DE CONTAMINATION. Le run aider est le meilleur substrat possible
   pour ce test, et c'est un hasard heureux : le modele y ecrit A L'AVEUGLE
   -- pas de fichier de test, pas d'execution, pas de .meta. Ce qu'il produit
   ne peut donc PAS avoir ete ajuste a des assertions lues. S'il retrouve
   malgre tout la solution canonique d'Exercism, l'explication tient en un
   mot : il l'a memorisee.

   Le controle interne : comparer la distribution de similarite des exercices
   REUSSIS a celle des exercices RATES. Deux solutions correctes du meme
   petit probleme se ressemblent par construction -- c'est le plancher de
   convergence spontanee, pas de la memorisation. Si les deux distributions
   se superposent, la similarite ne dit rien. Si les reussis sont nettement
   au-dessus, il faut aller regarder.

   Ce script ne CONCLUT pas a la contamination : il dit s'il y a lieu de
   lancer la sonde de completion, qui, elle, est decisive.
"""
import difflib
import glob
import io
import json
import os
import re

RUN = (r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
       r"\2026-08-25-19-06-21--dsh-q8q4-160k-16k-t1-tries4-full")

COMMENTAIRE = {".py": r"#.*", ".rs": r"//.*", ".go": r"//.*",
               ".js": r"//.*", ".cpp": r"//.*", ".h": r"//.*", ".java": r"//.*"}
PLANCHER = 400   # caracteres normalises : en dessous, on ne conclut rien


def normaliser(texte, ext):
    motif = COMMENTAIRE.get(ext)
    if motif:
        texte = re.sub(motif, "", texte)
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    return re.sub(r"\s+", "", texte)


def lire(chemin):
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def quant(t, q):
    if not t:
        return float("nan")
    return sorted(t)[int(round(q * (len(t) - 1)))]


resultats = sorted(glob.glob(os.path.join(
    RUN, "*", "exercises", "practice", "*", ".aider.results.json")))

# ---------------------------------------------------------------- A ----
outcomes = []
for res in resultats:
    d = json.loads(lire(res) or "{}")
    o = d.get("tests_outcomes", [])
    if o:
        outcomes.append(o)

n = len(outcomes)
print("=" * 72)
print("A. SATURATION MARGINALE -- aider polyglot, %d exercices, 4 tours" % n)
print("=" * 72)
print("")
print("%-10s %8s %10s %12s %14s"
      % ("tentative", "gain", "cumul", "taux cumule", "gain marginal"))
cumul = 0
prec = 0.0
for k in range(1, 5):
    gain = sum(1 for o in outcomes if len(o) >= k and o[k - 1] and
               not any(o[:k - 1]))
    cumul += gain
    taux = 100.0 * cumul / n
    print("%-10d %8d %10d %11.1f %% %13.1f pt"
          % (k, gain, cumul, taux, taux - prec))
    prec = taux
print("")
print("Lecture : la these 'plus de cycles utiles' exige que le gain marginal")
print("ne soit pas retombe a zero a la derniere tentative mesuree. Un gain")
print("encore franc au tour 4 dit que le plafond n'est PAS atteint -- et")
print("qu'un banc a 2 tentatives sous-estime le systeme, ce qui est une")
print("affirmation testable, pas un argument.")

# ---------------------------------------------------------------- B ----
lignes = []
for res in resultats:
    ex_dir = os.path.dirname(res)
    p = os.path.normpath(res).split(os.sep)
    nom = "%s/%s" % (p[-5], p[-2])
    cfg = lire(os.path.join(ex_dir, ".meta", "config.json"))
    if not cfg:
        continue
    fics = json.loads(cfg).get("files", {})
    solutions, exemples = fics.get("solution", []), fics.get("example", [])
    if not solutions or not exemples:
        continue

    cible, na, ext = None, "", ""
    for sol in solutions:
        a = lire(os.path.join(ex_dir, sol))
        if a is None:
            continue
        e = os.path.splitext(sol)[1]
        norm = normaliser(a, e)
        if len(norm) > len(na):
            cible, na, ext = sol, norm, e
    if cible is None or len(na) < PLANCHER:
        continue

    meilleur, contre = 0.0, ""
    for exm in exemples:
        b = lire(os.path.join(ex_dir, exm))
        if b is None:
            continue
        r = difflib.SequenceMatcher(None, na, normaliser(b, ext)).ratio()
        if r > meilleur:
            meilleur, contre = r, exm

    d = json.loads(lire(res) or "{}")
    o = d.get("tests_outcomes", [])
    lignes.append((meilleur, len(na), nom, bool(o and o[-1]), cible, contre))

lignes.sort(reverse=True)
print("")
print("=" * 72)
print("B. SIGNAL DE CONTAMINATION -- solution ecrite A L'AVEUGLE vs canonique")
print("=" * 72)
print("%d exercices d'au moins %d caracteres normalises" % (len(lignes), PLANCHER))

for etiq, sel in (("REUSSIS", True), ("RATES", False)):
    v = [x[0] for x in lignes if x[3] == sel]
    if not v:
        continue
    print("")
    print("  %-8s n=%-4d  mediane %5.1f %%   q75 %5.1f %%   q90 %5.1f %%   "
          "max %5.1f %%   >80%% : %d"
          % (etiq, len(v), 100 * quant(v, 0.5), 100 * quant(v, 0.75),
             100 * quant(v, 0.9), 100 * max(v),
             sum(1 for x in v if x > 0.80)))

tous = [x[0] for x in lignes]
suspects = [x for x in lignes if x[0] > 0.80]
print("")
print("  ENSEMBLE  n=%d  mediane %.1f %%   >80%% : %d (%.1f %%)"
      % (len(tous), 100 * quant(tous, 0.5), len(suspects),
         100.0 * len(suspects) / max(1, len(tous))))
print("")
if suspects:
    print("  au-dessus de 80 %% -- a inspecter un par un :")
    for r, taille, nom, ok, cible, contre in suspects:
        print("    %6.1f %%  %-34s %-4s %6d car.  %s"
              % (100 * r, nom, "PASS" if ok else "FAIL", taille, cible))
else:
    print("  aucun exercice au-dessus de 80 %%.")

print("")
print("  les 10 plus ressemblants :")
for r, taille, nom, ok, cible, contre in lignes[:10]:
    print("    %6.1f %%  %-34s %-4s %6d car." % (100 * r, nom,
                                                 "PASS" if ok else "FAIL", taille))

vr = [x[0] for x in lignes if x[3]]
vf = [x[0] for x in lignes if not x[3]]
print("")
print("VERDICT DE CE CONTROLE (il ne conclut pas a la contamination) :")
if vr and vf:
    ecart = 100 * (quant(vr, 0.5) - quant(vf, 0.5))
    print("  ecart de mediane reussis - rates : %+.1f point." % ecart)
    print("  Un ecart faible dit que la similarite mesure la convergence")
    print("  spontanee de deux solutions correctes du meme petit probleme,")
    print("  pas du rappel. Un ecart franc, plus les cas >80 %%, justifie la")
    print("  sonde de completion -- la seule mesure decisive.")
