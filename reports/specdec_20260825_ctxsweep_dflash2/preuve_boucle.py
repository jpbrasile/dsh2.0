"""L'agent dsh execute-t-il LUI-MEME la suite de tests ?

C'est la question qui decide si 92,1 % et 52,5 % se comparent.

Dans le banc aider polyglot, le modele ecrit le fichier a l'aveugle : il ne voit
jamais le fichier de test, ne compile pas, n'execute rien. C'est le HARNAIS qui
lance les tests entre deux tours et lui renvoie la sortie d'echec.

dsh est un agent avec un shell. Si sa queue de sortie parle d'avoir lance les
tests, alors il a boucle contre la suite reelle DANS un tour -- autant de fois
qu'il voulait. Les deux nombres ne mesurent alors pas la meme chose.

Sortie forcee en UTF-8 : la console Windows est en cp1252 et les fleches
Unicode des reponses du modele la font tomber.
"""
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

RUN = (r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
       r"\dsh-polyglot-estim-p6")

# formulations qui n'ont de sens que si l'agent a VU une sortie de test
PREUVES = [
    (r"all tests? (?:passed|pass)", "dit que les tests passent"),
    (r"\d+ (?:assertions?|tests?) (?:passed|in \d+ test)", "cite un compte de tests"),
    (r"\b(?:pytest|cargo test|go test|gradlew|ctest|npm test)\b", "nomme la commande de test"),
    (r"tests? (?:now )?pass", "dit que les tests passent"),
    (r"\bcmake\b", "a lance cmake"),
    (r"(?:ran|running|executed|re-?ran) the tests?", "dit avoir lance les tests"),
]

total, avec_preuve = 0, []
for res in sorted(glob.glob(os.path.join(RUN, "*", "exercises", "practice", "*",
                                         ".dsh.results.json"))):
    d = json.loads(io.open(res, encoding="utf-8", errors="replace").read())
    p = os.path.normpath(res).split(os.sep)
    nom = "%s/%s" % (p[-5], p[-2])
    total += 1
    texte = " ".join((t.get("sortie_queue") or "") for t in d.get("turns", []))
    bas = texte.lower()
    trouves = sorted({etiq for motif, etiq in PREUVES if re.search(motif, bas)})
    if trouves:
        outc = d.get("tests_outcomes", [])
        avec_preuve.append((nom, "PASS" if (outc and outc[-1]) else "FAIL", trouves))

print("exercices dont la sortie d'agent prouve qu'il a lance les tests : %d / %d"
      % (len(avec_preuve), total))
print("")
print("%-34s %-5s %s" % ("exercice", "issue", "indices"))
for nom, issue, trouves in avec_preuve:
    print("%-34s %-5s %s" % (nom, issue, " ; ".join(trouves)))

print("")
print("RAPPEL : la queue ne garde que les 600 derniers caracteres du DERNIER")
print("message de chaque tour. Un agent qui a lance les tests sans le dire dans")
print("ces 600 caracteres n'apparait pas ici. Ce compte est donc un PLANCHER.")
