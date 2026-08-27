# Seconde pré-enregistrement — le **libellé** d'un message d'erreur

**Déposé le 27/08/2026**, run `pi_D_t1_dflash2`, alors que **java en est à
2 exercices sur 47** et que javascript, python et rust n'ont pas commencé.
Les 45 exercices java restants et les 113 des trois autres pistes n'ont pas
été joués : c'est sur eux que cette prédiction se teste.

## Ce qui l'a provoquée

Les **deux** premiers échecs java sont tombés **exclusivement** sur le texte
d'un message d'exception. Jamais sur la logique.

| exercice | attendu | obtenu |
|---|---|---|
| `java/affine-cipher` | `Error: keyA and alphabet size must be coprime.` | `a and m must be coprime.` |
| `java/all-your-base` | `Bases must be at least 2.` | `base must be >= 2` |

Dans les deux cas l'agent lève **la bonne exception, au bon moment**, avec un
message correct. Pour `affine-cipher`, il le rédige même avec le vocabulaire
de l'énoncé (`a`, `m` — lignes 26-27), qui est le choix le plus fidèle
possible. Le libellé attendu n'est écrit **nulle part** que l'agent puisse
lire : vérifié par recherche de la chaîne exacte dans `.docs/`.

## Pourquoi il n'y a **pas** de détecteur par exercice

J'en ai écrit un, il échouait son propre contrôle, et je ne le dépose pas.
La raison est instructive, et elle vaut mieux que le détecteur :

- **`java/affine-cipher`** — l'énoncé dit ligne 27 *« your program should
  indicate that this is an error »*. Le signal « une erreur est attendue » est
  donc là. Mais rien ne distingue « une erreur » de « une erreur dont le texte
  sera comparé au caractère près ».
- **`java/all-your-base`** — l'énoncé fait 1 362 caractères et ne contient
  **aucun** mot du champ de l'erreur. Le stub ne porte que le remplisseur
  `UnsupportedOperationException`, identique dans 46 stubs java sur 47. **Rien,
  ni dans l'énoncé ni dans le stub, n'annonce l'exception.**

En java, un détecteur *a priori* de cette famille serait donc soit aveugle
(cas 2), soit équivalent à « tous les exercices java » — ce qui n'est pas une
prédiction mais une tautologie. C'est exactement la limite déjà constatée quand
S4 a été restreinte : le gabarit du track masque le signal.

## La prédiction, sous une forme falsifiable

Pas une liste d'exercices : un **taux**, sur la piste java.

> **P1.** Parmi les échecs **jugés** de la piste java de ce run (hors coupures,
> hors pannes d'infra, hors les 2 exercices ci-dessus qui l'ont inspirée),
> **au moins la moitié** auront pour **seule** divergence le **texte** d'un
> message d'erreur — la logique passant par ailleurs.

> **P2.** Cette famille sera **nettement plus fréquente en java** que dans les
> pistes go, python et rust réunies, en part des échecs jugés de chaque piste.

## Comment elles se dépouillent

Chaque échec jugé entre dans `classification_echecs.json` avec un champ
`divergence` valant `libelle_seul` quand — et seulement quand — la sortie du
juge ne montre **que** des assertions sur un texte de message, tous les autres
cas de l'exercice passant. Le comptage est alors mécanique.

**Règle d'arrêt, la même que pour la première prédiction** : le dépouillement
fait foi une seule fois, sur le run terminé. Les lectures intermédiaires
pilotent le travail, jamais la conclusion.

## Ce que ça ne dit pas

Rien ici n'accuse le corpus. Comparer un message d'exception est une pratique
de test légitime. Ce que la prédiction mesure, c'est le **coût, pour un agent
sans information complémentaire**, d'une exigence qui n'est écrite nulle part
dans ce qu'il reçoit — et si ce coût est concentré sur une piste.
