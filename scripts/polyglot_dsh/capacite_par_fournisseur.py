# CE FOURNISSEUR TIENT-IL UNE INVITE DE dsh ? -- verification gratuite.
#
# POURQUOI CE SCRIPT AVANT L'ESSAI. La sonde de debit du 26/08 classe Venice
# premier, 94,0 jetons/s contre 33,9 chez AkashML. Mais elle l'a mesure sur une
# invite de trois lignes. dsh, lui, envoie jusqu'a 29 000 jetons de contexte :
# un fournisseur peut etre le plus rapide du catalogue ET refuser la requete.
# L'essai coute ~0,50 $ sur 11,26 $ de credit ; le verifier coute zero.
#
# CE QU'IL LIT, ET OU. `/models/<id>/endpoints` d'OpenRouter -- metadonnee
# declaree par le fournisseur, aucune generation, aucun jeton facture. C'est
# donc une DECLARATION, pas une mesure : un fournisseur qui annonce 262 144 et
# coupe a 40 000 ne serait demasque que par un appel reel. Le script sert a
# ECARTER ceux qui s'annoncent trop courts, pas a certifier les autres.
#
# LE SEUIL. 29 632 jetons de sortie mesures sur `go/beer-song` chez dsh, et une
# invite finale du meme ordre. On demande 40 000 de marge : sous ce chiffre, le
# fournisseur est declare hors-jeu pour un exercice agentique dsh.
#
#     python capacite_par_fournisseur.py [--modele qwen/qwen3.8-27b] [--seuil 40000]

import argparse
import io
import json
import os
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def charger_env(chemin):
    if not os.path.exists(chemin):
        return
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        k, v = ligne.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modele", default="qwen/qwen3.8-27b")
    p.add_argument("--seuil", type=int, default=40000)
    args = p.parse_args()

    charger_env(os.path.join(RACINE, ".env"))
    cle = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")
    if not cle:
        raise SystemExit("REFUS : OPENROUTER_API_KEY absent de l'environnement.")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models/%s/endpoints" % args.modele,
        headers={"Authorization": "Bearer %s" % cle})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    pts = ((d.get("data") or {}).get("endpoints") or [])

    print("modele %s   %d fournisseurs   seuil %d jetons de contexte"
          % (args.modele, len(pts), args.seuil))
    print()
    print("  %-14s %-8s %-9s %-9s %-11s %-11s %s"
          % ("fournisseur", "quantif", "contexte", "max sortie", "$/M entree",
             "$/M sortie", "cache"))
    lignes = []
    for e in sorted(pts, key=lambda x: -(x.get("context_length") or 0)):
        nom = e.get("provider_name") or "?"
        ctx = e.get("context_length") or 0
        mx = e.get("max_completion_tokens") or 0
        pr = e.get("pricing") or {}
        pe = float(pr.get("prompt") or 0) * 1e6
        ps = float(pr.get("completion") or 0) * 1e6
        # Un prix de lecture de cache DECLARE est le seul indice, dans cette
        # metadonnee, qu'un fournisseur cache. Son absence ne prouve pas qu'il
        # ne cache pas -- elle dit qu'il ne le facture pas separement.
        cache = "oui" if pr.get("input_cache_read") else "-"
        verdict = "" if ctx >= args.seuil else "   <-- TROP COURT"
        print("  %-14s %-8s %-9d %-9s %-11.3f %-11.3f %s%s"
              % (nom[:14], (e.get("quantization") or "-")[:8], ctx,
                 (mx or "-"), pe, ps, cache, verdict))
        lignes.append((nom, ctx, ps, cache))

    print()
    ok = [l for l in lignes if l[1] >= args.seuil]
    print("  %d / %d tiennent %d jetons de contexte." % (len(ok), len(lignes), args.seuil))
    for nom in ("Venice", "AkashML"):
        m = [l for l in lignes if l[0] == nom]
        if m:
            n, ctx, ps, cache = m[0]
            print("  %-9s : contexte %d, sortie %.3f $/M, cache %s%s"
                  % (n, ctx, ps, cache,
                     "" if ctx >= args.seuil else "  -- HORS-JEU pour dsh"))


main()
