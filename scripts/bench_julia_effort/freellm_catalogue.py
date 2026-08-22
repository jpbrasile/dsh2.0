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
        "values (?,?,?,?,?,?,?,?,?,?,1,?,?,?,'')",
        (args.plateforme, args.modele, args.nom, args.rang_intel, args.rang_vitesse,
         args.taille, args.rpm, args.rpd, args.budget, args.ctx,
         1 if args.vision else 0, 1 if args.outils else 0,
         getattr(args, "source", None) or SOURCE_MOISSON))
    c.commit()
    apres = c.execute("select count(*) from models where platform = ?",
                      (args.plateforme,)).fetchone()[0]
    ligne = c.execute(
        "select id, platform, model_id, context_window, enabled, supports_tools, source "
        "from models where platform = ? and model_id = ?",
        (args.plateforme, args.modele)).fetchone()
    c.close()
    if ligne is None:
        raise SystemExit("catalogue: insertion sans effet ET ligne absente -- anomalie")
    etat = "INSEREE" if apres > avant else "DEJA PRESENTE (idempotent)"
    print("  %s : id=%s %s / %s ctx=%s active=%s outils=%s src=%s"
          % (etat, ligne[0], ligne[1], ligne[2], ligne[3], ligne[4],
             ligne[5], ligne[6]))
    print("  lignes plateforme %s : %d -> %d" % (args.plateforme, avant, apres))


def sonder(args):
    """Le discriminant : 404 avant, 200 apres, et le corps NOMME qui a repondu.
    Un 200 seul ne prouve rien -- le routeur peut avoir bascule sur un autre
    modele. On lit donc `model` dans la reponse."""
    cle = _cle()
    charge = {
        "model": args.modele,
        "messages": [{"role": "user", "content": "reponds exactement: OK"}],
        "max_tokens": 8,
    }
    if getattr(args, "avec_outils", False):
        # Un outil REEL, pas un tableau vide : un amont qui ne gere pas l'appel
        # de fonction rend une erreur ici, et c'est ce qu'on veut savoir.
        charge["tools"] = [{
            "type": "function",
            "function": {
                "name": "obtenir_heure",
                "description": "Rend l heure courante.",
                "parameters": {"type": "object", "properties": {}},
            },
        }]
        charge["tool_choice"] = "auto"
    corps = json.dumps(charge).encode("utf-8")
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


# PROVENANCE. La base de FreeLLMAPI est TENUE A JOUR EN AMONT : ses 525 lignes
# portent `source = 'catalog'` et ne nous appartiennent pas. Nos ajouts doivent
# rester reconnaissables en UNE requete, sinon on ne pollue pas seulement la
# base -- on perd la capacite de defaire ce qu'on y a mis.
#
# Defaut mesure le 22/08 : nos huit premieres lignes avaient pris le DEFAUT de
# la colonne, `catalog`. Elles etaient indiscernables des 525 autres. Corrige,
# et la colonne devient l'instrument de la peremption ci-dessous.
#
# Deux valeurs, parce que les deux populations ne vieillissent pas au meme
# rythme :
#   `stealth` -- avant-premieres (ox-alpha, x-preview-f...). Nom de code,
#                montee d'usage tres rapide, DISPARITION sans preavis quand
#                l'editeur renomme ou retire. A verifier a CHAQUE session.
#   `moisson` -- gratuits ordinaires releves en amont. Vieillissent lentement.
SOURCE_STEALTH = "stealth"
SOURCE_MOISSON = "moisson"
SOURCE_AMONT = "catalog"


