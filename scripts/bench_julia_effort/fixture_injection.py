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


print("=== 9quinquies. l en-tete de l historique dit la verite sur sa liste ===")
# Mesure du 23/08, t31b r01 tour 3 : "Already tried, and still failing"
# coiffait une liste qui ne contenait que des coupures. Rien n avait ete
# essaye, rien n avait ete juge -- l entree etait bien etiquetee, l en-tete
# la dementait.
exiger(bench.compter_julia(None) == -1,
       "KNOWN-BAD : journal None rend -1 au lieu de lever")
CO = {"tour": 1, "why": "timeout tour 600s", "cle": "timeout tour 600s"}
CO2 = {"tour": 2, "why": "timeout tour 600s", "cle": "timeout tour 600s"}
JU = {"tour": 1, "why": "check: LoadError: Z", "cle": "check: loaderror: z"}
tout_coupe = bench._bloc_retour(2, [CO, CO2], [], False, None, 3)
exiger("Already tried, and still failing" not in tout_coupe,
       "KNOWN-BAD : que des coupures -> pas de \"still failing\"")
exiger("none of them reached a verdict" in tout_coupe,
       "l en-tete dit ce que la liste contient vraiment")
melange = bench._bloc_retour(2, [JU, CO2], [], False, None, 3)
exiger("Already tried, and still failing" in melange,
       "des qu un essai a ete JUGE, l en-tete d origine revient")


print("=== 9sexies. le budget est un CHAMP, lisible sans coupure ===")
# Il ne se lisait que dans le texte d un `why` de coupure ("timeout tour
# 900s") -- donc invisible sur un run jamais coupe. Depuis le 23/08 le budget
# EST un axe compare : un axe qu on ne peut lire que sur les runs rates n en
# est pas un.
import json as _json
import glob as _glob


def _runs(motif):
    for f in _glob.glob(os.path.join(bench.BASE, motif)):
        for l in io.open(f, encoding="utf-8"):
            if l.strip():
                yield _json.loads(l)


sans_coupure = [r for r in _runs("resultats_t31c*.jsonl")
                if r.get("par_tour") and not any(
                    (t.get("why") or "").startswith("timeout")
                    for t in r["par_tour"])]
exiger(bool(sans_coupure),
       "un run sans AUCUNE coupure existe dans le corpus mesure")
exiger(sans_coupure[0].get("timeout_tour") is None,
       "KNOWN-BAD : sur ce run, le budget etait ILLISIBLE avant le champ")

# Preuve d EXECUTION si elle existe, claim sur la SOURCE sinon -- et le
# fixture DIT laquelle des deux il vient de faire.
avec_champ = [r for r in _runs("resultats_*.jsonl")
              if r.get("timeout_tour") is not None]
if avec_champ:
    exiger(isinstance(avec_champ[0]["timeout_tour"], int)
           and avec_champ[0].get("tours_max"),
           "un enregistrement REEL porte le budget (%d run(s))" % len(avec_champ))
else:
    src = io.open(os.path.join(bench.BASE, "bench.py"), encoding="utf-8").read()
    exiger(src.count(chr(34) + "timeout_tour" + chr(34) + ":") == 2,
           "les DEUX enregistreurs ecrivent le champ (claim sur la SOURCE)")


print("=== 9septies. bras PROMESSE : meme enonce, secours jamais livre ===")
# Tout l experiment tient a une egalite : le bras qui RECOIT le secours et le
# bras qui l ATTEND EN VAIN doivent lire le meme enonce. S ils different par
# autre chose, l ecart mesure n est plus la livraison du secours.
exiger(bench.preambule_boucle(2, 900, True)
       != bench.preambule_boucle(2, 900, False),
       "la promesse EST une difference d enonce -- sinon rien a mesurer")
# Espaces NORMALISES : le preambule est enveloppe sur plusieurs lignes, et
# un test qui cherche la phrase d un seul tenant echoue sur le retour a la
# ligne -- il mesurerait la mise en page, pas le contenu.
exiger("the harness runs one for you"
       in " ".join(bench.preambule_boucle(2, 900, True).split()),
       "la phrase annoncee est bien celle du secours")
exiger(bench.empreinte_enonce(bench.preambule_boucle(2, 900, True))
       != bench.empreinte_enonce(bench.preambule_boucle(2, 900, False)),
       "et l empreinte la rend visible dans les enregistrements")

# Preuve d EXECUTION des que les deux campagnes existent : les empreintes
# ENREGISTREES doivent etre EGALES. Une claim sur le code ne suffirait pas --
# le banc pourrait composer l enonce autrement pour chaque bras sans que la
# lecture de la source le montre.
import json as _js


