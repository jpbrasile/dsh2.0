# Route pi vers le serveur LOCAL a travers l'enregistreur, comme dsh.
#
# LE BRAS QUI MANQUE. Question posee le 26/08 au soir : « connait-on maintenant
# un reglage dsh aussi performant que pi ? ». On ne peut pas y repondre. Les
# quatre tirages locaux de dsh (269 a 547 s) encadrent les 282,5 s de pi, mais
# ces 282,5 s ont ete mesures CHEZ AKASHML, a 33 jetons/s de decode, contre 43,5
# en local. Mettre les deux dans la meme phrase compare un dsh local a un pi
# distant.
#
# `local-8005` existe deja cote pi (pose par cabler_local.py) mais parle au
# serveur EN DIRECT : aucun fil, donc ni pensee, ni cache, ni raison d'arret --
# c'est-a-dire aucune des grandeurs qui ont servi a diagnostiquer dsh. Cette
# route-ci passe par 8013, le meme enregistreur, avec le meme plafond de sortie
# de 16 384 que tous les bras de la soiree.
#
# PLAFOND 16 384, ET C'EST UNE CONTRAINTE, PAS UN DETAIL. Un tirage de dsh sur
# trois meurt dessus (`finish_reason: length`, sortie a 16 384 pile). Donner a pi
# un plafond plus haut lui epargnerait un mode d'echec que dsh subit, et le bras
# ne mesurerait plus le meme jeu.
#
# FUSION, PAS REECRITURE. Meme regle que cabler_local.py : `models.json` est
# relu et complete. `cabler_proxy_injection.py` ecrasait, et c'est pour ca que pi
# s'etait retrouve sans route locale.
#
#     python cabler_pi_mesure.py [--port-proxy 8013] [--port-serveur 8005]

import argparse
import io
import json
import os
import urllib.request

ACCUEIL_PI = os.path.join(os.path.expanduser("~"), ".pi-bench-polyglot")
NOM = "local-mesure"
CTX = 163840
MAX_SORTIE = 16384


def alias_vivant(port):
    url = "http://127.0.0.1:%d/v1/models" % port
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        raise SystemExit("REFUS : %s injoignable (%s)." % (url, e))
    ids = [m.get("id") or m.get("model")
           for m in (d.get("data") or d.get("models") or [])]
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

    chemin = os.path.join(ACCUEIL_PI, "models.json")
    if not os.path.exists(chemin):
        raise SystemExit("REFUS : %s introuvable ; jouer cabler_local.py d'abord."
                         % chemin)
    try:
        conf = json.load(io.open(chemin, encoding="utf-8", errors="replace"))
    except ValueError:
        raise SystemExit("REFUS : %s illisible ; ne pas ecraser un fichier qu'on "
                         "ne sait pas relire." % chemin)
    conf.setdefault("providers", {})
    conf["providers"][NOM] = {
        "baseUrl": "http://127.0.0.1:%d/v1" % args.port_proxy,
        "api": "openai-completions",
        "apiKey": "$DSH_LOCAL_API_KEY",
        "authHeader": True,
        "models": [{"id": alias,
                    "name": "Qwen3.8-27B local via enregistreur",
                    "reasoning": True,
                    "contextWindow": CTX,
                    "maxTokens": MAX_SORTIE}]}
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conf, indent=2) + "\n")
    print("pi : route `%s` -> 127.0.0.1:%d (modele %s, plafond %d)"
          % (NOM, args.port_proxy, alias, MAX_SORTIE))
    print("     routes presentes : %s" % ", ".join(sorted(conf["providers"])))


main()
