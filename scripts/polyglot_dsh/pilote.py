#!/usr/bin/env python3
"""Pilote dsh sur le corpus polyglot d'Aider -- 225 exercices, 6 langages.

POURQUOI CE FICHIER EXISTE
--------------------------
Le harnais officiel `benchmark/benchmark.py` pilote *aider* : il construit un
objet `Coder` et l'appelle. Il ne sait pas lancer un autre agent. Pour poser
dsh sur le MEME corpus il faut refaire le tour de piste -- et le refaire
FIDELEMENT, sinon les deux chiffres ne se comparent pas.

Ce qui est repris au harnais officiel, au mot et au parametre pres :
  * l'assemblage de la consigne : .docs/introduction.md + .docs/instructions.md
    + .docs/instructions.append.md + `instructions_addendum` (copie mot pour mot
    de benchmark/prompts.py), avec la meme `file_list`;
  * le choix des fichiers editables : `config.files.solution` MOINS les fichiers
    de test, d'exemple, .meta/**, .docs/**, CMakeLists.txt et Cargo.toml;
  * la restauration des fichiers solution depuis l'original AVANT chaque
    exercice (le harnais le fait aussi : sans ca une reprise repartirait du code
    a moitie ecrit d'un run precedent);
  * la copie FRAICHE des fichiers de test depuis l'original avant de juger, et
    le retrait des `@Disabled(...)` en Java -- c'est ce qui empeche l'agent de
    faire passer les tests en les modifiant;
  * les commandes de test par langage et leur delai de 180 s;
  * le message de relance `test_failures`, copie mot pour mot;
  * le nettoyage de la sortie de test (les durees sont gommees, sinon deux runs
    identiques donnent des consignes differentes).

CE QUI DIFFERE, ET QUI DOIT ETRE DECLARE AU RAPPORT
---------------------------------------------------
1. L'HISTORIQUE. aider garde la conversation litterale entre les tours : au
   tour 2 le modele relit ses propres messages. `dsh --profile headless`
   repond a UNE tache puis sort -- il n'a pas de session. Ici la memoire d'un
   tour a l'autre est L'ESPACE DE TRAVAIL : au tour 2 l'agent relit le code
   qu'il a ecrit, plus les erreurs de test. Il ne revoit pas sa propre prose.
   C'est inherent a dsh headless, pas un choix de ce pilote.
2. L'ECHANTILLONNAGE -- MESURE ET CORRIGE LE 26/08.
   Le run aider force temperature 1.0 / top_p 0.95 / top_k 20 / min_p 0 par
   `--read-model-settings`. Mesure au serveur temoin (corps de requete reels,
   pas lecture de code) : NI dsh NI pi n'envoyaient AUCUN de ces quatre champs.
   Les deux heritaient du defaut de l'amont -- inconnu, non journalise, et
   susceptible de changer si OpenRouter bascule d'amont.
   Deux consequences : les deux agents etaient sur un pied d'egalite EXACT
   entre eux (corps identiques au champ pres), mais tous deux decales par
   rapport au bras aider.
   pi sait poser un `samplingParams` ; dsh n'a AUCUNE voie de configuration
   (sa doc amont le confirme : l'echantillonnage arrive par `GenerateOptions`
   a l'appel, et aucun paquet dsh ne le remplit -- une cle inconnue dans
   settings.yaml est jetee SANS message). Regler pi seul aurait casse le pied
   d'egalite. La correction est donc EXTERIEURE aux deux : le proxy
   d'injection (`scripts/bench_julia_effort/proxy.mjs`, PROXY_INJECT), qui
   pose les quatre champs dans chaque requete et journalise ce qui part.
   Voir `cabler_proxy_injection.py`. Verifie : OpenRouter accepte les quatre
   pour qwen/qwen3.8-27b (HTTP 200).
   Un run SANS le proxy reste possible et reste declarable : c'est le bras
   « echantillonnage amont », celui des runs dsh-dev-or / pi-dev-or.
3. LE PROMPT SYSTEME. aider a le sien, dsh a le sien. Aucun des deux n'est
   neutralisable sans denaturer l'agent mesure.

Autrement dit : ce pilote compare DEUX AGENTS sur le meme corpus et le meme
juge, pas deux modeles toutes choses egales.

OU TOURNE QUOI
--------------
dsh tourne sur l'hote Windows ; les chaines de test (pytest, cargo, go, npm,
gradle, cmake) vivent dans l'image `aider-benchmark`. Les deux voient les memes
fichiers parce que `tmp.benchmarks` est monte dans le conteneur. L'agent edite
sur l'hote, le juge s'execute par `docker exec`. Aucune chaine de test n'est a
installer sous Windows.

USAGE
-----
    python pilote.py <nom-du-run> [--tours 2] [--langages python,go]
                     [--limite 5] [--effort medium] [--cont]

Le resultat de chaque exercice est ecrit dans `.dsh.results.json`, avec les
memes cles que `.aider.results.json` (`tests_outcomes`, `duration`, ...) : le
depouillement se fait donc avec les memes outils.
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

# --- l'installation aider, seule source du corpus et des chaines de test ----
AIDER_HOTE = r"C:\Users\test\tools\aider-bench\aider"
BENCH_HOTE = os.path.join(AIDER_HOTE, "tmp.benchmarks")
BENCH_CONT = "/benchmarks"          # meme repertoire, vu du conteneur
ORIGINAL = "polyglot-benchmark"     # le corpus vierge
IMAGE = "aider-benchmark"
CONTENEUR = "dsh-polyglot-tests"    # conteneur dormant, juge uniquement

# --- dsh ---------------------------------------------------------------------
DSH_DEFAUT = os.path.join(os.path.expanduser("~"), ".dsh", "runtime",
                          "dsh-0.1.1-rc.2", "node_modules", ".bin", "dsh.cmd")
# La consigne longue ne passe PAS en argument : le shim cmd.exe coupe un
# argument multi-ligne a la premiere ligne (mesure du 23/08), et un texte
# destine a etre lu passe par un fichier. L'agent lit TASK.md.
CONSIGNE = "Read the file TASK.md in the current directory and do exactly what it says."

# --- copies mot pour mot de benchmark/prompts.py -----------------------------
INSTRUCTIONS_ADDENDUM = """
####

