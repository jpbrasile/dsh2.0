#!/usr/bin/env python3
"""Calibrage de la variante B -- SANS GPU, sans modele, sans un jeton.

Le risque de la variante B est precis et il est grave : si `demasquer` echoue,
le juge tourne sur un exercice DONT LE FICHIER DE TEST A DISPARU. Selon le
langage, il rendra soit une erreur, soit -- pire -- un succes vide (pytest sans
fichier de test collecte 0 test et sort en code 5 ; `go test ./...` sans fichier
_test.go sort en code 0). Un run entier rendrait alors un « 100 % » parfaitement
presentable et entierement faux. C'est exactement le defaut MISSING_CREDENTIAL
du 26/08, sous une autre forme.

Ce script verifie quatre choses sur des temoins, avant de bruler une heure de
carte :

  1. le masquage RETIRE bien ce qu'il annonce,
  2. le demasquage REMET tout, octet pour octet,
  3. un `finally` rend l'exercice intact meme si le tour leve,
  4. et le controle qui decide de tout : apres un cycle masquer/demasquer, une
     souche VIERGE echoue toujours au juge. Si elle passe, le juge ne juge plus.

    python calibrer_masque.py [--langages python,go,rust]
"""
import argparse
import hashlib
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilote


def empreinte(chemin):
    """Somme de controle de l'arbre : chemins relatifs + contenu."""
    h = hashlib.sha256()
    for cur, dirs, fs in os.walk(chemin):
        dirs.sort()
        for f in sorted(fs):
            p = os.path.join(cur, f)
            rel = os.path.relpath(p, chemin).replace("\\", "/")
            h.update(rel.encode("utf-8"))
            try:
                with io.open(p, "rb") as fh:
                    h.update(fh.read())
            except Exception:
                h.update(b"<illisible>")
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langages", default="python,go,rust,cpp")
    ap.add_argument("--run", default="dsh-calibrage-masque")
    args = ap.parse_args()

    vierge = os.path.join(pilote.BENCH_HOTE, pilote.ORIGINAL)
    if not os.path.isdir(vierge):
        raise SystemExit("REFUS : corpus vierge introuvable : %s" % vierge)

    run = os.path.join(pilote.BENCH_HOTE, args.run)
    pilote.preparer_run(run, vierge)
    pilote.conteneur_pret()

    langages = [l for l in args.langages.split(",") if l]
    temoins = []
    for lang in langages:
        d = os.path.join(run, lang, "exercises", "practice")
        if not os.path.isdir(d):
            continue
        for ex in sorted(os.listdir(d)):
            if os.path.isdir(os.path.join(d, ex)):
                temoins.append((lang, ex))
                break

    if not temoins:
        raise SystemExit("REFUS : aucun temoin trouve.")

    echecs = []
    for lang, ex in temoins:
        ex_hote = os.path.join(run, lang, "exercises", "practice", ex)
        ex_vierge = os.path.join(vierge, lang, "exercises", "practice", ex)
        stash = os.path.join(pilote.BENCH_HOTE, "_masque", args.run, lang, ex)
        print("")
        print("=== %s/%s" % (lang, ex))

        cfg = pilote.lire_config(ex_hote)
        fichiers_test = cfg.get("files", {}).get("test", [])
        editables = pilote.fichiers_editables(ex_hote, cfg)
        pilote.restaurer(ex_hote, ex_vierge, editables)
        print("  tests declares : %s" % ", ".join(fichiers_test))

        avant = empreinte(ex_hote)
        masques = pilote.chemins_a_masquer(ex_hote, fichiers_test, True, True)

        # --- 1. le masquage retire ---------------------------------------
        sortis = pilote.masquer(ex_hote, stash, masques)
        manquants = [f for f in fichiers_test
                     if not os.path.exists(os.path.join(ex_hote, f.replace("/", os.sep)))]
        meta_parti = not os.path.isdir(os.path.join(ex_hote, ".meta"))
        print("  1. masque         : %d chemins ; tests absents %d/%d ; .meta parti %s"
              % (len(sortis), len(manquants), len(fichiers_test), meta_parti))
        if len(manquants) != len(fichiers_test) or not meta_parti:
            echecs.append("%s/%s : le masquage n'a pas tout retire" % (lang, ex))

        # --- 2. le demasquage remet, octet pour octet ---------------------
        pilote.demasquer(ex_hote, stash, sortis)
        apres = empreinte(ex_hote)
        identique = (avant == apres)
        print("  2. demasque       : arbre identique octet pour octet : %s" % identique)
        if not identique:
            echecs.append("%s/%s : l'arbre n'est pas revenu a l'identique" % (lang, ex))

        # --- 3. le finally protege d'un tour qui leve ---------------------
        sortis = pilote.masquer(ex_hote, stash, masques)
        try:
            raise RuntimeError("panne simulee pendant le tour")
        except RuntimeError:
            pass
        finally:
            pilote.demasquer(ex_hote, stash, sortis)
        protege = (empreinte(ex_hote) == avant)
        print("  3. tour qui leve  : exercice intact apres le finally : %s" % protege)
        if not protege:
            echecs.append("%s/%s : un tour qui leve laisse l'exercice ampute" % (lang, ex))

        # --- 4. LE controle : souche vierge => le juge doit ECHOUER -------
        sortis = pilote.masquer(ex_hote, stash, masques)
        pilote.demasquer(ex_hote, stash, sortis)
        pilote.poser_tests(ex_hote, ex_vierge, fichiers_test)
        pilote.restaurer(ex_hote, ex_vierge, editables)   # souche VIERGE
        try:
            erreurs = pilote.lancer_tests(ex_hote, fichiers_test)
        except Exception as e:
            erreurs = "EXCEPTION: %r" % e
        verdict = "ECHOUE (attendu)" if erreurs is not None else "PASSE -- ANORMAL"
        print("  4. souche vierge  : le juge %s" % verdict)
        if erreurs is None:
            echecs.append("%s/%s : une souche VIERGE passe le juge apres un "
                          "cycle de masquage -- le juge ne juge plus" % (lang, ex))

    print("")
    if echecs:
        print("CALIBRAGE ECHOUE :")
        for e in echecs:
            print("  - %s" % e)
        raise SystemExit(2)
    print("CALIBRAGE OK sur %d temoins : le masquage se defait, et une souche "
          "vierge echoue toujours." % len(temoins))
    print("Le stash residuel peut etre retire a la main : %s"
          % os.path.join(pilote.BENCH_HOTE, "_masque", args.run))


if __name__ == "__main__":
    main()
