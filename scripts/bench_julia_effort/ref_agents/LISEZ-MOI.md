# Référence « sous-agents » — les deux bras web, sur les douze tâches dures

Ce dossier tient la mesure décrite en 3.9 de `docs/DSH_QWEN_LOCAL_LOGBOOK.md`.

**Ce qui a été mesuré.** Vingt-quatre exécutants neufs (Claude Opus 5), un par
couple (bras, tâche), aucun n'ayant jamais vu le corpus. Chacun a reçu un dossier
de travail contenant un seul fichier, `TASK.md`, produit par le **même code que
`bench.py`** (`bench.PREAMBULE_WEB` + `prompts/tNN.txt`) : l'énoncé est identique
à l'octet près à celui que reçoit l'agent dsh. La consigne d'entrée est celle de
dsh, mot pour mot. Le verdict vient de `tasks/harness.jl`, comme pour tout le banc.

**Résultat : 12/12 dans les deux bras**, y compris sur les quatre tâches dont le
fait n'est pas dans l'énoncé (`t22`, `t24`, `t32`, `t34`). Le bras web a bien
cherché — 39 recherches, 12 tâches sur 12 — et il a cherché la bonne chose ; les
requêtes sont dans `journaux/`, verbatim. Ça n'a rien changé au verdict et ça a
coûté +15,0 % de jetons et +38,4 % de temps.

## Contenu

| fichier | ce que c'est |
|---|---|
| `resultats.json` | une entrée par run : verdict, exécutions de Julia, recherches, requêtes, lignes, jetons, appels d'outils, durée |
| `journaux/<bras>_<tache>.txt` | le `_journal.txt` écrit par l'agent lui-même, copié tel quel |

## Ce que ces chiffres ne sont pas

- Les exécutions de Julia et les recherches sont **auto-déclarées** par l'agent :
  aucun `_shim/julia.cmd` n'était installé pour les compter de l'extérieur.
- Les espaces de travail eux-mêmes (les `solution.jl`) vivaient dans le
  répertoire temporaire d'une session et ne sont pas conservés ici ; seuls les
  journaux et le tableau le sont.
- L'exécutant est Opus 5, pas Qwen3.8-27B. Cette ligne est un **plafond**, pas
  une prédiction sur le modèle local.

## Rejouer le jugement

    python scripts/bench_julia_effort/juger_agents.py <racine>

où `<racine>` contient `<bras>/<tache>/solution.jl`. Sans argument, le script
cherche `ref_agents/espaces/`.
