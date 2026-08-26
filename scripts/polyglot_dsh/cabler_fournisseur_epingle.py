# Cable dsh sur UN fournisseur OpenRouter EPINGLE, via un proxy dedie.
#
# POURQUOI UN PROXY DE PLUS, ET PAS CELUI DE 8009. Le 26/08, l'ajustement
# prefill/decode attribue 65 % de la paroi de dsh au decode, a 33,0 jetons/s.
# La sonde de debit montre ensuite que 33,9 t/s est le debit d'AkashML -- qui a
# servi 29 appels sur 29 sans qu'on l'ait choisi -- et que Venice rend 94,0.
# Pour le verifier sur un exercice reel il faut EPINGLER, et dsh n'a aucune voie
# de configuration pour le champ `provider` : la correction doit etre exterieure
# a l'agent. C'est exactement ce que fait `PROXY_INJECT`.
#
# Le proxy 8009 tourne DEJA et journalise le bras a outils reduits, en vol.
# L'arreter pour lui poser une injection tuerait cette mesure. On en pose donc
# un second, sur son propre port et son propre journal.
#
# EPINGLER N'EST PAS ETRE SERVI. `allow_fallbacks: false` empeche le
# remplacement silencieux, mais la seule preuve reste le champ `fournisseur` du
# journal, ecrit d'apres la REPONSE. Le depouillement doit le lire et refuser
# le run si un autre nom apparait -- sinon on publierait le debit de Venice
# sous le nom d'un autre, ou l'inverse.
#
# CE QUE CE CABLAGE NE CHANGE PAS. La route existante `openrouter-inject` et
# toutes les autres. Le fichier est sauvegarde avant ecriture, le script refuse
# si l'ancre manque plutot que d'inserer a l'aveugle, et il est idempotent :
# rejoue, il ne duplique pas la route. Aucune cle n'entre dans le fichier --
# `apiKeyEnv` nomme une variable d'environnement.
#
#     python cabler_fournisseur_epingle.py --fournisseur Venice --port 8012

import argparse
import io
import json
import os

ACCUEIL_DSH = os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2")
MODELE = "qwen/qwen3.8-27b"
CTX = 262144
MAX_SORTIE = 16384


def cabler(nom_route, fournisseur, port):
    chemin = os.path.join(ACCUEIL_DSH, "settings.yaml")
    if not os.path.exists(chemin):
        raise SystemExit("REFUS : %s introuvable." % chemin)
    texte = io.open(chemin, encoding="utf-8", errors="replace").read()
    if "\n    %s:\n" % nom_route in texte:
        print("dsh : route `%s` deja presente, rien a faire." % nom_route)
        return
    route = ("""    %s:
      name: OpenRouter epingle sur %s (proxy %d)
      apiKeyEnv: OPENROUTER_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:%d/api/v1
      defaultContextWindow: %d
      models:
        - id: %s
          name: Qwen3.8-27B (%s epingle)
          contextWindow: %d
          maxTokens: %d
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
""" % (nom_route, fournisseur, port, port, CTX, MODELE, fournisseur, CTX, MAX_SORTIE))
    ancre = "\n  providers:\n"
    if ancre not in texte:
        raise SystemExit("REFUS : ancre `  providers:` introuvable ; ne pas "
                         "inserer a l'aveugle dans %s." % chemin)
    sauve = chemin + ".avant-epingle"
    if not os.path.exists(sauve):
        io.open(sauve, "w", encoding="utf-8", newline="\n").write(texte)
        print("dsh : sauvegarde -> %s" % sauve)
    io.open(chemin, "w", encoding="utf-8", newline="\n").write(
        texte.replace(ancre, ancre + route, 1))
    print("dsh : route `%s` ajoutee (modele %s, epingle sur %s)"
          % (nom_route, MODELE, fournisseur))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fournisseur", required=True)
    p.add_argument("--port", type=int, required=True)
    args = p.parse_args()

    nom_route = "or-%s" % args.fournisseur.lower().replace(" ", "")
    cabler(nom_route, args.fournisseur, args.port)

    inject = {"provider": {"order": [args.fournisseur], "allow_fallbacks": False}}
    print()
    print("Proxy a lancer (detache, sinon il meurt avec le terminal) :")
    print("  $env:UP_TLS = '1'")
    print("  $env:UP_HOST = 'openrouter.ai'")
    print("  $env:PROXY_PORT = '%d'" % args.port)
    print("  $env:PROXY_LOG = 'wire_%s.jsonl'" % nom_route)
    print("  $env:PROXY_INJECT = '%s'" % json.dumps(inject))
    print("  node proxy.mjs")
    print()
    print("Puis :")
    print("  python pilote.py <run> --fournisseur %s --modele %s" % (nom_route, MODELE))
    print()
    print("APRES le run : lire le champ `fournisseur` du journal. Epingler ne")
    print("prouve rien ; un nom autre que %s invalide la mesure." % args.fournisseur)


main()
