# UN appel reel a travers le proxy d'injection : OpenRouter accepte-t-il les
# quatre champs d'echantillonnage pour ce modele, ou rend-il 400 ?
#
# POURQUOI CE FICHIER. `top_k` et `min_p` ne sont pas des champs OpenAI
# standard. Un amont qui refuse un champ inconnu ferait echouer TOUS les appels
# du banc -- et la panne ressemblerait a un probleme d'agent. Un appel a un
# jeton coute presque rien et repond avant qu'on engage une campagne.
#
# LA CLE NE PASSE PAS PAR LA LIGNE DE COMMANDE. Elle est lue du .env dans le
# processus et posee dans l'en-tete ; elle n'est ni affichee, ni journalisee,
# ni visible dans la liste des processus.

import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

DOTENV = r"C:\Users\test\Documents\dsh2.0\.env"
# OpenRouter sert /api/v1, pas /v1. Le proxy transmet le chemin tel quel :
# une baseURL en /v1 donne un 404 HTML, qui ressemble a un refus de champ.
PROXY = "http://127.0.0.1:8009/api/v1/chat/completions"
MODELE = "qwen/qwen3.8-27b"


def cle():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for ligne in io.open(DOTENV, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=(.*)$", ligne)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("REFUS : OPENROUTER_API_KEY introuvable.")


def main():
    corps = {
        "model": MODELE,
        "messages": [{"role": "user", "content": "ok"}],
        "max_tokens": 1,
        # Volontairement PAS d'echantillonnage ici : c'est le proxy qui doit
        # l'injecter. Si les champs arrivent chez OpenRouter, ils viennent
        # de lui -- c'est exactement ce qu'on veut prouver.
    }
    req = urllib.request.Request(
        PROXY, data=json.dumps(corps).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 # SANS User-Agent, Cloudflare rend 403 code 1010 et on croit a
                 # un refus de champ (mesure du 26/08). Les agents envoient le
                 # leur ; ce client de test doit en avoir un aussi, sinon il
                 # teste le pare-feu et pas l'API.
                 "User-Agent": "dsh2.0-verif-injection/1.0",
                 "Authorization": "Bearer " + cle()})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        print("HTTP 200 -- OpenRouter a ACCEPTE les champs injectes.")
        print("  modele servi : %s" % d.get("model"))
        print("  usage        : %s" % d.get("usage"))
        ch = (d.get("choices") or [{}])[0]
        print("  finish       : %s" % ch.get("finish_reason"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        print("HTTP %d -- REFUS de l'amont. L'injection n'est PAS utilisable "
              "telle quelle." % e.code)
        print(detail)
        sys.exit(1)
    except Exception as e:
        print("ECHEC reseau : %s" % e)
        sys.exit(2)


if __name__ == "__main__":
    main()
