# Phase 1 — boucle modèles : ce qui est livré, ce qui est mesuré (2026-08-23)

Journal de mesure de la Phase 1 du README (« Model loop »). Règle du document :
un chiffre par affirmation, la commande qui le redonne, et la limite en clair.

| # | Étape README | Livré | Contrôle | Mesure du 23/08 |
|---|---|---|---|---|
| 1 | Refresh → SQLite → rank → emit | `harness/modeles.py` (`--rafraichir`, `--classer`, `--emettre`), base `harness/modeles.sqlite` (gitignorée), fichiers émis `harness/providers.emis.yaml` + `harness/chaines.yaml` (en git, relus par diff) | `python harness/modeles_unit.py` (gratuit, sans réseau) | catalogue OpenRouter : **422 modèles, 267 candidats** (outils + contexte ≥ 65 536, hors routeurs `openrouter/*`, alias `~x/latest`, variantes `:batch`) ; 18 gratuits, 1 stealth ; unitaire **43/43** (37 avant le red team, +6 après) |
| 2 | Stealth + probation + tier, hook de session ⚑RT | tier et probation calculés du catalogue seul ; bloc `openrouter-auto` (OPEN only) ; `scripts/dsh.ps1` appelle `modeles.py --session` avant le boot (`-SkipModelRefresh` pour sauter) | unitaire (catalogue malformé ×13, fausse entrée stealth, levée de probation, fichier émis trafiqué) ; fumée `fumee_route.py stealth/ox-alpha openrouter-auto` | `stealth/ox-alpha` (apparu le 21/08) → `openrouter-auto [probation, OPEN, stealth]` → fumée **OK, 2 appels, 19,7 s**, servi par le modèle demandé ; 2 `--session` consécutifs : « CHANGE + install » puis « identique » (pas de réécriture inutile) ; après le red team : 3 fumées `minimal` vertes (30,0 s, 22,4 s, 6,4 s ; 9 appels, 0 USD) notées par `fumee_route.py` → **probation 0** → `--session` : `open: [stealth/ox-alpha]` |
| 3 | cost-meter + dsh-context, prix réels, cache visible | `harness/cout.py` (grand livre `harness/_cout/grand_livre.jsonl`, gitignoré) ; `fumee_route.py` y verse chaque run ; campagne `redteam:<étape>` posée par `redteam_run.py` | `python harness/cout.py` | journée du 23/08 : **67 appels, 80,9 % des tokens d'entrée servis par le cache, 0,2157 USD** (tout le coût = le red team, 54 appels deepseek-v4-pro ; les 13 appels stealth = 0 USD). Par appel, le cache va de 0 % (premier appel d'une campagne) à 97-98 % (appels suivants) : les pourcentages d'une campagne sont des agrégats, pas des taux par appel ; coût réel = champ `usage.cost` facturé par OpenRouter, pas un tarif relu |

## 1. Ce que « classer » veut dire ici

Famille → filtre → ordre. Trois familles, écrites dans `FAMILLES` de `modeles.py` :

- `ouvrier` : payants (PRIVATE+OPEN), score de verdicts décroissant, puis **prix pondéré**
  croissant (40 × entrée + 1 × sortie : un tour d'agent dsh ≈ 8 000 tokens d'entrée pour
  ≈ 200 de sortie, même ratio que `openrouter_cheapest_proxy.mjs`).
- `open` : gratuits ou stealth **hors probation**, score puis contexte décroissant.
- `probation` : gratuits ou stealth **en probation**, score puis le plus récent d'abord.
- red team : `redteam_pour(ouvrier)` = la famille `ouvrier` moins le préfixe de fournisseur
  de l'ouvrier (règle « autre famille », README « Rules »).

« Task-fit » au 23/08 = le score `verts − rouges` de la table `verdicts` (0 sans verdict),
alimentée par `--verdict ID --tache T --preset P --vert|--rouge`. Aucun verdict réel n'est
encore enregistré : le classement d'aujourd'hui est donc **prix et contexte seulement**.
Les verdicts arrivent avec la Phase 2 (porte Julia) et la Phase 3 (distillateur).

