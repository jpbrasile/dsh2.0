# Plan de mesure — agent de code local sur une seule carte grand public

Révision du 26/08/2026, intégrant la critique méthodologique du 26/08 10:06.

Ce fichier est le plan **et** le journal des désaccords. Une objection écartée
est écrite avec sa raison, pour qu'on ne la re-litige pas dans trois semaines.

---

## 0. Ce que la critique a corrigé, et ce que les données disaient déjà

Trois failles ont été soulevées : contamination, budget non apparié, puissance
statistique. Toutes trois sont réelles. Deux se testaient sur des données déjà
sur disque, sans GPU — fait avant d'en discuter
(`reports/specdec_20260825_ctxsweep_dflash2/contamination_et_saturation.py`).

### Saturation marginale — le graphique central existe déjà

aider polyglot, 225 exercices, 4 tours :

| tentative | gain | cumul | taux cumulé | gain marginal |
|---|---|---|---|---|
| 1 | 31 | 31 | 13,8 % | +13,8 pt |
| 2 | 87 | 118 | **52,4 %** | +38,7 pt |
| 3 | 38 | 156 | 69,3 % | +16,9 pt |
| 4 | 21 | 177 | **78,7 %** | +9,3 pt |

Lecture honnête : **pas de plateau à 4**, mais le gain marginal décroît d'un
facteur ~0,5 par tour. C'est une géométrique décroissante, pas une saturation.
Asymptote extrapolée ~88-90 %. La courbe n=1..8 réclamée par la critique
testera si la décroissance tient ce facteur.

À noter : le piège que la critique redoutait (« comparer un harnais 4 passes à
un score de leaderboard obtenu à 2 tentatives ») **a déjà été évité**. Les deux
chiffres sont rapportés séparément et le 52,4 % à 2 tours est le seul présenté
comme opposable au board.

### Signal de contamination — le run aveugle est le bon substrat

Le run aider est un test de contamination presque idéal, par hasard : le modèle
y écrit **à l'aveugle** — pas de fichier de test, pas d'exécution, pas de
`.meta`. Sa production ne peut donc pas avoir été ajustée à des assertions lues.
Similarité au corrigé canonique d'Exercism, plus gros fichier par exercice,
plancher 400 caractères normalisés :

| | n | médiane | q90 | max | > 80 % |
|---|---|---|---|---|---|
| réussis | 163 | 12,2 % | 34,4 % | 72,2 % | **0** |
| ratés | 45 | 9,0 % | 31,4 % | 49,7 % | **0** |

Zéro cas au-dessus de 80 % sur 208 ; écart de médiane réussis − ratés :
**+3,1 point**. Sous l'hypothèse « le modèle recrache le corrigé public », les
réussis devraient être nettement au-dessus des ratés. Ils ne le sont pas.

**Ce que ça élimine** : la régurgitation verbatim du corrigé canonique.
**Ce que ça n'élimine pas** : la mémorisation de l'*approche*, et celle des
milliers de solutions **communautaires** d'Exercism, dont `.meta/example` n'est
qu'un représentant. La sonde de complétion reste au plan, rétrogradée d'urgente
à nécessaire.

---

## 1. Contamination — étape 0, avec une correction de protocole

Retenu de la critique : sonde de mémorisation + jeu réécrit. **Avec deux
corrections, sans lesquelles le test ne prouve rien.**

### 1.1 Sonde de complétion (décisive, ~30 min, coût carte négligeable)

Modèle nu, énoncé tronqué, on regarde s'il complète la signature canonique et
les cas de test. Se fait sur les 225 énoncés. C'est la seule mesure qui
distingue *rappel* de *compétence*.

### 1.2 Jeu réécrit — le confondant que la critique ne nomme pas

Renommer les fonctions et reformuler l'énoncé change **la mémorisation ET la
difficulté**. Une chute de score est alors inattribuable : réécriture plus dure,
ou mémorisation cassée ? Deux garde-fous obligatoires :

- **La suite de tests garde sa sémantique exacte.** Seule la surface bouge :
  identifiants, prose, ordre des exemples. Pas de contrainte « mineure »
  changée — c'est une modification de difficulté déguisée.
- **Contrôle par second modèle.** Faire tourner original + réécrit sur *notre*
  modèle **et** sur un modèle de provenance très différente (OpenRouter, coût
  négligeable, aucun GPU). Si les deux chutent également, la réécriture a
  durci la tâche. Si seul le nôtre chute, c'est de la contamination.