Use the above instructions to modify the supplied files: {file_list}
Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.
Only use standard libraries, don't suggest installing any packages.
"""  # noqa: E501

TEST_FAILURES = """
####

See the testing errors above.
The tests are correct, don't try and change them.
Fix the code in {file_list} to resolve the errors.
"""

# --- copie de benchmark.py::run_unit_tests -----------------------------------
COMMANDES_TEST = {
    ".py": ["pytest"],
    ".rs": ["cargo", "test", "--", "--include-ignored"],
    ".go": ["go", "test", "./..."],
    ".js": ["/aider/benchmark/npm-test.sh"],
    ".cpp": ["/aider/benchmark/cpp-test.sh"],
    ".java": ["./gradlew", "test"],
}
DELAI_TEST = 60 * 3
IGNORES = {"CMakeLists.txt", "Cargo.toml"}


def dire(*a):
    print(*a)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# dsh
# ---------------------------------------------------------------------------
def commande_dsh(dsh):
    """dsh en liste, SANS le shim `dsh.cmd`.

    Le shim transmet `%*` par cmd.exe, qui coupe un argument multi-ligne a la
    premiere ligne (mesure 23/08, tache `coder` : l'agent recevait l'entete
    sans la tache). Meme choix que bench_julia_effort::commande_dsh().
    """
    if dsh.lower().endswith(".cmd"):
        binjs = os.path.normpath(os.path.join(
            os.path.dirname(dsh), "..", "@deepseek-ai", "dsh", "lib", "bin.js"))
        if os.path.exists(binjs):
            return ["node", binjs]
    return [dsh]


def tuer_arbre(p):
    """Tue le processus ET sa descendance.

    `subprocess.run(timeout=)` ne tue que le fils DIRECT ; dsh lance des
    petits-fils (outils, sous-agents) qui survivraient et garderaient le
    modele occupe pendant l'exercice suivant.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True)
    else:
        try:
            p.kill()
        except OSError:
            pass


def lancer_dsh(cmd, ws, env, delai):
    """Lance dsh dans `ws`. Rend (rc, sortie, secondes, coupe_par_le_delai)."""
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=ws, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    coupe = False
    try:
        out, _ = p.communicate(timeout=delai)
    except subprocess.TimeoutExpired:
        coupe = True
        tuer_arbre(p)
        try:
            out, _ = p.communicate(timeout=60)
        except Exception:
            out = ""
    return p.returncode, out or "", time.time() - t0, coupe


# ---------------------------------------------------------------------------
# le juge : dans le conteneur
# ---------------------------------------------------------------------------
def conteneur_pret():
    """Un conteneur DORMANT qui ne sert qu'a executer les tests.

    Il ne lance aucun banc : `sleep infinity`. On y entre par `docker exec`.
    Reutilise s'il tourne deja -- on ne recree pas ce qui existe.
    """
    vu = subprocess.run(["docker", "ps", "-a", "--filter", "name=^%s$" % CONTENEUR,
                         "--format", "{{.Names}}\t{{.State}}"],
                        capture_output=True, text=True).stdout.strip()
    if vu:
        if "running" in vu:
            dire("juge : conteneur %s deja en cours." % CONTENEUR)
            return
        subprocess.run(["docker", "start", CONTENEUR], capture_output=True)
        dire("juge : conteneur %s redemarre." % CONTENEUR)
        return
    r = subprocess.run([
        "docker", "run", "-d", "--name", CONTENEUR,
        "-e", "AIDER_BENCHMARK_DIR=" + BENCH_CONT,
        "-e", "AIDER_DOCKER=1",
        "-v", "%s:/aider" % AIDER_HOTE,
        "-v", "%s:%s" % (BENCH_HOTE, BENCH_CONT),
        "-w", "/aider", IMAGE, "bash", "-c", "sleep infinity",
    ], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("REFUS : le conteneur juge n'a pas demarre.\n" + r.stderr)
    dire("juge : conteneur %s cree." % CONTENEUR)


def chemin_conteneur(chemin_hote):
    """Traduit un chemin de l'hote en chemin vu du conteneur."""
    rel = os.path.relpath(chemin_hote, BENCH_HOTE).replace("\\", "/")
    return BENCH_CONT + "/" + rel


def nettoyer_sortie(sortie, nom_ex):
    """Copie de benchmark.py::cleanup_test_output.

    Les durees sont gommees : sans ca deux executions identiques produisent des
    consignes de relance differentes, et le tour 2 n'est plus reproductible.
    """
    res = re.sub(r"\bin \d+\.\d+s\b", "", sortie)
    return res.replace(nom_ex, os.path.basename(nom_ex))


def lancer_tests(ex_hote, fichiers_test):
    """Execute les tests dans le conteneur. Rend None si tout passe, sinon la
    sortie nettoyee (c'est elle qui repart dans la consigne du tour suivant)."""
    exts = {os.path.splitext(f)[1] for f in fichiers_test}
    cmd = None
    for e in exts:
        if e in COMMANDES_TEST:
            cmd = COMMANDES_TEST[e]
            break
    if not cmd:
        raise ValueError("aucune commande de test pour les extensions %s" % exts)

    wd = chemin_conteneur(ex_hote)
    r = subprocess.run(["docker", "exec", "-w", wd, CONTENEUR] + cmd,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=DELAI_TEST + 60)
    sortie = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return None
    return nettoyer_sortie(sortie, ex_hote)


# ---------------------------------------------------------------------------
# preparation d'un exercice
# ---------------------------------------------------------------------------
def lire_config(ex_hote):
    with io.open(os.path.join(ex_hote, ".meta", "config.json"),
                 encoding="utf-8") as f:
        return json.loads(f.read())


def fichiers_editables(ex_hote, cfg):
    """Les fichiers que l'agent a le droit de modifier.

    Meme regle que le harnais : `solution` moins les tests, les exemples, tout
    .meta/** et .docs/**, plus CMakeLists.txt et Cargo.toml -- ces deux-la sont
    des fichiers de construction, les toucher casse la chaine de test.
    """
    tests = cfg.get("files", {}).get("test", [])
    exemples = cfg.get("files", {}).get("example", [])
    solution = set(cfg.get("files", {}).get("solution", []))
    ignores = set(IGNORES) | set(tests) | set(exemples)
    for sous in (".meta", ".docs"):
        d = os.path.join(ex_hote, sous)
        for cur, _s, fs in os.walk(d):
            for f in fs:
                ignores.add(os.path.relpath(os.path.join(cur, f),
                                            ex_hote).replace("\\", "/"))
    return [f for f in sorted(solution) if f not in ignores]


def restaurer(ex_hote, ex_vierge, fichiers):
    """Remet les fichiers depuis l'original vierge.

    Le harnais officiel le fait aussi. Sans ca, une reprise ferait repartir
    l'agent du code a moitie ecrit d'un run precedent, et le verdict ne
    voudrait rien dire.
    """
    for f in fichiers:
        src = os.path.join(ex_vierge, f.replace("/", os.sep))
        dst = os.path.join(ex_hote, f.replace("/", os.sep))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)


