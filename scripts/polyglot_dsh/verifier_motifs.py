# -*- coding: utf-8 -*-
"""Verifie les motifs de `tracer_conventions_muettes.py` sur des sorties REELLES.

POURQUOI CE FICHIER EXISTE. Les motifs d'extraction ont d'abord ete ecrits de
memoire, et TROIS DES CINQ etaient faux pour ce corpus :

  - java  : le corpus utilise AssertJ (989 `assertThat`), pas JUnit. Le format
            est « expected: X » / « but was: Y » sur DEUX lignes, sans
            chevrons. Le motif JUnit `expected: <X> but was: <Y>` n'aurait
            jamais mordu.
  - python: le corpus utilise unittest (735 `self.assertEqual`), donc
            « AssertionError: X != Y », et non le `assert X == Y` de pytest nu.
  - rust  : le Dockerfile du juge installe rustup SANS EPINGLE, donc un rustc
            recent, dont `assert_eq!` n'entoure plus les valeurs de guillemets
            obliques.

Un traceur qui ne mord pas rend « illisible » et ne ment pas -- mais il ne
mesure rien non plus. D'ou ces echantillons, tous CAPTURES en executant
vraiment, le 27/08 :

  go      sortie du juge conservee pour `go/beer-song` (run pi_D_t1_dflash2)
  java    `./gradlew test --offline` sur affine-cipher, solution de REFERENCE
          dont on a change GROUP_SIZE de 5 a 4 -- logique juste, groupement
          faux, exactement la classe que le traceur doit reconnaitre
  rust    `rustc --test` sur des assert_eq! (rustc 1.95.0)
  python  `python -m unittest` sur des assertEqual (Python 3.11.5)

  javascript : AUCUN echantillon reel. jest est absent de l'hote et n'existe
  que dans le conteneur du juge. Le motif js n'est donc PAS verifie, et il est
  declare tel quel plutot que suppose bon.

USAGE : python verifier_motifs.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tracer_conventions_muettes import (MOTIFS, classer, deguillemete,
                                        difference_lisible, rejet_uniforme)

# Chaque cas : (langue, attendu_motif, attendu_classe, texte reel).
CAS = [
    ("go", "go/got-want", "blancs",
     'beer_song_test.go:59: Verses(3, 0)\n'
     ' got:"3 bottles of beer on the wall.\\n"\n'
     'want:"3 bottles of beer on the wall.\\n\\n"\n'),

    ("java", "java/assertj", "blancs",
     '    org.opentest4j.AssertionFailedError: \n'
     '    expected: "rzcwa gnxzc dgt"\n'
     '     but was: "rzcw agnx zcdg t"\n'
     '        at app//AffineCipherTest.testEncodeMindBlowingly'
     '(AffineCipherTest.java:34)\n'),

    ("rust", "rust/left-right-1.73", "blancs",
     "thread 't_str' panicked at gen_rust.rs:8:5:\n"
     "assertion `left == right` failed\n"
     '  left: "bonjour\\n"\n'
     ' right: "bonjour\\n\\n"\n'),

    ("rust-ordre", "rust/left-right-1.73", "ordre",
     "assertion `left == right` failed\n"
     "  left: a\\nb\\nc\n"
     " right: c\\nb\\na\n"),

    ("python", "py/unittest-neq", "blancs",
     "AssertionError: 'bonjour\\n' != 'bonjour\\n\\n'\n"),

    ("python-liste", "py/unittest-neq", "ordre",
     "AssertionError: Lists differ: a\\nb != b\\na\n"),
]

# Rejet uniforme : capture reelle du juge sur go/connect (8 cas identiques).
REJET = ("connect_test.go:24: ResultOf() returned error invalid board: "
         "unknown cell\n") * 8


def premier_motif(texte):
    for nom, motif in MOTIFS:
        m = motif.search(texte)
        if m:
            return nom, deguillemete(m.group("got")), \
                deguillemete(m.group("want"))
    return None, None, None


def main():
    echecs = 0
    for langue, motif_attendu, classe_attendue, texte in CAS:
        nom, got, want = premier_motif(texte)
        cl = classer(got, want) if nom else None
        ok = (nom == motif_attendu and cl == classe_attendue)
        if not ok:
            echecs += 1
        print("%-14s motif=%-22s classe=%-10s %s"
              % (langue, nom or "AUCUN", cl or "-", "ok" if ok else
                 "ECHEC (attendu %s / %s)" % (motif_attendu, classe_attendue)))
        if nom:
            print("               %s" % difference_lisible(got, want))

    r = rejet_uniforme(REJET)
    ok = bool(r) and r[1] == 8
    if not ok:
        echecs += 1
    print("%-14s %s" % ("go/connect", "rejet uniforme %s, %d cas -- ok"
                        % (r[0], r[1]) if ok else "ECHEC : rejet non detecte"))

    print("")
    print("javascript : NON VERIFIE -- jest n'existe que dans le conteneur du")
    print("             juge, aucun echantillon reel n'a pu etre capture.")
    print("")
    print("%d cas, %d echec(s)" % (len(CAS) + 1, echecs))
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
