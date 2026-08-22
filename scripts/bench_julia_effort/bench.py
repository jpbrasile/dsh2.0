"""Banc : 10 taches Julia x N niveaux d'effort de raisonnement, sur un modele
servi localement par llama-server et pilote par l'agent dsh.

Ce qu'il mesure, et par quel instrument :

  reussite      -- Julia execute la solution ecrite par le modele contre un
                   fichier d'assertions qu'il n'a jamais vu. PASS/FAIL binaire.
  debit (t/s)   -- le bloc `timings` que llama-server rend lui-meme, releve par
                   le proxy enregistreur entre deux marqueurs. PAS un chrono
                   client : le chrono client compte aussi l'agent et les outils.
  temps / tache -- chrono client, du lancement de dsh au verdict. Il INCLUT
                   l'agent, les appels d'outils et Julia -- c'est precisement ce
                   qu'on veut appeler "temps par tache".

Le prompt passe par un FICHIER, jamais par la ligne de commande : mesure du
22/08, un argument multi-ligne traverse cmd.exe en se faisant manger, dsh a
recu une tache VIDE, et le modele a invente un Project Euler. Un banc qui ne
verifie pas que la consigne est arrivee mesure l'imagination du modele.

TEMOIN NEGATIF INTEGRE. Le gabarit de chat de Qwen3.8 aliase `high` sur
`xhigh` (`if resolved == 'high' -> 'xhigh'`) : verifie serveur-side via
/apply-template, les deux niveaux rendent un prompt IDENTIQUE, sha256
15c034577114cced, 352 caracteres. Les faire tourner tous les deux ne donne donc
pas deux points -- ca donne l'ETALON DE BRUIT du banc. Si l'ecart high/xhigh
depasse l'ecart entre deux vrais niveaux, la conclusion n'est pas "tel niveau
est meilleur", c'est "a 10 taches ce banc ne separe rien". C'est un resultat.

  python bench.py --selftest              calibre le verificateur (obligatoire)
  python bench.py off,low,medium,high,xhigh
  python bench.py low t03,t07             sous-ensemble
  python analyse.py                       la table
"""
import io
import json
import os
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from dsh_effort import set_default  # noqa: E402

DSH = os.environ.get(
    "DSH_BIN",
    os.path.join(os.path.expanduser("~"), ".dsh", "runtime",
                 "dsh-0.1.1-rc.2", "node_modules", ".bin", "dsh.cmd"))
JULIA = os.environ.get("JULIA_BIN", "julia")
PROXY = os.environ.get("BENCH_PROXY", "http://127.0.0.1:8006")
# Journal du fil, cote dorsale externe. En mode `auto` le routeur CHOISIT le
# modele : `MODELE` dit ce qu'on a demande, ce journal dit qui a repondu.
WIRE = os.environ.get("BENCH_WIRE")
PROVIDER = os.environ.get("BENCH_PROVIDER", "local-think")
MODELE = os.environ.get("BENCH_MODEL", "specdec-q38-plain-vision")

# --- campagne PARALLELE ---------------------------------------------------
# Pourquoi le parallelisme n'a de sens que sur la dorsale EXTERNE : le Qwen
# local est UN serveur sur UNE carte -- douze agents simultanes s'y mettraient
# en file, et le chrono par tache mesurerait la file d'attente, pas le modele.
# FreeLLMAPI agrege 16 fournisseurs derriere un endpoint et bascule tout seul
# sur 429/5xx : le parallelisme y est le mode NORMAL, et la bascule est
# exactement ce qui empeche un quota epuise d'arreter la campagne -- la
# campagne epinglee du 22/08 en est morte, 29 lancements pour 1 reussite.
PORT_PAR = int(os.environ.get("BENCH_PAR_PORT", "8020"))
AMONT_PAR = os.environ.get("BENCH_PAR_AMONT", "127.0.0.1:31415")
VERROU = threading.Lock()
# Le JUGE est serialise meme quand les agents ne le sont pas : douze harnais
# Julia lances ensemble se battent pour le CPU de la campagne locale voisine.
N_JUGES = int(os.environ.get("BENCH_JUGES", "4"))
SEM_JUGE = threading.Semaphore(N_JUGES)

