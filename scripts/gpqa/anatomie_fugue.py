"""A QUOI RESSEMBLE UNE FUGUE ? -- diagnostic AVANT de proposer un remede.

Trois remedes possibles s'excluent, et le choix depend entierement de ce que le
modele fait pendant ses 32 768 jetons :

  boucle degeneree   -> probleme d'ECHANTILLONNAGE (penalite de repetition, DRY)
  pensee longue mais
  productive         -> probleme de PLAFOND (le monter, ou forcer la conclusion)
  </think> jamais
  emis               -> probleme de GABARIT (format du raisonnement)

On mesure donc, sur les tronques : taux de repetition en n-grammes, plus longue
repetition litterale, et presence des marqueurs de pensee.
"""
import json, os, re, collections

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")

def charger(nom):
    return [json.loads(l) for l in open(os.path.join(BASE, nom), encoding="utf-8") if l.strip()]

def repetition(texte, n=12):
    """part des n-grammes de mots qui sont des doublons"""
    mots = texte.split()
    if len(mots) < n * 2:
        return 0.0, 0
    grams = [" ".join(mots[i:i + n]) for i in range(len(mots) - n + 1)]
    c = collections.Counter(grams)
    dupes = sum(v - 1 for v in c.values() if v > 1)
    return dupes / len(grams), max(c.values())

for fich, etiq in (("local_q4_t1_libre_tournant.jsonl", "Q4 local"),
                   ("or_bf16.jsonl", "BF16 OpenRouter")):
    recs = charger(fich)
    tr = [r for r in recs if r.get("finish_reason") == "length"]
    li = [r for r in recs if r.get("finish_reason") != "length"]
    print("=== %s : %d tronques ===" % (etiq, len(tr)))
    if not tr:
        continue
    sans_ouvre = sum(1 for r in tr if "<think>" not in (r.get("reponse") or ""))
    sans_ferme = sum(1 for r in tr if "</think>" not in (r.get("reponse") or ""))
    print("  sans <think>  : %d/%d      sans </think> : %d/%d"
          % (sans_ouvre, len(tr), sans_ferme, len(tr)))
    doms = collections.Counter(r.get("domaine") for r in tr)
    print("  domaines      : %s" % dict(doms))

    reps_t = []
    for r in tr:
        p, mx = repetition(r.get("reponse") or "")
        reps_t.append((p, mx, r.get("domaine"), len(r.get("reponse") or "")))
    reps_t.sort(reverse=True)
    moy = sum(x[0] for x in reps_t) / len(reps_t)
    print("  repetition 12-grammes, MOYENNE sur les tronques : %.1f %%" % (100 * moy))
    print("  les 5 pires :")
    for p, mx, dom, n in reps_t[:5]:
        print("     %-10s repetition %5.1f %%  bloc vu %3d fois  (%d car.)"
              % (dom, 100 * p, mx, n))

    # temoin : les libres du meme bras
    reps_l = [repetition(r.get("reponse") or "")[0] for r in li]
    if reps_l:
        print("  TEMOIN, memes appels mais LIBRES : repetition moyenne %.1f %%"
              % (100 * sum(reps_l) / len(reps_l)))
    print()
"""Suite : la fugue se passe-t-elle DANS la pensee ou APRES ?

La repetition est ecartee (0,2 % chez les tronques contre 0,7 % chez les
libres : ils se repetent MOINS). Reste a savoir ou part le budget.
Le harnais journalise pensee_car et reponse_car separement.
"""
import json, os, statistics as st, collections

BASE = os.path.join(os.environ["USERPROFILE"], "Documents", "dsh2.0", "scripts", "gpqa")
recs = [json.loads(l) for l in
        open(os.path.join(BASE, "local_q4_t1_libre_tournant.jsonl"), encoding="utf-8") if l.strip()]

tr = [r for r in recs if r.get("finish_reason") == "length"]
li = [r for r in recs if r.get("finish_reason") != "length"]

print("=== OU PART LE BUDGET ? (Q4 local) ===")
print("%-26s %8s %10s %10s" % ("", "n", "pensee_car", "reponse_car"))
for nom, s in (("LIBRES", li), ("TRONQUES", tr)):
    p = [r.get("pensee_car") or 0 for r in s]
    q = [r.get("reponse_car") or 0 for r in s]
    print("%-26s %8d %10d %10d   (medianes)" % (nom, len(s), st.median(p), st.median(q)))
print()

print("=== LES BALISES DE PENSEE, LIBRES CONTRE TRONQUES ===")
for nom, s in (("LIBRES", li), ("TRONQUES", tr)):
    o = sum(1 for r in s if "<think>" in (r.get("reponse") or ""))
    f = sum(1 for r in s if "</think>" in (r.get("reponse") or ""))
    print("  %-10s <think> present %2d/%-3d   </think> present %2d/%-3d"
          % (nom, o, len(s), f, len(s)))
print()
print("  Si les LIBRES non plus n'ont pas de balises, c'est que ce serveur rend")
print("  la pensee dans un champ separe : l'absence de balise chez les tronques")
print("  n'est alors PAS un symptome.")
print()

print("=== CHIMIE : COMBIEN AURAIT-IL FALLU ? ===")
ch_li = [r for r in li if r.get("domaine") == "Chemistry"]
j = sorted(r["tokens_sortie"] for r in ch_li)
print("  chimie qui FINIT (n=%d) : mediane %d, p75 %d, p90 %d, max %d jetons"
      % (len(j), st.median(j), j[int(.75 * len(j))], j[int(.90 * len(j))], j[-1]))
print("  chimie qui NE FINIT PAS  : %d appels, tous a 32 768" % len(
    [r for r in tr if r.get("domaine") == "Chemistry"]))
print()
print("  La chimie qui finit tient LARGEMENT sous le plafond. Les tronques ne")
print("  sont donc pas « un peu trop courts » : ils sont d'un autre regime.")
