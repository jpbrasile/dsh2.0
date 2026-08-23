# -*- coding: utf-8 -*-
"""Porte red-team (README, boucle 3) : un agent sur une AUTRE famille de modele
attaque le critere « done » d une etape, et son rapport brut est verse dans
redteam/<phase>-<etape>.md avec ce qui permet de le relire : modele, entrees,
usage mesure sur le fil, et le controle que le red team n a rien modifie.

    python harness/redteam_run.py <phase>-<etape> harness/redteam/<prompt>.md [--modele M] [--provider P]

Defaut : deepseek/deepseek-v4-pro sur openrouter-banc (route enregistree), cwd =
racine du depot dsh2.0, couche Lean, DSH_PERMISSION_MODE=workspace-write pour
qu il puisse LANCER les controles (lean_check, pin_check, fumee_route, dump-config)
-- la regle « lecture seule » du README est verifiee APRES coup par `git status` :
un fichier suivi modifie par le red team est un ECHEC du run, pas une trouvaille.

Le rapport n est pas interprete ici : la gravite des trouvailles et leur
acceptation sont ecrites par l humain dans le meme fichier (README : « A step
closes only when every HIGH finding is fixed or explicitly accepted »).
"""
import argparse, io, json, os, subprocess, sys, time

ICI = os.path.dirname(os.path.abspath(__file__))
DEPOT = os.path.dirname(ICI)
BENCH = os.path.join(DEPOT, "scripts", "bench_julia_effort")
S = os.path.join(BENCH, "_fumee")

ap = argparse.ArgumentParser()
ap.add_argument("etape", help="ex. 0-lean -> redteam/0-lean.md")
ap.add_argument("prompt", help="fichier du prompt (UTF-8)")
ap.add_argument("--modele", default="deepseek/deepseek-v4-pro")
ap.add_argument("--provider", default="openrouter-banc")
ap.add_argument("--effort", default="off")
ap.add_argument("--delai", type=int, default=1500)
ap.add_argument("--cwd", default=DEPOT)
ap.add_argument("--prep", action="append", default=[],
                help="commande (shell) lancee AVANT le red team, depuis cwd, sortie dans "
                     "_rt_scratch/prep_<n>.txt : ce que le red team ne peut pas lancer lui-meme "
                     "depuis le sandbox (ex. dsh --dump-config, qui ecrit hors espace)")
A = ap.parse_args()

avant = subprocess.run(["git", "-C", A.cwd, "status", "--porcelain"], capture_output=True, text=True).stdout
scratch = os.path.join(A.cwd, "_rt_scratch")
import shutil
shutil.rmtree(scratch, ignore_errors=True)     # le rapport au fil de l eau du run precedent
if A.prep:
    os.makedirs(scratch, exist_ok=True)
    for n, cmd in enumerate(A.prep, 1):
        pr = subprocess.run(cmd, shell=True, cwd=A.cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=600)
        io.open(os.path.join(scratch, "prep_%d.txt" % n), "w", encoding="utf-8").write(
            "$ %s\n(rc=%s)\n%s\n%s" % (cmd, pr.returncode, pr.stdout, pr.stderr))
        print("prep %d : rc=%s -> _rt_scratch/prep_%d.txt" % (n, pr.returncode, n))
env = dict(os.environ, DSH_PERMISSION_MODE="workspace-write")
for k in ("OPENROUTER_API_KEY", "ZAI_API_KEY", "DEEPSEEK_API_KEY"):
    env.pop(k, None)
t0 = time.time()
r = subprocess.run([sys.executable, os.path.join(BENCH, "fumee_route.py"), A.modele, A.provider,
                    "--patch", os.path.join(ICI, "lean.patch.yml"), "--fichier", "-",
                    "--cwd", A.cwd, "--delai", str(A.delai), "--effort", A.effort,
                    "--tache-fichier", os.path.abspath(A.prompt)],
                   cwd=BENCH, env=env, capture_output=True, text=True, timeout=A.delai + 120)
dt = time.time() - t0
apres = subprocess.run(["git", "-C", A.cwd, "status", "--porcelain"], capture_output=True, text=True).stdout
modifies = sorted(set(apres.splitlines()) - set(avant.splitlines()))

calls = []
wire = os.path.join(S, "wire.jsonl")
if os.path.exists(wire):
    calls = [json.loads(l) for l in io.open(wire, encoding="utf-8")]
    calls = [c for c in calls if c.get("kind") == "call"]
servis = sorted({c.get("servi") for c in calls})
tok_in = sum((c.get("usage") or {}).get("prompt_tokens") or 0 for c in calls)
tok_out = sum((c.get("usage") or {}).get("completion_tokens") or 0 for c in calls)
reponse = io.open(os.path.join(S, "dsh_stdout.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(S, "dsh_stdout.txt")) else ""
partiel = os.path.join(scratch, "rapport.md")
if not reponse and os.path.exists(partiel):
    reponse = ("_Rapport PARTIEL : le red team n a pas rendu de reponse finale (delai %ds) ; "
               "ci-dessous son fichier au fil de l eau `_rt_scratch/rapport.md` tel quel._\n\n" % A.delai
               + io.open(partiel, encoding="utf-8").read().strip())
verdict_fumee = [l for l in r.stdout.splitlines() if l.startswith("VERDICT")]

os.makedirs(os.path.join(DEPOT, "redteam"), exist_ok=True)
cible = os.path.join(DEPOT, "redteam", A.etape + ".md")
lignes = [
    "# Red team -- %s" % A.etape,
    "",
    "| | |",
    "|---|---|",
    "| date | %s |" % time.strftime("%Y-%m-%d %H:%M"),
    "| modele red team | `%s` via `%s` (servi : %s) |" % (A.modele, A.provider, ", ".join("`%s`" % s for s in servis) or "aucun appel"),
    "| prompt | `%s` |" % os.path.relpath(os.path.abspath(A.prompt), DEPOT).replace(os.sep, "/"),
    "| cwd | `%s` |" % A.cwd,
    "| appels / tokens | %d appels, %d entree, %d sortie, %.0f s |" % (len(calls), tok_in, tok_out, dt),
    "| dsh | rc de fumee_route = %s ; %s |" % (r.returncode, " ; ".join(verdict_fumee) or "pas de ligne VERDICT"),
    "| fichiers suivis modifies par le red team | %s |" % ("**AUCUN**" if not modifies else "**ECHEC DU RUN** : " + ", ".join("`%s`" % m for m in modifies)),
    "",
    "## Rapport brut du red team (non edite)",
    "",
    reponse or "_(reponse vide : voir scripts/bench_julia_effort/_fumee/dsh_out.txt)_",
    "",
    "## Decision humaine",
    "",
    "_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_",
    "",
]
io.open(cible, "w", encoding="utf-8", newline="\n").write("\n".join(lignes))
print("rapport : %s" % os.path.relpath(cible, DEPOT))
print("appels=%d servis=%s tokens in/out=%d/%d duree=%.0fs rc=%s" % (len(calls), servis, tok_in, tok_out, dt, r.returncode))
print("fichiers suivis modifies :", modifies or "aucun")
print("reponse : %d caracteres" % len(reponse))
if not reponse:
    print(r.stdout[-1500:])
sys.exit(0 if reponse and not modifies else 1)
