# Pré-enregistrement — javascript, python, rust

**Déposé le 27/08/2026.** État du run `pi_D_t1_dflash2` à la minute du dépôt,
mesuré et non recopié :

| piste | rendus / corpus |
|---|---|
| cpp | 26 / 26 |
| go | 39 / 39 |
| java | 46 / 47 |
| **javascript** | **2 / 49** |
| **python** | **0 / 34** |
| **rust** | **0 / 30** |

**Réserve honnête, écrite avant tout le reste :** javascript porte déjà deux
verdicts au dépôt (`alphametics` FAIL, et un second). Ce document n'est donc
**pas** un pré-enregistrement pur pour javascript — il l'est pour python et
rust, et il est *quasi*-pré pour javascript (2/49). Toute lecture doit le dire.
Le dépôt tardif est ma faute : l'audit du 27/08 signalait que c'était
périssable, javascript a démarré pendant que je traitais autre chose.

Tout ce qui suit se mesure sur le **corpus vierge** — énoncés et suites
officielles — donc sans aucun verdict. C'est ce qui rend les prédictions
falsifiables plutôt que descriptives.

---

## Les mesures qui fondent les prédictions

Refaites ici, pas reprises d'un rapport. Script :
`scripts/polyglot_dsh/mesurer_pistes_restantes.py`, plus les comptes nominatifs ci-dessous.

### Chaînes d'erreur : publiées ou non ?

En **java**, la famille `libelle_seul` compte 9 des 38 échecs jugés (**23,7 %**),
et pour **0 des 8** cas examinés la chaîne attendue figurait dans quoi que ce
soit de lisible par l'agent. (Le 9ᵉ, `java/pov`, a été **reclassé `fond`** le
27/08 précisément parce que sa chaîne, elle, était publiée.)

En **python**, la convention du corpus est inverse. `instructions.append.md`
publie la chaîne dans un bloc de code, et la suite la compare au caractère près
via `err.exception.args[0]` :

| exercice python | assertions sur la chaîne | chaînes publiées dans l'append |
|---|---|---|
| phone-number | 13 | 9 |
| wordy | 10 | 3 |
| forth | 18 | 1 |
| dot-dsl | 8 | 1 |
| sgf-parsing | 6 | 4 |
| go-counting | 4 | **0** |
| affine-cipher | 2 | 1 |
| hangman | 2 | 1 |
| variable-length-quantity | 2 | 1 |
| bowling | 0 | 1 |
| two-bucket | 0 | 1 |

**8 exercices sur les 9 qui comparent une chaîne publient la leur.** Seul
`go-counting` compare sans publier.

Pièce qui donne son sens à tout ça : l'append de **python/affine-cipher** publie
`raise ValueError("a and m must be coprime.")` — **exactement** la chaîne que
notre agent a produite sur **java**/affine-cipher, où elle est fausse. Sa
mémoire paramétrique servait déjà la bonne réponse, sur la mauvaise piste.

### Exigences de rejet : énoncé muet ou non ?

Une suite « exige un rejet » si elle attend une exception. L'énoncé est « muet »
s'il n'emploie aucun mot du champ (`error`, `invalid`, `must`, `throw`,
`cannot`, `raise`, `fail`, `reject`, `illegal`, `panic`…).

| piste | suites exigeant un rejet | dont énoncé **muet** |
|---|---|---|
| cpp | 26 | 15 |
| go | 14 | 9 |
| java | 23 | 14 |
| javascript | 14 | **6** |
| python | 14 | **0** |
| rust | 2 | **1** |

javascript, les 6 muets nommés d'avance : `forth`, `palindrome-products`,
`phone-number`, `resistor-color-trio`, `simple-linked-list`,
`variable-length-quantity`.

---

## Les prédictions

Chacune est un nombre, avec son seuil de falsification. Aucune n'est réécrite
après coup ; celles qui tombent sont publiées comme tombées.

**P3 — python, famille `libelle_seul`.**
La part des échecs jugés python classés `libelle_seul` sera **≤ 10 %**, contre
23,7 % en java. Motif : la chaîne est publiée dans 8 des 9 exercices concernés.
*Falsifiée si* la part python dépasse 10 %.

**P4 — python, famille `exigence_de_rejet`.**
**Aucun** échec jugé python ne sera classé `exigence_de_rejet` au motif d'un
énoncé muet. Motif : 0 énoncé muet sur 14 suites de rejet.
*Falsifiée si* au moins un l'est.

**P5 — javascript, famille `exigence_de_rejet`.**
La famille apparaîtra en javascript, à un taux **strictement inférieur à java**
(14/23 = 60,9 % des suites de rejet y sont muettes, contre 6/14 = 42,9 % en js).
*Falsifiée si* la part javascript égale ou dépasse celle de java.

**P6 — `specification_deleguee`, exercices nommés d'avance.**
Les énoncés courts (< 700 caractères) portant un lien externe sont, sur les
pistes restantes : `javascript/alphametics`, `javascript/poker`,
`python/paasio`, `python/poker`, `rust/alphametics`, `rust/luhn-from`.
Au moins **la moitié** des échecs jugés parmi ces six relèvera de
`specification_deleguee` ou d'une ambiguïté dont l'information manquante est
derrière le lien.
*Falsifiée si* moins de la moitié.

**P7 — la mémoire paramétrique sert la mauvaise piste.**
`python/affine-cipher` **passera**, alors que `java/affine-cipher` a échoué sur
la chaîne — parce que la chaîne que l'agent produit spontanément est celle du
corpus python.
*Falsifiée si* python/affine-cipher échoue sur le libellé.

---

## Règle de lecture, gelée maintenant

1. **Dépouillement mécanique unique**, en fin de run, depuis
   `classification_echecs.json`. Une seule lecture ; les lectures d'étape
   orientent le travail, jamais les conclusions.
2. **Bonferroni** sur le nombre de prédictions déposées ici — **5** (P3 à P7).
   Un seuil nominal de 0,05 devient 0,01.
3. Une prédiction qui ne peut pas être évaluée (piste non terminée, effectif
   nul) est déclarée **non évaluable**, jamais réinterprétée.
4. Les familles employées sont celles déjà gelées dans
   `classification_echecs.json`. Une famille **nouvelle** rencontrée sur ces
   trois pistes est enregistrée comme *famille candidate* et **ne compte dans
   aucune** des prédictions ci-dessus.
