# OU LE CACHE DE PREFIXE MEURT-IL ? -- la question qui porte le rapport 7.
#
# CE QU'ON CHERCHE. Sur les memes exercices, pi paie 78 % de ses jetons d'entree
# en cache et dsh 25 %. Un appel non cache re-prefille ~29 000 jetons (29,4 s)
# la ou un appel cache en re-prefille ~2 000 (11,3 s). Ce n'est pas une question
# de vitesse du modele : c'est le prefixe qui casse entre deux appels
# consecutifs, et le cache amont repart de l'octet ou il a diverge.
#
# COMMENT ON LE MESURE SANS LIRE LE CONTENU. Le proxy pose, pour chaque appel,
# `prefix_h` : une empreinte FNV-1a CUMULEE, amorcee sur la liste d'outils puis
# etendue message par message. Deux appels consecutifs partagent donc leur
# prefixe exactement jusqu'au dernier indice ou leurs empreintes coincident.
# Le premier indice qui differe EST l'endroit ou le cache meurt -- et l'indice 0
# a un sens special : il porte les outils, donc une divergence des l'indice 0
# veut dire que la liste d'outils a bouge et qu'AUCUN octet n'est reutilisable.
#
# Rien de tout cela ne lit un contenu : seulement des longueurs, des roles et
# des empreintes. C'est deliberé -- le journal du fil ne doit jamais devenir une
# copie des prompts.
#
# CE QUE LE RESULTAT PERMET DE DIRE, ET PAS PLUS. On mesure ce que le CLIENT
# envoie. Un amont peut par ailleurs refuser de cacher (fenetre trop courte,
# fournisseur qui ne cache pas, requete trop petite) : un prefixe stable ne
# garantit donc pas un cache chaud. L'implication ne tient que dans un sens --
# un prefixe QUI CASSE rend le cache impossible. C'est la moitie qui nous
# interesse, parce que c'est celle qu'on peut corriger.
#
#     python ou_casse_le_prefixe.py <wire.jsonl> [--par-modele]

import argparse
import io
import json
from collections import defaultdict


def lire(chemin):
    appels = []
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        if d.get("kind") != "call":
            continue
        s = d.get("sent") or {}
        if not isinstance(s.get("prefix_h"), list):
            continue
        appels.append(d)
    return appels