Classement du 23/08 (`python harness/modeles.py --classer`), tête de chaque famille :
`ouvrier` = inclusionai/ling-2.6-flash 0,43 $/M pondéré, mistralai/mistral-nemo 0,79,
inclusionai/ling-3.0-flash 0,90 (qwen/qwen3.8-27b épinglé en tête de chaîne : 19,0 $/M
pondéré — il n'est pas le moins cher, il est celui que la Phase 0 a mesuré) ;
`probation` = stealth/ox-alpha (ctx 1 M), dots-studio/dots-3-note-preview:free,
liquid/lfm-2.5-2.6b:free, nvidia/nemotron-3.5-lightning:free ; `open` = vide au premier
classement (aucun gratuit n'avait 3 verts sous `minimal`), puis `[stealth/ox-alpha]` après
ses 3 fumées vertes (§5).

## 2. Tier et probation — par construction, pas par option

- `tier = OPEN` ⇔ l'id finit par `:free`, ou prix d'entrée ET de sortie = 0, ou l'id commence
  par `stealth/`. Tout le reste = `PRIVATE+OPEN`. Le **nom** ne compte pas (une entrée payante
  nommée « stealth (hidden) » reste PRIVATE+OPEN ; une entrée `x:free` à prix non nul reste
  OPEN). Recalculé à chaque rafraîchissement, jamais lu d'un verdict ni d'une option.
- `probation = 1` pour tout OPEN tant qu'il a moins de `N_VERTS = 3` verdicts verts sous le
  preset `minimal` (stock). Un vert sous `lean` ne compte pas. Lever la probation ne change pas
  le tier : un stealth sorti de probation reste OPEN only.
- Le fichier émis ne contient **que** `openrouter-auto`, et `--emettre` relit le YAML écrit et
  supprime le fichier si un id non-OPEN s'y trouve (code 3). `chaines.yaml` : `ouvrier` et
  `redteam` n'ont que des PRIVATE+OPEN, `open` et `probation` que des OPEN.
- Catalogue malformé (pas une liste, entrée sans id, doublon, prix non numérique ou négatif
  hors routeur, `context_length` non entier, JSON cassé) : refus en bloc, code 2, base
  intacte (empreinte identique avant/après, 10 cas unitaires).

Ce que ça ne fait pas : décider. Le bloc émis est une proposition ; `providers_install.py`
l'applique à `~/.dsh/settings.yaml` avec sauvegarde, et seulement si le texte a changé.

## 3. Le hook de session, mesuré

`scripts/dsh.ps1` exécute `python harness/modeles.py --session` après les deux preflights
et avant le boot. Sans réseau : avertissement, config précédente conservée, lancement
normal. Mesuré le 23/08 à 16:58 avec `dsh.ps1 -Ask "…" -Fresh -NoOpen` :

```
modeles     : rafraichi : 422 modeles (267 candidats outils+ctx>=65536) ; nouveaux 0 [] ; disparus 0 []
modeles     : emis : providers.emis.yaml (4 modeles OPEN) et chaines.yaml -- identique
arbre       : epingle -- C:\Users\test\.dsh\runtime\dsh-0.1.1-rc.2
```

puis le boot a échoué pour une cause **antérieure et hors de cette phase** : le profil
`~/.dsh/profiles/headless/cordis.yml` de la machine référence un paquet absent
(`dsh-subagent-timeout`) et un serveur MCP inexistant
(`agentic-flow-fresh/scripts/dsh-mcp/effitech-image/server.mjs`, campagne vision du 21/08).
Les bancs et les red teams passent parce que `fumee_route.py` utilise un accueil isolé vierge.
À réparer par l'utilisateur (ses settings) ; noté, pas touché.

Correction annexe du lanceur : l'avertissement « OPENROUTER_API_KEY absente du .env » était
périmé depuis la Phase 0 (clés dans `.credentials.yaml` seulement) ; il vérifie maintenant le
fichier de credentials et signale une clé venue de l'environnement comme une entorse.

## 4. Le compteur de coût — ce qu'il compte, ce qu'il ne compte pas

Compté : tout ce qui passe par l'enregistreur `proxy.mjs` (routes `openrouter-banc`,
`openrouter-auto` et toute route passée à `fumee_route.py`, dont les red teams). Source = la
réponse `usage` d'OpenRouter : `cost` (USD facturés), `prompt_tokens`, `completion_tokens`,
`cached_tokens`. Dédoublonnage sur (t0, ms, modèle servi, tokens d'entrée).

Pas compté : la route `openrouter` directe du lanceur interactif et `openrouter-cheap`
(`openrouter_cheapest_proxy.mjs` n'écrit pas de fil). Pour ces deux-là, le relevé est
https://openrouter.ai/activity. Les coûts des red teams de la Phase 0 ne sont pas dans le
grand livre (fil écrasé avant sa création) : ils sont dans les rapports (0-walls ≈ 0,15 USD,
0-done ≈ 0,08 USD).

« dsh-context » : aucun greffon de ce nom dans l'arbre 0.1.1-rc.2 (`dsh-token-meter` estime
à 4 caractères/token, `dsh-session-stats` compte par session). Le cache-hit mesuré sur le
fil rend le greffon inutile pour le sprint ; si le taux passe sous 50 % (règle README), le
casseur de cache se cherche dans le préfixe du prompt système, visible dans `wire.jsonl`
(`sent.sys_chars`).

## 5. Critère Done

« new OpenRouter stealth model reaches the OPEN chain in one session start » — première
lecture (avant le red team) : `stealth/ox-alpha` dans `openrouter-auto` et dans la chaîne
`probation` après un seul `--session`. Le red team a lu « OPEN chain » littéralement : la
chaîne `open:` de `chaines.yaml` (hors probation) était vide, zéro verdict en base. Il a
raison — la première lecture confondait le tier OPEN et la chaîne `open`. Réponse, mesurée :

1. `fumee_route.py` note maintenant un verdict (`modeles.py --verdict`) à chaque run dont
   tous les appels ont été servis par le modèle demandé : VERT si le run est OK, ROUGE sinon,
   preset `minimal` sans `--patch`, sinon le nom du patch (`FUMEE_SANS_VERDICT=1` pour ne
   rien noter). Un run servi par un autre modèle ne note rien.
2. 3 fumées `minimal` sur `stealth/ox-alpha` via `openrouter-auto` (PONG, 3 appels chacune,
   30,0 s / 22,4 s / 6,4 s, 0 USD) → verts minimal 1, 2, 3 → probation 0.
3. `--session` suivant : « emis : 5 modeles OPEN, CHANGE ; providers_install rc=0 » et
   `chaines.yaml` porte `open: [stealth/ox-alpha]`.

Donc : un stealth **nouveau** arrive dans `openrouter-auto` + chaîne `probation` au premier
démarrage de session ; il passe dans la chaîne `open` au démarrage qui suit ses 3 verts.
Limites dites : la barre des 3 verts est la fumée PONG (faible enjeu, c'est ce que la
probation promet — pas une preuve de qualité sur une vraie tâche) ; « new » a été simulé
en unitaire (`stealth/faux-rt`) — le seul vrai stealth du jour existait déjà avant la Phase 1.

« one day's cost + cache-hit rate visible » : oui — `python harness/cout.py --jour 2026-08-23`
= 67 appels, 80,9 % de cache, 0,2157 USD. Limite : seules les routes enregistrées y sont ;
un doublon de clé ignoré est maintenant compté et affiché (DIVERGENT si son coût diffère).

Red team de la phase (un seul, sur le Done, décision utilisateur du 23/08) :
`redteam/1-done.md` — FALSIFIED (1 HIGH, 1 MEDIUM, 3 LOW), les 5 corrigés ci-dessus et dans
`modeles_unit.py` (43/43).