TACHES = ["t%02d" % i for i in range(1, 11)]
# Palier DUR. Ajoute le 22/08 : sur la campagne one-shot de 50 runs, SIX des dix
# taches de base n'ont echoue a AUCUN niveau d'effort. Une tache que tout le
# monde reussit n'informe pas, elle dilue. Les six ci-dessous visent des pieges
# qui separent -- instabilite numerique, allocations, contrats d'interface,
# stabilite de type. Corpus SEPARE, jamais melange au corpus de base : melanger
# les deux rendrait les deux campagnes incomparables.
TACHES_DUR = ["t%02d" % i for i in range(11, 17)]
# Palier EXPERT : taches a phase de planification (plusieurs composants a
# decider avant d'ecrire). Palier LIMITE : taches ou la reference elle-meme
# etait incertaine du premier coup. Voir _generer_palier_expert.py et
# _generer_palier_limite.py pour ce que chacune piege.
TACHES_EXPERT = ["t%02d" % i for i in range(21, 27)]
TACHES_LIMITE = ["t%02d" % i for i in range(31, 37)]
CONSIGNE = "Read the file TASK.md in the current directory and do exactly what it says."

# Bras "avec recherche web prealable".
#
# Mesure qui rend ce preambule OBLIGATOIRE : sur 91 sessions du banc, 10 395
# appels d'outils et ZERO appel a web_search ou web_fetch, alors que les deux
# outils etaient declares au modele dans chacune. Laisse seul, ce modele ne
# cherche jamais. Sans instruction explicite, le bras "avec web" serait le meme
# bras que le bras "sans", et la campagne mesurerait la difference entre deux
# tirages du meme reglage.
# Le paquet de base monte `dsh-tool-web` avec `fetch: false`
# (dsh-base/cordis.patch.yml) : seul `web_search` est enregistre, et le
# greffon adapte lui-meme sa consigne dans ce cas. Un preambule qui demande
# `web_fetch` demande un outil INEXISTANT -- le modele perdrait un tour a
# l'appeler, et le bras "avec web" mesurerait cette perte au lieu de mesurer
# la recherche. Verifie dans la configuration livree le 22/08.
PREAMBULE_WEB = """Before writing any code, do these two things in order.

1. SEARCH. Use the `web_search` tool to look up the parts of this task that depend
   on facts outside your own memory: the exact semantics of a documented interface,
   the byte order or constants a format or an algorithm specifies, the published
   parameters of a numerical method. Read the snippets and the source URLs the tool
   returns -- `web_fetch` is NOT available in this composition, so the
   snippets are what you get. Do not skip this step, and do not search for
   the whole task at once -- search for the specific facts you are unsure of.

2. PLAN. Write down, in a few lines, the components you are going to write and the
   decision you took for each one. Only then write the code.

The task itself follows.

----------------------------------------------------------------------

"""
TIMEOUT = 900        # mode one-shot
TIMEOUT_ITER = 1800  # mode iteratif : l'agent tourne en boucle, il lui faut de la place
SHIM = os.path.join(BASE, "_shim")


def preparer_shim():
    """Installe un `julia` intercepteur en tete du PATH de l'agent.

    Compter les iterations en devinant -- nombre d'appels au modele, fichiers
    laisses derriere -- mesure une correlation. Ici on veut le nombre EXACT
    d'executions de Julia par l'agent, donc on l'observe la ou il se produit.

    Le shim n'est pose que dans l'environnement passe a dsh. Le verdict, lui,
    appelle Julia avec le PATH du processus parent : le juge n'est jamais
    compte comme une iteration du candidat.
    """
    reel = shutil.which("julia")
    if not reel:
        raise SystemExit("julia introuvable dans le PATH : le shim n'aurait "
                         "rien a appeler, et les iterations seraient comptees "
                         "a zero au lieu d'echouer.")
    os.makedirs(SHIM, exist_ok=True)
    # .cmd => CRLF (convention du depot), et le journal est optionnel pour que
    # le shim reste utilisable hors campagne.
    lignes = ["@echo off",
              'if defined BENCH_JULIA_LOG >>"%BENCH_JULIA_LOG%" echo %*',
              '"%s" %%*' % reel]
    io.open(os.path.join(SHIM, "julia.cmd"), "w", encoding="utf-8",
            newline="\r\n").write("\n".join(lignes) + "\n")
    return reel


def marquer(tag, slot=None, base=None):
    """Pose une borne dans le journal du proxy. Sans borne, les appels du
    modele ne peuvent etre attribues a AUCUNE tache et le debit par niveau
    n'existe pas."""
    # BENCH_PROXY vide = pas de proxy a marquer. Sur une API EXTERNE il n'y
    # en a pas, et marquer celui du modele local injecterait des bornes
    # etrangeres dans le journal d'une AUTRE campagne : analyse.py y lit
    # des fenetres, elle croirait a des appels qui n'ont jamais eu lieu.
    base = base or PROXY
    if not base:
        return
    voie = "" if slot is None else "/w%d" % slot
    urllib.request.urlopen("%s%s/__mark?tag=%s" % (base, voie, tag),
                           timeout=30).read()


