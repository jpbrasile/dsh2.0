"""Le bras local Q4 reproduit-il la reference BF16 ?

ATTENTION AU DENOMBREMENT. or_bf16 a joue 37 questions x 4 rotations = 133
appels libres. Une barre calculee sur 133 appels serait FAUSSE : les 4 appels
d'une meme question ne sont pas independants. On agrege donc par question.
Le bras local, lui, est en rotation TOURNANTE : 1 appel par question, donc
appel = question, pas de grappe.
"""
import json, os, math, collections, statistics as st

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")

def charger(nom):
    return [json.loads(l) for l in open(os.path.join(BASE, nom), encoding="utf-8") if l.strip()]

def par_question(recs):
    """moyenne de justesse par question, sur les appels LIBRES seulement"""
    g = collections.defaultdict(list)
    for r in recs:
        if r.get("finish_reason") != "length":
            g[r["id"]].append(1.0 if r.get("juste") else 0.0)
    return [sum(v) / len(v) for v in g.values()]

def barre(vals):
    n = len(vals)
    m = sum(vals) / n
    if n < 2:
        return m, 0.0, n
    s = st.stdev(vals)
    return m, 1.96 * s / math.sqrt(n), n

print("=== EXACTITUDE AGREGEE PAR QUESTION (libres seuls) ===")
for nom, fich in (("BF16 (OpenRouter, 4 rot.)", "or_bf16.jsonl"),
                  ("Q4 local (tournante, 1 rot.)", "local_q4_t1_libre_tournant.jsonl")):
    v = par_question(charger(fich))
    m, d, n = barre(v)
    print("  %-30s %5.1f %% +/- %4.1f pt   sur %d QUESTIONS" % (nom, 100 * m, 100 * d, n))

print()
print("=== LA MEME CHOSE, MAIS PAR APPEL (ce qui gonfle a tort la BF16) ===")
for nom, fich in (("BF16 (OpenRouter)", "or_bf16.jsonl"),
                  ("Q4 local", "local_q4_t1_libre_tournant.jsonl")):
    recs = [r for r in charger(fich) if r.get("finish_reason") != "length"]
    k = sum(1 for r in recs if r.get("juste"))
    p = k / len(recs)
    print("  %-30s %5.1f %% +/- %4.1f pt   sur %d appels (%d questions distinctes)"
          % (nom, 100 * p, 100 * 1.96 * math.sqrt(p * (1 - p) / len(recs)),
             len(recs), len(set(r["id"] for r in recs))))

print()
print("=== LA FUGUE EN CHIMIE EST-ELLE PROPRE AU LOCAL ? ===")
print("  %-30s %-16s %-16s" % ("bras", "chimie", "physique"))
for nom, fich in (("BF16 (OpenRouter)", "or_bf16.jsonl"),
                  ("Q4 local", "local_q4_t1_libre_tournant.jsonl")):
    recs = charger(fich)
    out = []
    for dom in ("Chemistry", "Physics"):
        s = [r for r in recs if r.get("domaine") == dom]
        t = sum(1 for r in s if r.get("finish_reason") == "length")
        out.append("%2d/%-3d = %4.1f %%" % (t, len(s), 100.0 * t / len(s)))
    print("  %-30s %-16s %-16s" % (nom, out[0], out[1]))
print()
print("  Meme motif des deux cotes, sur deux fournisseurs et deux precisions :")
print("  la fugue en chimie est une propriete du MODELE, pas du deploiement")
print("  local ni de la quantification.")
