# Pré-enregistrement — balayage du budget de pensée

**Écrit et commité AVANT que les données existent.** C'est la seule protection
contre le geste qui consiste à choisir après coup le *n*, le seuil ou la
population qui donne le résultat qu'on espérait. Ce qui est écrit ici ne se
modifie pas en cours de route ; si une modification s'impose, elle est datée,
justifiée, et l'analyse d'origine est publiée aussi.

## La question

Le budget de pensée est un réglage libre entre 0 et illimité. Le lanceur portait
512 nu depuis le 25/08, ce qui est le pire régime documenté. Le bras 8192 +
message tourne. **Quel budget retenir ?**

## Pourquoi un petit *n* suffit ici, et pourquoi il n'aurait pas suffi ailleurs

`gpqa_diamond.py` mélange les questions avec `random.Random(--graine)`, graine
1234 par défaut, et l'ordre des distracteurs de chaque question est tiré par
`random.Random("<id>|<graine>")`. **L'ordre est donc identique dans tous les
bras.** Prendre les *N* premières questions dans deux bras, c'est prendre les
mêmes questions, avec les mêmes rotations, dans le même ordre : les bras sont
**appariés par construction**.

Un réglage se lit alors **par question**. Une question réussie 4/4 des deux
côtés n'apporte aucune information ; seules les questions **discordantes**
comptent. La variance de la différence appariée est très inférieure à celle de
chaque score absolu, et c'est ce qui autorise 50 questions là où une mesure
absolue en demanderait 198.

## Ce que ce plan peut établir, et ce qu'il ne peut pas

**Peut** : le taux de non-convergence ; la distribution des jetons de pensée ;
le **taux de récupération des appels coupés** (la quantité qui décide) ; le
temps et le coût par appel ; un effondrement d'exactitude (ordre de 10 points).

**Ne peut pas** : départager deux budgets à 2 ou 3 points d'exactitude. Il n'y
a que 198 questions dans GPQA Diamond au total ; même le jeu complet ne
trancherait pas nettement à cette échelle. **Un résultat « les deux budgets se
valent » devra être publié comme *non départagés*, jamais comme *équivalents*.**

## Plan arrêté

**Bras de réglage, 50 questions × 4 rotations = 200 appels chacun**, mêmes 50
questions partout (`--questions 50 --graine 1234`) :

| bras | budget | message | état |
|---|---|---|---|
| A | 8192 | oui | en vol, replafonné à 50 questions |
| B | 2048 | oui | à lancer après A |

Coût : ~2,4 h chacun au rythme mesuré (42,4 s/appel sur 45 appels), sur le
4090, donc **gratuit en argent**. Aucun appel OpenRouter.

Bras déjà gelés, versés à la comparaison sans être rejoués :

| bras | budget | message | n | score |
|---|---|---|---|---|
| `local_q4_t1_budget512.jsonl` | 512 | **non** | 294 appels / 74 q | 68,7 % ± 4,2 |
| `local_q4_t1_budget_illimite.jsonl` | −1 | s.o. | 30 appels / 8 q | 81,2 % ± 12,3 |

## Règles de lecture, arrêtées maintenant

1. **Arrêt.** Chaque bras s'arrête **seul** à 200 appels (`--questions 50`).
   Pas d'arrêt à la main, pas de prolongation « pour voir ».
2. **Comparaison appariée** sur les 50 questions communes. Le chiffre publié
   est la différence par question, avec le compte de questions discordantes.
   Le score absolu de chaque bras est publié aussi, avec son erreur type
   groupée par question.
3. **Appel tronqué = non-mesure**, exclu **et compté**, dans tous les bras.
4. **Population « coupée au budget »** : définie par la présence du message de
   transition dans le bloc de pensée — témoin direct, pas un seuil choisi après
   coup. Le seuil en jetons n'est qu'un filet de sécurité.
5. **Critère de décision, dans cet ordre :**
   - un bras qui perd plus de **10 points** d'exactitude appariée est écarté ;
   - à exactitude non départagée, **le budget le plus bas gagne** — le gain
     recherché est le temps et le coût, pas l'exactitude ;
   - si le taux de récupération des appels coupés tombe au niveau du hasard
     (**25 %** sur un QCM à 4 options), le bras est écarté même si son score
     global tient : il fabrique du bruit qui entre dans le score sans se
     signaler.
6. **Le budget retenu est ensuite mesuré sur le jeu complet** (198 questions,
   792 appels). Le balayage règle ; il ne publie pas le chiffre final.

## Ce que je n'ai pas encore fait, et pourquoi

