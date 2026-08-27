"""Compare APPARIEE des deux protocoles sur le MEME modele et les MEMES exercices.

LA QUESTION, posee le 27/08 : un modele qui recoit le fichier de test officiel
et la sortie d'echec (protocole du board aider, 2 essais, pas d'execution) fait
52,0 % sur 225. Le MEME modele, en agent qui n'a jamais vu la suite officielle
et ecrit ses propres tests (variante D), fait combien ?

CE QUE CE SCRIPT REFUSE DE FAIRE. Comparer 65,9 % sur 88 exercices a 52,0 % sur
225 : les deux nombres ne portent pas sur le meme corpus, et le sous-ensemble
joue a ce jour est le FAVORABLE (cpp termine a 96 %, javascript/python/rust pas
commences). Le script restreint donc les DEUX bras a l'INTERSECTION exacte des
exercices juges de part et d'autre, et ne publie rien d'autre.

CE QU'IL SORT :
  * le taux de chaque bras sur l'intersection, par piste et au total ;
  * la table de concordance 2x2 (les deux passent / D seul / aider seul / les
    deux echouent), qui porte l'information -- un ecart de taux global peut
    cacher des basculements dans les deux sens ;
  * McNemar exact bilateral sur les discordants.

DEFAUT CORRIGE LE 27/08 -- L'APPARIEMENT ETAIT ASYMETRIQUE. La premiere version
comparait la variante D au `pass_rate_2` du board, soit 52,0 %. C'est le taux du
DEUXIEME essai : le modele a d'abord vu le fichier de test officiel, l'a fait
tomber, a recu la SORTIE D'ECHEC, puis a recommence. La variante D, elle, joue
UN tour et ne recoit aucun retour officiel. On mettait donc un bras sans retour
face a un bras avec retour, et on appelait le resultat une parite.

Le board publie les deux (reports/specdec_20260825_ctxsweep_dflash2/
aider_polyglot_stats.yml) : `pass_rate_1 = 16,9 %`, `pass_rate_2 = 52,0 %`. Le
retour du juge vaut donc +35,1 points POUR CE MODELE MEME. L'appariement honnete
est par nombre de tours :
    D a 1 tour   <->  pass_rate_1  (16,9 %)   -- aucun des deux n'a de retour
    D a 2 tours  <->  pass_rate_2  (52,0 %)   -- les deux en ont un
Ce script sort DESORMAIS LES DEUX, et refuse de n'en publier qu'un.

CE QUE LE TOUR 2 FAIT, ET POURQUOI CE N'EST PAS UN DEFAUT. `pilote.py:1071`
reinjecte `erreurs`, qui sort de `lancer_tests()` sur les fichiers de test
OFFICIELS. C'est VOULU et documente : ordre operateur du 27/08 07:10, inscrit
dans `lancer_polyglot_complet.ps1:50-68` -- « Au tour 2, pilote.py renvoie a
l'agent la SORTIE D'ERREUR de la suite officielle (jamais son code source) avec
la relance mot pour mot d'aider. C'est la definition de pass_rate_2. » Un bras D
a 2 tours est le symetrique honnete de `pass_rate_2` ; un bras D a 1 tour est le
symetrique de `pass_rate_1`. Aucun des deux n'est illegitime ; ils ne se posent
simplement pas a cote des memes lignes publiees.

LE VRAI DEFAUT, MESURE LE 27/08 : LE BRAS N'EST PAS HOMOGENE. Le run
`pi_D_t1_dflash2` porte 107 exercices a 1 tour ET 5 exercices cpp a 2 tours --
sequelle de l'etape « complement » de mesurer_valeur_du_semis.ps1:136-141, qui
rejoue en `--tours 2` DANS LE MEME repertoire de run. 4 des 5 basculent
FAIL -> PASS au tour 2. Un meme bras melange donc pass_rate_1 et pass_rate_2, et
rien ne le signalait : `len(tests_outcomes)` etait le seul indice, et il ne
distingue pas « 2 tours demandes, converge au premier » de « 1 tour demande ».
D'ou le champ `tours_demandes` (pilote.py) et l'alerte de `etat_run.py`, tous
deux poses le 27/08. Ce script ISOLE les 5 et publie le taux sans eux.

RESERVE, a lire avec tout chiffre qui sort d'ici : le run variante D est EN
COURS. Ceci est une lecture d'etape, jamais un depouillement. La regle d'arret
tient : le depouillement fait foi une seule fois, sur les 225 verdicts.
"""

