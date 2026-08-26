# SONDE. Le budget 8192 coupe-t-il vraiment, et le message de transition
# arrive-t-il bien AVANT la balise de fin de pensee ?
#
# On ne se fie pas au journal : `--reasoning-budget` ne leve JAMAIS
# finish_reason: length -- c'est precisement ce qui a rendu la guillotine 512
# invisible pendant vingt heures. Le seul temoin est le TEXTE rendu.
#
# Question choisie pour provoquer la sur-deliberation : ouverte, sans reponse
# courte evidente. Si le bloc de pensee sort a ~8192 jetons et se termine par le
# message, le dispositif fonctionne. S'il sort bien en dessous, la question
# n'etait pas assez dure -- ce n'est pas une preuve que le budget est mort.

import json
import re
import urllib.request

BASE = "http://127.0.0.1:8005"

Q = ("Estimate, from first principles and showing your reasoning, the total "
     "mass of all the ants on Earth relative to the total mass of all humans. "
     "Consider several independent estimation routes and reconcile them.")


def poste(chemin, corps):
    req = urllib.request.Request(
        BASE + chemin, data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


d = poste("/v1/chat/completions", {
    "messages": [{"role": "user", "content": Q}],
    "max_tokens": 16384,
    "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
})

ch = (d.get("choices") or [{}])[0]
msg = ch.get("message") or {}
txt = msg.get("content") or ""
# llama.cpp peut rendre la pensee separement selon --reasoning-format.
pensee = msg.get("reasoning_content") or ""
if not pensee:
    m = re.search(r"<think>(.*?)</think>", txt, re.S)
    pensee = m.group(1) if m else ""
    apres = re.sub(r"(?s).*?</think>", "", txt) if m else txt
else:
    apres = txt

u = d.get("usage") or {}
n_pensee = len(poste("/tokenize", {"content": pensee}).get("tokens") or [])

print("finish_reason      : %s" % ch.get("finish_reason"))
print("jetons sortie      : %s" % u.get("completion_tokens"))
print("jetons de pensee   : %d   (budget pose : 8192)" % n_pensee)
print()
print("--- 400 derniers caracteres de la PENSEE ---")
print(pensee[-400:])
print()
print("--- reponse hors pensee (300 premiers) ---")
print(apres.strip()[:300])
print()
cle = "thinking budget is now exhausted"
print("message de transition present dans la pensee : %s" % (cle in pensee))
print("derniere ligne Answer: presente               : %s"
      % bool(re.search(r"(?im)^\s*Answer:\s*\S", apres)))
