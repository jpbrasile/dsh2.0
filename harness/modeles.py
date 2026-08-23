# -*- coding: utf-8 -*-
"""
modeles.py -- la boucle modeles du README (Phase 1) : catalogue OpenRouter -> SQLite ->
classement par famille de tache -> config emise (bloc provider + chaines de repli).

    python harness/modeles.py --rafraichir              GET /api/v1/models -> upsert dans modeles.sqlite
    python harness/modeles.py --classer [FAMILLE]       tableau des candidats d'une famille (toutes si omis)
    python harness/modeles.py --emettre                 ecrit providers.emis.yaml + chaines.yaml (deterministe)
    python harness/modeles.py --session                 rafraichir + emettre + installer si la config a change
                                                        (appele par scripts/dsh.ps1 au demarrage)
    python harness/modeles.py --verdict ID --tache T --preset minimal --vert|--rouge [--note ...]
                                                        note un resultat ; la probation se leve a N verts
    python harness/modeles.py --montrer ID              la fiche d'un modele
    --catalogue FICHIER   lire le catalogue dans un JSON local (tests, red team) au lieu du reseau
    --base FICHIER        autre base SQLite (tests)

Regles, en clair (README "Loops 1", "Model routes", "Rules") :
- tier OPEN = gratuit (`:free` ou prix 0) ou stealth (`stealth/...`). Un tel modele ne va
  JAMAIS sur une route PRIVATE : `tier` est calcule a chaque rafraichissement, jamais lu d'un
  verdict ni d'une option. Le reste = PRIVATE+OPEN.
- probation = 1 a l'apparition d'un stealth ou d'un gratuit, tant qu'il n'a pas N_VERTS
  verdicts verts sous le preset `minimal` (stock). La probation limite aux taches a faible
  enjeu (famille `probation`) ; la lever ne change PAS le tier.
- les routeurs `openrouter/*` (auto, free, fusion...) et les alias `~fournisseur/x-latest`
  sont gardes en base mais exclus des classements : on ne mesure jamais un modele qu'on ne
  peut pas nommer exactement.
- un catalogue malforme (pas une liste, entrees sans `id`, prix non numerique, doublons) est
  REFUSE en bloc : rien n'est ecrit, la base garde son dernier etat, code de sortie 2.
- le prix pondere = 40 x prix d'entree + 1 x prix de sortie (un tour d'agent dsh ~ 8000 tokens
  d'entree pour ~200 de sortie, mesure 2026-08-20 ; meme ratio que openrouter_cheapest_proxy).

Ce qui n'est PAS fait ici : la decision d'utiliser un modele. Le fichier emis est une
proposition relue par l'humain (diff git), puis `providers_install.py` l'applique a
~/.dsh/settings.yaml avec sauvegarde.
"""
import argparse, io, json, math, os, re, sqlite3, subprocess, sys, time, urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ICI, "modeles.sqlite")
EMIS = os.path.join(ICI, "providers.emis.yaml")
CHAINES = os.path.join(ICI, "chaines.yaml")
URL = "https://openrouter.ai/api/v1/models"
N_VERTS = 3                 # verdicts verts sous `minimal` pour lever la probation
CTX_MIN = 65536             # contexte minimal d'un candidat (seuil de compaction du harnais)
RATIO = 40                  # ponderation entree/sortie du prix
ROUTEURS = ("openrouter/", "~")       # routeurs et alias "derniere version" : non epinglables
PINNED_OUVRIER = "qwen/qwen3.8-27b"        # decision Phase 0 : ouvrier du sprint
PINNED_REDTEAM = "deepseek/deepseek-v4-pro"

SCHEMA = """
CREATE TABLE IF NOT EXISTS modeles (
  id TEXT PRIMARY KEY, provider TEXT, nom TEXT, ctx INTEGER, tool_calls INTEGER,
  free INTEGER, stealth INTEGER, probation INTEGER, tier TEXT,
  first_seen TEXT, last_seen TEXT, disparu INTEGER DEFAULT 0,
  prix_in REAL, prix_out REAL, cree INTEGER, task_scores TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS verdicts (
  id TEXT, tache TEXT, preset TEXT, date TEXT, vert INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS rafraichissements (
  date TEXT, source TEXT, total INTEGER, nouveaux TEXT, disparus TEXT);
"""


def maintenant():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ouvrir(chemin):
    c = sqlite3.connect(chemin)
    c.executescript(SCHEMA)
    return c


