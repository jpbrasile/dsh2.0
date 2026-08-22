"""Table finale : reussite, debit, temps par tache, par niveau d'effort.

Les jetons et les secondes de decodage viennent du bloc `timings` que
llama-server rend lui-meme, releve par le proxy 8006 entre deux marqueurs.
Le chrono client ne sert qu'au temps de tache (il inclut l'agent, les outils,
Julia -- c'est bien ce qu'on veut pour "temps par tache").
"""
import io, json, os, statistics as st, sys

# Une campagne archivee s'analyse la ou elle a ete rangee : `analyse.py <dir>`.
# Sans ca, comparer deux campagnes obligerait a les ecraser l'une l'autre.
B = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))


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
iteratif = any(l.get("mode") == "iterate" for l in lignes)
print("=== synthese par niveau ===")
entete = "%-8s %-8s %9s %9s %10s %10s %9s" % ("effort","reussite","temps_med","temps_moy","gen_tok_moy","dec_t/s","appels_moy")
if iteratif:
    entete += " %8s %9s" % ("julia_moy", "sans_test")
print(entete)
synth = {}
for e in efforts:
    g = [x for x in lignes if x["effort"] == e]
    ok = sum(1 for x in g if x["verdict"] == "PASS")
    tot_gen = sum(x["gen"] for x in g); tot_dec = sum(x["dec_s"] for x in g)
    s = dict(n=len(g), ok=ok,
             med=st.median([x["wall_s"] for x in g]),
             moy=st.mean([x["wall_s"] for x in g]),
             gen=tot_gen/len(g), tps=(tot_gen/tot_dec if tot_dec else 0),
             ap=st.mean([x["appels"] for x in g]),
             jl=st.mean([x.get("julia_runs", 0) for x in g]),
             # Un run sans mytest.jl en mode iteratif n'est pas une donnee
             # manquante : le modele a repondu DONE sans faire ce qu'on lui a
             # explicitement demande. C'est une mesure d'obeissance.
             sans=sum(1 for x in g if not x.get("a_teste", False)))
    synth[e] = s
    ligne = "%-8s %2d/%-5d %9.1f %9.1f %10.0f %10.1f %9.1f" % (
        e, ok, len(g), s["med"], s["moy"], s["gen"], s["tps"], s["ap"])
    if iteratif:
        ligne += " %8.1f %9s" % (s["jl"], "%d/%d" % (s["sans"], len(g)))
    print(ligne)

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

# --- BRAS WEB : compare, et verifie que les bras sont bien distincts ----------
# Le bras "sans web" ne desactive pas les outils, il ne les demande pas. La
# comparaison n'a donc de sens que si on MESURE ce que chaque bras a reellement
# appele. Deux facons d'etre trompe, et les deux sont verifiees ici :
#   - un bras "sans" qui cherche quand meme  -> les bras ne sont pas disjoints ;
#   - un bras "avec" qui ne cherche jamais   -> il n'y a qu'un seul bras, et
#     l'ecart mesure est un ecart entre deux tirages du meme reglage.
bras = sorted({l.get("bras_web", False) for l in lignes})
if len(bras) > 1 or any(l.get("appels_web", -1) > 0 for l in lignes):
    print()
    print("=== bras web ===")
    print("%-12s %-9s %9s %10s %10s %9s" % ("bras", "reussite", "temps_moy",
                                            "gen_tok_moy", "appels_web", "runs_web"))
    for b in bras:
        g = [x for x in lignes if x.get("bras_web", False) == b]
        mes = [x for x in g if x.get("appels_web", -1) >= 0]
        aw = [x["appels_web"] for x in mes]
        print("%-12s %2d/%-6d %9.1f %10.0f %10s %9s"
              % ("avec web" if b else "sans web",
                 sum(1 for x in g if x["verdict"] == "PASS"), len(g),
                 st.mean([x["wall_s"] for x in g]),
                 st.mean([x["gen"] for x in g]),
                 ("%.1f" % st.mean(aw)) if aw else "n/a",
                 "%d/%d" % (sum(1 for v in aw if v > 0), len(mes)) if mes else "n/a"))

    triche = [l for l in lignes if not l.get("bras_web", False) and l.get("appels_web", -1) > 0]
    muet = [l for l in lignes if l.get("bras_web", False) and l.get("appels_web", -1) == 0]
    if triche:
        print("!!! %d run(s) du bras SANS web ont appele un outil web : les bras "
              "ne sont pas disjoints." % len(triche))
        for l in triche[:8]:
            print("      %-6s %-5s r%d : %d appel(s)" % (l["effort"], l["tache"], l["rep"], l["appels_web"]))
    if muet:
        print("!!! %d run(s) du bras AVEC web n'ont appele AUCUN outil web : pour "
              "ces runs il n'y a pas deux bras, il y en a un." % len(muet))
        for l in muet[:8]:
            print("      %-6s %-5s r%d" % (l["effort"], l["tache"], l["rep"]))
    if not triche and not muet and len(bras) > 1:
        print("les deux bras sont disjoints : aucun run 'sans' n'a cherche, "
              "aucun run 'avec' ne s'en est dispense.")

    # Les taches a fait externe sont le lieu ou une recherche PEUT aider ; les
    # autres sont le temoin. Si le bras web ameliore aussi les temoins, ce n'est
    # pas la recherche qui agit.
    for nom in ("expert_faits_externes.txt", "limite_faits_externes.txt"):
        p = os.path.join(B, "tasks", nom)
        if not os.path.exists(p):
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", nom)
        if not os.path.exists(p):
            continue
        ext = {x.strip() for x in io.open(p, encoding="utf-8") if x.strip()}
        concernees = {l["tache"] for l in lignes} & ext
        if not concernees or len(bras) < 2:
            continue
        print()
        print("--- %s : taches a fait externe %s, temoins le reste"
              % (nom.split("_")[0], ",".join(sorted(concernees))))
        for etiquette, cible in (("fait externe", lambda t: t in ext),
                                 ("temoin", lambda t: t not in ext)):
            cases = []
            for b in bras:
                g = [x for x in lignes if x.get("bras_web", False) == b and cible(x["tache"])]
                if g:
                    cases.append("%s %d/%d" % ("avec" if b else "sans",
                                               sum(1 for x in g if x["verdict"] == "PASS"), len(g)))
            print("    %-14s %s" % (etiquette, "   ".join(cases)))

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
