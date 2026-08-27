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


def verdict_aider(chemin):
    """Verdict aider = pass_rate_2, soit le DERNIER essai de tests_outcomes."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return None
    outcomes = d.get("tests_outcomes")
    if not outcomes:
        return None
    return bool(outcomes[-1])


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
    ai = recolter(os.path.join(a.racine, a.run_aider), ".aider.results.json", verdict_aider)

    inter = sorted(set(d) & set(ai))
    print(f"variante D  : {len(d):3d} exercices juges")
    print(f"aider board : {len(ai):3d} exercices juges")
    print(f"INTERSECTION: {len(inter):3d}  <-- tout ce qui suit porte SUR ELLE SEULE")
    print()

    print(f"{'piste':12s} {'n':>4s} {'D pass':>8s} {'aider pass':>11s} {'ecart':>8s}")
    print("-" * 48)
    for piste in PISTES:
        sous = [k for k in inter if k[0] == piste]
        if not sous:
            continue
        nd = sum(d[k] for k in sous)
        na = sum(ai[k] for k in sous)
        n = len(sous)
        print(f"{piste:12s} {n:4d} {nd:4d} {100*nd/n:6.1f}% {na:4d} {100*na/n:6.1f}% "
              f"{100*(nd-na)/n:+7.1f}")
    n = len(inter)
    nd = sum(d[k] for k in inter)
    na = sum(ai[k] for k in inter)
    print("-" * 48)
    print(f"{'TOTAL':12s} {n:4d} {nd:4d} {100*nd/n:6.1f}% {na:4d} {100*na/n:6.1f}% "
          f"{100*(nd-na)/n:+7.1f}")

    aa = sum(1 for k in inter if d[k] and ai[k])
    b = sum(1 for k in inter if d[k] and not ai[k])
    c = sum(1 for k in inter if not d[k] and ai[k])
    dd = sum(1 for k in inter if not d[k] and not ai[k])
    print()
    print("CONCORDANCE (c'est elle qui porte l'information, pas l'ecart global)")
    print(f"  les deux PASSENT          {aa:4d}")
    print(f"  D seul passe              {b:4d}   <- l'agent gagne")
    print(f"  aider seul passe          {c:4d}   <- l'agent perd")
    print(f"  les deux ECHOUENT         {dd:4d}")
    print(f"  McNemar exact bilateral   p = {mcnemar_exact(b, c):.4f}  (n discordants = {b+c})")

    if b:
        print("\n  D gagne :", ", ".join(f"{p}/{e}" for p, e in inter if d[(p, e)] and not ai[(p, e)]))
    if c:
        print("\n  D perd  :", ", ".join(f"{p}/{e}" for p, e in inter if not d[(p, e)] and ai[(p, e)]))

    print("\nRESERVE : run variante D EN COURS. Lecture d'etape, pas un depouillement.")


if __name__ == "__main__":
    main()
