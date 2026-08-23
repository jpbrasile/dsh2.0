# -*- coding: utf-8 -*-
"""Fumee d une ROUTE : un run dsh headless, enregistreur -> amont, modele epingle.

    python fumee_route.py [modele] [provider] [options]
        defaut : qwen/qwen3.8-27b, openrouter-banc

    options (phase 0, 23/08) :
      --patch <yml>            couche patch dsh (--patch), repetable -- le preset Lean
      --tache "<texte>"        remplace la tache PONG par defaut
      --attend-absent a,b      ECHEC si un appel offre l un de ces outils
      --attend-present a,b     ECHEC si le premier appel avec outils n offre pas chacun
      --amont <hote>           amont de l enregistreur (defaut : derive du baseURL du
                               provider ; openrouter.ai si ce baseURL est deja local)
      --fichier <nom>          fichier attendu dans l espace de travail (defaut PONG.txt ;
                               `-` = aucun fichier attendu)

Preuve attendue dans _fumee/wire.jsonl : chaque appel `servi` par le modele
demande, avec usage et ms, et le fichier attendu ecrit. Un HTTP 200 ne prouve
rien : c est `servi` qui nomme qui a repondu. Le fil porte aussi les NOMS des
outils offerts et la taille du prompt systeme : c est la seule preuve de ce
que le modele RECOIT (un --dump-config prouve la composition, pas l envoi).
Tout est isole (DSH_HOME et espace de travail sous _fumee/, gitignore). Mesure
du 23/08 : ce test a attrape un arbre dsh vide (bin.js absent) et un modele
sans bloc `reasoningEfforts` (dsh refuse `off`) avant la premiere campagne."""
import argparse, io, json, os, re, shutil, subprocess, sys, time, urllib.request

BENCH = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(BENCH, "_fumee")
sys.path.insert(0, BENCH)
os.chdir(BENCH)
import bench  # noqa: E402  (dsh_effort.set_default, _reecrire_baseurl, DSH, tuer_arbre)

ap = argparse.ArgumentParser(add_help=True)
ap.add_argument("modele", nargs="?", default="qwen/qwen3.8-27b")
ap.add_argument("provider", nargs="?", default="openrouter-banc")
ap.add_argument("--patch", action="append", default=[])
ap.add_argument("--tache", default=None)
ap.add_argument("--attend-absent", default="")
ap.add_argument("--attend-present", default="")
ap.add_argument("--amont", default=os.environ.get("FUMEE_AMONT"))
ap.add_argument("--fichier", default="PONG.txt")
ap.add_argument("--effort", default="off")
ap.add_argument("--cwd", default=None, help="espace de travail de dsh (defaut : _fumee/ws) ; "
                "un depot reel pour une tache reelle (critere Done de la phase 0)")
ap.add_argument("--delai", type=int, default=300, help="secondes avant de tuer dsh (defaut 300)")
ap.add_argument("--tache-fichier", default=None, help="lire la tache dans ce fichier (UTF-8)")
A = ap.parse_args()
MODELE, PROVIDER = A.modele, A.provider
PORT = int(os.environ.get("FUMEE_PORT", "8050"))
ABSENTS = [x for x in A.attend_absent.split(",") if x]
PRESENTS = [x for x in A.attend_present.split(",") if x]

acc = os.path.join(S, "home")
ws = os.path.abspath(A.cwd) if A.cwd else os.path.join(S, "ws")
for d in (acc, ws):
    os.makedirs(d, exist_ok=True)
wire = os.path.join(S, "wire.jsonl")
if os.path.exists(wire):
    os.remove(wire)
attendu = None if A.fichier == "-" else os.path.join(ws, A.fichier)
if attendu and os.path.exists(attendu):
    os.remove(attendu)

# Accueil dsh isole : le settings.yaml de l utilisateur, baseURL du provider
# redirigee vers l enregistreur (meme CHEMIN que l amont : l enregistreur
# transmet le chemin tel quel), modele epingle, raisonnement `off`.
# Le fichier de credentials de dsh est copie tel quel : c est la SEULE source de
# cles que l accueil isole connaisse (phase 0 : cles dans le fichier, pas dans
# l env du process).
home = os.path.expanduser("~")
src = os.path.join(home, ".dsh", "settings.yaml")
s = io.open(src, encoding="utf-8").read()
m = re.search(r"(?m)^    " + re.escape(PROVIDER) + r":\s*\n(?:^(?!    \S).*\n)*?^\s+baseURL:\s*(\S+)", s)
if not m:
    raise SystemExit("provider `%s` sans baseURL dans %s" % (PROVIDER, src))
base = m.group(1)
mu = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", base)
if not mu:
    raise SystemExit("baseURL illisible pour `%s` : %s" % (PROVIDER, base))
sch, hote, port_amont, chemin = mu.group(1), mu.group(2), mu.group(3), (mu.group(4) or "/v1").rstrip("/")
if A.amont:
    UP_HOST, UP_TLS, UP_PORT = A.amont, "1", "443"
