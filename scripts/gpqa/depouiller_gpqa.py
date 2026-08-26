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


# --- Regle 3, Revision 2 du 26/08/2026 ------------------------------------
# La regle 3 d'origine (« appel tronque = non-mesure, exclu et compte ») a ete
# ecrite avant que les bras a budget existent et confondait DEUX accidents qui
# n'ont rien de commun :
#
#   COUPURE AU BUDGET   le budget de raisonnement est epuise, le message de
#                       transition est injecte, ET LE MODELE REND UNE REPONSE.
#                       Mesure sur le bras 8192 : 7 justes sur 10, contre 25 %
#                       au hasard. C'est une MESURE -- d'une reponse degradee,
#                       c'est-a-dire du cout du budget, la chose meme qu'on
#                       mesure. L'exclure retire l'effet du traitement du bras
#                       traite ; sous rotation tournante, ou une question n'a
#                       qu'un appel, ca retire carrement la question du jeu
#                       apparie, et non au hasard : les questions dures brulent
#                       plus de pensee. Le biais efface le cout du petit budget.
#   TRONCATURE PLAFOND  finish_reason == "length" contre --max-tokens : la
#                       reponse est coupee en cours d'ecriture, il n'y a rien a
#                       lire. Panne d'instrument, sans rapport avec le budget.
#                       Non-mesure, exclue ET comptee.
#
# Les deux calculs sont publies cote a cote (regle 3c) : on ne choisit pas
# apres coup celui qui arrange.

MARQUE = "thinking budget is now exhausted"


def pensee_de(d):
    """Bloc de pensee, y compris quand l'ouverture <think> a ete rognee par le
    stockage en queue de chaine (reponse[-24000:])."""
    txt = d.get("reponse") or ""
    i = txt.find("<think>")
    j = txt.find("</think>")
    if i >= 0 and j > i:
        return txt[i + 7:j]
    if j >= 0:
        return txt[:j]
    return ""


def classer(d):
    if d.get("finish_reason") == "length":
        return "plafond"
    if MARQUE in pensee_de(d):
        return "coupe"
    return "libre"


