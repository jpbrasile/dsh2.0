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


# COMPARER DEUX BRAS : `analyse.py --comparer A.jsonl B.jsonl`.
#
# La mesure vit ici et pas dans la tete de qui redige. Elle a deja derive une
# fois : un bras annonce 2/3 contre 1/3 le 23/08 alors que les deux enonces
# differaient par autre chose que l'axe teste. Trois choses sont donc dites
# ensemble, toujours, et dans cet ordre -- l'avertissement AVANT le score.
#
# LE SCORE FINAL N'EST PAS LA MESURE. Un run qui passe du premier coup ne
# pose pas la question ; un run coupe au delai n'y repond pas. Ce qui compte
# est : PARMI les runs qui n'ont pas passe au tour 1, combien finissent en
# PASS -- et sur combien de runs la question se pose reellement.
def _marques(r):
    out = []
    for t in r.get('par_tour') or []:
        why = t.get('why') or ''
        out.append('C' if why.startswith('timeout')
                   else ('P' if t.get('verdict') == 'PASS' else 'F'))
    return ''.join(out) or '-'


def _comparer(chemins):
    bras = []
    for c in chemins:
        rs = [json.loads(l) for l in io.open(c, encoding='utf-8') if l.strip()]
        bras.append((os.path.basename(c), rs))

    print('=== provenance : quel enonce chaque bras a-t-il recu ? ===')
    shas = []
    for nom, rs in bras:
        e = sorted({r.get('enonce_sha') or '(aucune)' for r in rs})
        shas.append(tuple(e))
        b = sorted({(r.get('timeout_tour'), r.get('tours_max')) for r in rs})
        # Budget ABSENT = 'inconnu', jamais un nombre par defaut : les
        # campagnes anterieures au 23/08 ne l enregistrent pas.
        bud = ', '.join('inconnu' if t is None else ('%ss x%s' % (t, n))
                        for t, n in b)
        print('  %-28s %-14s budget %s' % (nom[:28], ', '.join(e), bud))
    if any('(aucune)' in e for e in shas):
        print('  Au moins un bras N ENREGISTRE PAS son enonce (campagne lancee')
        print('  avant l ajout de l empreinte) : cet enonce est INCONNU.')
        print('  L ecart mesure ci-dessous ne peut pas etre attribue a l axe teste.')
    elif len(set(shas)) > 1:
        print('  Les deux bras ont des enonces DIFFERENTS. C est correct si et')
        print('  seulement si cette difference EST l axe teste.')

    print()
    print('=== les runs, tour par tour  (P=passe  F=juge et rate  C=coupe) ===')
    for nom, rs in bras:
        for r in sorted(rs, key=lambda z: z.get('rep', 0)):
            faites = sum(1 for x in (r.get('recherches_banc') or []) if x.get('requete'))
            print('  %-18s r%-2s %-4s %7.1fs julia=%-3s [%s] rech=%d'
                  % (nom[:18], r.get('rep'), r.get('verdict'), r.get('wall_s') or 0,
                     r.get('julia_runs'), _marques(r), faites))

    print()
    print('=== la mesure : PARMI les runs qui n ont pas passe au tour 1 ===')
    for nom, rs in bras:
        pose = [r for r in rs if (r.get('par_tour') or [{}])[0].get('verdict') != 'PASS']
        gagne = [r for r in pose if r.get('verdict') == 'PASS']
        print('  %-28s la question se pose sur %d run(s) sur %d ; %d finissent PASS'
              % (nom[:28], len(pose), len(rs), len(gagne)))
    petit = min(len(rs) for _, rs in bras)
    if petit < 10:
        print('  n=%d par bras : aucun ecart n est separable ici. Le tableau' % petit)
        print('  ci-dessus se lit, il ne se conclut pas.')

    print()
    print('=== tours sans verdict (coupes au delai) ===')
    for nom, rs in bras:
        tours = [t for r in rs for t in (r.get('par_tour') or [])]
        coup = [t for t in tours if (t.get('why') or '').startswith('timeout')]
        t1 = [r for r in rs if ((r.get('par_tour') or [{}])[0].get('why') or '').startswith('timeout')]
        jam = [r for r in rs if r.get('par_tour') and all(
               (t.get('why') or '').startswith('timeout') for t in r['par_tour'])]
        print('  %-28s %d/%d tours coupes ; %d run(s) perdent le 1er ; %d jamais juge(s)'
              % (nom[:28], len(coup), len(tours), len(t1), len(jam)))