ARTEFACTS = ("build",)


def nettoyer_artefacts(ex_hote, ex_vierge):
    """Efface les arbres de compilation entre l'agent et le juge.

    LE DEFAUT, mesure le 26/08 sur cpp/binary-search-tree. L'agent tourne sur
    l'hote WINDOWS et lance cmake : `build/` se remplit d'un cache MSVC
    (`build/x64/Debug/...`, generateur "Visual Studio"). Le juge tourne dans le
    conteneur LINUX et execute benchmark/cpp-test.sh :

        [ ! -d "build" ] && mkdir build
        cd build
        cmake -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles" ..

    Le script REUTILISE le repertoire existant. CMake y trouve un CMakeCache
    d'un autre generateur et refuse net -- « does not match the generator used
    previously » -- puis `set -e` sort. Resultat : une solution C++ CORRECTE
    est notee FAIL parce que l'agent l'avait compilee avant. Deux des trois
    echecs de la variante C etaient ca.

    La collision joue dans les DEUX SENS : au tour 2, l'agent Windows
    retrouverait le cache Linux laisse par le juge. On nettoie donc aux deux
    passages de temoin, pas seulement avant le juge.

    Meme principe que la recopie des tests d'origine : le juge doit voir un
    depot frais plus les EDITS DE SOURCE de l'agent, jamais ses artefacts.

    Deux garde-fous, parce qu'on efface :
      * un lien symbolique n'est jamais suivi (npm-test.sh fait de
        `node_modules` un lien vers /npm-install : le suivre effacerait
        l'installation npm partagee du conteneur) ;
      * un repertoire qui EXISTE dans le corpus vierge est du source : on
        REFUSE au lieu de detruire. Verifie le 26/08 : zero `build/` sur les
        225 exercices vierges. Le controle reste pour le jour ou ce sera faux.
    """
    efface = []
    for nom in ARTEFACTS:
        chemin = os.path.join(ex_hote, nom)
        if not os.path.isdir(chemin) or os.path.islink(chemin):
            continue
        if os.path.exists(os.path.join(ex_vierge, nom)):
            raise SystemExit(
                "REFUS : `%s` existe dans le corpus vierge (%s) -- c'est du "
                "source, pas un artefact. Effacer ici mutilerait l'exercice."
                % (nom, ex_vierge))
        shutil.rmtree(chemin, ignore_errors=True)
        if not os.path.isdir(chemin):
            efface.append(nom)
    return efface


def poser_tests(ex_hote, ex_vierge, fichiers_test):
    """Recopie les tests depuis l'original AVANT de juger, et retire les
    @Disabled en Java.

    C'est le garde-fou central du corpus : l'agent peut avoir edite les tests,
    ils sont ecrases juste avant le verdict. Un @Disabled laisse en place ferait
    passer un exercice sans que le code marche.
    """
    for f in fichiers_test:
        src = os.path.join(ex_vierge, f.replace("/", os.sep))
        dst = os.path.join(ex_hote, f.replace("/", os.sep))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
        if f.endswith(".java") and os.path.exists(dst):
            t = io.open(dst, encoding="utf-8").read()
            t2 = re.sub(r"@Disabled\([^)]*\)\s*\n", "", t)
            if t2 != t:
                io.open(dst, "w", encoding="utf-8", newline="\n").write(t2)


# --- variante D : l'agent ecrit ses propres tests ---------------------------
# Ou il doit les poser, par langage. Ce n'est pas un detail de confort : c'est
# ce qui rend leur RETRAIT fiable avant le verdict (voir `tests_de_l_agent`).
OU_LES_TESTS = {
    ".py":   "test_maison.py",
    ".go":   "maison_test.go",
    ".rs":   "tests/maison.rs",
    ".js":   "maison.test.js",
    ".cpp":  "maison_test.cpp",
    ".java": "src/test/java/MaisonTest.java",
}

# Motifs que les lanceurs de test ramassent d'eux-memes. Un fichier qui ne
# correspond a aucun ne serait pas collecte par le juge non plus : les deux
# listes suivent la meme convention, volontairement.
MOTIFS_TEST = [
    r"(^|/)test_[^/]*\.py$", r"[^/]*_test\.py$", r"(^|/)conftest\.py$",
    r"[^/]*_test\.go$",
    r"^tests/[^/]*\.rs$", r"[^/]*_test\.rs$",
    r"[^/]*\.(test|spec)\.js$", r"(^|/)maison\.test\.js$",
    r"[^/]*_test\.cpp$", r"[^/]*test[^/]*\.cpp$",
    r"^src/test/",
]

INSTRUCTIONS_TESTS_MAISON = """
####

You do NOT have the acceptance test suite for this exercise. It exists, it is
hidden, and it is what will grade you.

Before writing the solution, write your OWN tests from the instructions above.
Run them. Iterate until they pass. Your tests are your only feedback.

Put your tests in this file and nowhere else: {ou_les_tests}
Do not put tests inside {file_list}: those files are graded, and any failing
test left in them counts against you.
"""


