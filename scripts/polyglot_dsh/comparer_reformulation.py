# -*- coding: utf-8 -*-
"""Les DEUX metriques, cote a cote : sans reformulation, avec.

Ne compare que les exercices REELLEMENT joues des deux cotes. Un exercice
present d'un seul cote est signale, jamais complete par un defaut -- c'est
comme ca qu'on fabrique un taux qui n'a jamais ete mesure.

Le sens de lecture, et il n'est pas symetrique :
  FAIL -> PASS   l'ambiguite de l'enonce expliquait l'echec ;
  FAIL -> FAIL   elle ne l'expliquait pas, l'echec est de fond ;
  PASS -> FAIL   la reformulation a NUIT -- a regarder de pres, un ajout mal
                 tourne peut detourner l'agent d'une solution qu'il avait.

USAGE : python comparer_reformulation.py <run-sans> <run-avec>
"""
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preparer_rejeu_reformule import verdicts


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    sans_nom, avec_nom = sys.argv[1], sys.argv[2]
    sans, avec = verdicts(sans_nom), verdicts(avec_nom)

    # Le run « avec » DOIT porter la trace de ce qu'il a recu, sinon on ne sait
    # pas ce qu'on compare.
    degres = collections.Counter()
    for d in avec.values():
        for r in d["reformulations"]:
            degres[r["degre"]] += 1
    if not degres:
        print("REFUS : %s ne porte aucune reformulation. Ce n'est pas la "
              "colonne « avec » -- soit le run est parti sans --degres, soit "
              "ce n'est pas le bon nom." % avec_nom)
        return 2

    communs = sorted(set(sans) & set(avec))
    seul_sans = sorted(set(sans) - set(avec))
    seul_avec = sorted(set(avec) - set(sans))

    print("sans reformulation : %s   (%d verdicts)" % (sans_nom, len(sans)))
    print("avec reformulation : %s   (%d verdicts, ajouts par degre : %s)"
          % (avec_nom, len(avec),
             ", ".join("%s=%d" % kv for kv in sorted(degres.items()))))
    print("compares           : %d exercice(s) joues des DEUX cotes" % len(communs))
    if seul_avec:
        print("  joues seulement AVEC : %d (ignores)" % len(seul_avec))
    if seul_sans:
        print("  joues seulement SANS : %d (ignores)" % len(seul_sans))
    print("")

    bascules = collections.Counter()
    lignes = []
    for k in communs:
        a, b = sans[k]["ok"], avec[k]["ok"]
        cle = ("%s -> %s" % ("PASS" if a else "FAIL", "PASS" if b else "FAIL"))
        bascules[cle] += 1
        if a != b:
            lignes.append((cle, k, sans[k]["duree"], avec[k]["duree"]))

    for cle in ("FAIL -> PASS", "PASS -> FAIL", "FAIL -> FAIL", "PASS -> PASS"):
        if bascules[cle]:
            print("  %-14s %d" % (cle, bascules[cle]))
    print("")
    if lignes:
        print("=== ce qui a bascule ===")
        for cle, k, ds, da in sorted(lignes):
            print("  %-14s %-34s %7.1f s -> %7.1f s" % (cle, k, ds, da))
        print("")

    n = len(communs)
    ps = sum(1 for k in communs if sans[k]["ok"])
    pa = sum(1 for k in communs if avec[k]["ok"])
    print("taux sur les %d compares :  sans %d/%d = %.1f %%   avec %d/%d = %.1f %%"
          % (n, ps, n, 100.0 * ps / n, pa, n, 100.0 * pa / n))
    print("ecart : %+.1f point(s) -- c'est le COUT DE L'AMBIGUITE des enonces,"
          % (100.0 * (pa - ps) / n))
    print("pas une performance de l'agent. Colonne a etiqueter : un run")
    print("reformule ne se compare ni a la variante D pure, ni au banc aider.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
