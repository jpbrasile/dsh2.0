# -*- coding: utf-8 -*-
"""Carte statique « fichier source -> fichiers de test » du framework Julia.

    python carte.py [--repo DIR] [--json SORTIE] [--inverse FICHIER_SRC ...]

Lecture seule. Pour chaque fichier de test (test/**/*.jl) on suit :
  - include("...") transitifs (chemins relatifs au fichier qui inclut) ;
  - `using/import PlasmaDigitalTwin.X` -> les fichiers atteints par le
    sous-module X dans le graphe d include du paquet (src/PlasmaDigitalTwin.jl) ;
  - `using/import PlasmaDigitalTwin` nu -> tout le paquet, marque « large ».
La carte inverse donne, pour un fichier source, les tests « precis » (qui
l atteignent par include ou sous-module) et « larges » (paquet entier).
Les fichiers source qu aucun test n atteint sont listes : la porte doit
les traiter comme NON COUVERTS, jamais comme verts.

Limites connues (a garder en tete pour l equipe rouge) :
  - include(joinpath(@__DIR__, "a", "b.jl")) est reconnu pour les formes
    courantes ; un chemin construit dynamiquement ne l est pas ;
  - `push!(LOAD_PATH, ...)` + `using Foo` d un module hors paquet n est
    pas suivi (liste « using inconnus » en sortie pour les reperer).
"""
import io
import json
import os
import re
import sys

REPO_DEFAUT = r"C:\Users\test\Documents\agentic-flow-fresh\plasma-digital-twin"
PAQUET = "PlasmaDigitalTwin"

RE_INCLUDE = re.compile(r'^\s*include\(\s*(?:joinpath\(\s*@__DIR__\s*,\s*)?((?:"[^"]*"\s*,?\s*)+)\)?\s*\)', re.M)
RE_USING_PAQUET = re.compile(r'^\s*(?:using|import)\s+' + PAQUET + r'(?:\.([A-Za-z_][A-Za-z0-9_]*))?(?:\s*:|\s*,|\s*$|\s+#)', re.M)
RE_USING_LOCAL = re.compile(r'^\s*(?:using|import)\s+\.([A-Za-z_][A-Za-z0-9_]*)', re.M)
RE_MODULE = re.compile(r'^\s*module\s+([A-Za-z_][A-Za-z0-9_]*)', re.M)


def _norm(p):
    return os.path.normpath(p).replace("\\", "/")


def _lire(p):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


