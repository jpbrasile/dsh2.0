# -*- coding: utf-8 -*-
"""Ce qu'on peut savoir des pistes RESTANTES sans les avoir jouees.

Sert a fonder un pre-enregistrement : toutes les mesures ici portent sur le
CORPUS VIERGE (enonces + suites officielles), jamais sur des verdicts. Elles
sont donc disponibles avant que la piste soit jouee -- c'est ce qui rend la
prediction falsifiable au lieu de descriptive.

Trois questions :
  1. combien d'enonces PUBLIENT la chaine exacte que la suite comparera ?
  2. combien de suites exigent un REJET, et parmi elles combien d'enonces sont
     muets sur ce rejet ?
  3. quels enonces sont assez courts pour que la specification soit ailleurs
     (lien externe porteur) ?
"""

import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIERGE = os.path.join(os.path.expanduser("~"), "tools", "aider-bench", "aider",
                      "tmp.benchmarks", "polyglot-benchmark")
PISTES = ("cpp", "go", "java", "javascript", "python", "rust")

# Une suite « exige un rejet » si elle attend une exception / une erreur.
REJET = re.compile(
    r"assertRaises|pytest\.raises|with self\.assertRaises|"          # python
    r"assertThrows|assertThatExceptionOfType|expectThrows|"          # java
    r"toThrow|assert\.throws|"                                       # javascript
    r"should_panic|\.is_err\(\)|unwrap_err|"                         # rust
    r"REQUIRE_THROWS|CHECK_THROWS|"                                  # cpp
    r"if err == nil|wantErr|ErrorContains",                          # go
    re.I)

# L'enonce est « muet » sur le rejet s'il n'emploie AUCUN mot du champ.
MOTS_REJET = re.compile(
    r"\berror\b|\berrors\b|\binvalid\b|\braise\b|\braises\b|\bthrow\b|"
    r"\bthrows\b|\bexception\b|\bmust\b|\bcannot\b|\bshould not\b|"
    r"\bfail\b|\breject\b|\billegal\b|\bnot allowed\b|\bpanic\b", re.I)

# Chaine litterale attendue par la suite, au caractere pres.
LITTERAL = {
    "python": re.compile(r"""(?:ValueError|Exception|TypeError)\(\s*["']([^"']{6,})["']"""),
    "java": re.compile(r"""(?:withMessage|hasMessage(?:Containing)?)\(\s*"([^"]{6,})\""""),
    "javascript": re.compile(r"""toThrow\w*\(\s*(?:new \w+\()?\s*["'`]([^"'`]{6,})["'`]"""),
    "rust": re.compile(r"""(?:expect|panic!)\(\s*"([^"]{6,})\""""),
}


def lire(p):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def enonce(d):
    return "\n".join(lire(f) for f in sorted(glob.glob(os.path.join(d, ".docs", "*.md"))))


def fichiers_test(d):
    out = []
    for pat in ("*_test.*", "*test*.py", "*Test.java", "*.spec.js", "*.test.js",
                "test/*", "tests/*", "*_test.go", "*_test.cpp"):
        out += glob.glob(os.path.join(d, pat)) + glob.glob(os.path.join(d, "**", pat),
                                                           recursive=True)
    return sorted({f for f in out if os.path.isfile(f)
                   and ".meta" not in f and "build" not in f})


print("%-12s %6s %8s %8s %10s %10s %8s"
      % ("piste", "exos", "rejet", "muets", "litteraux", "publies", "courts"))
print("-" * 68)
recap = {}
for piste in PISTES:
    base = os.path.join(VIERGE, piste, "exercises", "practice")
    if not os.path.isdir(base):
        continue
    exos = sorted(d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d))
    n_rejet = n_muet = n_litt = n_publie = n_court = 0
    muets, publies, courts = [], [], []
    for d in exos:
        nom = os.path.basename(d)
        txt = enonce(d)
        tests = "\n".join(lire(f) for f in fichiers_test(d))
        if REJET.search(tests):
            n_rejet += 1
            if not MOTS_REJET.search(txt):
                n_muet += 1
                muets.append(nom)
        rx = LITTERAL.get(piste)
        if rx:
            chaines = set(rx.findall(tests))
            if chaines:
                n_litt += 1
                # PUBLIE = au moins une des chaines attendues figure telle
                # quelle dans l'enonce.
                if any(c in txt for c in chaines):
                    n_publie += 1
                    publies.append(nom)
        if 0 < len(txt) < 700 and re.search(r"https?://", txt):
            n_court += 1
            courts.append(nom)
    print("%-12s %6d %8d %8d %10d %10d %8d"
          % (piste, len(exos), n_rejet, n_muet, n_litt, n_publie, n_court))
    recap[piste] = {"muets": muets, "publies": publies, "courts": courts}

print()
for piste in ("javascript", "python", "rust"):
    r = recap.get(piste)
    if not r:
        continue
    print("== %s ==" % piste)
    print("   enonces MUETS sur un rejet exige (%d) : %s"
          % (len(r["muets"]), ", ".join(r["muets"]) or "-"))
    print("   chaines PUBLIEES dans l'enonce (%d) : %s"
          % (len(r["publies"]), ", ".join(r["publies"]) or "-"))
    print("   enonces COURTS a lien externe (%d) : %s"
          % (len(r["courts"]), ", ".join(r["courts"]) or "-"))
    print()
