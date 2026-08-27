# -*- coding: utf-8 -*-
"""FIGE la partition du corpus en « enonce auto-suffisant » / « ambigu ».

POURQUOI FIGER, ET POURQUOI MAINTENANT. La variante D juge l'agent sur le seul
enonce. Or >= 31 % des enonces d'exercism ont ete ecrits en supposant le
fichier de test VISIBLE : ils ne disent pas la convention (index a partir de 0
ou de 1, quelle exception, de quel cote on empile). Sur ceux-la on ne mesure
pas l'agent, on mesure un tirage au sort. Publier un taux sur le corpus entier
serait donc melanger deux choses.

Une selection decidee APRES les resultats ne vaut rien. Ce script COMPTE, au
moment ou il tourne, les exercices deja juges, et l'inscrit dans le fichier
produit (`preuve_d_anteriorite`). La partition precede donc tout le reste du
corpus, et c'est verifiable sans me croire sur parole.

LE CRITERE, ET IL N'EST PAS DE MOI. Il est celui de `contrat_muet.py`, importe
ici plutot que recopie -- une seule implementation, donc pas de derive possible
entre le critere publie et la liste figee :

    l'enonce (.docs/*.md) cite-t-il AU MOINS UN des identifiants
    que declare le stub editable ?

Si aucun n'est cite, l'enonce ne dit rien de ce que ces fonctions font, et leur
semantique ne peut venir que du test -- masque en variante D.

CE CRITERE SE TROMPE DANS LES DEUX SENS, et c'est ecrit dans le fichier produit :

  * il SOUS-COMPTE : `go/simple-linked-list` cite `Reverse`, donc il est classe
    auto-suffisant -- alors que l'enonce ne dit nulle part que `Push` ajoute EN
    FIN. C'est le cas qui a revele le probleme (mesure du 27/08, FAIL 141,1 s).
  * il SUR-COMPTE : `cpp/gigasecond` ne cite pas `advance`, donc il est classe
    ambigu -- alors que l'enonce decrit exactement le comportement attendu, et
    qu'il PASSE en variante D (pi_dimD2, PASS 459,7 s).

La partition est donc un instrument mecanique et reproductible, pas une verite.
Elle vaut parce qu'elle est fixee d'avance et qu'on peut la rejouer, pas parce
qu'elle serait exacte. Toute correction ulterieure se lira comme un diff contre
ce fichier.

ETAT DU CORPUS AU MOMENT DU GEL. Les 26 stubs cpp sont SEMES (leurs originaux
sont a cote en `.stub-origine`) : le critere tourne donc sur ce que l'agent voit
vraiment, pas sur un corpus qu'aucun run n'utilise.
"""
import glob
import hashlib
import io
import json
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                      "aider", "tmp.benchmarks", "polyglot-benchmark")
SORTIE = os.path.join(ICI, "sous_ensemble_autosuffisant.json")


def sha(chemin):
    try:
        return hashlib.sha256(open(chemin, "rb").read()).hexdigest()
    except Exception:
        return None


def importer_critere():
    """Importe contrat_muet en avalant son affichage.

    On l'IMPORTE au lieu de recopier ses expressions regulieres : si le critere
    change un jour, la liste figee et le chiffre publie changent ENSEMBLE ou
    pas du tout.
    """
    sys.path.insert(0, ICI)
    vrai = sys.stdout
    sys.stdout = io.StringIO()
    try:
        import contrat_muet
    finally:
        sys.stdout = vrai
    return contrat_muet


def tous_les_exercices():
    out = []
    for langue in ("cpp", "go", "java", "javascript", "python", "rust"):
        base = os.path.join(CORPUS, langue, "exercises", "practice")
        if not os.path.isdir(base):
            continue
        for ex in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, ex)):
                out.append((langue, ex))
    return out


def deja_juges(run):
    """Combien d'exercices sont DEJA juges au moment du gel.

    C'est la preuve que la partition precede les resultats.
    """
    racine = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                          "aider", "tmp.benchmarks", run)
    return len(glob.glob(os.path.join(racine, "*", "exercises", "practice",
                                      "*", ".dsh.results.json")))


