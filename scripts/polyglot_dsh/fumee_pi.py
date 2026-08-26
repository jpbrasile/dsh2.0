# -*- coding: utf-8 -*-
"""Test de fumee de pi en tete baissee, avant de l'inserer dans le pilote.

Quatre choses verifiees d'un coup, chacune par une consequence observable et
non par la lecture du journal :

1. AUTHENTIFICATION OpenRouter depuis l'environnement (pas d'auth.json).
2. ARRIVEE INTACTE d'une consigne MULTI-LIGNE. C'est le point critique : sur
   Windows le shim `pi.cmd` passe par cmd.exe, qui coupe un argument
   multi-ligne a la premiere ligne -- defaut mesure le 23/08 sur dsh, ou
   l'agent recevait l'entete sans la tache. On appelle donc `node cli.js`
   directement. La preuve : on demande d'ecrire la TROISIEME ligne du
   message ; si la consigne avait ete coupee, cette ligne n'existerait pas.
3. OUTIL D'ECRITURE : le fichier preuve.txt doit apparaitre.
4. OUTIL BASH : le fichier horodatage.txt doit apparaitre, ecrit par une
   commande shell et non par l'outil d'edition.

Sort en code 2 des qu'un des quatre echoue, avec la sortie.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

CLI = (r"C:\Users\test\AppData\Roaming\npm\node_modules"
       r"\@earendil-works\pi-coding-agent\dist\bundle\cli.js")
DOTENV = r"C:\Users\test\Documents\dsh2.0\.env"
MODELE = "qwen/qwen3.8-27b"

SECRET = "MOT-SECRET-42"
CONSIGNE = (
    "LIGNE-A-ignoree\n"
    "LIGNE-B-ignoree\n"
    + SECRET + "\n"
    "\n"
    "Do exactly two things, then stop:\n"
    "1. Write a file named preuve.txt whose only content is the third line\n"
    "   of this message.\n"
    "2. Using a shell command, write the output of `date` into a file named\n"
    "   horodatage.txt\n"
)


def charger_dotenv(chemin):
    import re
    n = 0
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", ligne)
        if m:
            os.environ.setdefault(
                m.group(1), m.group(2).strip().strip('"').strip("'"))
            n += 1
    return n


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    if not os.path.exists(CLI):
        raise SystemExit("REFUS : cli.js introuvable : %s" % CLI)
    print("%d variables chargees depuis .env (valeurs jamais affichees)"
          % charger_dotenv(DOTENV))
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("REFUS : OPENROUTER_API_KEY absente.")

    ws = tempfile.mkdtemp(prefix="fumee_pi_")
    print("bac a sable : %s" % ws)
    cmd = ["node", CLI, "-p",
           "--provider", "openrouter",
           "--model", MODELE,
           "--thinking", "medium",
           "-a", "--no-session",
           "--", CONSIGNE]
    print("commande : node cli.js -p --provider openrouter --model %s "
          "--thinking medium -a --no-session -- <consigne multi-ligne>" % MODELE)
    print("")

    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=ws, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    try:
        out, _ = p.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate(timeout=30)
        print("COUPE au bout de 300 s.")
    secondes = time.time() - t0
    print("rc = %s   %.1f s" % (p.returncode, secondes))
    print("--- sortie (2000 derniers caracteres) ---")
    print((out or "")[-2000:])
    print("--- fin de sortie ---")
    print("")

    echecs = []
    if p.returncode != 0:
        echecs.append("1+3+4. code de retour %s" % p.returncode)

    preuve = os.path.join(ws, "preuve.txt")
    if not os.path.exists(preuve):
        echecs.append("3. outil d'ecriture : preuve.txt absent")
    else:
        contenu = io.open(preuve, encoding="utf-8", errors="replace").read()
        print("preuve.txt : %r" % contenu[:120])
        if SECRET not in contenu:
            echecs.append("2. MULTI-LIGNE COUPE : preuve.txt ne contient pas "
                          "%s -- la 3e ligne n'est pas arrivee" % SECRET)

    horo = os.path.join(ws, "horodatage.txt")
    if not os.path.exists(horo):
        echecs.append("4. outil bash : horodatage.txt absent")
    else:
        print("horodatage.txt : %r"
              % io.open(horo, encoding="utf-8", errors="replace").read()[:120])

    print("")
    print("fichiers laisses : %s" % sorted(os.listdir(ws)))
    if echecs:
        print("")
        print("ECHEC :")
        for e in echecs:
            print("   %s" % e)
        print("bac a sable CONSERVE pour inspection : %s" % ws)
        raise SystemExit(2)
    shutil.rmtree(ws, ignore_errors=True)
    print("")
    print("FUMEE OK -- auth, multi-ligne, ecriture, bash : les quatre passent.")


if __name__ == "__main__":
    main()
