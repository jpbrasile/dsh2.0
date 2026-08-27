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
                    "reformulations": d.get("reformulations", [])}
    return out


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
    echecs = sorted(k for k, d in v.items() if not d["ok"])
    print("run de reference : %s" % run)
    print("  verdicts   : %d / %d%s" % (len(v), total,
                                        "" if fini else "  -- NON TERMINE"))
    print("  echecs     : %d" % len(echecs))
    for k in echecs:
        print("      %-34s %7.1f s" % (k, v[k]["duree"]))
    print("")

    if not fini and not partiel:
        print("REFUS : le run de reference n'est pas termine (%d / %d). "
              "Rejouer maintenant comparerait une colonne complete a une "
              "colonne partielle. Attendre, ou assumer avec --partiel."
              % (len(v), total))
        return 1
    if not echecs:
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
    }
    chemin = os.path.join(ICI, "rejeu_%s.json" % run)
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, ensure_ascii=False, indent=2))
    print("ecrit -> %s" % os.path.basename(chemin))
    print("")
    print("Pour lancer le rejeu, une fois le run de reference ARRETE :")
    print("")
    print("  .\\lancer_polyglot_complet.ps1 -Nom %s_reformB `" % run)
    print("      -Modele specdec-q38-dflash2 -Tours 1 `")
    print("      -Degres B -Exercices (Get-Content rejeu_%s.json |" % run)
    print("          ConvertFrom-Json).exercices")
    print("")
    print("Puis comparer avec comparer_reformulation.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