def instantane(ex_hote):
    """Liste des fichiers presents, en chemins relatifs POSIX."""
    vus = set()
    for cur, _d, fs in os.walk(ex_hote):
        for f in fs:
            rel = os.path.relpath(os.path.join(cur, f), ex_hote)
            vus.add(rel.replace("\\", "/"))
    return vus


def tests_de_l_agent(ex_hote, avant, editables):
    """Les fichiers de test que l'agent a crees pendant le tour.

    Pourquoi ce retrait est OBLIGATOIRE en variante D : `pytest` collecte
    `test_*.py`, `go test ./...` balaie recursivement, `cargo test` prend
    `tests/*.rs`. Un test maison qui echoue ferait sortir le juge en code != 0
    et l'exercice serait compte FAIL alors que la VRAIE suite passe. Ce ne sont
    pas de faux succes -- ce sont de faux echecs, et un taux trop bas est aussi
    faux qu'un taux trop haut.

    On ne retire QUE ce qui ressemble a un test. Un module utilitaire cree par
    l'agent et importe par la solution doit rester, sinon on casse le code
    qu'on juge.

    Limite declaree : en Rust, un `#[cfg(test)] mod tests` ecrit DANS src/lib.rs
    est execute par `cargo test` et ne peut pas etre retire sans reecrire le
    fichier juge. La consigne demande explicitement de poser les tests dans
    tests/ ; si l'agent desobeit, l'echec lui est imputable et reste visible.
    """
    apres = instantane(ex_hote)
    edit = {e.replace("\\", "/") for e in editables}
    neufs = [f for f in sorted(apres - avant) if f not in edit]
    return [f for f in neufs if any(re.search(m, f) for m in MOTIFS_TEST)]


def ou_poser_les_tests(editables):
    for e in editables:
        c = OU_LES_TESTS.get(os.path.splitext(e)[1])
        if c:
            return c
    return "test_maison.py"


