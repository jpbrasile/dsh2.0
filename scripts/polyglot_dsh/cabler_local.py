# Cable dsh ET pi sur le llama-server LOCAL, en lisant l'alias sur le serveur.
#
# POURQUOI CE SCRIPT EXISTE. Le 26/08 au soir, avant de lancer le polyglot
# complet en local, j'ai regarde les deux configurations :
#   dsh : route `local-think` -> http://127.0.0.1:8006, modele
#         `specdec-q38-dflash2`. Le port 8006 N'ECOUTE PAS (le serveur est sur
#         8005) et l'alias vivant est `specdec-q38-plain`. Route morte.
#   pi  : AUCUNE route locale. `cabler_proxy_injection.py` REECRIT models.json
#         au lieu de le completer, donc toute route locale y disparait.
# Les deux auraient echoue au pre-vol, c'est-a-dire au milieu de la nuit.
#
# CE QUI EST LU, PLUTOT QUE SUPPOSE. L'alias vient de `/v1/models` du serveur
# vivant, jamais d'une constante. C'est la meme regle que pour le lanceur du
# bras de production : l'alias change avec la configuration (`q38-plain` contre
# `q38-dflash2`), et une constante recopiee redevient fausse au premier
# redemarrage -- exactement le defaut qu'on repare ici.
#
# CE QUI N'EST PAS TOUCHE. Les autres routes, des deux cotes. Cote pi le
# fichier est FUSIONNE, pas reecrit ; cote dsh la route est ajoutee apres une
# sauvegarde, et le script refuse si l'ancre `providers:` manque plutot que
# d'inserer a l'aveugle. Aucune cle n'entre dans un fichier : dsh prend
# `apiKeyEnv`, pi interpole depuis l'environnement.
#
# LA CLE N'EST PAS UN SECRET ICI, ET C'EST QUAND MEME LA MEME REGLE.
# llama-server accepte n'importe quel jeton, mais les deux agents en exigent un.
# On declare donc une variable d'environnement, pas une valeur -- si demain le
# serveur en demande une vraie, rien a changer.
#
#     python cabler_local.py [--port 8005]

import argparse
import io
import json
import os
import urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACCUEIL_DSH = os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2")
ACCUEIL_PI = os.path.join(os.path.expanduser("~"), ".pi-bench-polyglot")
NOM = "local-8005"
CTX = 163840
MAX_SORTIE = 32768


def alias_vivant(port):
    """L'identifiant que le serveur annonce LUI-MEME. Refus s'il ne repond pas.

    Un cablage ecrit contre un serveur eteint est un cablage ecrit contre une
    supposition : c'est precisement ce qui a produit la route morte vers 8006.
    """
    url = "http://127.0.0.1:%d/v1/models" % port
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        raise SystemExit("REFUS : %s injoignable (%s).\n"
                         "  Demarrer llama-server avant de cabler : l'alias se "
                         "lit sur le serveur, il ne se devine pas." % (url, e))
    ids = [m.get("id") for m in (d.get("data") or []) if m.get("id")]
    if len(ids) != 1:
        raise SystemExit("REFUS : %d modeles annonces (%s) ; on ne choisit pas "
                         "a la place de l'operateur." % (len(ids), ids))
    return ids[0]


def cabler_pi(alias, port):
    chemin = os.path.join(ACCUEIL_PI, "models.json")
    conf = {"providers": {}}
    if os.path.exists(chemin):
        # FUSION, pas reecriture : c'est la difference avec
        # cabler_proxy_injection.py, et c'est pour ca que pi n'avait pas de
        # route locale.
        try:
            conf = json.load(io.open(chemin, encoding="utf-8", errors="replace"))
        except ValueError:
            raise SystemExit("REFUS : %s illisible ; ne pas ecraser un fichier "
                             "qu'on ne sait pas relire." % chemin)
        conf.setdefault("providers", {})
    else:
        os.makedirs(ACCUEIL_PI, exist_ok=True)
    conf["providers"][NOM] = {
        "baseUrl": "http://127.0.0.1:%d/v1" % port,
        "api": "openai-completions",
        "apiKey": "$DSH_LOCAL_API_KEY",
        "authHeader": True,
        "models": [{"id": alias, "name": "Qwen3.8-27B local (%s)" % alias,
                    "reasoning": True, "contextWindow": CTX,
                    "maxTokens": MAX_SORTIE}]}
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conf, indent=2) + "\n")
    print("pi  : route `%s` -> %s (modele %s)" % (NOM, chemin, alias))
    print("      routes presentes : %s" % ", ".join(sorted(conf["providers"])))


def cabler_dsh(alias, port):
    chemin = os.path.join(ACCUEIL_DSH, "settings.yaml")
    if not os.path.exists(chemin):
        raise SystemExit("REFUS : %s introuvable." % chemin)
    texte = io.open(chemin, encoding="utf-8", errors="replace").read()
    route = ("""    %s:
      name: Qwen3.8-27B local (%s)
      apiKeyEnv: DSH_LOCAL_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:%d/v1
      defaultContextWindow: %d
      models:
        - id: %s
          name: Qwen3.8-27B local
          contextWindow: %d
          maxTokens: %d
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
""" % (NOM, alias, port, CTX, alias, CTX, MAX_SORTIE))
    if "\n    %s:\n" % NOM in texte:
        print("dsh : route `%s` deja presente." % NOM)
        print("      VERIFIER l'alias a la main : ce script n'ecrase pas une")
        print("      route existante, donc un alias devenu faux le reste.")
        return
    ancre = "\n  providers:\n"
    if ancre not in texte:
        raise SystemExit("REFUS : ancre `  providers:` introuvable ; ne pas "
                         "inserer a l'aveugle dans %s." % chemin)
    sauve = chemin + ".avant-local"
    if not os.path.exists(sauve):
        io.open(sauve, "w", encoding="utf-8", newline="\n").write(texte)
        print("dsh : sauvegarde -> %s" % sauve)
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        texte.replace(ancre, ancre + route, 1))
    print("dsh : route `%s` ajoutee dans %s (modele %s)" % (NOM, chemin, alias))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8005)
    args = p.parse_args()
    alias = alias_vivant(args.port)
    print("alias lu sur le serveur vivant : %s" % alias)
    print()
    cabler_pi(alias, args.port)
    cabler_dsh(alias, args.port)
    print()
    print("Poser la variable AVANT de lancer (llama-server accepte n'importe")
    print("quelle valeur, les deux agents en exigent une) :")
    print("  $env:DSH_LOCAL_API_KEY = 'local'")
    print()
    print("Puis, pour un run local :")
    print("  pilote.py <run> --fournisseur %s --modele %s" % (NOM, alias))
    print("  (pour pi, ajouter --accueil-pi %s)" % ACCUEIL_PI)
    print()
    print("L'alias est fige dans les deux fichiers AU MOMENT DE CE CABLAGE.")
    print("Tout redemarrage du serveur dans une autre configuration le rend")
    print("faux : rejouer ce script apres chaque changement de -Config.")


main()
