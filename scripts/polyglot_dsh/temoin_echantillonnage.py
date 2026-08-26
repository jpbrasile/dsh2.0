# SERVEUR TEMOIN : que mettent REELLEMENT dsh et pi dans le corps de requete ?
#
# POURQUOI CE FICHIER EXISTE
# --------------------------
# Le 26/08 on a constate que ni settings.yaml (banc dsh) ni le bundle de pi ne
# posent temperature / top_p / top_k. On en DEDUIT qu'aucun des deux n'en envoie.
# Une deduction par lecture de code n'est pas une mesure : un defaut peut etre
# injecte plus loin dans la pile, et l'absence d'une constante en dur ne prouve
# pas l'absence du champ sur le fil. Ce serveur lit ce qui part.
#
# CE QU'IL NE FAIT PAS. Il ne touche PAS au 4090 : le run GPQA local occupe le
# port 8005 et un banc partage ne se bouscule pas. Le temoin repond lui-meme,
# ne charge aucun modele, ne consomme aucun credit OpenRouter.
#
# CE QU'IL ENREGISTRE. Le corps JSON entier de chaque POST, plus -- et c'est le
# chiffre qu'on cherche -- la LISTE DES CLES d'echantillonnage presentes. Une
# cle absente est le resultat, au meme titre qu'une valeur.
#
# USAGE
#   python temoin_echantillonnage.py --port 8007 --journal temoin_dsh.jsonl
# puis pointer l'agent sur http://127.0.0.1:8007/v1 et lire le journal.

import argparse
import io
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Les champs d'echantillonnage qu'on cherche. Presence/absence, pas seulement
# valeur : c'est la question posee.
CLES = ("temperature", "top_p", "top_k", "min_p", "typical_p",
        "presence_penalty", "frequency_penalty", "repetition_penalty",
        "repeat_penalty", "seed", "max_tokens", "max_completion_tokens",
        "stream", "reasoning_effort", "chat_template_kwargs", "reasoning")

REPONSE = ("Mesure du temoin : rien a faire. Cette reponse est fabriquee par le "
           "serveur temoin, aucun modele n'a tourne.")


class Temoin(BaseHTTPRequestHandler):
    journal = None
    modele = "temoin"

    def log_message(self, *a):
        pass  # le journal de acces d'http.server n'apporte rien ici

    # -- lecture ---------------------------------------------------------
    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": [
                {"id": self.modele, "object": "model", "owned_by": "temoin"}]})
        else:
            self._json({"ok": True})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        brut = self.rfile.read(n) if n else b""
        try:
            corps = json.loads(brut.decode("utf-8"))
        except Exception as e:
            corps = {"_illisible": str(e), "_octets": len(brut)}

        presentes = {k: corps.get(k) for k in CLES if k in corps}
        enreg = {
            "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "chemin": self.path,
            # LA MESURE. Les cles d'echantillonnage effectivement transmises.
            "cles_echantillonnage": sorted(presentes),
            "valeurs": presentes,
            # Toutes les cles du corps, pour voir ce qu'on n'avait pas prevu.
            "toutes_cles": sorted(k for k in corps if not k.startswith("_")),
            "modele_demande": corps.get("model"),
            "nb_messages": len(corps.get("messages") or []),
        }
        if self.journal:
            with io.open(self.journal, "a", encoding="utf-8") as f:
                f.write(json.dumps(enreg, ensure_ascii=False) + "\n")
        sys.stdout.write("  POST %s  cles=%s\n"
                         % (self.path, enreg["cles_echantillonnage"] or "AUCUNE"))
        sys.stdout.flush()

        if corps.get("stream"):
            self._flux(corps.get("model") or self.modele)
        else:
            self._json(self._completion(corps.get("model") or self.modele))

    # -- reponses --------------------------------------------------------
    def _completion(self, modele):
        return {"id": "temoin-1", "object": "chat.completion",
                "created": int(time.time()), "model": modele,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant",
                                         "content": REPONSE}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                          "total_tokens": 2}}

    def _json(self, obj):
        d = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)

    def _flux(self, modele):
        """SSE. Les deux agents streament par defaut ; sans ce chemin le temoin
        recevrait la requete (donc la mesure serait faite) mais l'agent
        planterait et n'en enverrait pas d'autre."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        base = {"id": "temoin-1", "object": "chat.completion.chunk",
                "created": int(time.time()), "model": modele}
        for delta, fin in (({"role": "assistant", "content": REPONSE}, None),
                           ({}, "stop")):
            morceau = dict(base)
            morceau["choices"] = [{"index": 0, "delta": delta,
                                   "finish_reason": fin}]
            self.wfile.write(b"data: " + json.dumps(morceau).encode() + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8007)
    ap.add_argument("--journal", default="temoin.jsonl")
    ap.add_argument("--modele", default="temoin")
    a = ap.parse_args()
    Temoin.journal = os.path.abspath(a.journal)
    Temoin.modele = a.modele
    print("temoin sur http://127.0.0.1:%d/v1  ->  %s" % (a.port, Temoin.journal))
    print("aucun modele charge, aucun credit consomme, le 4090 n'est pas touche.")
    sys.stdout.flush()
    ThreadingHTTPServer(("127.0.0.1", a.port), Temoin).serve_forever()


if __name__ == "__main__":
    main()