def juger(fichier_solution, tache):
    """Rend (verdict, pourquoi). Le harnais imprime une seule ligne VERDICT :
    un `showerror` Julia tient sur plusieurs lignes et un `tail -1` y attrapait
    'in expression starting at ...' au lieu de la cause (defaut du 22/08)."""
    if not os.path.exists(fichier_solution):
        return "FAIL", "aucun solution.jl ecrit"
    p = subprocess.run(
        [JULIA, "--startup-file=no", "--color=no",
         os.path.join(BASE, "tasks", "harness.jl"),
         fichier_solution,
         os.path.join(BASE, "tasks", "%s_checks.jl" % tache)],
        capture_output=True, text=True, timeout=600, cwd=BASE)
    for l in (p.stdout or "").splitlines():
        if l.startswith("VERDICT PASS"):
            return "PASS", ""
        if l.startswith("VERDICT FAIL"):
            return "FAIL", l[len("VERDICT FAIL "):][:200]
    return "FAIL", "aucun verdict (rc=%d) %s" % (p.returncode, (p.stderr or "")[:200])


def selftest(taches=None):
    """Bras known-GOOD et bras known-BAD. Un verificateur dont on n'a jamais vu
    l'echec n'a pas ete montre mesurer quoi que ce soit : les 10 solutions de
    `bad/` portent chacune UN defaut nomme, et le banc exige que chacune soit
    attrapee -- et imprime PAR QUOI, parce qu'un compte egal a la population est
    exactement ce qu'un verificateur casse produit aussi."""
    taches = taches or TACHES
    n = len(taches)
    print("=== known-GOOD : ref/ doit passer %d/%d ===" % (n, n))
    bons = 0
    for t in taches:
        v, why = juger(os.path.join(BASE, "ref", "%s.jl" % t), t)
        bons += v == "PASS"
        print("  %s %s %s" % (t, v, why[:90]))
    print("=== known-BAD : bad/ doit ECHOUER %d/%d, chacune par son defaut ===" % (n, n))
    pris = 0
    for t in taches:
        v, why = juger(os.path.join(BASE, "bad", "%s.jl" % t), t)
        pris += v == "FAIL"
        print("  %s %-4s %s" % (t, v, why[:90]))
    # SECOND bras known-GOOD, ecrit independamment de ref/ (Claude Code, 22/08).
    # Le bras ref/ montre que le juge accepte LA solution de reference ; il ne
    # montre pas que le juge teste le CONTRAT plutot que les choix de conception
    # de cette solution-la. Une seconde implementation correcte, ecrite sans
    # avoir lu la premiere, est exactement ce controle-la.
    # AVIS SEULEMENT a la naissance (G10) : il rapporte, il ne refuse pas. Il a
    # deja tire une fois -- la premiere version de ref2/t35 conservait bien la
    # contenance mais laissait la borne EGALE au flottant, et le juge l'a dit :
    # [0.3, 0.30000000000000004].
    # Contamination declaree : t22, t31 et t34 ont ete ecrites apres avoir vu
    # une partie du juge (tolerances, assertions, temoins). Les neuf autres non.
    dispo = [t for t in taches
             if os.path.isfile(os.path.join(BASE, "ref2", "%s.jl" % t))]
    if dispo:
        print("=== second known-GOOD (avis) : ref2/ , ecrit sans lire ref/ ===")
        bons2 = 0
        for t in dispo:
            v, why = juger(os.path.join(BASE, "ref2", "%s.jl" % t), t)
            bons2 += v == "PASS"
            print("  %s %-4s %s" % (t, v, why[:90]))
        if bons2 < len(dispo):
            print("  !!! AVIS -- %d/%d seulement : soit ref2 est fausse, soit une"
                  " assertion teste la CONCEPTION de ref/ et pas le contrat."
                  % (bons2, len(dispo)))
        else:
            print("  second bras %d/%d : les assertions tiennent sur une AUTRE"
                  " conception correcte." % (bons2, len(dispo)))
    else:
        print("=== second known-GOOD : aucun fichier ref2/ pour ce palier ===")

    ok = bons == len(taches) and pris == len(taches)
    print("\nknown-GOOD %d/%d   known-BAD attrapes %d/%d   =>  %s"
          % (bons, len(taches), pris, len(taches), "CALIBRE" if ok else "NON CALIBRE"))
    return 0 if ok else 1


# meme accueil que celui ou dsh_effort ecrit : sinon on compterait les
# recherches web dans les sessions d'une AUTRE campagne.
#
# CALCULE PAR APPEL, plus en constante de module : en campagne parallele chaque
# ouvrier a SON accueil dsh, donc son propre repertoire de sessions. Une
# constante figee a l'import ferait compter les recherches web de l'ouvrier 0
# pour les douze.
def sessions_de(accueil=None):
    accueil = accueil or os.environ.get("DSH_HOME") or os.path.join(
        os.path.expanduser("~"), ".dsh")
    return os.path.join(accueil, "sessions")