def _appel_brut(modele, delai, outils=False):
    """Un appel minimal au routeur. Rend (code HTTP, corps brut)."""
    charge = {"model": modele,
              "messages": [{"role": "user", "content": "reponds exactement: OK"}],
              "max_tokens": 8}
    if outils:
        charge["tools"] = [{"type": "function", "function": {
            "name": "obtenir_heure", "description": "Rend l heure courante.",
            "parameters": {"type": "object", "properties": {}}}}]
        charge["tool_choice"] = "auto"
    req = urllib.request.Request(
        ROUTEUR + "/v1/chat/completions",
        data=json.dumps(charge).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + _cle(),
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, "ECHEC RESEAU: %s" % e


def _classe_refus(corps, code):
    """PERIME, ou seulement INDISPONIBLE ? La distinction EST l'instrument.

    Un 429 est un quota, un 403 une autorisation : dans les deux cas le modele
    EXISTE. Les lire comme une peremption retirerait du service un modele
    vivant, et le geste serait invisible -- la ligne passe a `enabled = 0` et
    plus rien ne la tire. Mesure du 22/08 : sur trois ajouts sondes dans la
    foulee, deux ont rendu 403 et un 429. Aucun n'etait perime. Une regle qui
    aurait lu "HTTP different de 200" comme une disparition en aurait retire
    trois sur trois.

    Seul un amont qui dit NE PAS CONNAITRE le modele vaut peremption."""
    t = (corps or "").lower()
    if ("model_not_found" in t or "no endpoints found" in t
            or "is not in the catalog" in t or "no allowed providers" in t
            or ("not found" in t and "404" in t)):
        return "PERIME"
    if code == 200:
        return "VIVANT"
    if code in (401, 403):
        return "INDISPONIBLE (autorisation)"
    if code == 429:
        return "INDISPONIBLE (quota)"
    if code == 0:
        return "INDECIDABLE (reseau)"
    return "INDECIDABLE (HTTP %s)" % code


def perimer(args):
    """Retirer du service les lignes A NOUS dont l'amont ne repond plus.

    On ne touche JAMAIS une ligne `catalog` : celle-la est tenue a jour par
    l'application, et la corriger serait se mettre en travers de sa propre
    synchronisation. On ne touche que ce qu'on a ajoute.

    Et on DEPINGLE, on ne supprime pas : une ligne desactivee garde son rang,
    ses limites et sa trace ; le jour ou l'amont revient, il suffit de la
    rallumer. Une ligne supprimee, il faut la reconstituer.

    Par defaut, ne fait qu'AFFICHER. `--appliquer` ecrit."""
    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    lignes = c.execute(
        "select id, platform, model_id, source from models "
        "where source <> ? and enabled = 1 order by source, platform, model_id",
        (SOURCE_AMONT,)).fetchall()
    total = c.execute("select count(*) from models where source = ?",
                      (SOURCE_AMONT,)).fetchone()[0]
    c.close()
    print("  base de l'application : %d lignes `%s`, JAMAIS touchees." % (total, SOURCE_AMONT))
    if not lignes:
        print("  aucune ligne a nous en service -- rien a perimer.")
        return []
    print("  a nous, en service : %d. L'amont decide, pas nous." % len(lignes))
    morts = []
    for (i, plat, mid, src) in lignes:
        code, corps = _appel_brut(mid, args.delai)
        verdict = _classe_refus(corps, code)
        # Un INDECIDABLE qu'on peut lever a bon compte doit etre leve.
        # Mesure du 22/08 : a 30 s, les deux SEULES lignes que cette
        # routine existe pour surveiller -- les avant-premieres -- sont
        # sorties "reseau". Un modele de raisonnement met plus de 30 s a
        # rendre son premier jeton ; le delai court ne mesurait pas leur
        # peremption, il mesurait ma patience.
        if verdict.startswith("INDECIDABLE (reseau)"):
            code, corps = _appel_brut(mid, args.delai * 3)
        verdict = _classe_refus(corps, code)
        print("  %-9s %-42s src=%-8s -> %s" % (plat, mid, src, verdict))
        if verdict == "PERIME":
            morts.append((i, plat, mid))
            print("       %s" % (corps or "").replace(chr(10), " ")[:150])
    print()
    if not morts:
        print("  AUCUNE PEREMPTION -- rien n'est retire.")
        return []
    print("  PERIMES (%d) : %s" % (len(morts), ", ".join(m[2] for m in morts)))
    if not args.appliquer:
        print("  (affichage seul -- --appliquer pour depingler)")
        return morts
    sauve = DB + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(DB, sauve)
    print("  sauvegarde : %s" % sauve)
    c = sqlite3.connect(_uri(DB), uri=True)
    for (i, plat, mid) in morts:
        c.execute("update models set enabled = 0 where id = ?", (i,))
        print("  depingle : %s / %s (id=%d)" % (plat, mid, i))
    c.commit()
    c.close()
    return morts


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
            "values (?,?,?,?,?,?,20,200,'gratuit OpenRouter',?,1,?,1,?,'')",
            (args.plateforme, mid, (m.get("name") or mid)[:80], ri, rv, taille,
             m.get("context_length"), vision, SOURCE_MOISSON))
        n_add += cur.rowcount or 0
    for mid in a_depingler:
        cur = c.execute("update models set enabled = 0 where platform = ? and model_id = ?",
                        (args.plateforme, mid))
        n_off += cur.rowcount or 0
    c.commit()
    c.close()
    print("  ECRIT : %d ligne(s) ajoutee(s), %d depinglee(s)." % (n_add, n_off))
    print("  Verifier chaque ajout avec `sonder` : 404 avant, 200 apres, et la route nommee.")


