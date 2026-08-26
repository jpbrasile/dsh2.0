# Sonde d'un seul appel : le mur a 512 jetons de pensee est-il tombe ?
#
# Une verification de l'argv prouve que le drapeau est pose, pas que l'effet a
# disparu. On mesure donc la chose elle-meme : un bloc <think> dont la longueur
# TOKENISEE par le serveur depasse franchement 512.
import io
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8005"
# Question volontairement couteuse en raisonnement, hors GPQA pour ne pas
# polluer le corpus mesure.
Q = ("A 0.1 mol sample of a weak triprotic acid (Ka1=1e-3, Ka2=1e-8, "
     "Ka3=1e-12) is dissolved in 1.00 L of water and titrated with 0.50 M "
     "NaOH. Compute the pH at the second equivalence point, showing every "
     "approximation you make and checking each one.")


def poste(chemin, charge):
    req = urllib.request.Request(
        BASE + chemin, data=json.dumps(charge).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


d = poste("/v1/chat/completions", {
    "model": "specdec-q38-dflash2",
    "messages": [{"role": "user", "content": Q}],
    "max_tokens": 16384,
    "temperature": 1.0, "top_p": 0.95,
})
msg = d["choices"][0]
txt = msg["message"]["content"] or ""
print("finish_reason : %s" % msg.get("finish_reason"))
print("jetons sortie : %s" % (d.get("usage") or {}).get("completion_tokens"))

m = re.search(r"<think>(.*?)</think>", txt, re.S)
if not m:
    print("AUCUN bloc <think> -- la sonde ne conclut pas.")
    sys.exit(1)
bloc = m.group(1)
n = len(json.loads(io.BytesIO(urllib.request.urlopen(urllib.request.Request(
    BASE + "/tokenize", data=json.dumps({"content": bloc}).encode("utf-8"),
    headers={"Content-Type": "application/json"}), timeout=120).read()
).read().decode("utf-8"))["tokens"])
print("bloc <think>  : %d jetons" % n)
fin = bloc.rstrip()[-70:]
print("fin du bloc   : ...%s" % fin.replace("\n", " "))
print()
if n > 600:
    print("VERDICT : mur tombe (%d > 512)." % n)
else:
    print("VERDICT : %d jetons -- NON CONCLUANT, le mur peut tenir." % n)