def cle_freellm():
    """Rend la clef unifiee de FreeLLMAPI, ou leve. Jamais imprimee."""
    lecteur = os.path.join(os.path.dirname(os.path.dirname(BASE)),
                           "scripts", "freellm_key.py")
    p = subprocess.run([sys.executable, lecteur], capture_output=True, text=True)
    k = (p.stdout or "").strip()
    if p.returncode != 0 or not k.startswith("freellmapi-"):
        raise SystemExit(
            "banc: clef FreeLLMAPI illisible (%s). L'app Desktop tourne-t-elle ? "
            "Sonder `Get-Process FreeLLMAPI`. Refus de partir : une clef vide "
            "casserait qu'au premier appel, en disant 'No API key for provider'."
            % ((p.stderr or "").strip()[:120] or "code %d" % p.returncode))
    return k


def modeles_servis(t0, t1, wire=None, slot=None):
    """Rend ({modele: nb appels}, nb appels ayant bascule) sur la fenetre du run.

    Sans ca, une campagne en mode `auto` rend douze lignes toutes etiquetees
    "auto" : le verdict existe, l'executant non.

    `slot` est la VOIE de l'ouvrier. En parallele, la fenetre de temps ne
    suffit plus -- douze runs se chevauchent et chacun ramasserait les appels
    des onze autres. Filtrer sur la voie rend l'attribution exacte : une voie
    ne porte qu'un run a la fois.
    """
    wire = wire or WIRE
    if not wire or not os.path.exists(wire):
        return None, None
    vus, casc = {}, 0
    for l in io.open(wire, encoding="utf-8", errors="replace"):
        l = l.strip()
        if not l:
            continue
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("kind") != "call":
            continue
        if slot is not None and r.get("slot") != slot:
            continue
        t = (r.get("t0") or 0) / 1000.0
        if not (t0 <= t <= t1):
            continue
        m = r.get("servi")
        if m:
            vus[m] = vus.get(m, 0) + 1
        if r.get("bascule"):
            casc += 1
    return vus, casc


def compter_web(ws, depuis, accueil=None):
    """Nombre d'appels REELS a web_search / web_fetch pendant ce run.

    Le bras "sans web" ne desactive pas les outils : il ne les demande pas. La
    difference entre les deux bras n'est donc credible que si on MESURE ce que
    chaque bras a reellement appele -- un bras "sans" qui cherche quand meme est
    un bras contamine, et rien d'autre ne le montrerait.

    La source est le journal de session de dsh, compresse en zstd, range sous un
    repertoire par repertoire de travail. Comme chaque run a son propre ws, la
    correspondance est exacte. Rend -1 si la mesure n'a pas pu etre faite : c'est
    une absence de mesure, pas un zero, et l'analyse doit pouvoir les distinguer.
    """
    try:
        import zstandard
    except ImportError:
        return -1
    sessions = sessions_de(accueil)
    if not os.path.isdir(sessions):
        return -1
    d = zstandard.ZstdDecompressor()
    cible = os.path.abspath(ws)
    n = 0
    trouve = False
    for nom in os.listdir(sessions):
        chemin = os.path.join(sessions, nom)
        try:
            if os.path.getmtime(chemin) < depuis - 5:
                continue
        except OSError:
            continue
        for sous in os.listdir(chemin):
            f = os.path.join(chemin, sous, "session.jsonl.zstd")
            if not os.path.exists(f):
                continue
            try:
                with io.open(f, "rb") as fh:
                    brut = d.stream_reader(fh).read()
            except Exception:
                continue
            lignes = brut.split(b"\n")
            if not lignes:
                continue
            try:
                tete = json.loads(lignes[0])
            except Exception:
                continue
            if os.path.abspath(tete.get("cwd", "")) != cible:
                continue
            trouve = True
            for l in lignes:
                if not l.strip():
                    continue
                try:
                    e = json.loads(l)
                except Exception:
                    continue
                if "tool" not in e.get("type", ""):
                    continue
                data = e.get("data") or {}
                nom_outil = data.get("name") or data.get("toolName") or ""
                if nom_outil.startswith("web_"):
                    n += 1
    return n if trouve else -1


