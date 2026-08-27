# -*- coding: utf-8 -*-
"""REPARE les exercices AMPUTES par un arret du pilote en plein tour.

LE DEGAT. `un_exercice` masque la suite officielle le temps que l'agent
travaille, et la remet dans un `finally`. Si le processus est TUE pendant ce
creneau, le `finally` ne tourne pas : les fichiers restent dans
`_masque/<run>/<langage>/<exercice>/` et l'exercice est ampute. A la relance,
`masquer` cherche des fichiers deja absents et l'exercice sort en

    FAIL  0.0s  tours=0  FileNotFoundError(2, 'No such file or directory')

C'est un FAUX ECHEC, produit par l'arret, pas par le modele. Le laisser dans le
run compterait un FAIL fabrique dans le taux publie -- exactement ce qu'on
s'interdit.

CE QUE FAIT CE SCRIPT.
  1. remet en place tout ce qui traine dans le stash d'un exercice ;
  2. ECARTE (renomme, jamais supprime) le resultat des exercices sortis sans
     aucun tour joue, pour qu'ils soient rejoues ;
  3. refuse de toucher a un exercice qui semble EN COURS -- son TASK.md a bouge
     dans les deux dernieres minutes.

Le sous-dossier `_maison` du stash n'est PAS un degat : il porte les tests
ecrits par l'agent, sortis le temps du verdict. On ne le touche pas.

    python reparer_amputes.py <nom-du-run>            # etat des lieux
    python reparer_amputes.py <nom-du-run> --appliquer
"""

import io
import json
import os
import shutil
import subprocess
import sys
import time

AIDER_HOTE = os.path.join(os.path.expanduser("~"), "tools", "aider-bench", "aider")
BENCH_HOTE = os.path.join(AIDER_HOTE, "tmp.benchmarks")

# Un exercice dont le TASK.md a bouge il y a moins de ca est presume EN COURS.
FRAICHEUR_S = 120


def exercice_hote(run, lang, ex):
    return os.path.join(BENCH_HOTE, run, lang, "exercises", "practice", ex)


def pilote_vivant():
    """Un pilote en vie masque LEGITIMEMENT l'exercice qu'il joue.

    La fraicheur de TASK.md ne suffit pas : il n'est ecrit qu'au debut de
    chaque tour, donc un tour long le fait paraitre vieux, et l'exercice en
    cours passerait pour ampute. On regarde donc les processus.
    """
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
             " Where-Object { $_.CommandLine -match 'pilote\\.py' }).ProcessId"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except Exception:
        return True          # dans le doute, on considere qu'il tourne
    return bool(p.stdout.decode("utf-8", "ignore").strip())


def en_cours(chemin):
    task = os.path.join(chemin, "TASK.md")
    if not os.path.exists(task):
        return False
    return (time.time() - os.path.getmtime(task)) < FRAICHEUR_S


def fichiers_du_stash(stash):
    """Fichiers a remettre : tout le stash SAUF le sous-arbre `_maison`."""
    out = []
    for racine, dossiers, fichiers in os.walk(stash):
        dossiers[:] = [d for d in dossiers if d != "_maison"]
        for f in fichiers:
            plein = os.path.join(racine, f)
            out.append((plein, os.path.relpath(plein, stash)))
    return out


def resultat_bidon(chemin):
    """Vrai si le resultat est celui d'un exercice sorti sans jouer un tour."""
    res = os.path.join(chemin, ".dsh.results.json")
    if not os.path.exists(res):
        return False
    try:
        d = json.load(io.open(res, encoding="utf-8"))
    except Exception:
        return True
    return not (d.get("turns") or [])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    applique = "--appliquer" in sys.argv
    if not args:
        print(__doc__)
        return 2
    run = args[0]

    if applique and pilote_vivant():
        print("REFUS : un pilote.py tourne encore.")
        print("  L'exercice qu'il joue est masque LEGITIMEMENT ; le reparer")
        print("  maintenant lui remettrait sa suite officielle sous les yeux.")
        print("  Arreter le pilote, puis relancer avec --appliquer.")
        return 5

    racine_stash = os.path.join(BENCH_HOTE, "_masque", run)
    if not os.path.isdir(racine_stash):
        print("pas de stash pour le run %s -- rien a reparer." % run)
        return 0

    amputes = []
    for lang in sorted(os.listdir(racine_stash)):
        d_lang = os.path.join(racine_stash, lang)
        if not os.path.isdir(d_lang):
            continue
        for ex in sorted(os.listdir(d_lang)):
            stash = os.path.join(d_lang, ex)
            if not os.path.isdir(stash):
                continue
            restes = fichiers_du_stash(stash)
            if restes:
                amputes.append((lang, ex, stash, restes))

    if not amputes:
        print("run %s : aucun exercice ampute." % run)
        return 0

    print("run %s : %d exercice(s) ampute(s)\n" % (run, len(amputes)))
    touches = 0
    for lang, ex, stash, restes in amputes:
        cible = exercice_hote(run, lang, ex)
        if not os.path.isdir(cible):
            print("  !! %-11s %-24s exercice introuvable, ignore" % (lang, ex))
            continue
        if en_cours(cible):
            print("  .. %-11s %-24s EN COURS (TASK.md frais), ignore" % (lang, ex))
            continue
        bidon = resultat_bidon(cible)
        print("  %-11s %-24s %d fichier(s) au stash%s"
              % (lang, ex, len(restes), "   resultat bidon a ecarter" if bidon else ""))
        for plein, rel in restes:
            print("      %s" % rel.replace("\\", "/"))
        if not applique:
            continue
        for plein, rel in restes:
            dst = os.path.join(cible, rel)
            dossier = os.path.dirname(dst)
            if dossier and not os.path.isdir(dossier):
                os.makedirs(dossier)
            shutil.move(plein, dst)
        if bidon:
            res = os.path.join(cible, ".dsh.results.json")
            ecarte = res + ".ampute-%s" % time.strftime("%Y%m%d-%H%M%S")
            shutil.move(res, ecarte)
            print("      resultat ECARTE -> %s" % os.path.basename(ecarte))
        touches += 1

    if not applique:
        print("\n(etat des lieux -- relancer avec --appliquer pour reparer)")
    else:
        print("\n%d exercice(s) repare(s). Ils seront rejoues a la prochaine passe." % touches)
    return 0


sys.exit(main())
