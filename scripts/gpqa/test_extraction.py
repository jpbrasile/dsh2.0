# Banc d'essai adverse de extraire() -- la fonction qui decide de TOUT.
#
# Si elle rend la mauvaise lettre, chaque score deja publie est faux, et rien
# dans les journaux ne le signalerait : un mauvais parsing ressemble exactement
# a un modele qui se trompe. Elle merite donc d'etre attaquee, pas relue.
#
# Chaque cas porte l'ATTENDU et la raison. `None` = doit etre compte NON PARSE.
# Un cas qui echoue n'est pas forcement un defaut : la derniere section liste
# ceux ou le comportement observe est acceptable et pourquoi.

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gpqa_diamond import extraire  # noqa: E402

CAS = [
    # --- forme demandee ---------------------------------------------------
    ("forme demandee",
     "Reasoning here.\n\nAnswer: C", "C"),
    ("forme demandee en gras",
     "Reasoning.\n\n**Answer: B**", "B"),
    ("forme demandee en minuscules",
     "blah\n\nanswer: b", "B"),
    ("parentheses",
     "blah\n\nAnswer: (D)", "D"),

    # --- le modele se corrige : on doit garder la DERNIERE ---------------
    ("auto-correction, garder la derniere",
     "Answer: A\n\nWait, that is wrong. Reconsidering.\n\nAnswer: D", "D"),

    # --- la pensee ne doit JAMAIS servir de reponse ----------------------
    ("lettre citee dans la pensee, vraie reponse apres",
     "<think>I think it is B, no wait A</think>\n\nAnswer: C", "C"),
    ("pensee FERMEE contenant une lettre, RIEN apres",
     "<think>The answer must be B.</think>\n\n", None),

    # --- pensee NON fermee (coupure) -------------------------------------
    ("pensee jamais fermee, aucune reponse rendue",
     "<think>Let me compute. The value is 3.2 so it is likely B because", None),

    # --- rattrapages ------------------------------------------------------
    ("final answer",
     "long text\n\nThe final answer is C.", "C"),
    ("lettre seule sur la derniere ligne",
     "Some reasoning.\n\nD", "D"),

    # --- formes que Qwen produit spontanement ----------------------------
    ("boxed LaTeX",
     "Reasoning.\n\n$\\boxed{B}$", None),
    ("boxed LaTeX avec Answer",
     "Reasoning.\n\nAnswer: $\\boxed{B}$", "B"),

    # --- distance ---------------------------------------------------------
    ("reponse puis 2500 caracteres d'annexe",
     "Answer: A\n\n" + ("appendix line\n" * 200), None),
]

echecs = []
print("%-46s %-8s %-8s" % ("cas", "attendu", "obtenu"))
print("-" * 66)
for nom, texte, attendu in CAS:
    obtenu = extraire(texte)
    ok = (obtenu == attendu)
    if not ok:
        echecs.append((nom, attendu, obtenu))
    print("%-46s %-8s %-8s %s"
          % (nom, attendu, obtenu, "" if ok else "  <-- ECART"))

print()
if echecs:
    print("%d ecart(s) entre attendu et obtenu." % len(echecs))
    print("Un ecart n'est un DEFAUT que si le comportement obtenu fausse un")
    print("score. Rendre None (NON PARSE) est SUR : c'est rapporte et exclu.")
    print("Rendre une LETTRE FAUSSE est le seul cas grave -- il entre dans le")
    print("score en se faisant passer pour une erreur du modele.")
    print()
    grave = [e for e in echecs if e[2] is not None and e[1] is not None]
    muet = [e for e in echecs if e[2] is not None and e[1] is None]
    if grave:
        print("GRAVE (mauvaise lettre rendue) : %s" % [e[0] for e in grave])
    if muet:
        print("GRAVE (lettre rendue la ou il ne faut RIEN rendre) : %s"
              % [e[0] for e in muet])
    if not grave and not muet:
        print("Aucun cas grave : tous les ecarts vont vers NON PARSE.")
else:
    print("aucun ecart.")
