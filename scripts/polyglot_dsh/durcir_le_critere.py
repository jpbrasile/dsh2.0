# -*- coding: utf-8 -*-
"""« Toutes les questions du sous-ensemble sont-elles autonomes ? » -- NON.

Le critere fige (`sous_ensemble_autosuffisant.json`) demande que l'enonce cite
AU MOINS UN identifiant declare par le stub. C'est permissif par construction :
`go/simple-linked-list` cite `Reverse` et passe la barre, alors que l'enonce ne
dit nulle part de quel cote `Push` empile -- il a echoue pour cette raison.

Ce script ne remplace pas la partition figee ; il la SONDE, en durcissant la
barre d'un cran, de facon mecanique :

    combien des identifiants declares par le stub l'enonce cite-t-il ?

Trois seuils sont rendus : au moins un (le critere fige), la moitie, et tous.
L'ecart entre les trois est la mesure de la fragilite du sous-ensemble -- pas
une nouvelle verite, un ordre de grandeur de ce que la barre laisse passer.

RIEN N'EST FIGE ICI. La partition publiee reste celle du 27/08 11:38 ; ce
sondage se lit a cote, et sert a dire quelle confiance lui accorder.
"""
import collections
import io
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
FIGE = os.path.join(ICI, "sous_ensemble_autosuffisant.json")


def importer_critere():
    sys.path.insert(0, ICI)
    vrai = sys.stdout
    sys.stdout = io.StringIO()
    try:
        import contrat_muet
    finally:
        sys.stdout = vrai
    return contrat_muet


def main():
    cm = importer_critere()
    fige = json.load(io.open(FIGE, encoding="utf-8"))
    ambigus = set(fige["ambigus"])

    # On refait le parcours de contrat_muet, mais en gardant le TAUX de
    # citation au lieu du seul booleen.
    par_langue = collections.defaultdict(
        lambda: {"n": 0, "un": 0, "moitie": 0, "tous": 0})
    faibles = []
    for langue, exts in cm.EXT.items():
        base = os.path.join(cm.CORPUS, langue, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            d = os.path.join(base, ex)
            if not os.path.isdir(d):
                continue
            noms = set()
            for racine, dirs, fics in os.walk(d):
                dirs[:] = [x for x in dirs if x not in
                           (".meta", ".docs", ".approaches", "build",
                            "node_modules", "target", ".git")]
                for f in fics:
                    e = os.path.splitext(f)[1]
                    if e not in exts or "test" in f.lower() \
                            or "spec" in f.lower():
                        continue
                    if f.endswith(".stub-origine"):
                        continue
                    src = open(os.path.join(racine, f), encoding="utf-8",
                               errors="ignore").read()
                    for m in cm.DECL[e].findall(src):
                        if m and m not in cm.BRUIT and len(m) > 2:
                            noms.add(m)
            if not noms:
                continue
            txt = cm.enonce(d).lower()
            cites = [n for n in noms if n.lower() in txt]
            part = len(cites) / float(len(noms))
            s = par_langue[langue]
            s["n"] += 1
            if cites:
                s["un"] += 1
            if part >= 0.5:
                s["moitie"] += 1
            if part >= 1.0:
                s["tous"] += 1
            cle = "%s/%s" % (langue, ex)
            if cle not in ambigus and part < 1.0:
                faibles.append((part, cle, len(cites), len(noms),
                                sorted(set(noms) - set(cites))[:4]))

    print("=== COMBIEN D'IDENTIFIANTS DU STUB L'ENONCE CITE-T-IL ? ===")
    print("")
    print("%-12s %6s %10s %10s %10s" % ("langue", "n", "au moins 1",
                                        ">= moitie", "TOUS"))
    tot = collections.Counter()
    for langue in ("cpp", "go", "java", "javascript", "python", "rust"):
        s = par_langue.get(langue)
        if not s:
            continue
        for k in ("n", "un", "moitie", "tous"):
            tot[k] += s[k]
        print("%-12s %6d %10d %10d %10d"
              % (langue, s["n"], s["un"], s["moitie"], s["tous"]))
    print("%-12s %6d %10d %10d %10d"
          % ("TOTAL", tot["n"], tot["un"], tot["moitie"], tot["tous"]))
    print("")
    print("La partition figee retient les %d de la colonne « au moins 1 »."
          % tot["un"])
    print("Si l'on exigeait TOUS les identifiants, il n'en resterait que %d."
          % tot["tous"])
    print("L'ecart -- %d exercices -- est ce que la barre laisse passer."
          % (tot["un"] - tot["tous"]))
    print("")
    print("=== les 20 plus fragiles du sous-ensemble retenu ===")
    print("(identifiants declares mais JAMAIS nommes par l'enonce)")
    for part, cle, nc, nn, manquants in sorted(faibles)[:20]:
        print("  %-34s %d/%d cites   muets : %s"
              % (cle, nc, nn, ", ".join(manquants)))
    print("")
    print("REPONSE : non, le sous-ensemble n'est pas 'autonome sans")
    print("exception'. C'est le meilleur decoupage MECANIQUE dont on dispose,")
    print("fige d'avance et rejouable -- pas un corpus verifie a la main.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
