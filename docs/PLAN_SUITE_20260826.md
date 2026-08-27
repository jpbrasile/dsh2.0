# Plan de la suite — 26/08/2026, écrit pour être attaqué

Ce fichier est le **plan prévu**. Il est écrit avant exécution, il porte ses
chiffres avec la commande qui les a produits, et il nomme ce qu'il ne prouve
pas. Il est destiné à un red team.

---

## 0. Ce qui est mesuré, ce qui sera revendiqué

**Objet** : Qwen3.8-27B Q4_K_M servi par llama.cpp sur une RTX 4090, mesuré sur
GPQA Diamond, 198 questions, **un appel par question** (rotation tournante,
règle 6 révision 3).

**Revendication visée** : un taux d'exactitude avec sa barre, mis en regard du
chiffre publié pour ce modèle en BF16, et le budget de pensée retenu par le
balayage pré-enregistré.

---

## 1. État re-mesuré le 26/08 à 16:20 — aucun chiffre repris d'un résumé

Bras A (budget 8192, tournant), `scripts/gpqa/local_q4_t1_b8192_tournant.jsonl` :

```
appels                 : 55
justes                 : 46  (83,6 %)
tronques (length)      : 0
coupes au budget       : 25  (45,5 %)
secondes  med/moy/max  : 80,1 / 73,6 / 137,6
jetons entree med      : 245
jetons sortie med/moy  : 6018 / 5090
debit median (jet/s)   : 70,8
temps de paroi cumule  : 4050 s = 1,13 h
projection 198 appels  : 4,41 h (a la mediane)
```

argv serveur vivant, PID 46184, démarré à 14:12:06 :

```
llama-server.exe --model Qwen3.8-27B-Q4_K_M.gguf --host 127.0.0.1 --port 8005
  --ctx-size 163840 --flash-attn on --cache-type-k q8_0 --cache-type-v q4_0
  --batch-size 2048 --ubatch-size 512 --n-gpu-layers 99 --parallel 1 --jinja
  --reasoning-format none --reasoning-budget 8192 --temp 0.6 --top-k 20
  --top-p 0.95 --min-p 0 --presence-penalty 0.0 --repeat-penalty 1.0
  --reasoning-budget-message "..." --alias specdec-q38-dflash2
  --spec-type draft-dflash -md Qwen3.8-27B-DFlash2-Q4_K_M.gguf
  --spec-draft-n-max 7
```

**Ce que ces deux blocs disent ensemble.** 6018 jetons / 70,8 jet/s = 85 s, soit
la médiane de 80 s à la dispersion près : **le temps est de la génération pure**.
L'invite fait **245 jetons** — il n'y a pas de préfixe à cacher, et le client ne
pèse rien. Le seul levier de débit est côté serveur.

Rien ne tourne : ni `gpqa_diamond.py`, ni le chaîneur. Le bras B
(`local_q4_t1_b2048_tournant.jsonl`) **n'existe pas**.

---

## 2. Étape 1 — A/B serveur sur le débit

**Hypothèse à tester** : le décodage à lot 1 d'un 27B Q4 est limité par la bande
passante mémoire ; servir 8 séquences concurrentes coûte presque le même temps
qu'une seule, donc le débit agrégé monte quasi linéairement.

**Ce qui la contredit aujourd'hui, sans mesure** : le commentaire de
`scripts/gpqa/gpqa_diamond.py:316-319` — « Le local se fait en séquentiel
(`--parallele 1`) : une seule carte, la concurrence n'y gagne rien et fausse les
temps par appel. » C'est une affirmation, pas un résultat. Le red team du 26/08
l'a d'ailleurs reprise à son compte et classée « à son optimum ».

**Design.**

- 20 questions, mêmes `id`, même graine, même rotation tournante, **un fichier
  JSONL neuf par configuration** (jamais de mélange de régimes serveur).
- **C1, témoin** : argv actuel — `--parallel 1`, specdec actif, client
  `--parallele 1`.
- **C2** : `--parallel 8`, **specdec retiré**, client `--parallele 8`.
- **C3** : `--parallel 8`, specdec actif, client `--parallele 8`.
- Contexte : `--ctx-size 163840` inchangé ; à `--parallel 8` chaque slot reçoit
  20 480 jetons, soit ~245 d'invite + 16 384 de sortie avec marge.
- **Mesure primaire** : temps de paroi des 20 questions. Effet attendu ≥ 2× ;
  une seule mesure par config suffit à trancher un effet de cette taille.
- **Garde-fous de validité** : le taux de coupure au budget et la médiane de
  jetons de sortie doivent rester du même ordre qu'en C1. S'ils bougent, la
  configuration est suspecte et on ne conclut pas sur la vitesse seule.
- **Ce que ce test n'établit PAS** : l'équivalence en exactitude. À n = 20, un
  écart de 5 points est invisible. C'est assumé, pas ignoré.
- Redémarrer le serveur entre configurations demande une **autorisation
  humaine** (règle « irréversible / ressource partagée »).

---

## 3. Étape 2 — bras A relancé à zéro