def divergence(a, b):
    """Premier indice ou deux chaines d'empreintes cessent de coincider.

    Rend (indice, n_commun, n_a, n_b). L'indice 0 signifie que les OUTILS
    different : rien n'est reutilisable, pas meme le prompt systeme.
    """
    ha = (a.get("sent") or {}).get("prefix_h") or []
    hb = (b.get("sent") or {}).get("prefix_h") or []
    k = 0
    while k < min(len(ha), len(hb)) and ha[k] == hb[k]:
        k += 1
    return k, k, len(ha), len(hb)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("journal")
    p.add_argument("--un-seul-fil", action="store_true",
                   help="ne PAS separer par famille d'outils (deconseille)")
    args = p.parse_args()

    appels = lire(args.journal)
    if not appels:
        raise SystemExit("aucun appel avec prefix_h dans %s\n"
                         "  (le proxy est-il en service, et un run est-il "
                         "passe par lui ?)" % args.journal)

    appels.sort(key=lambda d: d.get("t0") or 0)

    # SEPARER LES FILS AVANT DE COMPARER, sinon la mesure est un artefact.
    # Le journal du proxy melange plusieurs conversations : l'agent, qui porte
    # 25 outils, et des appels auxiliaires qui n'en portent aucun (61, 169,
    # 176 jetons d'entree -- mesure du 26/08). Comparer un appel de l'agent au
    # petit appel auxiliaire qui le precede donnerait « prefixe rompu des
    # l'indice 0 » a chaque transition, et accuserait le harnais d'un defaut
    # qui n'est que l'entrelacement de deux fils.
    #
    # prefix_h[0] EST l'empreinte de la liste d'outils : c'est donc deja le bon
    # discriminant, sans rien ajouter au proxy. Deux appels qui partagent leur
    # graine partagent leur famille de harnais.
    fils = defaultdict(list)
    for d in appels:
        ph = (d.get("sent") or {}).get("prefix_h") or []
        cle = "tous" if args.un_seul_fil else ("outils:" + (ph[0] if ph else "?"))
        fils[cle].append(d)

    for cle, suite in sorted(fils.items()):
        print("=" * 74)
        print("fil : %s   %d appels" % (cle, len(suite)))
        s0 = suite[0].get("sent") or {}
        print("  outils offerts au premier appel : %d  %s"
              % (len(s0.get("tools") or []),
                 ",".join((s0.get("tools") or [])[:8])))
        print()

        # Un tableau par transition : c'est la transition qui coute, pas
        # l'appel. N appels donnent N-1 transitions.
        print("  %-4s %-6s %-9s %-9s %-11s %-9s %s"
              % ("#", "msgs", "prefixe", "reutilise", "jetee", "outils", "role au point de rupture"))
        n_tools_change, n_racine, total_jete, total_garde = 0, 0, 0, 0
        for i in range(1, len(suite)):
            a, b = suite[i - 1], suite[i]
            k, _, na, nb = divergence(a, b)
            sb = b.get("sent") or {}
            roles = sb.get("roles") or []
            chars = sb.get("msg_chars") or []
            # prefix_h[0] = outils ; prefix_h[j+1] = apres le message j.
            # Un point de rupture a l'indice k concerne donc le message k-1.
            j = k - 1
            role = roles[j] if 0 <= j < len(roles) else ("OUTILS" if k == 0 else "-")
            garde = sum(chars[:max(0, j)]) if chars else 0
            jete = sum(chars[max(0, j):]) if chars else 0
            total_garde += garde
            total_jete += jete
            if k == 0:
                n_tools_change += 1
            elif k == 1:
                n_racine += 1
            print("  %-4d %-6d %-9d %-9d %-11d %-9s %s"
                  % (i, len(roles), k, garde, jete,
                     len(sb.get("tools") or []), role))

        n_tr = len(suite) - 1
        if n_tr <= 0:
            print("  (un seul appel : aucune transition a mesurer)")
            continue
        print()
        print("  transitions                     : %d" % n_tr)
        print("  dont la LISTE D'OUTILS change   : %d  (%.0f %%) -- prefixe nul"
              % (n_tools_change, 100.0 * n_tools_change / n_tr))
        print("  dont rupture des le 1er message : %d  (%.0f %%) -- systeme instable"
              % (n_racine, 100.0 * n_racine / n_tr))
        tot = total_garde + total_jete
        if tot:
            print("  caracteres d'entree reutilisables : %d / %d = %.1f %%"
                  % (total_garde, tot, 100.0 * total_garde / tot))
        print()
        print("  Lecture : « prefixe » = nombre d'empreintes communes avec")
        print("  l'appel precedent ; 0 = meme les outils ont change. « jetee » =")
        print("  caracteres qu'aucun cache ne peut reutiliser sur cet appel.")

        # Ce que l'amont a REELLEMENT cache, quand il le dit -- a confronter au
        # calcul ci-dessus. Les deux ne coincident pas forcement, et c'est
        # justement l'ecart qui dit si le probleme est chez nous ou en face.
        vus, caches, entrees = 0, 0, 0
        for d in suite:
            u = d.get("usage") or {}
            det = u.get("prompt_tokens_details") or {}
            c = det.get("cached_tokens")
            if c is None:
                c = u.get("cache_read_input_tokens")
            if c is None or not u.get("prompt_tokens"):
                continue
            vus += 1
            caches += c
            entrees += u["prompt_tokens"]
        if vus:
            print()
            print("  ce que l'AMONT declare avoir cache : %d / %d jetons = %.1f %%"
                  " (sur %d appels qui le disent)"
                  % (caches, entrees, 100.0 * caches / entrees, vus))
        else:
            print()
            print("  l'amont n'a declare aucun compte de cache sur ces appels.")


main()