Un bras **512 + message** reproduirait chez nous l'effet publié (coupure nue
78 % contre 89 % avec message, Qwen3 9B / HumanEval) en le comparant au bras
512 **nu** déjà gelé. Ce serait le résultat le plus intéressant du lot. Il
coûte ~2 h de 4090 de plus. **Non lancé — hors de la demande.**

---

# Révision 1 — 26/08/2026, avant que les données du balayage existent

Le plan d'origine (50 questions × 4 rotations) est **remplacé**, pas corrigé
après coup : aucun bras du balayage n'était terminé, et rien n'a été lu.
L'analyse d'origine n'a donc produit aucun chiffre à publier.

## Ce qui a déclenché la révision

Remarque de l'utilisateur : le placement de la bonne réponse ne semble pas
biaiser le modèle — donc pourquoi payer 4 rotations ?

**Mesuré avant d'agir**, `biais_position.py`, sur les quatre plus gros
journaux disponibles :

| journal | n | χ² préférence | étendue exactitude max−min |
|---|---|---|---|
| `local_q4_t1_budget512` | 285 | 4,16 | 6,1 pts |
| `local_q4` | 235 | 2,02 | 9,0 pts |
| `or_bf16` | 128 | 0,31 | 6,2 pts |

Seuils du χ² à 3 degrés de liberté : 7,81 à 5 %, 11,34 à 1 %. **Aucun biais
détectable**, ni de préférence de lettre, ni de position.

**La réserve, qui est la moitié du résultat :** avec ~71 appels par lettre on
ne détecte un écart d'exactitude entre deux positions qu'à partir de ~15
points. « Pas de biais détecté » ne veut donc **pas** dire « pas de biais » —
un effet de 6 points serait invisible. On ne supprime pas le contrôle de
position ; on le déplace.

## Le piège évité

Passer naïvement à `--rotations 1` aurait été **faux**. Le code prend
`rotations(item)[:args.rotations]`, donc la rotation 0 de *chaque* question :
**la bonne réponse en A pour les 198**. On n'aurait pas retiré le contrôle de
position, on l'aurait remplacé par un confondant systématique — et d'autant
plus gênant que le modèle rend A dans 22,1 % des cas, sous les 25 % attendus.

## Le plan révisé

Nouveau drapeau `--rotation-tournante` : **un appel par question, la position
de la bonne réponse tournant *entre* les questions** (rang mod 4). Vérifié :
50 A / 50 B / 49 C / 49 D sur les 198. L'ordre vient d'un mélange graîné, donc
l'assignation est déterministe et **identique d'un bras à l'autre** — les bras
restent appariés question par question.

**Bras de réglage : 198 questions × 1 appel = 198 appels chacun**, soit le
**jeu entier** pour le prix d'un quart du protocole complet, et à peu près le
même coût que les 200 appels prévus en révision 0 — qui ne couvraient que 50
questions.

| bras | budget | message | fichier |
|---|---|---|---|
| A | 8192 | oui | `local_q4_t1_b8192_tournant.jsonl` |
| B | 2048 | oui | `local_q4_t1_b2048_tournant.jsonl` |

~2,3 h chacun au rythme mesuré (42,4 s/appel), sur le 4090, gratuit en argent.

## Ce que la révision change aux règles de lecture

Les règles 1 à 6 tiennent, avec deux ajouts :

7. **Le score d'un bras tournant n'est PAS comparable en absolu aux bras à 4
   rotations** déjà gelés : ce n'est ni le même protocole ni la même mesure par
   question. La comparaison A contre B est appariée et interne au balayage ; les
   bras gelés servent de repère, pas de terme de comparaison.
8. **Chaque question ne pèse plus qu'un tirage.** Le bruit de génération par
   question passe de p(1−p)/4 à p(1−p) ; ce qu'on gagne, c'est la disparition
   de la variance d'échantillonnage des questions, qui était le terme dominant.
   Ce choix est fait **pour la comparaison appariée**, et il serait mauvais pour
   une mesure absolue.

Le partiel à 4 rotations du bras 8192 (12 questions × 4) est **conservé**, gelé
sous `local_q4_t1_b8192_4rot_partiel.jsonl`. Il n'est pas jeté : il sert au
contrôle de stabilité, qui demande les 4 positions d'une même question.

---

## Révision 2 — 26/08/2026, bras A à 33/198, bras B sans aucune donnée

**Statut : pré-enregistré au sens strict.** Le bras B (2048) n'a pas démarré ;
le script de chaînage attend la fin du bras A. Cet amendement est écrit avant
que la moindre donnée du bras B existe, et il est daté pour qu'on puisse le
vérifier sur l'horodatage des fichiers.