def _reecrire_baseurl(s, provider, url):
    """Remplace la ligne `baseURL:` DU provider nomme, ancree en texte.

    Ancre en texte et pas parse-and-dump : charger le YAML et le re-serialiser
    reecrit tout le document et perd les commentaires -- ceux-ci portent les
    pieges mesures (slugs courts, `off` booleen, apiKeyEnv), c'est-a-dire ce
    qui evite de repayer une demi-journee. Meme raison que dsh_effort.py.
    """
    lignes = s.split("\n")
    debut = None
    for i, l in enumerate(lignes):
        if re.match(r"^    " + re.escape(provider) + r":\s*$", l):
            debut = i
            break
    if debut is None:
        raise AssertionError(
            "provider `%s` introuvable : refus de router a l'aveugle." % provider)
    for j in range(debut + 1, len(lignes)):
        if re.match(r"^    \S", lignes[j]):   # provider suivant, meme indentation
            break
        if re.match(r"^\s+baseURL:", lignes[j]):
            lignes[j] = "      baseURL: %s" % url
            return "\n".join(lignes)
    raise AssertionError(
        "aucune ligne baseURL sous `%s` : refus d'en ajouter une a l'aveugle."
        % provider)


def preparer_voies(n, effort):
    """Cree n accueils dsh isoles ; l'ouvrier k parle a la voie /wk.

    Deux etats partages rendaient le parallelisme faux, chacun repare ici :
      - `agent-default-model` est UNE ligne globale. N ouvriers dessus, et
        chacun change le modele des autres en plein run. => un settings.yaml
        par ouvrier, via DSH_HOME.
      - l'attribution des appels se faisait par fenetre de temps. En parallele
        les fenetres se chevauchent : chaque run ramasserait les appels des
        autres. => une VOIE par ouvrier dans l'enregistreur.
    Rend [(accueil, slot, wire)].
    """
    src = os.path.join(
        os.environ.get("DSH_HOME") or os.path.join(os.path.expanduser("~"), ".dsh"),
        "settings.yaml")
    s = io.open(src, encoding="utf-8").read()
    racine = os.path.join(BASE, "_par")
    os.makedirs(racine, exist_ok=True)
    voies = []
    for k in range(n):
        acc = os.path.join(racine, "w%d" % k)
        os.makedirs(acc, exist_ok=True)
        cible = os.path.join(acc, "settings.yaml")
        # UN PORT PAR OUVRIER. Le prefixe de chemin (.../wK/v1) a ete essaye et
        # mesure faux : dsh normalise la baseURL et le jette, 47 appels sur 47
        # sont arrives sans voie. Le port, lui, ne se normalise pas.
        io.open(cible, "w", encoding="utf-8", newline="\n").write(
            _reecrire_baseurl(s, PROVIDER,
                              "http://127.0.0.1:%d/v1" % (PORT_PAR + k)))
        set_default(PROVIDER, MODELE, effort, cible)
        voies.append((acc, k, os.path.join(acc, "wire.jsonl"),
                      "http://127.0.0.1:%d" % (PORT_PAR + k)))
    return voies


def _ecoute(port, delai=15):
    """Attente ACTIVE de l'ecoute, jamais un sleep : un proxy pas encore ouvert
    donne N runs qui echouent en 2 s sur ECONNREFUSED, et la campagne rend N
    FAIL avec la mauvaise cause."""
    fin = time.time() + delai
    while time.time() < fin:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            pass
        finally:
            s.close()
        time.sleep(0.3)
    return False


