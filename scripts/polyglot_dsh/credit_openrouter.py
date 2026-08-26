# Credit OpenRouter restant. La cle est lue du .env dans le processus, jamais
# affichee ni passee en argument.
import io
import json
import os
import re
import urllib.request

DOTENV = r"C:\Users\test\Documents\dsh2.0\.env"


def cle():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for ligne in io.open(DOTENV, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=(.*)$", ligne)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("REFUS : OPENROUTER_API_KEY introuvable.")


req = urllib.request.Request(
    "https://openrouter.ai/api/v1/credits",
    headers={"Authorization": "Bearer " + cle(),
             "User-Agent": "dsh2.0-credit/1.0"})
with urllib.request.urlopen(req, timeout=60) as r:
    d = json.loads(r.read().decode("utf-8", "replace")).get("data", {})
achete = d.get("total_credits")
use = d.get("total_usage")
if achete is not None and use is not None:
    print("achete %.2f $   utilise %.2f $   RESTANT %.2f $"
          % (achete, use, achete - use))
else:
    print(json.dumps(d, indent=2))
