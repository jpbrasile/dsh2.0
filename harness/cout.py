# -*- coding: utf-8 -*-
"""
cout.py -- le compteur de cout du harnais (README Phase 1 : "real prices, cache-hit visible").

    python harness/cout.py --ingerer FICHIER.jsonl [--campagne NOM]   ajoute les appels d'un fil au grand livre
    python harness/cout.py [--jour AAAA-MM-JJ] [--depuis AAAA-MM-JJ]  bilan : par jour, par modele, par campagne
    python harness/cout.py --csv                                      le grand livre en CSV sur stdout

Source de verite : le fil enregistre par scripts/bench_julia_effort/proxy.mjs (wire.jsonl), qui
contient la reponse `usage` d'OpenRouter telle quelle : `cost` en USD (prix REEL facture, pas un
tarif relu du catalogue), `prompt_tokens`, `completion_tokens`,
`prompt_tokens_details.cached_tokens`, `cost_details.upstream_inference_cost`.

Grand livre : harness/_cout/grand_livre.jsonl (gitignore : des chiffres et des ids de modeles,
jamais de contenu). Cle de dedoublonnage = (t0, ms, servi, prompt_tokens) : ingerer deux fois le
meme fil n'ajoute rien.

Taux de cache = cached_tokens / prompt_tokens, sur les appels qui ont un `usage` ; on donne aussi
la part des appels sans `usage` (un 4xx, un flux coupe : pas de prix, compte en "non factures").

Ce qui n'est PAS compte : le trafic qui ne passe pas par l'enregistreur (route `openrouter`
directe du lanceur interactif, `openrouter-cheap` via openrouter_cheapest_proxy.mjs). Pour ces
routes, le releve reste https://openrouter.ai/activity. Limite ecrite dans docs/PHASE1.md.
"""
import argparse, collections, io, json, os, sys, time

ICI = os.path.dirname(os.path.abspath(__file__))
LIVRE = os.path.join(ICI, "_cout", "grand_livre.jsonl")


def jour_de(t0):
    """t0 = millisecondes epoch (proxy.mjs) ou secondes ; rend AAAA-MM-JJ local."""
    if t0 is None:
        return "?"
    t = float(t0)
    if t > 1e11:
        t /= 1000.0
    return time.strftime("%Y-%m-%d", time.localtime(t))


def aplatir(c, campagne):
    u = c.get("usage") or {}
    d = u.get("prompt_tokens_details") or {}
    return {
        "t0": c.get("t0"), "jour": jour_de(c.get("t0")), "ms": c.get("ms"),
        "servi": c.get("servi") or (c.get("sent") or {}).get("model") or "?",
        "campagne": campagne,
        "status": c.get("status"),
        "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"),
        "cache": d.get("cached_tokens"), "cout": u.get("cost"),
        "amont": (u.get("cost_details") or {}).get("upstream_inference_cost"),
    }


def cle(r):
    return (r["t0"], r["ms"], r["servi"], r["in"])


def charger():
    if not os.path.exists(LIVRE):
        return []
    return [json.loads(l) for l in io.open(LIVRE, encoding="utf-8") if l.strip()]


def ingerer(fichier, campagne):
    """Rend (ajoutes, total, ignores) ; `ignores` = une ligne par doublon NON ecrit, marquee
    DIVERGENT si son cout differe de la ligne deja au livre (red team 1-done : le premier
    ecrit gagnait en silence)."""
    livre = charger()
    vues = {cle(r): r for r in livre}
    ajoutes, ignores = 0, []
    os.makedirs(os.path.dirname(LIVRE), exist_ok=True)
    with io.open(LIVRE, "a", encoding="utf-8", newline="\n") as f:
        for l in io.open(fichier, encoding="utf-8"):
            if not l.strip():
                continue
            r = aplatir(json.loads(l), campagne)
            k = cle(r)
            if k in vues:
                d = vues[k]
                ignores.append("doublon %s%s" % (k, " DIVERGENT cout %s != %s au livre" % (r.get("cout"), d.get("cout"))
                                                    if r.get("cout") != d.get("cout") else ""))
                continue
            vues[k] = r
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            ajoutes += 1
    return ajoutes, len(livre) + ajoutes, ignores


def bilan(livre, jour=None, depuis=None):
    rows = [r for r in livre if (not jour or r["jour"] == jour) and (not depuis or r["jour"] >= depuis)]
    if not rows:
        print("grand livre : aucun appel%s" % ((" le " + jour) if jour else ""))
        return
    def agg(par):
        g = collections.OrderedDict()
        for r in sorted(rows, key=lambda r: (r["jour"], r["t0"] or 0)):
            k = r[par]
            a = g.setdefault(k, {"appels": 0, "factures": 0, "in": 0, "out": 0, "cache": 0, "cout": 0.0})
            a["appels"] += 1
            if r["cout"] is not None:
                a["factures"] += 1
                a["in"] += r["in"] or 0
                a["out"] += r["out"] or 0
                a["cache"] += r["cache"] or 0
                a["cout"] += float(r["cout"])
        return g
    for titre, par in (("par jour", "jour"), ("par modele", "servi"), ("par campagne", "campagne")):
        print("== %s" % titre)
        print("  %-44s %6s %6s %10s %9s %7s %10s" % ("", "appels", "factu.", "tokens in", "out", "cache%", "USD"))
        for k, a in agg(par).items():
            pc = (100.0 * a["cache"] / a["in"]) if a["in"] else 0.0
            print("  %-44s %6d %6d %10d %9d %6.1f%% %10.4f" % (str(k)[:44], a["appels"], a["factures"], a["in"], a["out"], pc, a["cout"]))
    tot = agg("campagne")
    n = sum(a["appels"] for a in tot.values()); f = sum(a["factures"] for a in tot.values())
    i = sum(a["in"] for a in tot.values()); ca = sum(a["cache"] for a in tot.values()); usd = sum(a["cout"] for a in tot.values())
    print("TOTAL : %d appels (%d factures, %d sans usage) ; %d tokens d'entree dont %.1f%% servis par le cache ; %.4f USD" % (
        n, f, n - f, i, (100.0 * ca / i) if i else 0.0, usd))


def main(argv):
    global LIVRE
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingerer")
    ap.add_argument("--campagne", default="")
    ap.add_argument("--jour")
    ap.add_argument("--depuis")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--livre", default=LIVRE)
    A = ap.parse_args(argv)
    LIVRE = A.livre
    if A.ingerer:
        n, total, ign = ingerer(A.ingerer, A.campagne or os.path.basename(os.path.dirname(os.path.abspath(A.ingerer))))
        print("grand livre : +%d appel(s) (%d au total), %d doublon(s) ignore(s) <- %s" % (n, total, len(ign), A.ingerer))
        for x in ign:
            print("  ", x)
        return 1 if any("DIVERGENT" in x for x in ign) else 0
    livre = charger()
    if A.csv:
        cols = ["jour", "t0", "ms", "servi", "campagne", "status", "in", "out", "cache", "cout", "amont"]
        print(",".join(cols))
        for r in livre:
            print(",".join("" if r.get(c) is None else str(r[c]) for c in cols))
        return 0
    bilan(livre, A.jour, A.depuis)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
