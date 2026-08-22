# `ref2/` — second bras known-GOOD

Douze solutions aux mêmes tâches que `ref/`, **écrites sans lire `ref/`**, par
Claude Code (modèle par défaut) le 22/08/2026. Elles ne remplacent pas `ref/` :
elles répondent à une question que `ref/` ne peut pas se poser à lui-même.

## Ce que ce bras mesure, et que le bras `ref/` ne mesure pas

`ref/` prouve que le juge **accepte la solution de référence**. Il ne prouve pas
que les assertions testent le **contrat de l'énoncé** plutôt que les choix de
conception de cette solution-là. Une assertion sur-ajustée à `ref/` passerait
`ref/` et refuserait toute autre implémentation correcte — et un modèle qui
propose une conception différente mais juste serait compté en échec.

Une seconde implémentation correcte, écrite indépendamment, est exactement ce
contrôle. Mesure du 22/08 : **12/12**, donc sur ces douze tâches les assertions
tiennent sur au moins deux conceptions distinctes.

## Ce bras a déjà tiré

La première version de `t35.jl` détectait l'erreur d'arrondi exactement (TwoSum
de Knuth pour la somme, `fma` pour produit et quotient) et n'élargissait la
borne **que** si l'opération avait réellement arrondi. Elle **conserve la
propriété de contenance** — elle n'est pas fausse — mais elle laisse la borne
**égale** au résultat flottant, alors que le contrat demande une borne
strictement à l'extérieur. Le juge l'a dit en un mot :
`les bornes ne sont pas elargies vers l'exterieur : [0.3, 0.30000000000000004]`.

Ce n'était donc pas un faux positif du juge : le juge avait raison, et le
contrôle a fait son travail dès sa première utilisation.

## Statut : AVIS, pas refus

Conforme à la règle « la fatalité se mérite » : ce bras **rapporte** et ne fait
pas échouer `--selftest`. Un `!!! AVIS` signifie l'une de deux choses, et il
faut lire laquelle avant d'agir : ou bien `ref2/` est fausse, ou bien une
assertion teste la conception de `ref/` et pas le contrat.

## Contamination déclarée

Trois des douze n'ont **pas** été écrites à l'aveugle, parce que j'avais lu une
partie du juge plus tôt dans la même session :

| tâche | ce qui avait été vu avant d'écrire |
|---|---|
| `t31` | la référence **et** le fichier d'assertions, en entier |
| `t22` | les deux tolérances du juge (`1e-6`, `1e-5`) |
| `t34` | les deux témoins de primalité utilisés par le juge |

Les neuf autres ont été écrites à partir du seul énoncé `prompts/tNN.txt`.
Le détail de la mesure (temps, essais, échec de `t35`) est en 3.8 du logbook
`docs/DSH_QWEN_LOCAL_LOGBOOK.md`.
