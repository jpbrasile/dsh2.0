"""Banc QUALITE des configs KV -- etage 1 : differentiel + rappel long.

Pourquoi ce banc : la vitesse des configs KV quantifiees est mesuree
(rapport 7bis) mais leur qualite ne l'est que par sources externes
(#23470, Qwen2.5-7B a ctx 512). Ce banc mesure NOTRE modele, aux
profondeurs qui nous servent (60k-190k), sur la MEME chaine.

Deux modes de mesure + un mode de comparaison :

  --mode diff    : generation greedy deterministe a des profondeurs fixes ;
                   le texte genere est sauve en JSON. Compare ensuite avec
                   --mode score (reference = arm f16). Metrique : jetons
                   identiques en prefixe + taux de correspondance
                   positionnelle (via /tokenize du serveur).
  --mode needle  : 5 codes plantes a 5/25/50/75/95 pour cent de la
                   profondeur ; UNE generation demande les cinq ;
                   score = codes exacts retrouves / 5. Verite terrain
                   objective, fonctionne au-dela du plafond f16 (la ou
                   il n'existe PAS de reference differentielle).
  --mode score   : compare deux JSON de --mode diff (ref puis candidat).

Discipline heritee de bench_llama_ctx.py : refus hors-bornes AVANT tir
(un 400 serveur serait attribue au serveur), calibrage par /tokenize
(jamais d'extrapolation de ratio), greedy temperature 0.0,
cache_prompt False, --selftest known-BAD.

Usage :
  python scripts/bench_kv_quality.py --mode diff   --label f16 --depths 500,14000,60000 --out diff_f16.json
  python scripts/bench_kv_quality.py --mode needle --label q8q8 --depth 120000 --out needle_q8q8_120k.json
  python scripts/bench_kv_quality.py --mode score  --ref diff_f16.json --cand diff_q8q8.json
  python scripts/bench_kv_quality.py --selftest
"""
import argparse
import json
import sys

from bench_llama_ctx import (HorsBornes, MARGE, _post, calibrer, filler,
                             jetons, props)

# Codes deterministes (PAS de random : reproductibilite inter-configs).
NOMS = ("alpha", "bravo", "charlie", "delta", "echo")
FRACTIONS = (0.05, 0.25, 0.50, 0.75, 0.95)


