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
# --- MORT FOURNISSEUR, cable dans --comparer ---------------------------------
#
# Sixieme instance de la meme forme : une ABSENCE rendue comme un RESULTAT.
# Quand la dorsale coupe (429, quota, credential), `dsh` meurt en deux lignes.
# Le banc, lui, voit ce qui reste sur le disque et enregistre un verdict :
# "aucun solution.jl ecrit", ou pire, la vraie erreur Julia d un brouillon que
# le modele etait en train de remplacer (mesure du 23/08 : t31_web/r03 tour 2,
# coupe sur "Fixing both files:" et juge sur le fichier d avant).
#
# Un tour tue par le fournisseur n est NI un echec NI une reussite du modele.
# Il recoit donc sa propre valeur -- la lettre X -- et il n entre dans aucun
# taux. L absence sans trace en recoit une autre : "SANS TRACE".
TYPES_FATAL = ('RATE_LIMIT', 'QUOTA', 'MISSING_CREDENTIAL',
               'INVALID_REQUEST', 'PI_AI_ERROR', 'AUTH', 'SERVER_ERROR')


def _type_fatal(chemin):
    """Le type d erreur fournisseur qui a tue ce tour, ou None."""
    try:
        for l in io.open(chemin, encoding='utf-8', errors='replace'):
            if not l.startswith('dsh: '):
                continue
            t = l[5:].split(':', 1)[0].strip()
            if t in TYPES_FATAL:
                return t
    except OSError:
        return None
    return None


def _morts_fournisseur(chemin_jsonl, racine=None):
    """{(rep, effort, tache, tour): TYPE}, ou None si aucune trace au sol.

    None et {} ne disent PAS la meme chose : {} veut dire "regarde, rien" ;
    None veut dire "pas regarde" -- et c est ce que le rapport doit ecrire.
    """
    base = os.path.basename(chemin_jsonl)
    if not base.startswith('resultats_') or not base.endswith('.jsonl'):
        return None
    etiq = base[len('resultats_'):-len('.jsonl')]
    rac = racine or os.path.join(os.path.dirname(os.path.abspath(chemin_jsonl)), 'runs')
    d = os.path.join(rac, etiq)
    if not os.path.isdir(d):
        return None
    out = {}
    for rep_dir in sorted(os.listdir(d)):
        if not rep_dir.startswith('r'):
            continue
        try:
            rep = int(rep_dir[1:].split('_')[0])
        except ValueError:
            continue
        for cur, _sous, fichiers in os.walk(os.path.join(d, rep_dir)):
            for f in fichiers:
                if not (f.startswith('_dsh') and f.endswith('.out')):
                    continue
                t = _type_fatal(os.path.join(cur, f))
                if not t:
                    continue
                # _dsh_t3.out -> tour 3 ; _dsh.out -> tour 1 (un seul coup).
                milieu = f[len('_dsh'):-len('.out')]
                tour = int(milieu[2:]) if milieu.startswith('_t') and milieu[2:].isdigit() else 1
                # La tache DOIT etre dans la cle. Sans elle, une campagne
                # multi-taches ecrase ses 9 morts en 1 -- mesure du 23/08 sur
                # oxviafree, trouvee par le bras known-BAD de ce garde meme.
                tache = os.path.basename(cur)
                effort = os.path.basename(os.path.dirname(cur))
                out[(rep, effort, tache, tour)] = t
    return out

def _marques(r, morts=None):
    out = []
    rep = r.get('rep')
    for t in r.get('par_tour') or []:
        why = t.get('why') or ''
        cle = (rep, r.get('effort'), r.get('tache'), t.get('tour'))
        if morts and cle in morts:
            out.append('X')          # tue par la dorsale : ni echec ni reussite
        elif why.startswith('timeout'):
            out.append('C')
        else:
            out.append('P' if t.get('verdict') == 'PASS' else 'F')
    return ''.join(out) or '-'