def lancer_enregistreurs(voies):
    """Un enregistreur par ouvrier, chacun sur SON port et SON journal."""
    hote, port = AMONT_PAR.split(":")
    procs = []
    for acc, k, wire, base in voies:
        if os.path.exists(wire):
            os.remove(wire)
        env = dict(os.environ)
        env["PROXY_PORT"] = str(PORT_PAR + k)
        env["PROXY_LOG"] = wire
        env["PROXY_SLOT"] = str(k)
        env["UP_HOST"] = hote
        env["UP_PORT"] = port
        p = subprocess.Popen(["node", os.path.join(BASE, "proxy.mjs")],
                             cwd=BASE, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if p.poll() is not None or not _ecoute(PORT_PAR + k):
            for q in procs:
                tuer_arbre(q)
            raise SystemExit(
                "enregistreur w%d muet sur le port %d (deja occupe ?) -- refus "
                "de partir : la campagne rendrait des FAIL de connexion."
                % (k, PORT_PAR + k))
        procs.append(p)
    print("enregistreurs %d..%d -> %s"
          % (PORT_PAR, PORT_PAR + len(voies) - 1, AMONT_PAR))
    return procs


def tuer_arbre(p):
    """Tue le processus ET tous ses descendants."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                       capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            pass
    try:
        p.kill()
    except OSError:
        pass


def lancer_borne(cmd, cwd, env, delai):
    """Lance une commande sous echeance et tue TOUT L'ARBRE si elle deborde.

    Defaut mesure le 22/08 : il a fige une campagne 689 s et l'aurait figee
    indefiniment. `subprocess.run(timeout=)` ne tue que le fils DIRECT. Ici le
    fils direct est `dsh.cmd` ; l'agent lui-meme est le PETIT-fils. A
    l'echeance, le .cmd meurt, l'agent survit -- orphelin, toujours en train
    d'appeler le modele et d'occuper la carte -- et il garde le tuyau de sortie
    ouvert. Le communicate() que Python enchaine apres le kill attend alors la
    fermeture de ce tuyau, c'est-a-dire POUR TOUJOURS.

    Constate sur r2/high/t11 : echeance 900 s, duree relevee 1588,9 s, aucun
    essai suivant pendant tout ce temps, et le journal du proxy montrait
    l'orphelin encore actif. Aucun nombre deja publie ne l'aurait montre ; ce
    qui l'a montre, c'est duree > echeance -- controle desormais cable dans
    analyse.py.

    Rend (sortie, code de retour, a_depasse).
    """
    kw = {}
    if os.name != "nt":
        kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, **kw)
    try:
        out, err = proc.communicate(timeout=delai)
        return (out or "") + (err or ""), proc.returncode, False
    except subprocess.TimeoutExpired:
        tuer_arbre(proc)
        # Seconde echeance, courte. Si le tuyau n'est toujours pas ferme 60 s
        # apres avoir tue l'arbre, c'est qu'un descendant a echappe au kill :
        # on rend la main plutot que de figer la campagne. Un run perdu se
        # remesure, une campagne figee ne se remesure pas.
        try:
            out, err = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            out, err = "", "arbre non ferme 60 s apres le kill"
        return ("TIMEOUT %ds" % delai + chr(10)
                + ((out or "") + (err or ""))[-2000:], -1, True)


def un_run(effort, tache, rep=1, iteratif=False, web=False,
           slot=None, accueil=None, wire=None, proxy_base=None):
    ws = os.path.join(BASE, "runs", "r%02d" % rep, effort, tache)
    if os.path.isdir(ws):
        shutil.rmtree(ws)
    os.makedirs(ws)
    dossier = "prompts_iter" if iteratif else "prompts"
    consigne = io.open(os.path.join(BASE, dossier, "%s.txt" % tache),
                       encoding="utf-8").read()
    if web:
        consigne = PREAMBULE_WEB + consigne
    io.open(os.path.join(ws, "TASK.md"), "w", encoding="utf-8",
            newline="\n").write(consigne)
    env = dict(os.environ)
    env.setdefault("DSH_LOCAL_API_KEY", "local-loopback-noauth")
    # Accueil dsh de l'ouvrier : sa configuration, ses sessions, sa voie vers
    # l'enregistreur. Sans lui, les N ouvriers se disputent les trois lignes de
    # `agent-default-model` et chacun change le modele des autres en plein run.
    if accueil:
        env["DSH_HOME"] = accueil
    if PROVIDER == "freellm":
        # `apiKeyEnv` DECLARE n'est pas `apiKeyEnv` DEFINI. Une variable vide
        # ne casse qu'au PREMIER APPEL, et sous une forme trompeuse :
        # "PI_AI_ERROR: No API key for provider". Le banc refuse donc de
        # partir plutot que de rendre 90 runs FAIL avec la mauvaise cause.
        env["DSH_FREELLM_API_KEY"] = cle_freellm()
    journal_julia = os.path.join(ws, "julia_calls.log")
    # SHIM DANS LES DEUX MODES (repare le 22/08). Il n'etait pose qu'en mode
    # iteratif : en un coup, `BENCH_JULIA_LOG` n'existait pas, le shim n'etait
    # pas dans le PATH, et `julia_runs` valait donc 0 PAR CONSTRUCTION pour
    # toute la population -- quoi qu'ait fait le modele. Un compteur qui rend
    # la meme valeur pour tous les runs ne mesure rien, et celui-la a ete
    # publie comme "zero execution de Julia", c'est-a-dire comme un resultat.
    # Le mode un coup ne DEMANDE pas de lancer Julia ; savoir si le modele le
    # fait quand meme est precisement ce qui separe "il a verifie" de "il
    # affirme avoir verifie".
    env["PATH"] = SHIM + os.pathsep + env.get("PATH", "")
    env["BENCH_JULIA_LOG"] = journal_julia
    delai = TIMEOUT_ITER if iteratif else TIMEOUT

    # Le marqueur porte la REPETITION. Sans elle, les 3 passages d'une meme
    # tache portent le meme tag, et la regle "derniere fenetre" d'analyse.py
    # n'en garde qu'un : deux tiers des appels deviennent orphelins et les
    # debits de ces lignes sont faux sans en avoir l'air.
    marquer("%s|%s|r%d|debut" % (effort, tache, rep), slot, proxy_base)
    t0 = time.time()
    sortie, rc, depasse = lancer_borne(
        [DSH, "--profile", "headless", CONSIGNE], ws, env, delai)
    dt = time.time() - t0
    marquer("%s|%s|r%d|fin" % (effort, tache, rep), slot, proxy_base)

    io.open(os.path.join(ws, "_dsh.out"), "w", encoding="utf-8",
            errors="replace").write(str(sortie))
    # Le juge est SERIALISE, pas l'agent. Douze harnais Julia lances ensemble
    # se battent pour le meme CPU que la campagne locale qui tourne a cote --
    # et un juge qui rame allonge le chrono qu'il est cense mesurer.
    with SEM_JUGE:
        v, why = juger(os.path.join(ws, "solution.jl"), tache)
    if depasse:
        v, why = "FAIL", "timeout %ds" % delai
    # Nombre EXACT d'executions de Julia par l'agent, releve par le shim.
    # 0 en mode iteratif est un resultat, pas une donnee manquante : cela veut
    # dire que le modele a repondu DONE sans jamais lancer ce qu'on lui a
    # explicitement demande de lancer.
    julia_runs = 0
    if os.path.exists(journal_julia):
        julia_runs = sum(1 for _ in io.open(journal_julia, encoding="utf-8",
                                            errors="replace"))
    appels_web = compter_web(ws, t0, accueil)
    rec = {"effort": effort, "tache": tache, "rep": rep,
           "mode": "iterate" if iteratif else "oneshot", "verdict": v,
           "why": why, "wall_s": round(dt, 1), "julia_runs": julia_runs,
           "a_teste": os.path.exists(os.path.join(ws, "mytest.jl")), "rc": rc,
           "bras_web": bool(web), "appels_web": appels_web,
           # QUI a repondu. Depuis le 22/08 le banc sert deux dorsales --
           # le Qwen local et une API externe via FreeLLMAPI. Une ligne
           # sans provider/modele n'est attribuable a aucun executant, et
           # deux campagnes deviennent un seul tas de chiffres.
           "provider": PROVIDER, "modele": MODELE}
    if slot is not None:
        rec["slot"] = slot
    servis, casc = modeles_servis(t0, time.time(), wire, slot)
    if servis is not None:
        rec["servis"] = servis          # qui a REPONDU, et combien de fois
        rec["appels_bascules"] = casc   # appels ou le routeur a du changer de route
    with VERROU:
        print("  r%d %-6s %s  %-4s  %6.1fs  julia=%-2d  web=%-3s %s%s"
              % (rep, effort, tache, v, dt, julia_runs,
                 "n/a" if appels_web < 0 else appels_web,
                 "" if slot is None else "w%d " % slot, why[:52]))
        sys.stdout.flush()
    return rec


def main():
    # DIRE D'OU L'ON TOURNE, a chaque lancement. Le 22/08 la campagne tournait
    # depuis une COPIE du banc figee dans le repertoire temporaire d'une session
    # terminee : deux heures de correctifs -- l'orphelin, les paliers t21..t36,
    # trois controles cables -- n'etaient dans aucun processus en cours. Rien
    # dans la sortie ne le disait. "j'ai corrige bench.py" et "le correctif
    # tourne" sont deux affirmations differentes ; cette ligne est la seule qui
    # transforme la seconde en mesure.
    print("banc : %s" % BASE)
    argv = list(sys.argv[1:])
    if argv and argv[0] == "--selftest":
        if len(argv) > 1:
            paliers = {"dur": TACHES_DUR, "expert": TACHES_EXPERT,
                       "limite": TACHES_LIMITE}
            liste = paliers.get(argv[1]) or argv[1].split(",")
        else:
            liste = TACHES
        raise SystemExit(selftest(liste))

    reps = 1
    if "--reps" in argv:
        i = argv.index("--reps")
        reps = int(argv[i + 1])
        del argv[i:i + 2]

    par = 1
    if "--par" in argv:
        i = argv.index("--par")
        par = int(argv[i + 1])
        del argv[i:i + 2]

    iteratif = "--iterate" in argv
    if iteratif:
        argv.remove("--iterate")
        print("mode ITERATIF : enonces prompts_iter/, l'agent doit ecrire "
              "mytest.jl et le lancer jusqu'a ce qu'il passe.")
    # Le shim est pose DANS LES DEUX MODES : en un coup, son absence rendait
    # julia_runs = 0 pour toute la population, ce qui se lisait comme une
    # mesure alors que c'etait une impossibilite structurelle.
    reel = preparer_shim()
    print("shim julia -> %s  (les executions de l'agent sont comptees)" % reel)

    defaut = TACHES
    for drapeau, liste, nom in (("--dur", TACHES_DUR, "DUR"),
                                ("--expert", TACHES_EXPERT, "EXPERT"),
                                ("--limite", TACHES_LIMITE, "LIMITE")):
        if drapeau in argv:
            argv.remove(drapeau)
            defaut = liste
            print("corpus %s : %s" % (nom, ",".join(defaut)))

    web = "--web" in argv
    if web:
        argv.remove("--web")
        print("bras AVEC RECHERCHE WEB : le preambule impose search puis plan.")
        print("  Les appels web reellement passes sont comptes par run "
              "(colonne web=) -- un bras 'sans' qui cherche quand meme se voit.")

    efforts = argv[0].split(",") if argv else ["off", "low", "medium", "high", "xhigh"]
    taches = argv[1].split(",") if len(argv) > 1 else defaut
    out = os.path.join(BASE, "resultats.jsonl")

    def ecrire(rec):
        with VERROU:
            with io.open(out, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec) + "\n")

    voies, procs = None, []
    if par > 1:
        if PROVIDER == "local-think":
            print("!!! AVIS -- %d ouvriers sur la dorsale LOCALE : un seul "
                  "serveur, une seule carte. Le chrono par tache mesurerait la "
                  "file d'attente, pas le modele." % par)
        voies = preparer_voies(par, efforts[0])
        procs = lancer_enregistreurs(voies)
        print("campagne PARALLELE : %d ouvriers, un port et un journal chacun, "
              "%d juges Julia au plus." % (par, N_JUGES))
    sys.stdout.flush()

    try:
        boucle(reps, efforts, taches, par, iteratif, web, ecrire, voies)
    finally:
        for q in procs:
            tuer_arbre(q)


def boucle(reps, efforts, taches, par, iteratif, web, ecrire, voies=None):
    for rep in range(1, reps + 1):
        # La REPETITION est la boucle EXTERIEURE, et le sens alterne.
        # Repeter une tache 3 fois d'affilee mesurerait 3 fois le meme instant
        # de la machine ; parcourir la campagne entiere 3 fois etale chaque
        # niveau sur les 3 moments. Et comme les bras tournent en sequence, un
        # niveau toujours lance en dernier heriterait de toute derive
        # monotone : le sens alterne pour qu'aucun bras ne reste en queue.
        # Ce n'est PAS un equilibrage exact -- a 3 repetitions il n'existe pas.
        ordre = efforts if rep % 2 else list(reversed(efforts))
        print("=== repetition %d/%d  (ordre : %s) ===" % (rep, reps, ",".join(ordre)))
        sys.stdout.flush()
        for effort in ordre:
            print("--- effort %s ---" % effort)
            sys.stdout.flush()
            if par > 1:
                # Le niveau d'effort reste la boucle EXTERIEURE, meme en
                # parallele : il vit dans le settings.yaml de chaque ouvrier,
                # donc melanger deux niveaux dans un meme lot demanderait de
                # reecrire la configuration sous un run en cours.
                # Les ports et les journaux sont poses une fois pour toute
                # la campagne ; seul le NIVEAU change d'un lot a l'autre, et il
                # se reecrit dans le settings.yaml de chaque ouvrier -- jamais
                # sous un run en cours, puisque le lot precedent est joint.
                for acc, _k, _w, _b in voies:
                    set_default(PROVIDER, MODELE, effort,
                                os.path.join(acc, "settings.yaml"))
                libres = queue.Queue()
                for v in voies:
                    libres.put(v)

                def travail(tache, _e=effort, _r=rep):
                    acc, slot, wire, base = libres.get()
                    try:
                        return un_run(_e, tache, _r, iteratif, web,
                                      slot, acc, wire, base)
                    finally:
                        libres.put((acc, slot, wire, base))

                with ThreadPoolExecutor(max_workers=par) as ex:
                    futurs = {ex.submit(travail, t): t for t in taches}
                    for f, t in futurs.items():
                        try:
                            ecrire(f.result())
                        except Exception as e:
                            # Un run qui explose ne doit pas emporter le lot :
                            # il se remesure, une campagne perdue non.
                            with VERROU:
                                print("  %s ERREUR OUVRIER %s" % (t, e))
                            ecrire({"effort": effort, "tache": t, "rep": rep,
                                    "verdict": "FAIL", "why": "ouvrier: %s" % e,
                                    "provider": PROVIDER, "modele": MODELE})
            else:
                set_default(PROVIDER, MODELE, effort)
                for tache in taches:
                    ecrire(un_run(effort, tache, rep, iteratif, web))


if __name__ == "__main__":
    main()
