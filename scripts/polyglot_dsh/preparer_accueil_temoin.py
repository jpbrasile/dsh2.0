# Prepare un ACCUEIL DSH ISOLE qui pointe sur le serveur temoin (port 8007).
#
# POURQUOI ISOLE. `pilote.py` et `bench.py` REECRIVENT `agent-default-model`
# dans l'accueil qu'on leur donne, sans le restaurer (pilote.py:779-789). Ecrire
# la route temoin dans `.dsh-bench-dflash2` laisserait ce banc pointe sur un
# serveur factice apres coup, et le run suivant mesurerait le temoin.
# On copie donc, on ne modifie rien en place.
#
# CE QUE CA NE FAIT PAS : aucun trafic vers 8005 (le run GPQA local y tourne) ni
# vers 8006 (un enregistreur y ecoute deja, il relaie vers 8005).

import io
import os
import shutil
import sys

SOURCE = os.path.join(os.path.expanduser("~"), ".dsh-bench-dflash2")
CIBLE = os.path.join(os.path.expanduser("~"), ".dsh-temoin-echantillonnage")

# `samplingParams` : le bouton qu'on cherche. La doc de pi (docs/models.md:255)
# dit que seules les APIs OpenAI-compatibles l'appliquent -- c'est le cas ici --
# et qu'il BAT le champ de requete de meme nom, donc c'est la source unique.
# dsh et pi partagent la meme bibliotheque (llm-pi-ai) : on teste la meme cle
# des deux cotes, et le temoin dit si elle part vraiment.
# Valeurs = carte de modele Qwen3.8-27B, mode thinking.
ROUTE = """    temoin:
      name: Temoin echantillonnage (port 8007)
      apiKeyEnv: DSH_TEMOIN_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:8007/v1
      models:
        - id: temoin
          name: Temoin
          contextWindow: 32768
          maxTokens: 4096
          samplingParams:
            temperature: 1.0
            top_p: 0.95
            top_k: 20
            min_p: 0.0
          reasoningEfforts: { "off": , low: low, medium: medium, high: high }
"""


def main():
    if not os.path.isdir(SOURCE):
        raise SystemExit("REFUS : accueil source introuvable : %s" % SOURCE)
    reglages_src = os.path.join(SOURCE, "settings.yaml")
    if not os.path.exists(reglages_src):
        raise SystemExit("REFUS : pas de settings.yaml dans %s" % SOURCE)

    if os.path.isdir(CIBLE):
        print("accueil temoin deja present : %s (reutilise)" % CIBLE)
    else:
        os.makedirs(CIBLE)
        # Les profils sont necessaires : le banc lance `--profile headless`.
        prof = os.path.join(SOURCE, "profiles")
        if os.path.isdir(prof):
            shutil.copytree(prof, os.path.join(CIBLE, "profiles"))
            print("profils copies.")

    texte = io.open(reglages_src, encoding="utf-8", errors="replace").read()

    # Insertion de la route juste apres la ligne `  providers:` de llm-pi-ai.
    ancre = "\n  providers:\n"
    if ancre not in texte:
        raise SystemExit("REFUS : ancre `  providers:` introuvable dans %s ; "
                         "ne pas inserer a l'aveugle." % reglages_src)
    if "\n    temoin:\n" in texte:
        print("route temoin deja presente.")
    else:
        texte = texte.replace(ancre, ancre + ROUTE, 1)

    # Le defaut pointe sur le temoin. C'est une COPIE : on n'ecrase rien.
    lignes, sortie, dans_defaut = texte.split("\n"), [], False
    for l in lignes:
        if l.startswith("agent-default-model:"):
            dans_defaut = True
            sortie.append(l)
            sortie.append("  provider: temoin")
            sortie.append("  model: temoin")
            sortie.append("  reasoningEffort: medium")
            continue
        if dans_defaut:
            # On saute les anciennes lignes du bloc (indentees) et ses
            # commentaires, jusqu'a la prochaine cle de premier niveau.
            if l.startswith(" ") or l.startswith("#") or not l.strip():
                continue
            dans_defaut = False
        sortie.append(l)

    cible_reglages = os.path.join(CIBLE, "settings.yaml")
    io.open(cible_reglages, "w", encoding="utf-8", newline="\n").write(
        "\n".join(sortie))
    print("ecrit : %s" % cible_reglages)
    print("accueil temoin pret : %s" % CIBLE)
    print("lancer dsh avec DSH_HOME=%s" % CIBLE)


if __name__ == "__main__":
    main()