# ----------------------------------------------------------------- catalogue
def lire_catalogue(fichier=None):
    if fichier:
        brut = json.load(io.open(fichier, encoding="utf-8"))
    else:
        brut = json.load(urllib.request.urlopen(URL, timeout=30))
    return valider(brut)


class CatalogueInvalide(Exception):
    pass


def _prix(p, cle):
    v = (p or {}).get(cle)
    if v is None:
        return 0.0
    if isinstance(v, bool):
        raise CatalogueInvalide("prix booleen (%s=%r)" % (cle, v))
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise CatalogueInvalide("prix non numerique (%s=%r)" % (cle, v))
    if not math.isfinite(x):  # red team 1-done : "NaN" passait float() puis devenait NULL en base
        raise CatalogueInvalide("prix non fini (%s=%r)" % (cle, v))
    return x


def valider(brut):
    """Rend une liste de dicts propres ou leve CatalogueInvalide. Tout ou rien."""
    data = brut.get("data") if isinstance(brut, dict) else brut
    if not isinstance(data, list) or not data:
        raise CatalogueInvalide("le catalogue n'est pas une liste non vide")
    vus, out = set(), []
    for i, m in enumerate(data):
        if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"].strip():
            raise CatalogueInvalide("entree %d sans id" % i)
        mid = m["id"].strip()
        if mid in vus:
            raise CatalogueInvalide("id en double : %s" % mid)
        if not re.match(r"^~?[A-Za-z0-9_.:-]+/[A-Za-z0-9_.:+-]+$", mid):
            raise CatalogueInvalide("id mal forme : %r" % mid)
        vus.add(mid)
        ctx = m.get("context_length")
        if ctx is not None and not isinstance(ctx, int):
            raise CatalogueInvalide("context_length non entier pour %s" % mid)
        params = m.get("supported_parameters") or []
        if not isinstance(params, list):
            raise CatalogueInvalide("supported_parameters non liste pour %s" % mid)
        pin, pout = _prix(m.get("pricing"), "prompt"), _prix(m.get("pricing"), "completion")
        if (pin < 0 or pout < 0) and not mid.startswith(ROUTEURS):
            raise CatalogueInvalide("prix negatif pour %s" % mid)   # -1 = "variable", tolere sur un routeur seulement
        free = mid.endswith(":free") or (pin == 0 and pout == 0)
        stealth = mid.startswith("stealth/")
        out.append({
            "id": mid, "provider": mid.split("/")[0], "nom": str(m.get("name") or mid),
            "ctx": int(ctx or 0), "tool_calls": 1 if "tools" in params else 0,
            "free": 1 if free else 0, "stealth": 1 if stealth else 0,
            "prix_in": pin, "prix_out": pout, "cree": int(m.get("created") or 0),
        })
    return out


def tier_de(m):
    return "OPEN" if (m["free"] or m["stealth"]) else "PRIVATE+OPEN"


def est_routeur(mid):
    return mid.startswith(ROUTEURS)


# ----------------------------------------------------------------- base
def verts_minimal(c, mid):
    return c.execute("SELECT COUNT(*) FROM verdicts WHERE id=? AND preset='minimal' AND vert=1", (mid,)).fetchone()[0]


def probation_de(c, m):
    """Stealth ou gratuit : en probation tant que < N_VERTS verts sous minimal. Les autres : 0."""
    if not (m["free"] or m["stealth"]):
        return 0
    return 0 if verts_minimal(c, m["id"]) >= N_VERTS else 1


def rafraichir(c, catalogue, source):
    now = maintenant()
    avant = {r[0] for r in c.execute("SELECT id FROM modeles WHERE disparu=0")}
    vus = set()
    nouveaux = []
    with c:                                            # une transaction : tout ou rien
        for m in catalogue:
            vus.add(m["id"])
            tier = tier_de(m)
            prob = probation_de(c, m)
            ex = c.execute("SELECT first_seen FROM modeles WHERE id=?", (m["id"],)).fetchone()
            if ex:
                c.execute("""UPDATE modeles SET provider=?, nom=?, ctx=?, tool_calls=?, free=?, stealth=?,
                             probation=?, tier=?, last_seen=?, disparu=0, prix_in=?, prix_out=?, cree=? WHERE id=?""",
                          (m["provider"], m["nom"], m["ctx"], m["tool_calls"], m["free"], m["stealth"],
                           prob, tier, now, m["prix_in"], m["prix_out"], m["cree"], m["id"]))
            else:
                nouveaux.append(m["id"])
                c.execute("""INSERT INTO modeles (id, provider, nom, ctx, tool_calls, free, stealth, probation, tier,
                             first_seen, last_seen, disparu, prix_in, prix_out, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)""",
                          (m["id"], m["provider"], m["nom"], m["ctx"], m["tool_calls"], m["free"], m["stealth"],
                           prob, tier, now, now, m["prix_in"], m["prix_out"], m["cree"]))
        disparus = sorted(avant - vus)
        for mid in disparus:
            c.execute("UPDATE modeles SET disparu=1 WHERE id=?", (mid,))
        c.execute("INSERT INTO rafraichissements VALUES (?,?,?,?,?)",
                  (now, source, len(catalogue), json.dumps(nouveaux), json.dumps(disparus)))
    return nouveaux, disparus


