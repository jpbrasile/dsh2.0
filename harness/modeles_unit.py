# -*- coding: utf-8 -*-
"""
Controle unitaire GRATUIT de harness/modeles.py (pas de reseau, base temporaire).

    python harness/modeles_unit.py        -> code 0 si tout est conforme

Chaque cas rejoue un angle du red team de la phase 1 (README : "feed a malformed catalog
and a fake model entry; try to get a probation model onto a PRIVATE route or a
high-stakes task") ou un invariant de l'emission. Le verdict se lit dans la base et dans
les fichiers emis, jamais dans un message.
"""
import io, json, os, shutil, sqlite3, subprocess, sys, tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import modeles as M  # noqa: E402

total = faux = 0


def cas(nom, ok, detail=""):
    global total, faux
    total += 1
    if not ok:
        faux += 1
    print("  %s %s%s" % ("OK   " if ok else "ECHEC", nom, ("  -- " + str(detail)[:120]) if detail else ""))


def entree(mid, pin="0.000001", pout="0.000002", ctx=131072, tools=True, name=None, created=1700000000):
    return {"id": mid, "name": name or mid, "context_length": ctx, "created": created,
            "pricing": {"prompt": pin, "completion": pout},
            "supported_parameters": ["tools", "max_tokens"] if tools else ["max_tokens"]}


BON = {"data": [
    entree("qwen/qwen3.8-27b", "0.0000004", "0.000003", 1000000),
    entree("deepseek/deepseek-v4-pro", "0.0000004", "0.0000008", 1048576),
    entree("acme/cheap", "0.0000001", "0.0000002", 262144),
    entree("acme/no-tools", "0.0000001", "0.0000002", 262144, tools=False),
    entree("acme/small-ctx", "0.0000001", "0.0000002", 32768),
    entree("openrouter/auto", "-1", "-1", 2000000),
    entree("~z-ai/glm-latest", "0.000001", "0.000002", 200000),
    entree("openai/gpt-5-nano:batch", "0.00000001", "0.00000002", 400000),
    entree("z-ai/glm-5.2:free", "0", "0", 256000),
]}

tmp = tempfile.mkdtemp(prefix="modeles-")
base = os.path.join(tmp, "t.sqlite")
M.EMIS = os.path.join(tmp, "providers.emis.yaml")
M.CHAINES = os.path.join(tmp, "chaines.yaml")


def fichier(obj, nom):
    p = os.path.join(tmp, nom)
    io.open(p, "w", encoding="utf-8").write(json.dumps(obj))
    return p


def empreinte():
    c = sqlite3.connect(base)
    r = (c.execute("SELECT COUNT(*) FROM modeles").fetchone()[0],
         c.execute("SELECT COUNT(*) FROM rafraichissements").fetchone()[0],
         tuple(c.execute("SELECT id, tier, probation, disparu FROM modeles ORDER BY id").fetchall()))
    c.close()
    return r