**Origine : red team externe (z.ai GLM-5.3), constats 1, 2 et 3.** Les deux
affirmations mécaniques ont été vérifiées sur le code avant d'être retenues.

### Le défaut : la règle 3 confond deux événements sous un seul mot

La règle 3 dit « appel tronqué = non-mesure, exclu et compté ». Écrite avant
que les bras à budget existent, elle ne visait qu'un seul accident. Il y en a
deux, et ils n'ont rien de commun.

**Coupure au budget.** Le budget de raisonnement est épuisé, le message de
transition est injecté, **et le modèle rend une réponse.** Mesuré sur le bras
8192 : 7 justes sur 10 appels coupés, contre 25 % attendus au hasard. Un appel
coupé est donc une **mesure** — d'une réponse de qualité dégradée, ce qui est
exactement le coût du budget, c'est-à-dire la chose que ce balayage mesure.
L'exclure revient à retirer l'effet du traitement du bras traité.

**Troncature au plafond de sortie.** `finish_reason == "length"` contre
`--max-tokens 16384` : la réponse est coupée en cours d'écriture, il n'y a pas
de réponse à lire. C'est une panne d'instrument, sans rapport avec le budget.
Non-mesure, exclue et comptée — la règle 3 d'origine, qui reste juste ici.

### Pourquoi ça ne pouvait pas attendre le dépouillement

Sous `--rotation-tournante`, une question n'a **qu'un seul appel**. Exclure cet
appel n'enlève pas une rotation sur quatre : ça retire **la question entière**
du jeu apparié. Or la probabilité d'être coupé est une fonction de la question
— les questions dures brûlent plus de pensée (bras illimité : médiane 1111,
p90 2695, max sain 4371). La comparaison A contre B tournerait donc sur le
sous-ensemble des questions que 2048 arrive à survivre.

Direction du biais, et elle n'est pas neutre : elle **efface le coût de 2048**,
mène à « non départagés », et la règle 5 tranche alors « le budget le plus bas
gagne ». Le protocole aurait choisi 2048 par construction. C'est un biais de
sélection sur le traitement, décidé par la variable même qu'on étudie.

### Règle 3 (Révision 2)

> **3a. Coupure au budget = MESURE.** Un appel portant le message de transition
> (règle 4) est **conservé** et entre dans le score et dans l'appariement, avec
> le verdict que sa réponse mérite. Son taux et son exactitude propre sont
> publiés à part, jamais fondus dans le total sans être nommés.
>
> **3b. Troncature au plafond de sortie = NON-MESURE.** Un appel
> `finish_reason == "length"` est **exclu et compté**, dans tous les bras.
>
> **3c. Les deux calculs sont publiés côte à côte** — coupées gardées et
> coupées exclues. Aucun des deux n'est choisi après avoir vu lequel arrange.
> Si les deux mènent à des décisions opposées, le balayage est déclaré non
> concluant et le budget n'est pas réglé sur ces données.

### Effet sur les chiffres déjà publiés

Les 68,7 % (bras 512 nu) et 81,2 % (bras illimité) ont été calculés par
`depouiller_gpqa.py`, dont `par_question()` ingère tous les enregistrements :
un appel tronqué y compte comme **faux**. Vérifié sur le code, pas déduit. Ces
deux chiffres sont donc des mélanges d'erreur du modèle et d'échec de mesure,
en proportions inconnues. Ils sont **recalculés sous 3a/3b, les deux calculs
publiés**, et l'ancien chiffre reste au carnet avec la mention de son défaut.

### Ce qui est identifié et N'EST PAS amendé ici

Le constat 3 du red team vise l'échelle de décision de la règle 5 : entre le
hasard (25 %) et la récupération saine (~70 %) s'étend un régime que aucun
échelon ne rattrape, si bien qu'un bras 2048 récupérant à 40 % passerait tout.
**Non amendé**, et dit ici pour être sur le compte-rendu. La correction 3a le
désamorce en grande partie sans le viser : les appels coupés entrant désormais
dans la comparaison appariée, une récupération à 40 % produit une perte
appariée réelle et visible, là où l'exclusion la rendait invisible. Ce qui
reste à trancher, si le cas se présente, est le seuil de perte.

Le rattrapage symétrique à 32768 des appels tronqués des bras gelés reste **dû
et non lancé** — la carte est occupée.

---

## Révision 3 — 26/08/2026 : la règle 6 abandonne les 792 appels

