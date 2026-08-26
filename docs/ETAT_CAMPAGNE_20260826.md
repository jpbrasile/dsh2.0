# État de la campagne au 26/08/2026 — à relire après compaction

Ce fichier existe pour survivre à une compaction. **Aucun chiffre ici n'est une
mesure fraîche** : chacun porte sa commande de re-mesure. Un nombre repris d'un
résumé sans être re-mesuré est une affirmation, pas un résultat.

> **Lire la section 8 en premier.** Elle date de la soirée du 26/08 et prime sur
> les sections 1 à 5 partout où elles se contredisent.

---

## 1. Ce qui tourne, ce qui est arrêté

| quoi | état | note |
|---|---|---|
| GPQA bras A (8192, tournant) | **ARRÊTÉ à 55 appels** | arrêté sur demande le 26/08 pour optimisation |
| chaîneur bras B (2048) | **ARRÊTÉ** | tué avant le bras A, sinon il l'aurait armé tout seul |
| bras B `local_q4_t1_b2048_tournant.jsonl` | **inexistant** | jamais démarré — vérifier avant toute affirmation |
| llama-server 8005 | **debout** | `--parallel 1`, specdec dflash2 actif |
| proxy 8009 | **relancé propre** | PID à re-vérifier ; sonde de préfixe ACTIVE ; journal `wire_sonde_20260826.jsonl` |
| banc polyglot dsh | terminé | 6 exercices |
| banc polyglot pi | terminé | 6 exercices |

Re-mesurer :
```
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='node.exe' OR Name='llama-server.exe'\" | Where-Object { $_.CommandLine -match 'gpqa_diamond|pilote.py|proxy.mjs|llama-server' } | Select-Object ProcessId, CommandLine"
```

---

## 2. Le chantier ouvert : optimiser le bras GPQA

**Diagnostic fait, correctif NON appliqué.**

- 55 appels, **80 s médians**, débit 69,1 jet/s, **6018 jetons de sortie
  médians** pour un QCM à 4 options. Projection : 4,1 h pour 198 questions.
- **Goulot identifié : `--parallel 1` sur llama-server.** Le client
  `--parallele 1` n'était pas un choix mais une conséquence.
- Le contexte serveur est `--ctx-size 163840`. llama-server répartit le
  contexte entre slots : `--parallel 8` donnerait 20 480 jetons par slot,
  suffisant pour ~250 d'invite + 16 384 de sortie. **Aucun besoin de toucher au
  contexte.**
- **Obstacle non levé** : le décodage spéculatif est actif
  (`--spec-type draft-dflash -md ... --spec-draft-n-max 7`). Spéculatif et
  lot se marient mal. **À trancher par un A/B, pas par hypothèse.**
- `start_llama_qwen38_27b_specdec.ps1` **n'expose pas** de paramètre
  `-Parallel` (vérifié sur les `param()`). Il faut l'ajouter ou passer outre.

Re-mesurer l'argv vivant :
```
powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object -First 1).CommandLine"
```

**Décision à prendre** : A/B de 20 questions, `--parallel 1` + specdec (config
actuelle) contre `--parallel 8` sans specdec. Comparer le temps de paroi pour
20 questions. Puis **redémarrer le bras A de zéro** sous la config retenue :
les 55 appels actuels ne sont pas comparables à des appels servis autrement.

---

## 3. Pré-enregistrement : trois révisions, toutes commitées avant leurs données

- **Rév. 1** : rotation tournante, 198 questions × 1 appel.
- **Rév. 2 (26/08)** : règle 3 scindée. **3a** coupure au budget = MESURE,
  gardée et appariée (elle rend une réponse). **3b** troncature au plafond de
  sortie = non-mesure, exclue et comptée. **3c** les deux calculs publiés côte
  à côte ; s'ils se contredisent, le balayage est non concluant.
- **Rév. 3 (26/08)** : la règle 6 abandonne les 792 appels. Mesuré :
  **78 % de la variance est la dispersion des difficultés**, incompressible.
  198×4 → ± 2,5 pt ; 198×1 → ± 3,2 pt. Quadrupler les appels achète 0,7 point.

Re-mesurer : `python scripts/gpqa/cout_de_diviser.py local_q4_t1_budget512.jsonl`

---

## 4. Chiffres publiés qui ont bougé — et un qui n'existe plus

| bras | avant | après Rév. 2 | encadrement des non-mesures |
|---|---|---|---|
| 512 nu | 68,7 % | **69,9 %** | [68,7 ; 71,2] — largeur 2,5 pt, tient |
| illimité | 81,2 % | — | **[81,2 ; 100,0] — largeur 18,8 pt, PAS de chiffre publiable** |

Le 81,2 % était la **borne basse présentée comme un point**. **Rattrapage à
32768 dû** sur les 5 appels tronqués du bras illimité et les 7 du bras 512,
symétriquement, **avant toute publication**.

