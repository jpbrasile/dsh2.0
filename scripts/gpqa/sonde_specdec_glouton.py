# LE DECODAGE SPECULATIF EST-IL SANS PERTE ? -- la dette declaree de la campagne.
#
# CE QUI EST AFFIRME AUJOURD'HUI. Que le specdec dflash2 ne change pas les
# sorties, seulement leur vitesse. C'est un COMMENTAIRE, pas une mesure :
# SPECDEC_4090_BENCH.md le dit lui-meme trois fois (`:18`, `:184`
# « 9/9 MISMATCH at temp 0.6 -- a affirmer en glouton », `:672`). Le fork en
# service porte de surcroit un « Revert draft sampling in rejection sampling »
# (`:588`) : le chemin d'echantillonnage du brouillon a bouge.
#
# POURQUOI EN GLOUTON, ET SEULEMENT EN GLOUTON. L'echantillonnage speculatif
# n'est mathematiquement equivalent qu'EN DISTRIBUTION : a temperature > 0, deux
# sorties differentes ne prouvent rien. En glouton (temperature 0, top_k 1) il
# n'y a plus de distribution -- une seule suite de jetons est correcte, et
# l'egalite devient verifiable octet par octet. C'est le seul regime ou la
# question a une reponse binaire.
#
# LE TEMOIN QUE LE PLAN N'AVAIT PAS. Une divergence entre les deux jambes ne
# prouve « specdec avec perte » que si le serveur est REPRODUCTIBLE. Sans
# controle, un serveur non deterministe (lot, cache de prompt, ordre de
# reduction flottante) produit exactement le meme symptome. La jambe specdec
# est donc jouee DEUX FOIS : B1 contre B2 mesure le bruit de l'instrument, et
# c'est seulement si B1 == B2 que A1 != B1 accuse le specdec.
#
#   verdict possible 1 : B1 != B2                -> instrument non reproductible,
#                                                   la question reste ouverte
#   verdict possible 2 : B1 == B2 et A1 == B1    -> sans perte en glouton
#   verdict possible 3 : B1 == B2 et A1 != B1    -> le specdec change la sortie
#
# Aucun de ces trois verdicts n'est un echec du banc. Le troisieme est meme le
# plus utile : il retire le specdec de toute configuration qui produit un
# chiffre d'exactitude.
#
# LE PROMPT VIENT DE gpqa_diamond.py PAR IMPORT, jamais par recopie : un gabarit
# duplique derive en silence, et la sonde comparerait alors deux choses qu'elle
# croit identiques.
#
#     python sonde_specdec_glouton.py <sortie.jsonl> [--questions 12]
#
# Les deux jambes N'ONT PAS BESOIN de tourner sur le meme serveur -- c'est tout
# l'objet. Elles ont besoin du meme prompt, des memes parametres et du meme
# ordre. Comparaison : `python sonde_specdec_glouton.py --comparer a.jsonl b.jsonl`.

import argparse
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gpqa_diamond as G


def jouer(args):
    items = G.lire_csv(args.csv)[:args.questions]
    if not items:
        raise SystemExit("aucune question lue dans %s" % args.csv)

    # Rotation 0 partout : la sonde ne mesure pas l'exactitude, elle mesure
    # l'egalite de deux sorties. Faire varier la permutation n'ajouterait que
    # du bruit a comparer.
    extra = {"top_k": 1, "min_p": 0.0, "seed": args.graine}

    print("SONDE SPECDEC GLOUTON -- %d questions, rotation 0" % len(items))
    print("  url %s   modele %s" % (args.url, args.modele))
    print("  temperature %.1f  top_p %.1f  max_tokens %d  extra %s"
          % (args.temperature, args.top_p, args.max_tokens, extra))
    print("  sortie %s" % args.sortie)
    print()

    n_err = 0
    with io.open(args.sortie, "w", encoding="utf-8", newline="\n") as f:
        for i, item in enumerate(items, 1):
            rot = G.rotations(item, args.graine)[0]
            prompt = G.GABARIT.format(question=item["question"],
                                      a=rot["choix"][0], b=rot["choix"][1],
                                      c=rot["choix"][2], d=rot["choix"][3])
            enreg = {"rang": i, "id": item["id"], "rotation": rot["rotation"]}
            try:
                rep = G.interroger(args.url, None, args.modele, prompt,
                                   args.temperature, args.top_p,
                                   args.max_tokens, args.delai, extra)
                txt = rep["texte"] or ""
                # `raisonnement` est vide sous --reasoning-format none (la
                # pensee arrive dans le contenu), mais un serveur configure
                # autrement la mettrait la : on compare les DEUX, sinon une
                # divergence pourrait se cacher dans le champ non compare.
                enreg.update({
                    "texte": txt,
                    "raisonnement": rep.get("raisonnement") or "",
                    "finish_reason": rep.get("finish_reason"),
                    "tokens_sortie": rep.get("tokens_sortie"),
                    "secondes": round(rep.get("secondes") or 0.0, 2),
                })
                print("  %3d/%d  %-24s %6d tok  %6.1f s  %s"
                      % (i, len(items), item["id"][:24],
                         rep.get("tokens_sortie") or -1, rep.get("secondes") or 0,
                         rep.get("finish_reason")))
            except Exception as e:
                enreg["erreur"] = "%s: %s" % (type(e).__name__, str(e)[:300])
                n_err += 1
                print("  %3d/%d  ERREUR %s" % (i, len(items), enreg["erreur"]))
            f.write(json.dumps(enreg, ensure_ascii=False) + "\n")
            f.flush()

    print()
    print("appels %d   erreurs %d" % (len(items), n_err))
    if n_err:
        print("ATTENTION : une jambe avec erreur ne se compare pas -- rejouer.")
    return 1 if n_err else 0