Les 55 appels existants **ne sont pas fusionnables** avec des appels servis sous
une autre configuration serveur. Fichier neuf, 198 appels, config retenue à
l'étape 1. Les 55 appels sont conservés comme partiel daté, jamais concaténés.

---

## 4. Étape 3 — bras B, budget 2048

Même configuration serveur que le bras A **à `--reasoning-budget` près**.

**Point de validité qui décide de tout** : la comparaison A contre B n'exige pas
que la configuration retenue à l'étape 1 soit « la bonne ». Elle exige seulement
qu'elle soit **la même des deux côtés**. Le risque lié au changement de
configuration porte sur le **chiffre absolu** comparé au BF16 publié, pas sur le
départage des budgets.

---

## 5. Étape 4 — décision de budget

Règles du pré-enregistrement telles qu'amendées : 3a (coupure au budget =
mesure, gardée et appariée), 3b (troncature au plafond = non-mesure, exclue et
comptée), 3c (les deux calculs publiés côte à côte), 5 (échelle de décision),
6 révision 3 (198 appels, barre attendue ± 3,2 pt).

---

## 6. Étape 5 — rattrapage 32768, avant toute publication

5 appels tronqués du bras illimité et 7 du bras 512, **relancés symétriquement**
à plafond 32768. Sans lui, le bras illimité n'a pas de chiffre publiable :
l'encadrement de Manski vaut [81,2 ; 100,0], largeur 18,8 pt.

---

## 7. Proposition à trancher — « GPQA Diamond complet en local avec pi »

**Ce qui est vérifié dans le code**, et non supposé :

- `pilote.py:741` — `--agent` accepte `dsh` ou `pi`, et ce pilote est le banc de
  **code** (Exercism polyglot), pas un client de QCM.
- `pilote.py:880` — pi est lancé comme
  `node cli.js -p --provider ... --model ... --thinking ... -a --no-session --`,
  dans un conteneur, avec ses outils.
- `gpqa_diamond.py` parle directement à une API OpenAI, un appel par question.
  **Il n'existe aujourd'hui aucun chemin GPQA vers pi** ; il faudrait le
  construire.

**Ce que j'en conclus, et que je veux voir attaqué** :

1. L'avantage mesuré de pi sur dsh (3,2× en temps) était du **cache d'invite**
   sur des contextes de 20 à 40 k jetons chez un fournisseur distant. Sur GPQA
   l'invite fait **245 jetons** : il n'y a rien à cacher.
2. Le temps est **100 % de la génération** (§1). Changer de client ne change pas
   le débit du serveur. Le levier est `--parallel`, pas le harnais.
3. Un harnais d'agent rend le **budget de pensée inopérant** : sur plusieurs
   tours, le modèle réfléchit 8192 jetons *par tour*. Tout le balayage de budget
   perd son objet.
4. Des outils (shell, fichiers) transforment la mesure en **« GPQA avec
   outils »**, qui n'est plus comparable aux chiffres GPQA publiés.
5. Le coût GPU **monte** : invite 20 à 40× plus grosse, boucle multi-tours.

**Décision proposée** : **non** comme remplacement de la mesure brute ; **oui**
comme mesure séparée et explicitement étiquetée « GPQA agentique, avec outils,
non comparable au tableau GPQA », après la mesure brute, si le temps de carte le
permet.

---

## 8. Étape 6 — où dsh casse son préfixe

La sonde est posée et **active** dans `scripts/bench_julia_effort/proxy.mjs`
(`prefix_h`, `msg_chars`, `roles` complets, `fournisseur`), journal
`wire_sonde_20260826.jsonl`, proxy PID 31104. Il faut **un nouveau run dsh à
travers le proxy** pour qu'elle dise quelque chose. Aucune donnée pour l'instant.

---

## 9. Publication

Rien ne sort avant l'étape 5. Le 81,2 % du bras illimité est une borne basse
présentée comme un point ; il ne doit pas reparaître.

---

## Ce que je veux voir attaqué en priorité

1. L'hypothèse « batch 8 est presque gratuit » — si elle est fausse, l'étape 1
   coûte du temps de carte pour rien et le plan entier repose dessus.
2. Le fait de **jeter 55 appels**. Est-ce vraiment nécessaire, ou est-ce une
   prudence qui coûte 1,1 h de carte sans rien acheter ?
3. L'argument « même config des deux côtés suffit » (§4). Où se casse-t-il ?
4. La configuration serveur elle-même : KV `q8_0`/`q4_0`, specdec dflash2 à
   `n_max 7`, `--ctx-size 163840` pour des invites de 245 jetons. Qu'est-ce qui,
   là-dedans, peut changer **l'exactitude** et pas seulement la vitesse ?
5. Le refus de la proposition pi (§7). Y a-t-il une lecture de cette proposition
   sous laquelle j'ai tort ?
6. L'ordre des étapes. Est-ce que je mesure la bonne chose en premier ?

---

# Révision du 26/08/2026, 21:00 — ce que la soirée a cassé dans ce plan

