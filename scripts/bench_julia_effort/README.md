# Banc « effort de raisonnement » — 10 tâches Julia

Mesure ce qu'un modèle servi localement produit **réellement** quand on fait varier
son niveau d'effort de raisonnement : taux de réussite, débit de génération, temps
par tâche. Le modèle écrit le code ; Julia le juge contre des assertions qu'il n'a
jamais vues.

## Ce qui est mesuré, et par quel instrument

| grandeur | instrument | ce qu'elle inclut |
|---|---|---|
| **réussite** | Julia exécute `solution.jl` contre `tasks/tNN_checks.jl` | binaire, PASS/FAIL |
| **débit (t/s)** | bloc `timings` rendu par llama-server, relevé par le proxy | décodage seul |
| **temps / tâche** | chrono client, lancement de dsh → verdict | agent + outils + Julia |

Les trois ne se substituent pas. Le débit est une propriété du serveur ; le temps
par tâche est une propriété du *système*, et c'est lui qui décide si un niveau
d'effort est utilisable. Un niveau peut décoder plus vite **et** finir plus tard,
parce qu'il génère davantage de jetons ou passe plus d'appels d'outils.

## Le témoin négatif est intégré

Le gabarit de chat de Qwen3.8 **aliase `high` sur `xhigh`** — ligne
`if resolved == 'high' -> 'xhigh'`. Vérifié côté serveur via `/apply-template` :
les deux niveaux produisent un prompt **identique**, sha256 `15c034577114cced`,
352 caractères. Le gabarit n'accepte d'ailleurs que trois valeurs (`low`,
`medium`, `xhigh`) ; toute autre lève `raise_exception` et le serveur rend 400.
Et `medium` n'ajoute **aucune** instruction — la branche est absente du gabarit.

Faire tourner `high` **et** `xhigh` ne donne donc pas deux points de mesure : ça
donne **l'étalon de bruit du banc**. `analyse.py` l'imprime en fin de table.

> **À lire avant toute conclusion.** Si l'écart `high`/`xhigh` dépasse l'écart
> entre deux niveaux réellement distincts, la conclusion n'est pas « tel niveau
> est meilleur » — c'est « à 10 tâches, ce banc ne sépare rien ». C'est un
> résultat, pas un échec.

## Calibrage du vérificateur — obligatoire avant d'y croire

```bash
python bench.py --selftest
```

`ref/` contient 10 solutions correctes, `bad/` 10 solutions portant chacune **un
défaut nommé**. Le banc exige `10/10` réussies et `10/10` attrapées, et il
**imprime par quelle assertion** chacune est tombée.

Cette impression n'est pas décorative. Un vérificateur cassé — qui ne charge
rien, qui se trompe de chemin — rend lui aussi « 10/10 attrapées ». Ce qui
distingue le vérificateur qui mesure de celui qui refuse tout, c'est que chaque
échec est nommé par *son* défaut :

```
t09 FAIL check: AssertionError: dotp alloue 80119 octets, il en faut 0
t10 FAIL check: AssertionError: produit signe : got [6.0, 4.0]
```

Mesuré le 2026-08-22 : known-GOOD 10/10, known-BAD attrapées 10/10, **CALIBRÉ**.

## Prérequis

1. **llama-server** en écoute, servant le modèle sous l'alias attendu
   (`scripts/start_llama_qwen38_27b_specdec.ps1`).
2. **Le proxy enregistreur**, entre l'agent et le serveur — c'est lui qui écrit
   `wire.jsonl` et sans lui il n'y a **pas** de débit par niveau :
   ```bash
   node proxy.mjs          # 8006 -> 8005, journalise timings + marqueurs
   ```
3. **Une route dsh** pointant sur le proxy, en `thinkingFormat: chat-template`.
   C'est le seul des dix formats qui transmette un *niveau* :
   `qwen-chat-template` n'envoie qu'un booléen `enable_thinking`, et les cinq
   niveaux y seraient une seule et même requête.
4. **Piège YAML 1.1** : dans la liste `reasoningEfforts`, la clé `off` **doit**
   être quotée `"off"` — sans guillemets elle est relue comme le booléen `false`.

## Lancer

```bash
python bench.py --selftest                     # calibrer d'abord
python bench.py off,low,medium,high,xhigh      # la campagne (50 runs)
python bench.py low t03,t07                    # un sous-ensemble
python analyse.py                              # la table
```

`bench.py` réécrit `agent-default-model` dans `~/.dsh/settings.yaml` à chaque
niveau. **Il ne le restaure pas en sortant** : à la fin d'une campagne, remettre
la route habituelle à la main (`dsh_effort.py <provider> <model> <effort>`).

Variables d'environnement : `DSH_BIN`, `JULIA_BIN`, `BENCH_PROXY`,
`BENCH_PROVIDER`, `BENCH_MODEL`.

## Deux défauts qui ont coûté une campagne chacun

- **La consigne passe par un fichier, jamais par `argv`.** Un prompt multi-ligne
  traverse `cmd.exe` en se faisant manger : dsh a reçu une tâche **vide**, et le
  modèle a inventé un Project Euler qu'on ne lui avait pas demandé. Le banc
  écrit `TASK.md` dans l'espace de travail et ne passe qu'une ligne.
- **Le harnais imprime un verdict sur UNE ligne.** Un `showerror` Julia tient sur
  plusieurs lignes ; un `tail -1` y attrape `in expression starting at ...` au
  lieu de la cause, et le bras known-BAD rendait `0/10` alors qu'il attrapait
  tout. Le harnais aplatit le message et le banc filtre sur `^VERDICT`.

## Fichiers

| | |
|---|---|
| `bench.py` | pilote + `--selftest` |
| `analyse.py` | table finale, témoin `high`/`xhigh` inclus |
| `dsh_effort.py` | bascule `agent-default-model`, ancrée en texte, écriture atomique |
| `proxy.mjs` | proxy enregistreur, endpoint `/__mark?tag=` |
| `prompts/tNN.txt` | énoncés donnés au modèle |
| `tasks/tNN_checks.jl` | assertions — **le modèle ne les voit jamais** |
| `tasks/harness.jl` | charge la solution, exécute les checks, imprime un verdict |
| `ref/`, `bad/` | bras known-GOOD et known-BAD du vérificateur |
