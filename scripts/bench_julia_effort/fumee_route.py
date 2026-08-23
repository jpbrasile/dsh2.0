# -*- coding: utf-8 -*-
"""Fumee d une ROUTE : un run dsh headless, enregistreur -> OpenRouter, modele epingle.

    python fumee_route.py [modele] [provider]     (defaut : qwen/qwen3.8-27b, openrouter-banc)

Preuve attendue dans _fumee/wire.jsonl : chaque appel `servi` par le modele
demande, avec usage et ms, et le fichier PONG.txt ecrit. Un HTTP 200 ne prouve
rien : c est `servi` qui nomme qui a repondu. Tout est isole (DSH_HOME et
espace de travail sous _fumee/, gitignore). Mesure du 23/08 : ce test a
attrape un arbre dsh vide (bin.js absent) et un modele sans bloc
`reasoningEfforts` (dsh refuse `off`) avant la premiere campagne."""
import io, json, os, subprocess, sys, time, urllib.request

BENCH = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(BENCH, "_fumee")
MODELE = sys.argv[1] if len(sys.argv) > 1 else "qwen/qwen3.8-27b"
PROVIDER = sys.argv[2] if len(sys.argv) > 2 else "openrouter-banc"
PORT = int(os.environ.get("FUMEE_PORT", "8050"))
UP_HOST = os.environ.get("FUMEE_AMONT", "openrouter.ai")
sys.path.insert(0, BENCH)
os.chdir(BENCH)
import bench  # noqa: E402  (dsh_effort.set_default, _reecrire_baseurl, DSH, tuer_arbre)

acc = os.path.join(S, "home")
ws = os.path.join(S, "ws")
for d in (acc, ws):
    os.makedirs(d, exist_ok=True)
wire = os.path.join(S, "wire.jsonl")
if os.path.exists(wire):
    os.remove(wire)
if os.path.exists(os.path.join(ws, "PONG.txt")):
    os.remove(os.path.join(ws, "PONG.txt"))

# Accueil dsh isole : le settings.yaml de l utilisateur, baseURL du provider
# rediriee vers l enregistreur, modele epingle, raisonnement `off`.
src = os.path.join(os.path.expanduser("~"), ".dsh", "settings.yaml")
s = io.open(src, encoding="utf-8").read()
cible = os.path.join(acc, "settings.yaml")
bench.ecrire_texte(cible, bench._reecrire_baseurl(s, PROVIDER, "http://127.0.0.1:%d/api/v1" % PORT))
bench.set_default(PROVIDER, MODELE, "off", cible)

# Enregistreur -> amont en TLS.
env = dict(os.environ, PROXY_PORT=str(PORT), PROXY_LOG=wire, PROXY_SLOT="0",
           UP_HOST=UP_HOST, UP_PORT="443", UP_TLS="1")
px = subprocess.Popen(["node", os.path.join(BENCH, "proxy.mjs")], cwd=BENCH, env=env,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/api/v1/models" % PORT, timeout=2).read()
        break
    except Exception:
        time.sleep(0.5)
else:
    px.kill()
    raise SystemExit("enregistreur muet sur %d (port occupe ?)" % PORT)

# La tache : ecrire un fichier, puis s arreter. Pas de Julia, pas de juge.
tache = ("Create a file named PONG.txt in the current directory containing exactly the "
         "single word PONG. Then stop. Do not ask questions.")
env2 = dict(os.environ, DSH_HOME=acc)
t0 = time.time()
try:
    p = subprocess.run([bench.DSH, "--profile", "headless", tache], cwd=ws, env=env2,
                       capture_output=True, text=True, timeout=300)
    rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
except subprocess.TimeoutExpired as e:
    rc, out = "timeout", str(e)
dt = time.time() - t0
bench.tuer_arbre(px)
io.open(os.path.join(S, "dsh_out.txt"), "w", encoding="utf-8").write(out)

print("dsh rc=%s  duree=%.1fs" % (rc, dt))
pong = os.path.join(ws, "PONG.txt")
print("PONG.txt :", io.open(pong, encoding="utf-8").read().strip() if os.path.exists(pong) else "ABSENT")
calls = [json.loads(l) for l in io.open(wire, encoding="utf-8")] if os.path.exists(wire) else []
calls = [c for c in calls if c.get("kind") == "call"]
print("appels enregistres : %d" % len(calls))
for c in calls:
    u = c.get("usage") or {}
    print("  servi=%-26s status=%s ms=%-6s in=%s out=%s  n_messages=%s n_tools=%s"
          % (c.get("servi"), c.get("status"), c.get("ms"), u.get("prompt_tokens"),
             u.get("completion_tokens"), (c.get("sent") or {}).get("n_messages"),
             (c.get("sent") or {}).get("n_tools")))
ok = bool(calls) and all(c.get("servi") == MODELE for c in calls) and os.path.exists(pong)
if not ok and rc not in (0, None):
    for l in out.splitlines():
        if l.strip() and "warn" not in l.lower():
            print("  dsh :", l.strip()[:160])
            break
print("VERDICT :", ("OK -- chaque appel servi par %s, fichier ecrit" % MODELE) if ok else "ECHEC (voir _fumee/dsh_out.txt)")
raise SystemExit(0 if ok else 1)