def lignes(c, where="disparu=0", args=()):
    cur = c.execute("SELECT id, provider, nom, ctx, tool_calls, free, stealth, probation, tier, first_seen, last_seen, prix_in, prix_out, cree FROM modeles WHERE " + where, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ----------------------------------------------------------------- classement
def prix_pondere(m):
    return RATIO * m["prix_in"] + m["prix_out"]


def candidats(c):
    """Filtre commun : vivant, pas un routeur ni un `:batch` (API asynchrone), outils, contexte >= CTX_MIN.
    Chaque candidat recoit `score` = verts - rouges de ses verdicts (0 sans verdict) : le
    classement est "task-fit" des que des resultats existent, prix ensuite."""
    sc = {r[0]: r[1] for r in c.execute("SELECT id, SUM(CASE WHEN vert THEN 1 ELSE -1 END) FROM verdicts GROUP BY id")}
    out = []
    for m in lignes(c):
        if est_routeur(m["id"]) or m["id"].endswith(":batch") or not m["tool_calls"] or m["ctx"] < CTX_MIN:
            continue
        m["score"] = sc.get(m["id"], 0)
        out.append(m)
    return out


FAMILLES = {
    # nom : (description, filtre, cle de tri croissante)
    "ouvrier": ("payant, PRIVATE+OPEN : meilleur score de verdicts d'abord, puis le moins cher (prix pondere 40:1)",
                lambda m: m["tier"] == "PRIVATE+OPEN" and prix_pondere(m) > 0,
                lambda m: (-m["score"], prix_pondere(m), -m["ctx"], m["id"])),
    "open": ("gratuit ou stealth, OPEN seulement, hors probation : score, puis plus grand contexte",
             lambda m: m["tier"] == "OPEN" and not m["probation"],
             lambda m: (-m["score"], -m["ctx"], m["id"])),
    "probation": ("gratuit ou stealth EN probation : taches a faible enjeu sur le harnais seulement (score, puis le plus recent)",
                  lambda m: m["tier"] == "OPEN" and m["probation"],
                  lambda m: (-m["score"], -m["cree"], m["id"])),
}


def classer(c, famille):
    desc, filtre, cle = FAMILLES[famille]
    return sorted([m for m in candidats(c) if filtre(m)], key=cle)


def redteam_pour(c, ouvrier_id):
    """Payants d'une AUTRE famille de fournisseur que l'ouvrier, les moins chers d'abord."""
    fam = ouvrier_id.split("/")[0]
    return [m for m in classer(c, "ouvrier") if m["provider"] != fam]


# ----------------------------------------------------------------- emission
def _bloc_modele(m, etiquette):
    return [
        "      - id: %s" % m["id"],
        "        name: %s [%s]" % (re.sub(r"[\[\]#:]", " ", m["nom"]).strip(), etiquette),
        "        contextWindow: %d" % CTX_MIN,
        '        reasoningEfforts: { "off": , low: low, medium: medium, high: high }',
    ]


def emettre(c, date=None):
    """Ecrit providers.emis.yaml (bloc `openrouter-auto`, OPEN only) et chaines.yaml. Deterministe :
    meme base -> meme texte (la date est dans la base, pas dans le fichier)."""
    opens = classer(c, "open")[:4]
    probs = classer(c, "probation")[:4]
    ouvriers = classer(c, "ouvrier")[:6]
    rt = redteam_pour(c, PINNED_OUVRIER)[:4]
    derniere = c.execute("SELECT date, total FROM rafraichissements ORDER BY date DESC LIMIT 1").fetchone()
    en_tete = [
        "# GENERE par harness/modeles.py --emettre -- ne pas editer a la main (relire le diff git).",
        # pas de date ici : le texte doit etre identique tant que le classement ne bouge pas,
        # sinon chaque demarrage reecrirait settings.yaml (constate 23/08 16:56)
        "# Base : %s (%s modeles au dernier rafraichissement ; la date est dans la table rafraichissements)." % (os.path.basename(BASE), derniere[1] if derniere else "?"),
        "# Tier OPEN seulement : gratuits et stealth. Jamais de route PRIVATE ici, par construction",
        "# (tier calcule du catalogue, voir modeles.py). [probation] = < %d verts sous `minimal`." % N_VERTS,
        "",
        "providers:",
        "",
        "  openrouter-auto:",
        "    name: OpenRouter (auto, OPEN only -- emis par modeles.py)",
        "    apiKeyEnv: OPENROUTER_API_KEY",
        "    api: openai-completions",
        "    baseURL: https://openrouter.ai/api/v1",
        "    defaultContextWindow: %d" % CTX_MIN,
        "    models:",
    ]
    corps = []
    for m in opens:
        corps += _bloc_modele(m, "OPEN" + (", stealth" if m["stealth"] else ", free"))
    for m in probs:
        corps += _bloc_modele(m, "probation, OPEN" + (", stealth" if m["stealth"] else ", free"))
    if not corps:
        corps = ["      []"]
    texte = "\n".join(en_tete + corps) + "\n"
    io.open(EMIS, "w", encoding="utf-8", newline="\n").write(texte)

    def liste(ms):
        return "".join("  - %s   # %s, ctx %d, prix pondere %.2f $/M\n" % (m["id"], m["tier"] + (" probation" if m["probation"] else ""), m["ctx"], prix_pondere(m) * 1e6) for m in ms) or "  []\n"
    ch = [
        "# GENERE par harness/modeles.py --emettre -- chaines de repli lues par les scripts du harnais",
        "# (fumee_route.py, les ouvriers de la phase 2), pas par dsh. Ordre = ordre d'essai.",
        "# Regle : une chaine PRIVATE ne contient que des PRIVATE+OPEN ; `open` et `probation` ne",
        "# contiennent que des OPEN. L'ouvrier et le red team epingles (Phase 0) restent en tete.",
        "",
        "ouvrier:   # PRIVATE+OPEN -- epingle d'abord, puis les moins chers du catalogue",
        "  - %s   # epingle (Phase 0)\n" % PINNED_OUVRIER + liste([m for m in ouvriers if m["id"] != PINNED_OUVRIER][:4]).rstrip("\n"),
        "",
        "redteam:   # PRIVATE+OPEN, autre famille que l'ouvrier %s" % PINNED_OUVRIER,
        "  - %s   # epingle (Phase 0)\n" % PINNED_REDTEAM + liste([m for m in rt if m["id"] != PINNED_REDTEAM][:3]).rstrip("\n"),
        "",
        "open:      # OPEN only, hors probation",
        liste(opens).rstrip("\n"),
        "",
        "probation: # OPEN only, faible enjeu (harnais) jusqu'a %d verts sous minimal" % N_VERTS,
        liste(probs).rstrip("\n"),
        "",
    ]
    io.open(CHAINES, "w", encoding="utf-8", newline="\n").write("\n".join(ch))
    return texte


def verifier_emis():
    """Invariant relu sur le FICHIER emis : un seul bloc, `openrouter-auto` (red team 1-done :
    un bloc `openrouter` emis ecraserait la route payante dans providers_install), et aucun id
    de tier PRIVATE+OPEN dedans (verifie par l'appelant contre la base)."""
    import yaml
    d = yaml.safe_load(io.open(EMIS, encoding="utf-8").read())
    blocs = sorted((d or {}).get("providers") or {})
    if blocs != ["openrouter-auto"]:
        raise CatalogueInvalide("bloc(s) emis inattendu(s) : %s (seul openrouter-auto est permis)" % blocs)
    ids = [m["id"] for m in (d["providers"]["openrouter-auto"]["models"] or [])]
    return ids


# ----------------------------------------------------------------- commandes
def main(argv):
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--rafraichir", action="store_true")
    ap.add_argument("--classer", nargs="?", const="*")
    ap.add_argument("--emettre", action="store_true")
    ap.add_argument("--session", action="store_true")
    ap.add_argument("--verdict")
    ap.add_argument("--tache")
    ap.add_argument("--preset", default="minimal")
    ap.add_argument("--vert", action="store_true")
    ap.add_argument("--rouge", action="store_true")
    ap.add_argument("--note", default="")
    ap.add_argument("--montrer")
    ap.add_argument("--catalogue")
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--sans-installer", action="store_true", help="--session : ne pas appeler providers_install.py")
    A = ap.parse_args(argv)
    BASE = A.base
    c = ouvrir(A.base)

    if A.verdict:
        if A.vert == A.rouge:
            raise SystemExit("--vert ou --rouge, un seul")
        if not A.tache:
            raise SystemExit("--tache obligatoire")
        # red team 1-done-v2 (LOW) : un verdict sur un id absent ou disparu est REFUSE, sinon trois
        # verts pre-enregistres feraient naitre un futur stealth hors probation des son apparition.
        m = lignes(c, "id=? AND disparu=0", (A.verdict,))
        if not m:
            print("%s : VERDICT REFUSE, modele inconnu de la base ou disparu (rafraichir d'abord) -- rien ecrit" % A.verdict)
            return 2
        with c:
            c.execute("INSERT INTO verdicts VALUES (?,?,?,?,?,?)", (A.verdict, A.tache, A.preset, maintenant(), 1 if A.vert else 0, A.note))
            p = probation_de(c, m[0])
            c.execute("UPDATE modeles SET probation=? WHERE id=?", (p, A.verdict))
            print("%s : %s sous %s ; verts minimal = %d ; probation = %d ; tier = %s" % (
                A.verdict, "VERT" if A.vert else "ROUGE", A.preset, verts_minimal(c, A.verdict), p, m[0]["tier"]))
        return 0

    if A.montrer:
        for m in lignes(c, "id=?", (A.montrer,)):
            for k, v in m.items():
                print("  %-11s %s" % (k, v))
            print("  verdicts    %s" % c.execute("SELECT tache, preset, date, vert FROM verdicts WHERE id=? ORDER BY date", (A.montrer,)).fetchall())
            return 0
        print("inconnu : %s" % A.montrer)
        return 1

    if A.rafraichir or A.session:
        try:
            cat = lire_catalogue(A.catalogue)
        except CatalogueInvalide as e:
            print("CATALOGUE REFUSE : %s -- base inchangee" % e)
            return 2
        except (OSError, ValueError) as e:
            print("catalogue illisible (%s) -- base inchangee" % e)
            return 2
        nouveaux, disparus = rafraichir(c, cat, A.catalogue or URL)
        n = c.execute("SELECT COUNT(*) FROM modeles WHERE disparu=0").fetchone()[0]
        print("rafraichi : %d modeles (%d candidats outils+ctx>=%d) ; nouveaux %d %s ; disparus %d %s" % (
            n, len(candidats(c)), CTX_MIN, len(nouveaux), nouveaux[:6], len(disparus), disparus[:6]))

    if A.classer:
        fams = list(FAMILLES) if A.classer == "*" else [A.classer]
        for f in fams:
            print("== %s : %s" % (f, FAMILLES[f][0]))
            for m in classer(c, f)[:12]:
                print("  %-48s ctx %8d  %6.2f $/M pondere  score %+d  %s%s" % (m["id"], m["ctx"], prix_pondere(m) * 1e6, m["score"], m["tier"], " PROBATION" if m["probation"] else ""))
        print("== redteam pour %s : autre famille, payant" % PINNED_OUVRIER)
        for m in redteam_pour(c, PINNED_OUVRIER)[:6]:
            print("  %-48s ctx %8d  %6.2f $/M pondere" % (m["id"], m["ctx"], prix_pondere(m) * 1e6))

    if A.emettre or A.session:
        avant = io.open(EMIS, encoding="utf-8").read() if os.path.exists(EMIS) else ""
        texte = emettre(c)
        try:
            ids = verifier_emis()
        except CatalogueInvalide as e:
            os.remove(EMIS)
            print("INVARIANT VIOLE : %s -- fichier emis supprime" % e)
            return 3
        fuite = [i for i in ids if any(m["tier"] != "OPEN" for m in lignes(c, "id=?", (i,)))]
        if fuite:
            os.remove(EMIS)
            print("INVARIANT VIOLE : %s dans openrouter-auto sans etre OPEN -- fichier emis supprime" % fuite)
            return 3
        change = texte != avant
        print("emis : %s (%d modeles OPEN) et %s -- %s" % (os.path.basename(EMIS), len(ids), os.path.basename(CHAINES), "CHANGE" if change else "identique"))
        if A.session and change and not A.sans_installer:
            r = subprocess.run([sys.executable, os.path.join(ICI, "providers_install.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
            print("providers_install : rc=%d %s" % (r.returncode, (r.stdout or "").strip().splitlines()[-1:] if r.stdout else r.stderr[-200:]))
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
