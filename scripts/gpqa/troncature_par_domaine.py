"""La troncature est-elle un phenomene de CHIMIE ? -- 0/42 en physique,
17/49 en chimie. Si oui, le 92,7 % « libre » n'est pas une exactitude du
modele : c'est une exactitude dont on a retire un tiers de la chimie.
"""
import json, os, math, statistics as st, collections

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")
recs = []
with open(os.path.join(BASE, "local_q4_t1_libre_tournant.jsonl"), encoding="utf-8") as f:
    for l in f:
        l = l.strip()
        if l:
            recs.append(json.loads(l))

def bar(k, n):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    return 100 * p, 100 * 1.96 * math.sqrt(p * (1 - p) / n)

print("=== 1. SIGNIFICATIVITE : chimie contre physique ===")
ch = [r for r in recs if r.get("domaine") == "Chemistry"]
ph = [r for r in recs if r.get("domaine") == "Physics"]
tch = sum(1 for r in ch if r.get("finish_reason") == "length")
tph = sum(1 for r in ph if r.get("finish_reason") == "length")
print("  chimie   : %2d/%-3d tronques" % (tch, len(ch)))
print("  physique : %2d/%-3d tronques" % (tph, len(ph)))
# Fisher exact, une seule queue, calcul direct
def C(n, k):
    return math.comb(n, k)
a, b_, c, d = tch, len(ch) - tch, tph, len(ph) - tph
N = a + b_ + c + d
p = 0.0
for x in range(a, min(a + b_, a + c) + 1):
    p += C(a + b_, x) * C(c + d, a + c - x) / C(N, a + c)
print("  Fisher exact (unilateral) : p = %.3g" % p)
print()

print("=== 2. LONGUEUR DE PENSEE PAR DOMAINE (appels LIBRES seuls) ===")
for dom in ("Chemistry", "Physics", "Biology"):
    sous = [r for r in recs
            if r.get("domaine") == dom and r.get("finish_reason") != "length"]
    if not sous:
        continue
    j = [r["tokens_sortie"] for r in sous]
    print("  %-10s n=%2d  jetons med %6d  moy %6d  max %6d"
          % (dom, len(sous), st.median(j), sum(j) / len(j), max(j)))
print()

print("=== 3. EXACTITUDE PAR DOMAINE, SUR LES LIBRES ===")
print("  (rappel : les tronques sont exclus -- et ils sont presque tous en chimie)")
for dom in ("Chemistry", "Physics", "Biology"):
    sous = [r for r in recs
            if r.get("domaine") == dom and r.get("finish_reason") != "length"]
    if not sous:
        continue
    k = sum(1 for r in sous if r.get("juste"))
    v, e = bar(k, len(sous))
    print("  %-10s %2d/%-3d = %5.1f %% +/- %4.1f pt" % (dom, k, len(sous), v, e))
print()

print("=== 4. CE QUE LA SELECTION FAIT AU CHIFFRE GLOBAL ===")
libres = [r for r in recs if r.get("finish_reason") != "length"]
k = sum(1 for r in libres if r.get("juste"))
v, e = bar(k, len(libres))
print("  publie tel quel (libres)        : %5.1f %% +/- %4.1f pt sur %d" % (v, e, len(libres)))
comp = collections.Counter(r.get("domaine") for r in libres)
tot = collections.Counter(r.get("domaine") for r in recs)
print("  composition des LIBRES  : " + ", ".join(
    "%s %d/%d" % (d, comp[d], tot[d]) for d in sorted(tot)))
print()
print("  La chimie perd %d de ses %d questions en route ; la physique n'en perd"
      % (tch, len(ch)))
print("  aucune. Le chiffre « libre » est donc pondere vers la physique par")
print("  construction -- ce n'est pas un echantillon de GPQA Diamond.")