**Statut : aucune donnée de mesure finale n'existe.** La règle 6 n'a jamais été
exécutée ; cet amendement précède entièrement les données qu'il régit.

### Ce que disait la règle 6, et pourquoi elle tombe

> 6. Le budget retenu est ensuite mesuré sur le jeu complet (198 questions,
>    792 appels).

Et la règle 8 justifiait la rotation tournante en réservant explicitement son
usage : « Ce choix est fait **pour la comparaison appariée**, et il serait
mauvais pour une mesure absolue. » J'ai d'abord opposé cette phrase à la
demande de diviser le jeu final. **Mesuré, l'argument ne tient pas.**

### La mesure, sur les données à 4 rotations déjà gelées

`cout_de_diviser.py` sur `local_q4_t1_budget512.jsonl`, 67 questions complètes
à 4 rotations. Décomposition de la variance des moyennes par question par
méthode des moments :

```
Var(moyennes observees)        0,12220
E[p(1-p)]  bruit de generation 0,10821
Var(p)     dispersion vraie    0,09515   = 78 % de la variance
```

**78 % de la variance est la dispersion des difficultés entre questions.** Elle
est incompressible : aucun appel supplémentaire ne l'achète, parce qu'elle ne
vient pas du bruit de génération mais du fait que les questions ne se valent
pas. Seuls les 22 % restants se divisent par le nombre de rotations.

| protocole | appels | ± 1 σ |
|---|---|---|
| 198 q × 4 rotations (ancienne règle 6) | 792 | 2,5 pt |
| 198 q × 2 rotations | 396 | 2,7 pt |
| 198 q × 1 rotation (tournante) | **198** | **3,2 pt** |

**Quadrupler les appels achète 0,7 point.** À ~4,1 h par tranche de 198 appels
mesurées le 26/08, c'est ~12 h de 4090 pour 0,7 point.

### Le point qui tranche vraiment

À budget d'appels **égal** (792), le partage optimal serait 1 rotation × 792
questions : ± 1,6 pt. Impossible — Diamond n'a que 198 questions. Les rotations
supplémentaires ne sont donc pas un investissement, ce sont **les miettes d'un
budget qu'on ne peut pas réaffecter**. C'est le plus mauvais emploi disponible,
et la seule raison de le faire serait de ne pas savoir qu'il l'est.

### Règle 6 (Révision 3)

> **6. Le budget retenu est mesuré sur les 198 questions en rotation
> tournante, un appel par question, 198 appels.** La barre publiée est
> l'erreur-type groupée par question, attendue autour de ± 3,2 pt d'après la
> décomposition ci-dessus. Cette barre est publiée **avec** la mention que
> 78 % de la variance est de la dispersion de difficulté et ne se réduit pas
> par plus d'appels : une barre de ± 3,2 pt sur ce jeu n'est pas un défaut de
> protocole, c'est la taille de GPQA Diamond.

### Ce que ça retire à la règle 8

La phrase « serait mauvais pour une mesure absolue » est **remplacée** par :
la rotation tournante coûte × 1,29 sur l'erreur-type absolue, ce qui est le
prix mesuré et non une objection de principe. La réserve d'origine était
qualitative et n'avait jamais été chiffrée ; elle l'est maintenant.

### Ce que ça ne change pas

Le contrôle de stabilité (une question sue est-elle sue dans les 4 positions)
demande les 4 rotations d'une même question. Il continue de tourner sur les
partiels à 4 rotations déjà gelés, qui existent pour ça, et **pas** sur les
bras tournants.

---

## Révision 4 — 26/08/2026 : le balayage ne mesurait pas ce qu'il croyait

Écrite **avant** que `local_q4_t1_b2048_tournant.jsonl` existe, donc avant toute
donnée du bras B. Déclenchée par le red team GLM-5.3 du 26/08
(`redteam/plan_suite_20260826.md`, constat 1) puis par quatre mesures faites
pour le vérifier, toutes sur des bras **déjà gelés**, zéro seconde de 4090.

### A. La calibration de 8192 est caduque

Le budget 8192 avait été posé à « 1,9× le pire appel sain » d'un échantillon
illimité de 30 appels couvrant **8 questions**. Sur le bras tournant à 55
questions distinctes, **45,5 % des appels touchent ce budget** (25 sur 55). Une
valeur calibrée pour un événement rare en attrape la moitié.

L'échantillon de calibration était cinq fois moins étalé que la population qu'il
devait représenter :