def _comparer(chemins):
    bras = []
    for c in chemins:
        rs = [json.loads(l) for l in io.open(c, encoding='utf-8') if l.strip()]
        bras.append((os.path.basename(c), rs, _morts_fournisseur(c)))

    print('=== provenance : quel enonce chaque bras a-t-il recu ? ===')
    shas = []
    for nom, rs, _m in bras:
        e = sorted({r.get('enonce_sha') or '(aucune)' for r in rs})
        shas.append(tuple(e))
        # Trier une absence a cote d un entier fait planter la comparaison :
        # un run sans detail (exception d ouvrier) n enregistre pas son
        # budget, et None < 900 n existe pas. L absence se range en tete
        # et se dit 'inconnu' juste en dessous.
        b = sorted({(r.get('timeout_tour'), r.get('tours_max')) for r in rs},
                   key=lambda z: (z[0] is None, z[0] or 0,
                                  z[1] is None, z[1] or 0))
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
        # Avec plus de deux bras, "les deux bras different" est faux : il faut
        # dire QUI partage avec QUI. Un rapport qui resume mal la provenance
        # est un rapport qu on cesse de lire.
        groupes = {}
        for (nom, _rs, _m), e in zip(bras, shas):
            groupes.setdefault(e, []).append(nom[:24])
        print('  %d enonce(s) distinct(s) pour %d bras :' % (len(groupes), len(bras)))
        for e, noms in sorted(groupes.items(), key=lambda kv: -len(kv[1])):
            print('    %-14s <- %s' % (', '.join(e), ' + '.join(noms)))
        print('  C est correct si et seulement si CE decoupage est l axe teste.')

    print()
    print('=== tours tues par la dorsale (ni echec ni reussite du modele) ===')
    for nom, rs, m in bras:
        if m is None:
            print('  %-28s SANS TRACE : pas de repertoire runs/ pour cette' % nom[:28])
            print('  %-28s campagne. On ne sait pas -- ce n est pas "aucun".' % '')
            continue
        if not m:
            print('  %-28s aucun' % nom[:28])
            continue
        print('  %-28s %d tour(s) :' % (nom[:28], len(m)))
        for (rep, eff, tac, tour), t in sorted(m.items()):
            print('       r%-2s %-7s %-5s tour %s : %s' % (rep, eff, tac, tour, t))
    if any(m for _n, _r, m in bras if m):
        print('  Ces tours sont marques X ci-dessous et RETIRES de la mesure.')
        print('  Un tour tue par la dorsale a pu etre juge sur un brouillon que')
        print('  le modele etait en train de remplacer : son verdict est un')
        print('  artefact, pas un resultat.')

    print()
    print('=== les runs, tour par tour  (P=passe  F=juge et rate  C=coupe  X=dorsale) ===')
    for nom, rs, m in bras:
        for r in sorted(rs, key=lambda z: z.get('rep', 0)):
            faites = sum(1 for x in (r.get('recherches_banc') or []) if x.get('requete'))
            print('  %-18s r%-2s %-4s %7.1fs julia=%-3s [%s] rech=%d'
                  % (nom[:18], r.get('rep'), r.get('verdict'), r.get('wall_s') or 0,
                     r.get('julia_runs'), _marques(r, m), faites))

    print()
    print('=== la mesure : PARMI les runs qui n ont pas passe au tour 1 ===')
    nets = []
    for nom, rs, m in bras:
        sales = {(rep, eff, tac) for (rep, eff, tac, _t) in (m or {})}
        propres = [r for r in rs
                   if (r.get('rep'), r.get('effort'), r.get('tache')) not in sales]
        # Un run SANS detail par tour ne dit rien du tour 1. L ecriture
        # precedente -- (par_tour or [{}])[0] -- lui faisait dire "n a pas
        # passe au tour 1", ce qui est une SUPPOSITION deguisee en donnee :
        # un dict vide rend None, et None != 'PASS'. Ces runs existent (juge
        # sans reponse, exception d ouvrier) et ils comptent comme echecs --
        # mais pas dans une statistique qui a besoin du tour 1 pour exister.
        muets = [r for r in propres if not r.get('par_tour')]
        avec = [r for r in propres if r.get('par_tour')]
        # Deux mises de cote de plus, et elles portent sur MES defauts, pas
        # sur ceux du modele.
        #
        # 1) UN TOUR COUPE AU DELAI EST MON BUDGET, PAS UNE PROPRIETE DU
        #    MODELE. La lettre C l affichait deja ; la statistique, elle,
        #    comptait le run comme un echec du bras. Un run dont un tour
        #    meurt sur mon chronometre n a pas eu son tour : il ne temoigne
        #    ni pour ni contre le traitement.
        #
        # 2) UN RUN DU BRAS WEB SANS RECHERCHE DELIVREE N EST PAS UN RUN WEB.
        #    Le traitement n a pas ete administre : c est un run temoin
        #    portant une mauvaise etiquette, et le compter contre le bras web
        #    fait payer au traitement une panne de sa LIVRAISON. Seul le cas
        #    bench-side compte -- recherche REFUSEE alors que le run avait
        #    atteint l etape. Un run qui passe au tour 1 n a jamais eu besoin
        #    du traitement : il sort deja par la question ci-dessous.
        #
        #    Le bras PROMESSE est exclu de cette regle par construction : sa
        #    recherche est annoncee et jamais livree, c est SON traitement.
        coupes_r, sans_trt, detail = [], [], []
        for r in avec:
            if any((t.get('why') or '').startswith('timeout')
                   for t in r['par_tour']):
                coupes_r.append(r)
            elif (r.get('bras_web')
                  and r['par_tour'][0].get('verdict') != 'PASS'
                  and not r.get('rech_faites') and r.get('rech_refusees')):
                sans_trt.append(r)
            else:
                detail.append(r)
        nets.append(len(detail))
        pose = [r for r in detail if r['par_tour'][0].get('verdict') != 'PASS']
        gagne = [r for r in pose if r.get('verdict') == 'PASS']
        print('  %-28s la question se pose sur %d run(s) sur %d ; %d finissent PASS'
              % (nom[:28], len(pose), len(detail), len(gagne)))
        if coupes_r:
            print('  %-28s (%d run(s) avec un tour COUPE AU DELAI, hors mesure :'
                  ' %s -- mon budget, pas le modele)'
                  % ('', len(coupes_r),
                     ', '.join('r%s %s' % (r.get('rep'), r.get('verdict'))
                               for r in coupes_r)))
        if sans_trt:
            print('  %-28s (%d run(s) du bras web SANS recherche delivree,'
                  ' hors mesure : %s -- traitement non administre)'
                  % ('', len(sans_trt),
                     ', '.join('r%s %s' % (r.get('rep'), r.get('verdict'))
                               for r in sans_trt)))
        if muets:
            print('  %-28s (%d run(s) sans detail par tour, hors de CETTE'
                  ' statistique : %s)'
                  % ('', len(muets),
                     ', '.join('r%s %s' % (r.get('rep'), r.get('verdict'))
                               for r in muets)))
        if sales:
            print('  %-28s (%d run(s) mis de cote : %s -- dorsale)'
                  % ('', len(sales), ', '.join('r%s/%s' % (a, c)
                                                for a, _b, c in sorted(sales))))
    petit = min(nets)
    if petit < 10:
        print('  n=%d par bras : aucun ecart n est separable ici. Le tableau' % petit)
        print('  ci-dessus se lit, il ne se conclut pas.')

    print()
    print('=== tours sans verdict (coupes au delai) ===')
    for nom, rs, _m in bras:
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


