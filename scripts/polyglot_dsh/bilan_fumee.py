# Bilan de la fumee « cas durs » : dsh contre pi, exercice par exercice.
#
# TROIS ETATS, PAS DEUX. Un exercice tue au mur du --delai-tour est une
# NON-MESURE, pas un echec : l'agent n'a jamais rendu sa copie. Les confondre
# gonfle le taux d'echec du cote le plus lent et cache la cause reelle -- la
# sur-deliberation. go/beer-song, 26/08 : 1800,3 s, sortie agent vide.
#
# Le taux de reussite est donc rendu DEUX fois :
#   - sur les exercices MESURES des deux cotes (le seul chiffre comparable) ;
#   - sur tous les exercices tentes, non-mesures comptees comme echecs (la
#     lecture pessimiste, celle qui compte pour un usage reel : un agent qui
#     ne rend jamais sa copie ne resout pas l'exercice).
# Publier les deux evite de choisir apres coup celle qui arrange.

import glob
import io
import json
import os

BASE = r"C:\Users\test\tools\aider-bench\aider\tmp.benchmarks"
RUNS = {"dsh": "fumee-durs-dsh", "pi": "fumee-durs-pi"}


def charger(run):
    d = {}
    for motif in (".dsh.results.json", ".pi.results.json"):
        for f in glob.glob(os.path.join(BASE, run, "*", "exercises",
                                        "practice", "*", motif)):
            r = json.load(io.open(f, encoding="utf-8"))
            t = (r.get("turns") or [{}])[0]
            ex = os.path.basename(os.path.dirname(f))
            lang = f.replace("\\", "/").split("/")[-5]
            d["%s/%s" % (lang, ex)] = {
                "coupe": bool(t.get("coupe")),
                "ok": bool(t.get("ok")),
                "s": r.get("duration", 0.0),
            }
    return d


A = {k: charger(v) for k, v in RUNS.items()}
tous = sorted(set().union(*[set(v) for v in A.values()])) if any(A.values()) else []

if not tous:
    raise SystemExit("aucun resultat trouve sous %s" % BASE)


def etat(r):
    if r is None:
        return "(pas encore)"
    if r["coupe"]:
        return "NON-MESURE"
    return "PASS" if r["ok"] else "FAIL"


print("%-26s  %-14s %9s   %-14s %9s" % ("exercice", "dsh", "s", "pi", "s"))
print("-" * 78)
for ex in tous:
    a, b = A["dsh"].get(ex), A["pi"].get(ex)
    print("%-26s  %-14s %9s   %-14s %9s"
          % (ex, etat(a), ("%.1f" % a["s"]) if a else "-",
             etat(b), ("%.1f" % b["s"]) if b else "-"))
print()

for nom, d in A.items():
    fait = [v for v in d.values()]
    if not fait:
        print("%-4s : rien encore" % nom)
        continue
    mes = [v for v in fait if not v["coupe"]]
    ok = sum(1 for v in mes if v["ok"])
    coupes = len(fait) - len(mes)
    okt = sum(1 for v in fait if v["ok"] and not v["coupe"])
    print("%-4s : %d tentes, %d mesures, %d non-mesures (mur du delai)"
          % (nom, len(fait), len(mes), coupes))
    print("       sur les MESURES         : %d/%d = %.0f %%"
          % (ok, len(mes), 100.0 * ok / max(1, len(mes))))
    print("       non-mesures = echecs    : %d/%d = %.0f %%"
          % (okt, len(fait), 100.0 * okt / max(1, len(fait))))
    tot = sum(v["s"] for v in fait)
    print("       temps total %.0f s, mediane %.0f s"
          % (tot, sorted(v["s"] for v in fait)[len(fait) // 2]))

communs = [e for e in tous
           if A["dsh"].get(e) and A["pi"].get(e)
           and not A["dsh"][e]["coupe"] and not A["pi"][e]["coupe"]]
print()
if communs:
    da = sum(1 for e in communs if A["dsh"][e]["ok"])
    db = sum(1 for e in communs if A["pi"][e]["ok"])
    print("SUR LES %d EXERCICES MESURES DES DEUX COTES (seul chiffre comparable)"
          % len(communs))
    print("  dsh %d/%d    pi %d/%d" % (da, len(communs), db, len(communs)))
    print("  Avec %d exercices, un ecart de moins de %d exercice(s) ne veut"
          % (len(communs), max(1, len(communs) // 3)))
    print("  rien dire. Cette fumee sert a trouver des pannes, PAS a classer")
    print("  deux agents.")
else:
    print("Aucun exercice mesure des DEUX cotes pour l'instant :")
    print("la comparaison n'est pas encore possible.")
