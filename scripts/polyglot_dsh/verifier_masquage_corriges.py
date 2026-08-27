"""Le masquage des corriges .meta a-t-il VRAIMENT eu lieu, exercice par exercice ?

POURQUOI CE SCRIPT. 46 des 47 exercices java du corpus portent une solution de
reference dans .meta/src/reference/, dans le repertoire meme ou l'agent
travaille -- et pi dispose de read, ls, find et grep. Repondre « pilote.py:1509
pose sans_corriges = args.sans_corriges or args.tests_maison » decrit le
MECANISME ; ce n'est pas une preuve que le masquage s'est produit a chaque tour.

CE QUE CE SCRIPT LIT. Le pilote inscrit `sans_corriges` DANS CHAQUE
enregistrement, au moment du tour. C'est donc une trace contemporaine, par
exercice, et non une reconstitution. Il lit aussi `sortie_queue`, la fin de la
sortie de l'agent, pour y chercher toute mention de .meta, de reference ou de
corrige -- si l'agent avait tente d'aller voir, il en resterait quelque chose.

TROISIEME ELEMENT, indirect mais fort : le taux par piste croise avec la
presence des corriges sur le disque. Une fuite exploitee ferait de java la
meilleure piste ; c'est la pire.
"""

import collections
import glob
import json
import os
import re

RACINE = os.path.join(os.path.expanduser("~"),
                      "tools", "aider-bench", "aider", "tmp.benchmarks")
MOTIF = re.compile(r"\.meta|reference|corrig", re.I)


def verdict(d):
    tours = d.get("turns") or []
    if not tours:
        return None
    ok = tours[-1].get("ok")
    if ok is None:
        o = d.get("tests_outcomes") or []
        ok = bool(o and o[-1])
    return bool(ok)


def main(run="pi_D_t1_dflash2"):
    base = os.path.join(RACINE, run)
    drapeaux = collections.Counter()
    variantes = collections.Counter()
    non_masques = []
    mentions = []
    par_piste = collections.defaultdict(lambda: [0, 0])

    for f in glob.glob(os.path.join(base, "*", "exercises", "practice", "*",
                                    ".dsh.results.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rel = os.path.relpath(f, base).replace(os.sep, "/")
        piste = rel.split("/")[0]
        ex = piste + "/" + rel.split("/")[3]

        sc = d.get("sans_corriges")
        drapeaux[repr(sc)] += 1
        variantes[repr(d.get("variante"))] += 1
        if sc is not True:
            non_masques.append((ex, sc))

        q = (d.get("turns") or [{}])[-1].get("sortie_queue") or ""
        if MOTIF.search(q):
            mentions.append(ex)

        v = verdict(d)
        if v is not None:
            par_piste[piste][0] += 1
            par_piste[piste][1] += int(v)

    print("=== 1. trace contemporaine, inscrite par le pilote a chaque tour ===")
    print("  sans_corriges :", dict(drapeaux))
    print("  variante      :", dict(variantes))
    print("  exercices SANS masquage des corriges :",
          non_masques if non_masques else "AUCUN")
    print()
    print("=== 2. la sortie de l'agent mentionne-t-elle .meta / reference ? ===")
    print(" ", mentions if mentions else "AUCUN exercice")
    print()
    print("=== 3. correlation taux x presence du corrige sur le disque ===")
    print(f"  {'piste':12s} {'corriges .meta':>15s} {'joues':>6s} {'pass':>5s} {'taux':>7s}")
    for piste in sorted(par_piste):
        n, ok = par_piste[piste]
        refs = len(glob.glob(os.path.join(
            RACINE, "polyglot-benchmark", piste,
            "exercises", "practice", "*", ".meta", "src", "reference")))
        print(f"  {piste:12s} {refs:15d} {n:6d} {ok:5d} {100.0*ok/n:6.1f} %")
    print()
    print("  Une fuite exploitee ferait de la piste la MIEUX pourvue en corriges")
    print("  la MEILLEURE. Lire le tableau dans ce sens.")


if __name__ == "__main__":
    import sys
    main(*(sys.argv[1:] or []))