def _lire(p):
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def _charger(nom, pourquoi):
    """Lit B/<nom>. Si le fichier manque, tente la disposition que `bench.py
    --par` produit : B = _par/<etiq>/ avec w*/wire.jsonl par ouvrier, et les
    verdicts dans ../../resultats_<etiq>_<bras>.jsonl. Ce qui a ete assemble
    est DIT, ligne par ligne : l instrument nomme ce qu il a lu."""
    p = os.path.join(B, nom)
    if os.path.exists(p):
        return _lire(p)
    import glob
    etiq = os.path.basename(B)
    if nom == "wire.jsonl":
        morceaux = sorted(glob.glob(os.path.join(B, "w*", "wire.jsonl")))
    else:
        morceaux = sorted(glob.glob(os.path.join(B, "..", "..", "resultats_%s_*.jsonl" % etiq)))
    if morceaux:
        print("NOTE : %s absent dans %s ; assemble depuis %d fichier(s) :" % (nom, B, len(morceaux)))
        for m in morceaux:
            print("       %s" % os.path.relpath(m, B))
        out = []
        for m in morceaux:
            out += _lire(m)
        if nom == "wire.jsonl":
            out.sort(key=lambda r: r.get("t") or r.get("t0") or 0)
        print()
        return out
    raise SystemExit(
        "%s absent. %s\nLancer d'abord : python bench.py off,low,medium,high,xhigh"
        % (nom, pourquoi))


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
    """Rend (cle_du_run, bout, tour). Trois formes de marque existent :
      effort|tache|rN|tM|bout   mode BOUCLE  (bench.py, un_run_boucle)
      effort|tache|rN|bout      mode simple  (bench.py, un_run)
      effort|tache|bout         campagnes d avant la repetition
    Mesure du 23/08 (red team, t31e) : 55 marques au sol, TOUTES a cinq
    champs, 785 appels, ZERO attribue -- cette fonction ne connaissait que
    quatre et trois champs et rendait (None, None) sans le dire. La colonne
    appels affichait 0 partout, et deux controles cables (horloge, partage)
    passaient au vert sur une liste vide. Leur bras known-BAD tirait sur des
    marques a quatre champs : le chemin reel n avait jamais ete parcouru.
    Bras known-BAD a cinq champs : `python analyse.py fixtures/horloge_bad_boucle`.

    Quatrieme forme, depuis le 23/08 apres-midi (bras dans la marque) :
      effort|tache|rN|tM|bras|bout
    La cle rendue est (effort, tache, rep, bras, slot) ; bras et slot valent
    None quand la marque ne les porte pas. Sans le bras, `sans` et `web` a
    repetition egale partagent une cle ; sans le slot, deux ouvriers dont les
    fils sont assembles se donnent leurs appels. Le slot vient de
    l enregistrement de marque, pas du tag (voir la boucle ci-dessous).
    Bras known-BAD : `python analyse.py fixtures/bras_melanges_bad`."""
    if len(t) == 6 and t[2].startswith("r") and t[3].startswith("t"):
        return (t[0], t[1], int(t[2][1:]), t[4]), t[5], int(t[3][1:])
    if len(t) == 5 and t[2].startswith("r") and t[3].startswith("t"):
        return (t[0], t[1], int(t[2][1:]), None), t[4], int(t[3][1:])
    if len(t) == 4 and t[2].startswith("r"):
        return (t[0], t[1], int(t[2][1:]), None), t[3], 1
    if len(t) == 3:
        return (t[0], t[1], 1, None), t[2], 1
    return None, None, None