Sans ce second bras, un jeu réécrit produit un nombre ininterprétable.

### 1.3 Jeu filtré temporellement

Retenu tel quel : SWE-rebench ou équivalent post-cutoff comme contrôle. C'est
le seul contrôle de contamination qui ne repose sur aucune hypothèse.

---

## 2. Budget apparié — retenu, avec un durcissement

La critique a raison sur le fond et c'est le risque principal. Mais dans notre
cas précis, **le confondant dominant n'est pas le budget : c'est le retour
d'information.**

| ce que le système a | aider (banc A) | dsh (variante C) |
|---|---|---|
| lit le fichier de test | non | **oui** |
| compile et exécute dans le tour | non | **oui** |
| tentatives | 4, arbitrées par un juge externe | 1,13 en moyenne |

Apparier le budget sans apparier le retour d'information ne fait pas une
comparaison. L'échelle d'ablation doit être **à deux dimensions** :

| | 1 tentative | N tentatives |
|---|---|---|
| aveugle (A) | modèle nu | resampling naïf |
| écrit ses propres tests (D) | — | — |
| voit le test réel (C) | — | dsh actuel |

Les variantes B et D sont **déjà construites et calibrées** dans `pilote.py`
(`--sans-tests`, `--sans-corriges`, `--tests-maison`).

### Le durcissement : le sélecteur

« Resampling naïf à budget N » suppose un moyen de choisir la meilleure des N
tentatives. Sans fichier de test (variante B), **il n'y a pas de sélecteur** et
le best-of-N n'est pas défini. Avec le fichier de test (variante C), le test
**est** le sélecteur — autrement dit :

> **La variante C, c'est du best-of-N avec un sélecteur oracle.**

C'est la formulation honnête du 92,1 %, et il faut l'écrire ainsi. Corollaire :
le contrôle « resampling naïf » doit recevoir **le même oracle**, sinon on
compare un système qui sait quand il a réussi à un système qui l'ignore, et le
contrôle est truqué en notre faveur.

Retenu aussi, sans réserve : **colonne coût (tokens, tentatives, wall-clock) à
côté de chaque score.** Un tableau sans colonne coût se lit comme une
dissimulation.

---

## 3. Puissance statistique — partiellement déjà en place

### Ce qui est déjà fait

- **Comparaison appariée par question** : implémentée dans
  `scripts/gpqa/depouiller_gpqa.py` (moyenne des différences par question,
  erreur-type sur les questions). C'est exactement ce que la critique réclame.
- **n = 792 et non 198** : 4 rotations de position par question. 1 σ passe de
  ~3,6 à ~1,8 point, et le biais de position disparaît exactement de l'agrégat.
- **Refus explicite du σ binomial sur 792** : les 4 rotations d'une question
  sont corrélées. L'erreur publiée est groupée par question.

### Ce que la critique corrige à juste titre

- **Effet minimum détectable, déclaré AVANT.** Non apparié : 2 σ ≈ 3,6 pt.
  Apparié : ~1,8 pt. Une perte Q4 typique de 1 à 3 points est donc **au bord**
  du détectable — le haut de la fourchette passe, le bas non. À écrire dans le
  rapport avant de voir les résultats.
- **n ≥ 3 runs pour tout ce qui est agentique.** Notre chiffre le plus fragile
  est le **92,1 % sur 38 exercices, n = 1** : σ binomial ≈ 4,4 points, plus la
  variance run-à-run de l'agent par-dessus. Il ne doit pas porter la thèse en
  l'état.
- **Seuil de significativité fixé avant lancement.** Sur 225 exercices, un
  delta de 2-3 points n'est pas significatif.

### La tension à trancher

La comparaison appariée Q4 vs pleine précision **exige les deux côtés passés
par le même harnais**. Décision prise : le 89,2 publié sert de référence, on ne
refait pas le bf16. Conséquence assumée : la comparaison sera **non appariée et
inter-harnais**, donc la moins puissante des deux. Le run bf16 complet coûte
~3 $ et **aucune carte**. Le lot de mise au point (40 questions × 4 rotations)
en donne déjà un échantillon apparié — assez pour détecter une dérive
grossière du harnais, pas assez pour un effet de 2 points.

---

## 4. Ajustements par étape

