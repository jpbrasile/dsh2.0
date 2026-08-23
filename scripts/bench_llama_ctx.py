"""Debit d'un llama-server EN FONCTION DE LA LONGUEUR DE CONTEXTE.

Pourquoi ce script existe plutot qu'un chrono cote client : llama-server rend
son propre bloc `timings` sur /completion. Le nombre vient de l'instrument.

Pourquoi il CALIBRE au lieu d'extrapoler (mesure du 21/08/2026, Qwen3.8-27B) :
le remplissage `bloc<N>` coute de plus en plus cher par mot a mesure que N
grandit -- 4,638 jeton/mot a 3 000 mots, 5,380 a 17 905. Extrapoler un point
haut sur le ratio d'un point bas a fait deborder n_ctx et rendu
`HTTP 400 Bad Request`, qui se lit exactement comme une limite du serveur.
C'etait un defaut du BANC. On mesure donc le ratio par /tokenize, puis on vise.

Et il REFUSE avant de tirer : un point dont le prompt + n_predict depasse le
n_ctx annonce par /props est arithmetiquement impossible, et son 400 serait
attribue au serveur. Bras known-BAD cable : --selftest demande un point
volontairement hors bornes et EXIGE le refus.

Usage :
    python scripts/bench_llama_ctx.py --base http://127.0.0.1:8005
    python scripts/bench_llama_ctx.py --points 500,14000,32000,64000,95000
    python scripts/bench_llama_ctx.py --selftest
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAUT_POINTS = (500, 14000, 32000, 64000, 95000)
MARGE = 512  # jetons de gabarit + arrondi de tokenisation


class HorsBornes(Exception):
    """Le point demande ne TIENT PAS dans n_ctx : refus avant tir."""


def _post(base, chemin, charge, timeout):
    body = json.dumps(charge).encode()
    req = urllib.request.Request(base + chemin, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def props(base):
    with urllib.request.urlopen(base + "/props", timeout=60) as r:
        return json.loads(r.read())


def jetons(base, texte):
    return len(_post(base, "/tokenize", {"content": texte}, 300)["tokens"])


def filler(n_mots):
    return " ".join("bloc%d" % i for i in range(n_mots))


def calibrer(base, cible, essais=6, tolerance=None):
    """Trouve le nombre de MOTS qui rend ~cible JETONS, en interrogeant le
    tokenizer du serveur. Rend (n_mots, n_jetons_mesures).

    La tolerance est RELATIVE : une tolerance absolue de 1500 jetons accepte du
    premier coup un point vise a 500 et atterri a 290 -- mesure, l'etiquette
    ~500 valait alors n_past=315. Une bande large sur un petit point ne mesure
    pas le point qu'elle nomme."""
    if tolerance is None:
        tolerance = max(20, min(1500, int(0.03 * cible)))
    mots = max(1, int(cible / 5.0))
    n = 0
    for _ in range(essais):
        n = jetons(base, filler(mots))
        print("    calibrage : %6d mots -> %6d jetons (%.3f jeton/mot)"
              % (mots, n, n / float(mots)))
        sys.stdout.flush()
        if abs(n - cible) < tolerance:
            break
        mots = max(1, int(mots * cible / float(n)))
    return mots, n


def mesurer(base, etiquette, cible, n_ctx, n_predict=120):
    """Un point. Refuse AVANT de tirer si le budget ne tient pas dans n_ctx."""
    if cible + n_predict + MARGE > n_ctx:
        raise HorsBornes(
            "%s : %d jetons vises + %d generes + %d de marge = %d > n_ctx=%d. "
            "Le serveur rendrait 400, et ce 400 serait MIEN, pas le sien."
            % (etiquette, cible, n_predict, MARGE,
               cible + n_predict + MARGE, n_ctx))
    mots, _ = calibrer(base, cible)
    prompt = ("Voici un journal technique.\n" + filler(mots) +
              "\nFin du journal. Reponds par une phrase: combien de blocs precedent?")
    out = _post(base, "/completion", {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.0,
        "cache_prompt": False,
    }, 3600)
    t = out["timings"]
    print("%-10s n_past=%-6d prefill=%8.1f t/s (%6d tok)  decode=%6.2f t/s (%4d tok)"
          % (etiquette, out.get("tokens_evaluated", -1),
             t["prompt_per_second"], t["prompt_n"],
             t["predicted_per_second"], t["predicted_n"]))
    sys.stdout.flush()
    return t


def selftest(base, n_ctx):
    """Bras known-BAD : un point hors bornes DOIT etre refuse ici, pas la-bas."""
    cible = n_ctx + 1
    print("  known-BAD : point a %d jetons pour n_ctx=%d -- refus attendu" % (cible, n_ctx))
    try:
        mesurer(base, "KNOWN-BAD", cible, n_ctx)
    except HorsBornes as e:
        print("  OK : refuse avant tir -- %s" % e)
        return 0
    print("  ECHEC : le point hors bornes est parti au serveur. Le garde ne garde rien.")
    return 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8005")
    p.add_argument("--points", default=",".join(str(x) for x in DEFAUT_POINTS),
                   help="cibles en JETONS, separees par des virgules")
    p.add_argument("--n-predict", type=int, default=120)
    p.add_argument("--selftest", action="store_true",
                   help="ne mesure rien : verifie que le refus hors-bornes tire")
    a = p.parse_args()
    base = a.base.rstrip("/")

    try:
        d = props(base)
    except urllib.error.URLError as e:
        print("ECHEC : /props injoignable sur %s (%s). Le serveur tourne-t-il ?" % (base, e))
        return 2
    n_ctx = d["default_generation_settings"]["n_ctx"]
    print("serveur : %s  build=%s  n_ctx=%d  vision=%s"
          % (d.get("model_alias"), d.get("build_info"), n_ctx,
             d.get("modalities", {}).get("vision")))

    if a.selftest:
        return selftest(base, n_ctx)

    code = 0
    for cible in [int(x) for x in a.points.split(",") if x.strip()]:
        etiquette = "~%dk" % round(cible / 1000.0) if cible >= 1000 else "~%d" % cible
        try:
            mesurer(base, etiquette, cible, n_ctx, a.n_predict)
        except HorsBornes as e:
            print("REFUSE  %s" % e)
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
