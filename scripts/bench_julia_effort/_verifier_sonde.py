# Un appel minimal a travers le proxy 8009, pour verifier que la sonde de
# prefixe ecrit bien `prefix_h` -- AVANT de lancer un run qui coute.
#
# LA CLE NE SORT PAS. Elle est lue depuis .env, posee dans l'en-tete, et jamais
# imprimee, ni en entier ni en extrait. Le script n'affiche que le statut HTTP
# et le nom du journal qui a grossi.
#
# COUT : un appel de 1 jeton de sortie sur un modele a moins d'un dollar le
# million. C'est l'assurance la moins chere du banc -- un run de 6 exercices
# qui decouvre a la fin que la sonde n'ecrivait pas coute 2,37 $.

import io
import json
import os
import time
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def charger_env(chemin):
    if not os.path.exists(chemin):
        return
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        k, v = ligne.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


charger_env(os.path.join(RACINE, ".env"))
cle = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")
if not cle:
    raise SystemExit("REFUS : aucune cle OpenRouter dans l'environnement.")

ici = os.path.dirname(os.path.abspath(__file__))
avant = {}
for f in os.listdir(ici):
    if f.startswith("wire") and f.endswith(".jsonl"):
        avant[f] = os.path.getsize(os.path.join(ici, f))

corps = {
    "model": "qwen/qwen3.8-27b",
    "messages": [{"role": "system", "content": "s"},
                 {"role": "user", "content": "Reply with the single word: ok"}],
    "max_tokens": 1,
}
req = urllib.request.Request(
    "http://127.0.0.1:8009/api/v1/chat/completions",
    data=json.dumps(corps).encode("utf-8"),
    headers={"Content-Type": "application/json",
             "Authorization": "Bearer %s" % cle})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        statut = r.status
        d = json.loads(r.read().decode("utf-8", "replace"))
    print("statut HTTP %s   cout declare %s $"
          % (statut, (d.get("usage") or {}).get("cost")))
except Exception as e:
    print("appel en echec : %s: %s" % (type(e).__name__, str(e)[:200]))

time.sleep(1.5)
for f in sorted(os.listdir(ici)):
    if not (f.startswith("wire") and f.endswith(".jsonl")):
        continue
    taille = os.path.getsize(os.path.join(ici, f))
    if taille != avant.get(f):
        print("journal qui a grossi : %s  (%d -> %d octets)"
              % (f, avant.get(f, 0), taille))
        derniere = None
        for l in io.open(os.path.join(ici, f), encoding="utf-8", errors="replace"):
            l = l.strip()
            if l:
                derniere = l
        d = json.loads(derniere)
        s = d.get("sent") or {}
        print("  kind          : %s" % d.get("kind"))
        print("  champs sent   : %s" % sorted(s.keys()))
        ph = s.get("prefix_h")
        print("  prefix_h      : %s  (%s entrees)"
              % ("PRESENT" if isinstance(ph, list) else "ABSENT",
                 len(ph) if isinstance(ph, list) else "-"))
        print("  msg_chars     : %s" % (s.get("msg_chars")))
        print("  roles         : %s" % (s.get("roles")))
