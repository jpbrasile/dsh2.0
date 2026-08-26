# Sonde de memorisation : resultat, et ce qu'il ne dit pas — 26/08/2026

Etape 0 du plan (`reports/PLAN_MESURE.md`), faille n°1 de la critique :
le corpus polyglot est-il dans le pre-entrainement du modele ?

## Le protocole

Chaque exercice est joue deux fois sur LE MEME fichier de test, dont on donne
les 40 premiers pour cent en demandant la suite :

- **A. REEL** — le prefixe tel quel ; le modele peut reconnaitre l'exercice.
- **B. ANONYME** — meme structure, memes valeurs, meme difficulte, mais toute
  graphie du nom remplacee par un neutre de meme style. Seule l'ETIQUETTE
  disparait.

La cible est renommee de la meme facon dans B : on compare bien la meme tache.
Deux metriques, jamais une seule — la similarite floue se discute, le rappel de
lignes exactes (lignes non triviales restituees mot pour mot) est le chiffre
difficile a expliquer autrement.

## Le resultat, 120 paires, 240 appels, 0 non-mesure

| metrique | A reel | B anonyme | ecart apparie | z |
|---|---|---|---|---|
| **rappel de lignes exactes** | 30,3 % | 25,4 % | **+2,0 pt ± 0,9** | **+2,33** |
| similarite floue | 30,0 % | 24,2 % | +0,8 pt ± 1,6 | +0,47 |

Signes : A>B 49, A<B 31, egaux 40 (mediane +0,0 pt).

Par langage, le rappel exact : cpp +8,4 / python +3,9 / java +1,7 / go +1,1 /
rust −0,8 / javascript −1,6. La dispersion par exercice est enorme :
`cpp/gigasecond` +25,0, `cpp/phone-number` **−39,4**. Aucun exercice memorise
qui dominerait.

## LA LIMITE QUI PLAFONNE L'INTERPRETATION

**Le nom porte de la SEMANTIQUE, pas seulement de l'IDENTITE.** Un fichier de
test nomme `gigasecond` dit au modele de quoi il s'agit — de l'arithmetique sur
le temps, 10^9 secondes. Le meme fichier nomme `widget` ne dit rien. Un modele
qui n'aurait JAMAIS vu Exercism reussirait quand meme mieux le bras A, parce que
le nom l'informe sur ce que la fonction doit faire.

Donc **+2,0 pt est une BORNE SUPERIEURE de la memorisation, pas une mesure de
la memorisation.** L'ecart se decompose en (a) rappel du fichier precis et
(b) indice semantique, et cette sonde ne les separe pas. Elle repond a une
question plus etroite que celle qu'on aimerait poser : *l'identite aide-t-elle*,
et non *le modele se souvient-il*.

Un troisieme bras separerait les deux — le nom remplace par celui d'un AUTRE
exercice reel, semantique presente mais identite fausse. Non fait.

## Deux defauts corriges en route, et leur cout

1. **59 sorties vides sur 60** au premier essai : tout le budget parti dans le
   bloc de pensee, contenu vide. Compter ces zeros aurait produit un
   « A = B = 0, aucune memorisation » entierement fabrique. Corrige en coupant
   le raisonnement (la tache est une completion ; la coupure s'applique aux deux
   bras donc ne peut pas creuser l'ecart). Garde-fou ajoute : une sortie vide est
   `non_mesure` et EXCLUE, jamais comptee comme similarite nulle.

2. **Anonymisation cassee sur les noms d'un seul mot.** Les sept graphies
   s'effondraient sur la meme cle de dictionnaire et Python gardait la derniere :
   `diamond` -> `widget ops`, AVEC UNE ESPACE. Le bras anonyme recevait
   `#include "widget ops.h"` — du code qui ne compile pas. Il devenait plus dur
   pour une raison etrangere a l'identite.

   **Ce defaut portait TOUT l'effet :**

   | sous-ensemble | n | ecart A−B | z |
   |---|---|---|---|
   | noms d'un seul mot (casses) | 26 | +7,8 pt ± 3,7 | +2,12 |
   | noms de plusieurs mots (sains) | 34 | +1,1 pt ± 1,9 | +0,57 |

   Corrige : un nom d'un mot recoit un neutre d'un mot. Invariant de forme
   ajoute — une graphie sans espace ne peut pas recevoir un neutre avec espace —
   verifie sur les 225 exercices du corpus, 0 refus. `cpp/diamond` est passe de
   **+87,9 pt a +1,7 pt**.

**Trajectoire de la mesure, a garder comme lecon :** +12,5 pt (mise au point,
n=6) -> +4,0 pt (n=60, anonymisation cassee) -> **+2,0 pt** (n=120, corrigee).
Chaque correction d'un defaut de MON harnais a reduit l'effet. Le premier
depouillement imprimait « le corpus est contamine » ; c'etait mon bug qui
parlait.

## Ce que ca donne avec l'autre sonde

La mesure du 26/08 sur le run aider AVEUGLE (208 exercices, l'agent ecrit sans
executer) : similarite au corrige canonique, mediane 12,2 %, **zero exercice
au-dessus de 80 %**, ecart passes/echoues +3,1 pt de mediane.

Les deux sondes attaquent des faces differentes et reviennent petites toutes les
deux :

- cote SOLUTION : pas de regurgitation verbatim du corrige ;
- cote FICHIER DE TEST : un avantage lie au nom de +2,0 pt, borne superieure.

**Ce qui n'est PAS etabli :** aucun lien mesure entre ces +2,0 pt et un taux de
reussite. Dire « la contamination n'explique pas le 78,7 % » serait un saut. Ce
qui est etabli, c'est que les deux sondes disponibles rendent un signal faible.

## Reserve de portee

Les 120 exercices sont la tete alphabetique du corpus (20 par langage, ordre du
disque), pas un tirage au hasard. Le lot de TEST du banc (`--pas 6 --decalage 0`)
est reparti sur tout l'alphabet : le recouvrement est partiel.

## Recalcul

    cd scripts/gpqa
    python depouiller_sonde.py sonde_memo_v3.jsonl

Journaux conserves : `sonde_memo.jsonl` (sorties vides, defaut 1),
`sonde_memo_v2.jsonl` (anonymisation cassee, defaut 2), `sonde_memo_v3.jsonl`
(corrige, c'est celui-ci).
