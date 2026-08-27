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

### 3. `go/kindergarten-garden` — l'énoncé se contredit, et il se tait

Deux échecs distincts dans le même exercice. C'est le cas le plus instructif du
lot.

**3a. Le vocabulaire : trois formes, une seule bonne.**

- **Relevé** : 27/08. 7 cas classés `casse=1 lexique=6`.
- **Écart** : `["Radish" "Clover" "Grass" "Grass"]` au lieu de
  `["radishes" "clover" "grass" "grass"]`.
- **Preuve, dans l'énoncé lui-même** — les mêmes quatre plantes y figurent
  sous **trois formes différentes** :

  | ligne | forme | exemple |
  |---|---|---|
  | 6 | prose, minuscule pluriel | « grass, clover, **radishes**, and **violets** » |
  | 19-22 | **tableau**, capitale singulier | `Grass \| G`, `Radish \| R`, `Violet \| V` |
  | 58 | liste, capitale initiale | « Violets, radishes, violets, radishes » |

  L'agent a pris la forme du **tableau**. La suite attend celle de la **prose**.

**Ce qui rend le piège vicieux** : le tableau est la présentation la plus
*structurée*, donc la plus autoritaire à l'œil — c'est celle qu'on choisit
quand on cherche une spécification. Elle n'est pas la bonne. Rien dans
l'énoncé ne dit laquelle fait foi ; c'est un tirage à pile ou face.

**Règle** : quand un énoncé donne le même vocabulaire sous plusieurs formes,
c'est la **prose** qui fait foi, pas le tableau. Et un tableau qui sert à
associer un **code** (`R` → radish) donne le code, pas forcément le libellé
de sortie.

**3b. Quatre exigences que l'énoncé ne formule jamais.**

- **Relevé** : 4 cas — `wrong_diagram_format`, `odd_number_of_cups`,
  `duplicate_name`, `invalid_cup_codes` — tous avec
  `NewGarden expected error but got nil`.
- **Preuve** : recherche de « error », « invalid », « duplicate », « odd » dans
  l'énoncé → **aucune occurrence**. La suite officielle teste une validation
  dont l'énoncé ne dit pas un mot.

**Et c'est le symétrique exact de `go/connect`** :

| | `go/connect` | `go/kindergarten-garden` |
|---|---|---|
| faute | refuse des entrées **valides** | accepte des entrées **invalides** |
| coût | 8 échecs | 4 échecs |

Les deux perdent. La règle n'est donc pas « sois tolérant », qui ferait perdre
le second, ni « valide tout », qui ferait perdre le premier :

> **Tolérant sur la _forme_ de ce qui est valide ; strict sur les contraintes
> que le _type_ implique.**

Un diagramme de jardin a un nombre pair de godets, des noms uniques, des codes
dans un alphabet fini. Ces contraintes-là se déduisent du domaine, même quand
l'énoncé se tait. L'espacement des godets, lui, ne se déduit de rien.

---

## Les quatre familles, et ce qui reste à observer

Trois exercices, **quatre familles** déjà — et c'est le résultat le plus utile
à ce stade : l'ambiguïté d'un énoncé ne porte pas que sur le résultat.

| famille | ce qui diverge | cas observé |
|---|---|---|
| **sortie** | la forme de la valeur rendue | `go/beer-song` (séparateur terminal), `go/kindergarten-garden` (vocabulaire) |
| **entrée** | la forme de la donnée reçue | `go/connect` (tokenisation) |
| **exigence** | un comportement que l'énoncé ne demande jamais | `go/kindergarten-garden` (4 validations) |
| **contrat** | la signature publique attendue par la suite | *aucun à ce jour* |

Sous-familles de **sortie** — deux sur quatre ont maintenant un cas, et les
deux autres sont dites sans :

1. **Séparateur terminal** — *observé* (cas 1).
2. **Vocabulaire : casse, singulier/pluriel** — *observé* (cas 3a).
3. **Ordre du résultat** — trié, ou dans l'ordre de rencontre ? *Non observé.*
4. **Arrondi et forme des nombres** — troncature ou arrondi, décimales,
   notation. *Non observé.*

Toutes partagent un trait : **le critère de `sous_ensemble_autosuffisant.json`
ne peut rien en dire**. Ce critère demande si l'énoncé cite les identifiants
déclarés par le stub ; il regarde des *noms*, jamais la *forme d'une valeur*,
ni à l'entrée ni à la sortie. C'est le troisième biais nommé en R28i, et c'est
ce fichier-ci qui le mesure au lieu de le supposer.

