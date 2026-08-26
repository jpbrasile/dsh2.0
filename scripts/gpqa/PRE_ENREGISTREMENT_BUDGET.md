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
