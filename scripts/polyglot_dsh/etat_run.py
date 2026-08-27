# -*- coding: utf-8 -*-
"""Etat d'un run polyglot : verdicts par piste, echecs, populations.

POURQUOI CE FICHIER EXISTE. Le 27/08 j'ai lu le verdict a la RACINE de
`.dsh.results.json` (`d["ok"]`). Ce champ N'EXISTE PAS : il vaut None partout,
et tout exercice est alors compte en echec. La liste « java : 6 FAIL sur 6 »
qui en est sortie etait fausse -- java/book-store est un PASS (`turns[0].ok =
True`, `rc = 0`). Le garde-fou de rejuger.py a crie, et il criait a cause de ma
liste, pas d'une divergence du juge.

Le verdict est dans `turns[-1]["ok"]`, double par `tests_outcomes`. Un seul
lecteur, ici, pour que la faute ne se reproduise pas dans trois scripts.

USAGE :
    python etat_run.py [run]            # tableau par piste + liste des echecs
    python etat_run.py [run] --echecs   # seulement les echecs, une ligne chacun
"""
import glob
import io
import json
import os
import sys

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")
PISTES = ("cpp", "go", "java", "javascript", "python", "rust")

# Les memes motifs que preparer_rejeu_reformule.py : une panne de chaine
# d'outils du JUGE n'est pas un echec de l'agent.
import re
INFRA = re.compile(
    r"toolchain not available"
    r"|go: download go[\d.]+ .*not available"
    r"|could not resolve dependencies"
    r"|Could not (?:download|resolve)"
    r"|network is unreachable", re.I)


def verdict(d):
    """Rend (ok, coupe, erreurs). Source unique de verite pour ce depouillement.

    `ok = None` signale un exercice NON JOUE (le pilote a leve avant le premier
    tour), pas un echec. Voir classer().
    """
    tours = d.get("turns") or []
    if not tours:
        return None, False, ""
    t = tours[-1]
    ok = t.get("ok")
    if ok is None:
        # filet : tests_outcomes porte la meme information sous une autre forme
        outcomes = d.get("tests_outcomes") or []
        ok = bool(outcomes and outcomes[-1])
    return bool(ok), bool(d.get("tours_coupes")), (t.get("erreurs") or "")


def classer(ok, coupe, erreurs, exception=None):
    """QUATRIEME POPULATION : `plantage`.

    Mesure le 27/08 sur java/bowling. Un arret dur du pilote pendant qu'un
    exercice est masque le laisse ampute de `.meta/config.json` ; la reprise
    leve FileNotFoundError et ecrit un enregistrement SANS `turns`, avec
    `tests_outcomes: []`. L'exercice N'A PAS ETE JOUE. Le compter en echec juge
    fabriquerait un echec -- exactement ce que le garde-fou interdit. Il sort
    donc du denominateur, comme les coupures et l'infra, et se rejoue.
    """
    if ok is None and exception:
        return "plantage"
    if ok:
        return "pass"
    if coupe:
        return "coupe"
    if INFRA.search(erreurs):
        return "infra"
    return "juge"


def lire(run):
    out = []
    for lg in PISTES:
        motif = os.path.join(BENCH, run, lg, "exercises", "practice", "*",
                             ".dsh.results.json")
        for f in sorted(glob.glob(motif)):
            d = json.load(io.open(f, encoding="utf-8"))
            ok, coupe, err = verdict(d)
            out.append({
                "piste": lg,
                "exercice": os.path.basename(os.path.dirname(f)),
                "classe": classer(ok, coupe, err, d.get("exception")),
                "duree": d.get("duration") or 0.0,
                # Budget de tours DEMANDE. `tours_demandes` est ecrit par le
                # pilote depuis le 27/08 ; avant cette date on retombe sur le
                # nombre de tours JOUES, qui sous-estime (un run a 2 tours qui
                # converge au premier n'en joue qu'un). La sous-estimation est
                # sans danger ici : elle ne peut que MANQUER un melange, jamais
                # en inventer un.
                "tours": d.get("tours_demandes")
                         or len(d.get("tests_outcomes") or []) or 1,
            })
    return out


