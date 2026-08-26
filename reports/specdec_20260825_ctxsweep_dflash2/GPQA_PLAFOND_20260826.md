# GPQA : le plafond de tokens est un facteur, pas un detail — 26/08/2026

Ce fichier existe parce qu'un resume de conversation ne conserve pas les
preuves. Tout ce qui suit est mesure sur des fichiers presents sur le disque et
recalculable par les commandes donnees en bas.

## 1. Le fait

Les 160 appels du rodage bf16 (`or_bf16.jsonl`) portent sur **exactement les
memes 40 questions x 4 rotations** que les 160 premiers appels du run Q4 local
(`local_q4.jsonl`). Recouvrement verifie : 160 couples (id, rotation) communs.
La comparaison peut donc etre **appariee**, ce qui est le seul cadre ou ces
chiffres veulent dire quelque chose.

| | mediane tokens sortie | q90 | tronques (finish=length) | non-parses |
|---|---|---|---|---|
| Q4 local (16384) | 737 | 1 130 | 6 / 160 = 3,8 % | 6 = 3,8 % |
| bf16 AkashML (16384) | 3 653 | 16 384 | 42 / 160 = 26,2 % | 40 = 25,0 % |

**38 des 40 non-parses bf16 ont un contenu VIDE a exactement 16 384 tokens.**
Ce ne sont pas des refus de format : c'est le budget epuise avant qu'un seul
caractere de reponse soit ecrit.

## 2. La cause, et pourquoi elle n'etait pas visible

`<think>` present dans le contenu : **local 150/160, bf16 0/160.**

Sur OpenRouter le raisonnement part dans un champ `reasoning` distinct que le
harnais ne lit pas ; en local llama.cpp le laisse dans le contenu. Les deux
cotes sont bien plafonnes sur le TOTAL, la dissymetrie n'est donc pas dans la
comptabilite — elle est dans la CONSOMMATION : le bf16 raisonne cinq fois plus
longtemps que le Q4 pour les memes questions, et tape le plafond un quart du
temps.

Verification precoce trompeuse, a garder en memoire : sur 4 rotations testees le
24/08, local 210 tokens contre bf16 179/215/191/188 — « meme ordre de grandeur ».
A 160 appels apparies, mediane 737 contre 3 653. **Un echantillon de 4 avait
produit exactement la conclusion inverse de la bonne.**

## 3. Le piege de selection, a ne surtout pas publier

Deux chiffres circulent et **aucun des deux n'est la mesure** :

- sur les 160 appels : local 115, bf16 114 → defavorise bf16 par construction,
  puisque ses 40 budgets epuises sont comptes faux ;
- sur les 120 appels ou bf16 a repondu : **bf16 95,0 %, local 83,3 %** →
  favorise bf16 par construction, puisque ce sous-ensemble est selectionne PAR
  SA PROPRE REUSSITE. Ce sont les questions ou il n'a pas eu besoin de reflechir
  jusqu'au plafond, donc les plus faciles.

Conditionner sur une variable qui depend du resultat d'un des deux bras casse
l'appariement. Le 95,0 % est particulierement seduisant et particulierement
faux : il est proche du 89,2 publie, ce qui donnerait l'illusion d'un harnais
valide.

## 4. Ce qui est fait

Rattrapage **symetrique**, plafond 16384 → 32768, ne rejouant qu'un appel a la
fois tronque ET sans reponse :

    if d.get("finish_reason") == "length" and not d.get("donne"): continue

- bf16 : lance le 26/08, « reprise : 124 appels deja en place » → 36 rejoues.
  Les 4 non-parses NON tronques restent comptes faux : le modele avait la place
  d'ecrire le format et ne l'a pas fait. Les rejouer serait desserrer la barre.
- Q4 local : **le meme protocole**, applique quand le run de 792 aura fini. Il
  n'a que 6 tronques ; le rattrapage y sera marginal, mais il aura lieu et il
  sera dit.

## 5. La lecture, fixee AVANT de voir le resultat

- bf16 rattrape ≈ 89,2 (a ±7 pres, n = 40) → le harnais reproduit la reference
  publiee ; le chiffre du Q4 local devient interpretable.
- bf16 rattrape ≪ 89,2 → le harnais sous-mesure pour une autre raison ; **ne pas
  comparer le local a 89,2**, et chercher d'abord ce qui manque.

Reserve qui survivra au rattrapage : si le bf16 raisonne cinq fois plus que le
Q4, la comparaison porte sur deux regimes de calcul differents. La cause n'est
pas tranchee — quantification qui raccourcit la pensee, ou effort de raisonnement
par defaut different chez AkashML (aucun parametre `reasoning` n'est envoye,
donc c'est le defaut du fournisseur qui s'applique). **A dire comme confondu,
pas comme resultat.**

## 6. Recalcul

    cd scripts/gpqa
    python depouiller_gpqa.py or_bf16.jsonl
    python depouiller_gpqa.py local_q4.jsonl
    python depouiller_gpqa.py --comparer local_q4.jsonl or_bf16.jsonl

## 7. Le meme defaut, ailleurs, le meme jour

La sonde de memorisation a rendu **59 sorties vides sur 60**, tous a 3 000
tokens : meme cause exactement. Corrige en coupant le bloc de pensee
(`reasoning: {enabled: false}`) — la tache est une completion, pas un
raisonnement, et la coupure s'applique aux deux bras donc ne peut pas creuser
l'ecart mesure. Un garde-fou a ete ajoute : une sortie vide est enregistree
`non_mesure` et **exclue** du depouillement, jamais comptee comme « similarite
zero ». Sans lui la sonde aurait conclu « A = B = 0, aucune memorisation » —
une absence de mesure maquillee en resultat.