def _compatible(cle, l):
    """La fenetre `cle` = (effort, tache, rep, bras, slot) peut-elle etre celle
    du run `l` ? bras et slot ne departagent que s ils sont connus des DEUX cotes."""
    if cle[:3] != (l["effort"], l["tache"], l.get("rep", 1)):
        return False
    if l.get("bras") and cle[3] is not None and cle[3] != l["bras"]:
        return False
    if l.get("slot") is not None and cle[4] is not None and cle[4] != l["slot"]:
        return False
    return True


def appels_de(l):
    """Les appels du run `l` (une ligne de resultats).

    Candidates : les fenetres du fil compatibles (effort, tache, repetition,
    puis bras et slot quand les deux cotes les portent). Une seule : ses
    appels. Plusieurs, et `l` est la SEULE ligne de resultats qui leur
    corresponde : c est un rejeu (campagne relancee dans le meme fil), la
    derniere fenetre est retenue -- la convention d avant, gardee pour ce
    pour quoi elle a ete ecrite. Plusieurs fenetres ET plusieurs lignes :
    AMBIGU, rien n est attribue et c est dit. Attribuer au hasard produit un
    debit faux qui a l air mesure : c est ce que faisait le dict a une
    entree par cle (fixtures/bras_melanges_bad, 23/08)."""
    cands = [w for w in fenetres if _compatible(w["cle"], l)]
    if len(cands) == 1:
        return cands[0]["calls"]
    if not cands:
        return []
    concurrents = [x for x in res if any(_compatible(w["cle"], x) for w in cands)]
    if len(concurrents) == 1:
        return cands[-1]["calls"]
    ambigus.append((l["effort"], l["tache"], l.get("rep", 1), l.get("bras"), l.get("slot"),
                    [w["cle"] for w in cands]))
    return []


