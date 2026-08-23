# -*- coding: utf-8 -*-
"""Porte de tests Julia rapide (README, phase 0.5).

    python porte.py                      # fichiers modifies (git status) du framework
    python porte.py f1.jl f2.jl ...      # fichiers designes (src/ ou test/)
    python porte.py --budget 30 --port 8077 --repo DIR --arret --statut

Pour chaque fichier modifie, la carte (carte.py) donne les tests qui
l exercent, du plus cible au plus large ; la session persistante
(serveur.jl, lancee ici si absente) les rejoue dans l ordre jusqu au budget.

Verdict (code de retour) :
  0 VERT   : tous les tests selectionnes rejoues et passes, rien de non couvert
  1 ROUGE  : au moins un test faux ou en erreur
  2 ORANGE : rien de rouge, mais fichier non couvert, tests non rejoues
             (budget), ou carte muette -> ce n est PAS un vert
  3 PANNE  : serveur injoignable / non demarre
Ecrit _gate/dernier.json (verdict + detail) a cote de ce script.
"""
import io
import json
import os
import socket
import subprocess
import sys

# Sortie UTF-8 tolerante : sous Windows, stdout vers un tube est en cp1252 et l'impression
# d'un bloc d'erreur Julia (fleches, guillemets) faisait planter porte.py APRES le rejeu --
# rc 1 lu comme ROUGE par le greffon dsh-julia-gate (run Done de la phase 2, 23/08).
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import carte as C  # noqa: E402

ETAT = os.path.join(ICI, "_gate")


def _lire_args(argv):
    o = {"repo": C.REPO_DEFAUT, "port": 8077, "budget": 30.0, "fichiers": [],
         "arret": False, "statut": False, "max_tests": 50}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo":
            o["repo"] = argv[i + 1]; i += 2
        elif a == "--port":
            o["port"] = int(argv[i + 1]); i += 2
        elif a == "--budget":
            o["budget"] = float(argv[i + 1]); i += 2
        elif a == "--max-tests":
            o["max_tests"] = int(argv[i + 1]); i += 2
        elif a == "--arret":
            o["arret"] = True; i += 1
        elif a == "--statut":
            o["statut"] = True; i += 1
        else:
            o["fichiers"].append(a); i += 1
    return o


def _envoyer(port, req, timeout):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.settimeout(timeout)
    s.sendall((json.dumps(req) + "\n").encode("utf-8"))
    buf = b""
    while not buf.endswith(b"\n"):
        ch = s.recv(65536)
        if not ch:
            break
        buf += ch
    s.close()
    return json.loads(buf.decode("utf-8")) if buf.strip() else None


def ping(port):
    try:
        return _envoyer(port, {"ping": True}, 5)
    except (OSError, ValueError):
        return None


def demarrer(repo, port):
    """Lance serveur.jl detache ; attend le pong (chargement ~10 s tiede, plus a froid)."""
    os.makedirs(ETAT, exist_ok=True)
    if _pid_vivant(port):
        print("  un serveur a nous charge deja (pid %s) : on attend son pong" % _pid_vivant(port))
    else:
        _relancer_sans_attendre(repo, port)
    t0 = time.time()
    while time.time() - t0 < 600:
        r = ping(port)
        if r:
            if not _meme_projet(r, repo):
                print("  PANNE : le serveur repond pour le projet %s, pas pour %s" % (r.get("projet"), repo))
                return None, time.time() - t0
            return r, time.time() - t0
        time.sleep(1)
    return None, time.time() - t0


def _durees():
    p = os.path.join(ETAT, "durees.json")
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire_durees(d):
    os.makedirs(ETAT, exist_ok=True)
    io.open(os.path.join(ETAT, "durees.json"), "w", encoding="utf-8").write(json.dumps(d, indent=1))


def _meme_projet(pong, repo):
    """Vrai si le serveur dit avoir charge --project=repo. Un vieux serveur (sans champ
    `projet`) ne peut pas le prouver : on le considere different, il sera relance."""
    p = pong.get("projet")
    return bool(p) and C._norm(os.path.abspath(p)).lower() == repo.lower()


