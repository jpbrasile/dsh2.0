# -*- coding: utf-8 -*-
"""Bras connus de la porte : un fichier source est modifie TEMPORAIREMENT
(sauvegarde octet a octet, restauration garantie par `finally`, somme de
controle verifiee), la porte tourne en mode git (fichiers modifies), et on
exige le verdict attendu.

    python essai_rt.py bon          # test modifie (commentaire) -> VERT attendu (rc 0)
    python essai_rt.py bon-partiel  # source partage, suites lourdes -> ORANGE attendu (rc 2)
    python essai_rt.py mauvais  # n_processes faux    -> ROUGE attendu (rc 1)
    python essai_rt.py rouge-cache  # casse un fichier que la carte n atteint pas -> doit NE PAS etre VERT

Le bras « mauvais » est l arme de l equipe rouge : si la porte reste verte
sur un source casse, la carte a un trou et l etape 0.5 n est pas faite.
"""
import hashlib
import io
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import carte as C  # noqa: E402

REPO = os.environ.get("PORTE_REPO", C.REPO_DEFAUT)
BRAS = sys.argv[1] if len(sys.argv) > 1 else "mauvais"
BUDGET = os.environ.get("PORTE_BUDGET", "30")

CIBLES = {
    # un fichier de test modifie : lui seul est rejoue (99 tests, ~3 s) -> VERT
    "bon": (os.path.join(REPO, "test", "physics", "test_gas_species.jl"),
            None, "\n# porte: essai bras bon (ligne temporaire)\n", 0),
    # un source partage par 6 unites dont 3 suites lourdes (100-230 s) : a 30 s la
    # porte doit dire ORANGE (preuve incomplete), jamais ROUGE ni VERT
    "bon-partiel": (os.path.join(REPO, "src", "physics", "GasSpecies.jl"),
                    None, "\n# porte: essai bras bon-partiel (ligne temporaire)\n", 2),
    "mauvais": (os.path.join(REPO, "src", "physics", "GasSpecies.jl"),
                "n_processes(g::AbstractGas) = length(collision_processes(g))",
                "n_processes(g::AbstractGas) = length(collision_processes(g)) + 1", 1),
    # un fichier que la carte ne relie a aucun test : la porte doit le dire (ORANGE), pas VERT
    "rouge-cache": (os.path.join(REPO, "src", "hybrid", "PICburst.jl"),
                    None, "\nerror(\"porte: casse volontaire\")\n", 2),
}
fichier, ancien, nouveau, attendu = CIBLES[BRAS]


def md5(p):
    return hashlib.md5(io.open(p, "rb").read()).hexdigest()


octets = io.open(fichier, "rb").read()
somme = md5(fichier)
texte = octets.decode("utf-8")
if ancien is None:
    texte2 = texte + nouveau
else:
    assert texte.count(ancien) == 1, "motif introuvable ou multiple dans %s" % fichier
    texte2 = texte.replace(ancien, nouveau)
print("bras %s : modification temporaire de %s" % (BRAS, os.path.relpath(fichier, REPO)))
t0 = time.time()
try:
    io.open(fichier, "wb").write(texte2.encode("utf-8"))
    p = subprocess.run([sys.executable, os.path.join(ICI, "porte.py"), "--repo", REPO, "--budget", BUDGET],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    rc = p.returncode
    sortie = p.stdout + p.stderr
finally:
    io.open(fichier, "wb").write(octets)
    assert md5(fichier) == somme, "RESTAURATION RATEE : %s" % fichier
print("fichier restaure (md5 %s), duree %.1fs" % (somme[:8], time.time() - t0))
for l in sortie.splitlines():
    if l.startswith("VERDICT") or l.startswith("  ") and ("ok" in l or "NON COUVERT" in l or "---" in l) or "fichiers modifies" in l or "tests cibles" in l:
        print(l[:170])
noms = {0: "VERT", 1: "ROUGE", 2: "ORANGE", 3: "PANNE"}
if BRAS == "rouge-cache":
    ok = rc != 0
    print("attendu : pas VERT ; obtenu : %s -> %s" % (noms.get(rc, rc), "OK" if ok else "ECHEC DU CONTROLE"))
else:
    ok = rc == attendu
    print("attendu : %s ; obtenu : %s -> %s" % (noms[attendu], noms.get(rc, rc), "OK" if ok else "ECHEC DU CONTROLE"))
sys.exit(0 if ok else 1)
