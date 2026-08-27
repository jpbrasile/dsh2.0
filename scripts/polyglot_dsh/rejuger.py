# -*- coding: utf-8 -*-
"""Rejoue LE JUGE sur un exercice deja verdict, et imprime sa sortie ENTIERE.

POURQUOI. Le pilote ne conserve que la QUEUE de 3 000 caracteres de la sortie du
juge (`turns[].erreurs`). Pour go et python cette queue porte l'assertion ; pour
JAVA elle porte la pile d'appel de gradle, et l'assertion utile -- celle qui dit
QUOI diverge -- est en tete, donc tronquee. Sur java/affine-cipher, 27/08, tout
ce qui restait etait « 16 tests completed, 2 failed » : le compte, pas la cause.
Sans la cause, un echec ne peut pas etre classe ambiguite / fond.

CE QUE CA NE FAIT PAS, et c'est deliberé :
  * ne touche a AUCUN fichier de l'exercice -- ni solution, ni test, ni config ;
  * ne relance pas le pilote et ne change pas le protocole. La capture tronquee
    reste ce qu'elle est pour ce run ; on la contourne en lecture, on ne la
    corrige pas a chaud, ce qui rendrait les exercices suivants incomparables ;
  * n'ecrit rien dans le .dsh.results.json. Le verdict enregistre fait foi.

Le juge peut deposer un repertoire de compilation (build/, target/) dans le
repertoire de l'exercice. L'exercice est deja juge, son verdict est ecrit, et le
rejeu de fin de run part d'un repertoire NEUF : sans consequence.

USAGE :
    python rejuger.py <run> <langue/exercice> [--conteneur pi-polyglot-tests]
    python rejuger.py pi_D_t1_dflash2 java/affine-cipher
"""
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Les commandes du juge viennent du PILOTE, jamais recopiees : deux tables
# finiraient par diverger, et on rejugerait avec un autre juge que celui qui a
# rendu le verdict qu'on cherche a expliquer.
from pilote import COMMANDES_TEST, chemin_conteneur, poser_tests

BENCH = os.path.join(os.environ["USERPROFILE"], "tools", "aider-bench",
                     "aider", "tmp.benchmarks")
EXT = {"go": ".go", "java": ".java", "python": ".py", "rust": ".rs",
       "javascript": ".js", "cpp": ".cpp"}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    run, cible = sys.argv[1], sys.argv[2].replace("\\", "/")
    conteneur = "pi-polyglot-tests"
    if "--conteneur" in sys.argv:
        conteneur = sys.argv[sys.argv.index("--conteneur") + 1]
    if "/" not in cible:
        print("REFUS : attendu <langue>/<exercice>, recu %r" % cible)
        return 2
    langue, exercice = cible.split("/", 1)

    ex = os.path.join(BENCH, run, langue, "exercises", "practice", exercice)
    if not os.path.isdir(ex):
        print("REFUS : introuvable -> %s" % ex)
        return 2
    if not os.path.exists(os.path.join(ex, ".dsh.results.json")):
        print("REFUS : %s n'a pas de verdict. Rejuger un exercice ENCORE EN "
              "VOL lirait un repertoire que le pilote est en train d'ecrire."
              % cible)
        return 2

    cmd = COMMANDES_TEST.get(EXT.get(langue, ""))
    if not cmd:
        print("REFUS : aucune commande de test connue pour %r" % langue)
        return 2

    # REPRODUIRE LE JUGE, PAS L'APPROXIMER. Le pilote recopie les tests vierges
    # et RETIRE les @Disabled avant de juger, puis remet l'original en place --
    # verifie le 27/08 : java/affine-cipher porte 15 @Disabled sur disque, et
    # son verdict dit « 16 tests completed ». Rejuger sans ce retrait fait
    # tourner 1 test sur 16 et rend exit 0 sur un exercice en echec : c'est ce
    # que le premier essai a produit, et le garde-fou de fin l'a attrape.
    vierge = os.path.join(BENCH, "polyglot-benchmark", langue,
                          "exercises", "practice", exercice)
    cfg = os.path.join(vierge, ".meta", "config.json")
    fichiers_test = []
    if os.path.exists(cfg):
        import json
        fichiers_test = (json.load(io.open(cfg, encoding="utf-8"))
                         .get("files", {}).get("test", []) or [])
    if not fichiers_test:
        print("REFUS : .meta/config.json ne declare aucun fichier de test pour "
              "%s. Sans lui, impossible de reproduire ce que le juge a vu." % cible)
        return 2
    poser_tests(ex, vierge, fichiers_test)

    wd = chemin_conteneur(ex)
    print("juge     : %s" % " ".join(cmd))
    print("conteneur: %s" % conteneur)
    print("repertoire: %s" % wd)
    print("tests remis a neuf, @Disabled retires : %s" % ", ".join(fichiers_test))
    print("")
    try:
        r = subprocess.run(["docker", "exec", "-w", wd, conteneur] + cmd,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
    finally:
        # On rend le repertoire tel qu'on l'a trouve : le fichier de test y
        # etait la copie VIERGE, @Disabled compris.
        import shutil
        for f in fichiers_test:
            src = os.path.join(vierge, f.replace("/", os.sep))
            dst = os.path.join(ex, f.replace("/", os.sep))
            if os.path.exists(src):
                shutil.copy(src, dst)
    sortie = (r.stdout or "") + (r.stderr or "")
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "juge_%s_%s.txt" % (langue, exercice))
    io.open(dest, "w", encoding="utf-8", newline="\n").write(sortie)
    print("code de retour : %d   (%d caracteres -> %s)"
          % (r.returncode, len(sortie), os.path.basename(dest)))
    if r.returncode == 0:
        print("")
        print("ATTENTION : le juge PASSE maintenant alors que le verdict "
              "enregistre est un echec. Ce n'est pas une bonne nouvelle, c'est")
        print("un signal : quelque chose a change entre les deux executions "
              "(artefact de compilation, etat du conteneur). A elucider avant")
        print("d'utiliser cette sortie pour classer quoi que ce soit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
