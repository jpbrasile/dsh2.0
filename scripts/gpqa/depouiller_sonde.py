# -*- coding: utf-8 -*-
"""Depouillement de la sonde de memorisation. Aucun appel reseau.

CE QUI EST MESURE, ET POURQUOI C'EST L'ECART QUI COMPTE

Chaque exercice est joue deux fois sur LE MEME fichier de test :

  A. REEL     : le prefixe tel quel -- le modele peut reconnaitre l'exercice.
  B. ANONYME  : structure, valeurs et difficulte identiques, mais toute graphie
                du nom remplacee par un neutre de meme style. Seule l'ETIQUETTE
                qui permettrait le rappel a disparu.

Un niveau absolu eleve sur A ne prouve rien : les fichiers de test se
ressemblent, et beaucoup se complete par syntaxe. C'est la DIFFERENCE APPARIEE
A - B, exercice par exercice, qui isole ce que l'identite apporte.

  A >> B  -> le modele s'appuie sur l'identite de l'exercice : RAPPEL.
  A ~= B  -> il complete de la syntaxe : pas de preuve de memorisation.

DEUX GARDE-FOUS, tous deux appris a la dure

1. Les appels NON MESURES (sortie vide, erreur) sont EXCLUS et comptes a part.
   Le 26/08, 59 appels sur 60 avaient rendu un contenu vide -- tout le budget
   parti dans le bloc de pensee. Les compter comme "similarite 0" aurait
   produit un "A = B = 0, aucune memorisation" entierement fabrique. Un
   exercice n'entre dans l'analyse appariee que si SES DEUX bras sont mesures.

2. On rapporte deux metriques et jamais une seule. La similarite floue se
   discute -- un fichier de test ressemble a un autre. Le RAPPEL DE LIGNES
   EXACTES (lignes non triviales de la vraie suite restituees mot pour mot)
   est le chiffre difficile a expliquer autrement que par la memorisation.
"""
import argparse
import io
import json
import math
import sys


def mediane(v):
    if not v:
        return float("nan")
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def moyenne_et_erreur(v):
    """Moyenne et erreur-type. Rend (nan, nan) sous 2 points : sans variance
    estimable, publier une barre serait inventer une precision."""
    n = len(v)
    if n < 2:
        return (v[0] if v else float("nan")), float("nan")
    m = sum(v) / n
    var = sum((x - m) ** 2 for x in v) / (n - 1)
    return m, math.sqrt(var / n)


def signe(diffs, seuil=1e-9):
    plus = sum(1 for d in diffs if d > seuil)
    moins = sum(1 for d in diffs if d < -seuil)
    return plus, moins, len(diffs) - plus - moins


def bloc(titre, paires, cle):
    """Une metrique : niveaux des deux bras, puis l'ecart apparie."""
    a = [p["reel"][cle] for p in paires]
    b = [p["anonyme"][cle] for p in paires]
    d = [x - y for x, y in zip(a, b)]
    m, se = moyenne_et_erreur(d)
    plus, moins, nuls = signe(d)
    print("  %s" % titre)
    print("    bras A (reel)     mediane %5.1f %%   moyenne %5.1f %%"
          % (100 * mediane(a), 100 * (sum(a) / len(a))))
    print("    bras B (anonyme)  mediane %5.1f %%   moyenne %5.1f %%"
          % (100 * mediane(b), 100 * (sum(b) / len(b))))
    if se == se:   # non-nan
        print("    ECART A-B apparie : %+.1f pt +/- %.1f (1 sigma)   z = %+.2f"
              % (100 * m, 100 * se, m / se if se else float("nan")))
    else:
        print("    ECART A-B apparie : %+.1f pt (barre non estimable, n < 2)"
              % (100 * m))
    print("    signe de l'ecart  : A>B %d   A<B %d   egaux %d   (mediane %+.1f pt)"
          % (plus, moins, nuls, 100 * mediane(d)))
    return m, se, d