elif hote in ("127.0.0.1", "localhost"):
    # deja une route enregistree (openrouter-banc -> :8050) : l amont reel
    # n est pas dans le fichier, on prend le defaut historique.
    UP_HOST, UP_TLS, UP_PORT = "openrouter.ai", "1", "443"
else:
    UP_HOST, UP_TLS, UP_PORT = hote, ("1" if sch == "https" else "0"), (port_amont or ("443" if sch == "https" else "80"))
cible = os.path.join(acc, "settings.yaml")
bench.ecrire_texte(cible, bench._reecrire_baseurl(s, PROVIDER, "http://127.0.0.1:%d%s" % (PORT, chemin)))
bench.set_default(PROVIDER, MODELE, A.effort, cible)
cred = os.path.join(home, ".dsh", ".credentials.yaml")
if os.path.exists(cred):
    shutil.copyfile(cred, os.path.join(acc, ".credentials.yaml"))

# Greffons locaux (scripts/dsh-plugins/*) : l accueil isole est scaffolde par
# dsh lui-meme (profil headless vierge), il n a donc pas les jonctions que
# `dsh.ps1 -InstallPlugins` pose dans ~/.dsh. On les COPIE ici a chaque run
# (accueil jetable) : une couche `--patch` qui nomme `dsh-secret-redactor` ou
# `dsh-read-wall` echouait sinon au chargement (ERR_MODULE_NOT_FOUND, 23/08).
greffons = os.path.join(os.path.dirname(os.path.dirname(BENCH)), "scripts", "dsh-plugins")
nm = os.path.join(acc, "profiles", "headless", "node_modules")
if os.path.isdir(greffons):
    os.makedirs(nm, exist_ok=True)
    for g in os.listdir(greffons):
        d = os.path.join(nm, g)
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(os.path.join(greffons, g), d)

# Enregistreur -> amont.
env = dict(os.environ, PROXY_PORT=str(PORT), PROXY_LOG=wire, PROXY_SLOT="0",
           UP_HOST=UP_HOST, UP_PORT=str(UP_PORT), UP_TLS=UP_TLS)
