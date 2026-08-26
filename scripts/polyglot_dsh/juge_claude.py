# LE JUGE : verdict variante D sur l'agent Claude.
#
# On restaure la suite officielle -- que l'agent n'a jamais vue -- et on
# l'execute. On RETIRE d'abord les tests maison de l'agent : la note porte sur
# la suite cachee, pas sur les tests qu'il s'est ecrits. Un test maison qui
# echoue ne doit pas faire echouer le verdict, et un test maison qui passe ne
# doit rien accorder.
#
# ORDRE IMPORTANT : on mesure d'abord AVEC les tests maison retires et la suite
# officielle en place. C'est exactement ce que fait pilote.py pour dsh et pi.

import io
import json
import os
import re
import shutil
import subprocess
import sys

AIDER = r"C:\Users\test\tools\aider-bench\aider"
BENCH = os.path.join(AIDER, "tmp.benchmarks")
RUN = os.path.join(BENCH, "claude-durs")
CONTENEUR = "claude-polyglot-tests"
EX = os.path.join(RUN, "java", "exercises", "practice", "book-store")
GARDE = os.path.join(RUN, "_garde", "java", "book-store")
SUITE_REL = os.path.join("src", "test", "java", "BookStoreTest.java")
MAISON_REL = os.path.join("src", "test", "java", "MaisonTest.java")


def dire(m):
    print(m)
    sys.stdout.flush()


def dans_conteneur(chemin_hote):
    return "/benchmarks/" + os.path.relpath(chemin_hote, BENCH).replace(os.sep, "/")


def gradlew():
    r = subprocess.run(
        ["docker", "exec", "-w", dans_conteneur(EX), CONTENEUR,
         "./gradlew", "test", "--console=plain"],
        capture_output=True, text=True, timeout=3600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


if __name__ == "__main__":
    if not os.path.isdir(EX):
        raise SystemExit("REFUS : arene absente. Lancer arene_claude.py.")

    # 1. ecarter les tests maison de l'agent (on les garde, on ne les perd pas)
    maison = os.path.join(EX, MAISON_REL)
    ecarte = None
    if os.path.exists(maison):
        ecarte = os.path.join(GARDE, "MaisonTest.java.rendu")
        shutil.move(maison, ecarte)
        dire("tests maison de l'agent ecartes (conserves : %s)" % ecarte)
    else:
        dire("ATTENTION : aucun src/test/java/MaisonTest.java -- l'agent n'a "
             "pas ecrit de tests maison. A signaler tel quel.")

    # 2. restaurer la suite officielle
    src = os.path.join(GARDE, "BookStoreTest.java")
    if not os.path.exists(src):
        raise SystemExit("REFUS : suite officielle introuvable dans la garde.")
    dst = os.path.join(EX, SUITE_REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)

    # RETIRER LES @Disabled -- meme geste que pilote.py:377, et il n'est pas
    # cosmetique. Les suites Java d'Exercism desactivent tout sauf le premier
    # test : sans ce retrait, gradle rend BUILD SUCCESSFUL sur 1 test execute
    # et 17 SAUTES. C'est exactement ce que mon juge a fait a son premier essai
    # le 26/08 -- un PASS qui ne mesurait rien. Le compte est verifie plus bas.
    t = io.open(dst, encoding="utf-8").read()
    t2 = re.sub(r"@Disabled\([^)]*\)\s*\n", "", t)
    if t2 != t:
        io.open(dst, "w", encoding="utf-8", newline="\n").write(t2)
        dire("@Disabled retires : %d" % (t.count("@Disabled") - t2.count("@Disabled")))
    dire("suite officielle restauree : %s" % SUITE_REL)

    # 3. juger
    dire("")
    dire("=== ./gradlew test (suite OFFICIELLE) ===")
    rc, sortie = gradlew()
    for ligne in sortie.splitlines():
        if any(m in ligne for m in ("PASSED", "FAILED", "BUILD ", "tests completed",
                                    "> Task :test", "error:", "warning:")):
            dire("  " + ligne)
    # LE COMPTE, PAS LE CODE DE RETOUR. `BUILD SUCCESSFUL` est vrai aussi quand
    # tous les tests sont sautes. On lit le XML JUnit et on REFUSE de conclure
    # si un seul test a ete saute, ou si le nombre execute ne correspond pas au
    # nombre de @Test de la suite officielle.
    import glob
    import re as _re
    xml = glob.glob(os.path.join(EX, "build", "test-results", "test",
                                 "TEST-*.xml"))
    total = saute = echec = erreur = 0
    for f in xml:
        t = io.open(f, encoding="utf-8", errors="replace").read()
        m = _re.search(r'tests="(\d+)"\s+skipped="(\d+)"\s+failures="(\d+)"'
                       r'\s+errors="(\d+)"', t)
        if m:
            total += int(m.group(1)); saute += int(m.group(2))
            echec += int(m.group(3)); erreur += int(m.group(4))
    attendu = io.open(src, encoding="utf-8").read().count("@Test")
    dire("")
    dire("comptes JUnit : %d tests, %d sautes, %d echecs, %d erreurs "
         "(@Test dans la suite : %d)" % (total, saute, echec, erreur, attendu))

    if not xml:
        dire("VERDICT : INDETERMINE -- aucun rapport JUnit ecrit.")
        rc = 5
    elif saute:
        dire("VERDICT : INVALIDE -- %d tests SAUTES. Un BUILD SUCCESSFUL sur "
             "des tests sautes ne mesure rien." % saute)
        rc = 6
    elif total != attendu:
        dire("VERDICT : INVALIDE -- %d tests executes pour %d @Test attendus."
             % (total, attendu))
        rc = 7
    else:
        dire("VERDICT : %s (rc=%d, %d/%d tests reellement executes)"
             % ("PASS" if rc == 0 else "FAIL", rc, total - echec - erreur, total))

    journal = os.path.join(RUN, "verdict_claude.json")
    io.open(journal, "w", encoding="utf-8").write(json.dumps({
        "exercice": "java/book-store", "variante": "D",
        "tests_maison_ecrits": ecarte is not None,
        "rc": rc, "verdict": "PASS" if rc == 0 else "FAIL",
        "sortie_queue": sortie[-4000:],
    }, indent=2, ensure_ascii=False))
    dire("journal : %s" % journal)
