# Étude paramétrique tps × contexte × spéculation — DFlash2 vs MTP actuel (25/08/2026)

Ordre utilisateur : « jambes dflash2 : fais l'étude paramétrique tps vs
context vs mcp actuel » (lu « MTP actuel » = la config de service courante
q38-mtp ; c'est aussi le comparateur du rule-gate DFlash2). Question de
mi-course « tu as pris le pr qui fonctionne ? » : NON pour cette passe — voir
Limites ; « vérifie les problèmes potentiels de warm up » : fait, quantifié.

## Protocole

- Outil : `scripts/bench_llama_ctx.py` (timings du serveur, calibrage
  /tokenize, refus hors-bornes) — le même que la fenêtre 4, donc comparable.
- Points : cibles 500 / 8 200 / 16 100 / 32 000 / 61 000 jetons
  (n_past mesurés : 507 / 8 395 / 16 205 / 32 060 / 62 115), n_predict 256,
  greedy (temperature 0.0), cache_prompt false, 1 rép par point (méthodo
  fenêtre 4 — pas de médiane, dire « 1 rép », jamais « médiane »).
- Serveur : lanceur `start_llama_qwen38_27b_specdec.ps1`, ctx 65536,
  KV f16/f16, ubatch 512, pas de mmproj (texte seul), port 8005,
  production :8004 volontairement arrêtée depuis le 23/08 (pré-existant).
- **`--parallel 1` épinglé et vérifié** (question utilisateur 25/08) : le
  lanceur le passe toujours (ligne `"--parallel", "1"`), et les 12 logs
  serveur du balayage portent tous `n_slots = 1` avec `n_ctx_slot` égal au
  `-c` entier (65536 / 81920 / 98304 / 131072). Conséquences : le contexte
  n'est jamais divisé entre slots (les plafonds 80K/96K/128K et le
  65 KiB/jeton seraient faux avec `-np > 1`, car `n_ctx_slot = c / np`),
  et les requêtes du bench sont sérialisées côté serveur — aucun débit
  n'est contaminé par du batching inter-slots. `kv_unified = 'false'`
  partout (défaut).
- Modèle cible : Qwen3.8-27B Q4_K_M épinglé (17 106 775 008 B) ; draft
  DFlash2 incoai Q4_K_M épinglé (1 143 006 752 B).
- **Warmup (ordre utilisateur, mesuré)** : le 1er tir d'un serveur froid
  sous-lit le prefill ×2,3 (864 → 1 990 t/s au point ~500 sur le bras MTP,
  re-tiré chaud) ; le décode est insensible (79,6 → 78,3 t/s, bruit). Les
  bras dflash2 ont donc un tir de chauffe JETÉ (fichiers `warmup_*.txt`)
  avant le balayage ; le bras MTP garde son point 500 chaud en fichier
  séparé (`sweep_mtp-b10488_point500_chaud.txt`).

## Bras

| bras | binaire | spéculation | vérif identité |
|---|---|---|---|
| mtp-b10488 (« actuel ») | b10488-9d77fa172 | draft-mtp p-min 0.75 n-max 2 n-min 1 | /props alias+build |
| dflash2-n7 | PR #27342 tête 5ecbe1a (build local 19/08) | draft-dflash n-max 7 (défaut README) | log serveur `n_max=7` |
| dflash2-n4 | idem | draft-dflash n-max 4 (`-SpecDraftNMax 4`, param ajouté 25/08) | log serveur `n_max=4, block_size=8` |
| dflash2-n2 | idem | draft-dflash n-max 2 (sonde de la reco communautaire « 24 GB culmine à 2 ») | log serveur `n_max=2` |

Garde anti-charabia (première mise en service RÉELLE d'un checkpoint DFlash2
ici — la « serving verification » était NOT-RUN depuis le 19/08) : tir greedy
court, texte lu : « Paris is the capital of France. » — cohérent.
Avertissement bénin au chargement : `failed to measure draft model memory`
(le serveur sert normalement ensuite) — consigné, non expliqué.

## Résultats (décode t/s ; 1 rép/point ; greedy)

