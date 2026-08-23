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
A = ap.parse_args()
MODELE, PROVIDER = A.modele, A.provider
PORT = int(os.environ.get("FUMEE_PORT", "8050"))
ABSENTS = [x for x in A.attend_absent.split(",") if x]
PRESENTS = [x for x in A.attend_present.split(",") if x]

acc = os.path.join(S, "home")
ws = os.path.join(S, "ws")
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
tache = A.tache or ("Create a file named PONG.txt in the current directory containing exactly the "
                    "single word PONG. Then stop. Do not ask questions.")
env2 = dict(os.environ, DSH_HOME=acc)
args = [bench.DSH, "--profile", "headless"]
for p in A.patch:
    args += ["--patch", os.path.abspath(p)]
args.append(tache)
t0 = time.time()
try:
    p = subprocess.run(args, cwd=ws, env=env2, capture_output=True, text=True, timeout=300)
    rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
except subprocess.TimeoutExpired as e:
    rc, out = "timeout", str(e)
dt = time.time() - t0
bench.tuer_arbre(px)
io.open(os.path.join(S, "dsh_out.txt"), "w", encoding="utf-8").write(out)

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
raise SystemExit(0 if not fautes else 1)