Ce bloc est **ajouté**, pas substitué : le plan ci-dessus reste lisible tel
qu'il a été soumis au red team à 16:22. Ce qui suit dit lesquelles de ses
affirmations ne survivent pas à la mesure, et pourquoi.

## R1. §7.1 est FAUX — le cache n'est pas le levier

Le plan écrivait : « L'avantage mesuré de pi sur dsh (3,2× en temps) était du
**cache d'invite** sur des contextes de 20 à 40 k jetons chez un fournisseur
distant. »

**Mesuré le 26/08 au soir, sur le fil, serveur local.** Le préremplissage ne
pèse que **6 % de la paroi** d'un exercice local ; le cache local tourne à
**93–95 %** contre 19,4 % chez AkashML, et cet écart de taux ne peut pas
déplacer plus de 6 % du mur. Un cache parfait ferait gagner moins de 1,4×, pas
3,2×.

**Confirmé le soir même par le bras qui manquait** — pi et dsh sur le MÊME
serveur, trois tirages chacun :

| | dsh (9 tirages) | pi (3 tirages) |
|---|---|---|
| **cache d'invite** | **92,8 – 95,1 %** | **89,9 – 93,9 %** |
| décodage (j/s) | 42,8 – 44,5 | 45,6 – 45,8 |
| jetons produits | 11 101 – 27 330 | 4 028 – 6 163 |
| paroi (s) | 269 – 664 | 95 – 144 |

**dsh cache MIEUX que pi et reste 3× plus lent.** L'hypothèse du plan n'était
pas approximative, elle était **à l'envers**. La correction du cache, que le plan
qualifiait de « prioritaire et non cosmétique », est **retirée** du chemin
critique.

**Le 3,2× est un écart de VOLUME.** Rapport de paroi 3,16×, rapport de jetons
3,07× : ils coïncident à 3 %, et le débit est identique des deux côtés. dsh est
3× plus lent parce qu'il génère 3× plus. Le 3,2× d'AkashML sur six exercices se
reproduit à 3,1× sur le 4090 sur un exercice répliqué — deux amonts, deux
protocoles, même facteur.

## R2. Ce que la soirée a établi et qui n'était dans aucun plan — la partition

Sur **neuf tirages** de dsh (trois compositions × trois tirages) du même exercice,
même serveur :

| grandeur | dispersion mesurée | verdict |
|---|---|---|
| débit de décodage | 42,8 – 44,5 j/s (**±1,9 %**) | reproductible |
| taux de cache (5 tirages entiers) | 92,8 – 95,1 % | reproductible |
| jetons produits | 11 101 – 27 330 (**×2,46**) | **non** reproductible |
| paroi | 269 – 664 s (**×2,47**) | **non** reproductible |
| pensée par appel (bras @10) | 564 – 1 847 car. (**×3,3**) | **non** reproductible |

Le taux de cache est donné hors tirages morts au plafond : une fugue tue le
tirage avant qu'il ait fini de construire son cache (56,3 % à 69,0 %), ce qui
est une conséquence de la mort, pas une mesure du cache.

**Règle qui en découle, et qui vaut pour toute la suite du plan** : une grandeur
qui agrège des centaines d'événements *à l'intérieur* d'un tirage se reproduit ;
une grandeur qui est une décision d'agent propagée sur le tirage ne se reproduit
pas. **Aucun facteur sous ~1,5× ne sera lisible à un tirage.** Toute comparaison
d'agents publiée sans réplique est à refaire ou à retirer.

**pi, lui, se réplique** : paroi ×1,52, jetons ×1,53, pensée par appel ×1,08
(311 → 337 caractères) contre ×3,3 chez dsh. La dispersion mesurée n'est donc pas
une propriété de la tâche à température 1,0 — c'est une propriété de dsh.

Trois affirmations publiées plus tôt tombent sous cette règle et sont
**abandonnées** : « retirer 15 outils fait monter la pensée de +39 % »,
« Venice pense 3,2× plus », et la *magnitude* (non la direction) de « le local
génère 2,54× moins de jetons ».

## R3. §8 « où dsh casse son préfixe » — la question était mal posée

La sonde de préfixe a tourné. Elle ne trouve pas de rupture de préfixe à
réparer : **le cache local tient à 93–95 %**. dsh ne casse pas son préfixe sur
ce serveur. L'étape 6 est donc **close sans correctif** — ce qu'elle cherchait
n'existe pas ici.

## R4. Trois compositions de dsh essayées, aucune ne déplace rien

| bras | outils | système (car.) | paroi des 3 tirages (s) |
|---|---|---|---|
| standard | 25 | 4 327 | 405\* / 547 / 486 |
| réduit | 10 | 1 765 | 535 / 269 / 664 |
| minimal | 2 | 357 | 387\* / 387\* / 353 |

\* mort au plafond (`finish_reason: length`, 16 384 jetons pile).

Un facteur **12 sur la taille du prompt système** et un facteur **12,5 sur le
nombre d'outils** ne sortent pas de la dispersion, et le bras minimal — qui offre
**moins** d'outils et **moins** de système que pi — reste **3× plus lent que
lui**. La piste « un réglage de composition d'invite rendra dsh aussi rapide que
pi » est **fermée** sur ces trois points.

