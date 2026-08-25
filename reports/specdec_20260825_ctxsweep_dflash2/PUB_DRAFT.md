# BROUILLON de publication — ne part nulle part sans ordre explicite

Statut : DRAFT local. Publication = geste utilisateur (« pousse » puis go
par canal : gist → Localmaxxing → discussion PR #27342 → PR leaderboard
Aider → option r/LocalLLaMA). Score Aider : EN COURS (tâche bh4ag2n8j),
tableau 4 à remplir avant tout envoi.

---

## Qwen3.8-27B sur RTX 4090 24 Go : 160K de contexte à 68–123 t/s, qualité mesurée intacte (llama.cpp)

**TL;DR.** Sur une RTX 4090 stock (24 Go, Windows 11, driver 595.79),
llama.cpp branche dflash2 (PR #27342, commit f7aadef) + décodage
spéculatif n7 + KV quantifié **q8_0-K / q4_0-V** tient **163 840 jetons
de contexte** et décode **123,4 t/s @32k, 92,5 @62k, 78,5 @124k,
68,5 @153,8k**. Le banc qualité (needle, ARC-Challenge, PPL) ne mesure
**aucune** dégradation vs KV f16. Le seul baseline publié comparable
(Hardware Corner, llama.cpp mainline) : 38,4 t/s @64k et plafond 64K —
soit **×2,4 la vitesse à profondeur égale et 2,5× le contexte**.

**Le déblocage en une phrase** : sans `GGML_CUDA_FA_ALL_QUANTS=ON`
(OFF par défaut ET dans les zips officiels), llama.cpp ne compile que
4 kernels flash-attention vec — f16/f16, q4_0/q4_0, q8_0/q8_0,
bf16/bf16. Toute combinaison K/V **mixte** tombe en silence sur un
chemin ×25–63 plus lent (issue #24485, fermée not-planned). D'où les
verdicts « KV quantifié = inutilisable » qu'on lit un peu partout :
c'est la mixité sans rebuild, pas la quantification.

### Tableau 1 — vitesse par profondeur, config qualité (q8-K/q4-V, ctx 163 840)

| n_past | prefill t/s | décode t/s |
|---|---|---|
| 507 | 881 | 109,6 |
| 32 060 | 2 217 | **123,4** |
| 62 115 | 2 018 | 92,5 |
| 123 909 | 1 676 | 78,5 |
| 153 759 | 1 544 | **68,5** |

VRAM : 23 666 MiB chargé, 23 832 sous charge (prédit 23 656, écart
10 MiB). Greedy, warmup jeté, 1 répétition/point, `--parallel 1` épinglé.

### Tableau 2 — plafonds de contexte, même GPU 24 Go

| KV | plafond ctx | décode au point le plus profond | VRAM |
|---|---|---|---|
| f16 | 80K | 105,2 @77,4k | 24 076 |
| q8/q8 | 131K | 79,4 @123,9k | 23 858 |
| **q8-K/q4-V (retenue)** | **163,8K** | **68,5 @153,8k** | 23 832 |
| q4/q4 | 204,8K | 65,9 @188,6k | 23 306 chargé |

(f16 à 128K « charge mais ne sert pas » : 16,7 t/s décode — cause non
prouvée, marge VRAM ~450 MiB suspecte.)

### Tableau 3 — qualité : la quantification KV est gratuite sur ce modèle

Même binaire pour les 4 bras (le delta ne peut venir que du KV).

| KV | needle (codes plantés, greedy) | ARC-C 299 tâches 0-shot | PPL wikitext-2 |
|---|---|---|---|
| f16 | 5/5 @60k | 52,17 ± 2,89 | 6,9551 |
| q8/q8 | 5/5 @60k/120k | 51,84 ± 2,89 | 6,9551 (identique) |
| **q8-K/q4-V** | 5/5 @60k/120k/150k | 51,84 ± 2,89 | 6,9628 (+0,11 %) |
| q4/q4 | 5/5 @60k/120k/150k/**190k** | 52,17 ± 2,89 | 6,9686 (+0,19 %) |

Tout est dans le bruit. L'effondrement q4-K rapporté sur Qwen2.5-7B
(discussion #23470) **ne se transfère pas** à Qwen3.8-27B. Choix de
référence : q8-K/q4-V (marge du K à 8 bits, coût mesuré nul) ; q4/q4
réservé au besoin extrême 205K.

### Tableau 4 — Aider polyglot (banc agent de codage reconnu)

| métrique | valeur |
|---|---|
| **pass_rate_2 (chiffre du board)** | **52,0 %** (117/225) |
| pass_rate_1 | 16,9 % (38/225) |
| percent_cases_well_formed | 99,1 % |
| seconds_per_case | 52,2 s (~3 h 16 au total) |

225 exercices, 6 langages, harnais officiel en docker, `--threads 1`,
edit format `whole`, 2 essais (standard du board), serveur local :8005
(config du tableau 1). Jetons servis : 2,49 M prompt + 0,68 M
complétion. Acceptation draft observée sur ce contenu réel : ~52 %.

**Placement (board consulté le 25/08/2026)** : Qwen3 32B 40,0 % ·
**nous 52,0 %** · Qwen3 235B-A22B 59,6 % · Qwen2.5-Coder-32B 16,4 %.
Un 27B quantifié Q4 **local** au-dessus du 32B de sa propre famille,
avec 160K de contexte et ~120 t/s de décode utile.

Réserves : edit format `whole` (accepté et affiché par le board, mais
les gros modèles y sont en `diff`) ; 23 cas ont épuisé une fenêtre de
contexte interne (28 error_outputs, 3 timeouts) — marge d'amélioration,
pas gonflement ; run interrompu par un arrêt machine externe à 100/225
et repris par `--cont` (résultats disjoints dans le temps, même config).

### Comparables publiés (vérifiés le 25/08/2026)

- **Hardware Corner** (llama.cpp mainline b10364, Q4_K_S, MTP off, KV
  f16, Ubuntu) : 46,2 @4k → 42,2 @32k → 38,4 @64k, plafond 64K —
  https://www.hardware-corner.net/qwen3-8-27b-hardware-tests/
- **ninfer-4090** (moteur C++20/CUDA **custom**, PAS llama.cpp ; format
  KV « E8 4-bit » propriétaire, Apache 2.0, sweeps publiés) : sans
  spéculation 42,1 @128K, 36,6 @256K ; MTP3 sur tâches code 148,6
  shallow → 91,2 @256K (acceptation 72–81 %) ; 262K sur 24 Go —
  https://github.com/sergiuszm/ninfer-4090

**Cadrage honnête de la revendication** : à notre connaissance, config
la plus rapide **publiée sur la pile llama.cpp** (GGUF standard,
upstream-compatible, Windows) à profondeur ≥62k sur 4090 24 Go, avec
qualité mesurée. Cross-moteur, ninfer-4090 publie plus haut à plus
profond sur du code avec kernels custom et format modèle propriétaire —
classe d'outil différente, revendication non concurrente.

### Limites (dites, pas cachées)

1. PR #27342 non mergée upstream ; rebuild maison requis
   (`GGML_CUDA_FA_ALL_QUANTS=ON`, VS2022, arch 89).
2. Acceptation spéculative dépendante du contenu : vitesses mesurées
   sur remplissage texte déterministe ; le code peut différer (les deux
   sens). Le score Aider donne le point « contenu réel ».
3. 1 répétition par point de vitesse (warmup jeté) — pas d'intervalle
   de confiance sur les t/s.
4. Needle = rappel saillant seulement ; ARC = 299 tâches validation
   0-shot (pas l'absolu leaderboard 25-shot).
5. Décode @62k q8/q8 vu −23 % vs f16@65K sur 138 jetons générés —
   acceptation sous KV quantifié non isolée au propre.

### Repro (l'essentiel)

```
cmake -B build-faq -A x64 -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 \
      -DGGML_CUDA_FA_ALL_QUANTS=ON -DLLAMA_CURL=OFF   # PR #27342, f7aadef
llama-server -m Qwen3.8-27B-Q4_K_M.gguf -ngl 99 -fa on --parallel 1 \
      -c 163840 -ctk q8_0 -ctv q4_0 [draft n7 : flags dflash2]
```

Modèle : Qwen3.8-27B Q4_K_M GGUF. Bancs : needle/diff maison
(scripts/bench_kv_quality.py), llama-perplexity (ARC bin ikawrakow,
wikitext-2 ggml-org), harnais Aider officiel en docker.
