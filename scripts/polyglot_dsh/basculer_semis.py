# -*- coding: utf-8 -*-
"""RETIRE ou REMET le semis des signatures cpp dans le corpus vierge.

POURQUOI CE SCRIPT EXISTE. Le 27/08 on a seme les 26 stubs cpp : leur en-tete
d'origine est un NAMESPACE VIDE (3 a 11 lignes de garde d'inclusion), alors que
le test cache appelle des classes et des methodes dont le nom n'apparait ni
dans l'enonce ni dans le stub. En variante D l'agent ne voit jamais le test :
il devait DEVINER le contrat d'API. Les cinq autres langages livrent leurs
signatures gratuitement (go : `func (l *List) Push(element int)` avec un
`panic("Please implement")`), cpp non.

CE QUI A CHANGE DEPUIS. Le run passe a `--tours 2`. Or l'erreur de compilation
du tour 1 NOMME les symboles manquants -- c'est par la que tous les modeles du
classement passent le cpp, sans qu'on leur seme quoi que ce soit. Le semis est
donc largement redondant, et cumuler les deux donne au cpp plus d'aide qu'aux
autres langages ET plus que le banc publie.

D'ou la mesure appariee : les 26 cpp rejoues SANS semis, tout le reste
identique. Ce script fait la bascule, dans les deux sens, sans rien perdre.

    python basculer_semis.py                 # etat des lieux
    python basculer_semis.py --retirer       # remet les stubs d'origine
    python basculer_semis.py --remettre      # remet les stubs semes

ATTENTION -- LE CORPUS VIERGE EST LU EN DIRECT PAR LE PILOTE. `restaurer()` et
`poser_tests()` copient depuis `tmp.benchmarks/polyglot-benchmark` A CHAQUE
exercice. Basculer pendant qu'un run tourne changerait le stub servi en cours
de route. Le script refuse donc si un pilote est en vie.
"""

import os
import shutil
import subprocess
import sys

AIDER_HOTE = os.path.join(os.path.expanduser("~"), "tools", "aider-bench", "aider")
VIERGE = os.path.join(AIDER_HOTE, "tmp.benchmarks", "polyglot-benchmark")
PRATIQUE = os.path.join(VIERGE, "cpp", "exercises", "practice")

SUF_ORIGINE = ".stub-origine"      # ecrit par semer_signatures.py
SUF_SEME = ".avec-semis"           # ecrit ici, pour pouvoir revenir


def pilote_vivant():
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" |"
             " Where-Object { $_.CommandLine -match 'pilote\\.py' }).ProcessId"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except Exception:
        return True
    return bool(p.stdout.decode("utf-8", "ignore").strip())


def lignes(chemin):
    if not os.path.exists(chemin):
        return None
    with open(chemin, encoding="utf-8", errors="ignore") as f:
        return len([l for l in f if l.strip()])


def cibles():
    """(exercice, stub, origine, seme) pour chaque cpp porteur d'un semis."""
    out = []
    for ex in sorted(os.listdir(PRATIQUE)):
        d = os.path.join(PRATIQUE, ex)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(SUF_ORIGINE):
                stub = os.path.join(d, f[:-len(SUF_ORIGINE)])
                out.append((ex, stub, stub + SUF_ORIGINE, stub + SUF_SEME))
                break
    return out


def main():
    retirer = "--retirer" in sys.argv
    remettre = "--remettre" in sys.argv
    if retirer and remettre:
        print("REFUS : --retirer et --remettre ensemble.")
        return 2

    liste = cibles()
    if not liste:
        print("aucun stub cpp seme trouve sous %s" % PRATIQUE)
        return 1

    if (retirer or remettre) and pilote_vivant():
        print("REFUS : un pilote.py tourne encore.")
        print("  Le corpus vierge est lu EN DIRECT a chaque exercice ; basculer")
        print("  maintenant changerait le stub servi au milieu du run.")
        return 5

    faits = 0
    print("%-28s %8s %8s %8s" % ("exercice", "origine", "semis", "servi"))
    for ex, stub, origine, seme in liste:
        if retirer:
            if not os.path.exists(seme):
                shutil.copy2(stub, seme)      # on garde le semis avant d'ecraser
            shutil.copy2(origine, stub)
            faits += 1
        elif remettre:
            if os.path.exists(seme):
                shutil.copy2(seme, stub)
                faits += 1
            else:
                print("  !! %-25s pas de %s -- laisse tel quel" % (ex, SUF_SEME))
        print("%-28s %8s %8s %8s"
              % (ex, lignes(origine), lignes(seme) if os.path.exists(seme) else "-",
                 lignes(stub)))

    print("")
    if retirer:
        print("%d stubs cpp remis a leur ETAT D'ORIGINE (namespace vide)." % faits)
        print("Le semis est conserve dans *%s, revenir avec --remettre." % SUF_SEME)
    elif remettre:
        print("%d stubs cpp remis a leur etat SEME." % faits)
    else:
        print("(etat des lieux -- --retirer ou --remettre pour agir)")
    return 0


sys.exit(main())
