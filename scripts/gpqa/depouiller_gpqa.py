#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Depouillement d'un ou plusieurs runs GPQA Diamond produits par gpqa_diamond.py.

    python depouiller_gpqa.py local.jsonl [f16.jsonl ...]

Ce que ce fichier refuse de faire, et pourquoi :

* Il ne donne PAS un sigma binomial sur les 792 tirages. Les 4 rotations d'une
  meme question ne sont pas independantes : une question que le modele ne sait
  pas rater 4 fois. Traiter 792 tirages correles comme 792 tirages
  independants divise l'erreur affichee par ~2 et fabrique une precision qui
  n'existe pas. L'erreur publiee ici est GROUPEE PAR QUESTION (ecart-type des
  198 moyennes par question / racine(198)) -- c'est celle qui compte pour dire
  si deux runs different.

* Il compte les NON-PARSE et les reponses TRONQUEES a part, jamais comme des
  fautes silencieuses. Un modele qui deborde son budget de reflexion echoue
  pour une raison qui n'est pas son raisonnement, et ca doit se voir.

* La table par POSITION est un controle, pas un ornement : avec les 4
  rotations, un modele sans biais donne ~25 % de ses reponses a chaque lettre.
  Un ecart marque signale que le score mesure en partie une manie de format.

Compare deux runs : l'ecart et son erreur groupee sur les questions COMMUNES
(comparaison appariee -- la variance de difficulte des questions s'annule,
c'est nettement plus fin que de soustraire deux taux absolus).
"""
import collections
import io
import json
import math
import os
import sys


def charger(chemin):
    ok, err = [], 0
    with io.open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                d = json.loads(ligne)
            except Exception:
                continue
            if d.get("erreur"):
                err += 1
            else:
                ok.append(d)
    # une reprise peut redoubler un couple (id, rotation) : le dernier gagne
    uniq = {}
    for d in ok:
        uniq[(d.get("id"), d.get("rotation"))] = d
    return list(uniq.values()), err


def par_question(recs):
    q = collections.defaultdict(list)
    for d in recs:
        q[d["id"]].append(bool(d.get("juste")))
    return q


def moyenne_groupee(q):
    """Moyenne et erreur-type groupees par question.

    m = moyenne des moyennes par question ; se = ecart-type de ces moyennes
    sur racine(nombre de questions). Une question posee 4 fois pese autant
    qu'une question posee 1 fois -- c'est voulu : l'unite d'echantillonnage
    est la question, pas l'appel.
    """
    mo = [sum(v) / float(len(v)) for v in q.values()]
    n = len(mo)
    if n == 0:
        return 0.0, 0.0, 0
    m = sum(mo) / n
    if n < 2:
        return m, float("nan"), n
    var = sum((x - m) ** 2 for x in mo) / (n - 1)
    return m, math.sqrt(var / n), n


def quant(t, q):
    if not t:
        return float("nan")
    return sorted(t)[int(round(q * (len(t) - 1)))]


def rapport(chemin):
    recs, err = charger(chemin)
    if not recs:
        print("%s : aucun appel exploitable (%d erreurs)" % (chemin, err))
        return None
    modeles = sorted({d.get("modele", "?") for d in recs})
    q = par_question(recs)
    m, se, nq = moyenne_groupee(q)
    rots = sorted({d.get("rotation") for d in recs})
    complet = sum(1 for v in q.values() if len(v) == len(rots))

    non_parse = [d for d in recs if not d.get("donne")]
    tronques = [d for d in recs if d.get("finish_reason") == "length"]
    brut = sum(1 for d in recs if d.get("juste"))

    print("=" * 74)
    print("%s" % os.path.basename(chemin))
    print("  modele(s)   : %s" % ", ".join(modeles))
    print("  appels      : %d   erreurs reseau : %d" % (len(recs), err))
    print("  questions   : %d   dont completes sur %d rotations : %d"
          % (nq, len(rots), complet))
    print("")
    print("  EXACTITUDE  : %.1f %%   +/- %.1f pt (1 sigma, groupee par question)"
          % (100 * m, 100 * se))
    print("     brut par appel : %d/%d = %.1f %%   (a ne PAS utiliser pour"
          % (brut, len(recs), 100.0 * brut / len(recs)))
    print("     comparer : ignore la correlation entre rotations d'une question)")
    print("")
    print("  non parses  : %d (%.1f %%)   tronques (finish=length) : %d (%.1f %%)"
          % (len(non_parse), 100.0 * len(non_parse) / len(recs),
             len(tronques), 100.0 * len(tronques) / len(recs)))

    # --- biais de position ---------------------------------------------
    print("")
    print("  controle de position -- 4 rotations => ~25 %% attendus par lettre")
    donnees = collections.Counter(d.get("donne") for d in recs if d.get("donne"))
    tot = sum(donnees.values()) or 1
    print("     donnees   " + "  ".join(
        "%s %5.1f %%" % (L, 100.0 * donnees.get(L, 0) / tot) for L in "ABCD"))
    juste_pos = collections.defaultdict(lambda: [0, 0])
    for d in recs:
        c = juste_pos[d.get("attendu")]
        c[1] += 1
        c[0] += 1 if d.get("juste") else 0
    print("     exactes   " + "  ".join(
        "%s %5.1f %%" % (L, 100.0 * juste_pos[L][0] / juste_pos[L][1])
        if juste_pos[L][1] else "%s     -" % L for L in "ABCD"))

    # --- stabilite ------------------------------------------------------
    if len(rots) > 1:
        print("")
        print("  stabilite -- une question sue est sue dans les 4 positions")
        d4 = collections.Counter(sum(v) for v in q.values() if len(v) == len(rots))
        for k in range(len(rots), -1, -1):
            if d4.get(k):
                print("     %d/%d bonnes : %3d questions" % (k, len(rots), d4[k]))
        stables = d4.get(len(rots), 0) + d4.get(0, 0)
        if complet:
            print("     stables (tout juste ou tout faux) : %d/%d = %.1f %%"
                  % (stables, complet, 100.0 * stables / complet))

    # --- domaines -------------------------------------------------------
    dom = collections.defaultdict(list)
    for d in recs:
        dom[d.get("domaine", "?")].append(bool(d.get("juste")))
    if len(dom) > 1:
        print("")
        print("  %-40s %6s %8s" % ("domaine", "n", "exact"))
        for k in sorted(dom, key=lambda z: -len(dom[z]))[:12]:
            v = dom[k]
            print("  %-40s %6d %7.1f %%"
                  % (k[:40], len(v), 100.0 * sum(v) / len(v)))

    # --- cout -----------------------------------------------------------
    sec = [d["secondes"] for d in recs if d.get("secondes")]
    tok = [d["tokens_sortie"] for d in recs if d.get("tokens_sortie")]
    if sec:
        print("")
        print("  secondes/appel : moy %.0f  med %.0f  q90 %.0f   TOTAL %.2f h"
              % (sum(sec) / len(sec), quant(sec, 0.5), quant(sec, 0.9),
                 sum(sec) / 3600.0))
    if tok:
        print("  tokens sortie  : moy %.0f  med %.0f  q90 %.0f  max %d"
              % (sum(tok) / len(tok), quant(tok, 0.5), quant(tok, 0.9),
                 max(tok)))
    return q


def comparer(a, qa, b, qb):
    communs = sorted(set(qa) & set(qb))
    if not communs:
        print("\naucune question commune : pas de comparaison.")
        return
    diffs = []
    for k in communs:
        ma = sum(qa[k]) / float(len(qa[k]))
        mb = sum(qb[k]) / float(len(qb[k]))
        diffs.append(ma - mb)
    n = len(diffs)
    d = sum(diffs) / n
    var = sum((x - d) ** 2 for x in diffs) / (n - 1) if n > 1 else float("nan")
    se = math.sqrt(var / n) if n > 1 else float("nan")
    print("")
    print("=" * 74)
    print("COMPARAISON APPARIEE sur %d questions communes" % n)
    print("  %s  moins  %s" % (os.path.basename(a), os.path.basename(b)))
    print("  ecart : %+.1f pt   +/- %.1f pt (1 sigma)" % (100 * d, 100 * se))
    if se == se and se > 0:
        z = d / se
        print("  z = %+.2f" % z)
        if abs(z) < 2:
            print("  |z| < 2 : l'ecart n'est PAS separable du bruit. Dire")
            print("  'equivalent a la precision de ce banc', pas 'egal'.")
        else:
            print("  |z| >= 2 : ecart separable du bruit sur cet echantillon.")
    mieux = sum(1 for x in diffs if x > 0)
    pire = sum(1 for x in diffs if x < 0)
    print("  questions ou le 1er fait mieux : %d   moins bien : %d   ex aequo : %d"
          % (mieux, pire, n - mieux - pire))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    qs = []
    for chemin in sys.argv[1:]:
        q = rapport(chemin)
        qs.append((chemin, q))
        print("")
    if len(qs) >= 2 and qs[0][1] and qs[1][1]:
        comparer(qs[0][0], qs[0][1], qs[1][0], qs[1][1])


if __name__ == "__main__":
    main()