def par_question(recs, garder_coupees=True):
    """Regroupe par question. La troncature au plafond est TOUJOURS exclue
    (3b) ; les coupures au budget sont gardees (3a) ou exclues selon le mode,
    afin de publier les deux calculs."""
    q = collections.defaultdict(list)
    for d in recs:
        c = classer(d)
        if c == "plafond":
            continue
        if c == "coupe" and not garder_coupees:
            continue
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
    qg = par_question(recs, garder_coupees=True)
    qx = par_question(recs, garder_coupees=False)
    mg, seg, nqg = moyenne_groupee(qg)
    mx, sex, nqx = moyenne_groupee(qx)
    rots = sorted({d.get("rotation") for d in recs})
    complet = sum(1 for v in qg.values() if len(v) == len(rots))

    classes = collections.Counter(classer(d) for d in recs)
    coupees = [d for d in recs if classer(d) == "coupe"]
    plafond = [d for d in recs if classer(d) == "plafond"]
    libres = [d for d in recs if classer(d) == "libre"]
    non_parse = [d for d in recs if not d.get("donne")]
    brut = sum(1 for d in recs if d.get("juste"))

    print("=" * 74)
    print("%s" % os.path.basename(chemin))
    print("  modele(s)   : %s" % ", ".join(modeles))
    print("  appels      : %d   erreurs reseau : %d" % (len(recs), err))
    print("  questions   : %d   dont completes sur %d rotations : %d"
          % (nqg, len(rots), complet))
    print("")
    print("  POPULATIONS (regle 3, Revision 2)")
    print("     libres              : %3d (%.1f %%)"
          % (classes["libre"], 100.0 * classes["libre"] / len(recs)))
    print("     coupees au budget   : %3d (%.1f %%)   MESURE, gardee en 3a"
          % (classes["coupe"], 100.0 * classes["coupe"] / len(recs)))
    print("     tronquees plafond   : %3d (%.1f %%)   NON-MESURE, exclue en 3b"
          % (classes["plafond"], 100.0 * classes["plafond"] / len(recs)))
    print("")
    print("  EXACTITUDE -- LES DEUX CALCULS (regle 3c), plafond exclu des deux")
    print("     coupees GARDEES  : %.1f %%  +/- %.1f pt   sur %d questions"
          % (100 * mg, 100 * seg, nqg))
    print("     coupees EXCLUES  : %.1f %%  +/- %.1f pt   sur %d questions"
          % (100 * mx, 100 * sex, nqx))
    if nqg > nqx:
        print("     -> %d question(s) disparaissent quand on exclut les coupees."
              % (nqg - nqx))
        print("        C'est le biais de selection que 3a evite : la coupure")
        print("        depend de la difficulte de la question.")
    print("     brut par appel (toutes populations) : %d/%d = %.1f %%"
          % (brut, len(recs), 100.0 * brut / len(recs)))
    print("        a ne PAS utiliser pour comparer : ignore la correlation")
    print("        entre rotations d'une question, et melange les populations.")

    # --- ENCADREMENT DES NON-MESURES (bornes de Manski) -------------------
    # Exclure les tronquees du plafond est juste (il n'y a rien a lire) MAIS
    # ce n'est pas neutre : la troncature depend de la DIFFICULTE (une question
    # dure ecrit plus longtemps et sature le plafond). Les exclure remonte donc
    # le score, exactement comme les garder comme fausses l'abaisse. Aucun des
    # deux n'est LE chiffre.
    # La seule chose honnete a publier tant que le rattrapage a 32768 n'est pas
    # fait, c'est l'ENCADREMENT : toutes fausses (borne basse) et toutes justes
    # (borne haute). Si l'encadrement est large, il n'y a pas de chiffre.
    if plafond:
        def borne(val):
            qb = collections.defaultdict(list)
            for d in recs:
                if classer(d) == "plafond":
                    qb[d["id"]].append(val)
                elif classer(d) == "coupe":
                    qb[d["id"]].append(bool(d.get("juste")))
                else:
                    qb[d["id"]].append(bool(d.get("juste")))
            return moyenne_groupee(qb)[0]

        bas, haut = borne(False), borne(True)
        print("")
        print("  ENCADREMENT sur les %d non-mesures du plafond (%.1f %% des appels)"
              % (len(plafond), 100.0 * len(plafond) / len(recs)))
        print("     toutes fausses : %.1f %%      toutes justes : %.1f %%"
              % (100 * bas, 100 * haut))
        print("     largeur : %.1f pt" % (100 * (haut - bas)))
        if (haut - bas) > 0.05:
            print("     LARGEUR > 5 pt : ce bras N'A PAS de chiffre d'exactitude")
            print("     publiable tant que le rattrapage a 32768 n'a pas eu lieu.")
            print("     Le score 'coupees GARDEES' ci-dessus est la BORNE HAUTE")
            print("     (non-mesures retirees), pas une mesure.")
        else:
            print("     largeur <= 5 pt : les non-mesures ne peuvent pas")
            print("     retourner la conclusion.")
    print("")
    # Rendement des coupees contre le hasard : c'est la regle 5.
    if coupees:
        jc = sum(1 for d in coupees if d.get("juste"))
        jl = sum(1 for d in libres if d.get("juste"))
        print("  RENDEMENT DES COUPEES (regle 5) : %d/%d = %.0f %%   "
              "libres : %d/%d = %.0f %%   hasard : 25 %%"
              % (jc, len(coupees), 100.0 * jc / len(coupees),
                 jl, len(libres), 100.0 * jl / max(1, len(libres))))
        # Constat 5 du red team : le message porte un litteral $LETTER ; un
        # modele qui l'echote ne matche aucun MOTIF et compte comme faux.
        #
        # PIEGE, tombe dedans le 26/08 : chercher "$LETTER" dans `reponse`
        # entiere compte le message de transition LUI-MEME, qui est injecte
        # dans le bloc de pensee et donc stocke. Resultat : 16 echos sur 16
        # coupees et 0 non-parse -- impossible. Un echo ne se cherche que dans
        # ce que le modele ecrit APRES avoir ferme sa pensee.
        def apres_pensee(d):
            txt = d.get("reponse") or ""
            return txt.split("</think>")[-1] if "</think>" in txt else txt

        echos = [d for d in coupees if "$LETTER" in apres_pensee(d)]
        np_c = [d for d in coupees if not d.get("donne")]
        print("     dont non parses : %d   dont echos litteraux de $LETTER "
              "dans la reponse : %d" % (len(np_c), len(echos)))
        if echos:
            print("     ATTENTION : un echo de $LETTER est un artefact de format,")
            print("     pas une erreur de raisonnement. Il abaisse le rendement.")
    print("  non parses (toutes populations) : %d (%.1f %%)"
          % (len(non_parse), 100.0 * len(non_parse) / len(recs)))
    if plafond:
        print("  RAPPEL : %d appel(s) au plafond de sortie sont EXCLUS et"
              % len(plafond))
        print("  restent DUS a un rattrapage symetrique a 32768.")

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
        d4 = collections.Counter(sum(v) for v in qg.values() if len(v) == len(rots))
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
    # Les DEUX regroupements remontent : la comparaison appariee est faite
    # deux fois (regle 3c) et les deux resultats sont publies.
    return {"gardees": qg, "exclues": qx}


def comparer(a, qa, b, qb):
    communs = sorted(set(qa) & set(qb))
    if not communs:
        print("\naucune question commune : pas de comparaison.")
        return None
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
    return d


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    qs = []
    for chemin in sys.argv[1:]:
        q = rapport(chemin)
        qs.append((chemin, q))
        print("")
    if len(qs) >= 2 and qs[0][1] and qs[1][1]:
        # Regle 3c : la comparaison appariee est publiee DEUX fois. Si les deux
        # menent a des decisions opposees, le balayage est non concluant et le
        # budget n'est pas regle sur ces donnees.
        verdicts = {}
        for mode, etiq in (("gardees", "COUPEES GARDEES (regle 3a)"),
                           ("exclues", "COUPEES EXCLUES (ancienne regle 3)")):
            print("")
            print("### %s" % etiq)
            verdicts[mode] = comparer(qs[0][0], qs[0][1][mode],
                                      qs[1][0], qs[1][1][mode])
        a, b = verdicts.get("gardees"), verdicts.get("exclues")
        print("")
        print("=" * 74)
        if a is None or b is None:
            print("REGLE 3c : un des deux calculs n'a pas pu etre fait.")
        elif (a > 0) != (b > 0):
            print("REGLE 3c -- LES DEUX CALCULS SE CONTREDISENT (%+.1f pt contre"
                  % (100 * a))
            print("%+.1f pt). Le balayage est NON CONCLUANT : le budget n'est"
                  % (100 * b))
            print("PAS regle sur ces donnees.")
        else:
            print("REGLE 3c : les deux calculs vont dans le meme sens "
                  "(%+.1f et %+.1f pt)." % (100 * a, 100 * b))


if __name__ == "__main__":
    main()