fenetres, rejoues, inconnues, ambigus = [], 0, [], []
ouverts = {}          # slot -> fenetre ouverte
for r in wire:
    if r.get("kind") == "mark":
        cle, bout, tour = _cle(r["tag"].split("|"))
        if cle is None:
            # UNE MARQUE NON RECONNUE EST DITE, pas avalee : c est exactement
            # l absence qui a cache la trouvaille du 23/08.
            inconnues.append(r["tag"])
            continue
        s = r.get("slot")
        cle = cle + (s,)
        if bout == "debut":
            if tour > 1:
                # Tour suivant du MEME run : la `fin` du tour precedent a
                # ferme sa fenetre, on ROUVRE la meme -- les appels du tour
                # d avant restent attribues, ceux qui viennent s y ajoutent.
                # (Premiere version : une fenetre neuve par tour, 13 "rejeux"
                # sur t31e et des jetons divises par deux.)
                anc = [x for x in fenetres if x["cle"] == cle]
                if anc:
                    ouverts[s] = anc[-1]
                    continue
            if any(x["cle"] == cle for x in fenetres):
                rejoues += 1
            w = {"cle": cle, "calls": [], "a": r.get("t", 0), "b": None}
            fenetres.append(w)
            ouverts[s] = w
        else:
            w = ouverts.pop(s, None)
            if w is not None:
                w["b"] = r.get("t", 0)
        continue
    if r.get("kind") == "call":
        # Une fenetre ouverte PAR SLOT : dans un fil assemble de plusieurs
        # ouvriers, la `fin` du slot 1 ne ferme pas la fenetre du slot 0.
        w = ouverts.get(r.get("slot"))
        if w is not None:
            w["calls"].append(r)
if inconnues:
    print("!!! %d MARQUE(S) DE FORME INCONNUE dans wire.jsonl -- leurs appels ne "
          "sont attribues a AUCUN run, et tout controle fonde sur l attribution "
          "regarde une liste vide. Exemple : %s" % (len(inconnues), inconnues[0]))
    print()
if rejoues:
    print("NOTE : %d fenetre(s) de wire.jsonl portent la cle d une fenetre "
          "precedente (campagnes successives dans le meme fil). Pour un run "
          "unique, la DERNIERE est retenue ; pour plusieurs runs, voir AMBIGUS.\n"
          % rejoues)

def agrege(calls):
    """`ntim` : combien d appels portent REELLEMENT un bloc timings.

    Sans lui, une dorsale qui n en envoie jamais -- c est le cas de toute
    dorsale distante, seul llama-server les renvoie -- produisait gen=0 et
    0.0 t/s sur CHAQUE run. Un debit nul affiche comme une mesure, alors que
    la mesure n a simplement pas eu lieu. Mesure du 23/08 : 650 appels sur le
    fil des campagnes t31e, 0 avec timings, et la colonne debit entierement
    a zero. C est l un des trois instruments annonces en tete de ce fichier.
    """
    gen = dec_ms = pre_n = pre_ms = ntim = 0
    # Second instrument, quand `timings` manque : `usage.completion_tokens`
    # sur `ms` (duree de l appel vue par le proxy). Mesure du 23/08 (pair,
    # t31e) : 799 appels sur 803 le portent -- la donnee etait la depuis le
    # debut, et la colonne disait "-". C est un debit BOUT-EN-BOUT (prefill
    # et reseau compris), pas un debit de decodage : il est affiche avec un
    # "~" et jamais fondu dans l autre.
    gen_u = e2e_ms = nusage = 0
    for c in calls:
        t = c.get("timings") or {}
        if t:
            ntim += 1
        gen += t.get("predicted_n") or 0
        dec_ms += t.get("predicted_ms") or 0
        pre_n += t.get("prompt_n") or 0
        pre_ms += t.get("prompt_ms") or 0
        u = c.get("usage") or {}
        if u.get("completion_tokens") is not None and c.get("ms"):
            nusage += 1
            gen_u += u["completion_tokens"]
            e2e_ms += c["ms"]
    return dict(appels=len(calls), ntim=ntim, gen=gen, dec_s=dec_ms/1000.0,
                pre_n=pre_n, pre_s=pre_ms/1000.0,
                nusage=nusage, gen_u=gen_u, e2e_s=e2e_ms/1000.0)


