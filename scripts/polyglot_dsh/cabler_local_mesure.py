# Route dsh vers le llama-server LOCAL **a travers l'enregistreur**, au meme
# plafond de sortie que les bras OpenRouter.
#
# POURQUOI PAS `local-8005` TEL QUEL. Cette route parle au serveur en direct :
# aucun fil, donc aucun appel mesure, aucun compte de pensee, aucun debit de
# decode. Or c'est exactement ce qu'on veut comparer aux bras AkashML et
# Venice. Un run local non journalise ne donnerait qu'une paroi -- le chiffre
# le plus fragile des trois, puisqu'il depend de ce qui tourne sur la machine.
#
# ET POURQUOI 16 384 ET PAS 32 768. `local-8005` declare 32 768 jetons de
# sortie ; les deux bras OpenRouter ont tourne a 16 384. Le plafond n'est pas
# un detail de confort : le bras Venice vient de mourir dessus au 8e appel.
# Comparer un bras qui peut ecrire deux fois plus long a un bras qui ne le peut
# pas, c'est comparer deux regles differentes. On aligne sur la plus stricte,
# celle des mesures deja publiees.
#
# CE QUI N'EST PAS TOUCHE. `local-8005` reste en place, intacte, pour les
# usages qui ne demandent pas de fil. Ce script ajoute une route et n'en
# modifie aucune ; rejoue, il ne duplique pas.
#
#     python cabler_local_mesure.py [--port-proxy 8013] [--port-serveur 8005]

import argparse
import io
import json
import os
import urllib.request

ACCUEIL_DSH = os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2")
NOM = "local-mesure"
CTX = 163840
MAX_SORTIE = 16384


def alias_vivant(port):
    """L'identifiant annonce par le serveur LUI-MEME. Refus s'il ne repond pas.

    Meme regle que `cabler_local.py` : une constante recopiee redevient fausse
    au premier redemarrage dans une autre configuration.
    """
    url = "http://127.0.0.1:%d/v1/models" % port
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        raise SystemExit("REFUS : %s injoignable (%s)." % (url, e))
    ids = [m.get("id") or m.get("model") for m in (d.get("data") or d.get("models") or [])]
    ids = [i for i in ids if i]
    if len(ids) != 1:
        raise SystemExit("REFUS : %d modeles annonces (%s)." % (len(ids), ids))
    return ids[0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port-proxy", type=int, default=8013)
    p.add_argument("--port-serveur", type=int, default=8005)
    args = p.parse_args()

    alias = alias_vivant(args.port_serveur)
    print("alias lu sur le serveur vivant : %s" % alias)

    chemin = os.path.join(ACCUEIL_DSH, "settings.yaml")
    texte = io.open(chemin, encoding="utf-8", errors="replace").read()
    if "\n    %s:\n" % NOM in texte:
        print("dsh : route `%s` deja presente, rien a faire." % NOM)
        print("      VERIFIER l'alias a la main : ce script n'ecrase pas une")
        print("      route existante, donc un alias devenu faux le reste.")
    else:
        route = ("""    %s:
      name: Qwen3.8-27B local via enregistreur (%d -> %d)
      apiKeyEnv: DSH_LOCAL_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:%d/v1
      defaultContextWindow: %d
      models:
        - id: %s
          name: Qwen3.8-27B local (mesure)
          contextWindow: %d
          maxTokens: %d
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
""" % (NOM, args.port_proxy, args.port_serveur, args.port_proxy, CTX,
            alias, CTX, MAX_SORTIE))
        ancre = "\n  providers:\n"
        if ancre not in texte:
            raise SystemExit("REFUS : ancre `  providers:` introuvable.")
        sauve = chemin + ".avant-local-mesure"
        if not os.path.exists(sauve):
            io.open(sauve, "w", encoding="utf-8", newline="\n").write(texte)
            print("dsh : sauvegarde -> %s" % sauve)
        io.open(chemin, "w", encoding="utf-8", newline="\n").write(
            texte.replace(ancre, ancre + route, 1))
        print("dsh : route `%s` ajoutee (modele %s, plafond sortie %d)"
              % (NOM, alias, MAX_SORTIE))

    print()
    print("alias a passer au pilote : %s" % alias)


main()
