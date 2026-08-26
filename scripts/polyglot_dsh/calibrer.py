#!/usr/bin/env python3
"""Calibrage du pilote polyglot -- SANS MODELE NI GPU.

Le principe du banc dsh s'applique ici : on ne mesure rien avec un instrument
qu'on n'a pas calibre. Trois choses peuvent etre fausses EN SILENCE dans le
pilote, et chacune fabriquerait un faux resultat :

  1. Le juge ne juge pas. Si `docker exec` renvoyait 0 quoi qu'il arrive, TOUT
     passerait. Controle : on lance les tests sur le code VIERGE (les souches
     Exercism, qui ne resolvent rien). Elles DOIVENT echouer. Un PASS ici
     invaliderait tout le banc.
  2. La consigne est tronquee ou vide. Controle : on l'assemble et on mesure sa
     taille, et on verifie qu'elle finit bien par l'addendum avec la liste des
     fichiers.
  3. Le corpus n'est pas celui qu'on croit. Controle : compter les exercices
     par langage et les comparer aux 225 du run aider.

Aucun appel au modele : ce fichier tourne pendant qu'un autre banc occupe la
carte.
"""
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilote  # noqa: E402

VIERGE = os.path.join(pilote.BENCH_HOTE, pilote.ORIGINAL)


def titre(t):
    print("")
    print("=== %s ===" % t)
    sys.stdout.flush()


# --- 3. le corpus -----------------------------------------------------------
titre("corpus")
liste = pilote.exercices_du_corpus(VIERGE)
par_langue = {}
for lang, _ex in liste:
    par_langue[lang] = par_langue.get(lang, 0) + 1
for lang in sorted(par_langue):
    print("  %-12s %3d" % (lang, par_langue[lang]))
print("  %-12s %3d" % ("TOTAL", len(liste)))
if len(liste) != 225:
    print("  ATTENTION : %d exercices, le run aider en comptait 225." % len(liste))

# --- 2. la consigne ---------------------------------------------------------
titre("consigne assemblee (3 exercices temoins)")
temoins = [("python", "bowling"), ("go", "forth"), ("rust", "poker")]
for lang, ex in temoins:
    ex_v = os.path.join(VIERGE, lang, "exercises", "practice", ex)
    if not os.path.isdir(ex_v):
        print("  %-11s %-14s ABSENT" % (lang, ex))
        continue
    cfg = pilote.lire_config(ex_v)
    edit = pilote.fichiers_editables(ex_v, cfg)
    txt, liste_f = pilote.consigne_initiale(ex_v, edit)
    fin_ok = txt.rstrip().endswith("don't suggest installing any packages.")
    print("  %-11s %-14s %6d octets  editables=%-28s addendum=%s"
          % (lang, ex, len(txt), liste_f, "OK" if fin_ok else "MANQUANT"))
    if not edit:
        print("     REFUS : aucun fichier editable -- l'agent n'aurait rien a modifier.")

# --- 1. le juge -------------------------------------------------------------
titre("juge : le code VIERGE doit ECHOUER")
print("(un PASS ici voudrait dire que le juge ne juge pas)")
pilote.conteneur_pret()

run = os.path.join(pilote.BENCH_HOTE, "calibrage-juge")
pilote.preparer_run(run, VIERGE)

verdicts = []
for lang, ex in temoins:
    ex_h = os.path.join(run, lang, "exercises", "practice", ex)
    ex_v = os.path.join(VIERGE, lang, "exercises", "practice", ex)
    if not os.path.isdir(ex_h):
        continue
    cfg = pilote.lire_config(ex_h)
    fichiers_test = cfg.get("files", {}).get("test", [])
    edit = pilote.fichiers_editables(ex_h, cfg)
    pilote.restaurer(ex_h, ex_v, edit)          # souche vierge
    pilote.poser_tests(ex_h, ex_v, fichiers_test)
    try:
        err = pilote.lancer_tests(ex_h, fichiers_test)
    except subprocess.TimeoutExpired:
        err = "TIMEOUT"
    ok = err is None
    verdicts.append((lang, ex, ok))
    extrait = "" if ok else (err or "").strip().splitlines()
    extrait = extrait[-1][:70] if extrait else ""
    print("  %-11s %-14s %s   %s"
          % (lang, ex, "PASS (ANORMAL)" if ok else "FAIL (attendu)", extrait))

titre("verdict du calibrage")
mauvais = [v for v in verdicts if v[2]]
if not verdicts:
    print("  NON CONCLUANT : aucun temoin n'a pu etre juge.")
elif mauvais:
    print("  ECHEC : %d souche(s) vierge(s) passent les tests." % len(mauvais))
    print("  Le juge ne juge pas. NE PAS LANCER LE BANC.")
    sys.exit(2)
else:
    print("  CALIBRE : %d/%d souches vierges echouent, comme elles le doivent."
          % (len(verdicts), len(verdicts)))
