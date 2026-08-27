# -*- coding: utf-8 -*-
"""PREDIT, avant qu'ils soient joues, les enonces porteurs d'une ambiguite.

POURQUOI CE SCRIPT EXISTE, ET POURQUOI IL N'EST PAS UNE REFORMULATION.

La question posee le 27/08 : pendant l'attente, faut-il reformuler les enonces
mal poses, ou attendre les echecs ? Reformuler d'avance serait une erreur
MESURABLE : si je lis 225 enonces et reformule ceux que JE juge ambigus, mon
jugement devient le selecteur, et le resultat devient infalsifiable -- un score
plus haut ne dirait pas si de vraies ambiguites ont ete levees ou si 225 blocs
de conseils ont simplement ete ajoutes, ce qui remonte un score tout seul.

Ce script fait l'inverse : il ne touche a AUCUN enonce. Il PREDIT, a partir de
signatures purement structurelles, quels exercices porteront une ambiguite --
et cette prediction est ecrite AVANT que java, javascript, python et rust
tournent. Leurs echecs la testent alors, au lieu de l'illustrer apres coup.

LES QUATRE SIGNATURES, chacune tiree d'un cas REELLEMENT observe le 27/08 :

  S1  vocabulaire multiforme .... un tableau associe un code a un libelle, et
                                  le meme mot apparait ailleurs en prose sous
                                  une AUTRE forme (casse ou pluriel).
                                  Source : go/kindergarten-garden, ou l'agent a
                                  pris « Radish » (tableau) quand la suite
                                  attendait « radishes » (prose, ligne 6).
  S2  sortie rendue multi-ligne . l'enonce montre un bloc de sortie sur
                                  plusieurs lignes. Un separateur TERMINAL y
                                  est invisible a l'oeil.
                                  Source : go/beer-song, un « \\n » final.
  S3  entree decoree ............ l'enonce montre une entree alignee ou espacee
                                  pour la lisibilite. Sa TOKENISATION n'est
                                  jamais dite.
                                  Source : go/connect, dont le harnais retire
                                  tous les espaces avant de transmettre.
  S4  validation muette ......... le stub declare un retour d'ERREUR, et
                                  l'enonce n'emploie aucun mot du champ de
                                  l'erreur. La suite testera pourtant des
                                  entrees invalides.
                                  Source : go/kindergarten-garden, 4 cas.

CE QUE LA PREDICTION VAUT, ET CE QU'ELLE NE VAUT PAS. Une signature n'est pas
une cause : un exercice signale peut tres bien passer, et c'est meme le cas le
plus frequent attendu. La prediction ne se juge donc pas sur « combien de
signales echouent » mais sur l'ECART entre le taux d'echec des signales et
celui des autres. Ce depouillement se fait avec `verifier_prediction.py`, apres
coup, sur des donnees que ce script n'a jamais vues.

USAGE :
    python predire_enonces_ambigus.py [--ecrire]
"""
import collections
import io
import json
import os
import re
import sys

VIERGE = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                      "aider", "tmp.benchmarks", "polyglot-benchmark")
ICI = os.path.dirname(os.path.abspath(__file__))

# --- S1 : tableau code -> libelle -------------------------------------------
# Une ligne de tableau markdown a exactement deux cellules, dont l'une est un
# code court (1 a 3 caracteres, majuscules ou chiffres).
LIGNE_TABLEAU = re.compile(
    r"^\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*$", re.M)
CODE_COURT = re.compile(r"^[A-Z0-9]{1,3}$")
MOT = re.compile(r"[A-Za-z]{3,}")

# --- S2 : bloc de sortie rendue ---------------------------------------------
# On capture l'etiquette du bloc EN PLUS de son contenu : la premiere version
# de S2 signalait 78 exercices sur 225 parce qu'elle attrapait n'importe quel
# bloc de code. Elle ne mesurait donc pas ce qu'elle pretendait mesurer.
BLOC = re.compile(r"^```([^\n]*)\n(.*?)^```", re.M | re.S)
LANGAGES_DE_CODE = {
    "go", "rust", "java", "javascript", "js", "python", "py", "cpp", "c++",
    "c", "sh", "bash", "shell", "console", "json", "yaml", "toml", "xml",
    "html", "sql", "ruby", "elixir", "haskell", "scala", "kotlin", "swift",
}
PONCTUATION_DE_CODE = re.compile(r"[{};=<>()\[\]]")

# --- S3 : entree decoree ----------------------------------------------------
# Une ligne d'un bloc qui est faite de jetons d'un caractere separes par des
# espaces (« . . . . . »), ou qui commence par une indentation croissante.
LIGNE_ESPACEE = re.compile(r"^\s*(?:\S\s+){3,}\S\s*$")