if len(sys.argv) > 2 and sys.argv[1] == '--comparer':
    _comparer(sys.argv[2:])
    raise SystemExit(0)


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


par_run, bornes, courant, rejoues = {}, {}, None, 0
for r in wire:
    if r.get("kind") == "mark":
        cle, bout = _cle(r["tag"].split("|"))
        if cle and bout == "debut":
            courant = cle
            if courant in par_run:
                rejoues += 1
            par_run[courant] = []
            bornes[courant] = [r.get("t", 0), None]
        else:
            if courant in bornes:
                bornes[courant][1] = r.get("t", 0)
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
def _union_s(calls):
    """Duree COUVERTE par les appels, en union d'intervalles -- pas leur somme.

    Un run passe legitimement plusieurs appels en meme temps : dsh emet une
    requete de titre de session en parallele du premier tour de l'agent.
    Sommer les durees comptait deux fois le meme instant et faisait crier le
    controle sur des runs sains. Ce qui est impossible, ce n'est pas que la
    somme depasse la duree du run, c'est que le TEMPS COUVERT la depasse.
    """
    iv = sorted((c["t0"], c["t0"] + c.get("ms", 0)) for c in calls if "t0" in c)
    total, fin = 0, None
    for a, b in iv:
        if fin is None or a > fin:
            total += b - a
            fin = b
        elif b > fin:
            total += b - fin
            fin = b
    return total / 1000.0


# CLE A TROIS CHAMPS. Le 22/08, quand le marqueur a pris la repetition, la cle
# de `par_run` est passee a (effort, tache, rep) -- mais CE controle est reste
# sur (effort, tache). Une cle qui ne correspond a rien rend une liste vide,
# donc une somme nulle, donc la condition n'a plus jamais pu etre vraie : le
# controle a imprime "N/N runs coherents" pendant toute la campagne suivante
# sans regarder un seul appel. Un compte egal a la population est exactement ce
# que produit une porte qui ne mesure rien. Bras known-BAD :
# `python analyse.py fixtures/horloge_bad`.
print()
impossibles = []
for l in lignes:
    somme_s = _union_s(par_run.get((l["effort"], l["tache"], l.get("rep", 1)), []))
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

# --- CONTROLE D'ECHEANCE, cable : il tourne a chaque analyse ------------------
# Un run ne peut pas durer plus longtemps que sa propre echeance. S'il le fait,
# c'est que le kill du delai n'a PAS ferme l'arbre : le fils direct est mort,
# un descendant a survecu en gardant le tuyau de sortie ouvert, et la campagne
# est restee bloquee derriere lui -- pendant que l'orphelin continuait d'appeler
# le modele et d'occuper la carte.
#
# PRISE REELLE, 22/08 : r2/high/t11, echeance 900 s, duree relevee 1588,9 s.
# 689 s de campagne figee, et rien d'autre dans le fichier ne le montrait : le
# verdict FAIL/timeout etait exact, la duree seule etait aberrante. Le remede
# est dans bench.py (lancer_borne / tuer_arbre) ; ce controle est ce qui dirait
# qu'il a lache.
try:
    from bench import TIMEOUT, TIMEOUT_ITER
except Exception:
    TIMEOUT, TIMEOUT_ITER = 900, 1800