| étape | décision | motif |
|---|---|---|
| **aider polyglot** | **rétrogradé** en banc de développement du harnais | mesure l'écriture à l'aveugle, pas ce que fait dsh. Le 78,7 % ne se rapporte jamais sur l'échelle du board. |
| **GPQA Diamond** | **gardé, mais recadré** | voir ci-dessous |
| **GPQA-Web** | **supprimé** | retenu sans réserve : ne prouve rien, appelle la critique |
| **SWE-bench Pro** | sous-échantillon **stratifié 150-250**, gelé et publié, IC bootstrap | retenu sans réserve ; chiffrer le coût carte avant de s'engager |
| **Terminal-Bench 2.x** | **gardé, remonté** | tâches réellement multi-étapes : c'est là que la thèse est le plus testable |
| **deep research / GAIA** | **dernier, coupable sans regret** | une revendication de généralité mal étayée fait plus de mal qu'une revendication absente |

### Désaccord sur GPQA — le seul point où la critique est écartée

La critique propose de rétrograder GPQA en note de bas de page : « un 27B y
sera dans une zone basse où le signal est faible, et ça n'intéresse pas ton
public cible ». **Deux raisons de ne pas suivre :**

1. **La zone n'est pas basse.** La référence publiée pour ce modèle est
   **89,2**. On n'est pas dans le régime plancher où le bruit domine.
2. **Ce n'est pas une vitrine de raisonnement, c'est le contrôle d'intégrité du
   Q4.** *Tous* les résultats de code de cette campagne sont produits en Q4_K_M
   avec un KV quantifié q8/q4. Si la quantification abîme le raisonnement, tout
   le reste est bâti sur du sable. GPQA est le seul banc du plan qui teste ça
   directement, et il ne coûte pas de carte partagée.

**Recadrage retenu** : GPQA n'est pas rapporté comme « capacité de raisonnement
du modèle » mais comme *« contrôle d'intégrité de la quantification »*. Ce
recadrage répond au fond de l'objection — le public cible se moque du score
GPQA, mais pas de savoir si le Q4 qu'on lui recommande est intact.

---

## 5. Le graphique central

Retenu intégralement : axe x en **log** (secondes ou $), **frontière de
Pareto**, points frontier placés dessus uniquement **quand leur protocole est
documenté**, second axe **$ par tâche résolue**.

La **courbe de saturation marginale** est déjà calculée pour aider n=1..4
(§0). À étendre à n=1..8 sur le banc retenu. C'est le graphique qui teste la
thèse directement : si elle sature à 3, l'argument tombe.

---

## 6. La revendication finale

Abandonnée : « competitive with frontier coding-agent systems across multiple
independent task families ». *Competitive* n'est pas défini et la comparaison
n'est presque jamais à protocole égal.

Retenue :

