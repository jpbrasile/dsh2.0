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