# CLASSEMENT PAR USAGE -- releve OpenRouter du 21/08/2026, jetons traites par
# jour. Source : page publique des rankings, agregee ; pas d'API pour l'obtenir,
# donc la donnee est FIGEE ICI avec sa date, et elle vieillira. La redater est un
# geste manuel assume, pas une synchronisation.
#
# Pourquoi ce classement compte, alors que "l'usage n'est pas la qualite" :
# l'objection vaut quand on compare du gratuit a du payant, ou le prix explique
# le volume. A L'INTERIEUR du vivier gratuit le prix est CONSTANT, donc ce qui
# reste dans le volume est une preference revelee -- des gens qui ne paient rien
# choisissent quand meme celui-la. Et pour un modele sorti depuis deux jours,
# c'est le seul signal qui existe : aucun banc public ne l'a encore mesure.
#
# Le trafic dominant d'OpenRouter est de l'assistance au code. Un agent de code
# ne tourne pas sans outils : un modele massivement utilise LA-BAS gere donc les
# outils. L'inference est bonne, mais elle reste une inference -- d'ou
# `sonder --avec-outils`, qui la transforme en mesure en envoyant un vrai outil.
USAGE_20260821 = [
    ("ox-alpha", 2000, {"ox-alpha", "x-preview-f-free"}),
    ("deepseek-v4-flash", 1800, {"deepseek-v4-flash", "deepseek-v4-flash-free",
                                "deepseek-v4-flash-0731"}),
    ("mimo-v2.5", 1700, {"mimo-v2.5", "mimo-v2.5-free"}),
    ("hy3", 1100, {"hy3", "hy3-free"}),
]


def usage(args):
    """Porter en TETE du bareme les gratuits massivement utilises.

    Le rang du routeur est ordinal, petit = prefere. On donne 1..N aux modeles
    du releve, dans l'ordre du volume. Rien n'est retrograde : les autres lignes
    gardent leur rang."""
    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    lignes = list(c.execute(
        "select id, platform, model_id, intelligence_rank, supports_tools, enabled from models"))
    c.close()

    plans, absents = [], []
    for rang, (nom, jetons, alias) in enumerate(USAGE_20260821, start=1):
        vus = [l for l in lignes if _normalise(l[2]) in alias]
        if not vus:
            absents.append(nom)
            continue
        for (mid_db, plat, mid, ri, outils, actif) in vus:
            if ri != rang:
                plans.append((mid_db, plat, mid, ri, rang, nom, jetons, outils, actif))
    print("  releve OpenRouter du 21/08/2026, jetons/jour, vivier a cout nul :")
    for rang, (nom, jetons, _a) in enumerate(USAGE_20260821, start=1):
        print("    %d. %-22s %5d Md/j" % (rang, nom, jetons))
    print()
    print("  A RECLASSER (%d ligne(s))" % len(plans))
    for (_i, plat, mid, ri, neuf, nom, _j, outils, actif) in plans:
        note = "" if outils else "   [outils=0 au catalogue -- a verifier par sonde]"
        note += "" if actif else "   [ligne desactivee]"
        print("    %-12s %-40s rang %-3s -> %-3s (%s)%s" % (plat, mid, ri, neuf, nom, note))
    if absents:
        print()
        print("  ABSENTS du catalogue, a ajouter avant de pouvoir les classer : %s"
              % ", ".join(absents))
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
    n = 0
    for (mid_db, _p, _m, _ri, neuf, _nom, _j, _o, _a) in plans:
        n += c.execute("update models set intelligence_rank = ? where id = ?",
                       (neuf, mid_db)).rowcount or 0
    c.commit()
    c.close()
    print("  ECRIT : %d ligne(s) reclassee(s)." % n)