| n_past | mtp-b10488 | dflash2-n7 | dflash2-n4 | dflash2-n2 | n7 vs mtp |
|-------:|-----------:|-----------:|-----------:|-----------:|----------:|
|    507 |      79,59 | **127,40** |     123,08 |      94,28 | **+60 %** |
|  8 395 |      84,12 | **128,19** |     115,79 |      89,47 | +52 % |
| 16 205 |      80,81 | **121,01** |     119,29 |      87,88 | +50 % |
| 32 060 |      75,04 |     109,84 | **110,27** |      83,80 | +46 % |
| 62 115 |      74,04 | **116,87** |     110,74 |      81,09 | +58 % |

Prefill (t/s, points 8k→61k) : mtp 2 668→2 215 ; dflash2-n7 2 304→2 044 ;
dflash2-n4 2 314→2 047 ; dflash2-n2 2 309→2 049 — le draft coûte ~8–13 %
de prefill, indépendamment de n-max.

VRAM (nvidia-smi avant→après balayage) : mtp 21 144→21 188 MiB ;
dflash2-n7 23 014→23 064 MiB (+~1,9 GiB vs mtp) ; dflash2-n4
22 456→22 596 MiB ; dflash2-n2 22 156→22 276 MiB. Tout tient sous
24 564 MiB.

Acceptation (log serveur, par tir) : mtp 0,95–0,99 (n-max 2) ;
dflash2-n7 0,51–0,61 ; dflash2-n4 0,70–0,79 ; dflash2-n2 0,84–0,89.
Le mécanisme est cohérent : des blocs plus longs acceptent moins par
jeton mais avancent plus par pas — et le pas gagne.

Contrôle de continuité : le bras mtp-b10488 recoupe la fenêtre 4 du 22/08
(74–84 vs 72–85 t/s aux mêmes points, VRAM 21 144 MiB identique au MiB).

## Lectures

1. **DFlash2 bat le MTP actuel de +46 à +60 % en décode sur TOUT le domaine
   507→62k**, même avec la tête de PR obsolète. Le gain tient en long
   contexte (58 % à 62k) — l'effondrement mesuré le 19/08 était un artefact
   du KV quantifié + binaire v1, pas de DFlash2.
2. **n-max 4 ne bat PAS n-max 7 ici** : égalité à 32k (110,3 vs 109,8),
   n7 devant partout ailleurs (jusqu'à +10 % à 8k). L'affirmation de la
   revue externe (« 4 > 7 de ~29 % à 32k », bench de la PR) NE SE
   TRANSPORTE PAS sur cette carte/ce build — mesuré, pas supposé.
2bis. **La reco communautaire « les cartes 24 GB culminent à n-max 2 » est
   réfutée ici aussi** : n2 rend 81–94 t/s, sous n4 ET n7 à chaque point
   (ordre monotone n2 < n4 ≤ n7). Son argument VRAM ne tient pas non
   plus : n7 ne coûte que ~0,8 GiB de plus que n2 (23,0 vs 22,2 GiB) et
   rien ne sature. Les deux recos externes vont dans le même sens (petit
   n-max) et les deux sont contredites par la mesure locale — la règle
   « re-balayer sur SA config » est la seule qui survit.
3. Le coût : +1,9 GiB de VRAM et ~10 % de prefill. Au budget 24 GB avec
   mmproj (1 136 MiB), dflash2-n7 à ctx 65536 ≈ 24,2 GiB — JUSTE. Texte
   seul : marge 1,5 GiB.
3bis. **mmproj résident (contrainte utilisateur 25/08)** — trois options
   chiffrées, flag `--no-mmproj-offload` vérifié présent sur b10488 ET le
   build PR (défaut = offload GPU) :
   a) mmproj en VRAM + n7 : ≈ 24,2 GiB sur 24,56 — marge ~350 MiB, risqué ;
   b) `--no-mmproj-offload` (projecteur en RAM système) + n7 : VRAM reste
      ≈ 23,1 GiB, marge 1,5 GiB ; coût : encodage image sur CPU (TTFT des
      images seulement, décode texte intact) — À MESURER avant d'adopter ;
   c) mmproj en VRAM + n4 : ≈ 23,7 GiB, marge ~0,8 GiB, décode −3 %
      (110–123 vs 110–128 t/s).

