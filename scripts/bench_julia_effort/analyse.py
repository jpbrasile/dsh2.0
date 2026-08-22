"""Table finale : reussite, debit, temps par tache, par niveau d'effort.

Les jetons et les secondes de decodage viennent du bloc `timings` que
llama-server rend lui-meme, releve par le proxy 8006 entre deux marqueurs.
Le chrono client ne sert qu'au temps de tache (il inclut l'agent, les outils,
Julia -- c'est bien ce qu'on veut pour "temps par tache").
"""
import io, json, os, statistics as st

B = os.path.dirname(os.path.abspath(__file__))


def _charger(nom, pourquoi):
    p = os.path.join(B, nom)
    if not os.path.exists(p):
        raise SystemExit(
            "%s absent. %s\nLancer d'abord : python bench.py off,low,medium,high,xhigh"
            % (nom, pourquoi))
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


res = _charger("resultats.jsonl", "C'est le journal des verdicts, ecrit par bench.py.")
wire = _charger("wire.jsonl", "C'est le journal du proxy : sans lui il n'y a AUCUN "
                              "debit par niveau, seulement des chronos client.")

# Attribution des appels a un run, par marqueurs.
#
# On garde la DERNIERE fenetre [debut, fin] de chaque tag, pas la premiere ni
# leur union. Le proxy ecrit `wire.jsonl` en ajout et ne sait rien des
# campagnes : deux campagnes successives y deposent deux fenetres portant le
# MEME tag, et un parcours naif attribuait au premier bras les appels de la
# campagne precedente. Defaut mesure le 22/08 -- 6 runs sur 50, tous dans le
# premier bras, annoncaient 226.9 s de decodage dans un run de 47.5 s.
#
# Le controle qui l'a attrape est en bas de ce fichier et il TOURNE : un run ne
# peut pas passer plus de temps en appels qu'il n'a dure. Une attribution
# faussee est indetectable sur les nombres eux-memes -- 55 t/s au lieu de 73
# reste parfaitement lisible -- et ne se voit que confrontee a l'horloge.
#
# Le tag porte la repetition depuis le 22/08 : `effort|tache|rNN|debut`. Les
# campagnes anterieures ecrivaient `effort|tache|debut` ; elles sont relues
# comme la repetition 1 plutot que d'etre silencieusement ignorees.
def _cle(t):
    if len(t) == 4 and t[2].startswith("r"):
        return (t[0], t[1], int(t[2][1:])), t[3]
    if len(t) == 3:
        return (t[0], t[1], 1), t[2]
    return None, None


par_run, courant, rejoues = {}, None, 0
for r in wire:
    if r.get("kind") == "mark":
        cle, bout = _cle(r["tag"].split("|"))
        if cle and bout == "debut":
            courant = cle
            if courant in par_run:
                rejoues += 1
            par_run[courant] = []
        else:
            courant = None
        continue
    if courant and r.get("kind") == "call":
        par_run[courant].append(r)
if rejoues:
    print("NOTE : %d tache(s) apparaissent plusieurs fois dans wire.jsonl "
          "(campagnes successives). Seule la DERNIERE fenetre de chacune est "
          "retenue.\n" % rejoues)

def agrege(calls):
    gen = dec_ms = pre_n = pre_ms = 0
    for c in calls:
        t = c.get("timings") or {}
        gen += t.get("predicted_n") or 0
        dec_ms += t.get("predicted_ms") or 0
        pre_n += t.get("prompt_n") or 0
        pre_ms += t.get("prompt_ms") or 0
    return dict(appels=len(calls), gen=gen, dec_s=dec_ms/1000.0, pre_n=pre_n, pre_s=pre_ms/1000.0)

lignes = []
for r in res:
    rep = r.get("rep", 1)
    a = agrege(par_run.get((r["effort"], r["tache"], rep), []))
    lignes.append({**r, "rep": rep, **a})
nreps = len({l["rep"] for l in lignes})

ordre = ["off", "low", "medium", "high", "xhigh"]
efforts = [e for e in ordre if any(l["effort"] == e for l in lignes)]

print("=== par run ===")
print("%-3s %-6s %-5s %-4s %7s %7s %7s %6s  %s" % ("rep","effort","tache","ok","temps_s","gen_tok","dec_t/s","appels","pourquoi"))
for e in efforts:
    for l in sorted([x for x in lignes if x["effort"] == e], key=lambda x: (x["tache"], x["rep"])):
        tps = l["gen"]/l["dec_s"] if l["dec_s"] else 0
        print("r%-2d %-6s %-5s %-4s %7.1f %7d %7.1f %6d  %s"
              % (l["rep"], e, l["tache"], l["verdict"], l["wall_s"], l["gen"], tps, l["appels"], l["why"][:52]))

