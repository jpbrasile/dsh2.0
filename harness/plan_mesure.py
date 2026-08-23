"""Mesure deterministe d'un plan du planner contre les fautes consignees (Done phase 3).

    python harness/plan_mesure.py <plan.md> [...]

Trois marqueurs, chacun une regex nommee -- pas un jugement :
  verdict   : le plan nomme le verdict de la porte VERT (vocabulaire de julia_gate) et non PASS
  autoverif : le plan dit que l'auto-verification des invariants est statique / par lecture /
              inexecutable par le coder (faute consignee le 23/08 : « the coder could not execute
              the plan's self-check ... lacked direct Julia execution ») ; REPETEE si le plan
              demande au coder d'EXECUTER des verifications (« runs self-checks through julia_gate »,
              « must also verify ... ») sans cette reserve ; ABSENTE si le plan n'en parle pas
  fleche    : « f(...) -> T » (notation de l'enonce, pas du Julia) recopie : en ligne de code
              indentee (ce que le coder colle -- faute consignee : `-> Bool` dans le code, ROUGE x3)
              ou seulement cite dans la prose
Sortie : une ligne par plan, puis un tableau ; code 0.
"""
import io
import re
import sys

VERT = re.compile(r"\bVERT\b")
PASS = re.compile(r"\*\*PASS\*\*|verdict (is|must be|=) `?PASS`?|verdict `PASS`", re.I)
STATIQUE = re.compile(r"by inspect|inspect(ing|ion)|static(ally)?|by construction|cannot (be )?(run|execut)|can't (run|execute)|"
                      r"gate runs (the )?existing tests only|not executable|no (direct )?julia execution|only (runs|replays) existing tests|"
                      r"reason(ing)? about the code|mentally|without (running|executing)", re.I)
EXECUTE = re.compile(r"(runs?|perform|execute|do|carry out)\s+(a |the |its )?self-?checks?\s+(through|via|with|using)\s+`?julia_gate|"
                     r"(must|should|needs? to|has to)\s+(also\s+)?(perform|run|do|execute|carry out)\s+(a |an |the |its )?(\w+\s+)?self-?check|"
                     r"must (also )?verify|should (also )?verify (a |the )?(invariants|self)|self-?check(s)? (that|which) verif", re.I)
AUTOVERIF = re.compile(r"self-?check|invariant", re.I)
FONCTIONS = r"(validate_financing|compute_debt_schedule|total_interest_paid)\([^)]*\)\s*->\s*\w"
FLECHE_CODE = re.compile(r"^\s{4,}" + FONCTIONS, re.M)      # ligne de code indentee : ce que le coder colle
FLECHE_PROSE = re.compile(r"^\S.*" + FONCTIONS, re.M)       # dans la prose (liste, titre) : notation citee


def mesurer(chemin):
    t = io.open(chemin, encoding="utf-8", errors="replace").read()
    verdict = "VERT" if VERT.search(t) and not PASS.search(t) else ("PASS" if PASS.search(t) else "aucun")
    if not AUTOVERIF.search(t):
        autoverif = "absente"
    elif STATIQUE.search(t):
        autoverif = "EVITEE (statique)"
    elif EXECUTE.search(t):
        autoverif = "REPETEE (execution demandee)"
    else:
        autoverif = "floue"
    fleche = "%d code / %d prose" % (len(FLECHE_CODE.findall(t)), len(FLECHE_PROSE.findall(t)))
    return {"plan": chemin, "car": len(t), "verdict": verdict, "autoverif": autoverif, "fleche": fleche}


if __name__ == "__main__":
    rows = [mesurer(p) for p in sys.argv[1:]]
    print("%-12s %6s  %-8s %-30s %s" % ("plan", "car.", "verdict", "auto-verification", "-> signature (code / prose)"))
    for r in rows:
        print("%-12s %6d  %-8s %-30s %s" % (r["plan"].split("/")[-1].split("\\")[-1], r["car"], r["verdict"], r["autoverif"], r["fleche"]))
