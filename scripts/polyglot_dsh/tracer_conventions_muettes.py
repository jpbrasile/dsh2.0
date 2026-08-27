# -*- coding: utf-8 -*-
"""TRACE les echecs dus a une CONVENTION DE FORMAT que l'enonce ne dit pas.

LE CAS FONDATEUR (27/08, R28i). `go/beer-song` a echoue sur un seul caractere :

    got:"...5 bottles of beer on the wall.\\n"
   want:"...5 bottles of beer on the wall.\\n\\n"

`Verses` doit poser une ligne vide APRES le dernier couplet. L'enonce ne le dit
pas -- il affiche la chanson rendue, ou le dernier couplet n'est evidemment
suivi de rien. Les 5 cas de `Verse` et les 2 cas d'erreur passaient : la
LOGIQUE etait juste, la CONVENTION etait muette.

CE QUE CE SCRIPT N'EST PAS. Ce n'est pas `contrat_muet.py`, qui demande si
l'enonce cite les identifiants du stub. Ce critere-la ne peut, par
construction, rien dire de la FORME DE LA VALEUR DE RETOUR -- separateur final,
ordre, casse, arrondi. C'est le troisieme biais nomme en R28i, et celui-ci le
mesure au lieu de le supposer : il part de l'echec reel, pas de l'enonce.

D'OU VIENT LA MATIERE. Chaque tour du journal porte desormais `erreurs`, la
sortie du JUGE (correctif du 27/08, commit 41c9934). Rien n'est rejoue, rien
n'est modifie, aucun conteneur n'est sollicite : on lit des fichiers deja
ecrits. Un run anterieur au correctif n'a pas ce champ ; il est signale comme
tel plutot que devine.

LA CLASSIFICATION EST MECANIQUE, et elle se trompe dans les deux sens :
  - `blancs`  : got et want deviennent identiques une fois TOUS les blancs
                retires. La logique est juste, seul le format differe.
  - `casse`   : identiques une fois la casse ignoree (blancs deja retires).
  - `ordre`   : memes lignes, pas dans le meme ordre.
  - `fond`    : rien de tout ca -- l'echec n'est pas un probleme de format.
Un exercice peut avoir des cas de plusieurs classes ; on retient la PLUS
FAVORABLE a l'agent trouvee sur ses cas, et le compte des autres est ecrit.

USAGE PREVU -- ET CE QUI EST EXCLU. Le fichier produit alimente
BONNES_PRATIQUES_CONVENTIONS.md, qui s'accumule A COTE DU BANC et servira plus
tard. Il n'est PAS reinjecte dans un run de la variante D : cette convention
est DERIVEE DE LA SUITE CACHEE, et la variante D mesure precisement ce qu'un
agent trouve SANS information complementaire. La lui donner ne fait pas monter
son score, ca CASSE L'INSTRUMENT DE MESURE (decision de l'operateur, 27/08).
S'en servir un jour, ce sera dans un bras distinct, etiquete comme tel, et qui
ne se compare ni a la variante D ni au banc aider.
"""
import collections
import glob
import io
import json
import os
import re
import sys

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")
ICI = os.path.dirname(os.path.abspath(__file__))

# Comment chaque chaine de test annonce l'attendu et l'obtenu. Une seule
# expression par famille, et on garde le NOM de celle qui a mordu : un echec
# classe sans qu'on sache par quel motif ne serait pas verifiable.
MOTIFS = [
    # go : t.Fatalf("...\n got:%q\nwant:%q", ...)
    ("go/got-want", re.compile(
        r'\bgot\s*:\s*(?P<got>"(?:[^"\\]|\\.)*")\s*\n\s*want\s*:\s*'
        r'(?P<want>"(?:[^"\\]|\\.)*")', re.M)),
    # rust : assert_eq!  ->  left: `...`, right: `...`
    ("rust/left-right", re.compile(
        r'left:\s*`(?P<got>(?:[^`\\]|\\.)*)`\s*,?\s*\n?\s*right:\s*'
        r'`(?P<want>(?:[^`\\]|\\.)*)`', re.M)),
    # jest / vitest : Expected: ...  Received: ...
    ("js/expected-received", re.compile(
        r'Expected:\s*(?P<want>.+?)\n\s*Received:\s*(?P<got>.+?)\n', re.S)),
    # junit : expected: <...> but was: <...>
    ("java/expected-butwas", re.compile(
        r'expected:\s*<(?P<want>.*?)>\s*but was:\s*<(?P<got>.*?)>', re.S)),
    # pytest : assert X == Y
    ("py/assert-eq", re.compile(
        r'^E\s+assert\s+(?P<got>.+?)\s*==\s*(?P<want>.+?)$', re.M)),
]