def _debit(l):
    """(jetons, 'dec_t/s' ou '~e2e_t/s', source) du run, ou (None, None, None)."""
    if l["ntim"]:
        return l["gen"], (l["gen"]/l["dec_s"] if l["dec_s"] else 0.0), "timings"
    if l["nusage"]:
        return l["gen_u"], (l["gen_u"]/l["e2e_s"] if l["e2e_s"] else 0.0), "usage"
    return None, None, None

lignes = []
for r in res:
    rep = r.get("rep", 1)
    a = agrege(appels_de({**r, "rep": rep}))
    # Enregistrement de SECOURS (ouvrier mort avant le verdict) : pas de
    # wall_s, pas de why. Il est garde et NOMME, jamais converti en zero --
    # et il n entre dans aucune moyenne ni aucun controle chronometre.
    secours = "wall_s" not in r
    lignes.append({**r, "rep": rep, **a, "secours": secours,
                   "why": r.get("why") or ("(secours : ouvrier mort, aucun verdict)"
                                           if secours else "")})
if ambigus:
    print("!!! %d run(s) AMBIGUS : plusieurs fenetres du fil portent leur effort/tache/"
          "repetition et ni le bras ni le slot ne departagent. RIEN ne leur est "
          "attribue (appels=0, debit '-'). Exemple : %s -> %s"
          % (len(ambigus), ambigus[0][:5], ambigus[0][5]))
    print()
mesures = [l for l in lignes if not l["secours"]]
if len(mesures) < len(lignes):
    print("NOTE : %d enregistrement(s) de secours (ouvrier mort avant le verdict) : "
          "affiches, exclus des moyennes et des controles chronometres.\n"
          % (len(lignes) - len(mesures)))
nreps = len({l["rep"] for l in lignes})

ordre = ["off", "low", "medium", "high", "xhigh"]
efforts = [e for e in ordre if any(l["effort"] == e for l in lignes)]

print("=== par run ===")
print("%-3s %-6s %-5s %-4s %7s %7s %7s %6s  %s" % ("rep","effort","tache","ok","temps_s","gen_tok","dec_t/s","appels","pourquoi"))
for e in efforts:
    for l in sorted([x for x in lignes if x["effort"] == e], key=lambda x: (x["tache"], x["rep"])):
        jet, tps, src = _debit(l)
        # '-' veut dire NON MESURE. Zero voudrait dire mesure et nulle.
        # '~' veut dire bout-en-bout (usage/ms), pas decodage (timings).
        jt = ("%7d" % jet) if src else "      -"
        db = ("%7.1f" % tps) if src == "timings" else (("~%6.1f" % tps) if src else "      -")
        ws = ("%7.1f" % l["wall_s"]) if not l["secours"] else "      -"
        print("r%-2d %-6s %-5s %-4s %7s %7s %7s %6d  %s"
              % (l["rep"], e, l["tache"], l["verdict"], ws, jt, db, l["appels"], l["why"][:52]))

if any(_debit(l)[2] == "usage" for l in lignes):
    print("    ~ : debit BOUT-EN-BOUT = usage.completion_tokens / duree de l appel "
          "(prefill et reseau compris). Ce n est pas le debit de decodage des "
          "lignes sans ~ ; les deux ne se comparent pas entre eux.")
print()
iteratif = any(l.get("mode") == "iterate" for l in lignes)
print("=== synthese par niveau ===")
entete = "%-8s %-8s %9s %9s %10s %10s %9s" % ("effort","reussite","temps_med","temps_moy","gen_tok_moy","dec_t/s","appels_moy")
if iteratif:
    entete += " %8s %9s" % ("julia_moy", "sans_test")