def comparer(a, b):
    def lire(p):
        d = {}
        for l in io.open(p, encoding="utf-8", errors="replace"):
            l = l.strip()
            if not l:
                continue
            x = json.loads(l)
            d[x["rang"]] = x
        return d

    A, B = lire(a), lire(b)
    communs = sorted(set(A) & set(B))
    print("=" * 70)
    print("A : %s   (%d appels)" % (a, len(A)))
    print("B : %s   (%d appels)" % (b, len(B)))
    print("rangs communs : %d" % len(communs))
    if len(A) != len(B) or len(communs) != len(A):
        print("ATTENTION : les deux jambes n'ont pas le meme contenu.")
    print()

    ident, diff, err = 0, [], 0
    for r in communs:
        x, y = A[r], B[r]
        if x.get("erreur") or y.get("erreur"):
            err += 1
            continue
        sx = (x.get("texte") or "") + "\x00" + (x.get("raisonnement") or "")
        sy = (y.get("texte") or "") + "\x00" + (y.get("raisonnement") or "")
        if sx == sy:
            ident += 1
        else:
            # Premier octet qui differe : dit si la divergence est immediate
            # ou tardive. Une divergence tardive est le signe d'une derive
            # numerique, une divergence des le premier jeton celui d'un
            # chemin de code different.
            k = 0
            while k < min(len(sx), len(sy)) and sx[k] == sy[k]:
                k += 1
            diff.append((r, x.get("id"), k, len(sx), len(sy)))

    n = ident + len(diff)
    print("appels compares   : %d   (erreurs ecartees : %d)" % (n, err))
    print("IDENTIQUES octet a octet : %d / %d" % (ident, n))
    if diff:
        print("DIVERGENTS               : %d" % len(diff))
        print()
        print("  %-5s %-26s %10s %9s %9s" % ("rang", "id", "1er ecart", "len A", "len B"))
        for r, i, k, la, lb in diff[:20]:
            print("  %-5d %-26s %10d %9d %9d" % (r, (i or "")[:26], k, la, lb))
        if len(diff) > 20:
            print("  ... %d autres" % (len(diff) - 20))
    print()
    if not n:
        print("VERDICT : aucun appel comparable.")
    elif not diff:
        print("VERDICT : les deux jambes sont IDENTIQUES octet a octet sur %d appels." % n)
    else:
        print("VERDICT : DIVERGENCE sur %d appels sur %d." % (len(diff), n))
    return 0 if (n and not diff) else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sortie", nargs="?")
    p.add_argument("--comparer", nargs=2, metavar=("A", "B"))
    p.add_argument("--csv", default="gpqa_diamond.csv")
    p.add_argument("--url", default="http://127.0.0.1:8005/v1")
    p.add_argument("--modele", default="specdec-q38-dflash2")
    p.add_argument("--questions", type=int, default=12)
    p.add_argument("--graine", type=int, default=1234)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--top-p", type=float, default=1.0)
    p.add_argument("--max-tokens", type=int, default=3072)
    p.add_argument("--delai", type=int, default=1800)
    args = p.parse_args()

    if args.comparer:
        sys.exit(comparer(args.comparer[0], args.comparer[1]))
    if not args.sortie:
        p.error("donner un fichier de sortie, ou --comparer A B")
    sys.exit(jouer(args))


main()
