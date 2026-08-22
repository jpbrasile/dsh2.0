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
trouve, etat = bench.recherche_basique(q)
print("  etat du moteur : %s" % etat)
print("  %d resultat(s)" % len(trouve))
for t, u, _ in trouve:
    print("    - %s | %s" % (t[:60], u[:70]))
# L etat NOMME l etage qui a servi ("zai", "openrouter", eventuellement suivi
# des replis), ou commence par "aucun etage:" avec la raison de chacun. Un
# etat qui ne nomme personne serait un resultat sans provenance.
servi = etat.split(" (")[0]
exiger(servi in ("zai", "exa", "openrouter") or etat.startswith("aucun etage"),
       "l etat NOMME l etage qui a servi, ou dit qu aucun n a pu")
exiger(bool(trouve) == (not etat.startswith("aucun etage")),
       "des resultats si et seulement si un etage a servi")
if etat.startswith("aucun etage"):
    print("  (aucun etage -- on poursuit avec la liste vide, ce que le banc ferait)")
elif "replis" in etat:
    print("  ATTENTION : l etage qui a servi n est pas le premier -- %s" % etat)

print("=== 3. le bloc injecte, bras AVEC recherche ===")
HIST = [{"tour": 1, "why": WHY, "cle": bench._cle_echec(WHY)}]
bloc = bench._bloc_retour(1, HIST, trouve, True)
exiger(WHY[:40] in bloc, "le message du juge est dans le bloc")
exiger(all(u in bloc for _, u, _ in trouve), "chaque URL trouvee est dans le bloc")
exiger(len(bloc) > 200, "le bloc n est pas vide (%d caracteres)" % len(bloc))

print("=== 4. le bloc arrive dans TASK.md, comme l ecrit la boucle ===")
ws = os.path.join(bench.BASE, "runs", "_fixture_injection")
if not os.path.isdir(ws):
    os.makedirs(ws)
base = io.open(os.path.join(bench.BASE, "prompts", "%s.txt" % TACHE),
               encoding="utf-8").read()
base = bench.preambule_boucle(3, bench.TIMEOUT_TOUR, web=True) + base
cible = os.path.join(ws, "TASK.md")
io.open(cible, "w", encoding="utf-8", newline=chr(10)).write(base + bloc)
relu = io.open(cible, encoding="utf-8").read()
exiger(relu.endswith(bloc), "TASK.md se termine par le bloc")
exiger(all(u in relu for _, u, _ in trouve), "les URL sont dans le FICHIER relu")
exiger("Do NOT run a web search" in relu,
       "le preambule de boucle est present dans le FICHIER relu")
exiger("CUT OFF after" in relu and "at most 3 attempt(s)" in relu,
       "le budget arrive jusqu au fichier que le modele lira")

print("=== 5. bras KNOWN-BAD : pas de recherche => pas d extrait ===")
muet = bench._bloc_retour(1, HIST, [], False)
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
# Le defaut INVERSE, mesure le 22/08 sur t31 rep2 : ce resultat repondait a
# l erreur du tour et il a ete ECARTE. Ni l adresse, ni le titre, ni
# l extrait ne portent le mot "julia" -- seulement ".jl". Le bras existe
# pour que le filtre ne puisse plus se resserrer sans qu on le voie.
exiger(bench._pertinent("Numerical error with ForwardDiff",
                        "https://github.com/TuringLang/Turing.jl/issues/700", ""),
       "un depot .jl passe sans que le mot julia soit ecrit")
exiger(not bench._pertinent("Qqjj Ransomware Removal",
                            "https://www.enigmasoftware.com/qqjjransomware-removal/", ""),
       "le charabia du bras known-BAD reste ecarte apres elargissement")
exiger(not bench._pertinent("Fichier", "https://exemple.test/a.jlpackage", ""),
       ".jl en plein mot ne suffit pas -- suffixe seulement")

print("=== 8. la requete ne part plus avec le jargon du banc ===")
brut = ("check: LoadError: AssertionError: float64 gros-boutiste | in "
        "expression starting at C:/Users/test/runs/t24/mytest.jl:31")
q2 = bench._question_depuis_echec("t24", brut)
print("  %s" % q2)
exiger(not q2.startswith("Julia check:"), "le mot 'check:' du banc est retire")
exiger("in expression starting at" not in q2, "la queue de bruit est coupee")
exiger("AssertionError" in q2 and "float64" in q2, "l erreur et son objet survivent")