> On a single consumer GPU, a 27B Q4 model with a structured harness recovers
> **X %** of frontier coding-agent performance on SWE-bench Pro and
> Terminal-Bench at **Y×** lower cost per resolved task, with the gap
> concentrated in **[catégorie d'échec identifiée]**.

Une réserve à tenir : « X % de la performance frontier » exige que le chiffre
frontier soit mesuré **par notre harnais**, ou étiqueté sans ambiguïté comme
« protocole leaderboard ». Sinon la formulation reproduit exactement le défaut
qu'elle corrige.

### Taxonomie des échecs — matière déjà disponible

La critique a raison qu'elle vaut plus qu'un point de score. Trois catégories
sont déjà documentées par les runs de cette nuit :

- **contexte trop long** : 31 fenêtres épuisées / 225 sur le run aider,
  5 réponses malformées ;
- **exécution shell / environnement** : la collision `build/` hôte(Windows) —
  conteneur(Linux) explique les deux échecs C++ de la variante C ;
- **récupération** : 59 exercices sur 225 sauvés par les tours 3-4, soit la
  mesure directe de ce que vaut la reprise après échec.

---

## 7. Ordre d'exécution retenu

1. **Sonde de complétion** (contamination, décisive, ~30 min de carte)
2. **Contrôle budget-apparié avec oracle partagé** — variantes B/D déjà
   construites
3. **Terminal-Bench 2.x** — le plus discriminant pour la thèse
4. **SWE-bench Pro** sur sous-échantillon stratifié gelé
5. Le reste si le budget suit ; deep research coupé en premier

En cours pendant l'écriture de ce plan : GPQA Diamond sur le Q4 local
(792 appels) et le lot de mise au point bf16 sur OpenRouter (160 appels).

---

## 8. Échantillonnage et troncature — deux trous ouverts le 26/08

### 8.1 La température n'est pas forcément un réglage unique

**Mesure du 26/08, GPQA local, 128 appels APPARIÉS (même graine, même plafond) :**

| | justes / parses | tronqués | jetons médians |
|---|---|---|---|
| t=1,0 (réglage publié Qwen, mode thinking) | 94/126 = 74,6 % | 1 | 772 |
| t=0,6 (ancien, valeur portée de Qwen3) | 99/125 = 79,2 % | 3 | 754 |

Écart apparié **−3,9 pt ± 3,7, z = −1,04**. 9 appels mieux, 14 moins bien,
**105 identiques sur 128**. Rien. Le réglage publié ne remonte pas le score et
ne le casse pas.

**Hypothèse à tester : raisonnement et codage ne veulent peut-être pas la même
température.** L'argument est mécanique, pas esthétique — le mode de défaillance
que la température pilote n'est pas le même dans les deux tâches :

- GPQA rend **une lettre parmi quatre**. L'espace de sortie est minuscule ; la
  température ne peut bouger que l'appel déjà hésitant. Les 105 réponses
  identiques sur 128 le disent directement.
- Le codage est une **génération longue** où un seul jeton fautif casse la
  compilation, et où une boucle de répétition tue le tour à l'horloge. Qwen
  déconseille explicitement le décodage trop déterministe sur ses modèles
  thinking pour cette raison-là.

Donc : tester séparément, et ne pas transporter la conclusion GPQA sur le banc
de codage.

**PRÉREQUIS BLOQUANT — mesuré le 26/08.** On ne peut PAS aujourd'hui tester une
température sur le banc de codage, parce qu'aucun des deux agents n'en envoie :

- `settings.yaml` de `.dsh-bench-dflash2` : **aucune** clé `temperature`,
  `top_p` ou `top_k`, sur aucune route. *(vérifié)*
- bundle de pi : le patron est partout `temperature: options?.temperature`,
  transmise seulement si posée ; **aucun défaut numérique en dur**. La commande
  du banc (`-p --provider openrouter --model … --thinking medium -a
  --no-session`) n'en pose aucune. *(vérifié)*
- côté **code** dsh (et non plus config) : **non vérifié** — le parcours du
  runtime `~/.dsh/runtime/dsh-0.1.1-rc.2/node_modules` a dépassé le délai.

Conséquence : sur la route OpenRouter, l'échantillonnage réel est celui du
fournisseur amont — inconnu, non journalisé, et OpenRouter peut router vers
plusieurs amonts pour un même identifiant de modèle. **Rien ne garantit que deux
runs du banc ont été échantillonnés pareil.** C'est un trou de reproductibilité,
pas un détail de réglage : il est antérieur à la question « quelle température ».

Étape 0 de toute campagne température sur le codage : **rendre l'échantillonnage
explicite et le VÉRIFIER SUR LE FIL**, pas dans la config. Un processus écoute
déjà sur 127.0.0.1:8006 (PID 58072 au 26/08) — la route `local-think` de
`settings.yaml` le décrit comme le proxy enregistreur 8006 → 8005 ; vérifier ce
qu'il journalise avant de s'en servir. **Ne pas router de trafic d'agent vers
8005 tant que le run GPQA local y tourne** : ressource partagée.

### 8.2 Troncature — DEUX mécanismes, à ne pas confondre

**(a) GPQA : plafond de JETONS.** bf16 : 26 % des appels coupés à 16384 (bras
abandonné le 26/08). Local : 3/128 à t=0,6, 1/128 à t=1,0, soit ~1–2 %.

- **Règle de lecture, pré-enregistrée :** un appel tronqué n'est pas une réponse
  fausse, c'est une **NON-MESURE**. Exclu du dénominateur ET compté à part.
  C'est la même leçon que les 59 sorties vides de la sonde de mémorisation, où
  les compter à zéro aurait fabriqué un « aucune mémorisation ».
- **Protocole :** finir le run courant à 16384 — l'appariement avec le bras
  t=0,6 en dépend — PUIS rattraper à 32768 les tronqués **des deux bras**
  (`lancer_or_rattrapage.ps1`). Un rattrapage asymétrique rouvrirait exactement
  le biais de sélection identifié le 26/08.
- **Publier toujours les deux conventions** (tronqués exclus / tronqués comptés
  faux) : l'écart était 74,6 % contre 73,4 % sur le même journal.

**(b) Banc de codage : plafond d'HORLOGE** (`--delai-tour`, 900 s par défaut).
Mécanisme différent : le tour est coupé, la durée devient une **borne
inférieure** et `sortie_queue` revient vide — on ne sait même pas pourquoi.

Mesuré sur `dsh-dev-or` : **3 tours coupés sur 7 exercices**, médiane 869,8 s
contre un plafond de 900 s. La médiane au-dessus de la moyenne dit que la
distribution est plaquée contre le plafond. C'est de la **censure lourde**, pas
un incident isolé.

**CONSÉQUENCE IMMÉDIATE SUR LA VARIANTE D.** Passer à `--tours 1` (§8.3) retire
la moitié du temps d'horloge alors que l'itération, elle, passe À L'INTÉRIEUR du
tour. À 900 s on mesurerait le chronomètre et pas l'agent — et on le mesurerait
surtout chez dsh, le plus lent des deux, ce qui produirait un écart dsh/pi
entièrement artefactuel. **Relever `--delai-tour` avant de lancer D**
(proposition : 1800 s), et publier le taux de tours coupés À CÔTÉ du taux de
réussite, systématiquement.

### 8.3 Variante D : un seul tour, et pourquoi c'est une condition de validité

`pilote.py:620` fait `texte = erreurs + TEST_FAILURES…` : au tour 2 l'agent
reçoit **la sortie d'échec de la suite officielle, mot pour mot** — noms de
tests, valeurs attendues, assertions. En variante D cette suite est la recette
d'acceptation **cachée** : un deuxième tour la fuite. `--tours 1` n'est donc pas
une économie, c'est la condition pour que D soit honnête.

**Comparable côté aider :** `pass_rate_1` = **16,9 %**, et non 52,0 %. À citer
avec ce que « 1 tour » recouvre de chaque côté — aider : une écriture aveugle,
zéro exécution ; D : autant d'itérations internes que l'agent en veut. C'est
là que se chiffre « aider ne faisait que la moitié du travail ».

**Fumée du 26/08** (pi, go + python, 2 tours autorisés) : 2/2 PASS, les deux
**au tour 1**, 5,8 min. Le tour 2 ne s'est jamais déclenché : la machinerie de D
est vérifiée, la clause de tour 2 **ne l'est pas**. Raison de plus pour la
retirer plutôt que de l'éprouver.

**Limite déclarée par le harnais lui-même :** en cpp et java, câbler un test
maison demande de toucher `CMakeLists.txt` / Gradle, qui sont interdits —
**73 exercices sur 225** sont structurellement plus durs en variante D. À dire
dans tout résultat D, et à regarder par langage avant de conclure quoi que ce
soit sur l'agent.

### 8.4 Ce que dsh et pi envoient VRAIMENT — mesuré le 26/08 sur le fil

§8.1 déduisait de la lecture du code qu'aucun agent n'envoie de paramètre
d'échantillonnage. Une déduction n'est pas une mesure. Un **serveur témoin**
(`scripts/polyglot_dsh/temoin_echantillonnage.py`) répond lui-même en
OpenAI-compatible et journalise le corps de chaque requête : aucun modèle
chargé, aucun crédit, et surtout **aucun trafic vers 8005**, occupé par le run
GPQA local.

Accueils **isolés** des deux côtés — `PI_CODING_AGENT_DIR` pour pi,
`~/.dsh-temoin-echantillonnage` pour dsh (`preparer_accueil_temoin.py`) — parce
que `pilote.py:779-789` réécrit `agent-default-model` sans le restaurer :
écrire la route témoin dans le vrai banc l'aurait laissé pointé sur un serveur
factice.

**Résultat, corps de requête réels :**

| clé | dsh | pi |
|---|---|---|
| `max_completion_tokens` | 4096 | 4096 |
| `reasoning_effort` | `"medium"` | `"medium"` |
| `stream` / `stream_options` / `store` | oui | oui |
| **`temperature`** | **absente** | **absente** |
| **`top_p`, `top_k`, `min_p`** | **absentes** | **absentes** |

**Deux conclusions opposées, les deux importantes.**

1. **La comparaison dsh contre pi n'est PAS biaisée par l'échantillonnage.**
   Les corps sont identiques au champ près. C'était une hypothèse tacite de
   `dsh-dev-or` / `pi-dev-or` ; elle est maintenant vérifiée.
2. **Le réglage Qwen n'est appliqué nulle part.** Les deux héritent du défaut de
   l'amont OpenRouter — inconnu, non journalisé, et susceptible de changer d'un
   run à l'autre si OpenRouter route ailleurs.

Vérification annexe : `reasoning_effort: "medium"` **part bien** dans les deux
cas. La comparaison à effort égal reposait sur une hypothèse, elle est
maintenant mesurée.

Un troisième appel dsh part avec `max_completion_tokens: 64` et **sans**
`reasoning_effort` : c'est le générateur de titre de session
(`@deepseek-ai/dsh-session-title-llm`). À exclure de tout comptage de jetons.

**Le bouton : présent chez pi, ABSENT chez dsh.**

- **pi** — `samplingParams` dans `models.json` fonctionne, vérifié sur le fil :
  `temperature 1.0, top_p 0.95, top_k 20, min_p 0.0` sont partis. La doc de pi
  (`docs/models.md:255`) le désigne comme « the single source of sampling truth
  for a model ».
- **dsh** — aucune voie trouvée. `samplingParams`, `temperature` au niveau du
  modèle, `temperature` au niveau de la route : **les trois sont ignorées en
  silence**, sans message d'erreur. La construction du modèle
  (`dsh-llm-pi-ai/lib/index.js:639-657`) ne retient que id, name, api, provider,
  baseUrl, input, cost, contextWindow, maxTokens, reasoning, compat — aucun
  champ d'échantillonnage. Le transport existe pourtant
  (`index.js:1740`, `temperature === void 0 ? {} : { temperature }`) et le type
  `CallConfig.temperature` est déclaré — mais **rien dans les paquets dsh ne le
  remplit**. Un champ d'interface sans producteur.

**PIÈGE À RETENIR : dsh ne rejette pas une clé de configuration inconnue, il la
laisse tomber sans rien dire.** Poser `temperature: 1.0` dans `settings.yaml`
donne un fichier qui a l'air réglé et une requête qui ne l'est pas. Toute
affirmation « le banc tournait à telle température » doit être vérifiée sur le
fil, jamais dans la config.

**CONSÉQUENCE SUR LA MARCHE À SUIVRE.** Régler pi seul **casserait** la seule
propriété propre qu'on vient d'établir : le pied d'égalité. La correction doit
être symétrique et extérieure aux deux agents — un **proxy d'injection** placé
devant OpenRouter, qui ajoute les mêmes paramètres au corps de chaque requête,
quel que soit l'agent, et journalise ce qui part. Le dépôt a déjà la mécanique
(`scripts/bench_julia_effort/proxy.mjs`,
`scripts/openrouter_cheapest_proxy.mjs`). Ce proxy ferme du même geste le trou
de reproductibilité : on saura, pour chaque run, ce qui a réellement été envoyé.

Journaux du témoin, conservés :
`temoin_sans_bouton.jsonl` (état initial des deux agents),
`temoin_samplingparams.jsonl` (pi réglé, dsh sourd),
`temoin.jsonl` (dsh, clés `temperature` route et modèle : ignorées).

---

## 9. Le budget de raisonnement — facteur découvert le 26/08, et pré-enregistrement du bras

### 9.1 Ce que le §8.2 ne couvrait pas

Le §8.2 identifiait **deux** mécanismes de troncature : le plafond de jetons
(`--max-tokens`, GPQA) et le mur d'horloge (`--delai-tour`, banc de codage).
Il en manquait un **troisième**, et c'était le plus mordant :
**`--reasoning-budget` côté serveur**, qui coupe la *pensée* sans toucher à la
réponse, et donc **sans jamais lever `finish_reason: length`**.

C'est ce qui l'a rendu invisible : sur 294 appels, `finish_reason` valait
`length` 7 fois seulement (2,4 %). Le journal disait « terminé normalement »
pour 97,6 % d'appels dont 83 % avaient la pensée tranchée en pleine phrase.

**Règle ajoutée au protocole : un banc de raisonnement doit journaliser
l'argv du serveur, pas seulement les paramètres de la requête.** Un facteur qui
vit côté serveur est absent du corps HTTP et n'apparaît dans aucun champ de
réponse.

### 9.2 Comment on l'a mesuré, et comment on le mesurera désormais

Deux observables, dans cet ordre :

1. **Signature de coupure nue** — proportion de blocs `<think>` ne finissant pas
   sur une ponctuation terminale. 83 % ici. Cheap, calculable a posteriori sur
   tout journal existant.
2. **Histogramme des longueurs, tokenisées par le `/tokenize` DU SERVEUR.**
   Décisif : médiane 512, p90 512, max 514, 53/60 sur le budget exact.

**Ne jamais conclure sur une longueur en jetons estimée.** Ma première lecture
convertissait à 4 caractères/jeton et concluait « pas de mur visible » — faux,
ce texte fait ~3 car/jeton. Le tokenizer du serveur est à une requête, il ne
consomme pas de GPU, il n'y a aucune raison d'estimer.

### 9.3 Le bras pré-enregistré

**Facteur unique.** `--reasoning-budget 512 → -1`. Diff de l'argv complet
vérifié ligne à ligne : **une seule ligne change**. Tout le reste identique —
binaire `src-dflash2/build-faq` (`b1-f7aadef`), modèle Q4_K_M, draft dflash2,
ctx 163840, KV q8_0/q4_0, `--temp 1.0 --top-k 20 --top-p 0.95 --min-p 0
--presence-penalty 0.0 --repeat-penalty 1.0`, graine 1234, plafond 16384,
4 rotations, `--parallele 1`.

**Comparaison appariée** couple `(Record ID, rotation)` par couple, comme le
bras de température. Erreur groupée par question, comme partout ailleurs dans
ce plan.

| bras | fichier | état |
|---|---|---|
| budget 512 | `local_q4_t1_budget512.jsonl` | **gelé** : 294 appels, 74 questions (72 complètes 4/4), **68,7 % ± 4,2** |
| budget −1 | `local_q4_t1_illimite.jsonl` | en cours |

**Fichier neuf, obligatoire.** `gpqa_diamond.py` reprend en sautant les couples
déjà présents : réutiliser l'ancien fichier aurait sauté les 294 appels sous
guillotine et produit un journal mélangeant deux régimes de serveur, sans
signal.

### 9.4 Ce que le bras peut et ne peut pas trancher

**Il peut** : chiffrer ce que la guillotine coûtait, et donner enfin un niveau
absolu opposable au 89,2 publié.

**Il ne peut pas** : trancher l'écart résiduel. Si le bras −1 remonte à, disons,
80 %, il restera ~9 points à partager entre la quantification Q4_K_M, le
protocole publié (inconnu : passe unique ? consensus ? quel budget ?) et le
décodage spéculatif. Le seul test décisif reste **un bras bf16 sur le même
harnais**, abandonné le 26/08 par décision explicite. L'écart résiduel restera
donc attribué à « Q4 + protocole », sans partage mesuré, et il faut le dire.

**Attendu, et à ne pas confondre avec une panne :** le modèle va penser plus
longtemps, donc les tronqués à 16384 vont probablement **augmenter**. La règle
de lecture du §8.2 s'applique sans changement — un appel tronqué est une
**NON-MESURE**, exclu et **compté**, avec rattrapage symétrique à 32768 sur les
**deux** bras. Le débit va aussi baisser : c'est le coût du raisonnement rendu,
pas une régression.

### 9.5 Hygiène : deux échecs silencieux, deux garde-fous

- **Une relance qui ne relance rien ressemble à une réussite.** La 1re tentative
  a été refusée par le garde-fou « GPU occupé » du lanceur (qui s'exécute
  *avant* sa section d'arrêt de port), l'ancien serveur a survécu, `/props`
  répondait. Sortie du processus détaché non capturée ⇒ indiscernable.
  **Garde-fou ajouté** : `lancer_local_t1_illimite.ps1` refuse de partir si la
  ligne de commande du llama-server vivant ne porte pas `--reasoning-budget -1`.
- **Une valeur copiée-collée n'a pas d'auteur.** Le `512` est présent une
  soixantaine de fois dans une douzaine de projets, hérité des gabarits
  `start_llama_qwopus_27b_coder_*`. Il est désormais un **paramètre**
  (`-ReasoningBudget`, défaut `-1`) et non plus une constante, avec le pourquoi
  écrit dans le fichier. Les autres projets ne sont **pas** touchés : ils sont
  agentiques, et pour eux le choix d'origine peut rester le bon.