import argparse
import json
import os
from math import comb

PISTES = ("cpp", "go", "java", "javascript", "python", "rust")


def verdict_d(chemin):
    """Verdict variante D. Reprend etat_run.verdict : le champ racine `ok`
    N'EXISTE PAS, le verdict est dans turns[-1].ok, double par tests_outcomes.
    Rend None quand l'exercice n'a pas ete joue (pilote leve avant le tour 1)."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return None
    tours = d.get("turns") or []
    if not tours:
        return None
    ok = tours[-1].get("ok")
    if ok is None:
        outcomes = d.get("tests_outcomes") or []
        ok = bool(outcomes and outcomes[-1])
    return bool(ok)


def tours_d(chemin):
    """Nombre de tours joues cote D. > 1 signifie que l'exercice a recu la
    SORTIE D'ECHEC OFFICIELLE entre les deux (pilote.py:1071) : il n'est plus
    aveugle et ne se compare plus a pass_rate_1."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return None
    return len(d.get("tests_outcomes") or []) or None


def verdict_aider_2(chemin):
    """pass_rate_2 : DERNIER essai. Le modele a vu la sortie d'echec officielle."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return None
    outcomes = d.get("tests_outcomes")
    if not outcomes:
        return None
    return bool(outcomes[-1])


def verdict_aider_1(chemin):
    """pass_rate_1 : PREMIER essai. Le modele a le fichier de test officiel sous
    les yeux, mais aucune sortie d'echec -- c'est le bras comparable a une
    variante D a un tour."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return None
    outcomes = d.get("tests_outcomes")
    if not outcomes:
        return None
    return bool(outcomes[0])