print("=== 9. l historique des echecs, et la repetition NOMMEE ===")
H1 = [{"tour": 1, "why": "check: AssertionError: longueur apres 100",
       "cle": bench._cle_echec("check: AssertionError: longueur apres 100")}]
b1 = bench._bloc_retour(1, H1, [], False)
exiger("Already tried" not in b1, "au premier echec, pas de section historique")

W2 = "check: MethodError: no method matching similar"
H2 = H1 + [{"tour": 2, "why": W2, "cle": bench._cle_echec(W2)}]
b2 = bench._bloc_retour(2, H2, [], False)
exiger("Already tried" in b2, "au second echec, l historique apparait")
exiger("longueur apres 100" in b2, "l echec du tour 1 est rappele")
exiger("SAME FAILURE" not in b2, "deux causes DIFFERENTES ne sont pas dites identiques")

# meme cause, chemins et numeros de ligne differents : l empreinte doit coller
WA = "check: AssertionError: longueur apres 100 @ C:/Users/a/mytest.jl:14"
WB = "check: AssertionError: longueur apres 100 @ D:/autre/mytest.jl:31"
exiger(bench._cle_echec(WA) == bench._cle_echec(WB),
       "meme cause, chemins differents -> MEME empreinte")
exiger(bench._cle_echec(WA) != bench._cle_echec(W2),
       "causes differentes -> empreintes differentes")
H3 = [{"tour": 1, "why": WA, "cle": bench._cle_echec(WA)},
      {"tour": 2, "why": WB, "cle": bench._cle_echec(WB)}]
b3 = bench._bloc_retour(2, H3, [], False)
exiger("SAME FAILURE AS ATTEMPT 1" in b3, "la repetition est NOMMEE au modele")

print("=== 9bis. un tour COUPE n est pas un tour JUGE ===")
# Mesure du 22/08, t31 rep3 : le tour 1 est tombe sur le delai de 600 s et le
# bloc annoncait au tour 2 "le verificateur a lance votre solution et
# rapporte : timeout tour 600s". Le verificateur n avait jamais tourne.
jrnl = os.path.join(ws, "fixture_julia_calls.log")
io.open(jrnl, "w", encoding="utf-8", newline=chr(10)).write(
    "--version" + chr(10) + '-e "include(solution.jl)"' + chr(10))
coupe = bench._bloc_retour(1, [{"tour": 1, "why": "timeout tour 600s",
                                "cle": "timeout tour 600s"}], [], False, jrnl)
exiger("CUT OFF" in coupe, "la coupure est nommee comme telle")
exiger("The checker ran your solution.jl" not in coupe,
       "KNOWN-BAD : le bloc ne dit plus que le verificateur a tourne")
exiger("NO verdict" in coupe, "l absence de verdict est dite explicitement")
exiger("you invoked julia 2 time(s)" in coupe,
       "le journal du shim fournit ce qui est REELLEMENT su")
exiger("include(solution.jl)" in coupe, "la derniere commande julia est citee")

vide = os.path.join(ws, "fixture_vide.log")
io.open(vide, "w", encoding="utf-8", newline=chr(10)).write("")
zero = bench._bloc_retour(1, [{"tour": 1, "why": "timeout tour 600s",
                               "cle": "timeout tour 600s"}], [], False, vide)
exiger("ZERO times" in zero, "zero execution est un signal, pas un blanc")
absent = bench._bloc_retour(1, [{"tour": 1, "why": "timeout tour 600s",
                                 "cle": "timeout tour 600s"}], [], False,
                            os.path.join(ws, "pas-de-journal.log"))
exiger("ZERO times" not in absent and "you invoked julia" not in absent,
       "KNOWN-BAD : journal ABSENT -> aucun compte affirme")

# Le bras normal, lui, ne doit pas avoir bouge.
juge = bench._bloc_retour(1, [{"tour": 1, "why": "check: LoadError: X",
                               "cle": "check: loaderror: x"}], [], False, jrnl)
exiger("The checker ran your solution.jl" in juge and "CUT OFF" not in juge,
       "un vrai verdict reste presente comme un verdict")

# Deux coupures ont la MEME empreinte : sans garde, le bloc reprocherait au
# modele un correctif sans effet sur un tour qui n a jamais ete juge.
deux = bench._bloc_retour(2, [{"tour": 1, "why": "timeout tour 600s",
                               "cle": "timeout tour 600s"},
                              {"tour": 2, "why": "timeout tour 600s",
                               "cle": "timeout tour 600s"}], [], False, jrnl)
exiger("SAME FAILURE" not in deux,
       "KNOWN-BAD : deux coupures ne sont pas deux fois la meme erreur")