def masquer(ex_hote, stash_ex, chemins):
    """Sort des chemins de l'espace de travail de l'agent, par DEPLACEMENT.

    Variante B : l'agent ne voit pas le fichier de test. Pourquoi ce n'est pas
    une brimade -- et pourquoi ce n'est pas non plus « comparable a aider » :

      A  banc aider   : ne voit pas le test, ne peut PAS executer  -> le modele
      B  ici          : ne voit pas le test, PEUT executer         -> l'agent
      C  pilote actuel: voit le test,        PEUT executer         -> 92,1 %

    B ne rend pas le chiffre opposable au 52,5 % d'aider : la boucle
    compile/execute reste. B repond a une AUTRE question, et c'est celle qui
    vaut la mesure : l'agent resout-il le probleme, ou s'ajuste-t-il aux
    assertions qu'il a sous les yeux ? L'ecart avec 92,1 % est exactement cette
    part-la.

    DEPLACEMENT et non suppression : le pilote doit pouvoir etre interrompu
    sans que le corpus du run soit ampute. `demasquer` remet tout avant le juge.

    Limite honnete : le stash est ailleurs dans l'arborescence montee, pas dans
    un autre systeme de fichiers. Un agent qui remonterait deliberement les
    repertoires parents pourrait le retrouver. On mesure un agent qui travaille,
    pas un agent qui triche ; si la question se pose un jour, il faudra un
    montage separe.
    """
    poses = []
    for rel in chemins:
        src = os.path.join(ex_hote, rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue
        dst = os.path.join(stash_ex, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
        shutil.move(src, dst)
        poses.append(rel)
    return poses


def demasquer(ex_hote, stash_ex, chemins):
    """Remet ce que `masquer` a sorti. Appele AVANT le juge, et dans un
    `finally` : un tour qui leve ne doit pas laisser l'exercice ampute."""
    for rel in chemins:
        src = os.path.join(stash_ex, rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue
        dst = os.path.join(ex_hote, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
        shutil.move(src, dst)


def chemins_a_masquer(ex_hote, fichiers_test, sans_tests, sans_corriges):
    """Ce qui quitte l'espace de travail, selon les deux drapeaux.

    Deux drapeaux SEPARES, et c'est deliberé : melanger les deux dans un seul
    run rendrait l'ecart avec 92,1 % inattribuable. Un facteur a la fois.

    --sans-corriges est un correctif sans contrepartie (aider ne voit JAMAIS
    .meta/example.* ni .approaches/*/snippet.txt) ; --sans-tests est
    l'experience.
    """
    chemins = []
    if sans_tests:
        chemins.extend(fichiers_test)
    if sans_corriges:
        for d in (".meta", ".approaches"):
            if os.path.isdir(os.path.join(ex_hote, d)):
                chemins.append(d)
    return chemins


def consigne_initiale(ex_hote, editables):
    """Assemblage IDENTIQUE au harnais officiel."""
    txt = ""
    intro = os.path.join(ex_hote, ".docs", "introduction.md")
    if os.path.exists(intro):
        txt += io.open(intro, encoding="utf-8").read()
    txt += io.open(os.path.join(ex_hote, ".docs", "instructions.md"),
                   encoding="utf-8").read()
    app = os.path.join(ex_hote, ".docs", "instructions.append.md")
    if os.path.exists(app):
        txt += io.open(app, encoding="utf-8").read()
    liste = " ".join(os.path.basename(f) for f in editables)
    txt += INSTRUCTIONS_ADDENDUM.format(file_list=liste)
    return txt, liste


# ---------------------------------------------------------------------------
# un exercice, N tours
# ---------------------------------------------------------------------------
def un_exercice(ex_hote, ex_vierge, cmd_dsh, env, tours, delai_tour,
                stash_ex=None, sans_tests=False, sans_corriges=False,
                tests_maison=False):
    cfg = lire_config(ex_hote)
    editables = fichiers_editables(ex_hote, cfg)
    fichiers_test = cfg.get("files", {}).get("test", [])
    if not editables or not fichiers_test:
        return {"tests_outcomes": [], "erreur": "config sans solution ou sans test"}

    restaurer(ex_hote, ex_vierge, editables)
    # La consigne est assemblee AVANT tout masquage : elle lit .docs/**, que
    # l'on ne masque jamais (aider recoit les memes instructions).
    texte, liste = consigne_initiale(ex_hote, editables)
    if tests_maison:
        # VARIANTE D : on AJOUTE une consigne au harnais officiel. C'est un
        # ecart declare, pas une reformulation -- aider ne demande jamais ca.
        texte += INSTRUCTIONS_TESTS_MAISON.format(
            ou_les_tests=ou_poser_les_tests(editables), file_list=liste)
    masques = chemins_a_masquer(ex_hote, fichiers_test, sans_tests, sans_corriges)

    issues, journal = [], []
    t0 = time.time()
    coupes = 0
    nettoyes = []
    for tour in range(1, tours + 1):
        # La consigne du tour passe par un FICHIER, jamais par le shell.
        io.open(os.path.join(ex_hote, "TASK.md"), "w",
                encoding="utf-8", newline="\n").write(texte)
        # Le masquage encadre le SEUL moment ou l'agent regarde le disque.
        # `finally` : un tour qui leve ne doit pas laisser l'exercice ampute,
        # sinon le juge du tour suivant noterait un corpus mutile.
        sortis = masquer(ex_hote, stash_ex, masques) if masques else []
        avant = instantane(ex_hote) if tests_maison else None
        # Passage de temoin JUGE -> AGENT : l'agent Windows ne doit pas
        # heriter du cache cmake Linux laisse par le juge du tour precedent.
        nettoyes += nettoyer_artefacts(ex_hote, ex_vierge)
        try:
            rc, sortie, secondes, coupe = lancer_dsh(
                cmd_dsh + [CONSIGNE],
                ex_hote, env, delai_tour)
        finally:
            if sortis:
                demasquer(ex_hote, stash_ex, sortis)
        if coupe:
            coupes += 1

        # VARIANTE D : les tests ECRITS PAR L'AGENT sortent le temps du verdict,
        # puis reviennent. Ils sortent parce que le juge les ramasserait (pytest
        # collecte test_*.py, `go test ./...` balaie tout) : un test maison qui
        # echoue ferait compter FAIL un exercice dont la VRAIE suite passe.
        # Ils reviennent parce que sans eux le tour 2 repartirait sans le
        # travail du tour 1 -- l'espace de travail EST la memoire de l'agent.
        maison = tests_de_l_agent(ex_hote, avant, editables) if tests_maison else []
        stash_maison = os.path.join(stash_ex, "_maison") if maison else None
        if maison:
            masquer(ex_hote, stash_maison, maison)
        try:
            poser_tests(ex_hote, ex_vierge, fichiers_test)
            # Passage de temoin AGENT -> JUGE : c'est CE nettoyage qui corrige
            # le defaut. cpp-test.sh reutilise `build/` ; s'il porte un cache
            # MSVC, cmake refuse et une solution correcte est notee FAIL.
            nettoyes += nettoyer_artefacts(ex_hote, ex_vierge)
            try:
                erreurs = lancer_tests(ex_hote, fichiers_test)
            except subprocess.TimeoutExpired:
                erreurs = "TIMEOUT: les tests ont depasse %d s." % DELAI_TEST
        finally:
            if maison:
                demasquer(ex_hote, stash_maison, maison)

        issues.append(erreurs is None)
        journal.append({"tour": tour, "ok": erreurs is None, "rc": rc,
                        "secondes": round(secondes, 1), "coupe": coupe,
                        # La QUEUE de la sortie de l'agent est conservee. Sans
                        # elle, le 26/08, six exercices ont rendu FAIL en 1,1 s
                        # sans dire pourquoi : il a fallu relancer dsh a la main
                        # pour lire « MISSING_CREDENTIAL ». Un banc doit porter
                        # sa propre explication.
                        "sortie_queue": (sortie or "")[-600:]})
        if erreurs is None:
            break
        texte = erreurs + TEST_FAILURES.format(file_list=liste)

    return {
        "tests_outcomes": issues,
        "duration": round(time.time() - t0, 1),
        "num_turns": len(issues),
        "turns": journal,
        "tours_coupes": coupes,
        "editables": editables,
        # Combien de fois un arbre de compilation a du etre efface entre
        # l'agent et le juge. Un compte non nul dit que l'exercice AURAIT ete
        # note FAIL sans le correctif du 26/08 -- c'est la mesure de ce que le
        # defaut coutait, et elle doit rester visible dans les donnees.
        "artefacts_effaces": len(nettoyes),
        # La VARIANTE est ecrite dans chaque resultat. Sans ca, deux runs du
        # meme pilote produisent des `.dsh.results.json` indiscernables et on
        # finit par comparer B a C sans le savoir.
        "variante": ("D" if tests_maison else
                     ("C" if not (sans_tests or sans_corriges) else
                      ("B" if sans_tests else "C-sans-corriges"))),
        "sans_tests": bool(sans_tests),
        "sans_corriges": bool(sans_corriges),
        "tests_maison": bool(tests_maison),
        "tests_ecrits_par_l_agent": maison,
    }


# ---------------------------------------------------------------------------
def exercices_du_corpus(vierge, langages=None):
    out = []
    for lang in sorted(os.listdir(vierge)):
        d = os.path.join(vierge, lang, "exercises", "practice")
        if not os.path.isdir(d):
            continue
        if langages and lang not in langages:
            continue
        for ex in sorted(os.listdir(d)):
            if os.path.isdir(os.path.join(d, ex)):
                out.append((lang, ex))
    return out


def preparer_run(run_hote, vierge):
    """Copie les repertoires `practice` -- meme geste que le harnais."""
    if os.path.isdir(run_hote):
        return
    dire("copie du corpus %s -> %s ..." % (ORIGINAL, os.path.basename(run_hote)))
    os.makedirs(run_hote)
    for lang in sorted(os.listdir(vierge)):
        src = os.path.join(vierge, lang, "exercises", "practice")
        if not os.path.isdir(src):
            continue
        dst = os.path.join(run_hote, lang, "exercises", "practice")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst)
    dire("... fait.")


def main():
    # `global` doit preceder TOUT usage du nom dans la fonction --
    # sinon SyntaxError, que `ast.parse` ne voit pas (c'est un
    # controle de table de symboles). Verifier avec py_compile.
    global CONTENEUR
    ap = argparse.ArgumentParser()
    ap.add_argument("nom", help="nom du run (repertoire sous tmp.benchmarks)")
    ap.add_argument("--tours", type=int, default=2,
                    help="2 = comparable au board Aider ; 4 = protocole du 25/08")
    ap.add_argument("--langages", default="",
                    help="liste separee par des virgules ; vide = les 6")
    # Liste EXPLICITE d'exercices, `langage/exercice` separes par des virgules.
    # Elle existe pour rejouer les CAS DURS : un exercice qui a echoue, dont un
    # tour a ete coupe au chronometre, ou qui a demande d'effacer un arbre de
    # compilation. Une fumee sur des exercices faciles passe deja et ne peut
    # rien dementir ; seuls les cas casses testent un changement de protocole.
    # Prioritaire sur --langages / --pas / --decalage / --par-langue : quand on
    # nomme des exercices, on les veut EUX, pas un echantillon qui les contient.
    ap.add_argument("--exercices", default="",
                    help="liste `langage/exercice,...` -- rejoue exactement "
                         "ceux-la, ignore l'echantillonnage.")
    ap.add_argument("--limite", type=int, default=0,
                    help="n'executer que les N premiers (fumee, PAS un taux)")
    ap.add_argument("--pas", type=int, default=0,
                    help="n'executer qu'un exercice sur N, etale sur tout le "
                         "corpus. --limite prend les premiers de chaque langue "
                         "-- alphabetiquement les plus simples -- et donne donc "
                         "un taux flatte. Le pas echantillonne sans ce biais.")
    ap.add_argument("--decalage", type=int, default=0,
                    help="decale le pas : `--pas 6 --decalage 3` prend les "
                         "indices 3, 9, 15... au lieu de 0, 6, 12... C'est le "
                         "SPLIT. Regler un harnais sur des exercices puis "
                         "publier le taux sur ces memes exercices, c'est se "
                         "noter sur sa copie : le decalage donne un lot de "
                         "developpement DISJOINT du lot de test, meme taille, "
                         "meme repartition par langage.")
    ap.add_argument("--conteneur", default=CONTENEUR,
                    help="conteneur juge. Un run pi et un run dsh "
                         "peuvent tourner en meme temps sur des "
                         "conteneurs separes : les caches gradle, "
                         "cargo et npm vivent DANS le conteneur, et "
                         "deux ./gradlew test simultanes partagent "
                         "les verrous de ~/.gradle. RESERVE : les "
                         "durees de deux runs concurrents ne sont "
                         "PAS comparables -- ils se partagent le CPU. "
                         "Le comparatif final se fait en sequentiel.")
    ap.add_argument("--agent", default="dsh", choices=("dsh", "pi"),
                    help="quel harnais joue. Tout le reste du pipeline est "
                         "PARTAGE -- meme consigne, meme masquage, meme juge "
                         "sur tests d'origine, meme boucle de tours. C'est ce "
                         "qui rend la comparaison honnete : un seul facteur "
                         "change.")
    ap.add_argument("--pi", default=os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "npm", "node_modules",
        "@earendil-works", "pi-coding-agent", "dist", "bundle", "cli.js"),
                    help="cli.js de pi. On appelle `node cli.js` et jamais le "
                         "shim pi.cmd, qui couperait la consigne multi-ligne.")
    ap.add_argument("--par-langue", type=int, default=0,
                    help="apres le pas et le decalage, ne garder que les N "
                         "premiers exercices de CHAQUE langage. `--par-langue "
                         "2` donne un lot de 12 qui exerce les six chaines "
                         "d'outils. Sans ca, --limite 12 sur un corpus trie "
                         "par langage ne joue que cpp et go.")
    ap.add_argument("--dotenv", default=None,
                    help="fichier .env charge dans l'environnement avant de "
                         "lancer l'agent (pour OPENROUTER_API_KEY). La valeur "
                         "n'est ni affichee, ni journalisee, ni recopiee.")
    ap.add_argument("--sans-tests", action="store_true",
                    help="VARIANTE B : le fichier de test quitte l'espace de "
                         "travail pendant le tour, et revient pour le juge. "
                         "Repond a « l'agent resout-il, ou s'ajuste-t-il aux "
                         "assertions ? ». Ne rend PAS le chiffre opposable au "
                         "52,5 %% d'aider : la boucle compile/execute reste.")
    ap.add_argument("--sans-corriges", action="store_true",
                    help="masque .meta/** (dont example.*) et .approaches/** "
                         "(solutions commentees). aider ne les voit JAMAIS. "
                         "Correctif sans contrepartie -- mais a activer SEUL "
                         "si l'on veut attribuer l'ecart avec 92,1 %%.")
    ap.add_argument("--tests-maison", action="store_true",
                    help="VARIANTE D : l'agent n'a pas la suite d'acceptation "
                         "et doit ECRIRE ses propres tests depuis la "
                         "specification, puis les faire passer. Implique "
                         "--sans-tests et --sans-corriges. Ses tests sortent "
                         "le temps du verdict (sinon le juge les ramasse et "
                         "produit de FAUX echecs) et reviennent pour le tour "
                         "suivant.")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--accueil",
                    default=os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2"),
                    help="DSH_HOME isole -- JAMAIS ~/.dsh")
    # pi n'a pas d'accueil isole par defaut : il lit ~/.pi/agent. Pour le banc,
    # `models.json` doit pouvoir declarer une route (le proxy d'injection)
    # SANS toucher la configuration personnelle. Absent : pi garde la sienne.
    ap.add_argument("--accueil-pi", default=None,
                    help="PI_CODING_AGENT_DIR isole -- contient le models.json "
                         "du banc. Absent : pi lit ~/.pi/agent.")
    ap.add_argument("--modele", default="specdec-q38-dflash2")
    ap.add_argument("--fournisseur", default="local-think")
    ap.add_argument("--dsh", default=os.environ.get("DSH_BIN", DSH_DEFAUT))
    ap.add_argument("--delai-tour", type=int, default=900)
    args = ap.parse_args()

    vierge = os.path.join(BENCH_HOTE, ORIGINAL)
    if not os.path.isdir(vierge):
        raise SystemExit("REFUS : corpus vierge introuvable : %s" % vierge)

    run_hote = os.path.join(BENCH_HOTE, args.nom)
    preparer_run(run_hote, vierge)
    CONTENEUR = args.conteneur
    conteneur_pret()

    # pi prend son fournisseur et son modele sur la LIGNE DE COMMANDE ; il n'a
    # ni settings.yaml ni accueil isole a proteger. Reecrire la configuration
    # dsh pour un run pi la modifierait sans raison -- et un run dsh lance
    # ensuite repartirait sur le modele du run pi sans que personne ne l'ait
    # demande.
    if args.agent == "dsh":
        # L'accueil dsh est ISOLE : bench.py comme ce pilote reecrivent
        # `agent-default-model` sans le restaurer. Jamais dans ~/.dsh.
        reglages = os.path.join(args.accueil, "settings.yaml")
        if not os.path.exists(reglages):
            raise SystemExit("REFUS : accueil dsh sans settings.yaml : %s"
                             % reglages)
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "bench_julia_effort"))
        from dsh_effort import set_default  # reutilise, pas reecrit
        bloc = set_default(args.fournisseur, args.modele, args.effort, reglages)
    else:
        bloc = ("  agent: pi\n  provider: %s\n  model: %s\n  thinking: %s"
                % (args.fournisseur, args.modele, args.effort))
    dire("accueil dsh : %s" % args.accueil)
    for l in bloc.strip().split("\n"):
        dire("   " + l.strip())

    if args.dotenv:
        n = 0
        for ligne in io.open(args.dotenv, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$",
                         ligne)
            if m:
                # setdefault : une variable deja posee dans l'environnement
                # gagne sur le fichier. On ne remplace jamais en silence une
                # cle que l'operateur a choisie pour cette session.
                os.environ.setdefault(
                    m.group(1), m.group(2).strip().strip('"').strip("'"))
                n += 1
        dire("%d variables chargees depuis %s (valeurs jamais affichees)"
             % (n, args.dotenv))

    env = dict(os.environ)
    env["DSH_HOME"] = args.accueil
    env["DSH_TELEMETRY_DISABLED"] = "1"
    # La route `local-think` DECLARE un `apiKeyEnv` ; dsh refuse de demarrer si
    # la variable n'existe pas -- « MISSING_CREDENTIAL ... DSH_LOCAL_API_KEY,
    # which is not set », mesure du 26/08 04:49, six exercices sortis en 1,1 s
    # avec rc=1 avant qu'on ne trouve la cause.
    # La VALEUR n'a aucune importance : l'amont est notre llama-server en boucle
    # locale, qui n'authentifie rien. C'est un jeton nominal, pas un secret --
    # et surtout pas une raison de copier `~/.dsh/.credentials.yaml` dans
    # l'accueil isole. Meme geste que bench_julia_effort/bench.py.
    env.setdefault("DSH_LOCAL_API_KEY", "local-loopback-noauth")
    # `cmd_dsh` porte desormais la commande COMPLETE de l'agent, consigne
    # exclue : on lui ajoute le texte de la tache et rien d'autre. Les deux
    # agents partagent donc exactement le reste du pipeline -- preparation de
    # l'exercice, masquage, juge sur tests d'origine, boucle de tours. Un seul
    # facteur change entre un run dsh et un run pi.
    if args.agent == "dsh":
        cmd_dsh = commande_dsh(args.dsh) + ["--profile", "headless"]
    else:
        if not os.path.exists(args.pi):
            raise SystemExit("REFUS : cli.js de pi introuvable : %s" % args.pi)
        if args.accueil_pi:
            if not os.path.isdir(args.accueil_pi):
                raise SystemExit("REFUS : accueil pi introuvable : %s"
                                 % args.accueil_pi)
            env["PI_CODING_AGENT_DIR"] = args.accueil_pi
            dire("accueil pi : %s" % args.accueil_pi)
        # `node cli.js` et JAMAIS le shim `pi.cmd` : sur Windows le shim passe
        # par cmd.exe, qui coupe un argument multi-ligne a la premiere ligne.
        # La consigne polyglot est multi-ligne -- l'agent recevrait l'entete
        # sans la tache, et le run rendrait un taux faux sans rien signaler.
        # Meme defaut mesure le 23/08 sur le shim `dsh.cmd`.
        # `--` ferme l'analyse des options : une consigne commencant par un
        # tiret ne doit pas etre lue comme un drapeau.
        cmd_dsh = ["node", args.pi, "-p",
                   "--provider", args.fournisseur,
                   "--model", args.modele,
                   "--thinking", args.effort,
                   "-a", "--no-session", "--"]
    dire("agent : %s" % " ".join(cmd_dsh))

    langages = [x for x in args.langages.split(",") if x] or None
    liste = exercices_du_corpus(vierge, langages)
    if args.exercices:
        # On NOMME les exercices : l'echantillonnage est court-circuite.
        # Un nom absent du corpus ARRETE le run. Le laisser passer donnerait
        # une fumee « 5 sur 5 » alors qu'on en visait 6 -- un cas dur qui
        # disparait sans bruit est exactement ce qu'on essaie d'empecher.
        voulus = [x.strip() for x in args.exercices.split(",") if x.strip()]
        connus = {"%s/%s" % (l, e) for l, e in liste}
        manquants = [v for v in voulus if v not in connus]
        if manquants:
            raise SystemExit("REFUS : exercices introuvables dans le corpus "
                             "(ou hors --langages) : %s" % ", ".join(manquants))
        rang = {v: i for i, v in enumerate(voulus)}
        liste = sorted((p for p in liste if "%s/%s" % p in rang),
                       key=lambda p: rang["%s/%s" % p])
        dire("liste EXPLICITE : %d exercices -- echantillonnage ignore."
             % len(liste))
    elif args.pas:
        if not 0 <= args.decalage < max(1, args.pas):
            raise SystemExit("REFUS : --decalage doit etre dans [0, --pas[ ; "
                             "au-dela il chevauche un autre split.")
        liste = liste[args.decalage::args.pas]
    # `--exercices` est prioritaire : un filtre par langue ou une limite
    # appliques APRES retireraient silencieusement des cas durs nommes.
    if args.par_langue and not args.exercices:
        # Le corpus est trie PAR LANGAGE. `--limite 12` prendrait donc 12
        # exercices de cpp et go, et zero java, rust, python, javascript. Or
        # les defauts de harnais viennent surtout des chaines d'outils
        # (gradle, cmake, cargo, npm) : un lot de mise au point qui n'en
        # exerce que deux ne sert a rien. On prend N par langage.
        par = {}
        garde = []
        for lang, ex in liste:
            if par.get(lang, 0) < args.par_langue:
                par[lang] = par.get(lang, 0) + 1
                garde.append((lang, ex))
        liste = garde
        dire("lot stratifie : %s"
             % ", ".join("%s %d" % (k, v) for k, v in sorted(par.items())))
    if args.limite and not args.exercices:
        liste = liste[:args.limite]
    dire("exercices a jouer : %d   tours : %d   delai/tour : %d s"
         % (len(liste), args.tours, args.delai_tour))
    if args.tests_maison:
        dire("VARIANTE D : l'agent ECRIT ses propres tests.")
        dire("  la suite d'acceptation est masquee ; les tests de l'agent")
        dire("  sortent le temps du verdict et reviennent pour le tour suivant.")
        dire("  ecart declare : une consigne est AJOUTEE au harnais officiel.")
        dire("  limite declaree : en cpp et java, cabler un test maison demande")
        dire("  de toucher CMakeLists.txt / Gradle, qui sont interdits -- D y")
        dire("  est structurellement plus dur. 73 exercices sur 225.")
    elif args.sans_tests or args.sans_corriges:
        quoi = []
        if args.sans_tests:
            quoi.append("le fichier de test")
        if args.sans_corriges:
            quoi.append(".meta/** et .approaches/**")
        dire("VARIANTE %s : masque pendant le tour, remis pour le juge -- %s"
             % ("B" if args.sans_tests else "C-sans-corriges", " + ".join(quoi)))
        dire("  rappel : la boucle compile/execute RESTE. Ce chiffre n'est pas")
        dire("  opposable au 52,4 % d'aider (225/225), qui ecrit a l'aveugle.")
    else:
        dire("VARIANTE C : l'agent voit tout (c'est le protocole du 92,1 %).")
    dire("")

    # PRE-VOL : un agent qui ne demarre pas rend 225 FAIL, et 225 FAIL
    # ressemblent EXACTEMENT a un mauvais modele. Le 26/08, six exercices ont
    # ete rendus FAIL par un `MISSING_CREDENTIAL` -- un run complet aurait
    # produit un « 0 % » publiable et faux. Le banc refuse donc de partir si
    # l'agent ne sait pas repondre a une question triviale.
    dire("pre-vol : l'agent repond-il ?")
    rc, sortie, secondes, coupe = lancer_dsh(
        cmd_dsh + ["Reply with exactly: PREVOL-OK"], run_hote, env, 180)
    if rc != 0 or "PREVOL-OK" not in (sortie or ""):
        dire("  REFUS -- l'agent n'a pas repondu (rc=%s, %.1f s%s)."
             % (rc, secondes, ", coupe par le delai" if coupe else ""))
        for l in (sortie or "").strip().splitlines()[-6:]:
            dire("  | " + l)
        raise SystemExit(
            "Le banc ne part pas : un agent muet rendrait 225 FAIL "
            "indiscernables d'un mauvais modele.")
    dire("  OK en %.1f s." % secondes)
    dire("")

    faits = passes = 0
    t0 = time.time()
    for lang, ex in liste:
        ex_hote = os.path.join(run_hote, lang, "exercises", "practice", ex)
        ex_vierge = os.path.join(vierge, lang, "exercises", "practice", ex)
        res_f = os.path.join(ex_hote, ".dsh.results.json")
        if os.path.exists(res_f):
            continue                      # reprise : deja juge
        try:
            stash_ex = os.path.join(BENCH_HOTE, "_masque", args.nom, lang, ex)
            res = un_exercice(ex_hote, ex_vierge, cmd_dsh, env,
                              args.tours, args.delai_tour,
                              stash_ex=stash_ex,
                              sans_tests=args.sans_tests or args.tests_maison,
                              sans_corriges=args.sans_corriges or args.tests_maison,
                              tests_maison=args.tests_maison)
        except Exception as e:
            res = {"tests_outcomes": [], "exception": repr(e)}
        res.update({"langage": lang, "exercice": ex, "tours_max": args.tours,
                    "effort": args.effort, "modele": args.modele,
                    # Sans ce champ, un run pi et un run dsh sont
                    # indiscernables au depouillement -- et on finit par
                    # comparer un harnais a lui-meme sans le savoir. Meme
                    # raison que le champ "variante".
                    "agent": args.agent, "fournisseur": args.fournisseur})
        io.open(res_f, "w", encoding="utf-8", newline="\n").write(
            json.dumps(res, indent=2))

        faits += 1
        ok = bool(res["tests_outcomes"]) and res["tests_outcomes"][-1]
        passes += 1 if ok else 0
        dire("  %-11s %-32s %-4s  %6.1fs  tours=%s%s"
             % (lang, ex, "PASS" if ok else "FAIL", res.get("duration", 0),
                res.get("num_turns", 0),
                "  " + res["exception"] if "exception" in res else ""))

    d = time.time() - t0
    dire("")
    dire("=== %d joues, %d passes (%.1f %%) en %.1f min ==="
         % (faits, passes, 100.0 * passes / faits if faits else 0.0, d / 60))


if __name__ == "__main__":
    main()