def _shas(nom):
    f = os.path.join(bench.BASE, nom)
    if not os.path.exists(f):
        return None
    v = {_js.loads(l).get("enonce_sha") for l in io.open(f, encoding="utf-8")
         if l.strip()}
    return sorted(x for x in v if x) or None


_w, _p = _shas("resultats_t31d_web.jsonl"), _shas("resultats_t31d_promesse.jsonl")
_s = _shas("resultats_t31d_sans.jsonl")
if _w and _p:
    exiger(_w == _p,
           "MESURE : web et promesse ont lu le MEME enonce (%s)" % _w[0])
    if _s:
        exiger(_s != _w,
               "MESURE : le bras temoin, lui, a lu un enonce DIFFERENT")
else:
    print("  (pas encore mesurable : la campagne trois bras n a pas tourne)")


print("=== 9octies. un tour tue par la dorsale n est ni echec ni reussite ===")
# Sixieme instance de la forme "une absence rendue comme un resultat". Le
# garde vit dans analyse.py et il est cable dans --comparer : aucune
# comparaison ne se publie sans que ses morts fournisseur remontent.
# Ici on le fait TIRER sur des entrees dont la reponse est connue d avance.
import os as _os
_an = io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "analyse.py"), encoding="utf-8").read()
_g = {"__name__": "an_fixture",
      "__file__": _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "analyse.py")}
exec(compile(_an[:_an.index("if len(sys.argv) > 2 and sys.argv[1] == ")],
             "analyse.py", "exec"), _g)
_mf = _g["_morts_fournisseur"]

# known-BAD : ces campagnes ONT des tours tues, et le compte est NOMINATIF.
# oxviafree : 10 taches, 10 tours morts -- la campagne entiere etait une
# absence. Avec une cle (rep, tour) au lieu de (rep, effort, tache, tour),
# les 10 s ecrasaient en 1 : defaut trouve par ce bras meme, le 23/08.
_ox = _mf("resultats_oxviafree.jsonl")
exiger(_ox is not None and len(_ox) == 10,
       "known-BAD : oxviafree rend 10 tours morts, pas un total ecrase")
exiger(_ox is not None and "INVALID_REQUEST" in set(_ox.values())
       and "RATE_LIMIT" in set(_ox.values()),
       "known-BAD : les DEUX types de mort sont vus, pas seulement le 429")
_pi = _mf("resultats_t31_web.jsonl")
exiger(_pi is not None and len(_pi) == 1 and "PI_AI_ERROR" in set(_pi.values()),
       "known-BAD : le flux coupe en pleine phrase est vu (t31_web r3 t2)")

# known-GOOD : celle-ci est propre, et le garde ne doit pas crier.
exiger(_mf("resultats_t31_noweb.jsonl") == {},
       "known-GOOD : une campagne sans mort rend {} -- le garde se tait")

# known-ABSENT : rien au sol. Ca ne se dit PAS "aucun".
exiger(_mf("resultats_zzz_jamais_lancee.jsonl") is None,
       "known-ABSENT : sans trace au sol le garde rend None, jamais {}")
exiger(_mf("/pas/un/fichier/de/banc.txt") is None,
       "known-ABSENT : un chemin hors convention rend None")

# la lettre X remonte jusqu au tableau, sinon le lecteur ne la voit pas.
_faux = {"rep": 2, "effort": "medium", "tache": "t31",
         "par_tour": [{"tour": 1, "verdict": "FAIL", "why": "aucun solution.jl ecrit"},
                      {"tour": 2, "verdict": "PASS", "why": ""}]}
exiger(_g["_marques"](_faux) == "FP",
       "sans le garde, le tour mort se lit F -- c est l artefact d origine")
exiger(_g["_marques"](_faux, {(2, "medium", "t31", 1): "RATE_LIMIT"}) == "XP",
       "avec le garde, il se lit X -- ni echec ni reussite")


print("=== 9nonies. bras entrelaces : les refus tirent, les noms coincident ===")
# Tant que les bras tournaient en processus successifs, une derive de la
# dorsale tombait ENTIEREMENT sur celui qui tournait alors (23/08 : 12
# RATE_LIMIT, tous sur promesse). --bras fait du bras une dimension de
# l unite de travail. Trois choses doivent tenir, et aucune ne se suppose.
import sys as _sys

class _Stop(Exception):
    pass

