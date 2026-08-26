# QUEL BUDGET COUPE COMBIEN ? -- la courbe, pas une intuition sur 8 questions.
#
# LE DEFAUT QU'ON REPARE. Le budget 8192 a ete pose a « 1,9x le pire appel
# sain » d'un echantillon illimite de 30 appels sur 8 QUESTIONS. Mesure sur le
# bras tournant : 45,5 % des appels touchent ce budget. La calibration est donc
# caduque -- elle predisait un evenement rare, on observe la moitie des appels.
# Constat 1 (HIGH) du red team du 26/08.
#
# TROIS ETATS, PAS DEUX. Pour un seuil t, chaque appel est dans un et un seul
# de ces etats :
#
#   CONNU > t   sa pensee depasse t avec certitude
#   CONNU <= t  sa pensee ne depasse pas t
#   INCONNU     la censure interdit de trancher
#
# D'ou vient la censure. Un appel COUPE PAR LE BUDGET B : on sait que sa pensee
# naturelle depassait B, jamais de combien -- donc connu > t pour t <= B,
# inconnu au-dela. Un appel TRONQUE AU PLAFOND de sortie apres L jetons de
# pensee : meme forme, borne a L. Un appel LIBRE et complet : sa longueur est
# observee, il est connu des deux cotes.
#
# Ce script ne jette AUCUN appel censure et n'en invente aucun : il publie
#
#     borne basse = CONNU>t / N        borne haute = (CONNU>t + INCONNU) / N
#
# Quand INCONNU vaut zero les deux bornes se rejoignent et c'est une mesure.
# Sinon c'est un encadrement, et il est ecrit comme tel. Meme discipline que
# `depouiller_gpqa.py` (regle 3b) et que l'encadrement de Manski du bras
# illimite : une non-mesure ne devient pas une mesure en changeant de colonne.
#
# POURQUOI CA DECIDE. Le taux de coupure predit a 2048 dit si le bras B mesure
# encore quelque chose ou s'il n'est qu'un second degre d'amputation. Si les
# deux bras coupent la majorite de leurs appels, le balayage ne compare plus
# « combien de pensee faut-il » mais deux guillotines -- et il faut alors un
# bras temoin a pensee libre, sinon la question posee n'a aucun bras qui y
# reponde.
#
# LES JETONS VIENNENT DU SERVEUR (/tokenize), pas d'une regle de trois sur les
# caracteres : le rapport caracteres/jetons varie assez avec le contenu (code,
# formules, unicode) pour deplacer un seuil.
#
#     python courbe_de_coupure.py <bras.jsonl> [budget|0 pour illimite]
#
# RESERVE. Les enregistrements ecrits avant le 26/08 16:45 stockent une queue
# de 24 000 caracteres : la pensee d'un appel long y perd sa tete, ce qui
# SOUS-ESTIME sa longueur. Le script compte ces cas et le dit ; leurs bornes
# basses restent valides (une longueur sous-estimee ne fait que rendre le
# « connu > t » plus prudent). Les enregistrements recents portent `pensee_car`
# mesure AVANT troncature.

import io
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8005"
MARQUE = "thinking budget is now exhausted"
SEUILS = (256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384)


