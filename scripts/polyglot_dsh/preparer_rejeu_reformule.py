# -*- coding: utf-8 -*-
"""Prepare le REJEU AVEC ENONCE REFORMULE d'un run termine.

CE QUE CA MESURE. Deux metriques sur LES MEMES exercices : sans reformulation
(le run de reference, variante D pure) et avec (degre B par defaut -- une mise
en garde generique qui ne cite aucun exercice et ne dit pas de quel cote tombe
l'ambiguite). L'ecart entre les deux est le COUT DE L'AMBIGUITE DES ENONCES.

CE QUE CA NE MESURE PAS, et il faut le dire a la publication : un run reformule
n'est pas comparable au banc aider, dont le modele ne recoit ni outils ni
consigne ajoutee. C'est une colonne a part, etiquetee.

POURQUOI UN RUN SEPARE. Le rejeu ecrit dans SON PROPRE repertoire. Le run de
reference n'est ni relu ni touche : sans ca, on ecraserait la moitie « sans
reformulation » de la comparaison qu'on cherche a produire.

GARDE-FOU. Par defaut le script REFUSE de preparer un rejeu tant que le run de
reference n'est pas termine -- un echec encore en vol serait rejoue contre un
verdict qui n'existe pas. `--partiel` leve le refus et l'ECRIT dans le fichier
produit, pour que personne ne publie un partiel en croyant tenir un total.

USAGE :
    python preparer_rejeu_reformule.py pi_D_t1_dflash2 [--total 225] [--partiel]
"""
import glob
import io
import json
import os
import re
import sys

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")
ICI = os.path.dirname(os.path.abspath(__file__))


def verdicts(run):
    racine = os.path.join(BENCH, run)
    out = {}
    for f in sorted(glob.glob(os.path.join(racine, "*", "exercises",
                                           "practice", "*",
                                           ".dsh.results.json"))):
        cle = os.path.relpath(os.path.dirname(f), racine).replace(os.sep, "/")
        cle = cle.replace("/exercises/practice", "")
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        out[cle] = {"ok": bool(any(d.get("tests_outcomes") or [])),
                    "duree": d.get("duration", 0.0),
                    # Un tour coupe (silence trop long) n'a pas produit un
                    # verdict sur l'ENONCE : l'agent n'avait pas fini. Le champ
                    # est expose ici pour que chaque depouilleur decide s'il
                    # doit l'ecarter -- le rejeu, lui, le rejoue comme les
                    # autres, c'est justement une chance de le finir.
                    "coupe": bool(d.get("tours_coupes")),
                    # La sortie du juge du DERNIER tour. Elle vit dans
                    # turns[].erreurs, pas a la racine du fichier.
                    "erreurs": ((d.get("turns") or [{}])[-1].get("erreurs")
                                or ""),
                    "reformulations": d.get("reformulations", [])}
    return out


# Un echec d'INFRASTRUCTURE n'est pas un echec de solution : la chaine du juge
# n'a pas pu construire. Motifs OBSERVES, jamais devines -- chacun a ete lu
# dans un .dsh.results.json de ce run.
#   go/palindrome-products 27/08 : l'agent a reecrit go.mod en « go 1.24 », le
#   conteneur porte go1.21.5 et n'a pas de reseau. Le juge n'a jamais compile
#   la solution. Compter ce FAIL contre le modele attribue au modele une
#   panne de banc.
INFRA = re.compile(
    r"toolchain not available"
    r"|go: download go[\d.]+ .*not available"
    r"|could not resolve dependencies"
    r"|Could not (?:download|resolve)"
    r"|network is unreachable", re.I)