## La règle qui couvre les quatre familles

- **Tolérant sur la _forme_ de l'entrée** : accepter les formes voisines
  plutôt que rejeter. Un `return error` sur une entrée légitime détruit
  l'exercice entier, même quand la logique est juste — `go/connect`, 8 échecs
  identiques.
- **Strict sur les contraintes que le _type_ implique** : un nombre pair de
  godets, des noms uniques, un alphabet fini de codes. Ces contraintes-là se
  déduisent du domaine même quand l'énoncé se tait — `go/kindergarten-garden`,
  4 échecs.
- **Exact à la sortie** : un seul caractère de séparation suffit à faire
  échouer — `go/beer-song`, 1 caractère sur des milliers. Et le vocabulaire
  compte autant que la ponctuation — `go/kindergarten-garden`, 6 cas.
- **Fidèle au stub** : la suite officielle compile contre lui. Ajouter à côté,
  jamais renommer ni re-typer.

Les deux premières se contredisent en apparence. Elles ne portent pas sur la
même chose : **la forme** de l'entrée se devine mal et doit être acceptée
largement ; **le domaine** de l'entrée se déduit et doit être vérifié.

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

**Restes à traiter — mis à jour le 27/08.** `cpp/parallel-letter-frequency`
était noté « cause non déterminée » : elle est **déterminée**. Le champ existe,
il est dans `turns[].erreurs` et non à la racine du fichier — je le cherchais
au mauvais endroit. L'exercice porte `tours_coupes: 1` à 1 150 s : c'est une
**coupure** de la laisse de silence, pas un verdict du juge. Il part au bras de
rejeu D pur, avec `go/octal` (coupé aussi).

**Trois populations, et elles ne se mélangent pas** — `classer()` de
`preparer_rejeu_reformule.py` les sépare :

| population | ce qui s'est passé | ce que son rejeu mesure |
|---|---|---|
| **jugé** | l'agent a rendu, le juge a dit non | le coût de l'ambiguïté (degré B) |
| **coupé** | la laisse a arrêté l'agent avant qu'il rende | ce que la laisse coûte (D pur) |
| **infra** | la chaîne du juge n'a pas pu construire | un défaut du **banc** (D pur) |

Le cas d'infra observé : `go/palindrome-products`, 27/08. L'agent a réécrit
`go.mod` en `go 1.24` ; le conteneur porte `go1.21.5` et n'a pas de réseau
→ `toolchain not available`, la solution n'a **jamais** été compilée. À noter,
parce que c'est un défaut de banc et pas un accident : `go.mod` n'est pas dans
les éditables, et `restaurer()` ne remet à neuf que les éditables — un fichier
d'échafaudage modifié par l'agent survit donc jusqu'au juge. Non corrigé en
cours de route : changer ça maintenant rendrait les 176 exercices restants
incomparables aux 49 déjà joués.

---

## Cas 4 — `go/pig-latin` : des exceptions énumérées, la règle jamais énoncée

**Relevé** : 27/08/2026, run `pi_D_t1_dflash2`, 60,4 s, tour non coupé.

**Ce que le juge a dit**, mot pour mot :

```
--- FAIL: TestPigLatin/y_is_treated_like_a_consonant_at_the_beginning_of_a_word
    pig_latin_test.go:11: Sentence("yellow") = "yelloway", want "ellowyay"
```

**La preuve que la logique était juste.** L'énoncé donne quatre règles. La
règle 1 (`.docs/instructions.md`, exemples) liste :

```
- "apple"  -> "appleay"   (starts with vowel)
- "xray"   -> "xrayay"    (starts with "xr")
- "yttria" -> "yttriaay"  (starts with "yt")
```

L'agent a codé exactement cela :

```go
if isVowel(word[0]) || strings.HasPrefix(word, "xr") || strings.HasPrefix(word, "yt") {
    return word + "ay"
}
```

Les cas `xray`, `yttria`, `my`, `rhythm`, `quick`, `square` **passent tous**.
Un seul cas tombe : `yellow`.