RE_DOSSIER_VAR = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*joinpath\(\s*@__DIR__\s*,((?:\s*"[^"]+"\s*,?)+)\)')
RE_INCLUDE_BOUCLE = re.compile(r'include\(\s*joinpath\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*[A-Za-z_][A-Za-z0-9_]*\s*\)\s*\)')
RE_INCLUDE_VAR = re.compile(r'include\(\s*joinpath\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,((?:\s*"[^"]+"\s*,?)+)\)\s*\)')


def includes_de(fichier, texte=None):
    """Chemins inclus par `fichier` (absolus, normalises), dans l ordre.
    Reconnait aussi la boucle `d = joinpath(@__DIR__, "x")` ... `include(joinpath(d, f))`
    -> tous les .jl du dossier x (auto-decouverte, cf. NodeContract.jl)."""
    texte = _lire(fichier) if texte is None else texte
    base = os.path.dirname(fichier)
    out = []
    for m in RE_INCLUDE.finditer(texte):
        morceaux = re.findall(r'"([^"]*)"', m.group(1))
        if not morceaux:
            continue
        p = os.path.join(base, *morceaux)
        out.append(_norm(p))
    dossiers = {v: os.path.join(base, *re.findall(r'"([^"]+)"', parts)) for v, parts in RE_DOSSIER_VAR.findall(texte)}
    # include(joinpath(VAR, "src", "X.jl")) avec VAR = joinpath(@__DIR__, ...) : chemin litteral
    for var, parts in RE_INCLUDE_VAR.findall(texte):
        if var in dossiers:
            out.append(_norm(os.path.join(dossiers[var], *re.findall(r'"([^"]+)"', parts))))
    for var in RE_INCLUDE_BOUCLE.findall(texte):
        if var in dossiers:
            d = dossiers[var]
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    if f.endswith(".jl"):
                        out.append(_norm(os.path.join(d, f)))
    return out


def fermeture_includes(fichier, cache):
    """Ensemble transitif des fichiers inclus depuis `fichier` (lui exclu)."""
    vus = set()
    pile = [fichier]
    while pile:
        f = pile.pop()
        if f not in cache:
            cache[f] = includes_de(f) if os.path.isfile(f) else []
        for g in cache[f]:
            if g not in vus:
                vus.add(g)
                pile.append(g)
    return vus


def graphe_paquet(repo, cache):
    """Sous-module -> fichiers atteints (module defini dans src/<x>/X.jl)."""
    racine = _norm(os.path.join(repo, "src", PAQUET + ".jl"))
    texte = _lire(racine)
    sousmod = {}
    tout = set([racine])
    for inc in includes_de(racine, texte):
        noms = RE_MODULE.findall(_lire(inc))
        atteints = set([inc]) | fermeture_includes(inc, cache)
        tout |= atteints
        for n in noms[:1]:  # le module de tete du fichier
            sousmod[n] = atteints
    return racine, sousmod, tout


def est_test(t):
    """Unite rejouable : test_*.jl ou runtests.jl. Les debug_/diagnose_/validate_/
    benchmarks/helpers qui vivent sous test/ sont des scripts, jamais des cibles."""
    n = os.path.basename(t)
    return n == "runtests.jl" or n.startswith("test_")


EXCLUS = {".git", "node_modules", "artifacts", "data", "docs", "test", "tests"}


def sources_de(repo):
    """Tous les .jl sous un dossier `src/` du framework : src/ a la racine et
    les sous-projets (chemistry_mvp/src/, ...). Hors .git, artefacts, tests."""
    out = []
    for d, sous, fs in os.walk(repo):
        sous[:] = [x for x in sous if x not in EXCLUS and not x.startswith(".")]
        if "/src/" in _norm(d) + "/":
            for f in fs:
                if f.endswith(".jl"):
                    out.append(_norm(os.path.join(d, f)))
    return out


def est_source(repo, f):
    return "/src/" in f and f.startswith(_norm(repo) + "/")


def construire(repo):
    repo = _norm(repo)
    cache = {}
    racine, sousmod, paquet_tout = graphe_paquet(repo, cache)
    tests = []
    for d, _, fs in os.walk(os.path.join(repo, "test")):
        for f in fs:
            if f.endswith(".jl"):
                tests.append(_norm(os.path.join(d, f)))
    tests.sort()
    carte = {}
    using_inconnus = {}
    scripts = [t for t in tests if not est_test(t)]
    for t in tests:
        texte = _lire(t)
        precis = set()
        large = False
        # includes transitifs : on ne garde que ce qui tombe sous src/
        for g in fermeture_includes(t, cache):
            if "/src/" in g:
                precis.add(g)
        for m in RE_USING_PAQUET.finditer(texte):
            x = m.group(1)
            if x is None:
                large = True
            elif x in sousmod:
                precis |= sousmod[x]
            else:
                using_inconnus.setdefault(t, []).append(PAQUET + "." + x)
        # `using .Foo` apres un include : deja couvert par l include lui-meme
        carte[t] = {"precis": sorted(precis), "large": large, "script": not est_test(t),
                    "inclus": sorted(g for g in fermeture_includes(t, cache) if g in set(tests))}
    # Un fichier de test inclus par un autre (runtests.jl du dossier) et qui ne
    # charge rien lui-meme n est pas autonome : son unite de rejeu est l includeur.
    includeur = {}
    for t in tests:
        for g in cache.get(t, []):
            if g in carte and not carte[g]["precis"] and not carte[g]["large"]:
                includeur.setdefault(g, t)
    for g, t in includeur.items():
        carte[g]["unite"] = t
    src = sorted(sources_de(repo))
    inverse = {s: {"precis": [], "large": []} for s in src}
    for t, v in carte.items():
        if v["script"]:
            continue
        for s in v["precis"]:
            if s in inverse:
                inverse[s]["precis"].append(t)
        if v["large"]:
            for s in paquet_tout:
                if s in inverse:
                    inverse[s]["large"].append(t)
    non_autonomes = sorted(t for t, v in carte.items() if not v["precis"] and not v["large"] and "unite" not in v)
    non_couverts = [s for s, v in inverse.items() if not v["precis"] and not v["large"]]
    seulement_large = [s for s, v in inverse.items() if not v["precis"] and v["large"]]
    return {
        "repo": repo,
        "paquet_racine": racine,
        "sous_modules": {k: len(v) for k, v in sousmod.items()},
        "n_tests": len(tests), "n_src": len(src),
        "tests": carte, "inverse": inverse,
        "non_couverts": non_couverts,
        "seulement_large": seulement_large,
        "non_autonomes": non_autonomes,
        "scripts": scripts,
        "using_inconnus": using_inconnus,
    }


def tests_pour(carte, fichiers):
    """Pour des fichiers modifies : (tests precis ranges du plus cible au plus
    large, tests « paquet entier », fichiers non couverts).
    Un test non autonome est remplace par son unite (le runtests qui l inclut).
    Un fichier de test modifie est lui-meme a rejouer."""
    precis, large, non = {}, set(), []
    inv = carte["inverse"]
    T = carte["tests"]

    def unite(t):
        return T[t].get("unite", t)

    for f in fichiers:
        f = _norm(os.path.abspath(f))
        if f in T:
            u = unite(f)
            precis[u] = min(precis.get(u, 10 ** 9), 0)
            continue
        if f not in inv:
            non.append(f)  # hors src/ et hors test/ : on ne sait pas -> non couvert
            continue
        v = inv[f]
        if v["precis"]:
            for t in v["precis"]:
                u = unite(t)
                poids = len(T[u]["precis"])  # peu de sources atteintes = test cible
                precis[u] = min(precis.get(u, 10 ** 9), poids)
        elif v["large"]:
            large |= set(unite(t) for t in v["large"])
        else:
            non.append(f)
    ranges = sorted(precis, key=lambda t: (precis[t], t))
    # un candidat inclus (transitivement) par un autre candidat est deja couvert par lui
    couverts = set()
    for t in ranges:
        couverts |= set(T[t].get("inclus", []))
    ranges = [t for t in ranges if t not in couverts]
    large = set(t for t in large if t not in couverts and t not in ranges)
    return ranges, sorted(large), non


def main(argv):
    repo = REPO_DEFAUT
    sortie = None
    inverse = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo":
            repo = argv[i + 1]; i += 2
        elif a == "--json":
            sortie = argv[i + 1]; i += 2
        elif a == "--inverse":
            inverse = argv[i + 1:]; break
        else:
            print("argument inconnu :", a); return 2
        i += 0 if a in ("--repo", "--json") else 1
    c = construire(repo)
    if sortie:
        io.open(sortie, "w", encoding="utf-8").write(json.dumps(c, indent=1, ensure_ascii=False))
    n_precis = sum(1 for v in c["inverse"].values() if v["precis"])
    print("repo : %s" % c["repo"])
    print("tests : %d fichiers ; src : %d fichiers ; sous-modules du paquet : %d"
          % (c["n_tests"], c["n_src"], len(c["sous_modules"])))
    print("src atteints precisement : %d ; seulement par le paquet entier : %d ; non couverts : %d"
          % (n_precis, len(c["seulement_large"]), len(c["non_couverts"])))
    n_unite = sum(1 for v in c["tests"].values() if "unite" in v)
    print("tests non autonomes rattaches a leur runtests : %d ; ni autonomes ni rattaches : %d"
          % (n_unite, len(c["non_autonomes"])))
    if c["using_inconnus"]:
        print("using inconnus (%d tests) :" % len(c["using_inconnus"]))
        for t, u in list(c["using_inconnus"].items())[:10]:
            print("  %s : %s" % (os.path.relpath(t, c["repo"]), ", ".join(u)))
    if inverse:
        p, l, n = tests_pour(c, inverse)
        print("tests precis (%d) :" % len(p))
        for t in p:
            print("  " + os.path.relpath(t, c["repo"]))
        print("tests larges (%d) :" % len(l))
        for t in l[:10]:
            print("  " + os.path.relpath(t, c["repo"]))
        if n:
            print("NON COUVERTS (%d) :" % len(n))
            for f in n:
                print("  " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