def n_jetons(txt):
    if not txt:
        return 0
    req = urllib.request.Request(
        BASE + "/tokenize", data=json.dumps({"content": txt}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return len(json.loads(r.read().decode("utf-8", "replace")).get("tokens") or [])


def pensee_de(txt):
    """Rend (texte de pensee, tete_presente, fin_presente)."""
    i, j = txt.find("<think>"), txt.find("</think>")
    if i >= 0 and j > i:
        return txt[i + 7:j], True, True
    if j >= 0:
        return txt[:j], False, True              # tete perdue par la queue
    if i >= 0:
        return txt[i + 7:], True, False          # pensee jamais fermee
    return txt, False, False                     # tout est pensee, ou rien


def detecter_coupure(d, pensee, L, budget):
    """Une coupure au budget se voit de DEUX facons, et une seule ne suffit pas.

    (1) LE MARQUEUR. llama.cpp injecte `--reasoning-budget-message` juste avant
        la balise de fin. C'est le temoin le plus sur -- quand il existe.

    (2) LE MUR. Un serveur lance SANS message de transition coupe la pensee en
        pleine phrase et n'injecte RIEN. Aucun marqueur a chercher : la seule
        trace est que la longueur tombe pile sur le budget. C'est le cas du
        serveur du 25/08 20:57 au 26/08 14:12 (`--reasoning-budget 512` nu) --
        53 blocs sur 60 exactement a 512 jetons, mediane 512, max 514.

    Ne tester que (1) rend un bras a guillotine nue INVISIBLE : il se presente
    comme 100 % d'appels libres a pensee courte. C'est l'erreur que ce garde
    empeche. Le carnet, 26/08, « La guillotine a 512 jetons ».
    """
    m = d.get("marque")
    if m is None:
        m = MARQUE in pensee
    if m:
        return True
    # Le mur : tolerance de quelques jetons, la coupure tombe sur une frontiere
    # de jeton, pas sur un caractere (mesure : max 514 pour un budget de 512).
    return budget > 0 and L >= budget - 2


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python courbe_de_coupure.py <bras.jsonl> [budget]")
    chemin = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 8192

    # Chaque appel devient (borne, exact) :
    #   exact=True  -> pensee mesuree, longueur = borne
    #   exact=False -> pensee censuree AU-DELA de borne (budget ou plafond)
    appels, decapites, n_err = [], 0, 0
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne:
            continue
        d = json.loads(ligne)
        if d.get("erreur"):
            n_err += 1
            continue
        txt = d.get("reponse") or ""
        pensee, tete, fin = pensee_de(txt)
        if not tete and fin:
            decapites += 1
        L = n_jetons(pensee)
        marque = detecter_coupure(d, pensee, L, budget)
        if marque:
            # Coupe par le budget : la pensee NATURELLE depassait le budget.
            appels.append((max(L, budget), False))
        elif d.get("finish_reason") == "length":
            # Plafond de sortie atteint : censure a la longueur observee.
            appels.append((L, False))
        else:
            appels.append((L, True))

    n = len(appels)
    if n == 0:
        raise SystemExit("aucun appel exploitable dans %s" % chemin)

    n_cens = sum(1 for _, e in appels if not e)
    libres = sorted(L for L, e in appels if e)

    print("=" * 70)
    print("%s" % chemin)
    print("  budget du bras            : %s" % (budget if budget else "illimite"))
    print("  appels retenus            : %d  (%d mesures, %d censures)"
          % (n, n - n_cens, n_cens))
    if n_err:
        print("  erreurs ignorees          : %d" % n_err)
    print("  taux de censure OBSERVE   : %.1f %%" % (100.0 * n_cens / n))
    if decapites:
        print("  ATTENTION : %d pensees DECAPITEES par la queue de stockage ;"
              % decapites)
        print("    leur longueur est sous-estimee, les bornes basses restent valides.")
    print()

    if libres:
        def q(p):
            return libres[min(len(libres) - 1, int(p * len(libres)))]
        print("  pensee des appels MESURES (jetons), n = %d :" % len(libres))
        print("    min %d   q25 %d   mediane %d   q75 %d   p90 %d   max %d"
              % (libres[0], q(.25), q(.50), q(.75), q(.90), libres[-1]))
        print()

    print("  TAUX DE COUPURE d'un budget candidat -- encadrement :")
    print("  %-9s %10s %10s %9s   %s" % ("budget", "borne bas", "borne haut",
                                         "inconnus", "verdict"))
    for t in SEUILS:
        connu_sup = sum(1 for L, e in appels if (L >= t if not e else L > t))
        inconnu = sum(1 for L, e in appels if not e and L < t)
        bas = 100.0 * connu_sup / n
        haut = 100.0 * (connu_sup + inconnu) / n
        verdict = "mesure" if inconnu == 0 else "ENCADREMENT"
        print("  %-9d %9.1f %% %9.1f %% %9d   %s" % (t, bas, haut, inconnu, verdict))
    print()
    print("  Lecture : borne bas = appels dont on SAIT que la pensee depasse le")
    print("  seuil ; borne haut y ajoute ceux dont la censure empeche de trancher.")
    print("  Egalite des deux colonnes = mesure.")


main()
