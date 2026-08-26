# DANS LES APPELS LLM : LE PREFILL OU LE DECODE ? -- ce qui plafonne le gain.
#
# CE QUI PRECEDE. ou_passe_le_temps.py a deja tranche « harnais ou LLM » : sur
# la sonde du 26/08, ~98 % de la paroi est DANS les appels. La plomberie est
# donc hors de cause, et la question descend d'un cran : dans ces appels, le
# temps part-il en re-lecture du contexte (prefill) ou en generation (decode) ?
#
# POURQUOI LA REPONSE DECIDE DE LA SUITE. Les deux corrections n'ont rien a voir.
#   prefill domine  -> le cache de prefixe est le levier ; epingler un
#                      fournisseur qui cache change tout.
#   decode domine   -> le cache ne peut RIEN rendre. L'agent parle trop, et
#                      c'est l'agent qu'il faut changer, pas le routage.
#
# COMMENT ON SEPARE SANS INSTRUMENTER L'AMONT. On n'a ni ttft ni compteur de
# prefill : seulement (entree, cache, sortie, ms) par appel. Mais ces triplets
# varient beaucoup d'un appel a l'autre -- de 8 k a 50 k d'entree, de 72 a
# 13 435 jetons de sortie -- et cette dispersion suffit a identifier les deux
# pentes par moindres carres SANS CONSTANTE :
#
#     ms = a * (entree - cache) + b * sortie
#
# a est le cout d'un jeton re-prefille, b celui d'un jeton genere. On soustrait
# `cache` parce qu'un jeton servi depuis le cache n'est pas prefille : c'est
# precisement ce qu'on cherche a chiffrer.
#
# CE QUI VALIDE OU INVALIDE L'AJUSTEMENT. Le RESIDU est publie. Deux parametres
# qui expliquent la paroi a quelques pourcents pres, c'est un modele ; a 30 %
# de residu, c'est un dessin, et le verdict ne doit pas etre lu. Aucune barre
# n'est desserree pour faire tenir le modele.
#
# LE CONTREFACTUEL, ET SA LIMITE. On rend l'economie qu'un cache PARFAIT
# donnerait : a * (part reutilisable du prefixe). C'est une BORNE HAUTE du gain
# atteignable par le routage -- aucun fournisseur ne sert 100 %, et la part
# reutilisable vient d'ou_casse_le_prefixe.py, qui mesure des CARACTERES la ou
# l'amont compte des jetons. Si cette borne haute est deja tres en dessous du
# facteur vise, la piste est close sans avoir a l'essayer.
#
# SEPARATION DES FILS. Comme ou_casse_le_prefixe.py : le journal melange
# l'agent (25 outils) et des appels auxiliaires (0 outil, 61 a 176 jetons).
# Les seconds sont trop courts pour porter une pente et fausseraient les deux.
#
#     python prefill_ou_decode.py <wire.jsonl> [--part-reutilisable 0.808]

import argparse
import io
import json
from collections import defaultdict


def lire(chemin, min_outils):
    """Les appels de l'agent, en (entree_froide, sortie, secondes, fournisseur)."""
    out = []
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        if d.get("kind") != "call" or d.get("status") != 200:
            continue
        s = d.get("sent") or {}
        if (s.get("n_tools") or 0) < min_outils:
            continue
        u = d.get("usage") or {}
        det = u.get("prompt_tokens_details") or {}
        cache = det.get("cached_tokens")
        if cache is None:
            cache = u.get("cache_read_input_tokens") or 0
        entree = u.get("prompt_tokens") or 0
        sortie = u.get("completion_tokens") or 0
        ms = d.get("ms") or 0
        if not entree or not ms:
            continue
        out.append((entree - cache, sortie, ms / 1000.0, cache, entree,
                    d.get("fournisseur") or "?"))
    return out


