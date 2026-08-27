# -*- coding: utf-8 -*-
"""Repare un exercice laisse MASQUE par un arret dur du pilote.

LE DEFAUT, mesure le 27/08 sur java/bowling. En variante D, le pilote SORT la
suite d'acceptation et `.meta/` de l'exercice pendant que l'agent travaille
(`masquer`), et les remet dans un `finally` (`demasquer`). Un `Stop-Process
-Force` ne deroule pas le `finally` : l'exercice reste ampute de
`.meta/config.json`, et la reprise leve

    FileNotFoundError(2, 'No such file or directory')

Le pilote ecrit alors un enregistrement SANS `turns`, avec `tests_outcomes: []`
et un champ `exception`. Ce n'est pas un echec : c'est un exercice NON JOUE. Un
depouillement naif le compte en echec juge, et fabrique donc un echec.

CE QUE FAIT CE SCRIPT, et rien d'autre :
  * remet les FEUILLES du masque a leur place, via `demasquer` du pilote --
    jamais une copie. Les feuilles et pas les dossiers de tete : `src/` existe
    des deux cotes, et le deplacer en bloc effacerait le code de l'agent ;
  * MET DE COTE l'enregistrement de plantage sous `.plantage-<motif>` -- il
    n'efface rien, l'operateur tranche ;
  * ne rejoue pas l'exercice et ne touche pas au pilote en vol.

USAGE :
    python reparer_exercice_interrompu.py <run> <langue/exercice> [--faire]
Sans --faire, il montre ce qu'il ferait et sort.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilote import demasquer

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    run, cible = sys.argv[1], sys.argv[2].replace("\\", "/")
    faire = "--faire" in sys.argv
    if "/" not in cible:
        print("REFUS : attendu <langue>/<exercice>, recu %r" % cible)
        return 2
    langue, exercice = cible.split("/", 1)

    ex = os.path.join(BENCH, run, langue, "exercises", "practice", exercice)
    stash = os.path.join(BENCH, "_masque", run, langue, exercice)
    if not os.path.isdir(ex):
        print("REFUS : exercice introuvable -> %s" % ex)
        return 2

    # Les feuilles du masque, en chemins relatifs.
    feuilles = []
    for racine, _, fichiers in os.walk(stash):
        for f in fichiers:
            plein = os.path.join(racine, f)
            feuilles.append(os.path.relpath(plein, stash).replace(os.sep, "/"))
    feuilles.sort()

    res = os.path.join(ex, ".dsh.results.json")
    plantage = None
    if os.path.exists(res):
        d = json.load(io.open(res, encoding="utf-8"))
        if d.get("exception") and not d.get("turns"):
            plantage = d["exception"]

    print("exercice : %s" % ex)
    print("masque   : %s" % stash)
    print("")
    if not feuilles:
        print("  rien dans le masque -- l'exercice n'a pas ete laisse ampute.")
    else:
        print("  %d fichier(s) a remettre :" % len(feuilles))
        for rel in feuilles:
            existe = os.path.exists(os.path.join(ex, rel.replace("/", os.sep)))
            print("    %-46s %s" % (rel, "(ECRASERAIT un fichier present)"
                                    if existe else ""))
    print("")
    if plantage:
        print("  enregistrement de PLANTAGE a mettre de cote : %s" % plantage)
    elif os.path.exists(res):
        print("  un verdict REEL est present (il porte des `turns`). "
              "Je n'y touche pas.")
    else:
        print("  aucun verdict present.")

    if not faire:
        print("")
        print("Rien n'a ete fait. Relancer avec --faire pour appliquer.")
        return 0

    if feuilles:
        demasquer(ex, stash, feuilles)
        print("")
        print("  remis en place : %d fichier(s)." % len(feuilles))
    if plantage:
        # DEPLACE, jamais efface : un fichier supprime ne se rediscute pas.
        cote = res + ".plantage"
        n = 1
        while os.path.exists(cote):
            n += 1
            cote = res + ".plantage%d" % n
        os.rename(res, cote)
        print("  enregistrement de plantage mis de cote -> %s"
              % os.path.basename(cote))
        print("")
        print("  %s N'A PLUS DE VERDICT. Le pilote en vol est deja passe "
              "au-dela : il faut le rejouer explicitement, avec" % cible)
        print("      -Exercices %s" % cible)
        print("  a la fin du run, avec les bras de rejeu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