def main():
    if os.path.exists(SORTIE):
        print("REFUS : %s existe deja." % os.path.basename(SORTIE))
        print("Une partition figee ne se reecrit pas en silence : c'est tout")
        print("son interet. La supprimer est un acte delibere, a la main.")
        return 2

    cm = importer_critere()
    ambigus = {(l, e) for l, e, _n in cm.muets}
    detail = {"%s/%s" % (l, e): n for l, e, n in cm.muets}

    tous = tous_les_exercices()
    # `contrat_muet` ecarte de son champ tout exercice dont le stub ne declare
    # RIEN (`if not noms: continue`) : le critere ne peut pas s'y appliquer.
    # Ces exercices ne sont donc PAS ambigus au sens du critere, mais ils ne
    # sont pas non plus prouves auto-suffisants -- le compte des evalues le dit.
    total_evalues = sum(t for _m, t in cm.stats.values())
    auto = [(l, e) for l, e in tous if (l, e) not in ambigus]

    doc = {
        "gele_le": time.strftime("%Y-%m-%d %H:%M:%S"),
        "critere": ("l'enonce (.docs/*.md) cite-t-il au moins un des "
                    "identifiants declares par le stub editable ?"),
        "critere_source": {
            "fichier": "contrat_muet.py",
            "sha256": sha(os.path.join(ICI, "contrat_muet.py")),
        },
        "gel_source": {
            "fichier": os.path.basename(__file__),
            "sha256": sha(os.path.abspath(__file__)),
        },
        "corpus": {
            "chemin": CORPUS,
            "stubs_cpp_semes": len(glob.glob(os.path.join(
                CORPUS, "cpp", "exercises", "practice", "*",
                "*.stub-origine"))),
        },
        "preuve_d_anteriorite": {
            "run": "pi_D_t1_dflash2",
            "exercices_deja_juges_au_gel": deja_juges("pi_D_t1_dflash2"),
            "total_corpus": len(tous),
        },
        "biais_du_critere": {
            "sous_compte": ("go/simple-linked-list est classe AUTO-SUFFISANT "
                            "(l'enonce cite Reverse) alors que l'enonce ne dit "
                            "pas que Push ajoute en fin -- FAIL mesure le "
                            "27/08."),
            "sur_compte": ("cpp/gigasecond est classe AMBIGU (l'enonce ne cite "
                           "pas advance) alors qu'il decrit le comportement et "
                           "PASSE en variante D -- pi_dimD2, PASS 459,7 s."),
            "consequence": ("la partition est un instrument reproductible, pas "
                            "une verite ; toute correction se lira comme un "
                            "diff contre ce fichier."),
        },
        "comptes": {
            "total_corpus": len(tous),
            "evalues_par_le_critere": total_evalues,
            "ambigus": len(ambigus),
            "auto_suffisants": len(tous) - len(ambigus),
            "par_langue": {k: {"ambigus": v[0], "evalues": v[1]}
                           for k, v in sorted(cm.stats.items())},
        },
        "ambigus": sorted("%s/%s" % (l, e) for l, e in ambigus),
        "ambigus_identifiants": detail,
        "auto_suffisants": sorted("%s/%s" % (l, e) for l, e in auto),
    }

    io.open(SORTIE, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False))

    print("partition figee -> %s" % os.path.basename(SORTIE))
    print("  corpus                : %d exercices" % len(tous))
    print("  ambigus               : %d" % len(ambigus))
    print("  auto-suffisants       : %d" % (len(tous) - len(ambigus)))
    print("  deja juges au gel     : %d / %d  <- preuve d'anteriorite"
          % (doc["preuve_d_anteriorite"]["exercices_deja_juges_au_gel"],
             len(tous)))
    print("  stubs cpp semes       : %d"
          % doc["corpus"]["stubs_cpp_semes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
