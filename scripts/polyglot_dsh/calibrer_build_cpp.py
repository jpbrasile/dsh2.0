# -*- coding: utf-8 -*-
"""Preuve du defaut C++ et de son correctif. Docker seulement, aucun GPU.

Trois controles sur un exercice temoin, dont la solution posee est le CORRIGE
de reference -- donc il DOIT passer. Ce qui varie n'est jamais le code, c'est
uniquement l'etat de `build/` :

  1. TEMOIN      : build/ absent  -> le juge doit PASSER.
                   Si ce controle echoue, le banc lui-meme est casse et les
                   deux suivants ne veulent rien dire.
  2. DEFAUT      : build/ porte un CMakeCache d'un autre generateur, comme
                   apres une compilation de l'agent sur l'hote Windows
                   -> le juge doit ECHOUER. C'est la reproduction du defaut :
                   une solution correcte notee FAIL.
  3. CORRECTIF   : meme etat qu'en 2, puis nettoyer_artefacts()
                   -> le juge doit PASSER a nouveau.

Le controle 2 est celui qui compte : sans lui, on ne saurait pas si le
correctif repare quelque chose ou s'il ne fait rien.

Sort en code 2 des qu'un des trois ne rend pas le verdict attendu.
"""
import io
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilote  # noqa: E402

TEMOIN = ("cpp", "all-your-base")
BAC = "calibrage-build-cpp"

# Un CMakeCache minimal mais suffisant : CMake compare CMAKE_GENERATOR a celui
# demande et refuse si les deux different. C'est exactement ce que laisse une
# compilation MSVC sur l'hote.
CACHE_WINDOWS = """# This is the CMakeCache file.
CMAKE_GENERATOR:INTERNAL=Visual Studio 17 2022
CMAKE_GENERATOR_PLATFORM:INTERNAL=x64
CMAKE_HOME_DIRECTORY:INTERNAL=C:/Users/test/exercise
"""


def juger(ex_hote, fichiers_test):
    """Rend (passe, sortie_courte)."""
    try:
        erreurs = pilote.lancer_tests(ex_hote, fichiers_test)
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:200])
    if erreurs is None:
        return True, ""
    return False, " | ".join(
        l.strip() for l in erreurs.split("\n") if l.strip())[:300]


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    lang, ex = TEMOIN
    vierge = os.path.join(pilote.BENCH_HOTE, pilote.ORIGINAL)
    src = os.path.join(vierge, lang, "exercises", "practice", ex)
    if not os.path.isdir(src):
        raise SystemExit("REFUS : temoin introuvable : %s" % src)

    bac = os.path.join(pilote.BENCH_HOTE, BAC, lang, "exercises", "practice", ex)
    if os.path.isdir(os.path.join(pilote.BENCH_HOTE, BAC)):
        shutil.rmtree(os.path.join(pilote.BENCH_HOTE, BAC), ignore_errors=True)
    os.makedirs(os.path.dirname(bac), exist_ok=True)
    shutil.copytree(src, bac)
    print("temoin : %s/%s   bac : %s" % (lang, ex, bac))

    import json
    cfg = json.loads(io.open(os.path.join(bac, ".meta", "config.json"),
                             encoding="utf-8").read())["files"]
    solutions, exemples = cfg.get("solution", []), cfg.get("example", [])
    fichiers_test = cfg.get("test", [])
    print("solution %s   exemple %s   test %s"
          % (solutions, exemples, fichiers_test))

    # On POSE LE CORRIGE : a partir d'ici, tout echec du juge vient de
    # l'environnement et non du code.
    for cible, exm in zip(solutions, exemples):
        shutil.copyfile(os.path.join(bac, exm), os.path.join(bac, cible))
    print("corrige de reference pose -> le juge DOIT passer.")
    print("")

    pilote.conteneur_pret()
    echecs = []

    # --- 1. temoin ------------------------------------------------------
    ok, sortie = juger(bac, fichiers_test)
    print("1. TEMOIN    build/ absent            -> %s"
          % ("PASSE" if ok else "ECHOUE"))
    if not ok:
        print("     %s" % sortie)
        echecs.append("1. le temoin n'a pas passe : le banc est casse, les "
                      "controles 2 et 3 ne veulent rien dire.")

    # --- 2. le defaut ---------------------------------------------------
    b = os.path.join(bac, "build")
    shutil.rmtree(b, ignore_errors=True)
    os.makedirs(b)
    io.open(os.path.join(b, "CMakeCache.txt"), "w",
            encoding="utf-8", newline="\n").write(CACHE_WINDOWS)
    ok2, sortie2 = juger(bac, fichiers_test)
    print("2. DEFAUT    build/ = cache MSVC      -> %s"
          % ("PASSE" if ok2 else "ECHOUE"))
    print("     %s" % (sortie2[:220] if sortie2 else "(aucune sortie)"))
    if ok2:
        echecs.append("2. le defaut NE SE REPRODUIT PAS : le juge passe malgre "
                      "un cache etranger. Le correctif ne corrigerait alors "
                      "rien de demontre -- ne pas le presenter comme tel.")

    # --- 3. le correctif ------------------------------------------------
    efface = pilote.nettoyer_artefacts(bac, src)
    print("   nettoyer_artefacts a efface : %s" % (efface or "rien"))
    ok3, sortie3 = juger(bac, fichiers_test)
    print("3. CORRECTIF nettoyage puis juge      -> %s"
          % ("PASSE" if ok3 else "ECHOUE"))
    if not ok3:
        print("     %s" % sortie3)
        echecs.append("3. le correctif ne restaure pas le PASS.")

    print("")
    if echecs:
        print("CALIBRAGE ECHOUE :")
        for e in echecs:
            print("   %s" % e)
        print("bac CONSERVE pour inspection : %s" % bac)
        raise SystemExit(2)
    shutil.rmtree(os.path.join(pilote.BENCH_HOTE, BAC), ignore_errors=True)
    print("CALIBRAGE OK -- le defaut se reproduit, le correctif le repare.")


if __name__ == "__main__":
    main()