print(entete)
synth = {}
for e in efforts:
    tous = [x for x in lignes if x["effort"] == e]
    g = [x for x in tous if not x["secours"]]
    # Reussite sur TOUS les enregistrements : un ouvrier mort est un run perdu
    # et il compte comme son FAIL. Temps et debit sur les seuls mesures.
    ok = sum(1 for x in tous if x["verdict"] == "PASS")
    avec = [x for x in g if x["ntim"]]
    src = "timings"
    if avec:
        tot_gen = sum(x["gen"] for x in avec); tot_dec = sum(x["dec_s"] for x in avec)
    else:
        # Secours : bout-en-bout depuis usage/ms, sur les runs qui le portent.
        avec = [x for x in g if x["nusage"]]
        src = "usage" if avec else None
        tot_gen = sum(x["gen_u"] for x in avec); tot_dec = sum(x["e2e_s"] for x in avec)
    s = dict(n=len(tous), ok=ok, ntim=len(avec), src=src,
             med=st.median([x["wall_s"] for x in g]) if g else float("nan"),
             moy=st.mean([x["wall_s"] for x in g]) if g else float("nan"),
             gen=(tot_gen/len(avec) if avec else None),
             tps=((tot_gen/tot_dec if tot_dec else 0) if avec else None),
             ap=st.mean([x["appels"] for x in g]) if g else float("nan"),
             jl=st.mean([x.get("julia_runs", 0) for x in g]) if g else float("nan"),
             # Un run sans mytest.jl en mode iteratif n'est pas une donnee
             # manquante : le modele a repondu DONE sans faire ce qu'on lui a
             # explicitement demande. C'est une mesure d'obeissance.
             sans=sum(1 for x in g if not x.get("a_teste", False)))
    synth[e] = s
    ligne = "%-8s %2d/%-5d %9.1f %9.1f %10s %10s %9.1f" % (
        e, ok, len(tous), s["med"], s["moy"],
        ("%.0f" % s["gen"]) if avec else "-",
        (("%.1f" if src == "timings" else "~%.1f") % s["tps"]) if avec else "-", s["ap"])
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
    if h["gen"] is None or x["gen"] is None:
        # Deux absences comparees rendent un ecart de 0 %, qui se lit
        # "identiques" -- exactement la conclusion que le temoin doit
        # rendre impossible a atteindre sans mesure.
        print("    jetons    NON MESURES (aucun appel ne porte ni timings ni usage)")
    else:
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
def _web_de(l):
    """Activite web d un run : nombre de recherches COTE BANC (`rech_faites`,
    design --web-apres-julia : le banc cherche quand Julia a echoue N fois) si
    l enregistrement en porte, sinon les appels-outil web de l agent
    (`appels_web`, design ou l agent cherche lui-meme). -1 = non mesure.
    Mesure du 23/08 : t31e (banc chercheur) affichait appels_web=0 sur les 5
    runs du bras web et le controle criait "un seul bras" -- il lisait le
    compteur de l autre design."""
    if "recherches_banc" in l:
        return l.get("rech_faites", len(l["recherches_banc"] or []))
    return l.get("appels_web", -1)


banc_cherche = any("recherches_banc" in l for l in lignes)
bras = sorted({l.get("bras_web", False) for l in lignes})
if len(bras) > 1 or any(_web_de(l) > 0 for l in lignes):
    print()
    print("=== bras web ===")
    if banc_cherche:
        print("    (recherches faites PAR LE BANC apres echec Julia ; un run du bras "
              "web sans recherche est un run qui n a pas echoue assez pour en declencher une)")
    print("%-12s %-9s %9s %10s %10s %9s" % ("bras", "reussite", "temps_moy",
                                            "gen_tok_moy",
                                            "rech_banc" if banc_cherche else "appels_web",
                                            "runs_web"))
    for b in bras:
        g = [x for x in mesures if x.get("bras_web", False) == b]
        mes = [x for x in g if _web_de(x) >= 0]
        aw = [_web_de(x) for x in mes]
        print("%-12s %2d/%-6d %9.1f %10s %10s %9s"
              % ("avec web" if b else "sans web",
                 sum(1 for x in g if x["verdict"] == "PASS"), len(g),
                 st.mean([x["wall_s"] for x in g]),
                 (lambda t: ("%.0f" % st.mean(t)) if t else "n/a")(
                     [x["gen"] for x in g if x.get("ntim")]),
                 ("%.1f" % st.mean(aw)) if aw else "n/a",
                 "%d/%d" % (sum(1 for v in aw if v > 0), len(mes)) if mes else "n/a"))

    triche = [l for l in lignes if not l.get("bras_web", False) and _web_de(l) > 0]
    # Banc chercheur : le banc ECRIT chaque refus de chercher avec sa raison
    # (seuil julia non atteint, plafond, delai). "Muet" est alors un run du
    # bras web qui a echoue, n a rien cherche ET n a aucune raison ecrite :
    # la branche n a jamais ete atteinte. Un refus motive n est pas un
    # silence.
    def _muet(l):
        if not l.get("bras_web", False) or _web_de(l) != 0:
            return False
        if "recherches_banc" not in l:
            return True
        return (l.get("verdict") != "PASS"
                and not any(r.get("raison") for r in (l["recherches_banc"] or [])))
    muet = [l for l in lignes if _muet(l)]
    if triche:
        print("!!! %d run(s) du bras SANS web ont appele un outil web : les bras "
              "ne sont pas disjoints." % len(triche))
        for l in triche[:8]:
            print("      %-6s %-5s r%d : %d appel(s)" % (l["effort"], l["tache"], l["rep"], _web_de(l)))
    if muet:
        print("!!! %d run(s) du bras AVEC web n'ont fait AUCUNE recherche alors "
              "qu'ils le pouvaient : pour ces runs il n'y a pas deux bras, il y en a un."
              % len(muet))
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
JUGE_TIMEOUT = int(os.environ.get("BENCH_JUGE_TIMEOUT", "600"))   # meme source que bench.py
impossibles = []
for l in mesures:
    somme_s = _union_s(appels_de(l))
    if somme_s > l["wall_s"] * 1.15 + 2:
        impossibles.append((l["effort"], l["tache"], l["wall_s"], somme_s))