**Limite connue** : dans le bras 512 **nu**, les coupures au budget sont
invisibles au classificateur — pas de message de transition, donc pas de
témoin. Son 69,9 % reste un mélange.

Re-mesurer : `python scripts/gpqa/depouiller_gpqa.py local_q4_t1_budget512.jsonl`

---

## 5. dsh contre pi : résolu, sauf la cause racine

**Verdicts identiques 5 fois sur 5** (dsh 2/5, pi 2/5). Les échecs sont ceux du
modèle en variante D à un tour, pas du harnais. Ce qui les sépare est le temps :
**7510 s contre 2356 s, soit 3,2×**.

Cause établie : **cache 24,7 % contre 78,3 %**. À contexte comparable — et même
défavorable — un appel non caché de dsh met 29,4 s contre 11,3 s pour un appel
caché. Ce n'est pas du décodage mais du **temps de premier jeton**.

Écartés par mesure : concurrence, dérive fournisseur, longueur de contexte,
`cache_control` manquant (le cache est **automatique** sur cette route :
86,9 % sans rien poser, fournisseur **Phala**), ordre des 25 outils (stable).

**NON TROUVÉ : où dsh casse son préfixe.** C'est ce que la sonde doit dire.

Re-mesurer :
```
python scripts/polyglot_dsh/ou_passe_le_temps.py ../bench_julia_effort/wire_fumee_durs.jsonl "dsh=13:11,15:17" "pi=15:17,"
python scripts/polyglot_dsh/bilan_fumee.py
```

---

## 6. Red team z.ai — 12 constats, 3 traités

Transcript : `redteam/reglages_bench_20260826.md`.

**Traités et vérifiés** : #1 (le dépouilleur ignorait la troncature — confirmé
sur le code), #2 (exclure les coupées supprime la question entière — confirmé
sur données vivantes à **44 %** de coupées, pire que les 29 % annoncés),
#11 (garde de budget non ancrée — **confirmée par test direct**, un serveur à
20480 passait la garde 2048 ; corrigée et testée sur 5 cas).

**Non traités** : #3 (échelon manquant dans la règle 5), #4 (le χ² teste la
préférence de lettre, pas la position), #5 (écho `$LETTER` — **0 occurrence
mesurée sur 17 coupées**, risque réel mais nul en pratique), #6 (température
1,0 contre 0,6 recommandé), #7 (`reponse[-24000:]` trop court), #8 (KV
quantifié et specdec non vérifiés — **recoupe le chantier §2**), #9 (le mur
1800 s compté FAIL par l'instrument), #10 (sonde d'effort à n=1 sans
fournisseur enregistré).

---

## 7. Mes erreurs de la journée, pour ne pas les refaire

1. **Régression à R² 0,86 avec un coefficient négatif** sur le préfill caché.
   Un R² élevé n'est pas un permis d'interpréter — colinéarité. Garde-fou de
   signe ajouté ; sans lui je publiais « 1270 s économisables », un nombre
   inventé.
2. **« Dérive du fournisseur »** annoncée sur un effet de composition entre
   tranches de contexte. Corrigé avant publication.
3. **« Le web donne la cause »** (`cache_control` manquant) — réfuté par sonde
   directe. La doc visait Alibaba ; le modèle est servi par Phala.
4. **Test d'extension des rôles** : `proxy.mjs:155` ne journalisait que
   `slice(0, 3)`. Je mesurais une tautologie.
5. **Compteur d'échos `$LETTER`** : 16/16 avec 0 non-parsé — il comptait le
   message de transition lui-même, stocké dans le bloc de pensée.
6. **Auto-match de processus** : mes filtres `-match 'chainer'` ont matché ma
   propre commande d'inspection, deux fois. Exclure `$PID`.

---

## 8. Soirée du 26/08 — ce qui a bougé depuis la section 1

**Cette section prime sur les sections 1 à 5 partout où elles se contredisent.**

### Ce qui tourne au moment où j'écris

| quoi | état | re-mesure |
|---|---|---|
| **GPQA bras de PRODUCTION** | **EN VOL** — `local_q4_t1_libre_tournant.jsonl` | `wc -l scripts/gpqa/local_q4_t1_libre_tournant.jsonl` |
| llama-server 8005 | debout, **alias `specdec-q38-plain`** | argv sur le processus vivant |
| proxy 8009 | debout, sonde active | `wire_sonde_20260826.jsonl` |

Le bras de production : **budget −1** (aucune guillotine), **plafond de sortie
32768**, **198 questions en position tournante**, un appel par question,
température 1.0 / top_p 0.95 / top_k 20, `--delai 1800`. **Sans spéculation** —
voir ci-dessous. Rythme mesuré sur les 6 premières : 140 s/question, projection
**7,7 h**. Une question sur six tape le plafond de 32768.

