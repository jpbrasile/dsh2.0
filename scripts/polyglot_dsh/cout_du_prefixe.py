# QUE COUTE LE PREFIXE NON CACHE ? -- suite de ou_passe_le_temps.py
#
# ou_passe_le_temps.py a etabli que 85 % du temps de dsh est passe DANS les
# appels LLM : ce n'est pas de la plomberie. Mais « dans le LLM » ne veut pas
# dire « incompressible ». Un appel se decompose en deux :
#
#   PREFILL      lecture du prompt. Proportionnel aux jetons d'ENTREE, sauf
#                ceux qui sont deja en cache cote fournisseur -- ceux-la sont
#                relus beaucoup plus vite et factures beaucoup moins cher.
#   GENERATION   ecriture de la reponse. Proportionnelle aux jetons de SORTIE.
#                Celle-la, on ne l'evite pas.
#
# Le taux de cache est une propriete du HARNAIS, pas du modele : il tient a la
# stabilite du prefixe envoye. Un agent qui ajoute a la fin de la conversation
# garde son cache ; un agent qui reconstruit, reordonne, resume ou reinjecte
# quelque chose de variable en tete le casse a chaque appel et repaie le
# prefill au prix fort.
#
# CE QUE CETTE MESURE NE DIT PAS. Les coefficients viennent d'une regression
# sur des appels observes en production, pas d'un banc controle : la file du
# fournisseur, la longueur variable du raisonnement et la charge d'autres
# clients y sont melangees. Le R2 est publie a cote ; en dessous de ~0,5 les
# coefficients ne valent pas la peine d'etre cites. La contrefactuelle
# (« et si dsh avait le taux de cache de pi ») est une EXTRAPOLATION du
# modele lineaire, pas une mesure : elle suppose que seul le cache change.

import io
import json
import sys
import datetime

CHEMIN = sys.argv[1]
FENETRES = []
for a in sys.argv[2:]:
    nom, plage = a.split("=", 1)
    d, f = (plage.split(",") + [""])[:2]
    FENETRES.append((nom, d.strip(), f.strip()))