BLANCS = re.compile(r"\s+")

# ECHEC DE CONTRAT : la suite officielle ne COMPILE PAS contre la solution.
# L'agent a invente une API -- autre nom, autre arite, autre type -- alors que
# le stub la declarait. C'est une famille distincte de l'echec de forme : la
# forme se corrige au dernier caractere, le contrat invalide tout le fichier.
# Le libelle dit ce qu'il faut retenir, pas ce que le juge attendait.
SIGNATURES = [
    (re.compile(r"undefined:\s*(\w+)"),
     "identifiant %s absent : la suite officielle l'appelle, la solution ne "
     "l'exporte pas (nom, casse, ou fonction jamais ecrite)"),
    (re.compile(r"cannot find symbol\s*\n?\s*symbol:\s*\w+\s+(\w+)"),
     "symbole %s introuvable cote java : signature publique differente de "
     "celle du stub"),
    (re.compile(r"no member named '(\w+)'"),
     "membre %s absent de la classe : la suite officielle l'appelle"),
    (re.compile(r"no method named `(\w+)`"),
     "methode %s absente : la suite officielle l'appelle"),
    (re.compile(r"(?:too many|not enough) arguments (?:in call )?to (\S+)"),
     "arite de %s differente de celle que la suite officielle appelle"),
    (re.compile(r"cannot use .+ as (\S+) value"),
     "type de retour ou de parametre incompatible : la suite attend %s"),
    (re.compile(r"is not a type|expected type, found"),
     "type public attendu par la suite officielle, non declare"),
]


# REJET UNIFORME : la solution a refuse TOUTES les entrees officielles avec le
# MEME message, sorti de sa propre validation. Elle n'a pas calcule faux, elle
# n'a pas su LIRE -- la convention d'ENTREE differe de celle qu'elle attend.
# C'est une troisieme famille, distincte de la forme du RESULTAT (blancs,
# casse, ordre) et du CONTRAT public (signature).
REJETS = [
    re.compile(r"returned error\s+(?P<msg>.+?)\s*$", re.M),        # go
    re.compile(r"unexpected exception:?\s*(?P<msg>.+?)\s*$", re.M),  # junit
    re.compile(r"^E\s+(?P<msg>\w*Error:.+?)\s*$", re.M),           # pytest
    re.compile(r"panicked at [`'\"](?P<msg>.+?)[`'\"]", re.M),     # rust
    re.compile(r"^\s*(?P<msg>\w*Error:.+?)\s*$", re.M),            # jest
]


def rejet_uniforme(texte):
    """Rend (message, nombre) quand au moins TROIS cas ont ete refuses avec le
    MEME message, ou None.

    Le seuil de trois et l'unicite du message sont ce qui rend l'inference
    defendable : un bug de logique produit des ecarts VARIES ; un refus
    identique sur tous les cas, y compris les triviaux, ne peut venir que de
    la lecture de l'entree. En dessous de trois cas, on ne conclut pas.
    """
    for motif in REJETS:
        msgs = [m.group("msg").strip() for m in motif.finditer(texte)]
        if len(msgs) >= 3 and len(set(msgs)) == 1:
            return msgs[0], len(msgs)
    return None


