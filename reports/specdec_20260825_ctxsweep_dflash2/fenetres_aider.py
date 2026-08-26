"""Ou sont les 29 fenetres de contexte epuisees du run aider 4 tours ?

La question qui compte : l'annulation de la synthese d'historique
(max_chat_history_tokens = 1 000 000) a-t-elle DEPLACE le probleme -- plus de
resume, mais un contexte qui deborde ? Si oui, les exercices touches doivent
etre ceux qui vont loin dans les tours, et ils doivent echouer plus souvent.
"""
import glob
import json
import os

RUN = (r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
       r"\2026-08-25-19-06-21--dsh-q8q4-160k-16k-t1-tries4-full")

fics = sorted(glob.glob(os.path.join(RUN, "*", "exercises", "practice", "*",
                                     ".aider.results.json")))
touches, sains = [], []
for f in fics:
    try:
        r = json.loads(open(f, encoding="utf-8").read())
    except Exception:
        continue
    p = os.path.normpath(f).split(os.sep)
    nom = "%s/%s" % (p[-5], p[-2])
    outc = r.get("tests_outcomes", [])
    ex = r.get("num_exhausted_context_windows", 0)
    mal = r.get("num_malformed_responses", 0)
    fiche = {"nom": nom, "tours": len(outc), "ok": bool(outc) and outc[-1],
             "ex": ex, "mal": mal}
    (touches if ex else sains).append(fiche)

print("exercices touches par une fenetre epuisee : %d / %d"
      % (len(touches), len(touches) + len(sains)))
print("total de fenetres epuisees : %d"
      % sum(t["ex"] for t in touches))
print("")
print("%-34s %5s %6s %4s %4s" % ("exercice", "tours", "issue", "ep.", "mal."))
for t in sorted(touches, key=lambda x: (-x["ex"], x["nom"])):
    print("%-34s %5d %6s %4d %4d"
          % (t["nom"], t["tours"], "PASS" if t["ok"] else "FAIL",
             t["ex"], t["mal"]))

def taux(g):
    return (100.0 * sum(1 for x in g if x["ok"]) / len(g)) if g else float("nan")

print("")
print("reussite des touches : %d/%d = %.1f %%"
      % (sum(1 for x in touches if x["ok"]), len(touches), taux(touches)))
print("reussite des sains   : %d/%d = %.1f %%"
      % (sum(1 for x in sains if x["ok"]), len(sains), taux(sains)))

print("")
for n in (1, 2, 3, 4):
    g = [x for x in touches if x["tours"] == n]
    h = [x for x in sains if x["tours"] == n]
    print("  tours=%d : touches %2d   sains %3d" % (n, len(g), len(h)))
