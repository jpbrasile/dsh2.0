# -*- coding: utf-8 -*-
"""Ce que la queue ENREGISTREE du juge dit d'un echec -- sans rejouer le juge.

Le pilote ne garde que 3 000 caracteres de la sortie du juge (`turns[].erreurs`).
Pour go, python et une partie de java, cette queue porte deja l'assertion : il
est alors inutile de rejouer le juge, donc inutile de toucher au conteneur qui
sert le pilote en vol. Quand elle ne porte que « N tests completed, M failed »,
c'est le signal qu'il faut rejuger.py.

USAGE :
    python queue_juge.py <run> <langue/exercice> [...]
"""
import io
import json
import os
import sys

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")

INTERESSANT = ("FAILED", "PASSED", "expected", "but was", "Expecting",
               "tests completed", "error:", "AssertionError", "want ",
               "got ", "panic:", "assert")


def une(run, cible):
    langue, exercice = cible.replace("\\", "/").split("/", 1)
    f = os.path.join(BENCH, run, langue, "exercises", "practice", exercice,
                     ".dsh.results.json")
    print("=" * 72)
    print(cible)
    print("=" * 72)
    if not os.path.exists(f):
        print("  aucun verdict.")
        return
    d = json.load(io.open(f, encoding="utf-8"))
    t = (d.get("turns") or [{}])[-1]
    e = t.get("erreurs") or ""
    print("  ok=%s  coupe=%s  duree=%.1f s  queue=%d car."
          % (t.get("ok"), bool(d.get("tours_coupes")), d.get("duration") or 0,
             len(e)))
    lignes = [l.rstrip() for l in e.splitlines()
              if any(m in l for m in INTERESSANT)]
    if not lignes:
        print("  RIEN d'exploitable dans la queue -> rejuger.py")
        return
    echoues = [l for l in lignes if "FAILED" in l or "expected" in l
               or "but was" in l or "Expecting" in l]
    print("  %d ligne(s) utiles, dont %d sur l'echec :"
          % (len(lignes), len(echoues)))
    for l in lignes:
        print("     " + l.strip()[:112])


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    run = sys.argv[1]
    for cible in sys.argv[2:]:
        une(run, cible)
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