class _Args(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


def demarrage(args):
    """ROUTINE DE DEBUT DE SESSION.

    LA BASE DE REFERENCE EST CELLE DE FREELLMAPI, pas la notre. Ses lignes
    `catalog` sont tenues a jour en amont -- avec du RETARD sur l'engouement
    des utilisateurs, et c'est exactement ce retard qu'on comble. On n'y
    reverse donc pas tout ce qu'OpenRouter annonce : on y ajoute, au bon rang,
    les seuls modeles que l'usage designe, et on retire ceux qui ont expire.

    Trois gestes, dans cet ordre. L'ordre compte : perimer AVANT d'ajouter,
    sinon la base grossit d'une session a l'autre sans jamais maigrir.

    1. PERIMER -- nos lignes dont l'amont ne repond plus. Les avant-premieres
       se perimeent vite : elles montent en usage sous un nom de code puis
       disparaissent sans preavis quand l'editeur renomme ou retire.
    2. AJOUTER LES PLUS UTILISES QUI MANQUENT -- et seulement ceux-la, au rang
       que leur donne le volume d'usage. Un modele absent du catalogue
       OpenRouter n'est pas invente : il est SIGNALE, pas ajoute.
    3. SONDER AVEC UN VRAI OUTIL -- transformer l'inference en mesure.

    Le troisieme geste n'est pas decoratif. Mesure du 22/08, sur quatre
    modeles supposes outilles parce que massivement utilises : deux confirmes
    (hy3-free, nemotron-3.5-lightning-free repondent 200 avec un outil reel),
    un INFIRME (muse-spark rend un 400 depuis OpenCode Zen lui-meme), un
    indecidable ce jour-la (quota). L'inference etait bonne trois fois sur
    quatre -- donc fausse une fois sur quatre, et une fiche fausse se paie en
    runs qui echouent sur la mauvaise cause.

    Piege a connaitre : tant que la fiche du routeur dit `outils=0`, il REFUSE
    la requete outillee en citant SA PROPRE FICHE. Le refus ne mesure alors
    rien -- il faut lever le drapeau pour pouvoir mesurer.

    `--moissonner` ajoute le versement en masse depuis OpenRouter. Il n'est
    PAS dans la routine : il ajoute des dizaines de lignes que personne ne
    tirera, et c'est precisement ce qui pollue une base tenue en amont."""
    print("=" * 68)
    print("1/3  PEREMPTION -- nos lignes d'abord, celles de l'application jamais")
    print("=" * 68)
    perimer(_Args(appliquer=args.appliquer, delai=args.delai))

    if args.moissonner:
        print()
        print("=" * 68)
        print("1bis  MOISSON EN MASSE (hors routine, --moissonner)")
        print("=" * 68)
        moissonner(_Args(plateforme=args.plateforme, appliquer=args.appliquer,
                         delai=args.delai))

    print()
    print("=" * 68)
    print("2/3  LES PLUS UTILISES -- releve fige, voir USAGE_20260821")
    print("=" * 68)
    manquants = _usage_manquants(args.delai)
    for nom, jetons, ou, ctx in manquants:
        print("  MANQUANT %-22s %5d Md/j" % (nom, jetons), end="")
        if ou is None:
            print("  -- absent du catalogue OpenRouter : SIGNALE, pas ajoute.")
            continue
        print("  -- OpenRouter annonce %s (ctx=%s)" % (ou, ctx))
        if args.appliquer:
            ajouter(_Args(plateforme="openrouter", modele=ou, nom=nom,
                          ctx=ctx or 131072, outils=True, vision=False,
                          rang_intel=1, rang_vitesse=3, taille="Frontier",
                          rpm=20, rpd=200, budget="apercu gratuit",
                          source=SOURCE_STEALTH))
    if not manquants:
        print("  aucun manquant : les plus utilises sont deja au catalogue.")
    print()
    usage(_Args(appliquer=args.appliquer))

    if not args.appliquer:
        print()
        print("(affichage seul de bout en bout -- --appliquer pour ecrire et sonder)")
        return

    print()
    print("=" * 68)
    print("3/3  SONDES OUTILLEES -- l'inference devient une mesure")
    print("=" * 68)
    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    cibles = [r[0] for r in c.execute(
        "select distinct model_id from models "
        "where enabled = 1 and supports_tools = 1 and intelligence_rank <= ? "
        "and platform in ('openrouter', 'opencode') order by intelligence_rank",
        (args.jusqu_au_rang,))]
    c.close()
    for mid in cibles:
        sonder(_Args(modele=mid, delai=args.delai, avec_outils=True))


def _usage_manquants(delai):
    """Les noms du releve d'usage qui ne sont dans AUCUNE ligne du catalogue.

    On ne cherche pas seulement le nom exact : le meme modele circule sous
    plusieurs identifiants (`hy3`, `hy3-free`, `stealth/ox-alpha`), d'ou les
    alias du releve. Un modele est present des qu'UN de ses alias l'est.

    Et pour chaque manquant, on demande a OpenRouter s'il le connait -- un
    identifiant qu'aucun amont n'annonce ne s'ajoute pas, il se signale."""
    c = sqlite3.connect(_uri(DB, ro=True), uri=True)
    presents = {_normalise(r[0]) for r in c.execute("select model_id from models")}
    c.close()
    manque = [(nom, jetons, alias) for (nom, jetons, alias) in USAGE_20260821
              if not any(_normalise(a) in presents for a in alias)]
    if not manque:
        return []
    try:
        with urllib.request.urlopen(AMONT_OR, timeout=delai) as r:
            ms = json.loads(r.read().decode("utf-8", "replace")).get("data", [])
    except Exception as e:
        print("  (catalogue OpenRouter injoignable : %s -- signalement seul)" % e)
        ms = []
    par_cle = {}
    for m in ms:
        par_cle.setdefault(_normalise(m["id"]), m)
    sortie = []
    for nom, jetons, alias in manque:
        trouve = None
        for a in list(alias) + [nom]:
            if _normalise(a) in par_cle:
                trouve = par_cle[_normalise(a)]
                break
        sortie.append((nom, jetons, trouve["id"] if trouve else None,
                       (trouve or {}).get("context_length")))
    return sortie


def autotest(args):
    """FIXTURE : faire PARCOURIR la branche d'ajout automatique.

    Elle ne s'etait jamais executee, et pour une raison qui la rendait
    invisible : les modeles du releve d'usage etaient DEJA au catalogue, donc
    `_usage_manquants` rendait une liste vide a chaque appel. Une branche
    jamais parcourue ne prouve rien -- elle passe en silence, et le jour ou un
    stealth se perime pour de bon, c'est la premiere fois qu'elle tourne.

    On la parcourt donc a la demande, sur une COPIE de la base, dont on retire
    le modele de tete. Rien n'est ecrit dans la base de l'application."""
    import tempfile
    global DB
    if not os.path.exists(DB):
        raise SystemExit("autotest: base introuvable -- %s" % DB)
    tete = USAGE_20260821[0]
    dossier = tempfile.mkdtemp(prefix="fc_autotest_")
    copie = os.path.join(dossier, "essai.db")
    shutil.copy2(DB, copie)
    c = sqlite3.connect(copie)
    ids = [r[0] for r in c.execute("select id, model_id from models")
           if _normalise(r[1]) in {_normalise(a) for a in tete[2]}]
    for i in ids:
        c.execute("delete from models where id = ?", (i,))
    c.commit()
    reste = c.execute("select count(*) from models").fetchone()[0]
    c.close()
    print("  COPIE : %s" % copie)
    print("  retire %d ligne(s) de tete (%s) ; %d lignes restantes."
          % (len(ids), tete[0], reste))
    if not ids:
        raise SystemExit("autotest: le modele de tete n'etait pas au catalogue -- "
                         "fixture sans objet, la branche n'a pas ete parcourue.")

    vrai_db = DB
    DB = copie
    try:
        manquants = _usage_manquants(args.delai)
        vus = [m for m in manquants if m[0] == tete[0]]
        if not vus:
            raise SystemExit("autotest: ECHEC -- le modele de tete a ete retire et "
                             "n'est PAS signale manquant. La detection ne detecte rien.")
        nom, jetons, ou, ctx = vus[0]
        print("  detecte manquant : %s (%d Md/j)" % (nom, jetons))
        if ou is None:
            print("  amont ne l'annonce pas -- SIGNALE, pas ajoute. Branche d'ajout")
            print("  non parcourue : c'est le comportement voulu, pas une reussite.")
            return
        print("  amont annonce %s (ctx=%s) -- ajout." % (ou, ctx))
        ajouter(_Args(plateforme="openrouter", modele=ou, nom=nom,
                      ctx=ctx or 131072, outils=True, vision=False,
                      rang_intel=1, rang_vitesse=3, taille="Frontier",
                      rpm=20, rpd=200, budget="apercu gratuit",
                      source=SOURCE_STEALTH))
        c = sqlite3.connect(copie)
        l = c.execute("select intelligence_rank, enabled, supports_tools, source "
                      "from models where model_id = ?", (ou,)).fetchone()
        c.close()
        if l is None:
            raise SystemExit("autotest: ECHEC -- l'ajout n'a laisse aucune ligne.")
        if (l[0], l[1], l[2], l[3]) != (1, 1, 1, SOURCE_STEALTH):
            raise SystemExit("autotest: ECHEC -- ligne posee mais mal formee : "
                             "rang=%s actif=%s outils=%s src=%s" % l)
        print("  VERIFIE : rang=1, active, outillee, src=%s." % SOURCE_STEALTH)
        print("  AUTOTEST OK -- la branche d'ajout a ete parcourue de bout en bout.")
    finally:
        DB = vrai_db
        if not args.garder:
            shutil.rmtree(dossier, ignore_errors=True)
        else:
            print("  copie conservee : %s" % dossier)


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
    b.add_argument("--source", default=None,
                   help="provenance : %s pour une avant-premiere, %s sinon. "
                        "Jamais `catalog` : celle-la est la marque de l application."
                        % (SOURCE_STEALTH, SOURCE_MOISSON))
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

    i = sp.add_parser("perimer",
                      help="depingler NOS lignes dont l amont ne repond plus (jamais celles de l app)")
    i.add_argument("--appliquer", action="store_true")
    i.add_argument("--delai", type=int, default=60)
    i.set_defaults(fn=perimer)

    g = sp.add_parser("usage", help="porter en tete du bareme les gratuits massivement utilises")
    g.add_argument("--appliquer", action="store_true")
    g.set_defaults(fn=usage)

    h = sp.add_parser("demarrage",
                      help="routine de debut de session : perimer, ajouter les plus utilises, sonder")
    h.add_argument("--plateforme", default="openrouter")
    h.add_argument("--appliquer", action="store_true",
                   help="ecrire ET sonder ; sans ce drapeau, affichage seul")
    h.add_argument("--jusqu-au-rang", type=int, default=4, dest="jusqu_au_rang",
                   help="sonder les modeles jusqu a ce rang (defaut 4)")
    h.add_argument("--delai", type=int, default=90)
    h.add_argument("--moissonner", action="store_true",
                   help="ajouter le versement en masse OpenRouter -- HORS routine, il pollue")
    h.set_defaults(fn=demarrage)

    j = sp.add_parser("autotest",
                      help="faire PARCOURIR la branche d ajout, sur une copie de la base")
    j.add_argument("--delai", type=int, default=30)
    j.add_argument("--garder", action="store_true", help="ne pas effacer la copie")
    j.set_defaults(fn=autotest)

    d = sp.add_parser("sonder", help="404 avant / 200 apres, et QUI a repondu")
    d.add_argument("modele")
    d.add_argument("--delai", type=int, default=60)
    d.add_argument("--avec-outils", action="store_true", dest="avec_outils",
                   help="envoyer un vrai outil : mesure le support des tools au lieu de le supposer")
    d.set_defaults(fn=sonder)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