def contrat_rompu(texte):
    """Nomme la rupture de contrat, ou None. Ne devine pas : si aucun motif ne
    mord, on ne dit rien plutot que d'inventer une cause."""
    for motif, libelle in SIGNATURES:
        m = motif.search(texte)
        if m:
            return libelle % (m.group(1) if m.groups() else "") if "%s" \
                in libelle else libelle
    return None


def deguillemete(s):
    """Rend le texte que le motif a capture, guillemets et echappements go/rust
    compris. On ne devine pas : si l'echappement n'est pas lisible, on garde le
    brut, et la comparaison se fera dessus."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except Exception:
            s = s[1:-1]
    return (s.replace("\\n", "\n").replace("\\t", "\t")
             .replace('\\"', '"').replace("\\\\", "\\"))


def classer(got, want):
    if got == want:
        return "identiques"          # ne devrait pas arriver sur un echec
    a, b = BLANCS.sub("", got), BLANCS.sub("", want)
    if a == b:
        return "blancs"
    if a.lower() == b.lower():
        return "casse"
    la = sorted(x for x in got.splitlines() if x.strip())
    lb = sorted(x for x in want.splitlines() if x.strip())
    if la and la == lb:
        return "ordre"
    return "fond"


RANG = {"blancs": 0, "casse": 1, "ordre": 2, "identiques": 3, "fond": 4}


def difference_lisible(got, want):
    """Dit MECANIQUEMENT ce qui separe les deux, sans reveler l'attendu."""
    if want.startswith(got):
        q = want[len(got):]
        return ("l'attendu prolonge l'obtenu de %d caractere(s) : %s"
                % (len(q), json.dumps(q)))
    if got.startswith(want):
        q = got[len(want):]
        return ("l'obtenu prolonge l'attendu de %d caractere(s) : %s"
                % (len(q), json.dumps(q)))
    if got.strip() == want.strip():
        return "seuls les blancs de bord different"
    return "les deux chaines divergent en cours de texte"


def injectable(classe, got, want):
    """La phrase qu'on POURRAIT donner a l'agent -- et rien de plus.

    SEPARATION DELIBEREE. Les champs `obtenu` / `attendu` du fichier produit
    portent les valeurs reelles : ils servent au diagnostic humain et ne
    doivent JAMAIS repartir vers l'agent, sinon on lui donne la reponse et le
    bras ne mesure plus rien. Cette fonction ne decrit que la FORME de l'ecart.
    Le futur injecteur ne lira que ce champ-ci : la sobriete est garantie par
    construction, pas par la vigilance.
    """
    if classe == "blancs":
        if want.startswith(got):
            return ("La valeur attendue porte, APRES le dernier element, un "
                    "separateur terminal que ta sortie n'a pas. Verifie ce qui "
                    "suit le dernier element.")
        if got.startswith(want):
            return ("Ta sortie porte un separateur terminal EN TROP apres le "
                    "dernier element.")
        return ("Seuls des blancs separent ta sortie de l'attendu : verifie "
                "espaces, indentation et sauts de ligne.")
    if classe == "casse":
        return "La casse attendue n'est pas celle que tu produis."
    if classe == "ordre":
        return ("Les memes lignes sont attendues, dans un ORDRE different de "
                "celui que tu produis.")
    return None


