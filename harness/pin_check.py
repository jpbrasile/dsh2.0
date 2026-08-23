# -*- coding: utf-8 -*-
"""Controle d epinglage de dsh : l arbre qui TOURNE est-il celui que le depot versionne ?

    python harness/pin_check.py            -> 0 si tout concorde, 1 sinon (chaque ecart nomme)

Ce qui est compare, dans l ordre :
  1. harness/runtime/package-lock.json  ==  ~/.dsh/runtime/dsh-<v>/package-lock.json  (octet pour octet)
  2. l integrite sha512 de @deepseek-ai/dsh dans ce lock  ==  celle de harness/PIN.md
  3. la version installee (node_modules/@deepseek-ai/dsh/package.json)  ==  <v>
  4. chaque paquet @deepseek-ai/dsh* installe est a <v> (aucun greffon flottant)
  5. lib/bin.js present (un arbre vide a deja ete trouve le 23/08)

Un lock identique dit que `npm ci` rebatirait CET arbre ; il ne dit pas que
node_modules n a pas ete modifie apres coup -- c est le point 4 qui regarde
les versions reellement installees, paquet par paquet.
"""
import io, json, os, re, sys

ICI = os.path.dirname(os.path.abspath(__file__))
DEPOT = os.path.dirname(ICI)
VERSION = json.load(io.open(os.path.join(ICI, "runtime", "package.json"), encoding="utf-8"))["dependencies"]["@deepseek-ai/dsh"]
RUNTIME = os.path.join(os.path.expanduser("~"), ".dsh", "runtime", "dsh-" + VERSION)
erreurs = []

def lire(p):
    return io.open(p, "rb").read()

# 1. lock identique
a = os.path.join(ICI, "runtime", "package-lock.json")
b = os.path.join(RUNTIME, "package-lock.json")
if not os.path.exists(b):
    erreurs.append("aucun arbre epingle : %s absent (.\\scripts\\dsh.ps1 -InstallRuntime)" % b)
elif lire(a) != lire(b):
    erreurs.append("package-lock.json differe entre le depot et %s" % RUNTIME)

# 2. integrite du paquet principal == PIN.md
lock = json.load(io.open(a, encoding="utf-8"))
integ = lock["packages"]["node_modules/@deepseek-ai/dsh"]["integrity"]
pin = io.open(os.path.join(ICI, "PIN.md"), encoding="utf-8").read()
if integ not in pin:
    erreurs.append("l integrite du lock (%s...) n est pas celle de harness/PIN.md" % integ[:24])
if VERSION not in pin:
    erreurs.append("la version %s n apparait pas dans harness/PIN.md" % VERSION)

# 3-4. versions reellement installees
scope = os.path.join(RUNTIME, "node_modules", "@deepseek-ai")
if os.path.isdir(scope):
    flottants = []
    for nom in sorted(os.listdir(scope)):
        if nom != "dsh" and not nom.startswith("dsh-"):
            continue
        pj = os.path.join(scope, nom, "package.json")
        if not os.path.exists(pj):
            flottants.append("%s (package.json absent)" % nom); continue
        v = json.load(io.open(pj, encoding="utf-8")).get("version")
        if v != VERSION:
            flottants.append("%s@%s" % (nom, v))
    if flottants:
        erreurs.append("paquets du scope hors version %s : %s" % (VERSION, ", ".join(flottants)))
    # 5. binaire
    if not os.path.exists(os.path.join(scope, "dsh", "lib", "bin.js")):
        erreurs.append("lib/bin.js absent : arbre vide (relancer -InstallRuntime)")
else:
    erreurs.append("scope @deepseek-ai absent sous %s" % RUNTIME)

n = len([x for x in os.listdir(scope) if x == "dsh" or x.startswith("dsh-")]) if os.path.isdir(scope) else 0
print("dsh %s : %d paquets dsh* installes sous %s" % (VERSION, n, RUNTIME))
for e in erreurs:
    print("  ECART :", e)
print("VERDICT :", "OK -- l arbre qui tourne est celui du depot" if not erreurs else "ECHEC")
sys.exit(1 if erreurs else 0)