print()
debordements = []
for l in lignes:
    echeance = TIMEOUT_ITER if l.get("mode") == "iterate" else TIMEOUT
    # 60 s = la seconde echeance que lancer_borne s'accorde apres le kill, plus
    # le temps du verdict Julia. Au-dela, l'arbre n'a pas ete ferme.
    if l["wall_s"] > echeance + 60:
        debordements.append((l.get("rep", 1), l["effort"], l["tache"],
                             l["wall_s"], echeance))
if debordements:
    print("!!! ARBRE NON FERME -- %d run(s) ont dure plus que leur echeance."
          % len(debordements))
    for r, e, t, w, ech in debordements:
        print("      r%s %-6s %-5s  duree %.1f s  pour une echeance de %d s "
              "(campagne figee %.0f s)" % (r, e, t, w, ech, w - ech))
    print("      Le delai a tue le fils direct, pas l'arbre. Les temps par "
          "tache des lignes suivantes sont a lire avec cette pause en tete.")
else:
    print("controle d'echeance : %d/%d runs sous leur echeance (le delai a bien "
          "ferme l'arbre)." % (len(lignes), len(lignes)))

# --- CONTROLE DE PARTAGE DU SERVEUR, cable ------------------------------------
# Un agent ETRANGER qui parle au meme serveur pendant la campagne est invisible
# pour les deux controles ci-dessus : ses appels tombent DANS la fenetre du run
# ouvert, ils se chevauchent avec ceux du run, donc ni la somme ni l'union ne
# denoncent quoi que ce soit. Ils sont pourtant comptes dans le debit du run, et
# ils lui volent la carte -- sur un serveur `--parallel 1` le run attend derriere.
#
# Le signal qui le trahit vient d'ailleurs : une conversation d'agent APPARTIENT
# a un run. Elle commence a 2-3 messages, grandit de 2 par tour, et meurt avec
# lui. Une conversation qui TRAVERSE plusieurs fenetres n'appartient donc a
# aucune -- c'est un agent d'ailleurs, ou un orphelin d'avant.
#
# PRISE REELLE, 22/08 : quatre segments (la compaction remet le compteur a zero)
# de 09:16:08 a 09:54:59, 91 appels, ~2010 s de decodage, traversant 22 fenetres
# de la repetition 1. Les debits de ces runs incluent un agent qui n'etait pas
# la campagne. Bras known-BAD : `python analyse.py fixtures/intrus_bad`.
def _conversations(wire):
    """Chaine les appels en conversations : n messages prolonge n-2.

    Les appels de titre de session (`n_tools == 0`) sont ecartes : ils sont
    seuls, portent toujours 2 messages, et se raccrocheraient a tort.
    """
    convs, ouverts = [], {}
    for r in wire:
        if r.get("kind") != "call":
            continue
        env = r.get("sent") or {}
        n = env.get("n_messages")
        if n is None or (env.get("n_tools") or 0) == 0:
            continue
        c = ouverts.pop(n - 2, None)
        if c is None:
            c = {"n0": n, "calls": []}
            convs.append(c)
        c["calls"].append(r)
        c["n1"] = n
        ouverts[n] = c
    return convs


def _fenetre_de(ts, bornes):
    for cle, (a, b) in bornes.items():
        if a and a <= ts and (b is None or ts <= b):
            return cle
    return None


print()
intrus = []
for c in _conversations(wire):
    vues = {_fenetre_de(x["t0"], bornes) for x in c["calls"]}
    vues.discard(None)
    if len(vues) > 1:
        intrus.append((c, vues))
if intrus:
    runs = set()
    for c, vues in intrus:
        runs |= vues
    dec = sum(x.get("ms", 0) for c, _ in intrus for x in c["calls"]) / 1000.0
    print("!!! SERVEUR PARTAGE -- %d conversation(s) traversent plusieurs runs."
          % len(intrus))
    for c, vues in sorted(intrus, key=lambda z: -len(z[1]))[:6]:
        print("      messages %d -> %d : %d appels, %.0f s de decodage, "
              "%d fenetres traversees"
              % (c["n0"], c["n1"], len(c["calls"]),
                 sum(x.get("ms", 0) for x in c["calls"]) / 1000.0, len(vues)))
    print("      %d run(s) touches, %.0f s de decodage etranger au total."
          % (len(runs), dec))
    print("      Les debits de ces runs comptent un agent qui n'est pas la "
          "campagne, et leurs temps par tache incluent l'attente derriere lui.")
