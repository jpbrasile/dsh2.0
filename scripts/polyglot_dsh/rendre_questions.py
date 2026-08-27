# -*- coding: utf-8 -*-
"""Rend `questions_reformulees.json` en QUESTIONS_REFORMULEES.md.

Le JSON est la SOURCE : il est lu par le pilote (`--questions`) et par ce
rendu. Editer le .md a la main les ferait diverger, et on publierait une raison
qui n'est pas celle qui a servi.

USAGE : python rendre_questions.py
"""
import io
import json
import os

ICI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ICI, "questions_reformulees.json")
DST = os.path.join(ICI, "QUESTIONS_REFORMULEES.md")

DEGRES = {
    "A": ("désambiguïsation interne",
          "L'énoncé se contredit lui-même ; on ne garde que la forme qui fait "
          "foi. **Aucune information n'entre** : tout était déjà écrit dans "
          "l'énoncé. Reste comparable à la variante D."),
    "B": ("mise en garde générique",
          "On signale qu'une **classe** d'ambiguïté existe, sans dire de quel "
          "côté elle tombe. Ne cite aucun exercice, s'applique au corpus "
          "entier. C'est une amélioration de **consigne**, pas une réponse."),
    "C": ("révélation",
          "On donne la convention attendue. Elle vient de la **suite cachée**. "
          "Contamination maximale : ne se compare ni à la variante D ni au "
          "banc aider, et ne sert qu'à chiffrer le coût de l'ambiguïté."),
}


def main():
    doc = json.load(io.open(SRC, encoding="utf-8"))
    L = ["# Questions reformulées",
         "",
         "**Fichier généré — ne pas éditer à la main.** Source :",
         "`questions_reformulees.json`, régénérer avec `rendre_questions.py`.",
         "",
         "Autorisé le 27/08 : *« tu as le droit d'optimiser les questions à "
         "condition de tracer la raison, puis tu rejoues le test case. »* La "
         "raison est donc ici, et le résultat de chaque run porte le texte "
         "exact qui a été ajouté.",
         "",
         "## Les trois degrés",
         "",
         "| degré | nom | ce que ça implique |",
         "|---|---|---|"]
    for d in ("A", "B", "C"):
        nom, quoi = DEGRES[d]
        L.append("| **%s** | %s | %s |" % (d, nom, quoi))
    L += ["",
          "Le pilote n'ajoute **rien** sans `--degres` : la variante D reste le",
          "défaut, et un résultat sans reformulation porte une liste vide.",
          ""]

    L += ["## Ajouts génériques", "",
          "Ils ne citent aucun exercice et s'appliqueraient au corpus entier.",
          ""]
    for a in doc.get("generiques", []):
        nom, _ = DEGRES.get(a["degre"], ("?", ""))
        L += ["### `%s` — degré %s (%s)" % (a["id"], a["degre"], nom), "",
              "- **Issu de** : `%s`" % a["issu_de"],
              "- **Constat** : %s" % a["constat"],
              "- **Raison** : %s" % a["raison"], "",
              "> %s" % a["texte"], ""]

    L += ["## Ajouts visant un exercice", "",
          "Ceux-ci nomment un exercice. Un degré **C** y révèle une convention",
          "que seule la suite cachée porte : à n'employer que pour chiffrer le",
          "coût de l'ambiguïté, jamais dans une colonne comparée au banc.",
          ""]
    for a in doc.get("par_exercice", []):
        nom, _ = DEGRES.get(a["degre"], ("?", ""))
        L += ["### `%s` — degré %s (%s)" % (a["exercice"], a["degre"], nom), "",
              "- **Raison** : %s" % a["raison"], "",
              "> %s" % a["texte"], ""]

    io.open(DST, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("ecrit -> %s (%d generiques, %d par exercice)"
          % (os.path.basename(DST), len(doc.get("generiques", [])),
             len(doc.get("par_exercice", []))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