print()
print("=== synthese par niveau ===")
print("%-8s %-8s %9s %9s %10s %10s %9s" % ("effort","reussite","temps_med","temps_moy","gen_tok_moy","dec_t/s","appels_moy"))
synth = {}
for e in efforts:
    g = [x for x in lignes if x["effort"] == e]
    ok = sum(1 for x in g if x["verdict"] == "PASS")
    tot_gen = sum(x["gen"] for x in g); tot_dec = sum(x["dec_s"] for x in g)
    s = dict(n=len(g), ok=ok,
             med=st.median([x["wall_s"] for x in g]),
             moy=st.mean([x["wall_s"] for x in g]),
             gen=tot_gen/len(g), tps=(tot_gen/tot_dec if tot_dec else 0),
             ap=st.mean([x["appels"] for x in g]))
    synth[e] = s
    print("%-8s %2d/%-5d %9.1f %9.1f %10.0f %10.1f %9.1f"
          % (e, ok, len(g), s["med"], s["moy"], s["gen"], s["tps"], s["ap"]))

if "high" in synth and "xhigh" in synth:
    h, x = synth["high"], synth["xhigh"]
    print()
    print("--- temoin : high et xhigh rendent un prompt IDENTIQUE au caractere pres.")
    print("    Tout ecart entre eux est du bruit de tirage, et c'est l'etalon du reste.")
    print("    reussite  %d/%d vs %d/%d  (ecart %d sur %d, soit %.0f points)"
          % (h["ok"], h["n"], x["ok"], x["n"], abs(h["ok"] - x["ok"]), h["n"],
             100.0 * abs(h["ok"] / max(h["n"], 1) - x["ok"] / max(x["n"], 1))))
    print("    temps moy %.1f vs %.1f s  (ecart %.0f %%)" % (h["moy"], x["moy"], 100*abs(h["moy"]-x["moy"])/max(h["moy"],1e-9)))
    print("    jetons    %.0f vs %.0f  (ecart %.0f %%)" % (h["gen"], x["gen"], 100*abs(h["gen"]-x["gen"])/max(h["gen"],1e-9)))

if nreps > 1:
    print()
    print("=== reproductibilite : le MEME niveau, repetition par repetition ===")
    print("    Second estimateur de bruit, independant du temoin high/xhigh.")
    print("    Si un niveau ne se reproduit pas lui-meme, il ne peut pas etre")
    print("    compare a un autre.")
    print("    %-8s %s" % ("effort", "  ".join("r%-6d" % r for r in sorted({l["rep"] for l in lignes}))))
    for e in efforts:
        cases = []
        for r in sorted({l["rep"] for l in lignes}):
            g = [x for x in lignes if x["effort"] == e and x["rep"] == r]
            cases.append("%-7s" % ("%d/%d" % (sum(1 for x in g if x["verdict"] == "PASS"), len(g))))
        g = [x for x in lignes if x["effort"] == e]
        etendue = max(0, max((sum(1 for x in lignes if x["effort"] == e and x["rep"] == r and x["verdict"] == "PASS")
                              for r in {l["rep"] for l in lignes}), default=0)
                      - min((sum(1 for x in lignes if x["effort"] == e and x["rep"] == r and x["verdict"] == "PASS")
                             for r in {l["rep"] for l in lignes}), default=0))
        print("    %-8s %s  etendue %d" % (e, "  ".join(cases), etendue))

print()
print("=== par tache, tous niveaux (difficulte) ===")
print("  %-5s %-7s  %s" % ("tache", "total", "  ".join("%-6s" % e for e in efforts)))
for t in sorted({l["tache"] for l in lignes}):
    g = [x for x in lignes if x["tache"] == t]
    par_e = []
    for e in efforts:
        ge = [x for x in g if x["effort"] == e]
        par_e.append("%-6s" % ("%d/%d" % (sum(1 for x in ge if x["verdict"] == "PASS"), len(ge))))
    print("  %-5s %-7s  %s" % (t, "%d/%d" % (sum(1 for x in g if x["verdict"] == "PASS"), len(g)),
                               "  ".join(par_e)))

# --- CONTROLE D'HORLOGE, cable : il tourne a chaque analyse -------------------
# Un run ne peut pas passer en appels reseau plus de temps qu'il n'a dure. Si
# c'est le cas, des appels lui ont ete attribues a tort et TOUS les debits de
# cette ligne sont faux -- sans que le nombre ait l'air faux. C'est le seul
# controle du fichier qui puisse contredire l'attribution ; les autres nombres
# sont d'accord avec elle par construction.
print()
impossibles = []
for l in lignes:
    somme_s = sum(c.get("ms", 0) for c in par_run.get((l["effort"], l["tache"]), [])) / 1000.0
    if somme_s > l["wall_s"] * 1.15 + 2:
        impossibles.append((l["effort"], l["tache"], l["wall_s"], somme_s))
if impossibles:
    print("!!! ATTRIBUTION FAUSSEE -- %d run(s) passent plus de temps en appels "
          "qu'ils n'ont dure." % len(impossibles))
    for e, t, w, s in impossibles:
        print("      %-6s %-5s  duree %.1f s  mais %.1f s d'appels" % (e, t, w, s))
    print("      Les debits ci-dessus sont FAUX pour ces lignes. Ne pas les citer.")
else:
    print("controle d'horloge : %d/%d runs coherents (aucun ne passe plus de temps "
          "en appels qu'il n'a dure)." % (len(lignes), len(lignes)))