## Deuxième passe — tête fraîche `f7aadef` (build utilisateur-cloné, compilé ici le 25/08)

Le clone humain a débloqué le rebuild (VS2022 + nvcc 12.1, arch 89, cible
llama-server, exit 0) ; binaire installé `llama-cuda-pr27342-f7aadef\`,
allowlisté dans le lanceur, tests 37/37. Décode (t/s), mêmes points :

| n_past | n7 5ecbe1a | **n7 f7aadef** | n4 f7aadef | n7 f7aadef p-min 0.75 |
|-------:|-----------:|---------------:|-----------:|----------------------:|
|    507 |     127,40 |     **133,85** |     129,98 | 132,93 |
|  8 395 |     128,19 |     **133,69** |     122,22 | — |
| 16 205 |     121,01 |     **126,42** |     124,89 | — |
| 32 060 |     109,84 |     **114,53** |     114,99 | 114,09 |
| 62 115 |     116,87 |     **122,08** |     116,10 | 121,87 |

- **La tête fraîche paie +4 à +6 % sur toute la courbe** (le commit
  `Optimize Dflash 2 cost` en chiffres) ; VRAM inchangée (23 006→23 078 MiB).
- **n4 < n7 se confirme sur la tête fraîche** (4 points sur 5 ; 32k à
  égalité) — la réfutation du « 4>7 » tient aussi après l'optimisation.
- **p-min 0.75 : neutre** (<1 % vs n7 nu, 3 points) — la reco communautaire
  « bandwidth-poor » ne s'applique pas au 4090 ; p_min reste à 0.
- Acceptation n7 f7aadef : 0,43–0,61 (inchangée vs 5ecbe1a) — le gain
  vient du coût du draft, pas de l'acceptation.
- Gain total vs MTP actuel : **+53 à +65 %** selon le point.

## Plafonds de contexte (ordre « on peut monter le contexte ? attention aux oom »)

Méthode : prédiction d'abord (65 KiB/jeton de KV f16 mesuré fenêtre 4 +
bases VRAM mesurées ici), puis un serveur à la fois, nvidia-smi en main.

| config (texte seul, f16) | plafond | mesure au plafond | pic VRAM |
|---|---|---|---|
| dflash2-n7 (5ecbe1a) | **80K** (88K = OOM arithmétique : +532 MiB > marge 488) | 105,2 t/s @ n_past 77 415 | 24 076 / 24 564 MiB |
| q38-mtp | **96K** | 64,6 t/s @ n_past 94 173 | 23 428 MiB |
| q38-plain | 128K **chargé** (24 084 MiB, marge 480) | point profond mesuré (relance après interruption non voulue) : **s'effondre** — prefill 72,8 t/s (28,4 min de remplissage !), décode 16,73 t/s @ n_past 123 909 | 24 110 MiB |

**Verdict 128K f16 : charge mais ne sert pas.** Cause non prouvée ; la
marge VRAM de ~450 MiB est le suspect (le même bras en q8/q8 avec ~870 MiB
de marge sert à pleine vitesse, voir 7bis — compatible avec l'hypothèse,
pas une preuve du mécanisme).

**KV quantifié, verdict INITIAL (dépassé le soir même — gardé comme trace) :**
« K q8_0 / V f16 rend 1 538 MiB mais coûte prefill ×38 (68,3 t/s à 14k) et
décode ×4,8 (16,9) — même pathologie que le q8_0/q4_0 des fenêtres 2-3 ;
f16 obligatoire. » Ce verdict était vrai des combinaisons MESURÉES mais la
variable causale n'était pas le type : c'était la MIXITÉ. Voir 7bis.

## 7bis — KV quantifié débloqué : les kernels FA sont symétriques (25/08 soir, ordre « web search : d'autres l'ont fait »)

**Cause racine, prouvée dans nos binaires.** Sans `GGML_CUDA_FA_ALL_QUANTS`
(=OFF dans notre CMakeCache f7aadef ; le zip officiel b10488 est bâti
pareil), le build CUDA ne compile que 4 kernels flash-attention vec :
`f16/f16`, `q4_0/q4_0`, `q8_0/q8_0`, `bf16/bf16`
(`ggml/src/ggml-cuda/CMakeLists.txt:119-124`). Toute combinaison **mixte**
tombe sur un repli silencieux ×25-38, sans warning (issue upstream #24485 :
96 vs 2 361 t/s de prefill). Nos deux essais pathologiques — q8_0/q4_0
(fenêtres 2-3, la reco de la revue externe) et q8_0-K/f16-V (25/08) —
étaient tous deux mixtes. La seule combinaison rapide déjà présente,
q8_0/q8_0 symétrique, n'avait jamais été mesurée.

**Sonde q8_0/q8_0 @65536 (f7aadef n7, protocole identique à la sonde kq8) :**

| point | kq8 mixte (pathologique) | q8/q8 symétrique | f16 n7 (réf.) |
|---|---|---|---|
| ~500, décode | 73,6 t/s | **131,9** | 133,9 |
| ~14k, prefill | 68,3 | **2 316** | ~2 000 |
| ~14k, décode | 16,9 | **129,6** | ~126 |

VRAM 21 202 MiB (−1 862 vs f16). Vitesse f16, KV ÷2 : la pathologie était
le kernel manquant, pas la quantification.

**dflash2 n7 q8_0/q8_0 @131 072 — balayage complet (impossible en f16,
plafond 80K) :** VRAM 23 698 chargé / 23 858 sous charge, marge ~870 MiB.

| n_past | prefill t/s | décode t/s |
|---|---|---|
| 507 | 1 132 | 131,1 |
| 8 395 | 2 299 | 131,6 |
| 16 205 | 2 345 | 125,6 |
| 32 060 | 2 225 | 104,4 |
| 62 115 | 2 011 | 93,4 |
| 99 117 | 1 787 | 74,7 |
| 123 909 | **1 654** | **79,4** |

Au point 123 909 : **×23 en prefill et ×4,75 en décode** vs le plain f16
@128K (72,8 / 16,7). Le remplissage 125k passe de 28,4 min à 75 s.
(Le décode 93,4 @62k est −23 % vs f16@65K — 138 jetons générés seulement,
acceptation spéculative sous KV quantifié à retirer au propre.)

**Sonde q4_0/q4_0 @65536 :** VRAM 20 178 MiB (−2 886 vs f16) ; ~500 :
133,8 t/s (= f16) ; ~14k : prefill 2 276, décode 117,6 (−9 % vs q8/q8).
Aucun effondrement.

**200K atteint et balayé.** `-c 204800` q4/q4 charge à **23 306 MiB**
(prédit 23 272, écart 34 MiB) — le `-c 200000` de la revue externe,
inatteignable en f16 (~28 GiB), est réel sur la 4090 sans rebuild :

| n_past | prefill t/s | décode t/s |
|---|---|---|
| 507 | 1 813 | 134,0 |
| 32 060 | 2 203 | 116,7 |
| 62 115 | 2 011 | 91,7 |
| 123 909 | 1 671 | 73,8 |
| **188 643** | **1 414** | **65,9** |

**MAIS la qualité disqualifie probablement le q4/q4** (question utilisateur
« le dissymétrique q8 q4 était pour la qualité ») — discussion upstream
#23470 (mai-août 2026, KL-divergence sur Qwen2.5-7B + ARC-500) :

| KV | KLD moyen | tokens identiques |
|---|---|---|
| q8/q8 | 0,0018 | 98,0 % |
| q8-K/q4-V | 0,0048 | 96,7 % |
| q4/q4 | **5,51** | **11,6 %** |

« q4_0 sur K seul reproduit l'effondrement ; q4_0 sur V seul change 1/500
réponses. » Le K ne supporte pas 4 bits ; le tableau 200K ci-dessus est un
plafond de VITESSE, pas une config de production. (Chiffres d'un autre
modèle de la famille — à recouper sur le nôtre avant toute décision.)

**Asymétrique q8-K/q4-V ESSAYÉ sur f7aadef (pas seulement déduit)** :
20 422 MiB, ~500 : 75,4 t/s ; ~14k : prefill **36,6** / décode **8,3 t/s**
— effondrement confirmé sur ce binaire (kernel mixte absent). C'est
pourtant LE réglage de qualité (96,7 % ci-dessus) : d'où la route B.

**Route B FAITE le 25/08 au soir** : rebuild f7aadef avec
`-DGGML_CUDA_FA_ALL_QUANTS=ON` (build-faq séparé, l'installé pas touché ;
même empreinte de version — le CHEMIN distingue, allowlist annotée,
tests 37/37 re-passés). Résultat :

- Sonde @65536 : q8-K/q4-V passe de 36,6/8,3 à **2 324 / 122,2 t/s** à
  14k — ×63 récupéré, VRAM 20 690 MiB.
- **Balayage @163 840 (prédit 23 656 MiB, chargé 23 666 — écart 10 MiB ;
  23 832 sous charge, marge ~730)** :

| n_past | prefill t/s | décode t/s |
|---|---|---|
| 507 | 881 | 109,6 |
| 32 060 | 2 217 | **123,4** |
| 62 115 | 2 018 | 92,5 |
| 123 909 | 1 676 | 78,5 |
| **153 759** | **1 544** | **68,5** |

Aucun effondrement. C'est la config d'équilibre : le réglage QUALITÉ de
#23470 (96,7 % tokens identiques) au contexte 160K à 68,5 t/s profond.
Curiosité notée : au point 500 ce build génère 158 jetons (vs 220-224
build standard) et lit 107-111 t/s — sortie différente sous KV quantifié
(longueur de réponse greedy change), pas une régression prouvée ; les
points 32k+ sont au niveau ou AU-DESSUS du q8/q8 standard.
Leviers notés non essayés : `--cache-type-k-draft/v-draft` (KV du DRAFT,
vus dans un repo Windows-DFlash2 tournant q4/q4 @262K sur 4090 moddée
48 GB — sans contrôle qualité apparent). Forks TurboQuant (X-15,
Indras-Mirror TBQ4) : hors upstream, incompatibilités MTP/vision —
seulement si besoin au-delà.

## 7ter — Banc QUALITÉ, étage 1 : needle + greedy-diff (25/08 après-midi, ordre « les deux, attention aux launch nightly »)

Nocturne vérifié AVANT de lancer : aucune tâche installée (noms exacts
`dsh-julia-gate-arret` / `dsh-distiller-nightly` absents de schtasks —
l'installateur attend toujours son exécution manuelle) ; banc calé
l'après-midi, GPU rendu à 0 MiB entre configs.

Outil : `scripts/bench_kv_quality.py` (selftest known-BAD, garde
hors-bornes héritée, codes déterministes par profondeur). Budget needle
512 jetons — leçon mesurée : à 128 jetons la RÉFÉRENCE f16 rendait 3/5,
le modèle brûlait le budget en `<think>` avant d'atteindre delta/echo
(échec de budget, pas de rappel ; protocole corrigé, référence retirée).

**Needle (5 codes plantés à 5/25/50/75/95 %, 1 tir greedy, verite
terrain objective) — TOUT PASSE :**

| config | 60k | 120k | 150k | 190k |
|---|---|---|---|---|
| f16 (réf., plafond 65K) | **5/5** | — | — | — |
| q8/q8 @131K | **5/5** | **5/5** | — | — |
| q8-K/q4-V @160K (FAQ) | **5/5** | **5/5** | **5/5** | — |
| q4/q4 @204,8K | **5/5** | **5/5** | **5/5** | **5/5** |

**L'effondrement q4-K de #23470 NE SE REPRODUIT PAS sur Qwen3.8-27B** au
rappel saillant — dépendance modèle confirmée (leurs chiffres venaient de
Qwen2.5-7B à ctx 512). Le needle ne discrimine aucune config.

**Greedy-diff vs f16 (3 profondeurs, 256 jetons)** : divergence de
trajectoire, pas dégradation prouvée — préfixes identiques 33-256 jetons,
et l'ordre n'est pas stable (q8q4 rend 100 % à 60k là où q8q8 rend 73 %) :
un seul flip de jeton en début de génération suffit à faire diverger tout
le reste (fil du rasoir greedy). Instrument déclaré NON discriminant pour
classer les configs ; c'est le niveau logits qui tranche → étage 2.

**Étage 2 lancé** (ARC-challenge 299 tâches + PPL wikitext-2, 4 configs,
MÊME binaire build-faq pour toutes — le delta mesure la config KV, jamais
la chaîne ; `-fa on` forcé). Jeux téléchargés : wikitext-2-raw-v1.zip
(4,7 Mo, HF ggml-org/ci) et arc-challenge-validation.bin (95 Ko, HF
ikawrakow/validation-datasets-for-llama.cpp). Résultats au retour.

**Ce qui restera non mesuré après l'étage 2** : l'acceptation spéculative
par type de contenu (nos t/s viennent d'un texte de bench favorable) et
la qualité logits AU CONTEXTE LONG (ARC/PPL travaillent court ; le long
n'est couvert que par le needle).

## Validation web du sous-plan (25/08, sur question utilisateur)

Fait par mes propres requêtes le 25/08 :

- **API GitHub (vérifié)** : PR #27342 open/unmerged, tête `f7aadef`
  (24/08), 14 commits ; llama.cpp approuvé par ngxson, en attente du
  mainteneur CUDA. Le « 4 > 7 de 29 % à 32k » est le rapport d'UN testeur
  dans la discussion — pas le bench de l'auteur ; un utilisateur RTX 3090
  rapporte au contraire dflash2 n4 ≈ MTP (« hardware-dependent »).
- **README officiel incoai (recoupé)** : la commande de référence porte
  bien `--spec-draft-n-max 7` — le défaut du lanceur est conforme.
- **Recos communautaires (leads, PAS des mesures)** : « 24 GB culmine à
  n-max 2 » (réfuté ci-dessus), « p-min 0.60–0.75 sur les rigs limités en
  bande passante » — à sonder sur le NOUVEAU build seulement : notre
  5ecbe1a est ANTÉRIEUR au commit `Add p_min in DFlash2` (21/08), le
  serveur tourne à p_min=0.00.
- Caveats de la PR consignés : bug mrope corrigé mi-PR (« GGUF will need
  to be reconverted » pour la vision — notre usage est texte seul),
  trous positionnels du cache draft avec images (issue #27408, HTTP 500),
  kernel top-k custom ±2–5 %.

## Limites honnêtes

- **Build 5ecbe1a = tête du 18/08, 13 commits derrière f7aadef (24/08)**,
  dont `Optimize Dflash 2 cost`, `Revert draft sampling in rejection
  sampling`, `Gate output transforms on DFlash2`, `fix the mrope bug`,
  `Add p_min in DFlash2`. Ces chiffres MINORENT vraisemblablement la tête
  courante et la lecture n4-vs-n7 peut changer avec l'optimisation.
  Le rebuild à f7aadef est en attente (clone bloqué par le classifieur de
  permissions ; commande fournie à l'utilisateur).
- 1 répétition par point (méthodo fenêtre 4) ; le plancher de bruit
  high-vs-xhigh de la fenêtre 5 suggère quelques pourcents.
- Greedy (temp 0) : régime FAVORABLE à la spéculation ; à temp 0.6 les
  acceptations baissent (fenêtre 1 : mtp 0,80 à temp 0.6 vs 0,95–0,99 ici).
- PR #27342 toujours open/unmerged (25/08) : rien ici n'est « stable amont ».
- Décision du rule-gate : ce sont des t/s serveur ; la métrique de décision
  reste le wall-clock médian par tâche résolue (harnais A/B, fenêtre 6).
