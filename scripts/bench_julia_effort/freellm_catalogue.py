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
DB = os.environ.get("FREELLM_DB") or os.path.join(
    os.environ.get("APPDATA", ""), "FreeLLMAPI", "freeapi.db")
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
    route = None
    try:
        with urllib.request.urlopen(req, timeout=args.delai) as r:
            statut = r.status
            route = r.headers.get("X-Routed-Via")
            brut = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        statut = e.code
        route = e.headers.get("X-Routed-Via")
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
    # `X-Routed-Via` est le champ DECISIF, et le corps ne le remplace pas : il
    # nomme la PLATEFORME amont, pas seulement le modele. Mesure du 22/08 --
    # une demande `x-preview-f-free` a repondu 200 en se nommant
    # `stealth/ox-alpha` ; sans l'en-tete, impossible de dire si OpenCode Zen
    # renvoyait l'identifiant canonique ou si le routeur avait bascule sur la
    # plateforme OpenRouter. Il avait bascule.
    print("  demande %-32s -> HTTP %s  %s  servi=%s  via=%s"
          % (args.modele, statut, verdict, servi or "(non nomme)", route or "(non dit)"))
    if statut != 200:
        print("     %s" % brut[:220].replace(chr(10), " "))
    elif route and not route.endswith(args.modele):
        print("     ATTENTION : bascule -- demande %s, route %s." % (args.modele, route))
    elif servi and servi != args.modele:
        print("     ATTENTION : le routeur a servi un AUTRE modele que le demande.")


def desactiver(args):
    """DEPINGLER, jamais supprimer. Une ligne dont l'amont a disparu ne doit
    plus etre TIREE, mais son enregistrement reste : le supprimer effacerait
    la trace de ce qui a ete mesure avec. Mesure du 22/08 --
    `openai/gpt-oss-20b:free` etait encore actif au catalogue du routeur alors
    qu'il a disparu des 421 modeles annonces par OpenRouter."""
    horo = time.strftime("%Y%m%d-%H%M%S")
    sauve = DB + ".bak-" + horo
    shutil.copy2(DB, sauve)
    print("  sauvegarde : %s" % sauve)
    c = sqlite3.connect(_uri(DB), uri=True)
    avant = c.execute("select enabled from models where platform = ? and model_id = ?",
                      (args.plateforme, args.modele)).fetchone()
    if avant is None:
        raise SystemExit("catalogue: ligne absente -- %s / %s" % (args.plateforme, args.modele))
    c.execute("update models set enabled = 0 where platform = ? and model_id = ?",
              (args.plateforme, args.modele))
    c.commit()
    apres = c.execute("select enabled from models where platform = ? and model_id = ?",
                      (args.plateforme, args.modele)).fetchone()[0]
    c.close()
    print("  %s / %s : active %s -> %s%s"
          % (args.plateforme, args.modele, avant[0], apres,
             "  (deja desactivee)" if avant[0] == 0 else ""))


AMONT_OR = "https://openrouter.ai/api/v1/models"


def _normalise(mid):
    """`z-ai/glm-5.2:free` et `zai-org/GLM-5.2` designent le meme modele. On
    compare sur le dernier segment, sans suffixe de gratuite, en minuscules."""
    mid = mid.split(":")[0]
    mid = mid.split("/")[-1]
    return mid.lower().replace("_", "-")


def _rangs_connus(c):
    """Le rang n'est JAMAIS invente. Le routeur note deja la plupart de ces
    modeles sur d'AUTRES plateformes ; on reprend son propre bareme.

    Un modele qu'il ne connait nulle part prend la MEDIANE de sa plateforme.
    Pas le fond de classement : corrige le 22/08, parce que le fond n'est pas
    neutre -- c'est l'affirmation "moins bon que tout ce qu'on connait", et elle
    se referme sur elle-meme. `smartest` choisit par le rang, donc un modele mis
    dernier n'est jamais tire, donc jamais mesure, donc jamais promu. Le cas qui
    l'a montre : stealth/ox-alpha etait inconnu du routeur, et il fait 9/12 la
    ou le tirage `auto:smartest` fait 4/12 sur le meme corpus. La regle prudente
    l'aurait enterre. Mettre un inconnu HAUT fabriquerait un classement ; le
    mettre DERNIER en fabrique un autre. La mediane n'en fabrique aucun : le
    modele entre dans le tirage et gagne son rang sur des mesures."""
    connus = {}
    for mid, ri, rv, taille in c.execute(
            "select model_id, intelligence_rank, speed_rank, size_label from models"):
        k = _normalise(mid)
        # le MEILLEUR rang connu pour ce modele, tous fournisseurs confondus
        if k not in connus or ri < connus[k][0]:
            connus[k] = (ri, rv, taille)
    return connus