if impossibles:
    print("!!! ATTRIBUTION FAUSSEE -- %d run(s) passent plus de temps en appels "
          "qu'ils n'ont dure." % len(impossibles))
    for e, t, w, s in impossibles:
        print("      %-6s %-5s  duree %.1f s  mais %.1f s d'appels" % (e, t, w, s))
    print("      Les debits ci-dessus sont FAUX pour ces lignes. Ne pas les citer.")
else:
    attribues = sum(1 for l in mesures if appels_de(l))
    print("controle d'horloge : %d/%d runs coherents (aucun ne passe plus de temps "
          "en appels qu'il n'a dure) -- %d/%d ont des appels attribues."
          % (len(mesures), len(mesures), attribues, len(mesures)))
    if mesures and attribues == 0:
        print("      !!! AUCUN run n a d appels attribues : ce controle n a rien "
              "regarde. Un compte egal a la population sur une liste vide n est "
              "pas une mesure.")

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
for l in mesures:
    if l.get("mode") == "boucle" and l.get("timeout_tour") and l.get("tours_max"):
        # Mode BOUCLE : chaque tour a son delai, puis un verdict Julia borne
        # par JUGE_TIMEOUT. L echeance du run est la somme. Sans cette branche
        # le controle lisait TIMEOUT (900 s, un seul tour) et denoncait
        # 7 runs sur 14 de t31e "non fermes" -- ils etaient dans leur budget.
        # Meme regle que bench.py : juge >= tour, sauf BENCH_JUGE_TIMEOUT explicite.
        juge = JUGE_TIMEOUT if "BENCH_JUGE_TIMEOUT" in os.environ else max(JUGE_TIMEOUT, l["timeout_tour"])
        echeance = l["tours_max"] * (l["timeout_tour"] + juge)
    else:
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
        # Chainage PAR SLOT : dans un fil assemble, le n=5 de l ouvrier 0
        # ne prolonge pas le n=3 de l ouvrier 1.
        s = r.get("slot")
        c = ouverts.pop((s, n - 2), None)
        if c is None:
            c = {"n0": n, "calls": []}
            convs.append(c)
        c["calls"].append(r)
        c["n1"] = n
        ouverts[(s, n)] = c
    return convs


def _fenetre_de(ts, fenetres, slot=None):
    for i, w in enumerate(fenetres):
        cle, a, b = w["cle"], w["a"], w["b"]
        if slot is not None and cle[4] is not None and cle[4] != slot:
            continue
        if a and a <= ts and (b is None or ts <= b):
            return i
    return None


print()
intrus = []
for c in _conversations(wire):
    vues = {_fenetre_de(x["t0"], fenetres, x.get("slot")) for x in c["calls"]}
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