**La forme de l'écart.** L'énoncé énumère des **exceptions préfixées**
(`xr`, `yt`) sans jamais énoncer la **règle générale dont elles dérogent** :
il ne dit nulle part si un `y` initial est voyelle ou consonne. Le seul mot en
`y-` qu'il montre (`yttria`) est justement celui que l'exception `yt` couvre.
Pour `yellow`, l'énoncé est **muet**, et les deux lectures se défendent :

- `y` voyelle → règle 1 → `yelloway` (ce qu'a fait l'agent) ;
- `y` consonne → règle 2 → `ellowyay` (ce qu'attend la suite).

La suite cachée tranche, et le nom de son cas le dit sans détour :
`y_is_treated_like_a_consonant_at_the_beginning_of_a_word`. **Cette phrase
n'est nulle part dans l'énoncé.**

**La bonne pratique.** Quand un énoncé donne une liste d'exceptions par
préfixe sans donner la classification qui les fonde, la classification est
**muette**, pas absente : elle existe dans la suite. Traiter l'exception
comme une *exception* (donc : le cas général est l'autre branche) est le
pari le plus sûr — `yt` n'aurait pas eu besoin d'être mentionné si `y` était
déjà une voyelle.

**Cinquième famille, et elle manquait au tableau.** Les quatre familles
connues — sortie, entrée, exigence, contrat — ne couvrent pas celle-ci. Elle
s'ajoute :

| famille | ce qui manque à l'énoncé |
|---|---|
| **règle** | l'énoncé énumère des cas particuliers sans donner la règle générale dont ils sont les exceptions |

**Et c'est un raté de la prédiction du 27/08.** `go/pig-latin` n'était signalé
par **aucune** des quatre signatures S1–S4. C'est le premier échec jugé hors
cas fondateurs, et la prédiction ne l'avait pas vu. Le constat se publie tel
quel : **S5 n'est pas ajoutée à la liste figée** — l'ajouter après avoir vu
l'échec qu'elle doit attraper serait de l'ajustement après coup, exactement ce
que le pré-enregistrement sert à empêcher. Elle est candidate pour un
pré-enregistrement suivant, à déposer avant que d'autres langues jouent.

---

## Cas 5 — `go/poker` : deux caractères Unicode voisins, un seul valide

**Relevé** : 27/08/2026, run `pi_D_t1_dflash2`, 280,4 s, tour non coupé.

**Ce que le juge a dit** :

```
--- FAIL: TestBestHandInvalid/♥_is_an_invalid_suit
    poker_test.go:73: BestHand([2♡ 3♡ 4♥ 5♡ 7♡]) expected error, got: [2♡ 3♡ 4♥ 5♡ 7♡]
```

**La preuve que la logique était juste.** Tous les autres cas passent : mains
valides classées, égalités départagées. Le seul cas qui tombe est celui d'une
main que l'agent aurait dû **rejeter**.

**La forme de l'écart, et elle est double.**

1. **Une validation muette de plus.** Le stub déclare
   `func BestHand(hands []string) ([]string, error)`. L'énoncé fait
   **quatre lignes** et n'emploie aucun mot du champ de l'erreur — ni
   « error », ni « invalid », ni « must ». Le contrat d'erreur n'existe que
   dans la signature.
2. **Deux caractères que l'œil ne sépare pas.** `♡` (U+2661, cœur *blanc*) est
   la couleur valide ; `♥` (U+2665, cœur *noir*) doit être rejeté. Dans la
   sortie du juge, `[2♡ 3♡ 4♥ 5♡ 7♡]` — la carte fautive est la troisième, et
   rien ne la distingue à la lecture.

**La bonne pratique.** Quand l'entrée est faite de symboles Unicode, l'ensemble
valide se lit **au point de code**, jamais à l'œil. Et une signature qui rend
une erreur sur un énoncé qui n'en parle pas veut dire qu'un **jeu de valeurs
valides** existe quelque part : le construire en liste blanche explicite, et
rejeter tout ce qui n'y est pas — plutôt que d'accepter ce qui *ressemble* à
du valide.

**Pour la prédiction du 27/08 : c'est une confirmation hors échantillon.**
`go/poker` était signalé **S4**, et il échoue par le mécanisme même de S4 —
stub qui déclare une erreur, énoncé qui n'en dit rien. Premier cas où la
prédiction voit juste sur un exercice qui n'a pas servi à l'écrire. Un cas ne
conclut rien : à 49 verdicts, S4 hors cas fondateurs donne 1/5 contre 1/13,
soit +12,3 points, **p = 0,490**.
