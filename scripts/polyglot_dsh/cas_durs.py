# Extrait des runs precedents les exercices qui ONT ECHOUE ou dont un tour a
# ete COUPE au chronometre.
#
# POURQUOI. Une fumee sur deux exercices faciles ne dit rien : elle passe deja.
# Les cas qui portent l'information sont ceux qui ont casse -- FAIL, tour
# coupe, artefact de compilation efface. Ce sont eux qu'il faut rejouer quand on
# change le protocole (`--tours 1`, `--delai-tour` releve, echantillonnage
# injecte), parce qu'ils sont les seuls a pouvoir DEMENTIR le changement.
#
# Un tour coupe est une CENSURE : la duree devient une borne inferieure et la
# queue de sortie revient vide. Un exercice coupe qui passe quand meme reste un
# cas dur : il a frole le plafond.

import io
import json
import os
import sys

BENCH = r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"


def lire(run):
    racine = os.path.join(BENCH, run)
    out = []
    for lang in sorted(os.listdir(racine)) if os.path.isdir(racine) else []:
        base = os.path.join(racine, lang, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            f = os.path.join(base, ex, ".dsh.results.json")
            if not os.path.exists(f):
                continue
            try:
                d = json.load(io.open(f, encoding="utf-8"))
            except Exception as e:
                out.append({"langage": lang, "exercice": ex,
                            "illisible": str(e)})
                continue
            d.setdefault("langage", lang)
            d.setdefault("exercice", ex)
            out.append(d)
    return out


def main():
    runs = sys.argv[1:] or ["dsh-dev-or", "pi-dev-or", "fumee-d"]
    durs = {}
    for run in runs:
        res = lire(run)
        if not res:
            print("%-12s : aucun resultat lu" % run)
            continue
        passes = sum(1 for d in res if (d.get("tests_outcomes") or [False])[-1])
        print("== %s : %d exercices, %d passes ==" % (run, len(res), passes))
        for d in res:
            issues = d.get("tests_outcomes") or []
            ok = bool(issues and issues[-1])
            coupes = d.get("tours_coupes") or 0
            art = d.get("artefacts_effaces") or 0
            dur = coupes > 0 or not ok or art > 0
            marque = []
            if not ok:
                marque.append("FAIL")
            if coupes:
                marque.append("coupe x%d" % coupes)
            if art:
                marque.append("artefacts x%d" % art)
            if not dur:
                continue
            cle = "%s/%s" % (d["langage"], d["exercice"])
            durs.setdefault(cle, []).append(run)
            print("   %-38s %6.1fs  tours=%d  %s"
                  % (cle, d.get("duration") or 0, d.get("num_turns") or 0,
                     ", ".join(marque)))
        # La variante est ecrite dans chaque resultat : on la sort pour ne pas
        # comparer deux protocoles sans le savoir.
        vs = sorted({d.get("variante") for d in res})
        print("   variante(s) : %s   tests_maison=%s  sans_tests=%s  "
              "sans_corriges=%s" % (
                  vs, res[0].get("tests_maison"), res[0].get("sans_tests"),
                  res[0].get("sans_corriges")))
        print()

    if durs:
        print("== CAS DURS RETENUS POUR LA FUMEE ==")
        for cle in sorted(durs):
            print("   %-38s vu dans : %s" % (cle, ", ".join(durs[cle])))
        langs = sorted({c.split("/")[0] for c in durs})
        print()
        print("langages concernes : %s" % ",".join(langs))


if __name__ == "__main__":
    main()
