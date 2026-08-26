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