# --- S4 : champ lexical de l'erreur -----------------------------------------
MOTS_ERREUR = re.compile(
    r"\berror\b|\berrors\b|\binvalid\b|\bexception\b|\braise\b|\bthrow\b"
    r"|\bmust be\b|\bfail\b|\billegal\b|\bnot valid\b|\breject\b", re.I)
# Le stub declare-t-il un retour d'erreur ? Un motif par langue, sur la
# SIGNATURE seule -- on ne lit jamais le corps.
#
# TROIS LANGUES SEULEMENT, et c'est une limite du DETECTEUR, pas une propriete
# du corpus. Compte sur les stubs du corpus le 27/08 :
#
#   javascript  124 occurrences de `throw` dans les stubs. Les 124 sont le MEME
#               remplisseur Exercism : « Remove this statement and implement
#               this function ». Signal nul -- la premiere version signalait
#               34 exercices javascript, c'etait 34 fois le gabarit du track.
#   java        46 stubs sur 47 portent `throw new UnsupportedOperationException`
#               -- meme gabarit. Seuls 6 portent un vrai `throws` (alphametics,
#               bank-account, circular-buffer, dominoes, sgf-parsing,
#               tree-building) ; c'est ce motif-la, et lui seul, qui reste.
#   cpp         aucun stub ne porte `throw`.
#   python      aucune declaration d'erreur ne figure dans une signature.
#
# S4 est donc AVEUGLE sur javascript, cpp et python. Le tableau y imprime
# « - », jamais « 0 » : un zero ferait lire une absence de risque la ou il n'y
# a qu'une absence de mesure.
RETOUR_ERREUR = {
    ".go":   re.compile(r"\)\s*\([^)]*\berror\b[^)]*\)|\)\s*error\b"),
    ".rs":   re.compile(r"->\s*Result\s*<"),
    ".java": re.compile(r"\bthrows\s+\w+"),
}
LANGUES_S4 = ("go", "java", "rust")


def enonce(d):
    """Le MEME assemblage que consigne_initiale() du pilote, sans l'addendum."""
    txt = ""
    for nom in ("introduction.md", "instructions.md", "instructions.append.md"):
        p = os.path.join(d, ".docs", nom)
        if os.path.exists(p):
            txt += io.open(p, encoding="utf-8", errors="replace").read()
    return txt


def stubs(d):
    """Les fichiers que l'agent peut editer, d'apres .meta/config.json."""
    p = os.path.join(d, ".meta", "config.json")
    if not os.path.exists(p):
        return []
    try:
        cfg = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return []
    return cfg.get("files", {}).get("solution", []) or []


def s1_vocabulaire_multiforme(txt):
    """Un tableau code -> libelle, et le libelle ailleurs sous une autre forme.

    Etroit a dessein : on exige que le mot du tableau et celui de la prose
    partagent un prefixe d'au moins quatre lettres SANS etre identiques. Deux
    mots differents ne declenchent pas ; le meme mot a l'identique non plus.
    """
    libelles = []
    for a, b in LIGNE_TABLEAU.findall(txt):
        for code, lib in ((a, b), (b, a)):
            if CODE_COURT.match(code) and MOT.fullmatch(lib.strip()):
                libelles.append(lib.strip())
    if not libelles:
        return None
    prose = MOT.findall(txt)
    trouves = []
    for lib in libelles:
        bas = lib.lower()
        for m in prose:
            mb = m.lower()
            if mb != bas and mb[:4] == bas[:4] and len(bas) >= 4:
                trouves.append("%s / %s" % (lib, m))
                break
    if not trouves:
        return None
    return "tableau code->libelle, et le libelle ailleurs sous une autre " \
           "forme : %s" % ", ".join(sorted(set(trouves))[:4])


def blocs_non_code(txt):
    """Les blocs qui montrent une DONNEE, pas du code.

    Deux filtres, et les deux sont necessaires : l'etiquette du bloc (```go
    n'est pas une sortie rendue) et la ponctuation (une ligne sur deux portant
    des accolades ou des parentheses est du code, quelle que soit
    l'etiquette).
    """
    out = []
    for etiquette, corps in BLOC.findall(txt):
        if etiquette.strip().lower() in LANGAGES_DE_CODE:
            continue
        lignes = [l for l in corps.splitlines() if l.strip()]
        if not lignes:
            continue
        codeuses = sum(1 for l in lignes if PONCTUATION_DE_CODE.search(l))
        if codeuses * 5 > len(lignes):        # plus de 20 % : c'est du code
            continue
        out.append(lignes)
    return out


def s2_sortie_rendue(txt):
    for lignes in blocs_non_code(txt):
        if len(lignes) >= 4:
            return ("bloc de sortie rendue sur %d lignes, sans ponctuation de "
                    "code : un separateur TERMINAL y est invisible"
                    % len(lignes))
    return None