else:
    print("controle de partage : aucune conversation ne traverse deux runs "
          "(le serveur n'a servi que la campagne).")


print()
# TOURS COUPES PAR LE DELAI -- comptes A PART des echecs.
#
# Un tour coupe n'a pas ete juge : le verificateur n'a jamais tourne, donc il
# n'y a ni PASS ni FAIL. Les melanger aux echecs produit deux lectures
# fausses a la fois -- une coupure lue comme un refus du juge, et un budget
# trop court lu comme une incapacite du modele.
#
# Mesure du 22/08 sur les 34 runs en boucle enregistres : 12 tours coupes sur
# 58 joues (21 %), et 7 runs sur 34 perdent leur PREMIER tour -- celui qui ne
# transmet rien au suivant. La LISTE NOMINATIVE, pas le seul total : un
# compte de coupures depend de ce qu'on appelle une coupure.
coupes = [(l, t) for l in lignes for t in (l.get('par_tour') or [])
          if (t.get('why') or '').startswith('timeout')]
tours_joues = sum(len(l.get('par_tour') or []) for l in lignes)
if tours_joues:
    print('=== tours coupes par le delai (aucun verdict rendu) ===')
    if not coupes:
        print('  aucun -- les %d tours joues ont tous ete juges.' % tours_joues)
    else:
        t1 = {(l['effort'], l['tache'], l['rep']) for l, t in coupes if t['tour'] == 1}
        print('  %d tour(s) coupe(s) sur %d joues ; %d run(s) sur %d perdent'
              % (len(coupes), tours_joues, len(t1), len(lignes)))
        print('  leur PREMIER tour -- le seul qui ne transmet rien au suivant.')
        for l, t in sorted(coupes, key=lambda z: (z[0]['tache'], z[0]['rep'], z[1]['tour'])):
            print('    r%-2d %-6s %-5s tour %d : %s'
                  % (l['rep'], l['effort'], l['tache'], t['tour'], t.get('why')))
else:
    print('=== tours coupes par le delai : campagne hors boucle, sans tours ===')


print()
# QUEL ENONCE CES RUNS ONT-ILS REELLEMENT RECU ?
#
# Le 23/08 il a fallu retirer a la main une comparaison publiee : le
# preambule de boucle n'allait qu'au bras avec recherche, et rien dans les
# enregistrements ne le disait. Une campagne dont l'enonce a change se lisait
# exactement comme une campagne dont il n'avait pas change.
#
# ABSENCE != VALEUR : un run anterieur au 23/08 n'a pas d'empreinte, et il est
# compte comme SANS EMPREINTE, jamais range avec les autres.
print('=== empreintes de l enonce ===')
sha = {}
sans = 0
for l in lignes:
    e = l.get('enonce_sha')
    if not e:
        sans += 1
    else:
        sha.setdefault(e, []).append(l)
if sans:
    print('  %d run(s) SANS empreinte -- enregistres avant le 23/08. Leur enonce'
          % sans)
    print('  est inconnu : ils ne se comparent a rien sur cet axe.')
for e, rs in sorted(sha.items(), key=lambda z: -len(z[1])):
    bras = sorted({'avec web' if r.get('bras_web') else 'sans web' for r in rs})
    print('  %s : %d run(s)  [%s]' % (e, len(rs), ', '.join(bras)))
if len(sha) > 1:
    print('  ATTENTION : %d enonces differents dans cette campagne. Un ecart de'
          % len(sha))
    print('  score entre deux empreintes ne mesure pas ce que la campagne croit')
    print('  mesurer, sauf si la difference d enonce EST l axe teste.')
elif len(sha) == 1 and not sans:
    print('  un seul enonce pour toute la campagne.')
