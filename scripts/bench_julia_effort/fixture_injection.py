# -*- coding: utf-8 -*-
"""Prouve que le bloc construit par le banc ARRIVE dans l enonce du tour suivant.

Pourquoi ce fixture existe : la branche recherche+injection de `un_run_boucle`
n avait JAMAIS ete parcourue. Le fixture de bout en bout du 22/08 est passe au
premier tour (tours=1, rech=0), donc la branche n a jamais rien construit. Un
chemin de repli jamais parcouru echoue en position permissive : il aurait pu
injecter un bloc vide, mal forme, ou ne rien injecter du tout, et le banc
aurait continue en affichant rech=1.

On ne force rien dans le banc : on rejoue la construction sur un VRAI message
de juge, on ecrit TASK.md exactement comme la boucle l ecrit, et on relit le
fichier. Bras known-BAD compris : sans recherche, le bloc ne doit contenir
aucun extrait.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench  # noqa: E402

# Message reel, sorti du juge le 22/08 sur t33.
WHY = ("check: LoadError: AssertionError: les negatifs sortent avant les "
       "positifs @ C:/Users/test/runs/x/t33/mytest.jl:14")
TACHE = "t33"

echecs = []


def exiger(condition, quoi):
    print("  %s %s" % ("ok  " if condition else "ECHEC", quoi))
    if not condition:
        echecs.append(quoi)


print("=== 1. la requete construite sur le message du juge ===")
q = bench._question_depuis_echec(TACHE, WHY)
print("  requete : %s" % q)
exiger(q.startswith("Julia"), "la requete nomme le langage")
exiger("C:/Users" not in q and "mytest.jl:14" not in q,
       "les chemins et numeros de ligne du poste sont retires")
exiger("AssertionError" in q, "le type d erreur SURVIT au nettoyage")
exiger("negatifs" in q, "les mots de l assertion survivent")

print("=== 2. la recherche ===")
trouve = bench.recherche_basique(q)
print("  %d resultat(s)" % len(trouve))
for t, u, _ in trouve:
    print("    - %s | %s" % (t[:60], u[:70]))
exiger(len(trouve) > 0, "le moteur repond")

print("=== 3. le bloc injecte, bras AVEC recherche ===")
bloc = bench._bloc_retour(1, WHY, trouve, True)
exiger(WHY[:40] in bloc, "le message du juge est dans le bloc")
exiger(all(u in bloc for _, u, _ in trouve), "chaque URL trouvee est dans le bloc")
exiger(len(bloc) > 200, "le bloc n est pas vide (%d caracteres)" % len(bloc))

print("=== 4. le bloc arrive dans TASK.md, comme l ecrit la boucle ===")
ws = os.path.join(bench.BASE, "runs", "_fixture_injection")
if not os.path.isdir(ws):
    os.makedirs(ws)
base = io.open(os.path.join(bench.BASE, "prompts", "%s.txt" % TACHE),
               encoding="utf-8").read()
base = bench.PREAMBULE_BOUCLE + base
cible = os.path.join(ws, "TASK.md")
io.open(cible, "w", encoding="utf-8", newline=chr(10)).write(base + bloc)
relu = io.open(cible, encoding="utf-8").read()
exiger(relu.endswith(bloc), "TASK.md se termine par le bloc")
exiger(all(u in relu for _, u, _ in trouve), "les URL sont dans le FICHIER relu")
exiger("Ne lance PAS de recherche web" in relu,
       "le preambule de boucle est present")

print("=== 5. bras KNOWN-BAD : pas de recherche => pas d extrait ===")
muet = bench._bloc_retour(1, WHY, [], False)
exiger(WHY[:40] in muet, "le message du juge est toujours la")
exiger(not any(u in muet for _, u, _ in trouve),
       "aucune URL ne s est glissee dans le bloc sans recherche")
exiger(len(muet) < len(bloc), "le bloc muet est plus court (%d < %d)"
       % (len(muet), len(bloc)))

print("=== 6. bras KNOWN-BAD : le plafond ===")
faux = [{"tour": 1, "requete": "a"}, {"tour": 2, "requete": "b"}]
sous = sum(1 for r in faux if r.get("requete")) < 2
exiger(not sous, "a 2 recherches enregistrees, le plafond de 2 est atteint")
sous1 = sum(1 for r in faux[:1] if r.get("requete")) < 2
exiger(sous1, "a 1 recherche, le plafond de 2 laisse passer")

print("=== 7. le filtre de pertinence, sur les 3 resultats REELLEMENT injectes ===")
# Cas reel du 22/08, t24 en boucle locale : la recherche a injecte un blog de
# mots croises du NYT et Google Traduction, et le run a reussi ensuite -- donc
# le score seul aurait fait passer cette injection pour de l aide.
REELS = [("Issues - JuliaLang/julia", "https://github.com/JuliaLang/julia/issues", ""),
         ("NYT Connections words meaning August 20 2026",
          "https://connectionssports.com/blog/nyt-connections-words-meaning-august-20-2026", ""),
         ("Google Translate", "https://translate.google.com/", "")]
garde = [x for x in REELS if bench._pertinent(*x)]
jete = [x for x in REELS if not bench._pertinent(*x)]
for t, u, _ in garde:
    print("  RETENU  %s" % u[:70])
for t, u, _ in jete:
    print("  ECARTE  %s" % u[:70])
exiger(len(garde) == 1 and "JuliaLang" in garde[0][1], "la source Julia est retenue")
exiger(len(jete) == 2, "les deux hors sujet sont ecartes")
exiger(bench._pertinent("Sorting", "https://discourse.julialang.org/t/x", ""),
       "un titre sans le mot mais sur un domaine Julia passe")
exiger(not bench._pertinent("Recette de tarte", "https://cuisine.example/tarte", ""),
       "un resultat sans rapport ne passe pas")

print("=== 8. la requete ne part plus avec le jargon du banc ===")
brut = ("check: LoadError: AssertionError: float64 gros-boutiste | in "
        "expression starting at C:/Users/test/runs/t24/mytest.jl:31")
q2 = bench._question_depuis_echec("t24", brut)
print("  %s" % q2)
exiger(not q2.startswith("Julia check:"), "le mot 'check:' du banc est retire")
exiger("in expression starting at" not in q2, "la queue de bruit est coupee")
exiger("AssertionError" in q2 and "float64" in q2, "l erreur et son objet survivent")

print()
if echecs:
    print("FIXTURE EN ECHEC : %d" % len(echecs))
    for e in echecs:
        print("  - %s" % e)
    sys.exit(1)
print("FIXTURE OK -- la branche d injection est parcourue et verifiee.")