# La bonne pratique attachee a chaque verdict. Elle vise l'AGENT dans un futur
# bras -- jamais le run en cours -- et ne cite aucune valeur attendue.
LECONS = {
    "blancs": "Separateur ou blanc terminal : quand une fonction assemble N "
              "elements, « separateur ENTRE » et « separateur APRES CHACUN » "
              "sont deux contrats differents, et un exemple rendu ne les "
              "distingue pas. Sans test, c'est pile ou face.",
    "casse": "Casse du resultat : un exemple d'enonce montre souvent une "
             "phrase, pas la convention. Se caler sur la casse des donnees "
             "d'entree plutot que sur celle de la prose.",
    "ordre": "Ordre du resultat : une collection rendue peut etre attendue "
             "triee ou dans l'ordre de rencontre. L'enonce montre un ordre "
             "sans dire s'il est signifiant.",
    "entree": "Convention d'ENTREE : la solution a refuse tous les cas avec "
              "son propre message, sans rien calculer -- l'ecart est dans la "
              "LECTURE, pas dans le calcul. Deux pieges cumules : l'enonce "
              "montre l'entree RENDUE (alignee, espacee pour l'oeil) alors "
              "que la suite peut PASSER une forme canonique differente ; et "
              "le message d'un test en echec affiche souvent la donnee "
              "d'ORIGINE, pas celle qui a ete transmise. Ecrire un lecteur "
              "tolerant -- separateurs optionnels, indentation ignoree -- et "
              "ne jamais rejeter une entree qu'on n'a pas su lire.",
    "contrat": "Contrat public : la suite officielle compile contre le STUB. "
               "Ne jamais renommer, re-typer ni changer l'arite de ce que le "
               "stub declare, meme si un autre nom parait meilleur. Ajouter a "
               "cote, jamais remplacer.",
    "delai": "Delai : une solution correcte mais non bornee echoue comme une "
             "fausse. Verifier qu'aucune boucle ne depend d'une donnee de "
             "taille inconnue.",
    "compilation": "Compilation : la solution ne se construit pas avec la "
                   "suite officielle. Compiler le fichier livre avant de "
                   "conclure, pas seulement ses propres tests.",
    "fond": "Logique : l'ecart n'est pas de forme. A traiter comme un vrai "
            "echec, pas comme une ambiguite d'enonce.",
    "illisible": "Sortie du juge non reconnue par les motifs : a lire a la "
                 "main avant d'en tirer quoi que ce soit.",
}


def depouiller(run):
    racine = os.path.join(BENCH, run)
    sortie = {"run": run, "sans_champ_erreurs": [], "exercices": []}
    for f in sorted(glob.glob(os.path.join(racine, "*", "exercises",
                                           "practice", "*",
                                           ".dsh.results.json"))):
        d = json.load(io.open(f, encoding="utf-8"))
        if any(d.get("tests_outcomes") or []):
            continue                                  # PASS : rien a tracer
        rel = os.path.relpath(os.path.dirname(f), racine).replace(os.sep, "/")
        cle = rel.replace("/exercises/practice", "")
        tours = d.get("turns") or []
        texte = ""
        for t in tours:
            if t.get("erreurs"):
                texte = t["erreurs"]
        if not texte:
            sortie["sans_champ_erreurs"].append(cle)
            continue

        cas, motif_vu = [], None
        for nom, motif in MOTIFS:
            for m in motif.finditer(texte):
                got = deguillemete(m.group("got"))
                want = deguillemete(m.group("want"))
                cl = classer(got, want)
                cas.append({"classe": cl,
                            "ecart": difference_lisible(got, want),
                            # a donner a l'agent : la FORME seule
                            "injectable": injectable(cl, got, want),
                            # diagnostic humain : ne JAMAIS reinjecter
                            "obtenu": got[:400], "attendu": want[:400]})
                motif_vu = nom
            if cas:
                break

        comptes = collections.Counter(c["classe"] for c in cas)
        rupture = contrat_rompu(texte)
        rejet = rejet_uniforme(texte)
        if cas:
            verdict = min((c["classe"] for c in cas), key=lambda x: RANG[x])
        elif rejet:
            verdict = "entree"
            rupture = ("%d cas refuses avec le MEME message, sorti de sa "
                       "propre validation : %s" % (rejet[1], rejet[0]))
        elif rupture:
            verdict = "contrat"
        elif "TIMEOUT" in texte:
            verdict = "delai"
        elif re.search(r"redeclared|cannot find|error:|erreur|FAILED to compile"
                       r"|compilation", texte, re.I):
            verdict = "compilation"
        else:
            verdict = "illisible"

        sortie["exercices"].append({
            "exercice": cle,
            "verdict": verdict,
            "motif": motif_vu,
            "rupture": rupture,
            "lecon": LECONS.get(verdict),
            "cas_par_classe": dict(comptes),
            "cas": cas[:6],
            "juge_extrait": texte[:600],
        })
    return sortie