def codes_pour(profondeur):
    """5 codes a 4 chiffres, deterministes, dependant de la profondeur
    (deux bancs a profondeurs differentes ne partagent pas leurs codes :
    un cache ou un log de l'un ne peut pas faire reussir l'autre)."""
    return [1000 + (profondeur // 1000 + 137 * i + 31 * i * i) % 9000
            for i in range(5)]


def garde(etiquette, cible, n_predict, n_ctx):
    if cible + n_predict + MARGE > n_ctx:
        raise HorsBornes(
            "%s : %d vises + %d generes + %d marge > n_ctx=%d"
            % (etiquette, cible, n_predict, MARGE, n_ctx))


def prompt_diff(n_mots):
    """Prompt deterministe : la generation greedy qui suit ne depend que
    du modele et de la config KV -- c'est l'objet mesure."""
    return ("Voici un journal technique.\n" + filler(n_mots) +
            "\nFin du journal. Redige un paragraphe qui decrit la structure"
            " de ce journal, puis propose trois ameliorations numerotees.")


def prompt_needle(n_mots, profondeur):
    codes = codes_pour(profondeur)
    mots = filler(n_mots).split(" ")
    for i, frac in enumerate(FRACTIONS):
        pos = min(len(mots) - 1, int(frac * len(mots)))
        mots[pos] = ("Note importante: le code secret %s est %d."
                     % (NOMS[i], codes[i]))
    texte = ("Voici un journal technique contenant cinq codes secrets.\n" +
             " ".join(mots) +
             "\nFin du journal. Donne les cinq codes secrets dans l'ordre"
             " alpha, bravo, charlie, delta, echo, un par ligne.")
    return texte, codes


def tirer(base, prompt, n_predict):
    out = _post(base, "/completion", {
        "prompt": prompt, "n_predict": n_predict,
        "temperature": 0.0, "cache_prompt": False,
    }, 3600)
    return out


def mode_diff(base, a, n_ctx):
    resultats = []
    for cible in [int(x) for x in a.depths.split(",") if x.strip()]:
        etiquette = "~%dk" % round(cible / 1000.0) if cible >= 1000 else "~%d" % cible
        garde(etiquette, cible, a.n_predict, n_ctx)
        mots, _ = calibrer(base, cible)
        out = tirer(base, prompt_diff(mots), a.n_predict)
        t = out["timings"]
        print("%-8s n_past=%-7d genere=%4d jetons  decode=%6.2f t/s"
              % (etiquette, out.get("tokens_evaluated", -1),
                 t["predicted_n"], t["predicted_per_second"]))
        sys.stdout.flush()
        resultats.append({"cible": cible, "n_mots": mots,
                          "n_past": out.get("tokens_evaluated", -1),
                          "contenu": out.get("content", ""),
                          "predicted_n": t["predicted_n"]})
    return {"label": a.label, "mode": "diff", "n_predict": a.n_predict,
            "points": resultats}


def mode_needle(base, a, n_ctx):
    """n_predict genereux (512 conseille) : le modele pense en <think>
    avant de lister -- 128 jetons ont fait rater delta/echo a la
    REFERENCE f16 le 25/08 (budget, pas rappel). Le score ne vaut que
    compare a la reference tiree avec le MEME budget."""
    cible = a.depth
    garde("needle~%dk" % (cible // 1000), cible, a.n_predict, n_ctx)
    mots, _ = calibrer(base, cible)
    prompt, codes = prompt_needle(mots, cible)
    out = tirer(base, prompt, a.n_predict)
    reponse = out.get("content", "")
    trouves = [c for c in codes if str(c) in reponse]
    print("needle ~%dk : n_past=%d  score=%d/5  codes=%s  trouves=%s"
          % (cible // 1000, out.get("tokens_evaluated", -1),
             len(trouves), codes, trouves))
    sys.stdout.flush()
    return {"label": a.label, "mode": "needle", "cible": cible,
            "n_past": out.get("tokens_evaluated", -1), "codes": codes,
            "trouves": trouves, "score": len(trouves),
            "reponse": reponse}


def mode_score(base, a):
    """Compare deux JSON --mode diff. Le tokenizer du SERVEUR en cours
    sert d'arbitre (meme modele pour toutes les configs)."""
    ref = json.load(open(a.ref, encoding="utf-8"))
    cand = json.load(open(a.cand, encoding="utf-8"))
    print("score %s (ref) vs %s (cand)" % (ref["label"], cand["label"]))
    for pr, pc in zip(ref["points"], cand["points"]):
        if pr["cible"] != pc["cible"] or pr["n_mots"] != pc["n_mots"]:
            print("  ~%dk : NON COMPARABLE (cible ou n_mots differents)"
                  % (pr["cible"] // 1000))
            continue
        tr = _post(base, "/tokenize", {"content": pr["contenu"]}, 300)["tokens"]
        tc = _post(base, "/tokenize", {"content": pc["contenu"]}, 300)["tokens"]
        prefixe = 0
        for x, y in zip(tr, tc):
            if x != y:
                break
            prefixe += 1
        n = max(len(tr), len(tc), 1)
        pareils = sum(1 for x, y in zip(tr, tc) if x == y)
        print("  cible ~%-5dk : prefixe identique %4d jetons  "
              "correspondance %5.1f%%  (ref %d, cand %d jetons)"
              % (pr["cible"] // 1000, prefixe, 100.0 * pareils / n,
                 len(tr), len(tc)))
    return 0


def selftest():
    """Known-BAD sans serveur : la garde refuse, les codes sont plantes."""
    try:
        garde("KNOWN-BAD", 70000, 256, 65536)
    except HorsBornes:
        print("OK : hors-bornes refuse avant tir")
    else:
        print("ECHEC : la garde n'a pas tire")
        return 1
    prompt, codes = prompt_needle(1000, 60000)
    absents = [c for c in codes if str(c) not in prompt]
    if absents:
        print("ECHEC : codes absents du prompt : %s" % absents)
        return 1
    if codes_pour(60000) == codes_pour(120000):
        print("ECHEC : codes identiques entre profondeurs")
        return 1
    print("OK : 5 codes plantes, codes distincts par profondeur")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8005")
    p.add_argument("--mode", choices=["diff", "needle", "score"])
    p.add_argument("--label", default="?")
    p.add_argument("--depths", default="500,14000,60000")
    p.add_argument("--depth", type=int, default=60000)
    p.add_argument("--n-predict", type=int, default=256)
    p.add_argument("--out")
    p.add_argument("--ref")
    p.add_argument("--cand")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    base = a.base.rstrip("/")
    d = props(base)
    n_ctx = d["default_generation_settings"]["n_ctx"]
    print("serveur : %s  build=%s  n_ctx=%d"
          % (d.get("model_alias"), d.get("build_info"), n_ctx))
    if a.mode == "score":
        return mode_score(base, a)
    try:
        res = mode_diff(base, a, n_ctx) if a.mode == "diff" \
            else mode_needle(base, a, n_ctx)
    except HorsBornes as e:
        print("REFUSE  %s" % e)
        return 1
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
