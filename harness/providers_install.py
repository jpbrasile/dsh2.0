# -*- coding: utf-8 -*-
"""Pose les blocs provider de harness/providers.yaml dans ~/.dsh/settings.yaml.

    python harness/providers_install.py [--montrer] [--sans-cles]

Ancre en TEXTE, pas parse-and-dump : le fichier vivant porte des commentaires
mesures (slugs courts, `off` booleen, apiKeyEnv...) qu un round-trip YAML
perdrait. Pour chaque provider du depot :
  - present dans le fichier vivant  -> son bloc (de `    <nom>:` a la ligne
    avant le prochain `^ {0,4}\\S`) est REMPLACE ;
  - absent                          -> insere apres le dernier provider.
Sauvegarde d abord (`settings.yaml.bak-<horodatage>-phase0`), puis relecture
YAML du resultat : si elle echoue, la sauvegarde est restauree et on sort en 1.

Cles (sauf --sans-cles) : chaque `apiKeyEnv` reference doit exister dans
~/.dsh/.credentials.yaml (la couche `file` de dsh-credentials-local). Une
reference absente du fichier mais presente dans l env du process y est
COPIEE (jamais affichee) : le fichier devient la source unique. Une reference
absente des deux est nommee -- la route echouera en MISSING_CREDENTIAL.
"""
import argparse, io, os, re, shutil, sys, time

ICI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ICI, "providers.yaml")
EMIS = os.environ.get("DSH_PROVIDERS_EMIS") or os.path.join(ICI, "providers.emis.yaml")  # genere par modeles.py (Phase 1) ; lu s'il existe
HOME = os.path.join(os.path.expanduser("~"), ".dsh")
VIVANT = os.path.join(HOME, "settings.yaml")
CRED = os.path.join(HOME, ".credentials.yaml")

ap = argparse.ArgumentParser()
ap.add_argument("--montrer", action="store_true", help="ne rien ecrire, dire ce qui changerait")
ap.add_argument("--sans-cles", action="store_true")
A = ap.parse_args()

import yaml  # noqa: E402

# 1. blocs du depot, en texte, re-indentes de 2 (providers: a 2 -> llm-pi-ai.providers a 4)
def decouper(texte):
    blocs, nom, cour, ordre = {}, None, [], []
    for l in texte.split("\n"):
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", l)
        if m:
            if nom: blocs[nom] = cour
            nom, cour = m.group(1), [l]
            ordre.append(nom)
        elif nom is not None:
            if l.startswith("  ") or l.strip() == "":
                cour.append(l)
            else:
                blocs[nom] = cour; nom, cour = None, []
    if nom: blocs[nom] = cour
    return blocs, ordre


texte = io.open(SRC, encoding="utf-8").read()
blocs, ordre = decouper(texte)
if os.path.exists(EMIS):
    # le bloc emis est lu a part, memes regles, meme parseur ; un nom deja present dans
    # providers.yaml est REFUSE (red team 1-done : un bloc `openrouter` emis ecraserait la route payante)
    te = io.open(EMIS, encoding="utf-8").read()
    be, oe = decouper(te)
    collision = [n for n in oe if n in blocs]
    if collision:
        print("providers_install : bloc(s) emis en collision avec providers.yaml : %s -- rien ecrit" % ", ".join(collision))
        raise SystemExit(3)
    blocs.update(be); ordre += oe; texte += "\n" + te
for n in blocs:
    while blocs[n] and blocs[n][-1].strip() == "":
        blocs[n].pop()
    blocs[n] = [("  " + l if l.strip() else "") for l in blocs[n]]
refs = sorted(set(re.findall(r"(?m)^\s+apiKeyEnv:\s*(\S+)", texte)))
print("depot : %d providers (%s) ; references de cle : %s" % (len(blocs), ", ".join(ordre), ", ".join(refs)))

# 2. fichier vivant
s = io.open(VIVANT, encoding="utf-8").read()
vl = s.split("\n")
def bornes(nomp):
    deb = None
    for i, l in enumerate(vl):
        if re.match(r"^    " + re.escape(nomp) + r":\s*$", l):
            deb = i; break
    if deb is None:
        return None
    fin = len(vl)
    for j in range(deb + 1, len(vl)):
        if re.match(r"^ {0,4}\S", vl[j]):
            fin = j; break
    return deb, fin