def alerte_bras_heterogene(lignes):
    """UN BRAS NE MELANGE PAS DEUX PROTOCOLES.

    `--tours 1` produit un pass_rate_1 ; `--tours 2` produit un pass_rate_2,
    parce que le tour 2 rend a l'agent la sortie d'erreur de la suite
    officielle (pilote.py:1071, ordre operateur du 27/08 07:10 -- c'est la
    DEFINITION de pass_rate_2, pas un defaut). Les deux ne se posent pas a cote
    des memes lignes publiees, donc ils ne se moyennent pas.

    LE CAS QUI A MOTIVE CETTE ALERTE : `pi_D_t1_dflash2` porte 103 exercices a
    1 tour et 5 exercices cpp a 2 tours, residu de l'etape « complement » de
    mesurer_valeur_du_semis.ps1, qui rejoue en `--tours 2` DANS LE MEME
    repertoire de run. Quatre basculent FAIL -> PASS au tour 2. Rien ne le
    signalait : le melange s'est vu a la main, un mois de mesures plus tard.
    """
    par_tours = {}
    for x in lignes:
        par_tours.setdefault(x["tours"], []).append(x)
    if len(par_tours) <= 1:
        return False
    print("!" * 70)
    print("BRAS HETEROGENE -- CE RUN MELANGE DEUX PROTOCOLES. NE PAS MOYENNER.")
    print("!" * 70)
    for t in sorted(par_tours):
        gr = par_tours[t]
        p = sum(1 for x in gr if x["classe"] == "pass")
        taux = "pass_rate_1" if t == 1 else "pass_rate_%d" % t
        print("  %d tour(s) demande(s) -> %s : %3d exercices, %3d pass"
              % (t, taux, len(gr), p))
        if len(gr) <= 8:
            for x in sorted(gr, key=lambda y: (y["piste"], y["exercice"])):
                print("        %-6s %-30s %s" % (x["piste"], x["exercice"],
                                                 x["classe"]))
    print("  A 2 tours l'agent a recu la SORTIE D'ERREUR de la suite")
    print("  officielle : c'est le protocole du board, pas un tour aveugle.")
    print("  Rejouer le groupe minoritaire, ou publier les deux separement.")
    print("!" * 70)
    print("")
    return True


def main():
    run = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
        else "pi_D_t1_dflash2"
    seuls_echecs = "--echecs" in sys.argv
    lignes = lire(run)
    if not lignes:
        print("aucun verdict pour %r" % run)
        return 2

    if not seuls_echecs:
        print("run : %s" % run)
        print("")
        cls = ("pass", "juge", "coupe", "infra", "plantage")
        print("%-12s %6s %6s %6s %6s %6s %9s   %s"
              % ("piste", "rendus", "pass", "juge", "coupe", "infra",
                 "plantage", "taux"))
        print("-" * 76)
        tot = {}
        for lg in PISTES:
            l = [x for x in lignes if x["piste"] == lg]
            if not l:
                continue
            c = {k: sum(1 for x in l if x["classe"] == k) for k in cls}
            for k, v in c.items():
                tot[k] = tot.get(k, 0) + v
            joues = len(l) - c["coupe"] - c["infra"] - c["plantage"]
            taux = ("%.1f %%" % (100.0 * c["pass"] / joues)) if joues else "-"
            print("%-12s %6d %6d %6d %6d %6d %9d   %s"
                  % (lg, len(l), c["pass"], c["juge"], c["coupe"], c["infra"],
                     c["plantage"], taux))
        print("-" * 76)
        joues = (len(lignes) - tot.get("coupe", 0) - tot.get("infra", 0)
                 - tot.get("plantage", 0))
        print("%-12s %6d %6d %6d %6d %6d %9d   %.1f %%"
              % ("TOTAL", len(lignes), tot.get("pass", 0), tot.get("juge", 0),
                 tot.get("coupe", 0), tot.get("infra", 0),
                 tot.get("plantage", 0),
                 100.0 * tot.get("pass", 0) / joues if joues else 0))
        print("")
        print("brut (coupes et infra comptes en echec) : %d / %d = %.1f %%"
              % (tot.get("pass", 0), len(lignes),
                 100.0 * tot.get("pass", 0) / len(lignes)))
        print("")

    alerte_bras_heterogene(lignes)

    print("ECHECS :")
    for x in lignes:
        if x["classe"] != "pass":
            print("  %-8s %-28s %-6s %7.1f s"
                  % (x["piste"], x["exercice"], x["classe"], x["duree"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