def ajuster(pts):
    """Moindres carres sans constante sur deux pentes. Rend (a, b) en s/jeton.

    Sans constante deliberement : une ordonnee a l'origine absorberait la
    latence reseau ET une part du prefill, et rendrait `a` ininterpretable sur
    un echantillon ou l'entree ne descend jamais pres de zero.
    """
    Saa = sum(x * x for x, y, t, _, _, _ in pts)
    Sab = sum(x * y for x, y, t, _, _, _ in pts)
    Sbb = sum(y * y for x, y, t, _, _, _ in pts)
    Sat = sum(x * t for x, y, t, _, _, _ in pts)
    Sbt = sum(y * t for x, y, t, _, _, _ in pts)
    det = Saa * Sbb - Sab * Sab
    if abs(det) < 1e-9:
        raise SystemExit("systeme degenere : entree et sortie varient ensemble.\n"
                         "  L'echantillon ne permet pas de separer les deux pentes.")
    return ((Sbb * Sat - Sab * Sbt) / det, (Saa * Sbt - Sab * Sat) / det)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("journal")
    p.add_argument("--min-outils", type=int, default=20,
                   help="en dessous, l'appel n'est pas celui de l'agent")
    p.add_argument("--part-reutilisable", type=float, default=None,
                   help="fraction du prefixe reutilisable (ou_casse_le_prefixe.py)")
    args = p.parse_args()

    pts = lire(args.journal, args.min_outils)
    if len(pts) < 4:
        raise SystemExit("%d appels de l'agent : trop peu pour ajuster deux "
                         "pentes." % len(pts))

    a, b = ajuster(pts)
    tt = sum(t for _, _, t, _, _, _ in pts)
    tp = sum(a * x for x, _, _, _, _, _ in pts)
    td = sum(b * y for _, y, _, _, _, _ in pts)
    froid = sum(x for x, _, _, _, _, _ in pts)
    cache = sum(c for _, _, _, c, _, _ in pts)
    entree = sum(e for _, _, _, _, e, _ in pts)
    sortie = sum(y for _, y, _, _, _, _ in pts)

    print("AJUSTEMENT  ms = a*(entree non cachee) + b*(sortie)   %d appels"
          % len(pts))
    if a > 0:
        print("  prefill : %8.3f ms/jeton    %7.0f jetons/s" % (1000 * a, 1 / a))
    else:
        print("  prefill : pente NEGATIVE (%.4f) -- l'ajustement ne tient pas." % a)
    if b > 0:
        print("  decode  : %8.3f ms/jeton    %7.1f jetons/s" % (1000 * b, 1 / b))
    else:
        print("  decode  : pente NEGATIVE (%.4f) -- l'ajustement ne tient pas." % b)

    res = tt - tp - td
    print()
    print("  paroi LLM mesuree  : %7.0f s" % tt)
    print("  attribue au PREFILL: %7.0f s   %5.1f %%" % (tp, 100.0 * tp / tt))
    print("  attribue au DECODE : %7.0f s   %5.1f %%" % (td, 100.0 * td / tt))
    print("  RESIDU             : %7.0f s   %5.1f %%%s"
          % (res, 100.0 * res / tt,
             "" if abs(res) < 0.10 * tt else "   <-- AU DELA DE 10 %, NE PAS LIRE LE VERDICT"))

    print()
    print("  entree %d jetons dont %d caches (%.1f %%)   sortie %d jetons"
          % (entree, cache, 100.0 * cache / entree if entree else 0, sortie))

    # Ce que le cache peut rendre, au mieux. Le calcul se fait sur le prefill
    # RESTANT (part froide) : ce qui est deja cache est deja gagne.
    part = args.part_reutilisable
    print()
    print("CONTREFACTUEL : et si le cache etait servi ?")
    if part is None:
        print("  --part-reutilisable non fourni. Bornes brutes :")
        print("    cache nul      -> le prefill coute %.0f s (%.1f %% de la paroi)"
              % (tp, 100.0 * tp / tt))
        print("    cache parfait  -> il en coute 0, soit -%.1f %% de paroi LLM"
              % (100.0 * tp / tt))
    else:
        gain = part * tp
        print("  part reutilisable du prefixe : %.1f %%  (mesuree, pas supposee)"
              % (100.0 * part))
        print("  BORNE HAUTE du gain par le cache : %.0f s sur %.0f s = %.1f %%"
              % (gain, tt, 100.0 * gain / tt))
        reste = tt - gain
        print("  paroi LLM au mieux : %.0f s, soit un facteur %.2fx seulement."
              % (reste, tt / reste if reste else 0))
        if gain < 0.5 * tt:
            print()
            print("  LECTURE : le cache ne peut pas rendre un facteur 2, donc il")
            print("  n'explique pas un rapport de l'ordre de 7. Ce qui reste est")
            print("  du DECODE -- le volume que l'agent genere, pas le routage.")

    # Le detail par fournisseur : c'est lui qui dit si le cache est une
    # propriete du fournisseur ou du hasard de routage a l'interieur d'un seul.
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for x, y, t, c, e, f in pts:
        g = agg[f]
        g[0] += 1
        g[1] += e
        g[2] += c
        g[3] += 1 if c else 0
    print()
    print("PAR FOURNISSEUR")
    print("  %-14s %-7s %-11s %-11s %-9s %s"
          % ("fournisseur", "appels", "entree", "cache", "% cache", "appels caches"))
    for f, g in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        print("  %-14s %-7d %-11d %-11d %-9.1f %d / %d"
              % (f, g[0], g[1], g[2], 100.0 * g[2] / g[1] if g[1] else 0, g[3], g[0]))
    print()
    print("  Un fournisseur qui cache sur une PARTIE de ses appels seulement ne")
    print("  refuse pas le cache : il route vers une autre replique. Le prefixe")
    print("  n'est alors pas en cause, et aucune correction cote client n'y peut")
    print("  rien -- seul l'epinglage, s'il existe pour ce fournisseur.")


main()