def moissonner(args):
    """Synchroniser le catalogue avec les modeles a COUT NUL ET OUTILLES
    d'OpenRouter. Deux criteres, pas un : un modele gratuit sans outils ne peut
    pas mener une boucle d'agent -- mesure du 22/08, les dorsales qui
    n'executent jamais leur code echouent sur des fautes qu'une seule execution
    attrape. Le classement d'USAGE d'OpenRouter n'est pas un critere : il
    mesure du volume, et un modele gratuit y monte mecaniquement.

    Par defaut, ne fait qu'AFFICHER. `--appliquer` ecrit."""
    with urllib.request.urlopen(AMONT_OR, timeout=args.delai) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    ms = d.get("data", [])

    def cout_nul(m):
        pr = m.get("pricing") or {}
        try:
            return float(pr.get("prompt", 1)) == 0.0 and float(pr.get("completion", 1)) == 0.0
        except (TypeError, ValueError):
            return False

    amont = {}
    for m in ms:
        sp = m.get("supported_parameters") or []
        if cout_nul(m) and "tools" in sp:
            amont[m["id"]] = m
    print("  OpenRouter annonce %d modeles ; %d a cout nul ET outilles." % (len(ms), len(amont)))

    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    deja = {r[0]: r[1] for r in c.execute(
        "select model_id, enabled from models where platform = ?", (args.plateforme,))}
    connus = _rangs_connus(c)
    _rangs = [r[0] for r in c.execute(
        "select intelligence_rank from models where platform = ? order by intelligence_rank",
        (args.plateforme,))]
    neutre = _rangs[len(_rangs) // 2] if _rangs else 15
    c.close()

    # `openrouter/free` est un ROUTEUR, pas un modele. Mesure du 22/08 : une
    # campagne servie par un routeur ne compare pas des modeles, elle compare
    # des tirages. On l'ecarte a dessein plutot que de le laisser passer.
    routeurs = {"openrouter/free", "openrouter/auto"}

    a_ajouter, a_depingler, deja_la, ecartes = [], [], [], []
    for mid, m in sorted(amont.items()):
        if mid in routeurs:
            ecartes.append(mid)
        elif mid in deja:
            deja_la.append(mid)
        else:
            a_ajouter.append((mid, m))
    tous_amont = {m["id"] for m in ms}
    sans_outils = []
    for mid, actif in sorted(deja.items()):
        if mid in tous_amont:
            # Encore annonce en amont. S'il n'est pas dans `amont`, c'est qu'il
            # a perdu les outils ou la gratuite -- on le SIGNALE, on ne le
            # depingle pas. Repondre a "on rejette trop" par un rejet de plus
            # est le reflexe a ne pas avoir ; un rapport ne refuse rien.
            if mid not in amont:
                sans_outils.append(mid)
        elif actif:
            a_depingler.append(mid)

    print()
    print("  DEJA au catalogue         : %d" % len(deja_la))
    print("  ECARTES (routeurs)        : %s" % (", ".join(ecartes) or "aucun"))
    print()
    print("  A AJOUTER (%d) -- rang repris du bareme du routeur quand il connait" % len(a_ajouter))
    plans = []
    for mid, m in a_ajouter:
        k = _normalise(mid)
        if k in connus:
            ri, rv, taille = connus[k]
            src = "bareme routeur"
        else:
            ri, rv, taille = neutre, 5, "Medium"
            src = "MEDIANE de la plateforme (inconnu du routeur, NON MESURE)"
        vision = 1 if "image" in ((m.get("architecture") or {}).get("input_modalities") or []) else 0
        plans.append((mid, m, ri, rv, taille, vision, src))
        print("    %-50s intel=%-3s vit=%-3s %-9s vision=%s  <- %s"
              % (mid, ri, rv, taille, vision, src))
    print()
    print("  A DEPINGLER (%d) -- DISPARUS du catalogue amont" % len(a_depingler))
    for mid in a_depingler:
        print("    %s" % mid)
    print()
    print("  SIGNALES, non touches (%d) -- encore en amont mais plus gratuits+outilles" % len(sans_outils))
    for mid in sans_outils:
        print("    %s" % mid)

    if not args.appliquer:
        print()
        print("  (affichage seul -- relancer avec --appliquer pour ecrire)")
        return

    horo = time.strftime("%Y%m%d-%H%M%S")
    sauve = DB + ".bak-" + horo
    shutil.copy2(DB, sauve)
    print()
    print("  sauvegarde : %s" % sauve)
    c = sqlite3.connect(_uri(DB), uri=True)
    n_add = n_off = 0
    for mid, m, ri, rv, taille, vision, _src in plans:
        cur = c.execute(
            "insert or ignore into models "
            "(platform, model_id, display_name, intelligence_rank, speed_rank, "
            " size_label, rpm_limit, rpd_limit, monthly_token_budget, context_window, "
            " enabled, supports_vision, supports_tools, source, endpoint_scope) "
            "values (?,?,?,?,?,?,20,200,'gratuit OpenRouter',?,1,?,1,'catalog','')",
            (args.plateforme, mid, (m.get("name") or mid)[:80], ri, rv, taille,
             m.get("context_length"), vision))
        n_add += cur.rowcount or 0
    for mid in a_depingler:
        cur = c.execute("update models set enabled = 0 where platform = ? and model_id = ?",
                        (args.plateforme, mid))
        n_off += cur.rowcount or 0
    c.commit()
    c.close()
    print("  ECRIT : %d ligne(s) ajoutee(s), %d depinglee(s)." % (n_add, n_off))
    print("  Verifier chaque ajout avec `sonder` : 404 avant, 200 apres, et la route nommee.")


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

    e = sp.add_parser("desactiver", help="depingler une ligne dont l amont a disparu")
    e.add_argument("plateforme")
    e.add_argument("modele")
    e.set_defaults(fn=desactiver)

    f = sp.add_parser("moissonner",
                      help="synchroniser depuis OpenRouter les modeles a cout nul ET outilles")
    f.add_argument("--plateforme", default="openrouter")
    f.add_argument("--appliquer", action="store_true",
                   help="ecrire ; sans ce drapeau l outil ne fait qu afficher")
    f.add_argument("--delai", type=int, default=60)
    f.set_defaults(fn=moissonner)

    d = sp.add_parser("sonder", help="404 avant / 200 apres, et QUI a repondu")
    d.add_argument("modele")
    d.add_argument("--delai", type=int, default=60)
    d.set_defaults(fn=sonder)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