| échantillon | pensée mesurée, médiane | maximum |
|---|---|---|
| 30 appels / 8 questions (celui de la calibration) | 748 jetons | **1 320** |
| 55 appels / 55 questions tournantes | 1 506 jetons | **6 789** |

Huit questions ne peuvent pas porter une décision sur la dispersion : la
décomposition de variance du 26/08 attribue **78 % de la variance à la
dispersion de difficulté entre questions**, la part précisément absente d'un
échantillon de 8.

### B. La règle 4 est aveugle aux coupures nues — c'est le défaut le plus grave

La règle 4 définit la population « coupée au budget » par **la présence du
message de transition**, et relègue le seuil en jetons au rang de « filet de
sécurité ». Or un serveur lancé **sans** `--reasoning-budget-message` coupe la
pensée en pleine phrase et **n'injecte rien du tout**. Il n'y a alors aucun
message à chercher : le témoin unique est le mur en jetons.

Mesuré sur le bras 512 nu, 293 appels exploitables :

| témoin | appels détectés coupés |
|---|---|
| message de transition (règle 4 actuelle) | **0 / 293** |
| mur en jetons au budget (le « filet ») | **248 / 293 = 84,6 %** |

La règle 4 telle qu'écrite classe donc un bras à **84,6 % de coupure** comme
**100 % d'appels libres à pensée courte**. Ce n'est pas une imprécision, c'est
une inversion. Le carnet avait déjà vu le mur sur un échantillon de 60 (53 sur
60 exactement à 512, médiane 512, max 514) ; la mesure ci-dessus l'étend aux 293.

**Règle 4 (Révision 4).** La population « coupée au budget » est définie par
**la disjonction** de deux témoins, aucun n'étant subordonné à l'autre :

1. présence du message de transition dans le bloc de pensée ;
2. longueur du bloc de pensée, **tokenisée par le `/tokenize` du serveur**,
   supérieure ou égale à `budget − 2` jetons.

La tolérance de 2 jetons tient à ce que la coupure tombe sur une frontière de
jeton (mesure : max 514 pour un budget de 512). Un bras dont le serveur n'a pas
de message de transition ne peut être lu que par le témoin 2 ; **publier un tel
bras sans avoir appliqué le témoin 2 est interdit.**

Corollaire outil : le champ `marque` ajouté à `gpqa_diamond.py` ce jour est
**nécessaire et insuffisant**. Il ne voit que le témoin 1. Le fichier le dit à
l'endroit où il est écrit.

### C. La courbe de coupure, mesurée sur 55 questions au lieu de 8

`scripts/gpqa/courbe_de_coupure.py`, créé pour cette révision. Un bras à budget
*B* est **censuré à droite** : d'un appel coupé on sait que sa pensée naturelle
dépassait *B*, jamais de combien. La censure ne gêne pas en dessous de *B*, où
un appel coupé dépasse le seuil avec certitude. Le script publie donc un
**encadrement** — borne basse = appels connus au-dessus, borne haute = plus ceux
que la censure empêche de trancher — et refuse d'estimer au-delà du budget du
bras. Mesuré sur les 55 appels du bras 8192 :

| budget candidat | coupure prédite | statut |
|---|---|---|
| 512 | 89,1 % | mesure |
| 1024 | 78,2 % | mesure |
| **2048** | **63,6 %** | mesure |
| 4096 | 52,7 % | mesure |
| **8192** | **45,5 %** | mesure |
| 12288 et au-delà | [0,0 ; 45,5] % | **inestimable** |

### D. Ce que le balayage mesure vraiment — requalification

Le pré-enregistrement pose la question « combien de pensée faut-il ». Aux deux
points retenus, le bras A coupe 45,5 % de ses appels et le bras B en couperait
**63,6 %**. Le balayage ne compare donc pas une pensée libre à une pensée
bridée : **il compare deux guillotines**, à 18 points de taux de coupure d'écart.
Aucun des deux bras n'est le témoin « pensée libre » dont la question a besoin.

### E. Le témoin « pensée libre » était déjà sur le disque

`local_q4_t1_budget512.jsonl` (512 nu) et `local_q4_t1_b8192_tournant.jsonl`
(8192 + message) partagent **55 couples (question, rotation) identiques** :
même question, même permutation des réponses, même modèle, mêmes six paramètres
d'échantillonnage. Appariés :

| | exactitude sur les 55 couples |
|---|---|
| 512 nu | 34 / 55 = **61,8 %** |
| 8192 + message | 46 / 55 = **83,6 %** |

Table appariée : 33 justes des deux côtés, 8 faux des deux côtés, 1 juste
seulement à 512, **13 justes seulement à 8192**. McNemar exact bilatéral
**p = 0,0018** — la différence est établie.

