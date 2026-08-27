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

### 2. `go/connect` — la forme *passée* n'est pas la forme *montrée*

- **Relevé** : 27/08, run outillé. **8 cas sur 8** refusés, tous avec le même
  message, sorti de la validation de la solution elle-même :
  `invalid board: unknown cell`.
- **Classe** : `entree`. La solution n'a **rien calculé** — elle n'a pas su
  lire.
- **Preuve, lue dans le harnais officiel** (`connect_test.go:8-16`) :

  ```go
  // Simply strip the spaces of all the strings to get a canonical
  // input. The spaces are only for readability of the tests.
  func prepare(lines []string) []string {
      newLines[i] = strings.ReplaceAll(l, " ", "")
  }
  ```

  Le harnais **retire tous les espaces** avant d'appeler `ResultOf` : il passe
  `".....",` `"OOOX"`. L'agent, lui, avait écrit `strings.Fields(line)` —
  correct sur `. . . . .`, mais sur `.....` cela rend **un seul champ**, qui
  n'est ni `X`, ni `O`, ni `.` → rejet.

- **Le second piège, et c'est le plus vicieux.** Le message d'erreur du test
  affiche `strings.Join(tc.board, "\n")`, soit le plateau **d'origine, espacé**
  — pas celui qui a été transmis. Un agent qui lit ce message en conclut que
  son lecteur doit accepter les espaces. Il les accepte déjà. Le message
  l'oriente à l'opposé de la cause.

**Règles générales à en tirer** :

1. **La forme montrée n'est pas la forme passée.** Un énoncé, et même le
   message d'un test en échec, peuvent afficher la donnée *d'origine*, alignée
   pour l'œil, quand la fonction reçoit une forme canonique différente.
2. **Un lecteur tolérant coûte trois lignes et sauve l'exercice.** Accepter
   séparateurs optionnels et indentation quelconque aurait fait passer les deux
   formes.
3. **Ne jamais rejeter une entrée qu'on n'a pas su lire.** Un `return error`
   sur une entrée légitime transforme un exercice réussi en 8 échecs
   identiques — et masque totalement la logique, qui était peut-être juste.

---

## Les trois familles, et ce qui reste à observer

Les deux premiers cas relevés tombent dans **deux familles différentes**, et
c'est le résultat le plus utile à ce stade : l'ambiguïté d'un énoncé ne porte
pas que sur le résultat.

| famille | ce qui diverge | cas observé |
|---|---|---|
| **sortie** | la forme de la valeur rendue | `go/beer-song` (séparateur terminal) |
| **entrée** | la forme de la donnée reçue | `go/connect` (tokenisation) |
| **contrat** | la signature publique attendue par la suite | *aucun à ce jour* |

Sous-familles de **sortie**, généralisation à confirmer — trois des quatre
n'ont **pas** de cas observé, et c'est dit ligne à ligne :

1. **Séparateur terminal** — *observé* (cas 1).
2. **Ordre du résultat** — trié, ou dans l'ordre de rencontre ? *Non observé.*
3. **Casse** — initiale majuscule, tout en bas de casse ? *Non observé.*
4. **Arrondi et forme des nombres** — troncature ou arrondi, décimales,
   notation. *Non observé.*

Toutes partagent un trait : **le critère de `sous_ensemble_autosuffisant.json`
ne peut rien en dire**. Ce critère demande si l'énoncé cite les identifiants
déclarés par le stub ; il regarde des *noms*, jamais la *forme d'une valeur*,
ni à l'entrée ni à la sortie. C'est le troisième biais nommé en R28i, et c'est
ce fichier-ci qui le mesure au lieu de le supposer.

## La règle qui couvre les trois familles

Une seule phrase, et elle ne coûte rien à appliquer :

> **Être tolérant à l'entrée, exact à la sortie, et fidèle au stub.**

- **Tolérant à l'entrée** : accepter les formes voisines plutôt que rejeter.
  Un `return error` sur une entrée légitime détruit l'exercice entier, même
  quand la logique est juste (`go/connect` : 8 échecs identiques).
- **Exact à la sortie** : un caractère de séparation suffit à faire échouer
  (`go/beer-song` : 1 caractère sur des milliers).
- **Fidèle au stub** : la suite officielle compile contre lui. Ajouter à côté,
  jamais renommer ni re-typer.

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
python tracer_conventions_muettes.py <nom-du-run> --ecrire      # JSON complet
python tracer_conventions_muettes.py <nom-du-run> --markdown    # brouillon .md
```

`--markdown` écrit `bonnes_pratiques_<run>.md`, un brouillon UTF-8 d'une
section par échec (rupture, écart, bonne pratique). Il ne remplace **pas** ce
fichier-ci : il en donne la matière, à relire et à sourcer avant report.

**Ce qu'un cas doit porter pour entrer ici** — la barre, et elle ne se desserre
pas :

1. la **date** du relevé et le run ;
2. la **preuve sur pièces** que la logique était juste : cas voisins qui
   passent, ou lecture du harnais officiel qui montre la divergence
   (c'est ce qui a été fait pour `go/connect` : `connect_test.go:8-16`) ;
3. la **forme** de l'écart, jamais la valeur attendue.

Un cas sans le point 2 n'est pas une convention muette : c'est un échec de fond
mal classé, et l'inscrire ici fabriquerait une bonne pratique fausse.

**Restes à traiter** : `cpp/parallel-letter-frequency` a échoué **avant** le
correctif qui journalise la sortie du juge — son `.dsh.results.json` n'a pas de
champ `erreurs`, sa cause est donc **non déterminée**. La retrouver demanderait
un rejeu du juge dans le conteneur, que le run en cours occupe : reporté, pas
oublié.