def recolter(racine, nom_fichier, lecteur):
    """{(piste, exercice): bool} pour tout ce qui porte un verdict."""
    out = {}
    for piste in PISTES:
        base = os.path.join(racine, piste, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            f = os.path.join(base, ex, nom_fichier)
            if not os.path.isfile(f):
                continue
            v = lecteur(f)
            if v is not None:
                out[(piste, ex)] = v
    return out


def mcnemar_exact(b, c):
    """p bilateral exact sur les discordants : binomiale(b+c, 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    queue = sum(comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * queue)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_d", help="nom du run variante D, ex. pi_D_t1_dflash2")
    ap.add_argument("run_aider", help="dirname du run aider dans tmp.benchmarks")
    ap.add_argument("--racine", default=os.path.join(
        os.path.expanduser("~"), "tools", "aider-bench", "aider", "tmp.benchmarks"))
    a = ap.parse_args()

    d = recolter(os.path.join(a.racine, a.run_d), ".dsh.results.json", verdict_d)
    tours = recolter(os.path.join(a.racine, a.run_d), ".dsh.results.json", tours_d)
    a1 = recolter(os.path.join(a.racine, a.run_aider), ".aider.results.json", verdict_aider_1)
    a2 = recolter(os.path.join(a.racine, a.run_aider), ".aider.results.json", verdict_aider_2)

    inter = sorted(set(d) & set(a2))
    contamines = sorted(k for k in inter if (tours.get(k) or 1) > 1)
    print(f"variante D  : {len(d):3d} exercices juges")
    print(f"aider board : {len(a2):3d} exercices juges")
    print(f"INTERSECTION: {len(inter):3d}  <-- tout ce qui suit porte SUR ELLE SEULE")
    print()
    print("EXERCICES A 2 TOURS -- ILS RELEVENT DE pass_rate_2, PAS DE pass_rate_1.")
    print("Le tour 2 rend a l'agent la sortie d'erreur de la suite officielle")
    print("(pilote.py:1071) : c'est voulu et documente (ordre operateur 27/08),")
    print("mais ca ne se moyenne pas avec des tours aveugles. Isoles ici :")
    if contamines:
        for p, e in contamines:
            print(f"    {p}/{e:28s} tours={tours[(p, e)]}  verdict final={'PASS' if d[(p, e)] else 'FAIL'}")
    else:
        print("    AUCUN")
    print()

    def bloc(titre, ref, sous_inter, note):
        n = len(sous_inter)
        if not n:
            print(f"{titre} : intersection vide.")
            return
        print("=" * 62)
        print(titre)
        print(note)
        print("=" * 62)
        print(f"{'piste':12s} {'n':>4s} {'D pass':>8s} {'board pass':>11s} {'ecart':>8s}")
        print("-" * 48)
        for piste in PISTES:
            sous = [k for k in sous_inter if k[0] == piste]
            if not sous:
                continue
            nd = sum(d[k] for k in sous)
            na = sum(ref[k] for k in sous)
            m = len(sous)
            print(f"{piste:12s} {m:4d} {nd:4d} {100*nd/m:6.1f}% {na:4d} {100*na/m:6.1f}% "
                  f"{100*(nd-na)/m:+7.1f}")
        nd = sum(d[k] for k in sous_inter)
        na = sum(ref[k] for k in sous_inter)
        print("-" * 48)
        print(f"{'TOTAL':12s} {n:4d} {nd:4d} {100*nd/n:6.1f}% {na:4d} {100*na/n:6.1f}% "
              f"{100*(nd-na)/n:+7.1f}")
        aa = sum(1 for k in sous_inter if d[k] and ref[k])
        b = sum(1 for k in sous_inter if d[k] and not ref[k])
        c = sum(1 for k in sous_inter if not d[k] and ref[k])
        dd = sum(1 for k in sous_inter if not d[k] and not ref[k])
        print()
        print("CONCORDANCE (c'est elle qui porte l'information, pas l'ecart global)")
        print(f"  les deux PASSENT          {aa:4d}")
        print(f"  D seul passe              {b:4d}   <- l'agent gagne")
        print(f"  board seul passe          {c:4d}   <- l'agent perd")
        print(f"  les deux ECHOUENT         {dd:4d}")
        print(f"  McNemar exact bilateral   p = {mcnemar_exact(b, c):.4f}  (n discordants = {b+c})")
        if b:
            print("\n  D gagne :", ", ".join(f"{p}/{e}" for p, e in sous_inter
                                             if d[(p, e)] and not ref[(p, e)]))
        if c:
            print("\n  D perd  :", ", ".join(f"{p}/{e}" for p, e in sous_inter
                                             if not d[(p, e)] and ref[(p, e)]))
        print()

    aveugles = [k for k in inter if k not in set(contamines)]

    bloc("APPARIEMENT HONNETE -- D a 1 tour  CONTRE  board pass_rate_1",
         a1, aveugles,
         "Aucun des deux bras n'a recu de sortie d'echec. Le board garde son\n"
         "avantage propre : il LIT le fichier de test officiel. C'est la seule\n"
         "comparaison que ce run autorise.")

    bloc("POUR MEMOIRE -- D a 1 tour  CONTRE  board pass_rate_2  (ASYMETRIQUE)",
         a2, aveugles,
         "A NE PAS PUBLIER SEUL. Le board a ici DEUX essais et la sortie d'echec\n"
         "officielle entre les deux ; D n'a qu'un tour et aucun retour. Le bras\n"
         "symetrique (D a 2 tours) n'existe pas encore.")

    print("RESERVE : run variante D EN COURS. Lecture d'etape, pas un depouillement.")


if __name__ == "__main__":
    main()
