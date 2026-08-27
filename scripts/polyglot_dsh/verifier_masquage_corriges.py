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

ARGUMENT RETIRE, 27/08. Ce script avancait une correlation inverse : « les
pistes sans corrige sur le disque sont les meilleures, donc pas de fuite ». Elle
etait FAUSSE, et par un defaut de ce script meme : il ne comptait que
.meta/src/reference, qui est une convention JAVA. Compte sans presumer de la
disposition, CINQ pistes sur six portent des corriges -- cpp les range en
.meta/example.h et .meta/example.cpp. cpp est donc a la fois la meilleure piste
ET pourvue de corriges : la correlation n'existe pas. La section 3 compte
desormais juste et ne conclut plus rien.

CE SUR QUOI LA CONCLUSION REPOSE, donc : la section 1 seule -- la trace
contemporaine par exercice -- corroboree par le stash observe en direct,
pilote.py:1509, et auditer_pass.py qui ne trouve qu'une correspondance
solution/corrige (cpp/clock, explicable par le semis du 27/08).

LIMITE. Il n'existe pas de transcription des appels d'outils pour ce run : le
proxy n'y etait pas branche. On montre que le masquage a ete APPLIQUE a chaque
tour ; on n'exhibe pas le journal commande par commande.
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
    print("=== 3. corriges presents sur le disque, par piste (SANS presumer la")
    print("        disposition : java range en .meta/src/reference/, cpp en")
    print("        .meta/example.h, les autres varient) ===")
    print(f"  {'piste':12s} {'fich. corrige':>14s} {'exos':>5s} {'joues':>6s} {'pass':>5s} {'taux':>7s}")
    for piste in sorted(par_piste):
        n, ok = par_piste[piste]
        vierge = os.path.join(RACINE, "polyglot-benchmark", piste,
                              "exercises", "practice")
        fichiers = [f for f in glob.glob(os.path.join(vierge, "*", ".meta", "**", "*"),
                                         recursive=True)
                    if os.path.isfile(f) and not os.path.basename(f).startswith(
                        ("config.json", "tests.toml"))]
        exos = len(glob.glob(os.path.join(vierge, "*", ".meta")))
        print(f"  {piste:12s} {len(fichiers):14d} {exos:5d} {n:6d} {ok:5d} "
              f"{100.0*ok/n:6.1f} %")
    print()
    print("  CE TABLEAU NE CONCLUT RIEN. Il est ici pour interdire l'argument")
    print("  « pas de corrige donc pas de fuite » : cinq pistes sur six en ont,")
    print("  et cpp -- la meilleure -- en fait partie. Seule la section 1 prouve.")


if __name__ == "__main__":
    import sys
    main(*(sys.argv[1:] or []))