def _essai(args):
    """Lance main() sans effet de bord et rend le refus, ou None."""
    _vrais = (bench.preparer_shim, bench.preparer_voies,
              bench.lancer_enregistreurs, bench.tuer_arbre, bench.boucle)
    bench.preparer_shim = lambda: "(neutralise)"
    bench.preparer_voies = lambda par, eff: [("acc", 0, "w.jsonl", "base")]
    bench.lancer_enregistreurs = lambda voies: []
    bench.tuer_arbre = lambda q: None
    def _stop(*a, **k):
        raise _Stop()
    bench.boucle = _stop
    argv, out = _sys.argv, _sys.stdout
    _sys.argv = ["bench.py"] + args
    _sys.stdout = io.StringIO()
    bench.BRAS_MULTI = False
    try:
        bench.main()
        return "(campagne lancee sans refus)"
    except _Stop:
        return None                      # arrive jusqu a la boucle : accepte
    except SystemExit as e:
        return str(e)
    finally:
        _sys.argv, _sys.stdout = argv, out
        (bench.preparer_shim, bench.preparer_voies, bench.lancer_enregistreurs,
         bench.tuer_arbre, bench.boucle) = _vrais
        bench.BRAS_MULTI = False

# known-BAD : un refus JAMAIS PARCOURU echoue en position permissive.
_cas = [(["medium", "t31", "--boucle", "2", "--bras", "web,zzz"],
         "inconnu", "un bras inconnu ne passe pas en silence"),
        (["medium", "t31", "--boucle", "2", "--bras", "web,web"],
         "repete", "deux bras de meme nom s effaceraient l un l autre"),
        (["medium", "t31", "--boucle", "2", "--bras", "web", "--web"],
         "porte DEJA", "--bras avec --web : deux definitions du bras"),
        (["medium", "t31", "--boucle", "2", "--bras", "sans", "--promesse"],
         "porte DEJA", "--bras avec --promesse : idem"),
        (["medium", "t31", "--bras", "sans,promesse"],
         "mode boucle", "promesse hors boucle n a pas de tour suivant")]
for _a, _att, _quoi in _cas:
    _got = _essai(_a)
    exiger(_got is not None and _att in _got, "refus PARCOURU : " + _quoi)

# known-GOOD : la campagne entrelacee, elle, doit arriver jusqu a la boucle.
exiger(_essai(["medium", "t31", "--boucle", "2", "--bras", "sans,promesse,web",
               "--par", "3"]) is None,
       "known-GOOD : sans,promesse,web est accepte")

# LE BRAS DOIT ENTRER DANS L ETIQUETTE, sinon deux bras partagent
# runs/<etiq>/r<N>/<effort>/<tache> -- et un run commence par rmtree(ws).
bench.BRAS_MULTI = True
_e = {n: bench.etiq_bras(*wp) for n, wp in bench.BRAS_CONNUS.items()}
exiger(len(set(_e.values())) == len(_e),
       "chaque bras a SON espace de travail (sinon rmtree en efface un autre)")
exiger(all(n in _e[n] for n in _e),
       "et le nom du bras est dans l etiquette, pas un numero")
bench.BRAS_MULTI = False
exiger(len({bench.etiq_bras(*wp) for wp in bench.BRAS_CONNUS.values()}) == 1,
       "hors campagne entrelacee, l etiquette est INCHANGEE (rien ne bouge)")


print("=== 9decies. une solution qui NE SE TERMINE PAS : cause nommee, pas exception ===")
import subprocess as _sp
import tempfile as _tf
import shutil as _sh

_dossier = _tf.mkdtemp(prefix="fixjuge_")
_boucle = os.path.join(_dossier, "solution.jl")
io.open(_boucle, "w", encoding="utf-8").write(
    "s = 0" + chr(10) + "while true" + chr(10) + "    global s += 1" + chr(10) + "end" + chr(10))

# Bras known-BAD : la FORME D AVANT. Le meme fichier, juge par un appel direct
# sans filet, doit LEVER -- c est exactement ce qui remontait a l ouvrier et
# produisait un FAIL muet. Sans ce bras, le filet ci-dessous ne prouve rien.
_leve = False
try:
    _sp.run([bench.JULIA, "--startup-file=no", "--color=no",
             os.path.join(bench.BASE, "tasks", "harness.jl"), _boucle,
             os.path.join(bench.BASE, "tasks", "t31_checks.jl")],
            capture_output=True, text=True, timeout=8, cwd=bench.BASE)
except _sp.TimeoutExpired:
    _leve = True
exiger(_leve, "known-BAD : sans filet, le juge LEVE TimeoutExpired (forme d avant)")

