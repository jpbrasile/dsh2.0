# Porte de tests Julia rapide — phase 0.5 du README

**Ce que c'est.** Un agent modifie un fichier du framework Julia (`plasma-digital-twin`,
177 k lignes de source, 124 k de tests, 29 000 tests, 25 sous-suites). La porte répond en
**30 s maximum** : VERT / ORANGE / ROUGE, avec les comptes de `Test` lui-même. Elle ne
remplace pas la suite complète avant fusion ; elle dit vite si ce qui est *ciblé* casse.

Tout vit dans `scripts/julia_gate/` et ne touche jamais au dépôt du framework (lecture seule,
sauf le contrôle `essai_rt.py` qui modifie un fichier *temporairement* et le restaure octet à
octet).

## Les trois briques

| brique | rôle | fichier |
|---|---|---|
| carte | fichier source → fichiers de test qui l'exercent (statique : `include`, `using PlasmaDigitalTwin.X`, dossier inclus en boucle) | `carte.py` |
| session | Julia persistante : Revise + paquet chargés une fois (10 s tiède), rejoue un fichier de test à la demande dans un **module neuf** | `serveur.jl` (TCP 127.0.0.1:8077, JSON par ligne) |
| porte | fichiers modifiés (`git status` du framework, ou désignés) → tests rangés du plus ciblé au plus large → rejeux jusqu'au budget → verdict + `_gate/dernier.json` | `porte.py` |

```
python porte.py                 # fichiers .jl modifiés du framework, budget 30 s
python porte.py src/x/y.jl      # fichier désigné
python porte.py --budget 300    # budget large (couverture complète d'un source partagé)
python porte.py --statut | --arret
python essai_rt.py bon | mauvais | rouge-cache     # les bras connus (voir plus bas)
```

Codes de retour : 0 VERT, 1 ROUGE, 2 ORANGE, 3 PANNE (serveur absent).

## Les règles de la carte (et ce qu'elle rate)

- Unité rejouable = `test_*.jl` ou `runtests.jl`. Les `debug_*`, `diagnose_*`, `validate_*`,
  `benchmarks.jl` qui vivent sous `test/` sont des scripts, jamais des cibles (mesuré : ils
  plantent ou tournent des minutes).
- Un fichier de test qui ne charge rien lui-même (158 sur 459) est rejoué via le `runtests.jl`
  qui l'inclut. Un test inclus par un autre candidat n'est pas rejoué à part.
- Rang = nombre de sources atteintes par le test (peu = ciblé) ; les suites entières viennent
  après. Une durée mémorisée (`_gate/durees.json`) plus longue que le budget restant fait
  sauter le test (compté « non rejoué »), au lieu de bloquer le serveur.
- **22 sources sur 374 n'ont aucun test** (`hybrid/Hybrid.jl`, `PICburst.jl`,
  `node_contract/path_c_builders/*`, …) : modifier l'un d'eux donne ORANGE « non couvert »,
  jamais VERT. 27 fichiers de test ne sont ni autonomes ni inclus par un runner : invisibles
  pour la porte (liste : `carte.py` → `non_autonomes`).
- Non suivi : un chemin d'`include` construit dynamiquement (hors la boucle `readdir` de
  `NodeContract.jl`), `push!(LOAD_PATH…)` + `using Foo`.

## Le verdict, honnêtement

- **VERT** : tous les tests ciblés rejoués et passés, rien de non couvert.
- **ROUGE** : au moins un `@test` faux ou un fichier en erreur. Les blocs `Test Failed` /
  `Error During Test` sont imprimés ; journal complet dans `_gate/journaux/`.
- **ORANGE** : rien de rouge mais la preuve est incomplète — source non couvert, tests non
  rejoués faute de budget, ou rien à rejouer. **Un ORANGE n'est pas un vert** : la suite
  restante est due avant fusion.

Un source partagé (ex. `src/physics/GasSpecies.jl`, atteint par 6 unités) donne ORANGE à
30 s : les 3 unités légères (1 195 tests) passent en 13 s, les 3 suites lourdes (gpu2,
electrical_model, gpu3d) demandent 450 s de plus. Voir les mesures.

## Mesures (2026-08-23, RTX 4090 partagée avec un llama-server inactif)

| quoi | mesure |
|---|---|
| `using PlasmaDigitalTwin` à froid (paquet à re-précompiler) | 87 s |
| idem tiède | 10–11 s ; serveur prêt en 15 s |
| rejeu `test/physics/test_gas_species.jl` (99 tests), serveur tiède | 2–3 s ; 2,9 s bout en bout |
| `physics/runtests.jl` (1 149 tests) | 8 s |
| `gpu2/runtests.jl` (2 003 tests, CUDA) | 116 s (premier rejeu) |
| `electrical_model/runtests.jl` (2 279 tests, MTK) | 229 s — 3 erreurs, voir ci-dessous |
| `gpu3d_integration/runtests.jl` (4 897 tests, CUDA) | 104 s |

À compléter : second rejeu des suites lourdes dans la même session (le code du paquet reste
compilé ; seuls les sources inclus directement sont recompilés).

## Les bras connus (`essai_rt.py`)

| bras | modification temporaire | attendu | mesuré 2026-08-23 |
|---|---|---|---|
| `bon` | commentaire dans `test/physics/test_gas_species.jl` | VERT | VERT, 99 tests, 2,4 s |
| `bon-partiel` | commentaire dans `src/physics/GasSpecies.jl` (6 unités, 3 lourdes) | ORANGE, jamais ROUGE | ORANGE, 1 195 tests verts en 7,7 s, 3 suites non rejouées |
| `mauvais` | `n_processes` renvoie +1 | ROUGE | ROUGE en 12,9 s (10 tests faux dans `physics`) |
| `rouge-cache` | `error(...)` ajouté à `hybrid/PICburst.jl`, que la carte n'atteint pas | **pas** VERT | ORANGE « non couvert », 1 s |

Le bras `mauvais` est l'arme de l'équipe rouge : si la porte reste verte sur un source cassé,
la carte a un trou. Les quatre bras laissent l'arbre du framework intact (md5 vérifié).

## Ce que l'étape 0.5 du README donne, mesuré

- « un fichier modifié → verdict < 30 s » : **oui, toujours** (budget dur : verdict à 30 s au
  plus, serveur tué et relancé s'il dépasse). Mais un VERT en 30 s n'existe que si les tests
  ciblés tiennent dans le budget : vrai pour un fichier de test ou un module léger ; pour un
  fichier de `Physics` (maille module : 6 unités, 3 lourdes à 100–230 s) le verdict à 30 s est
  ORANGE — preuve partielle, suites lourdes dues avant fusion.
- Conséquence pour la phase 2 (le `coder` branché sur la porte) : ORANGE doit déclencher les
  suites restantes en arrière-plan, pas être lu comme un vert. Pas de redesign nécessaire.

## Journal

- 2026-08-23 — première version. Trois défauts d'instrument trouvés et corrigés par le bras
  `bon` : scripts de diagnostic pris pour des tests ; runner et ses fichiers inclus rejoués
  deux fois ; budget non dur (un script a tiré à 37 s et bloqué le serveur → budget dur,
  serveur tué et relancé en arrière-plan, durée mémorisée).