def s3_entree_decoree(txt):
    for lignes in blocs_non_code(txt):
        espacees = [l for l in lignes if LIGNE_ESPACEE.match(l)]
        indentees = [l for l in lignes if l.startswith(" ")]
        if len(espacees) >= 3 or (len(lignes) >= 3 and
                                  len(indentees) >= len(lignes) - 1 >= 2):
            return ("entree presentee alignee/espacee pour l'oeil (%d ligne(s)"
                    " concernee(s)) : sa tokenisation n'est pas dite"
                    % max(len(espacees), len(indentees)))
    return None


def s4_validation_muette(txt, d, sol):
    if MOTS_ERREUR.search(txt):
        return None
    for f in sol:
        ext = os.path.splitext(f)[1]
        motif = RETOUR_ERREUR.get(ext)
        p = os.path.join(d, f)
        if not motif or not os.path.exists(p):
            continue
        code = io.open(p, encoding="utf-8", errors="replace").read()
        if motif.search(code):
            return ("le stub %s declare un retour d'erreur, et l'enonce "
                    "n'emploie AUCUN mot du champ de l'erreur" % f)
    return None


def main():
    lignes, comptes = [], collections.Counter()
    total_langue = collections.Counter()
    total = 0
    for lang in sorted(os.listdir(VIERGE)):
        base = os.path.join(VIERGE, lang, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            d = os.path.join(base, ex)
            if not os.path.isdir(d):
                continue
            total += 1
            total_langue[lang] += 1
            txt, sol = enonce(d), stubs(d)
            sig = {}
            for nom, val in (("S1", s1_vocabulaire_multiforme(txt)),
                             ("S2", s2_sortie_rendue(txt)),
                             ("S3", s3_entree_decoree(txt)),
                             ("S4", s4_validation_muette(txt, d, sol))):
                if val:
                    sig[nom] = val
                    comptes[nom] += 1
            if sig:
                lignes.append({"exercice": "%s/%s" % (lang, ex),
                               "signatures": sig})

    print("=== PREDICTION : %d exercice(s) signale(s) sur %d ==="
          % (len(lignes), total))
    base_s4 = sum(total_langue[lg] for lg in LANGUES_S4)
    for nom in ("S1", "S2", "S3", "S4"):
        base = base_s4 if nom == "S4" else total
        print("  %s  %3d  (%.0f %% de %d%s)"
              % (nom, comptes[nom], 100.0 * comptes[nom] / base, base,
                 "" if nom != "S4" else
                 " -- %s seulement, S4 est aveugle ailleurs"
                 % "+".join(LANGUES_S4)))
    print("")
    # Par langue : une signature concentree sur un seul track dit quelque chose
    # du track, pas des enonces. Sans ce tableau on le croirait general.
    parl = collections.defaultdict(collections.Counter)
    for e in lignes:
        for s in e["signatures"]:
            parl[e["exercice"].split("/")[0]][s] += 1
    print("  %-12s %s" % ("langue", "  ".join("%-4s" % s
                                              for s in ("S1", "S2", "S3", "S4"))))
    for lg in sorted(total_langue):
        cells = []
        for s in ("S1", "S2", "S3", "S4"):
            if s == "S4" and lg not in LANGUES_S4:
                cells.append("%-4s" % "-")      # aveugle, pas zero
            else:
                cells.append("%-4d" % parl[lg][s])
        print("  %-12s %s" % (lg, "  ".join(cells)))
    print("")
    combos = collections.Counter(
        "+".join(sorted(e["signatures"])) for e in lignes)
    for c, n in combos.most_common(10):
        print("  %-14s %d" % (c, n))
    print("")
    # Controle sur les trois cas connus : une prediction qui ne retrouve pas
    # ce qui a deja echoue ne vaut rien.
    connus = {"go/beer-song": "S2", "go/connect": "S3",
              "go/kindergarten-garden": "S1"}
    print("=== controle sur les 3 echecs deja observes ===")
    par_ex = {e["exercice"]: e["signatures"] for e in lignes}
    for k, attendu in sorted(connus.items()):
        vu = sorted(par_ex.get(k, {}))
        etat = "ok" if attendu in vu else "MANQUE %s" % attendu
        print("  %-26s %-12s %s" % (k, ",".join(vu) or "-", etat))
    print("")
    print("Une signature n'est PAS une cause. La prediction ne se juge pas sur")
    print("le nombre de signales qui echouent, mais sur l'ECART entre le taux")
    print("d'echec des signales et celui des autres -- depouille apres coup.")

    if "--ecrire" in sys.argv:
        doc = {"total_corpus": total, "comptes": dict(comptes),
               "exercices": lignes}
        p = os.path.join(ICI, "prediction_enonces_ambigus.json")
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(doc, ensure_ascii=False, indent=2))
        print("")
        print("ecrit -> %s" % os.path.basename(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