Ce qui reste et n'a pas été isolé : la formulation du prompt système, la
structure des messages, la boucle d'agent. Ces trois-là varient ensemble entre
les deux agents. Les deux ponts d'écosystème publiés ne les séparent pas :
`pi-dsh` laisse dsh posséder prompt, mémoire et boucle (et démarre en
`danger-full-access`, épinglé à dsh 0.1.0-rc.6) ; `pi2dsh` dit explicitement ne
remplacer ni la boucle ni le prompt système de dsh. **Aucun des deux n'est un
instrument de décomposition**, et aucun ne sera installé sans décision humaine —
installer l'un ou l'autre modifierait l'agent sous test au milieu de la
campagne.

## R5. Un mode d'échec nouveau, et il est de dsh — la fugue au plafond

**Quatre tirages de dsh sur neuf** meurent en `finish_reason: length`, 16 384
jetons pile, en **un seul appel** de ~370 s. Le bras minimal en meurt **2 fois
sur 3** — le plus léger des trois est le plus atteint. **Aucun tirage de pi n'en
meurt.** Forme invariante : quatre appels courts, puis la fugue. Elle survient à
25 outils comme à 2 : **la composition de l'invite ne la cause pas**.

Les deux canaux peuvent fuguer, ce qui interdit une explication simple :

| tirage | jetons | pensée (car.) | visible (car.) |
|---|---|---|---|
| `m1` | 16 384 | 0 | 54 334 |
| `m2` | 16 384 | 50 225 | 138 |

Ce mode avait été attribué à Venice le 26/08 18:55 sur un tirage unique. **C'est
faux** : il est de dsh, sur le serveur local, et il n'a rien à voir avec le
fournisseur.

## R6. Ce qui reste vrai dans le plan, et ne bouge pas

- §1, §3, §4, §5, §6 — la campagne GPQA, ses règles de coupure, le rattrapage
  32768. Rien de la soirée ne les touche.
- §2 / B4 — **tranché par l'opérateur** : `--parallel 8` n'est pas finançable en
  VRAM (107 MiB libres sur 24 564 avec le brouillon dflash2, un contexte de
  brouillon par slot). La cellule C2/C3 sort du plan.
- §7 — la décision « pas de GPQA via pi comme mesure brute » tient. Le repli
  « GPQA agentique étiqueté » reste abandonné.
- « Aucun redémarrage du serveur sans autorisation humaine, à chaque fois. »
  **B3** (KV q8/q4 contre f16) en dépend et reste donc **en attente**, pas
  oublié.
- **B1 n'est plus en attente : il est FAIT, et la réponse est NON.** 12 questions,
  `temperature 0`, `top_k 1`, graine fixe, même binaire des deux côtés — plain
  contre dflash2 divergent **12/12**, premier octet différent entre 58 et 1113,
  les deux témoins muets (plain/plain 12/12 identiques sur deux processus,
  dflash2/dflash2 12/12 identiques). **Le décodage spéculatif avec le brouillon
  dflash2 n'est pas sans perte**, et le bras de production tourne donc sans lui
  (46,9 j/s au lieu de 103,6). Statut reporté dans `SPECDEC_4090_BENCH.md`, qui
  le listait encore en NOT-RUN.

## R7. L'ordre pour la nuit du 26 au 27

| # | quoi | carte | état |
|---|---|---|---|
| 1 | bras GPQA de production, 198 tournants, plafond 32768 | oui, ~4,4 h | **en cours** |
| 2 | dépouillement `--premier` du bras, deux calculs publiés | non | après 1 |
| 3 | **B2** rattrapage 32768 des bras gelés (5 + 7 appels) | oui, ~1,5 h | après 1 |
| 4 | **B3** KV q8/q4 contre f16 | redémarrage | **bloqué, autorisation** |
| 5 | **B6** polyglot agentique complet | oui, longue | après 3 |

**B1 est sorti de la file : fait le 26/08 à 17:43, réponse NON** (voir R6).

Rien ne sera lancé cette nuit qui demande un redémarrage du serveur.

---

# Révision du 26/08/2026, 21:20 — B3 retiré, et le livrable 1 change de bras

## R8. B3 (KV q8/q4 contre f16) est RETIRÉ, pas reporté

Le plan le gardait au motif du constat #2 du red team (« profondeur × KV »).
Il est **déjà répondu, et par un instrument plus fin**. Quatre configurations KV,
même binaire, mesurées le 25/08 — chiffres relus dans les fichiers de sortie,
pas dans les messages de commit :

| config KV | ARC-Challenge (299 tâches) | PPL wikitext-2 | needle |
|---|---|---|---|
| f16 | 52,17 ± 2,89 | 6,9551 ± 0,045 | 5/5 @60k |
| q8/q8 | 51,84 ± 2,89 | **6,9551** (identique) | 5/5 @60k, 120k |
| **q8-K/q4-V** ← production | **51,84 ± 2,89** | 6,9628 (**+0,11 %**) | 5/5 @60k, 120k, 150k |
| q4/q4 | 52,17 ± 2,89 | 6,9686 (+0,19 %) | 5/5 jusqu'à **190k** |