**Ce que cette mesure n'établit pas.** Deux variables ont changé ensemble entre
les deux serveurs : la valeur du budget (512 → 8192) **et** la présence du
message de transition (absent → présent). Les 22 points ne sont attribuables ni
à l'une ni à l'autre séparément. La littérature citée au carnet fait porter au
message une part non nulle (Qwen3 9B / HumanEval : coupure nue 78 %, message à
budget 1000 → 89 %). C'est un écart mesuré entre deux **régimes**, pas un effet
de budget.

### F. Où sont les erreurs : dans l'interruption, pas dans le modèle

Découpage de chaque bras gelé selon le sort de sa pensée, IC95 de Wilson :

| bras | pensée finie seule | interrompue au budget | butée au plafond de sortie |
|---|---|---|---|
| 8192 + message (55) | **30/30 = 100 %** [88,6 ; 100] | 16/25 = 64,0 % [44,5 ; 79,8] | — |
| 512 nu (293) | 34/38 = 89,5 % [75,9 ; 95,8] | 167/248 = 67,3 % [61,3 ; 72,9] | **0/7** |
| illimité −1 (30) | **25/25 = 100 %** [86,7 ; 100] | — | **0/5** |

Deux régularités tiennent sur les trois bras : un appel qui **finit de penser
seul** est juste 89 à 100 fois sur 100 ; un appel **interrompu** tombe à 64–67 %,
et un appel qui bute sur le plafond de 16 384 jetons de sortie est faux
**12 fois sur 12**.

**Ce que ça n'établit pas, et il faut le dire fort.** « Libre » et « coupé » ne
sont pas deux traitements d'une même population : ce sont **deux populations de
questions**, séparées par leur difficulté — une question facile finit sa pensée
tôt, c'est ce qui la range du côté « libre ». L'écart de 36 points est donc
**une sélection, pas un effet causal de la coupure**. Il ne prouve pas qu'ôter
le budget rendrait justes les appels aujourd'hui coupés. Il indique seulement
où chercher, et la seule expérience qui trancherait est de rejouer **les mêmes
questions** sans budget.

### G. Règle 5 — l'échelon manquant

À 45,5 % et 63,6 % de coupure, la règle 5 sélectionne structurellement le budget
le plus bas : « à exactitude non départagée, le budget le plus bas gagne »,
alors que l'exactitude appariée sur 50 questions n'a pas la puissance de
départager deux bras qui amputent l'un et l'autre la majorité de leurs appels.

**Règle 5 (Révision 4), échelon inséré avant le départage par le coût.** Un bras
dont l'exactitude sur ses **appels coupés** est à plus de **15 points** sous son
exactitude sur ses **appels libres**, avec **n_coupés ≥ 30**, est écarté quel que
soit son score global — il ne mesure plus le modèle, il mesure sa propre
guillotine. Appliquée aux bras gelés : le bras 8192 affiche 100 % contre 64,0 %,
soit **36 points**, et le bras 512 nu 89,5 % contre 67,3 %, soit **22 points**.
**Les deux sont écartés par leur propre critère.**

### H. Conséquence : le chiffre GPQA local ne passera pas par le balayage

Le livrable demandé est *un chiffre GPQA Diamond sur le modèle local*. Un bras
qui ampute 45 à 64 % de ses appels ne le fournit pas : il fournit le chiffre
d'une configuration, sous un handicap qu'aucun comparable publié ne porte.

**Bras de production arrêté ici, avant toute donnée :** `--reasoning-budget -1`
(pas de guillotine), `--max-tokens 32768` (le plafond de 16 384 est faux
**12 fois sur 12** quand il est atteint), **198 questions en position
tournante**, un appel par question, fichier neuf. Coût attendu : ~4 h au rythme
mesuré du bras 8192 (4,05 h extrapolées à 198), davantage si la queue est
lourde — c'est précisément ce que ce bras mesurera.

Le balayage de budget n'est pas abandonné : il devient une **courbe coût/qualité
optionnelle**, à lire après le bras de production, et il n'est plus sur le
chemin du livrable.

### I. Température 1.0 — actée comme valeur constructeur

`1.0 / top_p 0.95 / top_k 20 / min_p 0.0` est la valeur publiée par la carte
Qwen3.8-27B en mode *thinking* (`DSH_QWEN_LOCAL_LOGBOOK.md:1757-1760`). Le 0,6
concerne d'autres Qwen. Aucun bras mesuré n'est affecté : tous ont passé 1.0
explicitement. Le défaut de `--temperature` dans `gpqa_diamond.py` passe de 0,6
à **1.0** pour que l'invocation nue cesse d'être un piège, et chaque
enregistrement porte désormais `temperature`, `top_p`, `max_tokens` et `extra`.