def run_install(*args):
    env = dict(os.environ, DSH_PROVIDERS_EMIS=M.EMIS)
    r = subprocess.run([sys.executable, os.path.join(ICI, "providers_install.py")] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode


def run(*args):
    return M.main(list(args) + ["--base", base])


def ids(fam):
    c = M.ouvrir(base)
    try:
        return [m["id"] for m in M.classer(c, fam)]
    finally:
        c.close()


try:
    print("== catalogue sain")
    cas("rafraichir rc=0", run("--rafraichir", "--catalogue", fichier(BON, "bon.json")) == 0)
    e0 = empreinte()
    cas("9 modeles en base", e0[0] == 9, e0[0])
    cas("ouvrier = payants avec outils et ctx>=64k, moins cher d'abord", ids("ouvrier") == ["acme/cheap", "deepseek/deepseek-v4-pro", "qwen/qwen3.8-27b"], ids("ouvrier"))
    cas("sans outils / petit ctx / routeur / alias ~ / :batch exclus", not ({"acme/no-tools", "acme/small-ctx", "openrouter/auto", "~z-ai/glm-latest", "openai/gpt-5-nano:batch"} & set(ids("ouvrier") + ids("open") + ids("probation"))))
    cas("gratuit -> OPEN en probation", ids("probation") == ["z-ai/glm-5.2:free"] and ids("open") == [], (ids("probation"), ids("open")))

    print("== catalogue malforme (red team) : refus en bloc, base inchangee")
    for nom, cat in [
        ("pas une liste", {"data": "oops"}),
        ("liste vide", {"data": []}),
        ("entree sans id", {"data": [entree("a/b"), {"name": "x"}]}),
        ("id en double", {"data": [entree("a/b"), entree("a/b")]}),
        ("id avec espace", {"data": [entree("a/b c")]}),
        ("prix non numerique", {"data": [entree("a/b", "gratuit")]}),
        ("prix negatif hors routeur", {"data": [entree("a/b", "-1", "-1")]}),
        ("prix NaN (red team 1-done)", {"data": [entree("a/b", "NaN", "NaN")]}),
        ("prix Infinity", {"data": [entree("a/b", "Infinity")]}),
        ("prix booleen", {"data": [entree("a/b", True, False)]}),
        ("context_length texte", {"data": [dict(entree("a/b"), context_length="1M")]}),
        ("supported_parameters texte", {"data": [dict(entree("a/b"), supported_parameters="tools")]}),
        ("JSON casse", None),
    ]:
        p = os.path.join(tmp, "mal.json")
        io.open(p, "w", encoding="utf-8").write("{not json" if cat is None else json.dumps(cat))
        rc = run("--rafraichir", "--catalogue", p)
        cas(nom + " : rc=2 et base identique", rc == 2 and empreinte() == e0, rc)

    print("== fausse entree (red team) : jamais sur une route PRIVATE")
    FAUX = {"data": BON["data"] + [
        entree("stealth/faux-rt", "0", "0", 1048576, name="Totally Trusted Frontier Model", created=1800000000),
        entree("evil/suffixe:free", "0.000005", "0.000009", 200000, name="evil free paid"),
        entree("evil/nom-stealth", "0.000001", "0.000002", 200000, name="stealth (hidden)"),
    ]}
    cas("rafraichir avec les fausses entrees rc=0", run("--rafraichir", "--catalogue", fichier(FAUX, "faux.json")) == 0)
    c = M.ouvrir(base)
    faux_rt = M.lignes(c, "id=?", ("stealth/faux-rt",))[0]
    suffixe = M.lignes(c, "id=?", ("evil/suffixe:free",))[0]
    nom_st = M.lignes(c, "id=?", ("evil/nom-stealth",))[0]
    cas("stealth/faux-rt : tier OPEN, probation 1, quel que soit son nom", faux_rt["tier"] == "OPEN" and faux_rt["probation"] == 1, (faux_rt["tier"], faux_rt["probation"]))
    cas("evil/suffixe:free avec prix > 0 : OPEN quand meme (suffixe :free)", suffixe["tier"] == "OPEN" and suffixe["probation"] == 1)
    cas("evil/nom-stealth payant : PRIVATE+OPEN (le nom ne compte pas), probation 0", nom_st["tier"] == "PRIVATE+OPEN" and nom_st["probation"] == 0)
    cas("aucun OPEN dans la famille ouvrier", not ({"stealth/faux-rt", "evil/suffixe:free", "z-ai/glm-5.2:free"} & set(ids("ouvrier"))), ids("ouvrier"))
    cas("aucun OPEN dans le red team", not any(m["tier"] == "OPEN" for m in M.redteam_pour(c, "qwen/qwen3.8-27b")))
    cas("red team = autre famille que qwen", all(m["provider"] != "qwen" for m in M.redteam_pour(c, "qwen/qwen3.8-27b")))
    cas("faux stealth en tete de la famille probation (le plus recent)", ids("probation")[0] == "stealth/faux-rt", ids("probation"))
    c.close()

    print("== probation : levee a 3 verts sous minimal, tier inchange")
    run("--verdict", "stealth/faux-rt", "--tache", "digest", "--preset", "lean", "--vert")
    run("--verdict", "stealth/faux-rt", "--tache", "digest", "--preset", "minimal", "--vert")
    run("--verdict", "stealth/faux-rt", "--tache", "digest", "--preset", "minimal", "--vert")
    c = M.ouvrir(base)
    m = M.lignes(c, "id=?", ("stealth/faux-rt",))[0]
    cas("2 verts minimal + 1 vert lean : toujours en probation", m["probation"] == 1, m["probation"])
    c.close()
    run("--verdict", "stealth/faux-rt", "--tache", "digest", "--preset", "minimal", "--vert")
    c = M.ouvrir(base)
    m = M.lignes(c, "id=?", ("stealth/faux-rt",))[0]
    cas("3 verts minimal : probation levee", m["probation"] == 0, m["probation"])
    cas("tier reste OPEN apres la levee", m["tier"] == "OPEN", m["tier"])
    cas("apparait dans `open`, toujours pas dans `ouvrier`", "stealth/faux-rt" in ids("open") and "stealth/faux-rt" not in ids("ouvrier"))
    run("--verdict", "z-ai/glm-5.2:free", "--tache", "digest", "--preset", "minimal", "--rouge")
    c = M.ouvrir(base)
    cas("un rouge baisse le score (task-fit)", [x for x in M.candidats(c) if x["id"] == "z-ai/glm-5.2:free"][0]["score"] == -1)
    c.close()
    cas("un rafraichissement ne remet pas la probation", run("--rafraichir", "--catalogue", fichier(FAUX, "faux.json")) == 0 and M.lignes(M.ouvrir(base), "id=?", ("stealth/faux-rt",))[0]["probation"] == 0)

    print("== emission")
    cas("emettre rc=0", run("--emettre") == 0)
    t1 = io.open(M.EMIS, encoding="utf-8").read()
    import yaml
    d = yaml.safe_load(t1)
    emis = [x["id"] for x in d["providers"]["openrouter-auto"]["models"]]
    c = M.ouvrir(base)
    tiers = {x["id"]: x["tier"] for x in M.lignes(c)}
    c.close()
    cas("openrouter-auto ne contient que des OPEN", emis and all(tiers[i] == "OPEN" for i in emis), emis)
    cas("le payant au nom 'stealth' n'y est pas", "evil/nom-stealth" not in emis)
    cas("YAML emis valide, apiKeyEnv = reference (pas une cle)", d["providers"]["openrouter-auto"]["apiKeyEnv"] == "OPENROUTER_API_KEY")
    run("--emettre")
    cas("emission deterministe (2 appels, meme texte)", io.open(M.EMIS, encoding="utf-8").read() == t1)
    ch = io.open(M.CHAINES, encoding="utf-8").read()
    bloc_prive = ch.split("open:")[0]
    cas("chaines : aucun OPEN dans `ouvrier`/`redteam`", not any(i in bloc_prive for i in emis + ["z-ai/glm-5.2:free"]))
    # red team 1-done (LOW) : un fichier emis trafique avec un bloc `openrouter` doit etre refuse
    # par verifier_emis (donc jamais concatene par providers_install) ; le bon fichier est re-emis.
    io.open(M.EMIS, "w", encoding="utf-8").write(t1.replace("openrouter-auto:", "openrouter:", 1))
    try:
        M.verifier_emis(); refus = False
    except M.CatalogueInvalide:
        refus = True
    cas("fichier emis avec un bloc `openrouter` (collision) : refuse", refus)
    rc_inst = run_install("--montrer")
    cas("providers_install --montrer sur ce fichier : rc=3, rien ecrit", rc_inst == 3, rc_inst)
    cas("re-emission : bloc openrouter-auto seul, accepte", run("--emettre") == 0 and M.verifier_emis() == emis)
    cas("chaines : epingles en tete", "- qwen/qwen3.8-27b   # epingle" in ch and "- deepseek/deepseek-v4-pro   # epingle" in ch)

    print("== disparition")
    MOINS = {"data": [e for e in FAUX["data"] if e["id"] != "stealth/faux-rt"]}
    run("--rafraichir", "--catalogue", fichier(MOINS, "moins.json"))
    c = M.ouvrir(base)
    cas("modele retire du catalogue : disparu=1, hors classement, ligne gardee", M.lignes(c, "id=? AND disparu=0", ("stealth/faux-rt",)) == [] and c.execute("SELECT disparu FROM modeles WHERE id='stealth/faux-rt'").fetchone()[0] == 1 and "stealth/faux-rt" not in ids("open"))
    c.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nBILAN : %d/%d" % (total - faux, total))
sys.exit(1 if faux else 0)