def classer(d):
    """coupe | infra | juge -- dans cet ordre, et l'ordre compte.

    Une coupure d'abord : l'agent n'avait pas rendu, ce qui suit ne le juge
    pas. Puis l'infra. Ce qui reste est un vrai verdict sur la solution.
    """
    if d["coupe"]:
        return "coupe"
    if INFRA.search(d["erreurs"]):
        return "infra"
    return "juge"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = sys.argv[1]
    total = 225
    if "--total" in sys.argv:
        total = int(sys.argv[sys.argv.index("--total") + 1])
    partiel = "--partiel" in sys.argv

    v = verdicts(run)
    if not v:
        print("REFUS : aucun verdict dans %s" % run)
        return 2

    # Un run de reference DEJA reformule ne peut pas servir de « sans ».
    deja = [k for k, d in v.items() if d["reformulations"]]
    if deja:
        print("REFUS : %d exercice(s) du run de reference portent deja une "
              "reformulation. Ce run ne peut pas tenir la colonne « sans »."
              % len(deja))
        for k in deja[:5]:
            print("    %s" % k)
        return 2

    fini = len(v) >= total
    # DEUX POPULATIONS, ET ELLES NE SE REJOUENT PAS PAREIL.
    #   juges   l'agent a rendu, le juge a dit non -> le rejeu degre B teste si
    #           l'ambiguite de l'enonce expliquait le non.
    #   coupes  la laisse de silence a arrete l'agent avant qu'il rende ; le
    #           fichier porte encore le stub. Les mettre dans le bras « avec
    #           reformulation » ferait passer des timeouts pour du cout
    #           d'ambiguite : une coupure qui passe au rejeu passe parce
    #           qu'elle a eu le temps, pas parce que l'enonce etait plus clair.
    par = {"juge": [], "coupe": [], "infra": []}
    for k in sorted(v):
        if not v[k]["ok"]:
            par[classer(v[k])].append(k)
    echecs, coupes, infra = par["juge"], par["coupe"], par["infra"]
    print("run de reference : %s" % run)
    print("  verdicts   : %d / %d%s" % (len(v), total,
                                        "" if fini else "  -- NON TERMINE"))
    for titre, lot, note in (
            ("echecs juges", echecs, "degre B"),
            ("tours coupes", coupes, "bras SEPARE, D pur"),
            ("pannes d'infra", infra, "bras SEPARE, D pur -- pas un echec "
                                      "de solution")):
        print("  %-14s : %d  (%s)" % (titre, len(lot), note))
        for k in lot:
            print("      %-34s %7.1f s" % (k, v[k]["duree"]))
    print("")

    if not fini and not partiel:
        print("REFUS : le run de reference n'est pas termine (%d / %d). "
              "Rejouer maintenant comparerait une colonne complete a une "
              "colonne partielle. Attendre, ou assumer avec --partiel."
              % (len(v), total))
        return 1
    if not echecs and not coupes and not infra:
        print("Rien a rejouer : aucun echec.")
        return 0

    doc = {
        "reference": run,
        "verdicts_reference": len(v),
        "total_attendu": total,
        "reference_terminee": fini,
        "partiel_assume": bool(partiel and not fini),
        "echecs": echecs,
        "exercices": ",".join(echecs),
        "coupes": coupes,
        "exercices_coupes": ",".join(coupes),
        "infra": infra,
        "exercices_infra": ",".join(infra),
    }
    chemin = os.path.join(ICI, "rejeu_%s.json" % run)
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, ensure_ascii=False, indent=2))
    print("ecrit -> %s" % os.path.basename(chemin))
    print("")
    print("Pour lancer le rejeu, une fois le run de reference ARRETE.")
    print("")
    if echecs:
        print("  BRAS 1 -- les %d echecs JUGES, avec reformulation degre B :" % len(echecs))
        print("")
        print("  .\\lancer_polyglot_complet.ps1 -Nom %s_reformB `" % run)
        print("      -Modele specdec-q38-dflash2 -Tours 1 `")
        print("      -Degres B -Exercices (Get-Content rejeu_%s.json |" % run)
        print("          ConvertFrom-Json).exercices")
        print("")
    if coupes:
        print("  BRAS 2 -- les %d tours COUPES, D PUR, SANS -Degres :" % len(coupes))
        print("")
        print("  .\\lancer_polyglot_complet.ps1 -Nom %s_coupes `" % run)
        print("      -Modele specdec-q38-dflash2 -Tours 1 `")
        print("      -Exercices (Get-Content rejeu_%s.json |" % run)
        print("          ConvertFrom-Json).exercices_coupes")
        print("")
        print("  Ce bras-la ne mesure PAS l'ambiguite : il mesure ce que la")
        print("  laisse de silence a coute. Son resultat s'ajoute au taux D,")
        print("  il n'entre jamais dans la colonne « avec reformulation ».")
        print("")
    if infra:
        print("  BRAS 3 -- les %d pannes d'INFRA, D PUR, SANS -Degres :" % len(infra))
        print("")
        print("  .\\lancer_polyglot_complet.ps1 -Nom %s_infra `" % run)
        print("      -Modele specdec-q38-dflash2 -Tours 1 `")
        print("      -Exercices (Get-Content rejeu_%s.json |" % run)
        print("          ConvertFrom-Json).exercices_infra")
        print("")
        print("  La chaine du juge n'a pas pu construire ; la solution n'a")
        print("  jamais ete evaluee. Le rejeu part d'un repertoire neuf, donc")
        print("  d'un echafaudage vierge. Si l'agent le casse a nouveau, c'est")
        print("  reproductible et ca devient un defaut du BANC, pas du modele.")
        print("")
    print("Puis comparer avec comparer_reformulation.py -- qui ne doit voir")
    print("que le BRAS 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