# dernier provider existant : pour l insertion des absents
dernier_fin = None
for i, l in enumerate(vl):
    if re.match(r"^    [A-Za-z0-9_-]+:\s*$", l) and i > 0:
        b = bornes(l.strip()[:-1])
        if b: dernier_fin = max(dernier_fin or 0, b[1])
if dernier_fin is None:
    raise SystemExit("aucun provider a 4 espaces dans %s : refus d inserer a l aveugle" % VIVANT)

actions = []
for n in ordre:
    b = bornes(n)
    actions.append((n, "remplace (lignes %d-%d)" % (b[0] + 1, b[1]) if b else "insere"))
for n, a in actions:
    print("  %-16s %s" % (n, a))
if A.montrer:
    sys.exit(0)

# 3. appliquer, de bas en haut pour garder les indices
sauv = VIVANT + ".bak-%s-phase0" % time.strftime("%Y%m%d-%H%M%S")
shutil.copyfile(VIVANT, sauv)
rempl = [(n, bornes(n)) for n in ordre if bornes(n)]
rempl.sort(key=lambda x: -x[1][0])
for n, (deb, fin) in rempl:
    vl[deb:fin] = blocs[n] + [""]
# re-calculer la fin des providers apres remplacements
dernier_fin = None
for i, l in enumerate(vl):
    if re.match(r"^    [A-Za-z0-9_-]+:\s*$", l):
        fin = len(vl)
        for j in range(i + 1, len(vl)):
            if re.match(r"^ {0,4}\S", vl[j]):
                fin = j; break
        dernier_fin = fin
absents = [n for n in ordre if not any(re.match(r"^    " + re.escape(n) + r":\s*$", l) for l in vl)]
ins = []
for n in absents:
    ins += blocs[n] + [""]
vl[dernier_fin:dernier_fin] = ins
nouveau = "\n".join(vl)
tmp = VIVANT + ".tmp-phase0"
io.open(tmp, "w", encoding="utf-8", newline="\n").write(nouveau)
try:
    d = yaml.safe_load(io.open(tmp, encoding="utf-8").read())
    provs = d["llm-pi-ai"]["providers"]
    for n in ordre:
        assert n in provs and provs[n].get("baseURL"), n
except Exception as e:
    os.remove(tmp)
    print("RELECTURE IMPOSSIBLE (%s) : rien n est ecrit, sauvegarde %s" % (e, sauv))
    sys.exit(1)
os.replace(tmp, VIVANT)
print("ecrit : %s (sauvegarde %s) ; %d providers relus : %s" % (VIVANT, os.path.basename(sauv), len(provs), ", ".join(sorted(provs))))

# 4. cles : le fichier de credentials est la source unique
if A.sans_cles:
    sys.exit(0)
if os.path.exists(CRED):
    c = io.open(CRED, encoding="utf-8").read()
else:
    c = "version: 1\n\nrefs:\n"
presents = set(re.findall(r"(?m)^  ([A-Z0-9_]+):\s*\S", c))
ajout = []
for r in refs:
    if r in presents:
        print("  cle %-20s : dans .credentials.yaml" % r); continue
    v = os.environ.get(r)
    if v:
        ajout.append("  %s: %s" % (r, v))
        print("  cle %-20s : copiee de l env vers .credentials.yaml (longueur %d)" % (r, len(v)))
    else:
        print("  cle %-20s : ABSENTE (fichier et env) -> la route repondra MISSING_CREDENTIAL" % r)
if ajout:
    if not re.search(r"(?m)^refs:\s*$", c):
        raise SystemExit("pas de section `refs:` dans %s : refus d ecrire a l aveugle" % CRED)
    c = re.sub(r"(?m)^refs:\s*$", "refs:\n" + "\n".join(ajout), c, count=1)
    tmp = CRED + ".tmp-phase0"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(c)
    os.replace(tmp, CRED)