def hhmm(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M")


def cache_de(u):
    det = u.get("prompt_tokens_details") or {}
    return det.get("cached_tokens") or u.get("cache_read_input_tokens") or 0


def resoudre(A, b):
    """Moindres carres par equations normales, pivot partiel. n petit."""
    n = len(A[0])
    M = [[sum(A[k][i] * A[k][j] for k in range(len(A))) for j in range(n)]
         + [sum(A[k][i] * b[k] for k in range(len(A)))] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / M[c][c]
            for j in range(c, n + 1):
                M[r][j] -= f * M[c][j]
    return [M[i][n] / M[i][i] for i in range(n)]


v = [json.loads(l) for l in io.open(CHEMIN, encoding="utf-8") if l.strip()]
v = [d for d in v if d.get("kind") == "call" and d.get("status") == 200]
v.sort(key=lambda d: d["t0"])

profils = {}
for nom, deb, fin in FENETRES:
    sel = [d for d in v
           if (not deb or hhmm(d["t0"]) >= deb) and (not fin or hhmm(d["t0"]) < fin)]
    sel = [d for d in sel if (d.get("usage") or {}).get("prompt_tokens")]
    if len(sel) < 8:
        print("%-4s : %d appels exploitables -- trop peu pour une regression."
              % (nom, len(sel)))
        print()
        continue

    ent = sum(d["usage"]["prompt_tokens"] for d in sel)
    cac = sum(cache_de(d["usage"]) for d in sel)
    sor = sum(d["usage"].get("completion_tokens") or 0 for d in sel)
    rais = sum((d["usage"].get("completion_tokens_details") or {})
               .get("reasoning_tokens") or 0 for d in sel)
    cout = sum(d["usage"].get("cost") or 0 for d in sel)
    llm = sum(d["ms"] for d in sel) / 1000.0

    # ms = a*(entree non cachee) + b*(entree cachee) + c*(sortie) + d
    A = [[d["usage"]["prompt_tokens"] - cache_de(d["usage"]),
          cache_de(d["usage"]),
          d["usage"].get("completion_tokens") or 0,
          1.0] for d in sel]
    y = [d["ms"] / 1000.0 for d in sel]
    coef = resoudre(A, y)
    r2 = None
    if coef:
        pred = [sum(A[k][j] * coef[j] for j in range(4)) for k in range(len(A))]
        moy = sum(y) / len(y)
        sst = sum((t - moy) ** 2 for t in y)
        sse = sum((y[k] - pred[k]) ** 2 for k in range(len(y)))
        r2 = 1.0 - sse / sst if sst > 0 else None

    print("=== %s   %d appels, %s -> %s ==="
          % (nom, len(sel), hhmm(sel[0]["t0"]), hhmm(sel[-1]["t0"])))
    print("  entree      : %9d jetons   dont %d en cache = %.1f %%"
          % (ent, cac, 100.0 * cac / max(1, ent)))
    print("  entree PAYEE plein tarif (prefill a refaire) : %d" % (ent - cac))
    print("  sortie      : %9d jetons   dont %d de raisonnement (%.0f %%)"
          % (sor, rais, 100.0 * rais / max(1, sor)))
    print("  temps LLM   : %8.0f s        cout %.4f $" % (llm, cout))
    if coef and r2 is not None:
        a, b, c, cst = coef
        print("  regression  : R2 = %.2f" % r2)
        print("     prefill non cache : %7.2f s / 1000 jetons" % (a * 1000))
        print("     prefill cache     : %7.2f s / 1000 jetons" % (b * 1000))
        print("     generation        : %7.2f s / 1000 jetons" % (c * 1000))
        print("     constante         : %7.2f s / appel" % cst)
        # GARDE-FOU DE SIGNE. Un R2 eleve ne rend pas les coefficients
        # interpretables : ici la regression, tiree par la generation, rend un
        # cout NEGATIF au jeton cache. Du temps negatif n'existe pas -- c'est
        # de la colinearite (les appels a gros cache sont aussi ceux qui
        # generent peu). Publier l'imputation quand meme fabriquerait un
        # resultat. On refuse, et on le dit.
        negatifs = [n for n, x in (("prefill non cache", a),
                                   ("prefill cache", b),
                                   ("generation", c)) if x < 0]
        if r2 < 0.5:
            print("  R2 < 0,50 : imputation NON PUBLIEE, le modele n'explique pas assez.")
        elif negatifs:
            print("  IMPUTATION REFUSEE : coefficient NEGATIF sur %s."
                  % ", ".join(negatifs))
            print("     Du temps negatif n'existe pas. R2 %.2f eleve mais les" % r2)
            print("     regresseurs sont colineaires : seul le terme dominant")
            print("     est identifie, les autres absorbent du bruit de signe")
            print("     libre. Ne rien conclure sur le prefill par cette voie.")
        else:
            tp = a * (ent - cac) + b * cac
            tg = c * sor
            print("  IMPUTATION (modele, R2 %.2f) :" % r2)
            print("     prefill    %6.0f s = %2.0f %% du temps LLM"
                  % (tp, 100.0 * tp / max(1, llm)))
            print("     generation %6.0f s = %2.0f %%"
                  % (tg, 100.0 * tg / max(1, llm)))
    profils[nom] = {"ent": ent, "cac": cac, "sor": sor, "llm": llm,
                    "cout": cout, "coef": coef, "r2": r2, "n": len(sel)}
    print()

# Contrefactuelle : le lent adopte le taux de cache du rapide.
if len(profils) >= 2:
    noms = list(profils)
    lent = max(noms, key=lambda n: profils[n]["llm"])
    rapide = min(noms, key=lambda n: profils[n]["llm"])
    L, R = profils[lent], profils[rapide]
    tl = L["cac"] / max(1, L["ent"])
    tr = R["cac"] / max(1, R["ent"])
    print("CONTREFACTUELLE -- %s au taux de cache de %s (%.0f %% -> %.0f %%)"
          % (lent, rapide, 100 * tl, 100 * tr))
    if not L["coef"] or (L["r2"] or 0) < 0.5 or min(L["coef"][:3]) < 0:
        print("  REFUSEE : la regression de %s n'est pas exploitable" % lent)
        print("  (R2 %s, coefficient minimal %s). Une contrefactuelle batie"
              % ("n/a" if L["r2"] is None else "%.2f" % L["r2"],
                 "n/a" if not L["coef"] else "%.3f" % min(L["coef"][:3])))
        print("  sur un coefficient de signe faux serait un nombre invente.")
    elif tr <= tl:
        print("  sans objet : %s ne cache pas mieux." % rapide)
    else:
        a, b = L["coef"][0], L["coef"][1]
        avant = a * (L["ent"] - L["cac"]) + b * L["cac"]
        cac2 = L["ent"] * tr
        apres = a * (L["ent"] - cac2) + b * cac2
        print("  EXTRAPOLATION, pas une mesure : suppose que seul le cache change.")
        print("  prefill %.0f s -> %.0f s   soit %.0f s economises = %.0f %% du temps LLM"
              % (avant, apres, avant - apres,
                 100.0 * (avant - apres) / max(1, L["llm"])))
        print("  Le reste de l'ecart ne vient PAS du cache : il vient du nombre")
        print("  d'appels et de la taille de la conversation, qui sont des choix")
        print("  de l'agent, pas du harnais.")