def main():
    if len(sys.argv) < 2:
        print("usage : python tracer_conventions_muettes.py <nom-du-run> "
              "[--ecrire]")
        return 2
    run = sys.argv[1]
    doc = depouiller(run)
    ex = doc["exercices"]

    print("=== run %s : %d echec(s) avec sortie du juge ===" % (run, len(ex)))
    if doc["sans_champ_erreurs"]:
        print("  %d echec(s) SANS le champ `erreurs` (run anterieur au "
              "correctif du 27/08) :" % len(doc["sans_champ_erreurs"]))
        for c in doc["sans_champ_erreurs"][:8]:
            print("      %s" % c)
    print("")
    comptes = collections.Counter(e["verdict"] for e in ex)
    for v, n in comptes.most_common():
        print("  %-12s %d" % (v, n))
    print("")
    interessants = [e for e in ex if e["verdict"] in ("blancs", "casse",
                                                      "ordre")]
    print("=== echecs de CONVENTION DE FORMAT : %d ===" % len(interessants))
    for e in interessants:
        print("  %-28s %-8s %s" % (e["exercice"], e["verdict"],
                                   e["cas"][0]["ecart"] if e["cas"] else ""))
    print("")
    entrees = [e for e in ex if e["verdict"] == "entree"]
    print("=== echecs de CONVENTION D'ENTREE : %d ===" % len(entrees))
    for e in entrees:
        print("  %-28s %s" % (e["exercice"], e["rupture"]))
    print("")
    contrats = [e for e in ex if e["verdict"] == "contrat"]
    print("=== echecs de CONTRAT PUBLIC : %d ===" % len(contrats))
    for e in contrats:
        print("  %-28s %s" % (e["exercice"], e["rupture"]))
    print("")
    autres = [e for e in ex if e["verdict"] in ("fond", "delai", "compilation",
                                                "illisible")]
    print("=== autres echecs : %d ===" % len(autres))
    for e in autres:
        print("  %-28s %s" % (e["exercice"], e["verdict"]))
    print("")

    if "--markdown" in sys.argv:
        # Ecrit un FICHIER UTF-8 plutot que d'imprimer : la console Windows est
        # en cp1252 et mangeait les accents et les guillemets francais.
        lignes = []
        for e in ex:
            lignes.append("### `%s` — %s\n" % (e["exercice"], e["verdict"]))
            if e["rupture"]:
                lignes.append("- **Rupture** : %s." % e["rupture"])
            if e["cas"]:
                lignes.append("- **Écart** : %s." % e["cas"][0]["ecart"])
                if e["cas"][0]["injectable"]:
                    lignes.append("- **Forme seule** : %s"
                                  % e["cas"][0]["injectable"])
            if e["lecon"]:
                lignes.append("- **Bonne pratique** : %s" % e["lecon"])
            lignes.append("")
        chemin = os.path.join(ICI, "bonnes_pratiques_%s.md" % run)
        io.open(chemin, "w", encoding="utf-8", newline="\n").write(
            "\n".join(lignes))
        print("markdown -> %s  (%d echec(s))"
              % (os.path.basename(chemin), len(ex)))
        return 0
    print("Ces echecs-la ont une LOGIQUE juste et une CONVENTION muette.")
    print("A reporter dans BONNES_PRATIQUES_CONVENTIONS.md, qui s'accumule A")
    print("COTE du banc. NE PAS les redonner a un run de la variante D : la")
    print("convention vient de la suite cachee, la lui donner casse ce que la")
    print("variante D mesure. Un jour, un BRAS DISTINCT -- pas celui-ci.")

    if "--ecrire" in sys.argv:
        chemin = os.path.join(ICI, "conventions_muettes_%s.json" % run)
        io.open(chemin, "w", encoding="utf-8", newline="\n").write(
            json.dumps(doc, ensure_ascii=False, indent=2))
        print("")
        print("ecrit -> %s" % os.path.basename(chemin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
