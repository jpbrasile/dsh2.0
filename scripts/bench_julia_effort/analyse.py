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

# attribution des appels a un run, par marqueurs
par_run, courant = {}, None
for r in wire:
    if r.get("kind") == "mark":
        t = r["tag"].split("|")
        courant = (t[0], t[1]) if len(t) == 3 and t[2] == "debut" else None
        continue
    if courant and r.get("kind") == "call":
        par_run.setdefault(courant, []).append(r)

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
    a = agrege(par_run.get((r["effort"], r["tache"]), []))
    lignes.append({**r, **a})

ordre = ["off", "low", "medium", "high", "xhigh"]
efforts = [e for e in ordre if any(l["effort"] == e for l in lignes)]

print("=== par tache ===")
print("%-6s %-5s %-4s %7s %7s %7s %6s  %s" % ("effort","tache","ok","temps_s","gen_tok","dec_t/s","appels","pourquoi"))
for e in efforts:
    for l in [x for x in lignes if x["effort"] == e]:
        tps = l["gen"]/l["dec_s"] if l["dec_s"] else 0
        print("%-6s %-5s %-4s %7.1f %7d %7.1f %6d  %s"
              % (e, l["tache"], l["verdict"], l["wall_s"], l["gen"], tps, l["appels"], l["why"][:52]))

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
    print("    reussite  %d vs %d  (ecart %d)" % (h["ok"], x["ok"], abs(h["ok"]-x["ok"])))
    print("    temps moy %.1f vs %.1f s  (ecart %.0f %%)" % (h["moy"], x["moy"], 100*abs(h["moy"]-x["moy"])/max(h["moy"],1e-9)))
    print("    jetons    %.0f vs %.0f  (ecart %.0f %%)" % (h["gen"], x["gen"], 100*abs(h["gen"]-x["gen"])/max(h["gen"],1e-9)))

print()
print("=== par tache, tous niveaux (difficulte) ===")
for t in sorted({l["tache"] for l in lignes}):
    g = [x for x in lignes if x["tache"] == t]
    print("  %-5s %d/%d  %s" % (t, sum(1 for x in g if x["verdict"]=="PASS"), len(g),
                                " ".join("%s:%s" % (x["effort"][:2], "O" if x["verdict"]=="PASS" else ".") for x in g)))