exiger("cut off by the time limit -- no verdict" in deux,
       "l historique etiquette la coupure au lieu de la lister comme essai")


print("=== 9ter. le budget est DIT, et il est dit aux deux bras ===")
# Mesure du 22/08, t31 six fois : 6 tours sur 16 coupes au delai et 4 runs
# sur 6 perdant leur premier tour, alors que RIEN dans l enonce ne disait au
# modele qu il avait 10 minutes. Et le preambule de boucle n allait qu au
# bras AVEC recherche : la comparaison portait deux differences, pas une.
pa = bench.preambule_boucle(3, 600, web=True)
ps = bench.preambule_boucle(3, 600, web=False)
exiger("at most 3 attempt(s)" in pa and "at most 3 attempt(s)" in ps,
       "le nombre de tentatives est dit aux DEUX bras")
exiger("CUT OFF after 10 minutes" in ps,
       "le budget en minutes est dit au bras SANS recherche aussi")
exiger("no verdict" in ps,
       "et ce qu une coupure signifie -- pas un echec, une absence de verdict")
exiger("Do NOT run a web search" in pa and "Do NOT run a web search" not in ps,
       "KNOWN-BAD : seule la phrase sur la recherche depend du bras")
exiger(pa.replace(pa[pa.index("Do NOT run a web search") - 2:], "") == ps.rstrip(chr(10)),
       "hors cette phrase, les deux bras lisent le MEME preambule")
p20 = bench.preambule_boucle(2, 1200, web=False)
exiger("at most 2 attempt(s)" in p20 and "CUT OFF after 20 minutes" in p20,
       "les nombres viennent des reglages, ils ne sont pas ecrits en dur")

H = [{"tour": 1, "why": "check: LoadError: X", "cle": "check: loaderror: x"}]
b2 = bench._bloc_retour(1, H, [], False, None, 3)
b3 = bench._bloc_retour(2, H + [{"tour": 2, "why": "check: Y", "cle": "check: y"}],
                        [], False, None, 3)
exiger("This is attempt 2 of at most 3." in b2, "le bloc dit ou on en est")
exiger("LAST ONE" not in b2, "KNOWN-BAD : la 2e sur 3 n est pas la derniere")
exiger("This is attempt 3 of at most 3." in b3 and "LAST ONE" in b3,
       "la derniere tentative est annoncee comme telle")
muet = bench._bloc_retour(1, H, [], False, None, None)
exiger("This is attempt" not in muet,
       "KNOWN-BAD : sans plafond connu, le bloc n en invente pas un")


print("=== 9quater. l empreinte de l enonce ===")
# Sans elle, "ces deux campagnes sont comparables" est un souvenir. Le 23/08
# il a fallu retirer une comparaison publiee pour cette raison exacte.
pa3 = bench.preambule_boucle(3, 600, web=True)
ps3 = bench.preambule_boucle(3, 600, web=False)
exiger(bench.empreinte_enonce(pa3 + base) == bench.empreinte_enonce(pa3 + base),
       "meme texte -> meme empreinte")
exiger(bench.empreinte_enonce(pa3 + base) != bench.empreinte_enonce(ps3 + base),
       "les deux BRAS ont deux empreintes -- la difference est nommable")
exiger(bench.empreinte_enonce(ps3 + base)
       != bench.empreinte_enonce(bench.preambule_boucle(2, 600, False) + base),
       "changer le nombre de tentatives change l empreinte")
exiger(bench.empreinte_enonce(ps3 + base)
       != bench.empreinte_enonce(ps3 + base + " "),
       "KNOWN-BAD : un seul caractere de plus suffit a la faire changer")
exiger(len(bench.empreinte_enonce(base)) == 12,
       "l empreinte est courte -- elle se lit dans un tableau")


print("=== 10. le prefixe stable n est pas touche (le cache vaut 85 %) ===")
base = "ENONCE STABLE DE LA TACHE" + chr(10)
t1 = base + b2
t2 = base + b3
exiger(t1.startswith(base) and t2.startswith(base),
       "le bloc est APPENDU, l enonce de base reste en tete")
exiger(t1[:len(base)] == t2[:len(base)],
       "le prefixe est IDENTIQUE d un tour a l autre")

print()
if echecs:
    print("FIXTURE EN ECHEC : %d" % len(echecs))
    for e in echecs:
        print("  - %s" % e)
    sys.exit(1)
print("FIXTURE OK -- la branche d injection est parcourue et verifiee.")
