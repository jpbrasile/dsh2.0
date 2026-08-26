# Cable dsh ET pi sur le proxy d'injection (port 8009), en AJOUT.
#
# Rien d'existant n'est modifie : on ajoute une route `openrouter-inject` a
# cote de `openrouter`. Les runs precedents restent rejouables tels quels, et
# le bras « sans injection » reste disponible pour comparaison.
#
# POURQUOI DEUX FICHIERS DIFFERENTS. dsh lit `settings.yaml` dans son accueil
# isole ; pi lit `models.json` dans PI_CODING_AGENT_DIR. Les deux recoivent la
# MEME baseURL, donc le meme proxy, donc le meme echantillonnage -- c'est tout
# l'interet : la correction est exterieure aux deux agents et ne peut pas
# diverger entre eux.
#
# AUCUNE CLE N'ENTRE DANS UN FICHIER. dsh prend `apiKeyEnv`, pi interpole
# `"$OPENROUTER_API_KEY"` depuis l'environnement (docs/models.md:156). Le .env
# est charge par le pilote au lancement, jamais recopie.
#
# LE CHEMIN EST /api/v1 ET PAS /v1. Le proxy transmet l'URL telle quelle et
# OpenRouter sert /api/v1 : une baseURL en /v1 rend un 404 HTML qu'on prend
# pour un refus de champ (mesure du 26/08).

import io
import json
import os

ACCUEIL_DSH = os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2")
ACCUEIL_PI = os.path.join(os.path.expanduser("~"), ".pi-bench-polyglot")
BASE = "http://127.0.0.1:8009/api/v1"
MODELE = "qwen/qwen3.8-27b"
NOM = "openrouter-inject"

ROUTE_DSH = """    %s:
      name: OpenRouter via proxy d'injection (8009)
      apiKeyEnv: OPENROUTER_API_KEY
      api: openai-completions
      baseURL: %s
      defaultContextWindow: 65536
      models:
        - id: %s
          name: Qwen3.8-27B (echantillonnage injecte)
          contextWindow: 65536
          maxTokens: 16384
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
""" % (NOM, BASE, MODELE)


def cabler_pi():
    if not os.path.isdir(ACCUEIL_PI):
        os.makedirs(ACCUEIL_PI)
    chemin = os.path.join(ACCUEIL_PI, "models.json")
    conf = {"providers": {NOM: {
        "baseUrl": BASE,
        "api": "openai-completions",
        # Interpolation d'environnement : la valeur n'est jamais dans le fichier.
        "apiKey": "$OPENROUTER_API_KEY",
        "authHeader": True,
        "models": [{"id": MODELE, "name": "Qwen3.8-27B (injecte)",
                    "reasoning": True, "contextWindow": 65536,
                    "maxTokens": 16384}]}}}
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        json.dumps(conf, indent=2) + "\n")
    print("pi  : %s" % chemin)


def cabler_dsh():
    chemin = os.path.join(ACCUEIL_DSH, "settings.yaml")
    if not os.path.exists(chemin):
        raise SystemExit("REFUS : %s introuvable." % chemin)
    texte = io.open(chemin, encoding="utf-8", errors="replace").read()
    if "\n    %s:\n" % NOM in texte:
        print("dsh : route `%s` deja presente, rien touche." % NOM)
        return
    ancre = "\n  providers:\n"
    if ancre not in texte:
        raise SystemExit("REFUS : ancre `  providers:` introuvable ; ne pas "
                         "inserer a l'aveugle dans %s." % chemin)
    # Sauvegarde AVANT ecriture : ce fichier est celui du banc, pas une copie.
    sauve = chemin + ".avant-injection"
    if not os.path.exists(sauve):
        io.open(sauve, "w", encoding="utf-8", newline="\n").write(texte)
        print("dsh : sauvegarde -> %s" % sauve)
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        texte.replace(ancre, ancre + ROUTE_DSH, 1))
    print("dsh : route `%s` ajoutee dans %s" % (NOM, chemin))


if __name__ == "__main__":
    cabler_pi()
    cabler_dsh()
    print()
    print("Lancer le proxy AVANT tout run :")
    print("  cd scripts/bench_julia_effort")
    print("  PROXY_PORT=8009 UP_TLS=1 UP_HOST=openrouter.ai UP_PORT=443 \\")
    print("    PROXY_LOG=./wire_polyglot.jsonl \\")
    print("    PROXY_INJECT='{\"temperature\":1.0,\"top_p\":0.95,"
          "\"top_k\":20,\"min_p\":0}' node proxy.mjs")
    print()
    print("Puis : pilote.py <run> --fournisseur %s --modele %s" % (NOM, MODELE))
    print("       (pour pi, ajouter --accueil-pi %s)" % ACCUEIL_PI)
