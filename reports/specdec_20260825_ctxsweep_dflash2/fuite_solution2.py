"""Reprise de la mesure de fuite, deux defauts corriges.

Defaut 1 : je prenais le MAXIMUM de similarite sur tous les fichiers solution.
Pour C++ cela selectionnait le header (`#pragma once`, deux includes, une
signature) -- 9 lignes dictees par le sujet, identiques par construction. D'ou
un faux 100 %.

Defaut 2 : je ne regardais pas la TAILLE. Une similarite n'a de sens que sur un
fichier assez gros pour que la convergence spontanee soit improbable.

Ici : un fichier par exercice, le plus gros ; sa longueur normalisee affichee a
cote ; et la queue de sortie de l'agent pour les suspects.
"""
import difflib
import glob
import io
import json
import os
import re

RUN = (r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
       r"\dsh-polyglot-estim-p6")

COMMENTAIRE = {".py": r"#.*", ".rs": r"//.*", ".go": r"//.*",
               ".js": r"//.*", ".cpp": r"//.*", ".h": r"//.*", ".java": r"//.*"}
PLANCHER = 400   # caracteres normalises en dessous desquels on ne conclut rien


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


lignes = []
for res in sorted(glob.glob(os.path.join(RUN, "*", "exercises", "practice", "*",
                                         ".dsh.results.json"))):
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

    # le plus GROS fichier solution, pas le plus ressemblant
    cible, na, ext = None, "", ""
    for sol in solutions:
        a = lire(os.path.join(ex_dir, sol))
        if a is None:
            continue
        e = os.path.splitext(sol)[1]
        n = normaliser(a, e)
        if len(n) > len(na):
            cible, na, ext = sol, n, e
    if cible is None:
        continue

    meilleur, contre = 0.0, ""
    for exm in exemples:
        b = lire(os.path.join(ex_dir, exm))
        if b is None:
            continue
        r = difflib.SequenceMatcher(None, na, normaliser(b, ext)).ratio()
        if r > meilleur:
            meilleur, contre = r, exm

    d = json.loads(lire(res))
    outc = d.get("tests_outcomes", [])
    lignes.append((meilleur, len(na), nom,
                   "PASS" if (outc and outc[-1]) else "FAIL", cible, contre, d))

lignes.sort(reverse=True)
print("similarite du PLUS GROS fichier solution avec .meta/example")
print("(taille = caracteres normalises du fichier produit ; "
      "en dessous de %d on ne conclut rien)" % PLANCHER)
print("")
print("%-8s %6s %-34s %-5s %s" % ("simil.", "taille", "exercice", "issue", "produit"))
for r, taille, nom, issue, cible, contre, _ in lignes:
    drapeau = " <<<" if (r > 0.80 and taille >= PLANCHER) else ""
    print("%7.1f%% %6d %-34s %-5s %s%s" % (100 * r, taille, nom, issue, cible, drapeau))

gros = [x for x in lignes if x[1] >= PLANCHER]
if gros:
    vals = sorted(x[0] for x in gros)
    print("")
    print("sur les %d fichiers d'au moins %d caracteres :" % (len(gros), PLANCHER))
    print("  mediane %.1f %%   max %.1f %%   >80%% : %d"
          % (100 * vals[len(vals) // 2], 100 * vals[-1],
             sum(1 for v in vals if v > 0.80)))

print("")
print("=" * 70)
print("QUEUE DE SORTIE DE L'AGENT -- les 4 plus ressemblants (taille suffisante)")
print("=" * 70)
for r, taille, nom, issue, cible, contre, d in gros[:4]:
    print("")
    print("--- %s  (%.1f %% vs %s, %d car., %s)" % (nom, 100 * r, contre, taille, issue))
    for t in d.get("turns", []):
        q = (t.get("sortie_queue") or "").replace("\n", " | ")
        print("    tour %s : %s" % (t.get("tour"), q[:500]))