### J. Ce qui est identifié et N'EST PAS amendé ici

- **La queue de stockage décapitait 40 % des pensées.** 22 enregistrements sur
  55 font exactement 24 000 caractères et portent `</think>` sans `<think>`.
  Corrigé à 40 000 caractères et par les champs `reponse_car` / `pensee_car`
  mesurés **avant** troncature, mais les bras déjà gelés gardent le défaut : les
  longueurs de pensée qu'on en tire sont des **bornes basses**. Les taux du
  tableau C n'en dépendent pas (un appel coupé reste au-dessus du seuil quelle
  que soit la troncature du stockage).
- **La losslessness du décodage spéculatif n'est toujours pas mesurée.** Dette
  déclarée de la campagne (`SPECDEC_4090_BENCH.md:18`, `:184`, `:672`). Tant
  qu'elle tient, tout chiffre d'exactitude est publié « sous décodage spéculatif
  dflash2, égalité au glouton non vérifiée ». Sonde prévue avant le bras de
  production.
- **La qualité sous KV quantifié q8_0/q4_0 n'est pas mesurée**
  (`SPECDEC_4090_BENCH.md:640`). Limite déclarée, non levée ici.

---

## Révision 5 — la politique de plafond du bras de production, arrêtée pendant qu'il tourne

**Ce que je sais en écrivant.** Le bras `local_q4_t1_libre_tournant.jsonl` a
joué **8 questions**, dont **1 au plafond de 32768** (12,5 %, sans valeur
prédictive à ce n). Le rythme est de 137 s/question.

**Ce que je ne sais pas, et qui est précisément ce que cette révision arrête
avant de le savoir.** Le taux de plafond final. Quelles questions tronquent.
Leur exactitude. La largeur de l'encadrement qui en sortira.

La révision 4 a arrêté le plafond à 32768 sans dire ce qu'on fait des appels qui
l'atteignent. La règle 3b s'applique par héritage — tronqué = non-mesure, exclu,
encadrement — mais deux points ne sont pas couverts et le seraient trop tard si
j'attendais le dépouillement.

### K1. Un rattrapage à plafond plus haut est un TIRAGE NEUF, pas une reprise

Le bras échantillonne à température 1.0. On ne peut pas « finir » un appel
tronqué : rejouer la même question à 65536 produit une **autre** chaîne de
pensée, pas la suite de la première. Conséquence, à dire avant d'y avoir
intérêt :

**Aucun rattrapage ne peut FERMER l'encadrement.** Il peut seulement estimer
l'exactitude de la population « questions qui tronquent à 32768 », sous
l'hypothèse — déclarée, non vérifiable ici — qu'un nouveau tirage de la même
question à plafond plus haut est représentatif du tirage tronqué. Tout chiffre
issu d'un rattrapage sort donc avec cette hypothèse écrite à côté, et
l'encadrement brut reste publié en regard.

C'est une différence avec le rattrapage prévu pour les bras gelés (§ B2 du
plan) : là-bas le plafond de 16 384 était atteint par des appels **coupés au
budget**, et le budget est une propriété du serveur, pas du tirage. Ici la
troncature est une propriété du tirage lui-même.

### K2. Le seuil de déclenchement est celui qui existe déjà

Pas de seuil neuf inventé pour l'occasion. `depouiller_gpqa.py` refuse déjà de
publier un bras dont l'encadrement dépasse **5 points**, et la largeur de
l'encadrement est mécaniquement le taux de plafond. Donc :

| taux de plafond mesuré | ce qui se passe |
|---|---|
| ≤ 5 % | l'encadrement est publié tel quel, sans rattrapage |
| > 5 % | rattrapage dû, à 65536, sur **exactement** les questions tronquées, même serveur, mêmes paramètres d'échantillonnage, fichier neuf |

Le rattrapage ne rejoue **pas** les questions non tronquées : elles sont déjà
mesurées, et les rejouer transformerait le bras en un tirage moyen sur deux
plafonds, ce qui n'est plus le chiffre d'aucune configuration.

### K3. Ce qui est publié, dans tous les cas

Trois nombres, jamais un seul :

1. **borne basse** — tous les tronqués comptés faux ;
2. **borne haute** — tous les tronqués comptés justes ;
3. si rattrapage il y a : **l'estimation par tirage neuf**, avec l'hypothèse de
   K1 écrite à côté et le nombre de questions concernées.

