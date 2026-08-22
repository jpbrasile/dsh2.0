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
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from dsh_effort import set_default  # noqa: E402

DSH = os.environ.get(
    "DSH_BIN",
    os.path.join(os.path.expanduser("~"), ".dsh", "runtime",
                 "dsh-0.1.1-rc.2", "node_modules", ".bin", "dsh.cmd"))
JULIA = os.environ.get("JULIA_BIN", "julia")
PROXY = os.environ.get("BENCH_PROXY", "http://127.0.0.1:8006")
PROVIDER = os.environ.get("BENCH_PROVIDER", "local-think")
MODELE = os.environ.get("BENCH_MODEL", "specdec-q38-plain-vision")

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
PREAMBULE_WEB = """Before writing any code, do these two things in order.

1. SEARCH. Use the `web_search` tool to look up the parts of this task that depend
   on facts outside your own memory: the exact semantics of a documented interface,
   the byte order or constants a format or an algorithm specifies, the published
   parameters of a numerical method. Use `web_fetch` on a source when the snippet is
   not enough. Do not skip this step, and do not search for the whole task at once --
   search for the specific facts you are unsure about.

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


def marquer(tag):
    """Pose une borne dans le journal du proxy. Sans borne, les appels du
    modele ne peuvent etre attribues a AUCUNE tache et le debit par niveau
    n'existe pas."""
    urllib.request.urlopen("%s/__mark?tag=%s" % (PROXY, tag), timeout=30).read()


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
    ok = bons == len(taches) and pris == len(taches)
    print("\nknown-GOOD %d/%d   known-BAD attrapes %d/%d   =>  %s"
          % (bons, len(taches), pris, len(taches), "CALIBRE" if ok else "NON CALIBRE"))
    return 0 if ok else 1


SESSIONS = os.path.join(os.path.expanduser("~"), ".dsh", "sessions")


def compter_web(ws, depuis):
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
    if not os.path.isdir(SESSIONS):
        return -1
    d = zstandard.ZstdDecompressor()
    cible = os.path.abspath(ws)
    n = 0
    trouve = False
    for nom in os.listdir(SESSIONS):
        chemin = os.path.join(SESSIONS, nom)
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


def un_run(effort, tache, rep=1, iteratif=False, web=False):
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
    journal_julia = os.path.join(ws, "julia_calls.log")
    if iteratif:
        env["PATH"] = SHIM + os.pathsep + env.get("PATH", "")
        env["BENCH_JULIA_LOG"] = journal_julia
    delai = TIMEOUT_ITER if iteratif else TIMEOUT

    # Le marqueur porte la REPETITION. Sans elle, les 3 passages d'une meme
    # tache portent le meme tag, et la regle "derniere fenetre" d'analyse.py
    # n'en garde qu'un : deux tiers des appels deviennent orphelins et les
    # debits de ces lignes sont faux sans en avoir l'air.
    marquer("%s|%s|r%d|debut" % (effort, tache, rep))
    t0 = time.time()
    sortie, rc, depasse = lancer_borne(
        [DSH, "--profile", "headless", CONSIGNE], ws, env, delai)
    dt = time.time() - t0
    marquer("%s|%s|r%d|fin" % (effort, tache, rep))

    io.open(os.path.join(ws, "_dsh.out"), "w", encoding="utf-8",
            errors="replace").write(str(sortie))
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
    appels_web = compter_web(ws, t0)
    rec = {"effort": effort, "tache": tache, "rep": rep,
           "mode": "iterate" if iteratif else "oneshot", "verdict": v,
           "why": why, "wall_s": round(dt, 1), "julia_runs": julia_runs,
           "a_teste": os.path.exists(os.path.join(ws, "mytest.jl")), "rc": rc,
           "bras_web": bool(web), "appels_web": appels_web}
    print("  r%d %-6s %s  %-4s  %6.1fs  julia=%-2d  web=%-3s %s"
          % (rep, effort, tache, v, dt, julia_runs,
             "n/a" if appels_web < 0 else appels_web, why[:52]))
    sys.stdout.flush()
    return rec


def main():
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

    iteratif = "--iterate" in argv
    if iteratif:
        argv.remove("--iterate")
        reel = preparer_shim()
        print("mode ITERATIF : enonces prompts_iter/, l'agent doit ecrire "
              "mytest.jl et le lancer jusqu'a ce qu'il passe.")
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
            set_default(PROVIDER, MODELE, effort)
            print("--- effort %s ---" % effort)
            sys.stdout.flush()
            for tache in taches:
                rec = un_run(effort, tache, rep, iteratif, web)
                with io.open(out, "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
