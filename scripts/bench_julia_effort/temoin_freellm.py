# -*- coding: utf-8 -*-
"""Temoin FreeLLMAPI : nomme le modele REELLEMENT servi, pas un HTTP 200.

Un banc qui note "l'API a repondu" ne sait pas QUI a repondu. On imprime donc
`body["model"]` et l'en-tete `x-fallback-trail` : si le routeur a bascule, la
mesure porte sur un autre modele que celui qu'on croit epingler.
"""
import json, subprocess, sys, time, urllib.request, urllib.error
BASE = "http://127.0.0.1:31415/v1"
import os
# scripts/freellm_key.py, un niveau au-dessus de ce dossier (chemin relatif au
# depot dsh2.0, plus l'absolu de agentic-flow-fresh).
LECTEUR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "freellm_key.py")
KEY = subprocess.run([sys.executable, LECTEUR],
                     capture_output=True, text=True, check=True).stdout.strip()
OUTILS = [{"type": "function", "function": {
    "name": "ecrire_fichier",
    "description": "Ecrit un fichier sur le disque.",
    "parameters": {"type": "object",
                   "properties": {"chemin": {"type": "string"},
                                  "contenu": {"type": "string"}},
                   "required": ["chemin", "contenu"]}}}]

def appel(modele, avec_outils):
    corps = {"model": modele, "max_tokens": 200, "temperature": 0,
             "messages": [{"role": "user", "content":
                           "Ecris le fichier bonjour.txt contenant PONG."
                           if avec_outils else "Reponds exactement: PONG"}]}
    if avec_outils:
        corps["tools"] = OUTILS
        corps["tool_choice"] = "auto"
    req = urllib.request.Request(
        BASE + "/chat/completions",
        headers={"Authorization": "Bearer " + KEY,
                 "Content-Type": "application/json"},
        data=json.dumps(corps).encode())
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            b = json.loads(r.read())
            trail = r.headers.get("x-fallback-trail") or "aucune"
    except urllib.error.HTTPError as e:
        print("  %-18s outils=%-3s  HTTP %s : %s"
              % (modele, avec_outils, e.code, e.read()[:160].decode("utf-8", "replace")))
        return None
    msg = b["choices"][0]["message"]
    appels = msg.get("tool_calls") or []
    print("  %-18s outils=%-3s  servi=%-22s %5.1fs  tool_calls=%d  bascule=%s"
          % (modele, avec_outils, b.get("model"), time.time() - t0,
             len(appels), trail))
    if appels:
        print("      -> %s(%s)" % (appels[0]["function"]["name"],
                                   appels[0]["function"]["arguments"][:80]))
    u = b.get("usage") or {}
    if u:
        print("      jetons : entree=%s sortie=%s" % (u.get("prompt_tokens"), u.get("completion_tokens")))
    return b

for m in sys.argv[1:] or ["auto"]:
    appel(m, False)
    appel(m, True)
