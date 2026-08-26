# ARENE POUR UN AGENT CLAUDE, en variante D stricte.
#
# But : repondre a « et Claude, il mettrait combien de temps ? » avec une
# mesure, pas une impression. Meme exercice, meme consigne, meme masquage,
# meme juge que dsh -- seul l'agent change.
#
# CE QUI EST REPRODUIT A L'IDENTIQUE
#   - le corpus VIERGE (polyglot-benchmark), pas la copie ou dsh a travaille ;
#   - le masquage variante D : la suite officielle
#     src/test/java/BookStoreTest.java PART, et .meta/ (corrige de reference)
#     PART aussi. L'agent ne peut donc ni lire la recette d'acceptation ni
#     copier la solution ;
#   - le TASK.md mot pour mot, repris du run dsh ;
#   - le juge : `./gradlew test` dans un conteneur, sur la suite officielle
#     RESTAUREE apres coup, que l'agent n'aura jamais vue.
#
# CE QUI DIFFERE, ET IL FAUT LE DIRE
#   - conteneur SEPARE (claude-polyglot-tests) : les caches gradle vivent dans
#     le conteneur et deux `./gradlew test` simultanes se disputent les verrous
#     de ~/.gradle. dsh et pi ont deja chacun le leur, pour la meme raison.
#     Consequence honnete : le cache gradle de ce conteneur est FROID au premier
#     appel, la ou celui de dsh etait deja chaud. Le premier `gradlew test`
#     paiera un telechargement de dependances que dsh n'a pas paye.
#   - Claude tourne sur cette machine avec ses propres outils, pas via le
#     harnais dsh. La comparaison porte sur le TEMPS DE BOUT EN BOUT et le
#     verdict, pas sur un nombre d'appels LLM comparable.

import io
import json
import os
import shutil
import subprocess
import sys

AIDER = r"C:\Users\test\tools\aider-bench\aider"
BENCH = os.path.join(AIDER, "tmp.benchmarks")
VIERGE = os.path.join(BENCH, "polyglot-benchmark")
RUN = os.path.join(BENCH, "claude-durs")
IMAGE = "aider-benchmark"
CONTENEUR = "claude-polyglot-tests"
SOURCE_TASK = os.path.join(
    BENCH, "fumee-durs-dsh", "java", "exercises", "practice", "book-store",
    "TASK.md")


def dire(m):
    print(m)
    sys.stdout.flush()


def conteneur_pret():
    vu = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=^%s$" % CONTENEUR,
         "--format", "{{.State}}"], capture_output=True, text=True)
    etat = (vu.stdout or "").strip()
    if etat:
        if etat != "running":
            subprocess.run(["docker", "start", CONTENEUR], capture_output=True)
        dire("juge : conteneur %s pret (%s)." % (CONTENEUR, etat or "demarre"))
        return
    r = subprocess.run([
        "docker", "run", "-d", "--name", CONTENEUR,
        "-e", "AIDER_BENCHMARK_DIR=/benchmarks",
        "-e", "AIDER_DOCKER=1",
        "-v", "%s:/aider" % AIDER,
        "-v", "%s:/benchmarks" % BENCH,
        "-w", "/aider", IMAGE, "bash", "-c", "sleep infinity",
    ], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("REFUS : conteneur non demarre.\n" + r.stderr)
    dire("juge : conteneur %s cree." % CONTENEUR)


def monter(langage, exercice):
    src = os.path.join(VIERGE, langage, "exercises", "practice", exercice)
    if not os.path.isdir(src):
        raise SystemExit("REFUS : exercice vierge introuvable : %s" % src)
    dst = os.path.join(RUN, langage, "exercises", "practice", exercice)
    if os.path.exists(dst):
        raise SystemExit(
            "REFUS : %s existe deja. Le supprimer soi-meme si c'est voulu --\n"
            "  ce script n'efface rien qu'il n'a pas cree dans la seconde." % dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(src, dst)

    cfg = json.load(io.open(os.path.join(dst, ".meta", "config.json"),
                            encoding="utf-8"))
    tests = cfg["files"]["test"]
    solution = cfg["files"]["solution"]

    # --- masquage variante D ------------------------------------------------
    garde = os.path.join(RUN, "_garde", langage, exercice)
    os.makedirs(garde, exist_ok=True)
    partis = []
    for rel in tests:
        p = os.path.join(dst, rel.replace("/", os.sep))
        if os.path.exists(p):
            cible = os.path.join(garde, os.path.basename(p))
            shutil.move(p, cible)
            partis.append(rel)
    meta = os.path.join(dst, ".meta")
    if os.path.isdir(meta):
        shutil.move(meta, os.path.join(garde, "_meta"))
        partis.append(".meta/")
    dire("masque (variante D) : %s" % ", ".join(partis))

    shutil.copy(SOURCE_TASK, os.path.join(dst, "TASK.md"))
    dire("TASK.md copie mot pour mot du run dsh.")

    reste = []
    for r, _, f in os.walk(dst):
        for x in f:
            reste.append(os.path.relpath(os.path.join(r, x), dst))
    dire("")
    dire("l'agent voit exactement :")
    for x in sorted(reste):
        dire("   %s" % x)
    return dst, tests, solution, garde


if __name__ == "__main__":
    conteneur_pret()
    dst, tests, solution, garde = monter("java", "book-store")
    dire("")
    dire("REPERTOIRE DE TRAVAIL (hote)      : %s" % dst)
    dire("REPERTOIRE DE TRAVAIL (conteneur) : /benchmarks/%s"
         % os.path.relpath(dst, BENCH).replace(os.sep, "/"))
    dire("garde (suite officielle + corrige, A NE PAS OUVRIR) : %s" % garde)