Le chiffre « tronqués exclus » que `depouiller_gpqa.py` affiche en tête n'est
**pas** le chiffre du bras : c'est la borne haute conditionnée à ce que les
tronqués se comportent comme les autres. Il ne doit pas circuler seul.

### K4. Ce que cette révision n'amende pas

Le plafond reste **32768**, le budget reste **−1**, la configuration serveur
reste `specdec-q38-plain` (sans spéculation, cf. le verdict B1 du 26/08 au
soir), et les 198 questions restent en position tournante. Aucun paramètre du
bras en vol n'est touché : cette révision porte uniquement sur ce qu'on aura le
droit de dire de ses résultats.

---

## Révision 6 — 26/08/2026 19:35 : une pause du bras déclenche un rejeu, et il faut le dire avant

**Écrite pendant que le bras tourne, et avant que les enregistrements rejoués
existent.** Au moment où ces lignes sont commitées, le fichier porte 21
enregistrements et le processus vient de repartir en annonçant « reprise : 19
appels deja en place ». Les 2 rejeux ne sont pas encore écrits.

### Ce qui s'est passé

Le bras a été **mis en pause à 21/198** pour libérer la carte le temps d'un
essai agentique local, puis relancé. La pause elle-même est sans effet sur la
mesure : le fichier est en ajout seul, `deja_fait()` saute les couples
(Record ID, rotation) déjà présents, et la reprise est prévue par le script.

**Mais `deja_fait()` ne compte pas un appel TRONQUÉ comme fait** — par dessein,
et le commentaire du code le dit : sans cette clause, un rattrapage à plafond
plus haut sauterait en silence les questions qu'il est censé rejouer.

Conséquence non voulue : une simple pause déclenche, à la reprise, **un rejeu
des questions tronquées, au même plafond de 32 768**. Sur les 21
enregistrements, 19 sont sautés et **2 sont rejoués**.

### Pourquoi ce n'est pas anodin

`depouiller_gpqa.py` dédoublonne les couples (id, rotation) en gardant **le
dernier**. Et la règle 3b exclut toujours du taux les réponses tronquées au
plafond. Donc, sans intervention :

- le tirage d'origine, tronqué et **exclu** du taux, serait remplacé en silence
  par un second tirage, complet et **compté** ;
- la **borne basse** du bras — celle qui compte les tronquées comme fausses —
  deviendrait incalculable à partir du jeu dédoublonné ;
- et le taux publié ne serait plus celui du bras pré-enregistré, sans que rien
  ne le signale.

C'est exactement le défaut que la Révision 5 avait nommé une heure plus tôt :
**à température 1,0, un rejeu est un NOUVEAU tirage** (K1). Il ne « complète »
pas le tirage d'origine, il le remplace.

### Ce qui est décidé, et qui ne change rien au bras

**D1. Le chiffre du bras est calculé sur le PREMIER tirage de chaque couple
(id, rotation).** C'est le bras tel qu'il a été pré-enregistré : un tirage par
question, celui d'origine. La pause devient alors strictement sans effet sur la
mesure. Un drapeau `--premier` a été ajouté à `depouiller_gpqa.py` pour cela, et
il annonce son propre mode en tête de sortie.

**D2. Les tirages supplémentaires sont publiés séparément**, étiquetés
« rejeu au même plafond », et ne sont **jamais** mélangés au taux du bras.

**D3. Les trois nombres de la Révision 5 K3 restent dus** — borne basse, borne
haute, estimation par rejeu — et sont désormais tous les trois calculables :
les deux premiers sur le premier tirage, le troisième sur le dernier. C'est
`depouiller_gpqa.py` avec et sans `--premier`.

**D4. Ce rejeu n'est PAS le rattrapage de la Révision 5 K2**, qui se joue à un
plafond **plus haut**. Un rejeu au même plafond a toute chance de tronquer à
nouveau. Le rattrapage reste dû, et reste à faire.

**D5. Rien de ce qui est déjà sur le disque n'est modifié ni effacé.** Les 21
enregistrements restent tels quels ; toute la Révision 6 est une règle de
lecture, pas une réécriture.

### Ce qui n'est pas prétendu

Que la pause était sans coût. Elle a consommé un appel de plus par question
tronquée, et elle décale la fin du bras d'autant. Elle a été faite pour une
raison nommée — libérer le slot unique pour un essai local qui, lui non plus,
ne pouvait pas attendre — et le coût est celui-là, déclaré.
