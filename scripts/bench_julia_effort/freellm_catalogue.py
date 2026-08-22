"""Ajouter un modele au catalogue FreeLLMAPI, et prouver qu'il est servi.

Le routeur ne sert QUE ce qu'il a en catalogue : une demande hors catalogue
repond 404, quelle que soit la forme du nom. Mesure du 22/08 -- stealth/ox-alpha
demande sous quatre formes, quatre fois 404, alors que la cle de plateforme
`openrouter` etait saine et que le modele etait bien vivant en amont.

Le catalogue est une table SQLite de l'application de bureau. `ajouter` y insere
une ligne ; `sonder` fait la seule mesure qui compte -- l'appel passe-t-il de 404
a 200, et QUI a repondu.

    python freellm_catalogue.py lister openrouter
    python freellm_catalogue.py ajouter openrouter stealth/ox-alpha "Ox Alpha (stealth)" --ctx 1048576 --outils --vision
    python freellm_catalogue.py sonder stealth/ox-alpha
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.environ.get("APPDATA", ""), "FreeLLMAPI", "freeapi.db")
ROUTEUR = os.environ.get("FREELLM_URL", "http://127.0.0.1:31415")


def _uri(chemin, ro=False):
    u = "file:" + chemin.replace(os.sep, "/")
    return u + "?mode=ro" if ro else u


def _cle():
    """La cle unifiee ne transite JAMAIS par un fichier versionne ni par un
    echo : on la lit a la demande via l'utilitaire dedie."""
    for cand in (os.path.join(BASE, "freellm_key.py"),
                 os.path.join(os.path.dirname(BASE), "freellm_key.py")):
        if os.path.exists(cand):
            out = subprocess.run([sys.executable, cand], capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
    raise SystemExit("catalogue: cle unifiee introuvable (freellm_key.py)")


def lister(args):
    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    q = "select platform, model_id, display_name, context_window, enabled, supports_tools, source from models"
    p = []
    if args.plateforme:
        q += " where platform = ?"
        p.append(args.plateforme)
    q += " order by platform, model_id"
    n = 0
    for r in c.execute(q, p):
        n += 1
        print("  %-12s %-42s ctx=%-9s on=%s outils=%s src=%s  %s"
              % (r[0], r[1], r[3], r[4], r[5], r[6], r[2]))
    print("  -- %d ligne(s)" % n)
    c.close()


def ajouter(args):
    """Sauvegarde AVANT toute ecriture. Une base d'application qu'on modifie
    sans copie prealable est une modification qu'on ne peut pas defaire."""
    if not os.path.exists(DB):
        raise SystemExit("catalogue: base introuvable -- %s" % DB)
    horo = time.strftime("%Y%m%d-%H%M%S")
    sauve = DB + ".bak-" + horo
    shutil.copy2(DB, sauve)
    print("  sauvegarde : %s" % sauve)

    c = sqlite3.connect(_uri(DB), uri=True)
    avant = c.execute("select count(*) from models where platform = ?",
                      (args.plateforme,)).fetchone()[0]
    c.execute(
        "insert or ignore into models "
        "(platform, model_id, display_name, intelligence_rank, speed_rank, "
        " size_label, rpm_limit, rpd_limit, monthly_token_budget, context_window, "
        " enabled, supports_vision, supports_tools, source, endpoint_scope) "
        "values (?,?,?,?,?,?,?,?,?,?,1,?,?,'catalog','')",
        (args.plateforme, args.modele, args.nom, args.rang_intel, args.rang_vitesse,
         args.taille, args.rpm, args.rpd, args.budget, args.ctx,
         1 if args.vision else 0, 1 if args.outils else 0))
    c.commit()
    apres = c.execute("select count(*) from models where platform = ?",
                      (args.plateforme,)).fetchone()[0]
    ligne = c.execute(
        "select id, platform, model_id, context_window, enabled, supports_tools "
        "from models where platform = ? and model_id = ?",
        (args.plateforme, args.modele)).fetchone()
    c.close()
    if ligne is None:
        raise SystemExit("catalogue: insertion sans effet ET ligne absente -- anomalie")
    etat = "INSEREE" if apres > avant else "DEJA PRESENTE (idempotent)"
    print("  %s : id=%s %s / %s ctx=%s active=%s outils=%s"
          % (etat, ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], ligne[5]))
    print("  lignes plateforme %s : %d -> %d" % (args.plateforme, avant, apres))


def sonder(args):
    """Le discriminant : 404 avant, 200 apres, et le corps NOMME qui a repondu.
    Un 200 seul ne prouve rien -- le routeur peut avoir bascule sur un autre
    modele. On lit donc `model` dans la reponse."""
    cle = _cle()
    corps = json.dumps({
        "model": args.modele,
        "messages": [{"role": "user", "content": "reponds exactement: OK"}],
        "max_tokens": 8,
    }).encode("utf-8")
    req = urllib.request.Request(
        ROUTEUR + "/v1/chat/completions", data=corps, method="POST",
        headers={"Authorization": "Bearer " + cle, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=args.delai) as r:
            statut = r.status
            brut = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        statut = e.code
        brut = e.read().decode("utf-8", "replace")
    except Exception as e:
        print("  demande %-32s -> ECHEC RESEAU %s" % (args.modele, e))
        return
    servi = None
    try:
        servi = json.loads(brut).get("model")
    except Exception:
        pass
    verdict = "SERVI" if statut == 200 else "REFUSE"
    print("  demande %-32s -> HTTP %s  %s  servi=%s"
          % (args.modele, statut, verdict, servi or "(non nomme)"))
    if statut != 200:
        print("     %s" % brut[:220].replace(chr(10), " "))
    elif servi and servi != args.modele:
        print("     ATTENTION : le routeur a servi un AUTRE modele que le demande.")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = p.add_subparsers(dest="cmd", required=True)

    a = sp.add_parser("lister", help="lister le catalogue (option : une plateforme)")
    a.add_argument("plateforme", nargs="?")
    a.set_defaults(fn=lister)

    b = sp.add_parser("ajouter", help="inserer une ligne (idempotent, avec sauvegarde)")
    b.add_argument("plateforme")
    b.add_argument("modele")
    b.add_argument("nom")
    b.add_argument("--ctx", type=int, default=131072)
    b.add_argument("--outils", action="store_true")
    b.add_argument("--vision", action="store_true")
    b.add_argument("--rang-intel", type=int, default=10, dest="rang_intel")
    b.add_argument("--rang-vitesse", type=int, default=5, dest="rang_vitesse")
    b.add_argument("--taille", default="Frontier")
    b.add_argument("--rpm", type=int, default=20)
    b.add_argument("--rpd", type=int, default=200)
    b.add_argument("--budget", default="apercu gratuit")
    b.set_defaults(fn=ajouter)

    d = sp.add_parser("sonder", help="404 avant / 200 apres, et QUI a repondu")
    d.add_argument("modele")
    d.add_argument("--delai", type=int, default=60)
    d.set_defaults(fn=sonder)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