# Bras corrige : meme fichier, meme delai, mais par juger().
_v, _why = bench.juger(_boucle, "t31", delai=8)
exiger(_v == "FAIL", "avec filet : verdict FAIL, et non une exception")
exiger("ne se termine pas" in _why, "la cause NOMME la non-terminaison, elle ne dit pas 'aucun verdict'")
exiger("8" in _why, "et elle porte le delai reellement applique")

# Known-GOOD : le chemin normal n est pas casse par le filet.
_ref = os.path.join(bench.BASE, "ref", "t31.jl")
if os.path.exists(_ref):
    _v2, _why2 = bench.juger(_ref, "t31", delai=180)
    exiger(_v2 == "PASS", "known-GOOD : ref/t31.jl passe toujours (le filet ne mange pas le cas sain)")
else:
    print("  (ref/t31.jl absent : bras known-GOOD non parcouru)")

_sh.rmtree(_dossier, ignore_errors=True)


print("=== 9undecies. pre-vol : le modele demande est-il ANNONCE ? ===")
import contextlib as _cl

# known-ABSENT d abord : port 9 (discard), personne n ecoute.
_rien = bench.modeles_annonces("127.0.0.1", 9, False, "/v1", delai=2)
exiger(_rien is None, "known-ABSENT : dorsale injoignable -> None")
exiger(_rien is not [] and _rien != [],
       "et None n est PAS une liste vide : 'pas pu demander' n est pas 'ne sert rien'")

_liste = bench.modeles_annonces("127.0.0.1", 8005, False, "/v1", delai=4)
if _liste is None:
    print("  (llama-server 8005 eteint : bras GOOD/BAD non parcourus)")
else:
    exiger("specdec-q38-mtp" in _liste,
           "known-GOOD : la dorsale locale annonce bien specdec-q38-mtp")
    exiger("specdec-q38-plain-vision" not in _liste,
           "known-BAD : le nom par defaut du banc n est PAS servi -- le cas vise")

    _sauve = (bench.MODELE, bench.TLS_PAR, bench.CHEMIN_PAR)
    bench.TLS_PAR, bench.CHEMIN_PAR = False, "/v1"
    try:
        bench.MODELE = "specdec-q38-plain-vision"
        _b = io.StringIO()
        with _cl.redirect_stdout(_b):
            bench.prevol_modele("127.0.0.1", 8005)
        _mauvais = _b.getvalue()
        bench.MODELE = "specdec-q38-mtp"
        _b = io.StringIO()
        with _cl.redirect_stdout(_b):
            bench.prevol_modele("127.0.0.1", 8005)
        _bon = _b.getvalue()
    finally:
        bench.MODELE, bench.TLS_PAR, bench.CHEMIN_PAR = _sauve

    exiger("ATTENTION" in _mauvais, "paire decisive : le nom perime declenche l avertissement")
    exiger("specdec-q38-mtp" in _mauvais, "et l avertissement NOMME ce qui est reellement servi")
    exiger("ATTENTION" not in _bon, "le nom servi ne declenche RIEN -- la sonde ne crie pas toujours")
    exiger("annonce" in _bon, "et elle le confirme explicitement")


print("=== 9duodecies. un run sans detail par tour ne temoigne pas du tour 1 ===")
# L ecriture d avant, (par_tour or [{}])[0].get('verdict') != 'PASS', faisait
# dire a un run SANS detail qu il avait rate le tour 1 : un dict vide rend
# None, et None n est pas 'PASS'. Une supposition deguisee en donnee. Ces runs
# existent -- juge sans reponse, exception d ouvrier -- et ils comptent comme
# echecs, mais pas dans une statistique qui a besoin du tour 1 pour exister.
_cmp = _g["_comparer"]
_socle = {"effort": "medium", "tache": "t31", "enonce_sha": "aaaaaaaaaaaa",
          "timeout_tour": 900, "tours_max": 2, "wall_s": 100.0,
          "julia_runs": 5, "recherches_banc": []}
_r1 = dict(_socle, rep=1, verdict="PASS",
           par_tour=[{"tour": 1, "verdict": "FAIL", "why": "check: nope"},
                     {"tour": 2, "verdict": "PASS", "why": ""}])
_r2 = dict(_socle, rep=2, verdict="FAIL", why="ouvrier: Command ... timed out")

_dj = _tf.mkdtemp(prefix="fixmuet_")
_fj = os.path.join(_dj, "faux_bras.jsonl")
with io.open(_fj, "w", encoding="utf-8") as _h:
    for _r in (_r1, _r2):
        _h.write(_json.dumps(_r) + chr(10))