def _pid_vivant(port):
    """pid du serveur note dans _gate/ s il est encore un processus julia vivant, sinon None."""
    try:
        pid = int(io.open(os.path.join(ETAT, "serveur_%d.pid" % port)).read().strip())
    except (OSError, ValueError):
        return None
    out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return pid if "julia" in out.lower() else None


def _tuer_serveur(port):
    """Ne tue que le serveur lance par porte.py (pid note dans _gate/)."""
    p = os.path.join(ETAT, "serveur_%d.pid" % port)
    try:
        pid = int(io.open(p).read().strip())
    except (OSError, ValueError):
        return
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    try:
        os.remove(p)
    except OSError:
        pass


def _relancer_sans_attendre(repo, port):
    env = dict(os.environ)
    env["JULIA_LOAD_PATH"] = os.pathsep.join([repo, os.path.join(ICI, "env"), "@stdlib"])
    journal = io.open(os.path.join(ETAT, "serveur_%d.log" % port), "a", encoding="utf-8")
    p = subprocess.Popen(["julia", "--project=" + repo, os.path.join(ICI, "serveur.jl"), "--port", str(port),
                          "--journaux", os.path.join(ETAT, "journaux")],
                         cwd=repo, env=env, stdout=journal, stderr=journal,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0))
    io.open(os.path.join(ETAT, "serveur_%d.pid" % port), "w").write(str(p.pid))


def _blocs_erreur(r):
    """Lignes utiles d un rejeu non vert : blocs Test Failed / Error During Test
    du journal complet (6 lignes de contexte), sinon la fin de sortie."""
    j = r.get("journal") or ""
    try:
        lignes = io.open(j, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return (r.get("sortie_fin") or "").splitlines()[-12:]
    out, garde = [], -1
    for i, l in enumerate(lignes):
        if "Test Failed" in l or "Error During Test" in l or "LoadError" in l or l.startswith("ERROR"):
            garde = i + 6
            out.append("[%d] " % (i + 1) + l)
        elif i <= garde and l.strip():
            out.append("      " + l)
    return out or (r.get("sortie_fin") or "").splitlines()[-12:]


def fichiers_modifies(repo):
    out = subprocess.run(["git", "-C", repo, "status", "--porcelain", "--untracked-files=all"],
                         capture_output=True, text=True).stdout
    racine = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True).stdout.strip()
    fs = []
    for l in out.splitlines():
        if len(l) < 4 or l[1] == "D" or l[0] == "D":
            continue
        chemin = l[3:].strip().strip('"')
        if " -> " in chemin:
            chemin = chemin.split(" -> ")[-1]
        if chemin.endswith(".jl"):
            fs.append(os.path.join(racine, chemin))
    return fs


