# -*- coding: utf-8 -*-
"""Depouille la prediction figee dans prediction_enonces_ambigus.json.

CE QUE CA MESURE, et c'est la seule lecture valide : l'ECART entre le taux
d'echec des exercices SIGNALES et celui des NON SIGNALES. Pas le nombre de
signales qui echouent -- avec 55 exercices signales par S2, en signaler
beaucoup qui echouent est arithmetiquement banal. Une signature n'est pas une
cause ; elle n'a de valeur que si elle SEPARE.

CE QUE CA NE MESURE PAS. Rien ici n'etablit qu'une signature CAUSE l'echec. Un
ecart peut venir d'un tiers : S4 ne voit que go+java+rust, et ces trois pistes
n'ont aucune raison d'avoir la meme difficulte de base que cpp ou python. C'est
pourquoi chaque signature est depouillee SUR SON PROPRE PERIMETRE de visibilite,
jamais sur les 225.

LE PETIT EFFECTIF. S1 ne porte que 3 exercices. Deux echecs sur trois font
« 67 % contre 12 % » et ne prouvent rien. Le test de Fisher unilateral exact est
donc calcule et imprime a cote de chaque ecart : c'est lui qui dit si l'ecart
survit au hasard, pas la taille apparente du pourcentage.

USAGE :
    python verifier_prediction.py pi_D_t1_dflash2 [--prediction <f.json>]
"""
import collections
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preparer_rejeu_reformule import verdicts
# Le perimetre de visibilite de S4 vient du DETECTEUR lui-meme, jamais recopie
# ici : deux listes finiraient par diverger, et le depouillement se ferait alors
# sur un perimetre que la prediction n'a pas utilise.
from predire_enonces_ambigus import LANGUES_S4

ICI = os.path.dirname(os.path.abspath(__file__))
SIGNATURES = ("S1", "S2", "S3", "S4")

# LES TROIS CAS FONDATEURS. S1, S3 et S4 ont ete ECRITES en regardant ces
# echecs-la ; S2 aussi. Les compter dans le depouillement, c'est demander a une
# regle de retrouver les exemples qui l'ont produite -- elle les retrouve
# toujours, et le p qui en sort ne mesure rien. Tant que les seuls echecs
# depouilles sont ceux-la, le verdict est NON CONCLUANT, et le script le dit.
FONDATRICES = ("go/beer-song", "go/connect", "go/kindergarten-garden")


