# reasoning_effort PREND-IL VRAIMENT a travers OpenRouter ?
#
# POURQUOI CETTE QUESTION. La carte de modele et la presse technique disent que
# Qwen3.8-27B part en `xhigh` par defaut et sur-reflechit massivement (21 min et
# 22 276 jetons de raisonnement pour un SVG simple ; ~60 K jetons de pensee par
# tour). Le correctif documente est le parametre d'effort.
#
# Nos deux agents envoient DEJA `reasoning_effort: "medium"` -- mesure sur le
# fil au serveur temoin le 26/08. Et pourtant un appel du banc a brule 10 095
# jetons de raisonnement en 511 s. Deux lectures possibles :
#   (a) `medium` ne franchit pas OpenRouter (drapeau ignore, ou non traduit vers
#       le gabarit Jinja) et le modele tourne a son defaut xhigh ;
#   (b) `medium` passe bien, et il est simplement encore trop bavard.
#
# On tranche par la mesure : MEME question, MEME graine de parametres, seul
# l'effort change. L'observable est usage.completion_tokens_details
# .reasoning_tokens, rendu par OpenRouter lui-meme.
#
# Deux formes sont testees, parce qu'elles ne sont PAS equivalentes :
#   - `reasoning_effort` (alias compat OpenAI, ce que dsh et pi envoient) ;
#   - `reasoning: {"effort": ...}` (forme native OpenRouter).
# Si la premiere ne bouge pas et la seconde oui, le banc envoie un drapeau mort.

import io
import json
import os
import re
import sys
import time
import urllib.request

DOTENV = r"C:\Users\test\Documents\dsh2.0\.env"
URL = "https://openrouter.ai/api/v1/chat/completions"
MODELE = "qwen/qwen3.8-27b"

# Question courte mais qui invite a reflechir : c'est la ou l'effort se voit.
Q = ("A bookshop sells a 5-book series at $8 per book. Buying 2 different "
     "titles gives 5% off those two, 3 different gives 10%, 4 gives 20%, "
     "5 gives 25%. For a basket of 2,2,2,1,1 copies of the five titles, what "
     "is the cheapest total? Answer with the number only.")


def cle():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for ligne in io.open(DOTENV, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=(.*)$", ligne)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("REFUS : OPENROUTER_API_KEY introuvable.")


CLE = cle()


def appel(etiquette, extra):
    corps = {
        "model": MODELE,
        "messages": [{"role": "user", "content": Q}],
        "max_tokens": 16384,
        "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
    }
    corps.update(extra)
    req = urllib.request.Request(
        URL, data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + CLE,
                 "User-Agent": "dsh2.0-test-effort/1.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("%-34s ECHEC : %s" % (etiquette, e))
        return
    dt = time.time() - t0
    u = d.get("usage") or {}
    ct = u.get("completion_tokens") or 0
    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    fr = (d.get("choices") or [{}])[0].get("finish_reason")
    txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    print("%-34s %7.1fs  sortie=%-6d raisonnement=%-6d  fin=%-7s cout=%.4f$"
          % (etiquette, dt, ct, rt, fr, u.get("cost") or 0))
    print("%-34s reponse : %s" % ("", txt.strip()[-90:].replace("\n", " ")))
    sys.stdout.flush()


if __name__ == "__main__":
    print("modele : %s   question identique, seul l'effort change\n" % MODELE)
    appel("(1) aucun effort envoye", {})
    appel("(2) reasoning_effort=medium", {"reasoning_effort": "medium"})
    appel("(3) reasoning_effort=low", {"reasoning_effort": "low"})
    appel("(4) reasoning={effort:low}", {"reasoning": {"effort": "low"}})
    print()
    print("LECTURE : si (1) et (2) donnent le meme nombre de jetons de")
    print("raisonnement, le drapeau que le banc envoie est MORT.")