Fichiers : `reports/specdec_20260825_ctxsweep_dflash2/stage2_{arc,ppl}_*.txt`,
sonde `scripts/bench_kv_quality.py`.

**Quatre raisons de le retirer.**

1. L'effet est borné et nul : la config de production est à **0,33 pt** de f16
   sur ARC, barre ±2,89 ; +0,11 % en perplexité.
2. B3 serait **strictement plus faible** : 40 questions appariées contre 299
   tâches. Résoudre 0,33 pt demanderait de l'ordre de 10⁴ questions — GPQA
   Diamond en contient 198 en tout.
3. **Sa raison d'être ne s'applique pas à GPQA** : l'invite fait 245 jetons, il
   n'y a aucune profondeur d'entrée à faire interagir avec le KV ; et le needle
   tient 5/5 jusqu'à 190k, très au-delà du plafond de 32 768.
4. Il coûte un redémarrage du serveur (donc une autorisation) et
   l'interruption du bras de production.

**Réserve déclarée** : ARC et PPL ne sont pas GPQA, et un effet spécifique à une
tâche n'est pas logiquement exclu. Il devrait être invisible sur trois
instruments et visible sur un quatrième à n = 40. Ce n'est pas un risque qu'on
achète avec un redémarrage.

## R9. Livrable 1 — le polyglot agentique se fera avec **pi**, pas avec dsh

Tranché par l'opérateur le 26/08 à 21:10, sur la mesure des douze tirages : à
verdicts identiques, dsh coûte 3,07× les jetons de pi et 3,16× la paroi, et il
meurt au plafond 4 fois sur 9 là où pi n'y meurt jamais. Le corpus fait
**225 exercices** — cpp 26, go 39, java 47, javascript 49, python 34, rust 30 —
et le facteur 3 s'y multiplie par 225.

### Protocole, et la lecture qui a été écartée

« L'agent doit créer le src ET ses tests, et tourner jusqu'à ce que ça passe. »

| | ce que ça donne | statut |
|---|---|---|
| `--tests-maison --tours 1`, laisse 1800 s | l'agent écrit source et tests et **itère dans son tour** jusqu'à ce que SES tests passent ; la suite officielle juge une fois, à la fin | **RETENU** |
| `--tests-maison --tours 4+` | après chaque échec, le pilote renvoie à l'agent la **sortie de la suite officielle** comme consigne du tour suivant (`texte = erreurs + TEST_FAILURES`) | **écarté** |

La seconde n'est pas écartée par goût : en variante D elle ferait **fuir la
suite cachée par ses messages d'erreur dès le tour 2**, et « l'agent ne voit
jamais le script de test » deviendrait faux. Le pilote sort déjà de la boucle
dès que la suite officielle passe (`if erreurs is None: break`) : monter
`--tours` n'ajoute rien à un exercice réussi, seulement une relance informée aux
échecs.

### Dimensionnement obligatoire avant les 225

Les deux seules durées connues de pi en variante D encadrent trop large :

| source | durée |
|---|---|
| `go/beer-song`, local, 3 tirages ce soir | 95 – 144 s (3 FAIL) |
| 12 exercices, OpenRouter, cet après-midi | **14,2 min/exercice** (3 PASS sur 12) |

**×225 = entre 8 h et 53 h.** Aucune décision ne se prend sur cet intervalle.
`dimensionner_pi_polyglot.ps1` joue donc 5 exercices (`--pas 45 --decalage 10`,
disjoints de l'échantillon de l'après-midi) dans la variante exacte, et rendra
la durée réelle. Il ne rendra **aucun taux** : 5 exercices ne font pas un
`pass_rate`.

### Ordre de carte, tranché

**GPQA d'abord** (25/198 au moment de la décision, ~4 h), puis le
dimensionnement, puis les 225. Les deux ne tiennent pas dans la même nuit.

### Trace d'un run abandonné

`pi_dim_testsdonnes` existe sous `tmp.benchmarks` avec 2 exercices joués
(cpp/gigasecond PASS 68,5 s ; go/kindergarten-garden PASS 420,7 s) en variante
« tests donnés, corrigés masqués » — variante lancée sur une mauvaise lecture de
la consigne, arrêtée dès la correction. Ces deux mesures ne sont **pas** du
dimensionnement de la variante D et ne doivent pas y être mélangées. Le
répertoire est laissé en place : rien n'est supprimé sans autorisation.

---

# Révision du 26/08/2026, 23:55 — le bras GPQA coûte 3× l'annoncé, et B2 est sans objet

Les révisions précédentes sont laissées en place : la cible du red team doit
rester lisible. Celle-ci corrige un chiffre que **j'ai fourni faux** et sur
lequel un ordre de carte a été tranché.

## R10. « ~4 h » était le chiffre d'un autre bras. Le vrai est 12 h

Les 80 s par question et les 4,41 h du **§B5** décrivent le bras **budget
8192**. Le bras en cours est à **pensée libre** (`--reasoning-budget -1`),
plafond 32 768 : c'est la coupure du budget qui bornait le temps.

