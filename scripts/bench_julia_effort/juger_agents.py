# -*- coding: utf-8 -*-
"""Juge les espaces de travail des sous-agents avec LE MEME harnais que le banc.

Ne devine rien : le verdict vient de tasks/harness.jl, le journal vient du
fichier ecrit par l'agent, et les deux sont rendus separement -- un journal
absent est un journal absent, pas un zero.
"""
import io, json, os, subprocess, sys

B = os.path.dirname(os.path.abspath(__file__))
# racine des espaces de travail des sous-agents :
#   <racine>/<bras>/<tache>/solution.jl  et  _journal.txt
AG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(B, "ref_agents", "espaces")
SP = AG
TACHES = ["t21", "t22", "t23", "t24", "t25", "t26",
          "t31", "t32", "t33", "t34", "t35", "t36"]
# les quatre faits qui ne sont PAS dans l'enonce (mesure du 22/08)
EXTERNE = {"t22", "t24", "t32", "t34"}


def juger(sol, tache):
    if not os.path.exists(sol):
        return "ABSENT", "aucun solution.jl"
    p = subprocess.run([os.environ.get("JULIA", "julia"), "--startup-file=no",
                        "--color=no", os.path.join(B, "tasks", "harness.jl"),
                        sol, os.path.join(B, "tasks", "%s_checks.jl" % tache)],
                       capture_output=True, text=True, cwd=B)
    for l in ((p.stdout or "") + (p.stderr or "")).splitlines():
        if l.startswith("VERDICT PASS"):
            return "PASS", ""
        if l.startswith("VERDICT FAIL"):
            return "FAIL", l[len("VERDICT FAIL "):][:100]
    return "?", ((p.stdout or "") + (p.stderr or ""))[:100]


def journal(ws):
    f = os.path.join(ws, "_journal.txt")
    if not os.path.exists(f):
        return {}
    d = {}
    for l in io.open(f, encoding="utf-8-sig", errors="replace"):
        if "=" in l:
            k, _, v = l.partition("=")
            d[k.strip()] = v.strip()
    return d


def main():
    lignes = []
    for bras in ("web", "sansweb"):
        for t in TACHES:
            ws = os.path.join(AG, bras, t)
            if not os.path.isdir(ws):
                continue
            sol = os.path.join(ws, "solution.jl")
            v, why = juger(sol, t)
            j = journal(ws)
            autres = sorted(x for x in os.listdir(ws)
                            if x not in ("TASK.md", "solution.jl", "_journal.txt"))
            lignes.append({
                "bras": bras, "tache": t, "verdict": v, "pourquoi": why,
                "julia": j.get("JULIA_RUNS", "n/a"),
                "web": j.get("WEB_SEARCHES", "n/a"),
                "requetes": j.get("QUERIES", ""),
                "lignes": (sum(1 for _ in io.open(sol, encoding="utf-8",
                                                  errors="replace"))
                           if os.path.exists(sol) else 0),
                "fichiers_laisses": autres,
                "fait_externe": t in EXTERNE,
            })
    io.open(os.path.join(SP, "agents_resultats.json"), "w",
            encoding="utf-8", newline="\n").write(
        json.dumps(lignes, ensure_ascii=False, indent=1))

    print("bras     tache  ext  verdict  julia  web  lignes  pourquoi")
    for r in lignes:
        print("%-8s %-6s %-4s %-8s %-6s %-4s %-7d %s"
              % (r["bras"], r["tache"], "OUI" if r["fait_externe"] else "-",
                 r["verdict"], r["julia"], r["web"], r["lignes"],
                 r["pourquoi"][:46]))
    for bras in ("web", "sansweb"):
        s = [r for r in lignes if r["bras"] == bras]
        if not s:
            continue
        ok = sum(1 for r in s if r["verdict"] == "PASS")
        e = [r for r in s if r["fait_externe"]]
        eok = sum(1 for r in e if r["verdict"] == "PASS")
        wq = [r for r in s if r["web"] not in ("n/a", "0", "")]
        print("\n%-8s %d/%d PASS   dont fait externe %d/%d   runs ayant cherche : %d/%d"
              % (bras, ok, len(s), eok, len(e), len(wq), len(s)))


main()