def main():
    p = argparse.ArgumentParser()
    p.add_argument("journal", nargs="?", default="sonde_memo_v2.jsonl")
    p.add_argument("--top", type=int, default=8,
                   help="exercices les mieux restitues a lister")
    args = p.parse_args()

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)

    lignes = [json.loads(l) for l in io.open(args.journal, encoding="utf-8")
              if l.strip()]
    par_ex = {}
    exclus_err, exclus_vide = [], []
    for d in lignes:
        cle = (d["lang"], d["ex"])
        if "erreur" in d:
            exclus_err.append(cle + (d["bras"],))
            continue
        if "non_mesure" in d:
            exclus_vide.append(cle + (d["bras"], d["non_mesure"]))
            continue
        par_ex.setdefault(cle, {})[d["bras"]] = d

    complets = {k: v for k, v in par_ex.items()
                if "reel" in v and "anonyme" in v}
    orphelins = [k for k in par_ex if k not in complets]

    print("journal : %s   %d appels" % (args.journal, len(lignes)))
    print("NON MESURES  : %d erreurs, %d sorties vides"
          % (len(exclus_err), len(exclus_vide)))
    for x in exclus_vide[:5]:
        print("     vide : %s/%s %s -- %s" % x)
    if len(exclus_vide) > 5:
        print("     ... et %d autres" % (len(exclus_vide) - 5))
    print("exercices avec UN SEUL bras mesure (ecartes) : %d" % len(orphelins))
    print("exercices APPARIES retenus : %d" % len(complets))
    print("")

    if not complets:
        print("AUCUNE PAIRE COMPLETE -- rien a conclure. La sonde n'a pas")
        print("mesure ; ne pas presenter cela comme une absence de rappel.")
        raise SystemExit(2)

    paires = [{"lang": k[0], "ex": k[1], "reel": v["reel"],
               "anonyme": v["anonyme"]} for k, v in sorted(complets.items())]

    print("=== 1. RAPPEL DE LIGNES EXACTES (le chiffre qui compte) ===")
    m_r, se_r, d_r = bloc("lignes de la vraie suite restituees mot pour mot",
                          paires, "rappel_lignes")
    print("")
    print("=== 2. SIMILARITE FLOUE (indicatif) ===")
    m_s, se_s, _ = bloc("similarite au texte reel, blancs et commentaires "
                        "retires", paires, "similarite")
    print("")

    print("=== 3. PAR LANGAGE (rappel de lignes exactes) ===")
    langs = sorted(set(p["lang"] for p in paires))
    print("    %-12s %4s   %8s %8s   %8s" % ("langage", "n", "A reel",
                                             "B anon", "ecart"))
    for lg in langs:
        sub = [p for p in paires if p["lang"] == lg]
        a = [x["reel"]["rappel_lignes"] for x in sub]
        b = [x["anonyme"]["rappel_lignes"] for x in sub]
        print("    %-12s %4d   %7.1f %% %7.1f %%   %+7.1f pt"
              % (lg, len(sub), 100 * mediane(a), 100 * mediane(b),
                 100 * (mediane(a) - mediane(b))))
    print("")

    print("=== 4. EXERCICES LES MIEUX RESTITUES sur le bras REEL ===")
    print("    (candidats a la memorisation individuelle : si l'un d'eux est")
    print("     dans le lot de TEST, c'est actionnable exercice par exercice)")
    tri = sorted(paires, key=lambda p: -p["reel"]["rappel_lignes"])
    print("    %-12s %-24s %8s %8s %8s" % ("langage", "exercice", "A reel",
                                           "B anon", "ecart"))
    for p_ in tri[:args.top]:
        ra, rb = p_["reel"]["rappel_lignes"], p_["anonyme"]["rappel_lignes"]
        print("    %-12s %-24s %7.1f %% %7.1f %% %+7.1f pt"
              % (p_["lang"], p_["ex"][:24], 100 * ra, 100 * rb,
                 100 * (ra - rb)))
    print("")

    print("=== LECTURE ===")
    if se_r != se_r:
        print("  n trop faible pour une barre : ne rien conclure.")
        return
    z = m_r / se_r if se_r else 0.0
    print("  Ecart A-B sur le rappel exact : %+.1f pt +/- %.1f, z = %+.2f"
          % (100 * m_r, 100 * se_r, z))
    if z >= 2:
        print("  A >> B : connaitre l'identite de l'exercice AIDE de facon")
        print("  mesurable. C'est du RAPPEL. Le corpus est contamine ; les")
        print("  exercices du bloc 4 sont a examiner un par un.")
    elif z <= -2:
        print("  B >> A : resultat inattendu -- l'anonymisation AIDE. Suspecter")
        print("  un artefact de substitution avant toute interpretation.")
    else:
        print("  |z| < 2 : aucun ecart detectable A LA PRECISION DE CETTE SONDE")
        print("  (n = %d paires). Le modele complete de la SYNTAXE, pas un"
              % len(paires))
        print("  souvenir de l'exercice nomme.")
        print("  A dire ainsi -- 'pas de preuve de memorisation', jamais")
        print("  'preuve d'absence de memorisation'. Une sonde de %d paires ne"
              % len(paires))
        print("  peut pas exclure un rappel de quelques points.")
    niv = 100 * mediane([p["reel"]["rappel_lignes"] for p in paires])
    print("")
    print("  RESERVE, a porter avec le resultat : le NIVEAU du bras A est de")
    print("  %.1f %% de lignes exactes. Meme sans ecart A-B, un niveau eleve" % niv)
    print("  signifie que ces fichiers de test sont largement previsibles --")
    print("  par memorisation diffuse ou par convention, la sonde ne separe")
    print("  pas les deux. Elle repond a UNE question : l'identite aide-t-elle.")


if __name__ == "__main__":
    main()