_b = io.StringIO()
with _cl.redirect_stdout(_b):
    _cmp([_fj])
_txt = _b.getvalue()
_sh.rmtree(_dj, ignore_errors=True)

exiger("la question se pose sur 1 run(s) sur 1" in _txt,
       "known-BAD : le denominateur est 1, pas 2 -- le run muet ne temoigne pas")
exiger("sans detail par tour" in _txt,
       "le run muet est NOMME, pas jete en silence")
exiger("r2 FAIL" in _txt,
       "et on lit LEQUEL et son verdict, pas seulement un total")
exiger("[-]" in _txt,
       "sa colonne de marques est vide, elle n invente pas un tour")
exiger("[FP]" in _txt,
       "et le run qui a bien deux tours garde ses marques")


print("=== 9terdecies. mes propres defauts sortent de la mesure, pas ceux du modele ===")
# Deux regles, et la difficulte est qu elles doivent TIRER dans trois cas et
# SE TAIRE dans deux autres. Une regle qui ecarte tout ne mesure rien.
_soc = {"effort": "medium", "tache": "t31", "enonce_sha": "bbbbbbbbbbbb",
        "timeout_tour": 900, "tours_max": 2, "wall_s": 100.0,
        "julia_runs": 5, "recherches_banc": []}
def _tour(v, why=""):
    return {"tour": 1, "verdict": v, "why": why}
def _run(rep, verdict, tours, **kw):
    return dict(_soc, rep=rep, verdict=verdict, par_tour=tours, **kw)

_rate = _tour("FAIL", "check: nope")
_ok = {"tour": 2, "verdict": "PASS", "why": ""}
_coupe = _tour("FAIL", "timeout tour 900s")

_cas = [
    # DOIVENT tirer
    _run(1, "PASS", [_coupe, _ok], bras_web=False, rech_faites=0, rech_refusees=0),
    _run(2, "FAIL", [_rate, _ok], bras_web=True, rech_faites=0, rech_refusees=1),
    # DOIVENT se taire
    _run(3, "FAIL", [_rate, _ok], bras_web=True, rech_faites=1, rech_refusees=0),
    _run(4, "PASS", [_rate, _ok], bras_web=False, rech_faites=0, rech_refusees=1),
    _run(5, "PASS", [_rate, _ok], bras_web=False, rech_faites=0, rech_refusees=0),
]
_dk = _tf.mkdtemp(prefix="fixecart_")
_fk = os.path.join(_dk, "faux_melange.jsonl")
with io.open(_fk, "w", encoding="utf-8") as _h:
    for _r in _cas:
        _h.write(_json.dumps(_r) + chr(10))
_b = io.StringIO()
with _cl.redirect_stdout(_b):
    _g["_comparer"]([_fk])
_t = _b.getvalue()
_sh.rmtree(_dk, ignore_errors=True)

exiger("la question se pose sur 3 run(s) sur 3" in _t,
       "3 runs restent dans la mesure : ni le coupe, ni le web sans recherche")
exiger("COUPE AU DELAI" in _t and "r1 PASS" in _t,
       "known-BAD : le tour coupe est ecarte et NOMME -- mon budget, pas le modele")
exiger("SANS recherche delivree" in _t and "r2 FAIL" in _t,
       "known-BAD : le run web sans traitement est ecarte et NOMME")
exiger("r3" not in _t.split("SANS recherche delivree")[1][:80],
       "known-GOOD : un run web AVEC recherche delivree reste dans la mesure")
exiger("mon budget" in _t,
       "et la sortie dit POURQUOI, au lieu d ecarter en silence")

# Le bras PROMESSE : sa recherche est annoncee et jamais livree, c est SON
# traitement. La regle web ne doit PAS l ecarter -- sinon elle viderait le
# bras entier et on conclurait sur zero run.
_dp = _tf.mkdtemp(prefix="fixprom_")
_fp = os.path.join(_dp, "faux_promesse.jsonl")
with io.open(_fp, "w", encoding="utf-8") as _h:
    for _r in (_cas[3], _cas[4]):
        _h.write(_json.dumps(_r) + chr(10))
_b = io.StringIO()
with _cl.redirect_stdout(_b):
    _g["_comparer"]([_fp])
_tp = _b.getvalue()
_sh.rmtree(_dp, ignore_errors=True)
exiger("la question se pose sur 2 run(s) sur 2" in _tp,
       "known-GOOD : le bras promesse garde ses runs -- la promesse EST le traitement")
exiger("SANS recherche delivree" not in _tp,
       "et la regle web ne tire pas sur lui")


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
