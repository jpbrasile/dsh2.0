# QUEL FOURNISSEUR DECODE VITE ? -- la moitie de la question qu'on n'a pas posee.
#
# CE QUI A ETE MESURE, ET CE QUI NE L'A PAS ETE. Le 26/08, l'ajustement
# prefill/decode sur 29 appels de dsh donne 33,0 jetons/s en decode et attribue
# 65 % de la paroi a cette pente. Mais les 29 appels sont partis chez le MEME
# fournisseur, AkashML, sans epinglage. 33 t/s peut donc etre une propriete
# d'AkashML et pas du modele -- d'autant qu'au catalogue AkashML est le seul
# bf16 de la liste, les neuf autres servant en fp8.
#
# On avait ecarte le routage en montrant qu'un cache parfait ne rendrait que
# 1,39x. Cet argument porte sur le CACHE seul ; il ne dit rien du DEBIT, qui
# est justement la part dominante. L'ecarter sur cette base etait une erreur de
# portee.
#
# CE QUE CE SCRIPT MESURE. Pour chaque fournisseur, UN appel de generation a
# longueur imposee, epingle sans repli. Il rend les jetons/s vus au fil et le
# fournisseur REELLEMENT servi -- epingler dans la requete ne prouve rien, la
# reponse prouve. Un fournisseur qui repond sous un autre nom est ecarte.
#
# POURQUOI PAS UN EXERCICE COMPLET PAR FOURNISSEUR. 0,47 $ l'exercice chez dsh,
# 10 fournisseurs, sur 11,28 $ de credit : ce serait depenser la moitie du
# budget pour une question qu'un appel a quelques centimes tranche. On sonde
# large et pas cher, puis on joue UN exercice complet sur le gagnant.
#
# CE QUE CE SCRIPT NE PEUT PAS DIRE. Un appel par fournisseur ne donne aucun
# intervalle : la charge varie d'une minute a l'autre, et un ecart de 10 % ici
# ne veut rien dire. Ce qui est lisible, c'est un facteur -- 30 contre 90 t/s.
# Le prefill n'est pas separe non plus : l'invite est courte expres pour que le
# temps soit du decode, mais la latence d'etablissement reste dedans, ce qui
# SOUS-estime le debit d'autant plus que la reponse est courte.
#
#     python debit_par_fournisseur.py [--jetons 600] [--modele qwen/qwen3.8-27b]

import argparse
import io
import json
import os
import time
import urllib.error
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Une consigne qui force une generation longue et reguliere, sans faire penser
# le modele : on mesure un debit, pas un raisonnement. `reasoning_effort` est
# volontairement absent -- une pensee de longueur variable rendrait les
# fournisseurs incomparables entre eux.
CONSIGNE = ("Ecris la suite des entiers de 1 a 400, separes par des virgules, "
            "sans aucun autre texte. Ne t'arrete pas avant 400.")


def charger_env(chemin):
    if not os.path.exists(chemin):
        return
    for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        k, v = ligne.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def catalogue(modele, cle):
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models/%s/endpoints" % modele,
        headers={"Authorization": "Bearer %s" % cle} if cle else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return [(p.get("provider_name"), p.get("quantization") or "-")
            for p in ((d.get("data") or {}).get("endpoints") or [])
            if p.get("provider_name")]


def sonder(modele, nom, cle, jetons):
    corps = {
        "model": modele,
        "messages": [{"role": "user", "content": CONSIGNE}],
        "max_tokens": jetons,
        "temperature": 0.0,
        # allow_fallbacks False : sans ca, un fournisseur sature est remplace
        # en silence et on attribue son debit a quelqu'un d'autre.
        "provider": {"order": [nom], "allow_fallbacks": False},
        "usage": {"include": True},
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(corps).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % cle,
                 "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"erreur": "HTTP %s" % e.code}
    except Exception as e:
        return {"erreur": str(e)[:60]}
    dt = time.time() - t0
    u = d.get("usage") or {}
    servi = d.get("provider") or "?"
    sortie = u.get("completion_tokens") or 0
    return {"servi": servi, "sortie": sortie, "s": dt,
            "ts": sortie / dt if dt > 0 else 0,
            "cout": u.get("cost") or 0,
            "entree": u.get("prompt_tokens") or 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modele", default="qwen/qwen3.8-27b")
    p.add_argument("--jetons", type=int, default=600)
    args = p.parse_args()

    charger_env(os.path.join(RACINE, ".env"))
    cle = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_KEY")
    if not cle:
        raise SystemExit("REFUS : OPENROUTER_API_KEY absent de l'environnement.")

    pts = catalogue(args.modele, cle)
    print("modele %s   %d fournisseurs   plafond %d jetons"
          % (args.modele, len(pts), args.jetons))
    print()
    print("  %-14s %-8s %-8s %-8s %-9s %-9s %s"
          % ("demande", "quantif", "sortie", "sec", "jetons/s", "cout $", "servi"))
    lignes = []
    cout = 0.0
    for nom, quant in sorted(pts):
        r = sonder(args.modele, nom, cle, args.jetons)
        if r.get("erreur"):
            print("  %-14s %-8s %s" % (nom[:14], quant[:8], r["erreur"]))
            continue
        cout += r["cout"]
        # Epingler n'est pas etre servi : on ecarte plutot que de renommer.
        marque = "" if r["servi"] == nom else "   <-- SERVI PAR UN AUTRE, ecarte"
        print("  %-14s %-8s %-8d %-8.1f %-9.1f %-9.5f %s%s"
              % (nom[:14], quant[:8], r["sortie"], r["s"], r["ts"], r["cout"],
                 r["servi"], marque))
        if not marque:
            lignes.append((r["ts"], nom, quant, r["cout"]))

    print()
    print("  cout total de la sonde : %.4f $" % cout)
    if not lignes:
        print("  aucun fournisseur n'a repondu sous son propre nom.")
        return
    lignes.sort(reverse=True)
    print()
    print("CLASSEMENT (un seul appel chacun -- lire les FACTEURS, pas les %)")
    for ts, nom, quant, c in lignes:
        print("  %-14s %-8s %6.1f jetons/s   %.5f $" % (nom, quant, ts, c))
    meilleur = lignes[0]
    ref = [l for l in lignes if l[1] == "AkashML"]
    if ref:
        print()
        print("  AkashML (celui qui a servi TOUS les appels de dsh) : %.1f jetons/s"
              % ref[0][0])
        print("  Le plus rapide, %s : %.1f jetons/s, soit %.2fx."
              % (meilleur[1], meilleur[0], meilleur[0] / ref[0][0] if ref[0][0] else 0))
        print()
        print("  Rappel de portee : le decode pese 65 %% de la paroi de dsh.")
        print("  Un facteur ici se transmet presque entierement a cette part.")


main()
