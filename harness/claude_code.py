#!/usr/bin/env python
"""claude_code.py -- Phase 2 : le worker `claude-code` (README) = `claude -p` enveloppe.

    python harness/claude_code.py --tache-fichier T.txt [--cwd DIR] [--allowed "Read,Glob,Grep"]
                                  [--max-turns 6] [--max-budget-usd 0.50] [--model sonnet]
                                  [--campagne NOM] [--sortie resultat.json] [--delai 600]
    python harness/claude_code.py --reingerer harness/_cout/claude_code_X.json --campagne NOM

Ce que le script garantit, et rien d'autre :
  - la tache passe par un fichier (jamais un argument shell a retours a la ligne) ;
  - l'appel est borne : --max-turns, --max-budget-usd, --allowedTools (tout outil hors liste
    est REFUSE par claude en mode -p : il n'y a personne pour dire oui), delai mur (l'arbre
    est tue au-dela) ;
  - la sortie JSON brute de claude est ECRITE SUR DISQUE avant toute analyse, puis analysee
    (rc 3 si elle ne l'est pas) ; `is_error`, `num_turns`, `stop_reason`, `permission_denials`,
    `total_cost_usd` sont imprimes tels quels ;
  - le cout est porte au grand livre (harness/cout.py) en une ligne par modele facture
    (`modelUsage`), campagne `claude-code:<nom>`, AVANT tout affichage et MEME quand l'appel
    est en erreur ou coupe : une depense non mesuree n'existe pas dans ce harnais.
    `--reingerer` reporte au livre un JSON brut deja sauve (run dont l'analyse a plante).
Ce que le script ne garantit pas : l'authentification (ANTHROPIC_API_KEY si presente, sinon
le compte connecte -- `total_cost_usd` est alors un cout notionnel, pas une facture) et
l'isolation OS (claude -p ecrit la ou --allowedTools le permet ; le mur OS est pour plus tard).

Codes de retour : 0 ok ; 1 claude en erreur (is_error / rc != 0 / coupe au delai) ;
2 refus d'outil enregistre (permission_denials non vide) avec resultat non-erreur ;
3 sortie JSON inanalysable ; 4 claude introuvable.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

# stdout cp1252 sous Windows : un '->' unicode dans la reponse de claude a fait planter le
# script AVANT l'ecriture du livre (bras RT 23/08, deux fois : 0,15 + 0,16 USD non comptes
# sur le coup). Livre d'abord, affichage tolerant ensuite.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import cout  # noqa: E402


def lignes_cout(d, t0, ms, campagne):
    """Une ligne de grand livre par modele facture (modelUsage), au format du recorder."""
    out = []
    mu = d.get("modelUsage") or {}
    if not mu:  # pas de detail : une ligne globale
        u = d.get("usage") or {}
        mu = {"claude-code:?": {"inputTokens": u.get("input_tokens"), "outputTokens": u.get("output_tokens"),
                                "cacheReadInputTokens": u.get("cache_read_input_tokens"),
                                "costUSD": d.get("total_cost_usd")}}
    for modele, u in mu.items():
        out.append({"kind": "call", "t0": t0, "ms": ms, "servi": modele,
                    "status": 200 if not d.get("is_error") else 500,
                    "usage": {"prompt_tokens": (u.get("inputTokens") or 0) + (u.get("cacheReadInputTokens") or 0)
                              + (u.get("cacheCreationInputTokens") or 0),
                              "completion_tokens": u.get("outputTokens"),
                              "prompt_tokens_details": {"cached_tokens": u.get("cacheReadInputTokens")},
                              "cost": u.get("costUSD")}})
    return out


def porter_au_livre(d, t0_ms, ms, campagne, sortie, livre):
    if livre:
        cout.LIVRE = livre
    f = sortie + ".appel.jsonl"
    with io.open(f, "w", encoding="utf-8") as fh:
        for l in lignes_cout(d, t0_ms, ms, campagne):
            fh.write(json.dumps(l, ensure_ascii=False) + "\n")
    n, total, ign = cout.ingerer(f, "claude-code:" + campagne)
    print("grand livre : +%d ligne(s) (%d au total)%s" % (n, total, "  ignore : " + "; ".join(ign) if ign else ""))
    return n


def afficher(d):
    print("is_error=%s  num_turns=%s  stop_reason=%s  subtype=%s  cout=%s USD  api_ms=%s"
          % (d.get("is_error"), d.get("num_turns"), d.get("stop_reason"), d.get("subtype"), d.get("total_cost_usd"), d.get("duration_api_ms")))
    for m, u in (d.get("modelUsage") or {}).items():
        print("  modele %-28s in=%s cache_lu=%s cache_cree=%s out=%s cout=%s"
              % (m, u.get("inputTokens"), u.get("cacheReadInputTokens"), u.get("cacheCreationInputTokens"), u.get("outputTokens"), u.get("costUSD")))
    refus = d.get("permission_denials") or []
    for r in refus:
        print("  REFUS outil %s : %s" % (r.get("tool_name"), json.dumps(r.get("tool_input"), ensure_ascii=False)[:120]))
    res = d.get("result")
    print("resultat (%d car.) : %s" % (len(res or ""), (res or "").strip().replace("\n", " ")[:200]))
    return refus


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tache-fichier", default=None)
    ap.add_argument("--reingerer", default=None, help="JSON brut d'un run precedent a porter au livre (pas d'appel)")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--allowed", default="Read,Glob,Grep", help="liste --allowedTools (virgules)")
    ap.add_argument("--max-turns", type=int, default=6)
    ap.add_argument("--max-budget-usd", type=float, default=0.50)
    ap.add_argument("--model", default=None)
    ap.add_argument("--campagne", default="smoke")
    ap.add_argument("--sortie", default=None, help="fichier JSON brut de claude (defaut : harness/_cout/claude_code_<t0>.json)")
    ap.add_argument("--delai", type=int, default=600)
    ap.add_argument("--livre", default=None, help="grand livre (defaut : celui de cout.py)")
    A = ap.parse_args(argv)

    if A.reingerer:
        d = json.load(io.open(A.reingerer, encoding="utf-8"))
        st = os.stat(A.reingerer)
        t0_ms = int((st.st_mtime - (d.get("duration_ms") or 0) / 1000.0) * 1000)
        porter_au_livre(d, t0_ms, int(d.get("duration_ms") or 0), A.campagne, A.reingerer, A.livre)
        afficher(d)
        return 0
    if not A.tache_fichier:
        ap.error("--tache-fichier ou --reingerer")

    exe = shutil.which("claude")
    if not exe:
        print("claude introuvable dans le PATH")
        return 4
    tache = io.open(A.tache_fichier, encoding="utf-8").read()
    cmd = [exe, "-p", tache, "--output-format", "json", "--max-turns", str(A.max_turns),
           "--max-budget-usd", str(A.max_budget_usd), "--no-session-persistence",
           "--allowedTools"] + [t.strip() for t in A.allowed.split(",") if t.strip()]
    if A.model:
        cmd += ["--model", A.model]
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=A.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace")
    coupe = False
    try:
        so, se = p.communicate(timeout=A.delai)
    except subprocess.TimeoutExpired:
        coupe = True
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        p.kill()
        so, se = p.communicate()
    ms = int((time.time() - t0) * 1000)
    t0_ms = int(t0 * 1000)  # epoch ms, le format du recorder (cout.jour_de)
    os.makedirs(os.path.join(ICI, "_cout"), exist_ok=True)
    sortie = A.sortie or os.path.join(ICI, "_cout", "claude_code_%s.json" % time.strftime("%Y%m%d_%H%M%S", time.localtime(t0)))
    io.open(sortie, "w", encoding="utf-8").write(so or "")
    print("claude rc=%s  duree=%.1fs  allowed=%s  max-turns=%d  budget=%.2f USD%s"
          % (p.returncode, ms / 1000.0, A.allowed, A.max_turns, A.max_budget_usd, "  COUPE au delai %ds" % A.delai if coupe else ""))
    try:
        d = json.loads(so)
    except Exception as e:
        print("JSON inanalysable (%s) : brut dans %s ; stderr : %s" % (e, sortie, (se or "").strip()[:300]))
        # rien de facture n'est connu : on porte quand meme une ligne a cout inconnu
        porter_au_livre({"is_error": True, "usage": {}, "total_cost_usd": None,
                         "modelUsage": {"claude-code:inconnu" + (":coupe" if coupe else ""): {"costUSD": None}}},
                        t0_ms, ms, A.campagne, sortie, A.livre)
        print("(cout INCONNU porte au livre : %s)" % ("appel coupe" if coupe else "sortie illisible"))
        return 3
    # le livre D'ABORD : tout ce qui suit peut planter, la depense est deja comptee
    porter_au_livre(d, t0_ms, ms, A.campagne, sortie, A.livre)
    refus = afficher(d)
    if d.get("is_error") or p.returncode != 0 or coupe:
        return 1
    return 2 if refus else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
