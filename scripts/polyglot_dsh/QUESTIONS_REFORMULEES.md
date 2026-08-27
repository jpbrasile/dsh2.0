# Questions reformulées

**Fichier généré — ne pas éditer à la main.** Source :
`questions_reformulees.json`, régénérer avec `rendre_questions.py`.

Autorisé le 27/08 : *« tu as le droit d'optimiser les questions à condition de tracer la raison, puis tu rejoues le test case. »* La raison est donc ici, et le résultat de chaque run porte le texte exact qui a été ajouté.

## Les trois degrés

| degré | nom | ce que ça implique |
|---|---|---|
| **A** | désambiguïsation interne | L'énoncé se contredit lui-même ; on ne garde que la forme qui fait foi. **Aucune information n'entre** : tout était déjà écrit dans l'énoncé. Reste comparable à la variante D. |
| **B** | mise en garde générique | On signale qu'une **classe** d'ambiguïté existe, sans dire de quel côté elle tombe. Ne cite aucun exercice, s'applique au corpus entier. C'est une amélioration de **consigne**, pas une réponse. |
| **C** | révélation | On donne la convention attendue. Elle vient de la **suite cachée**. Contamination maximale : ne se compare ni à la variante D ni au banc aider, et ne sert qu'à chiffrer le coût de l'ambiguïté. |

Le pilote n'ajoute **rien** sans `--degres` : la variante D reste le
défaut, et un résultat sans reformulation porte une liste vide.

## Ajouts génériques

Ils ne citent aucun exercice et s'appliqueraient au corpus entier.

### `B1-separateur-terminal` — degré B (mise en garde générique)

- **Issu de** : `go/beer-song`
- **Constat** : classe blancs, l'attendu prolonge l'obtenu de 1 caractere : \n
- **Raison** : L'enonce affiche la chanson RENDUE, ou le dernier couplet n'est visiblement suivi de rien. Un separateur terminal est invisible a l'oeil dans un exemple rendu. Aucune ligne de l'enonce ne porte l'information, dans un sens ni dans l'autre.

> Quand une fonction assemble plusieurs elements en une seule chaine, deux contrats existent et un exemple rendu ne les distingue pas : le separateur peut etre place ENTRE les elements, ou APRES CHACUN, dernier compris. Choisis explicitement, et ecris un test qui verifie ce qui suit le dernier element.

### `B2-tokenisation-entree` — degré B (mise en garde générique)

- **Issu de** : `go/connect`
- **Constat** : 8 cas sur 8 refuses avec le meme message issu de la validation de la solution
- **Raison** : Le harnais officiel normalise l'entree avant de la transmettre (connect_test.go:8-16 retire tous les espaces), et son message d'erreur affiche la donnee D'ORIGINE, espacee. L'enonce montre la meme forme espacee. Rien, ni dans l'enonce ni dans l'indice fourni par l'echec, ne signale la normalisation.

> Ce qu'un enonce MONTRE d'une entree est une representation lisible, pas forcement la forme qui te sera transmise : alignement, espaces et decorations peuvent avoir ete retires. Ecris un lecteur tolerant -- separateurs optionnels, indentation ignoree -- et ne rejette jamais une entree que tu n'as pas su lire.

### `B3-contraintes-du-domaine` — degré B (mise en garde générique)

- **Issu de** : `go/kindergarten-garden`
- **Constat** : 4 cas ou une erreur etait attendue et n'est pas venue
- **Raison** : La suite officielle teste quatre validations -- format invalide, nombre impair de godets, nom en double, code inconnu -- dont l'enonce ne dit pas un mot : les mots « error », « invalid », « duplicate », « odd » n'y figurent pas.

> Un enonce decrit surtout le cas nominal. Les contraintes que le DOMAINE implique -- tailles appariees, identifiants uniques, alphabet fini de codes, bornes -- sont attendues meme quand l'enonce se tait : signale-les par une erreur. Sois tolerant sur la FORME de ce qui est valide, strict sur ce que le TYPE implique.

### `B4-vocabulaire-de-sortie` — degré B (mise en garde générique)

- **Issu de** : `go/kindergarten-garden`
- **Constat** : 7 cas, repartition casse=1 lexique=6
- **Raison** : Le meme enonce donne les quatre plantes sous TROIS formes : prose minuscule pluriel (ligne 6), tableau capitale singulier (lignes 19-22), liste a capitale initiale (ligne 58). L'agent a pris celle du tableau, la suite attend celle de la prose. Rien ne dit laquelle fait foi.

> Quand un enonce donne le meme vocabulaire sous plusieurs formes -- une phrase, un tableau, une liste --, c'est la forme de la PROSE qui fait foi pour les valeurs rendues. Un tableau qui associe un code a un libelle donne le CODE d'entree, pas necessairement le libelle de sortie. Verifie casse et singulier/pluriel.

## Ajouts visant un exercice

Ceux-ci nomment un exercice. Un degré **C** y révèle une convention
que seule la suite cachée porte : à n'employer que pour chiffrer le
coût de l'ambiguïté, jamais dans une colonne comparée au banc.

### `go/kindergarten-garden` — degré A (désambiguïsation interne)

- **Raison** : Desambiguisation INTERNE : la forme correcte est deja dans l'enonce, ligne 6 (« grass, clover, radishes, and violets »). On ne fait que retirer la contradiction que le tableau des lignes 19-22 introduit. Aucune information exterieure n'entre.

> Note : le tableau ci-dessus associe un CODE de diagramme a une plante ; les valeurs rendues emploient les noms tels qu'ils apparaissent dans la phrase d'introduction.

### `go/beer-song` — degré C (révélation)

- **Raison** : REVELATION : le separateur terminal n'existe nulle part dans l'enonce. Ce texte vient de la suite cachee. A n'utiliser que pour chiffrer le cout de l'ambiguite.

> Note : la chanson complete se termine par une ligne vide apres le dernier couplet.

### `go/connect` — degré C (révélation)

- **Raison** : REVELATION : la normalisation de l'entree vient du harnais (connect_test.go:8-16), pas de l'enonce. A n'utiliser que pour chiffrer le cout de l'ambiguite.

> Note : le plateau te sera transmis sans aucun espace ; les espaces des exemples ne servent qu'a la lisibilite.