def fisher_unilateral(a, b, c, d):
    """P(observer au moins `a` echecs chez les signales | marges fixees).

        signales      a echecs   b succes
        non signales  c echecs   d succes

    Unilateral a droite : l'hypothese testee est « les signales echouent PLUS ».
    Exact, par sommation hypergeometrique -- aucune approximation normale, qui
    serait fausse justement aux effectifs ou on en a besoin.
    """
    n1, n2, m1, N = a + b, c + d, a + c, a + b + c + d
    if not n1 or not n2 or not m1 or m1 == N:
        return 1.0
    total = math.comb(N, m1)
    p = 0.0
    for k in range(a, min(n1, m1) + 1):
        p += math.comb(n1, k) * math.comb(n2, m1 - k) / total
    return min(1.0, p)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = sys.argv[1]
    chemin = os.path.join(ICI, "prediction_enonces_ambigus.json")
    if "--prediction" in sys.argv:
        chemin = sys.argv[sys.argv.index("--prediction") + 1]

    if not os.path.exists(chemin):
        print("REFUS : prediction introuvable -> %s" % chemin)
        return 2
    pred = json.load(io.open(chemin, encoding="utf-8"))
    porte = collections.defaultdict(set)
    for e in pred["exercices"]:
        for s in e["signatures"]:
            porte[s].add(e["exercice"])

    v = verdicts(run)
    if not v:
        print("REFUS : aucun verdict dans %s" % run)
        return 2

    # Un run reformule ne depouille pas cette prediction : l'enonce qu'il a
    # servi n'est pas celui que le detecteur a lu.
    reform = [k for k, d in v.items() if d["reformulations"]]
    if reform:
        print("REFUS : %d exercice(s) de %s portent une reformulation. La "
              "prediction a ete calculee sur les enonces D PURS ; la depouiller "
              "sur un run reformule comparerait deux enonces differents."
              % (len(reform), run))
        return 2

    # Un tour COUPE n'a pas produit un verdict sur l'enonce : l'agent a ete
    # arrete par la laisse de silence, son fichier porte encore le stub. Le
    # compter en echec ferait remonter le taux des NON signales -- donc
    # RETRECIRAIT l'ecart mesure. L'ecarter est le geste conservateur, et il
    # est nomme pour que personne ne croie a un corpus complet.
    # ATTENTION au sens exact : on n'ecarte que les coupures qui ont ECHOUE.
    # Une coupure qui a PASSE reste un PASS -- le juge a tourne, il a dit oui ;
    # la laisse ne peut que nuire, jamais aider. En ecarter 3 (zebra-puzzle,
    # crypto-square, ledger, tous coupes ET passes) retirerait des succes du
    # denominateur et gonflerait le taux d'echec des deux colonnes.
    coupes = sorted(k for k in v if v[k]["coupe"] and not v[k]["ok"])
    joues = sorted(k for k in v if k not in set(coupes))
    if not joues:
        print("REFUS : tous les verdicts de %s sont des tours coupes." % run)
        return 2
    print("run depouille   : %s" % run)
    print("verdicts        : %d / %d du corpus" % (len(v),
                                                   pred["total_corpus"]))
    if coupes:
        print("tours coupes    : %d, ECARTES du depouillement" % len(coupes))
        for k in coupes:
            print("                    %-34s %7.1f s" % (k, v[k]["duree"]))
        print("depouilles      : %d" % len(joues))
    if len(joues) < pred["total_corpus"]:
        print("                  RUN PARTIEL -- les taux ci-dessous ne portent")
        print("                  que sur ce qui a ete joue, et les langues non")
        print("                  jouees ne pesent pas encore.")
    ech = sum(1 for k in joues if not v[k]["ok"])
    print("echecs          : %d  (%.1f %% des joues)"
          % (ech, 100.0 * ech / len(joues)))
    print("")

    def table(champ_total, titre):
        print("=== %s ===" % titre)
        ech_ici = sum(1 for k in champ_total if not v[k]["ok"])
        if not ech_ici:
            print("  NON CONCLUANT : %d exercice(s) depouille(s), AUCUN echec."
                  % len(champ_total))
            print("  Un taux d'echec de zero ne separe rien : toutes les")
            print("  signatures y sont a egalite. Attendre que le run avance.")
            print("")
            return
        print("  sig   perimetre        signales           non signales        ecart      Fisher")
        vides = []
        for s in SIGNATURES:
            # Perimetre : S4 est aveugle hors go+java+rust, donc y compter les
            # autres langues comme « non signalees » fabriquerait un ecart.
            champ = [k for k in champ_total
                     if s != "S4" or k.split("/")[0] in LANGUES_S4]
            if not champ:
                vides.append((s, "aucun exercice joue dans le perimetre"))
                continue
            sig = [k for k in champ if k in porte[s]]
            non = [k for k in champ if k not in porte[s]]
            if not sig:
                vides.append((s, "aucun exercice signale n'a encore ete joue"))
                continue
            a = sum(1 for k in sig if not v[k]["ok"])
            b = len(sig) - a
            c = sum(1 for k in non if not v[k]["ok"])
            d = len(non) - c
            ts = 100.0 * a / len(sig)
            tn = 100.0 * c / len(non) if non else float("nan")
            p = fisher_unilateral(a, b, c, d)
            print("  %-5s %-16s %2d/%-3d = %5.1f %%   %3d/%-3d = %5.1f %%   %+6.1f pt   p = %.3f%s"
                  % (s, "%d joues" % len(champ), a, len(sig), ts,
                     c, len(non), tn, ts - tn, p,
                     "" if len(sig) >= 5 else "   (n<5)"))
        for s, pourquoi in vides:
            print("  %-5s non depouillable : %s" % (s, pourquoi))
        print("")

    fond = [k for k in joues if k in FONDATRICES]
    hors = [k for k in joues if k not in FONDATRICES]
    table(joues, "TOUT, cas fondateurs compris -- A NE PAS PUBLIER SEUL")
    if fond:
        print("  Les %d cas fondateurs presents dans ce tableau (%s) ont SERVI"
              % (len(fond), ", ".join(fond)))
        print("  a ecrire les signatures. Une regle retrouve toujours les")
        print("  exemples dont elle est tiree : le p ci-dessus est circulaire.")
        print("")
    table(hors, "HORS cas fondateurs -- c'est CE tableau qui teste la prediction")

    print("LECTURE. Un ecart positif dit que la signature separe ; p dit si la")
    print("separation survit au hasard aux effectifs atteints. Un ecart de")
    print("+40 points sur 3 exercices signales ne conclut rien -- regarder p,")
    print("et attendre que le run avance. Un ecart NEGATIF est un resultat lui")
    print("aussi : la signature ne predit pas ce qu'elle pretendait.")
    print("")

    # Le detail nominatif : sans lui, un ecart ne se verifie pas a la main.
    rates = [(s, sorted(k for k in joues if k in porte[s] and not v[k]["ok"]))
             for s in SIGNATURES]
    print("=== echecs signales, par signature ===")
    for s, ks in rates:
        if ks:
            print("  %-5s %s" % (s, ", ".join(ks)))
    manques = sorted(k for k in joues
                     if not v[k]["ok"]
                     and not any(k in porte[s] for s in SIGNATURES))
    print("")
    print("=== echecs qu'AUCUNE signature n'avait signales : %d ==="
          % len(manques))
    for k in manques:
        print("  %s" % k)
    if manques:
        print("")
        print("Ce sont eux qui comptent le plus : chacun est une famille")
        print("d'ambiguite que le detecteur ne sait pas voir, ou un echec de")
        print("fond qui n'a rien a voir avec l'enonce. Les distinguer demande")
        print("de lire la sortie du juge, pas ce tableau.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