Le serveur n'est plus en dflash2 : `relance_serveur_illimite.ps1 -Config
q38-plain`, **même binaire** (build `src-dflash2`) des deux côtés.

### Quatre choses tranchées, toutes au carnet

1. **La règle 4 du pré-enregistrement classait à l'envers.** Un serveur lancé
   sans `--reasoning-budget-message` n'injecte aucun marqueur : le témoin par
   marqueur est alors muet par construction. Sur le bras 512 nu, marqueur
   0/293, **mur de jetons 248/293 (84,6 %)**. Règle 4 réécrite en disjonction
   des deux témoins. Ma phrase du matin — « le bras 512 n'a jamais existé,
   c'est une copie renommée » — était **fausse**.
2. **Le balayage de budget comparait deux guillotines.** Courbe de coupure
   mesurée sur 55 questions : 512 → 89,1 %, 2048 → **63,6 %**, 8192 →
   **45,5 %**, ≥ 12288 inestimable [0,0 ; 45,5]. La calibration de 8192 sur
   8 questions est caduque.
3. **Le décodage spéculatif n'est PAS sans perte en glouton.** Trois jambes :
   A1/A2 (plain, deux processus) 12/12 identiques ; B1/B2 (dflash2, même
   processus) 12/12 identiques ; **A1/B1 12/12 divergents**. Les deux témoins
   écartent le « serveur non reproductible ». Coût du choix : 46,9 t/s au lieu
   de 103,6.
4. **Le rapport dsh/pi est la PENSÉE, pas le cache.** Mesure appariée sur
   `go/beer-song` : dsh 1383,0 s contre pi 282,5 s (**4,9×**), même verdict
   FAIL. Cache servi 8,0 % contre 7,3 %, parts prefill/décode identiques à
   0,1 point — le cache est commun aux deux et ne peut pas expliquer un écart
   entre eux. Cause : 29 632 jetons générés contre 4 813, dont **17 722 de
   pensée contre 1 336** (611 par appel contre 95, à effort nominal égal).
   Contrefactuel : un cache parfait ne rendrait que **1,39×**.

### Livrables

| | état |
|---|---|
| 1 — polyglot agentique complet, variante D | **bloqué par la carte** jusqu'à la fin du bras GPQA. Amont : local (le crédit OpenRouter, 11,50 $, ne finance pas 225 exercices). |
| 2 — chiffre GPQA local | **en vol**, ETA ~7,7 h |
| 3 — comparaison pi/dsh | **condition levée** : le rapport est élucidé (mécanisme nommé, cause cache écartée par mesure appariée) |

### Ce qui reste ouvert

- ~~Pourquoi `medium` vaut 6,4× plus de pensée chez dsh que chez pi.~~
  **Mesuré, et ce n'est pas un réglage.** Le proxy journalisait déjà
  `reasoning_effort` ; son absence dans un enregistrement signifie que l'agent
  ne l'a pas envoyé, pas que l'instrument est aveugle. Les deux agents envoient
  **exactement** `reasoning_effort: "medium"`, `max_tokens 16384`, `1 / 0,95 /
  20 / 0`. L'écart vient donc de **l'invite**, seule chose qui diffère.
  Reste ouvert : *quelle partie* de l'invite (outils, système, structure) —
  isoler demanderait un bras qui ne fait varier que la liste d'outils.
- **B2** (rattrapage 32768 sur les bras gelés), **B3** (KV q8/q4 contre f16) —
  les deux demandent la carte, donc après le bras de production.
- Le levier « 25 outils contre 4 » côté dsh : réel, mais borné, le prefill ne
  pesant que 35 % de la paroi.

### Erreurs de la soirée, pour ne pas les refaire

- **Un bras a failli sortir mal étiqueté.** Le lanceur ne passait pas
  `--modele` ; `gpqa_diamond.py` écrivait son défaut et le bras joué sur le
  serveur plain sortait marqué `dflash2` dans ses 198 enregistrements.
  llama-server sert la requête quel que soit le champ `model` : rien ne lève à
  l'exécution. Rattrapé après une question. Le lanceur lit désormais l'alias sur
  le processus vivant et refuse (exit 6) s'il n'y en a pas.
- **Une renomination a fait sortir un `.jsonl` GPQA du `.gitignore`.** Le motif
  visait `*.jsonl` ; `x.jsonl.avorte` n'était plus couvert, sur un dépôt
  **public** avec des données sous accès restreint. Motif élargi aux suffixes.
- `pilote.py --agent pi` demande **deux** drapeaux que dsh n'exige pas :
  `--accueil-pi` et `--dotenv`. Sans eux le pré-vol refuse — c'est à ça qu'il
  sert, mais ça coûte deux tours.
