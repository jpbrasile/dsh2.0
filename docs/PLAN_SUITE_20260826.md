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