def main(argv):
    o = _lire_args(argv)
    repo = C._norm(os.path.abspath(o["repo"]))
    port = o["port"]
    if o["arret"]:
        try:
            print(_envoyer(port, {"arret": True}, 10))
        except OSError as e:
            print("serveur muet (%s) : arret par pid" % e)
            _tuer_serveur(port)
        return 0
    r = ping(port)
    if o["statut"]:
        print("serveur :", r or "absent")
        return 0 if r else 3
    if r and not _meme_projet(r, repo):
        # trouve le 23/08 en preparant le red team 0-done : un serveur deja vivant etait
        # reutilise sans regarder son --project ; un VERT sur la copie pouvait donc avoir
        # charge le module du vrai depot. On relance sur le bon depot, jamais en silence.
        print("serveur sur %d charge un autre projet (%s) que --repo (%s) : relance" % (port, r.get("projet"), repo))
        _tuer_serveur(port)
        r = None
    if not r:
        print("serveur absent sur %d : lancement (chargement du paquet)..." % port)
        r, dt = demarrer(repo, port)
        if not r:
            print("PANNE : serveur non demarre apres %.0fs (voir _gate/serveur_%d.log)" % (dt, port))
            return 3
        print("serveur pret en %.0fs (paquet charge en %ss)" % (dt, r.get("charge_s")))

    fichiers = o["fichiers"] or fichiers_modifies(repo)
    fichiers = [C._norm(os.path.abspath(f)) for f in fichiers]
    def dans_champ(f):
        return C.est_source(repo, f) or f.startswith(repo + "/test/")
    hors = [f for f in fichiers if not dans_champ(f)]
    fichiers = [f for f in fichiers if dans_champ(f)]
    for f in hors:
        print("  hors champ (ni */src/ ni test/ du framework, ignore) : " + f)
    if not fichiers:
        print("aucun fichier .jl modifie dans %s : rien a rejouer (verdict ORANGE, pas vert)" % repo)
        return 2
    carte = C.construire(repo)
    precis, large, non = C.tests_pour(carte, fichiers)
    a_rejouer = precis[:o["max_tests"]]
    if not precis and large:
        a_rejouer = large[:o["max_tests"]]
    print("fichiers modifies (%d) :" % len(fichiers))
    for f in fichiers:
        print("  " + os.path.relpath(f, repo) if f.startswith(repo) else "  " + f)
    print("tests cibles : %d (precis %d, paquet entier %d) ; budget %.0fs" % (len(a_rejouer), len(precis), len(large), o["budget"]))

    resultats = []
    t0 = time.time()
    depasse = []
    durees = _durees()
    serveur_perdu = False
    for t in a_rejouer:
        reste = o["budget"] - (time.time() - t0)
        connu = durees.get(t)
        if reste <= 0 or serveur_perdu or (connu is not None and connu > reste):
            depasse.append(t)  # budget epuise, ou duree connue trop longue pour ce qui reste
            continue
        try:
            res = _envoyer(port, {"fichier": t}, reste + 1)
            if res.get("etat") in ("ok", "echec"):  # rejeu complet : sa duree vaut, vert ou rouge
                durees[t] = float(res["s"])
        except socket.timeout:
            res = {"fichier": t, "etat": "depasse", "passes": 0, "echecs": 0, "erreurs": 0, "casses": 0,
                   "s": time.time() - t0, "sortie_fin": "budget depasse pendant ce fichier"}
            durees[t] = max(durees.get(t, 0), reste + 1)  # retenu : au moins ce qu on a attendu
            # le serveur est bloque sur ce fichier : on le tue (c est le notre) et on en relance un
            _tuer_serveur(port)
            serveur_perdu = True
        except OSError as e:
            res = {"fichier": t, "etat": "erreur", "passes": 0, "echecs": 0, "erreurs": 1, "casses": 0,
                   "s": 0, "sortie_fin": "serveur : %s" % e}
        resultats.append(res)
        print("  %-7s %5d ok %4d faux %3d err %6.1fs  %s" % (res["etat"], res["passes"], res["echecs"],
              res["erreurs"], float(res["s"]), os.path.relpath(t, repo)))
    _ecrire_durees(durees)
    if serveur_perdu:
        print("  serveur relance en arriere-plan (il sera tiede au prochain appel)")
        _relancer_sans_attendre(repo, port)
    wall = time.time() - t0
    rouges = [r for r in resultats if r["etat"] in ("echec", "erreur")]
    non_rejoues = depasse + [t for t in a_rejouer if t not in [r["fichier"] for r in resultats] and t not in depasse]
    if rouges:
        verdict, code = "ROUGE", 1
    elif non or non_rejoues or any(r["etat"] == "depasse" for r in resultats) or not resultats:
        verdict, code = "ORANGE", 2
    else:
        verdict, code = "VERT", 0
    print("VERDICT : %s  (%d tests rejoues en %.1fs ; %d non rejoues ; %d fichiers non couverts)"
          % (verdict, len(resultats), wall, len(non_rejoues), len(non)))
    for f in non:
        print("  NON COUVERT : " + f)
    for r in rouges[:3]:
        print("  --- %s" % os.path.relpath(r["fichier"], repo))
        for l in _blocs_erreur(r)[:40]:
            print("      " + l[:170])
    os.makedirs(ETAT, exist_ok=True)
    io.open(os.path.join(ETAT, "dernier.json"), "w", encoding="utf-8").write(json.dumps({
        "verdict": verdict, "fichiers": fichiers, "cibles": a_rejouer, "resultats": resultats,
        "non_rejoues": non_rejoues, "non_couverts": non, "wall_s": round(wall, 1),
        "date": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
