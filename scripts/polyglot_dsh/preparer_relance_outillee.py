# -*- coding: utf-8 -*-
"""Prepare la relance OUTILLEE : retire les verdicts go rendus sans chaine.

POURQUOI. Les 7 exercices go deja juges l'ont ete alors que l'agent n'avait ni
`go` ni `gofmt` sur son PATH : il ecrivait des tests qu'il ne pouvait pas
executer, puis partait les chercher avec un `find /` (chasses de 366 s et
603 s captees le 27/08). Les garder a cote des 32 autres melangerait deux
protocoles dans une meme colonne -- exactement le defaut nomme en R28k.

Les 26 cpp NE SONT PAS touches : `cmake` etait bien la, ils sont valides.

RIEN N'EST DETRUIT. Tout part au bac a sable, horodate. Le pilote rejouera ces
exercices parce qu'il ne trouvera plus de `.dsh.results.json`, et
`restaurer()` remet les editables a neuf : ce sont de vrais echantillons, pas
des reprises.
"""
import io
import json
import os
import shutil
import sys

RUN = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench", "aider",
                   "tmp.benchmarks", "pi_D_t1_dflash2")
VIERGE = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                      "aider", "tmp.benchmarks", "polyglot-benchmark")
BAC = os.path.join(os.environ["TEMP"], "claude",
                   "C--Users-test-Documents-dsh2-0",
                   "d490488e-4224-4ae1-a2c3-67d03791414b", "scratchpad",
                   "go_sans_chaine")

MAISON = "maison_test.go"


def main():
    appliquer = "--appliquer" in sys.argv
    base = os.path.join(RUN, "go", "exercises", "practice")
    vbase = os.path.join(VIERGE, "go", "exercises", "practice")
    if not os.path.isdir(base):
        print("REFUS : %s introuvable" % base)
        return 2

    aretirer, ecarts = [], []
    for ex in sorted(os.listdir(base)):
        d = os.path.join(base, ex)
        res = os.path.join(d, ".dsh.results.json")
        if not os.path.exists(res):
            continue
        aretirer.append(ex)
        # Les tests OFFICIELS doivent etre intacts : si l'un differe du corpus
        # vierge, on le dit au lieu de le rejouer en silence.
        vd = os.path.join(vbase, ex)
        for f in sorted(os.listdir(vd)) if os.path.isdir(vd) else []:
            if not f.endswith("_test.go"):
                continue
            a, b = os.path.join(vd, f), os.path.join(d, f)
            if os.path.exists(b):
                if io.open(a, "rb").read() != io.open(b, "rb").read():
                    ecarts.append("go/%s/%s" % (ex, f))

    print("exercices go a rejouer : %d" % len(aretirer))
    for ex in aretirer:
        d = os.path.join(base, ex)
        out = json.load(io.open(os.path.join(d, ".dsh.results.json"),
                                encoding="utf-8"))
        ok = any(out.get("tests_outcomes") or [])
        print("  %-22s %-4s %7.1f s   maison : %s"
              % (ex, "PASS" if ok else "FAIL", out.get("duration", 0),
                 "oui" if os.path.exists(os.path.join(d, MAISON)) else "non"))
    print("")
    if ecarts:
        print("ALERTE : test officiel DIFFERENT du corpus vierge :")
        for e in ecarts:
            print("    %s" % e)
    else:
        print("tests officiels : tous identiques au corpus vierge.")
    print("")

    if not appliquer:
        print("SIMULATION. Relancer avec --appliquer pour deplacer.")
        return 0

    os.makedirs(BAC, exist_ok=True)
    n = 0
    for ex in aretirer:
        d = os.path.join(base, ex)
        cible = os.path.join(BAC, ex)
        os.makedirs(cible, exist_ok=True)
        for f in (".dsh.results.json", MAISON):
            src = os.path.join(d, f)
            if os.path.exists(src):
                shutil.move(src, os.path.join(cible, f.lstrip(".")))
                n += 1
    print("%d fichiers deplaces vers %s" % (n, BAC))
    restants = [e for e in sorted(os.listdir(base))
                if os.path.exists(os.path.join(base, e, ".dsh.results.json"))]
    print("verdicts go restants : %d (doit etre 0)" % len(restants))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
