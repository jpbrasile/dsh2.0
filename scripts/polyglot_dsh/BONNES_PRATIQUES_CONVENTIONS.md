# Conventions muettes du corpus polyglot — bonnes pratiques

**Ce fichier n'entre pas dans le banc.** Il s'écrit à côté, il s'accumule, il
servira plus tard. Le donner à l'agent pendant un run de la variante D
**casserait l'instrument de mesure** : ce que la variante D mesure, c'est
précisément ce qu'un agent trouve *sans* information complémentaire. Une
convention tirée de la suite cachée est une information complémentaire.

Décision de l'opérateur, 27/08 : *« fais simplement un fichier des best
practices, on l'utilisera plus tard ; sinon tu casses l'instrument de mesure. »*

---

## D'où vient ce fichier

De `tracer_conventions_muettes.py`, qui lit la sortie du juge conservée dans
chaque `.dsh.results.json` (champ `erreurs`) et classe les échecs :

| classe | ce qu'elle dit |
|---|---|
| `blancs` | obtenu et attendu deviennent identiques une fois tous les blancs retirés |
| `casse` | identiques à la casse près |
| `ordre` | mêmes lignes, ordre différent |
| `fond` | l'échec n'est **pas** un problème de forme — hors sujet ici |

Les trois premières classes désignent des échecs où **la logique est juste et
la convention est muette** : l'énoncé ne dit pas la forme attendue de la valeur
de retour, et rien dans le stub ne la trahit.

Le fichier machine correspondant est
`conventions_muettes_<run>.json`. Il porte deux familles de champs, et la
séparation est délibérée :

- `injectable` — la **forme** de l'écart, jamais la valeur ;
- `obtenu` / `attendu` — les valeurs réelles, **diagnostic humain seulement**.

Tout ce qui est recopié ci-dessous vient de `injectable`.

---

## Cas observés

### 1. `go/beer-song` — séparateur terminal après le dernier élément

- **Relevé** : 27/08, deux fois (run initial, puis run outillé — la chaîne
  d'outils n'y change rien).
- **Classe** : `blancs`. L'attendu prolonge l'obtenu de **1 caractère**.
- **Convention** : `Verses` pose un séparateur **après le dernier couplet**, pas
  seulement *entre* les couplets.
- **Pourquoi l'énoncé ne peut pas le dire** : il affiche la chanson *rendue*,
  où le dernier couplet n'est visiblement suivi de rien. Un séparateur terminal
  est invisible à l'œil dans un exemple rendu.
- **Preuve que la logique était juste** : les 5 cas de `Verse` et les 2 cas
  d'erreur passaient. Seul l'assemblage échouait, et d'un caractère.

**Règle générale à en tirer** — quand une fonction assemble N éléments en une
chaîne, la question « le séparateur est-il *entre* les éléments ou *après
chacun* ? » n'a pas de réponse par défaut, et un exemple rendu ne la tranche
jamais. Produire les deux et choisir n'est possible qu'avec un test ; sans
test, c'est un tirage à pile ou face à 50 %.

---

## Les quatre conventions qu'un énoncé ne porte jamais

Généralisation, à confirmer par de nouveaux relevés — trois des quatre n'ont
pas encore de cas observé, c'est dit :

1. **Séparateur terminal** — *observé* (cas 1 ci-dessus).
2. **Ordre du résultat** — une collection rendue triée, ou dans l'ordre de
   rencontre ? *Non observé à ce jour.*
3. **Casse** — initiale majuscule, tout en bas de casse ? *Non observé à ce
   jour.*
4. **Arrondi et forme des nombres** — troncature ou arrondi, nombre de
   décimales, notation. *Non observé à ce jour.*

Ces quatre-là partagent un trait : **le critère de `sous_ensemble_autosuffisant.json`
ne peut rien en dire**. Ce critère demande si l'énoncé cite les identifiants
déclarés par le stub ; il regarde des *noms*, jamais la *forme d'une valeur de
retour*. C'est le troisième biais nommé en R28i, et c'est ce fichier-ci qui le
mesure au lieu de le supposer.

---

## Usage prévu, et ses conditions

Le jour où ce fichier sert :

- **Bras distinct, étiqueté.** Un run qui reçoit ces conventions n'est plus la
  variante D. Il ne se compare ni à elle, ni au banc aider — dont le modèle
  n'a, lui, aucun outil.
- **La forme, jamais la valeur.** On lit `injectable`. On ne lit pas `attendu`.
  Donner la valeur attendue ne mesure plus rien du tout.
- **Le chiffre que ça produit** est le coût de l'ambiguïté des énoncés, pas une
  performance de l'agent. Deux colonnes, deux noms.

## Entretien

```
python tracer_conventions_muettes.py <nom-du-run> --ecrire
```

À relancer en fin de run, puis reporter ici les cas neufs — un titre par
convention, avec la date du relevé et la preuve que la logique était juste.
Un cas sans cette preuve n'est pas une convention muette : c'est un échec de
fond mal classé.
