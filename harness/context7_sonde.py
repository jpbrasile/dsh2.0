# -*- coding: utf-8 -*-
"""Sonde Context7 (MCP HTTP, https://mcp.context7.com/mcp) pour les dependances Julia du
framework : resolve-library-id par paquet, sans cle (le serveur accepte aussi
CONTEXT7_API_KEY dans l'environnement, jamais affichee).

    python harness/context7_sonde.py [Project.toml]      (defaut : le framework)
    python harness/context7_sonde.py --paquets A,B,C

Sortie : une ligne par paquet -- TROUVE <id> (snippets, score) / PARENT <id> / ABSENT / ERREUR -- puis
le bilan et la liste a soumettre sur context7.com/add-library. Mesure, pas opinion :
le README (Phase 2, Context7) demande de sonder puis de soumettre les manquants."""
import argparse, io, json, os, re, sys, time, urllib.request

URL = "https://mcp.context7.com/mcp"
STDLIB = {"Dates", "LinearAlgebra", "Printf", "Random", "SHA", "Statistics", "Test"}  # stdlib Julia : docs.julialang.org
# Paquets couverts par un PARENT indexe (mesure 23/08) : le nom seul ne resout pas, le parapluie oui.
PARENTS = {"OrdinaryDiffEq": "/sciml/differentialequations.jl", "OrdinaryDiffEqBDF": "/sciml/differentialequations.jl",
           "OrdinaryDiffEqFIRK": "/sciml/differentialequations.jl", "OrdinaryDiffEqRosenbrock": "/sciml/differentialequations.jl",
           "OrdinaryDiffEqSDIRK": "/sciml/differentialequations.jl", "CairoMakie": "/makieorg/makie.jl"}
# Faux positifs connus : l'id nomme un autre projet (XGBoost C++/Python, pas XGBoost.jl).
FAUX = {"XGBoost": ("/dmlc/xgboost", "/websites/xgboost_readthedocs_io_en")}
FRAMEWORK = os.path.join(os.path.expanduser("~"), "Documents", "agentic-flow-fresh", "plasma-digital-twin", "Project.toml")


def appel(methode, params, ident=1):
    corps = json.dumps({"jsonrpc": "2.0", "id": ident, "method": methode, "params": params}).encode("utf-8")
    h = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    k = os.environ.get("CONTEXT7_API_KEY")
    if k:
        h["CONTEXT7_API_KEY"] = k
    req = urllib.request.Request(URL, data=corps, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        texte = r.read().decode("utf-8", "replace")
    for l in texte.splitlines():
        if l.startswith("data:"):
            return json.loads(l[5:])
    return json.loads(texte)


def resoudre(paquet):
    nom = paquet if paquet.endswith(".jl") else paquet + ".jl"
    d = appel("tools/call", {"name": "resolve-library-id", "arguments": {"libraryName": nom, "query": "Julia %s usage" % paquet}})
    if "error" in d:
        return "ERREUR", d["error"].get("message", "?")[:80], 0, 0
    texte = "".join(c.get("text", "") for c in d["result"].get("content", []))
    # entrees : Title / Context7-compatible library ID / Code Snippets / Benchmark Score
    blocs = [b for b in texte.split("----------") if "library ID:" in b]
    cible = paquet.lower()
    for b in blocs:
        titre = re.search(r"Title:\s*(.+)", b)
        lid = re.search(r"library ID:\s*(\S+)", b)
        snip = re.search(r"Code Snippets:\s*(\d+)", b)
        score = re.search(r"Benchmark Score:\s*([\d.]+)", b)
        t = (titre.group(1).strip() if titre else "").lower()
        i = (lid.group(1) if lid else "").lower()
        # correspondance : le titre ou l'id nomme le paquet (pas un homonyme : "json" != "json3")
        if lid and lid.group(1) in FAUX.get(paquet, ()):
            continue
        if re.search(r"(^|[^a-z0-9])%s(\.jl)?([^a-z0-9]|$)" % re.escape(cible), t) or re.search(r"/%s(\.jl|_jl)?$" % re.escape(cible), i):
            return "TROUVE", lid.group(1), int(snip.group(1)) if snip else 0, float(score.group(1)) if score else 0.0
    if paquet in PARENTS:
        return "PARENT", PARENTS[paquet], 0, 0
    return "ABSENT", "%d resultat(s) hors sujet" % len(blocs), 0, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projet", nargs="?", default=FRAMEWORK)
    ap.add_argument("--paquets", default=None)
    A = ap.parse_args()
    if A.paquets:
        paquets = [p for p in A.paquets.split(",") if p]
    else:
        t = io.open(A.projet, encoding="utf-8").read()
        m = re.search(r"(?ms)^\[deps\]\n(.*?)(?=^\[|\Z)", t)
        paquets = [l.split("=")[0].strip() for l in m.group(1).splitlines() if "=" in l]
    t0 = time.time()
    trouves, absents, erreurs = [], [], []
    for p in paquets:
        if p in STDLIB:
            print("%-24s STDLIB   docs.julialang.org" % p)
            continue
        try:
            etat, info, snip, score = resoudre(p)
        except Exception as e:  # noqa: BLE001
            etat, info, snip, score = "ERREUR", str(e)[:80], 0, 0
        if etat == "TROUVE":
            trouves.append(p)
            print("%-24s TROUVE   %s  (%d snippets, score %.0f)" % (p, info, snip, score))
        elif etat == "PARENT":
            trouves.append(p)
            print("%-24s PARENT   %s  (couvert par le parapluie)" % (p, info))
        elif etat == "ABSENT":
            absents.append(p)
            print("%-24s ABSENT   %s" % (p, info))
        else:
            erreurs.append(p)
            print("%-24s ERREUR   %s" % (p, info))
    n = len([p for p in paquets if p not in STDLIB])
    print("bilan : %d paquets sondes en %.0f s -- %d trouves, %d absents, %d erreurs (+%d stdlib)" % (
        n, time.time() - t0, len(trouves), len(absents), len(erreurs), len([p for p in paquets if p in STDLIB])))
    if absents:
        print("a soumettre sur https://context7.com/add-library :", ", ".join(absents))
    return 0 if not erreurs else 1


if __name__ == "__main__":
    sys.exit(main())