px = subprocess.Popen(["node", os.path.join(BENCH, "proxy.mjs")], cwd=BENCH, env=env,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d%s/models" % (PORT, chemin), timeout=2).read()
        break
    except urllib.error.HTTPError:
        break          # l amont a repondu (meme 401/404) : l enregistreur est la
    except Exception:
        time.sleep(0.5)
else:
    px.kill()
    raise SystemExit("enregistreur muet sur %d (port occupe ?)" % PORT)

# La tache : ecrire un fichier, puis s arreter. Pas de Julia, pas de juge.
if A.tache_fichier:
    A.tache = io.open(A.tache_fichier, encoding="utf-8").read()
tache = A.tache or ("Create a file named PONG.txt in the current directory containing exactly the "
                    "single word PONG. Then stop. Do not ask questions.")
env2 = dict(os.environ, DSH_HOME=acc)
args = [bench.DSH, "--profile", "headless"]
for p in A.patch:
    args += ["--patch", os.path.abspath(p)]
args.append(tache)
t0 = time.time()
# Popen + tuer_arbre, PAS subprocess.run(timeout=) : sous Windows, run() ne tue
# que l enfant direct (dsh.cmd) ; le node dsh orphelin continue d appeler le
# modele ET garde les tubes ouverts, donc run() bloque pour toujours (constate
# le 23/08 : 33 appels payes apres le delai, script fige).
# encoding explicite : sans lui, text=True decode en cp1252 et le rapport UTF-8 de
# l'agent arrive en mojibake (constate sur redteam/0-lean.md et 0-walls.md le 23/08)
p = subprocess.Popen(args, cwd=ws, env=env2, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     text=True, encoding="utf-8", errors="replace")
try:
    so, se = p.communicate(timeout=A.delai)
    rc, out, sortie = p.returncode, (so or "") + (se or ""), (so or "")
except subprocess.TimeoutExpired:
    bench.tuer_arbre(p)
    so, se = p.communicate()
    rc, out, sortie = "timeout", (so or "") + (se or "") + "\n[fumee_route] delai %ds depasse : arbre dsh tue\n" % A.delai, (so or "")
dt = time.time() - t0
bench.tuer_arbre(px)
io.open(os.path.join(S, "dsh_out.txt"), "w", encoding="utf-8").write(out)
# stdout seul = la reponse finale de l agent (sans les annonces stderr des greffons)
io.open(os.path.join(S, "dsh_stdout.txt"), "w", encoding="utf-8").write(sortie)

print("route %s / %s  amont=%s%s  patchs=%s" % (PROVIDER, MODELE, UP_HOST, chemin, ",".join(A.patch) or "-"))
print("dsh rc=%s  duree=%.1fs" % (rc, dt))
if attendu:
    print("%s :" % A.fichier, io.open(attendu, encoding="utf-8").read().strip()[:80] if os.path.exists(attendu) else "ABSENT")
calls = [json.loads(l) for l in io.open(wire, encoding="utf-8")] if os.path.exists(wire) else []
calls = [c for c in calls if c.get("kind") == "call"]
print("appels enregistres : %d" % len(calls))
for c in calls:
    u = c.get("usage") or {}
    st = c.get("sent") or {}
    print("  servi=%-26s status=%s ms=%-6s in=%s out=%s  n_messages=%s n_tools=%s sys_chars=%s"
          % (c.get("servi"), c.get("status"), c.get("ms"), u.get("prompt_tokens"),
             u.get("completion_tokens"), st.get("n_messages"), st.get("n_tools"), st.get("sys_chars")))
outilles = [c for c in calls if (c.get("sent") or {}).get("n_tools")]
if outilles:
    print("outils offerts (1er appel outille) :", " ".join(sorted((outilles[0].get("sent") or {}).get("tools") or [])))

fautes = []
if not calls:
    fautes.append("aucun appel enregistre")
for c in calls:
    if c.get("servi") != MODELE:
        fautes.append("appel servi par %s, pas %s" % (c.get("servi"), MODELE))
        break
if attendu and not os.path.exists(attendu):
    fautes.append("%s absent" % A.fichier)
for c in outilles:
    vus = set((c.get("sent") or {}).get("tools") or [])
    fuite = sorted(vus & set(ABSENTS))
    if fuite:
        fautes.append("outil(s) qui devaient etre ABSENTS et sont offerts : %s" % ",".join(fuite)); break
if PRESENTS:
    if not outilles:
        fautes.append("aucun appel avec outils, impossible de verifier --attend-present")
    else:
        vus = set((outilles[0].get("sent") or {}).get("tools") or [])
        manque = sorted(set(PRESENTS) - vus)
        if manque:
            fautes.append("outil(s) attendus et absents : %s" % ",".join(manque))
if fautes and rc not in (0, None):
    for l in out.splitlines():
        if l.strip() and "warn" not in l.lower():
            print("  dsh :", l.strip()[:160])
            break
print("VERDICT :", ("OK -- chaque appel servi par %s%s" % (MODELE, ", fichier ecrit" if attendu else ""))
      if not fautes else "ECHEC -- " + " ; ".join(fautes) + " (voir _fumee/dsh_out.txt)")
# Compteur de cout (Phase 1) : chaque run verse son fil dans harness/_cout/grand_livre.jsonl.
# Le fil est ecrase au run suivant ; le grand livre, lui, reste. Campagne = FUMEE_CAMPAGNE
# (redteam_run.py la pose) sinon provider/modele. Un echec d'ingestion ne change pas le verdict.
if calls:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(BENCH), "..", "harness"))
        import cout as _cout
        n_aj, n_tot, ign = _cout.ingerer(wire, os.environ.get("FUMEE_CAMPAGNE") or "%s/%s" % (PROVIDER, MODELE))
        usd = sum(float((c.get("usage") or {}).get("cost") or 0) for c in calls)
        ci = sum(int(((c.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") or 0) for c in calls)
        pi = sum(int((c.get("usage") or {}).get("prompt_tokens") or 0) for c in calls)
        print("cout : %.4f USD ce run, cache %.0f%% (%d/%d tokens d'entree) ; grand livre +%d (%d appels)%s" % (
            usd, (100.0 * ci / pi) if pi else 0.0, ci, pi, n_aj, n_tot, " ; %d doublon(s) ignore(s)" % len(ign) if ign else ""))
        for x in ign:
            print("   ", x)
    except Exception as e:  # noqa: BLE001
        print("cout : ingestion echouee (%s) -- le fil reste dans %s" % (e, wire))
# Verdict de modele (Phase 1, red team 1-done HIGH) : chaque run dont TOUS les appels ont ete servis
# par le modele demande note VERT (run OK) ou ROUGE (echec) dans harness/modeles.sqlite sous le preset
# effectif (`minimal` = stock sans --patch, sinon le nom du patch) ; N_VERTS verts sous `minimal`
# levent la probation d'un modele OPEN (voir modeles.py). FUMEE_SANS_VERDICT=1 pour ne rien noter.
if calls and not os.environ.get("FUMEE_SANS_VERDICT"):
    if all(c.get("servi") == MODELE for c in calls):
        preset = "minimal" if not A.patch else "+".join(re.sub(r"\.patch\.ya?ml$", "", os.path.basename(p)) for p in A.patch)
        tache = "fumee:" + (os.path.basename(A.tache_fichier) if A.tache_fichier else ("PONG" if A.tache is None else A.tache[:40]))
        try:
            r = subprocess.run([sys.executable, os.path.join(os.path.dirname(BENCH), "..", "harness", "modeles.py"),
                                "--verdict", MODELE, "--tache", tache, "--preset", preset,
                                "--vert" if not fautes else "--rouge", "--note", "%s ; %d appels ; %.1fs ; %s" % (PROVIDER, len(calls), dt, " ; ".join(fautes)[:200])],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            print("verdict note :", ((r.stdout or r.stderr).strip().splitlines() or ["?"])[-1])
        except Exception as e:  # noqa: BLE001
            print("verdict non note (%s)" % e)
    else:
        print("verdict non note : au moins un appel servi par un autre modele que %s" % MODELE)
raise SystemExit(0 if not fautes else 1)