| | bras 8192 (§B5) | bras libre (en cours) |
|---|---|---|
| secondes médiane | 80,1 | **164,5** |
| secondes moyenne | 73,6 | **262,8** |
| secondes max | 137,6 | **746,9** |
| jetons sortie médiane | 6 018 | **7 518** |
| jetons sortie moyenne | 5 090 | **11 856** |

Allure à l'horloge, lue dans la colonne d'écoulé du journal client (elle inclut
les frais de bout en bout, pas seulement le temps d'appel) : `30/179 … [2.5 h
ecoulees]` → **12,0 appels/h**.

**51/198 faits ; 147 restants = 12,2 h ; fin vers midi le 27/08.**

## R11. Le plafond consomme 44 % de la carte et ne rend aucune mesure

| population | n | coût moyen | part de la paroi |
|---|---|---|---|
| libres | 43 | 175 s | 56,0 % |
| **tronqués à 32 768** | **8 (15,7 %)** | **737 s** | **44,0 %** |

Un tronqué coûte **4,2×** un libre, rend `finish_reason: length` et
`donne NON-PARSE` : pas de lettre analysable. **44 % du temps de carte de ce
bras produit des réponses sans réponse.** Fait dimensionnant, absent du plan
jusqu'ici.

## R12. B2 (« rattrapage 32768 ») est SANS OBJET pour ce bras — à reformuler

B2 rattrapait les tronqués « à plafond 32 768 ». Ce bras **est déjà à 32 768** et
tronque à 15,7 %. Le rattrapage n'a donc pas d'objet : il faudrait un plafond
**plus haut**, donc en nommer un et le justifier — changement de protocole, pas
rattrapage. **B2 reste ouvert, mais sa rédaction est caduque.** Rien ne se publie
avant qu'il soit refait.

## R13. 90,7 % ne se publie pas, et le biais est structurel

    exactitude sur les 43 libres   : 90,7 %  +/- 8,7 pt
    encadrement sur les 8 tronqués : [76,5 % ; 92,2 %]   largeur 15,7 pt

La population « libre » n'est pas un échantillon : c'est l'ensemble des
questions où le modèle **a fini de penser seul**, et il tronque là où il peine.
Conditionner sur « a fini » sélectionne les questions résolues — un 27B Q4
au-dessus des modèles de frontière publiés mesure l'ampleur du biais, pas le
modèle. La règle 3b du pré-enregistrement tient donc pour la bonne raison, et
`depouiller_gpqa.py` refuse déjà de lui-même : *« LARGEUR > 5 pt : ce bras N'A
PAS de chiffre d'exactitude publiable »*.

**Le harnais est hors de cause, vérifié ce soir** : `rotations()` mélange les
distracteurs sur une graine dérivée de l'id puis insère la bonne réponse à la
position visée (`gpqa_diamond.py:142-157`) — aucune fuite ; `extraire()` retire
`<think>`, ne lit que les 2 000 derniers caractères et garde la **dernière**
occurrence (`:160-169`). Le biais est dans la sélection.

## R14. Conséquence sur l'ordre de carte — la décision revient à l'opérateur

L'ordre « GPQA d'abord » a été tranché sur « ~4 h ». À 12,2 h, GPQA occupe la
carte jusqu'à midi et **le dimensionnement pi n'a pas lieu cette nuit**. Je ne
renverse pas seul une décision explicite : le bras continue, la correction est
publiée, l'arbitrage est rendu à l'opérateur. Les deux issues, chiffrées :

| | ce que ça coûte | ce que ça rend au réveil |
|---|---|---|
| laisser finir (**en cours**) | carte prise jusqu'à ~12 h | GPQA complet, mais encadrement probablement encore trop large (R12/R13) |
| fenêtre de ~45 min pour `dimensionner_pi_polyglot.ps1` | ~9 appels GPQA différés, rien de perdu (la reprise saute les couples déjà faits) | la durée réelle de la variante D, qui débloque les 225 |

---

# Révision du 27/08/2026, 04:45 — R15 à R18 : une affirmation retirée, et B2 remplacé

## R15. RETRAIT de la R13 « le niveau absolu ne se publie pas »

La révision de 23:55 (R13) affirmait que ~90 % sur GPQA Diamond n'était pas
crédible pour un 27B et pointait une contamination. **Retiré.** Le chiffre publié
par Qwen pour Qwen3.8-27B est **89,2** sur GPQA Diamond.

| | GPQA Diamond |
|---|---|
| **publié (Qwen, officiel)** | **89,2** |
| BF16 OpenRouter, mesuré ici | 89,2 % ± 9,2 pt (37 q) |
| Q4 local 4090, mesuré ici | 92,7 % ± 5,7 pt (82 q) |

Le harnais reproduit le chiffre constructeur. Ce qui reste vrai de R13 : 89,2 est
un chiffre **constructeur**, non répliqué indépendamment ; et le 92,7 % **exclut**
les tronqués — comptés faux le bras tombe à 76,0 %, donc l'encadrement
**[76,0 % ; 94,0 %]** contient 89,2 sans le discriminer.

## R16. Le mécanisme de la fugue est établi : la pensée ne se referme jamais

    balise </think>     libres : 94/94        tronqués : 0/20
    répétition 12-gr.   tronqués : 0,2 %      libres : 0,7 %

Le modèle raisonne, **sans se répéter**, pendant 32 768 jetons, et n'émet jamais
la transition vers la réponse. `pensee_car = -1` sur tous les tronqués.

## R17. La fugue est une propriété de QUESTIONS, et le Q4 local y est moins sujet

40 questions jouées des deux côtés :

| | local finit | local FUIT |
|---|---|---|
| **BF16 finit** | 26 | **0** |
| **BF16 fuit** | 9 | 5 |

Zéro dans la case décisive : les fuites locales sont **strictement incluses** dans
celles du BF16, et le Q4 en récupère 9 sur 14. Le déploiement quantifié n'est pas
la cause.

## R18. B2 est REMPLACÉ — « rattrapage 32768 » devient « forcer la transition »

Deux remèdes écartés **par la mesure** :

| écarté | preuve |
|---|---|
| pénalité de répétition / DRY | les tronqués se répètent **moins** (0,2 % contre 0,7 %) |
| plafond 65 536 | 16k→32k n'a rien acheté (+1,3 ± 15,3 pt) et le coût double |

**B2 nouvelle rédaction, en deux temps.**

**B2a — publier le couple, sans carte, tout de suite.** Pas un nombre unique :
« exactitude quand le modèle conclut seul » **et** « part des questions où il ne
conclut pas », avec la liste nominative des questions. Déjà mesuré.

**B2b — rattrapage ciblé.** Rejouer **seulement** les questions tronquées avec
`--reasoning-budget 24576`, valeur prise sur le **p90 de la chimie qui finit**
(23 226) pour ne mordre que sur la queue. Le budget injecte `</think>` : c'est le
levier qui vise la panne réelle. Population **étiquetée** (`marque`), jamais
fusionnée.

- Coût : ~36 questions × ~600 s ≈ **6 h de carte**.
- Biais **connu et déjà mesuré** : un appel coupé au budget répond juste
  **64,0 %** contre 100 % pour un appel qui conclut seul. Le rattrapage ferme
  l'encadrement **et** introduit ce biais : il se publie en troisième population.

**Écarté pour l'instant, à rouvrir si la queue de journalisation monte** :
reprendre le raisonnement déjà produit et ne demander que la conclusion — 10 min
au lieu de 6 h, mais le journal ne garde que 40 000 des 101 344 caractères
produits, soit un raisonnement amputé des deux tiers.

---

# Révision du 27/08/2026, 05:00 — R19 : 24 576 arrêté pour B2b, et il ne transfère PAS au polyglot

## R19a. L'échelle de budget a été chiffrée, et elle ne paie pas

Idée examinée : partir bas (8 k ou 16 k) et monter quand le budget mord, au lieu
d'un barreau unique. Mesurée sur les 114 appels du bras libre.

La distribution de la **pensée** est lourde, et c'est elle qui commande tout :

    p25 1 358   p50 5 772   p75 10 474   p90 20 624   p95 25 442   + 20 fuites

| barreau | escalade | coût du barreau |
|---|---|---|
| 8 192 | **46,5 %** | 117 s |
| 16 384 | 30,7 % | 181 s |
| 24 576 | 21,9 % | 228 s |

**Et un ré-appel ne reprend pas, il recommence** : le cache couvre l'invite, pas
la pensée. Escalader repaie tout le raisonnement du barreau précédent.

| scénario | coût/question | reste non conclu |
|---|---|---|
| libre 32 768 (bras actuel) | **269 s** (mesuré) | 18 % |
| **barreau unique 24 576** | **228 s** | 21,9 % |
| échelle 8192 → 24576 | 223 s | 21,9 % |
| échelle 16384 → 32768 | 262 s | 19,3 % |
| échelle 8192 → 16384 → 32768 | **281 s** | 19,3 % |

L'échelle à deux barreaux gagne 2 % — dans le bruit du modèle de coût. Celle à
trois barreaux est **plus chère que de ne rien faire**. **Barreau unique retenu :
24 576**, valeur reportée dans B2b (R18).

Le barreau unique bat le bras actuel **sur les deux axes** : 228 s au lieu de
269 s, *et* une réponse forcée là où 18 % des questions n'en produisaient aucune.
Contrepartie déjà chiffrée : un appel coupé au budget répond juste **64,0 %**
contre 100 % pour un appel qui conclut seul — d'où le refus de descendre à 8 k,
qui couperait 46,5 % des appels au lieu de 21,9 %.

## R19b. NON, 24 576 ne transfère pas au polyglot aider — deux raisons mesurées

Question posée : le même barreau vaudrait-il pour le banc agentique ? **Non**, et
les deux raisons sont indépendantes.

**1. L'échelle n'est pas la même — le budget ne mordrait jamais.** Dans la boucle
agentique la pensée se compte **par appel**, et les douze tirages du 26/08 la
donnent :

| bras | pensée/appel |
|---|---|
| pi | 311 – 337 |
| dsh | 564 – 1 847 |

**pi pense ~320 jetons par appel. 24 576 est 75× au-dessus.** Un budget à cette
valeur ne s'activerait sur aucun appel du banc.

**2. La fugue du polyglot n'est pas dans le même canal.** Sur les 4 tirages dsh
morts au plafond de 16 384, la pensée par appel vaut **54**, **71** et
**10 118** : au moins deux de ces morts ont une pensée quasi nulle — **la fugue
était dans le canal VISIBLE**, pas dans le raisonnement. Un `--reasoning-budget`
ne plafonne que la pensée : il est **structurellement aveugle** à ces deux-là.

**3. Et c'est sans objet pour le livrable 1.** Le livrable 1 se fait avec **pi**,
qui n'est mort au plafond **sur aucun** de ses 3 tirages. Le problème de fugue au
banc est un problème de dsh, et dsh est sorti du livrable 1 (R9).

**L'instrument du polyglot reste donc celui déjà en place** : le plafond de
sortie par appel (16 384) et la laisse de tour (`--delai-tour 1800`). Ce sont
eux qui bornent, et ils bornent les deux canaux.

---

# Révision du 27/08/2026, 05:25 — R20 : le contrat d'API est semé dans les stubs cpp ; B6 en dépendait

## R20a. Le défaut, mesuré sur le premier FAIL du dimensionnement

`cpp/gigasecond` a échoué en 1 508 s avec des tests maison qui passaient. Cause :
le test officiel appelle `gigasecond::advance`, le stub livrait un **namespace
vide**, `TASK.md` ne nomme aucune fonction, et la variante D masque le test. Le
nom attendu n'était lisible nulle part. L'agent a écrit `anniversary` — le seul
mot de l'énoncé — avec une logique par ailleurs juste.

Ampleur re-mesurée sur les stubs d'origine sauvegardés :

| langue | stubs sans aucune déclaration | total |
|---|---|---|
| **cpp** | **26** | **26** — soit **100 % du cpp** |
| go / java / javascript / python / rust | **0** | 199 |
| TOTAL | 26 | 225 (**11,6 %**) |

Un premier comptage annonçait 26/47 java muets : artefact de motif (les stubs
java d'Exercism déclarent sans modificateur d'accès). Java est à **0/47**.

## R20b. Correction appliquée, et sa borne

`semer_signatures.py --appliquer` écrit dans les 26 stubs cpp les
**déclarations** de `.meta/example.h`, corps retirés ; sauvegarde
`<ex>.h.stub-origine`. Contrôle : **0 corps survivant sur 26** (6 des 26
en-têtes en contenaient — ils auraient été la solution).

Ce qui est semé est le **contrat**, pas la solution : nom, types, structure.
C'est exactement ce que go, java, javascript, python et rust livrent déjà. Le
semis **aligne le cpp sur les cinq autres**, il ne l'avantage pas.

**Écart à déclarer dans toute publication du livrable 1** : les stubs cpp du
corpus ont été modifiés par rapport à l'amont Exercism. Deux lignes suffisent —
le motif, et le fait que les 199 autres exercices sont intouchés.

## R20c. Conséquence sur B6 et sur le dimensionnement

Le tirage `pi_dimD` (4 FAIL, dont le FAIL cpp ci-dessus) est **arrêté, non
concaténé**. Relance sous `pi_dimD2`, répertoire et protocole neufs ; le lanceur
prend désormais `-Nom` pour interdire le mélange.

**B6 ne pouvait pas partir avant ce correctif** : 26 exercices sur 225 auraient
compté un échec de divination comme un échec de programmation, soit jusqu'à
11,6 points de `pass_rate` perdus pour une raison qui n'est pas le modèle.

## R20d. dflash2 reste hors de tous les chiffres, polyglot compris

Question posée : le brouillon dflash2 est-il utilisable pour le banc aider ?
**Non, et pour la raison déjà mesurée en B1** — pas une nouvelle.

En glouton, graine fixe, même binaire des deux côtés : `plain` contre `dflash2`
= **12/12 sorties divergentes**, premier octet différent entre 58 et 1113. Les
deux témoins (deux processus plain ; deux passes dflash2 même processus) sont à
12/12 identiques : l'accusation porte bien sur le spéculateur.

Le polyglot rend un **score**, exactement comme GPQA. Un score ne se mesure pas
avec un décodeur dont on vient de montrer qu'il change la suite de jetons là où
elle est décidable. Prix payé, le même qu'en GPQA : **46,9 t/s au lieu de
103,6** (2,2×).

**Caveat à porter sur le chiffre déjà publié** : le `pass_rate_2 = 52,0 %` de la
fenêtre 7quater a été mesuré **avec** dflash2 n7. Il reste valide comme mesure de
la *configuration publiée*, mais il n'est pas comparable jeton à jeton avec un
bras sans spéculation. Le dimensionnement en cours et B6 tournent sur
`specdec-q38-plain` — vérifié sur la ligne de commande du serveur vivant : aucun
`--model-draft`, aucun `--spec-*`.
