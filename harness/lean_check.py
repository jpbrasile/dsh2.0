# -*- coding: utf-8 -*-
"""Controle de derive du preset Lean.

    python harness/lean_check.py [--fil <wire.jsonl>] [--extra-patch <yml>]

1. Compose le profil headless deux fois (`--dump-config` sans puis avec
   harness/lean.patch.yml) et exige que la DIFFERENCE soit exactement ce que la
   couche declare : les ids qu elle desactive passent a `disabled: true`, les ids
   qu elle insere apparaissent, et RIEN d autre ne bouge. Une rangee qui change
   ailleurs -- ou une rangee declaree qui n existe plus apres un bump de dsh --
   est nommee.
2. Avec --fil : le catalogue d outils lu sur le fil (fumee_route.py) doit etre
   celui annonce par la ligne `# tools:` de la couche, et aucun outil de
   `# tools-absent:` ne doit y figurer. Le dump prouve la composition ; seul le
   fil prouve ce que le modele recoit.

--extra-patch <yml> est le bras known-BAD : une couche supplementaire, non
declaree, doit faire sortir ECHEC (mesure 23/08 : `tool-todo` desactive par une
couche parasite -> "derive non declaree : tool-todo").
"""
import argparse, io, json, os, re, subprocess, sys

ICI = os.path.dirname(os.path.abspath(__file__))
DEPOT = os.path.dirname(ICI)
COUCHE = os.path.join(ICI, "lean.patch.yml")
DSH = os.environ.get("DSH_BIN", os.path.join(os.path.expanduser("~"), ".dsh", "runtime",
                     "dsh-0.1.1-rc.2", "node_modules", ".bin", "dsh.cmd"))

ap = argparse.ArgumentParser()
ap.add_argument("--fil", default=None)
ap.add_argument("--extra-patch", default=None)
A = ap.parse_args()

import yaml  # noqa: E402


class Tolerant(yaml.SafeLoader):
    pass


def _tag_inconnu(loader, suffix, node):
    # `!!js <expr>` : on garde l expression comme texte, on ne l evalue pas.
    if isinstance(node, yaml.ScalarNode):
        return "!!js " + str(node.value)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


Tolerant.add_multi_constructor("tag:yaml.org,2002:", _tag_inconnu)
Tolerant.add_multi_constructor("!", _tag_inconnu)


def dump(patchs):
    args = [DSH, "--profile", "headless"]
    for p in patchs:
        args += ["--patch", os.path.abspath(p)]
    args.append("--dump-config")
    r = subprocess.run(args, cwd=DEPOT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise SystemExit("dump-config rc=%s :\n%s" % (r.returncode, (r.stderr or r.stdout)[-1500:]))
    rows = yaml.load(r.stdout, Loader=Tolerant) or []
    return {r_["id"]: r_ for r_ in rows if isinstance(r_, dict) and "id" in r_}


def declare(chemin):
    """Ce que la couche declare : ids desactives, ids inseres, outils annonces."""
    texte = io.open(chemin, encoding="utf-8").read()
    rows = yaml.load(texte, Loader=Tolerant) or []
    desact, inser = [], []
    for r in rows:
        if "insert" in r:
            inser += [x["id"] for x in r["insert"]]
        elif r.get("disabled") is True:
            desact.append(r["id"])
    m1 = re.search(r"(?m)^# tools:\s*(.*)$", texte)
    m2 = re.search(r"(?m)^# tools-absent:\s*(.*)$", texte)
    return desact, inser, (m1.group(1).split() if m1 else []), (m2.group(1).split() if m2 else [])


desact, inser, outils, absents = declare(COUCHE)
base = dump([])
lean = dump([COUCHE] + ([A.extra_patch] if A.extra_patch else []))
ecarts = []

for i in desact:
    if i not in base:
        ecarts.append("la couche desactive `%s`, qui n existe plus dans l arbre de base" % i)
    elif lean.get(i, {}).get("disabled") is not True:
        ecarts.append("`%s` devrait etre disabled: true dans l arbre Lean" % i)
for i in inser:
    if i in base:
        ecarts.append("`%s` est insere par la couche mais existe deja dans la base" % i)
    if i not in lean:
        ecarts.append("`%s` insere par la couche mais absent de l arbre Lean" % i)
touches = set(desact) | set(inser)
for i in sorted(set(base) | set(lean)):
    if i in touches:
        continue
    if i not in base:
        ecarts.append("derive non declaree : `%s` apparait dans l arbre Lean" % i)
    elif i not in lean:
        ecarts.append("derive non declaree : `%s` disparait de l arbre Lean" % i)
    elif json.dumps(base[i], sort_keys=True, default=str) != json.dumps(lean[i], sort_keys=True, default=str):
        ecarts.append("derive non declaree : `%s` change hors de la couche" % i)

print("arbre de base : %d rangees ; arbre Lean : %d rangees ; couche : %d desactivees, %d inserees"
      % (len(base), len(lean), len(desact), len(inser)))
actifs_base = sum(1 for r in base.values() if r.get("disabled") is not True)
actifs_lean = sum(1 for r in lean.values() if r.get("disabled") is not True)
print("rangees actives : base %d -> Lean %d" % (actifs_base, actifs_lean))

if A.fil:
    calls = [json.loads(l) for l in io.open(A.fil, encoding="utf-8")]
    outilles = [c for c in calls if c.get("kind") == "call" and (c.get("sent") or {}).get("n_tools")]
    if not outilles:
        ecarts.append("fil sans appel outille : rien a comparer")
    else:
        vus = set((outilles[0]["sent"].get("tools") or []))
        if set(outils) != vus:
            ecarts.append("catalogue du fil != `# tools:` de la couche : +%s -%s"
                          % (",".join(sorted(vus - set(outils))) or "0", ",".join(sorted(set(outils) - vus)) or "0"))
        fuite = vus & set(absents)
        if fuite:
            ecarts.append("outils annonces absents mais offerts sur le fil : %s" % ",".join(sorted(fuite)))
        print("fil : %d outils offerts, %d appels outilles" % (len(vus), len(outilles)))

for e in ecarts:
    print("  ECART :", e)
print("VERDICT :", "OK -- la couche Lean est exactement ce qu elle declare" if not ecarts else "ECHEC")
sys.exit(1 if ecarts else 0)
