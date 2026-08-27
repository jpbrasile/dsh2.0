# RED TEAM — Audit de la sonde d'adaptateur et des claims R28z/R29

Date de l'audit : 27/08/2026, session ~19:20–19:40. Règle de preuve appliquée :
chaque affirmation renvoie à un fichier + ligne (ou clé JSON), ou est retirée.
**Audit mené sur une cible mouvante** : six sondes et une réécriture de
`classification_echecs.json` sont apparues PENDANT l'audit (voir §10). Tous les
horodatages ci-dessous sont des `LastWriteTime` relevés pendant la session.

---

## 0. Verdict global

L'instrument est **honnête dans son mécanisme** (même juge docker, une seule
substitution, témoins négatifs réels) et **dérive dans sa règle écrite sur un
cas sur dix** (rational-numbers touche une formule, interdit par la lettre de
la règle). Sa publication est en retard de six sondes sur dix au moment de
l'audit. Le critère « un instrument qui ne s'applique que là où il réussit »
est **réfuté par les faits** : deux applications échouent à produire un PASS
et l'auteur a sondé ces exercices-là aussi.

---

## 1. Axe 1 — Honnêteté de la substitution (10 sondes au total)

La règle écrite, `docs/DSH_QWEN_LOCAL_LOGBOOK.md` L6569-6571 : « appliquer UNE
substitution, portant uniquement sur la lecture de l'entree ou la convention
en cause, puis relancer la suite officielle par le meme juge docker ». L6573 :
« Ce qui est interdit : toucher une comparaison, une borne, un tri, une
formule. »

| # | Exercice | Substitution (run → sonde) | Nature | Discipline |
|---|----------|---------------------------|--------|------------|
| 1 | js/killer-sudoku-helper | `killer-sudoku-helper.js` L1-3 : `(cage, excluded=[])` → `(entree, excluded=[])` + shim `{sum,size,exclude}` | lecture d'entrée stricte | OK |
| 2 | js/palindrome-products | L14 : `({min,max})` → `({minFactor:min,maxFactor:max})` | lecture d'entrée stricte | OK |
| 3 | js/meetup | L16 : `dayIndex[weekday]` → `dayIndex[String(weekday).toLowerCase()]` | lecture d'entrée stricte | OK |
| 4 | js/grep | `grep.js` L56-58 : position du motif dans `argv` (drapeaux avant motif, cf `grep.spec.js` L116-123) | lecture d'entrée stricte | OK |
| 5 | java/custom-set | `CustomSet.java` : `for (T element : elements) { if (!other.contains(...))` ↔ itération/containment permutés | orientation d'une relation binaire (opérandes d'entrée) | OK (rien de comparaison/borne/tri/formule) |
| 6 | java/rest-api | `RestApi.java` : littéral `"owed_by"` → `"owedBy"` | convention de nommage de clé (sortie) | couvert par « la convention en cause », pas par « lecture de l'entree » |
| 7 | java/variable-length-quantity | `VariableLengthQuantity.java` : `String.format("%02X")`+espaces → `"0x"+Integer.toHexString()` | format de sortie | idem |
| 8 | js/grade-school | L13/L16 : `const result=[]` → `{}` ; `result.push(...)` → `result[grade]=[...]` | structure de sortie (tableau → objet) | idem |
| 9 | java/rational-numbers | `Rational.java` L71 : `return Math.pow(numerator, exponent)/Math.pow(denominator, exponent);` → `return expOf(exponent);` (expOf L74-76 = code mort préexistant) | **remplacement d'une formule** (rôles d'opérandes permutés : this^arg → arg^this) | **VIOLE L6573 par la lettre** |
| 10 | java/forth | témoin négatif : 90 tests/54 échecs → sonde L2033 « 31 failed » ; reste = ordre de pile `[1,2,3,2]` vs `[2,3,2,1]` | — | OK |

**Aucune sonde ne touche une comparaison, une borne ou un tri** — la ligne
rouge explicite du brief tient partout. La ligne « formule » tient partout
sauf rational-numbers.

- **HIGH — rational-numbers** : la substitution remplace le corps de retour
  de `exp` par un appel à une autre formule. Intention défendable (corriger
  l'orientation des opérandes), mais la règle L6573 l'interdit mot pour mot.
  Résultat d'ailleurs non net : juge avant « 78 tests completed, 2 failed » →
  sonde « **3 failed** » — le cas négatif est sauvé, le cas positif échoue
  encore de 2,8e-15 (16.0 attendu vs 15.999999999999998, tolérance 1e-15 :
  ordre d'évaluation en virgule flottante), et 2 MaisonTest cassés.
- **MEDIUM — frontière entrée/sortie non écrite** : sondes 6-8 portent sur la
  sortie (clé JSON, format hex, structure de retour), pas sur « la lecture de
  l'entree ». La clause « ou la convention en cause » (L6569-6570) les couvre,
  mais l'écart entre les deux clauses mérite une phrase de règle, sinon la
  porte est ouverte à la prochaine dérive.

---

## 2. Axe 2 — Fidélité des copies

Comparaison récursive run (`tmp.benchmarks/pi_D_t1_dflash2/...`) vs sonde
(`tmp.benchmarks/_sonde_adaptateur/...`), fichier à fichier :

- **killer : 6 fichiers inertes manquants** dans la copie (`.eslintrc`,
  `.npmrc`, `.docs/instructions.md`, `.meta/*`). LOW — aucun effet sur le
  verdict (suite officielle passée : `sonde_adaptateur_killer-sudoku-helper.txt`
  L5 `PASS ./killer-sudoku-helper.spec.js`), mais la règle « copie hors du
  répertoire du run » (L6568-6569) devrait dire « copie INTÉGRALE, fichiers
  cachés compris ».
- palindrome, meetup, grep, grade-school, rational-numbers : jeux de fichiers
  identiques (avec `.dsh.results.json`).
- java/forth : 46/46 fichiers, zéro écart.
- java/custom-set : 45/45 ; java/rest-api : 54/54 ; java/variable-length-quantity : 45/45.

**Nouveau contrôle apparu pendant l'audit** (positif) : pour les trois sondes
java du 19:29-19:31, un rejugé du run réel a été sauvegardé AVANT
(`reel_java_*.bak`, 19:27-19:28) puis le run réel a été rejugé APRÈS
(`juge_java_*.txt`, 19:32:09) : listes d'échecs **strictement identiques**
(custom-set : 3×CustomSetTest ; rest-api : 8×RestApiTest ; vlq : 26×
VariableLengthQuantityTest). C'est la preuve de non-contamination promise en
L6649-6654, désormais fournie.

---

## 3. Axe 3 — Biais de sélection

- Assumé par l'auteur : L6622-6623 « J'ai sonde la ou j'avais vu la
  signature ». Les trois premières sondes JS sont les trois `contrat_d_entree_mal_lu`.
- Contre-poids réels : (a) java/forth sondé **exprès** comme témoin négatif
  (L6602) et il échoue ; (b) depuis 19:27, les exercices NON suspects sont
  sondés aussi (custom-set, rest-api, vlq — dont deux ne passent pas la
  sonde intégralement). Le biais de départ est réel mais se referme en
  direct pendant l'audit.

---

## 4. Axe 4 — Le critère gelé

- (1) « la logique passe les cas voisins » : désormais **mesurée**, pas
  jugée. La sonde produit des PASS non triviaux et des non-PASS : la règle
  « La sonde ne produit donc pas mecaniquement un PASS. Elle separe. »
  (L6612) est vérifiée sur 10 applications.
- La phrase L6562-6564 (« les seuls tests officiels qui passaient le
  faisaient parce que l'agent rendait une valeur vide ») se réconcilie
  exactement avec le juge killer avant : spec 13 échecs + 4 réussites
  vacues, maison 6/6 — les 4 réussites officielles sont les cas à sortie
  vide.
- (2) « l'élément divergent absent de tout ce que l'agent voit » : reste par
  lecture, la sonde n'y touche pas (correctement reconnu L6637-6638).
- Précédent Java/poker (« Tranche ») : conforme à la doctrine.

---

## 5. Axe 5 — La majuscule meetup

Constat : dans `meetup/TASK.md`, les jours de la semaine n'apparaissent
capitalisés qu'en **prose** ; les seuls tokens format machine sont les 5
valeurs de semaine L34 (backticks, minuscules). Le stub est paramétré
`export const meetup = () => {` (aucun exemple d'appel) ; l'appel réel suit
l'ordre `meetup(2013, 5, 'teenth', 'Monday')` de la spec. La sonde
(minusculation en entrée) passe 163/163.

**Verdict nuancé** : en substance, la casse de l'anglais courant n'est pas
une spécification de format — la normalisation par un agent compétent est
l'hypothèse la plus économique, et la classe `ambiguite` est défendable.
**Mais** la lecture strictement littérale de la condition (2) est affaiblie :
la chaîne `'Monday'` EST visible dans la prose du TASK.md. Ce point doit être
inscrit comme jurisprudence (« un token visible en prose, sans contrat de
format, n'établit pas (2) ») plutôt que laissé implicite.

---

## 6. Axe 6 — Cas non sondés / arithmétique R29

- L6624-6627 : « Sept entrees... restent non sondees, dont java/
  rational-numbers, java/custom-set, java/rest-api, javascript/grep,
  javascript/grade-school ». À l'heure de l'écriture (19:11:47) : 9 exercices
  en famille sondable − 4 déjà sondés = **5**, pas « sept ». La liste cite
  custom-set (hors famille `contrat_*`/`signature_*`) et omet
  variable-length-quantity. Nombre périmé DANS la section « limites honnêtes ».
- **Réfuté par les événements** : à 19:29-19:31, les cinq nommés PLUS
  variable-length-quantity sont sondés. À l'heure où je rends ce rapport :
  **0 cas non sondé** dans la famille. Le critère « un instrument appliqué
  seulement là où il donne le bon résultat n'est pas un instrument » tombe :
  forth (31/90 restants) et vlq (17 échecs restants dont 8 officiels decode)
  prouvent l'inverse.

---

## 7. Tableau de résultats — 10 sondes (officiel avant → après)

| Exercice | Juge avant (officiel) | Sonde (officiel) | Maison après | Verdict sonde |
|----------|----------------------|------------------|--------------|---------------|
| killer-sudoku-helper | 13 échecs/4 passent | PASS (L5) | 6 échecs | sauvetage net |
| palindrome-products | 9 échecs | PASS (L698) | 10 échecs (divulgué L6592-6594) | sauvetage net |
| meetup | échecs | 163/163 | — | sauvetage net |
| grep | 1 échec | PASS (L5) | PASS (L6) | sauvetage net |
| custom-set | 3 échecs CustomSetTest | 0 | 3 échecs MaisonTest | sauvetage net |
| rest-api | 8 échecs RestApiTest | 0 | 11 échecs MaisonTest | sauvetage net |
| grade-school | — | spec 9/10 (L40) | suite ne démarre pas (L6) | partiel |
| rational-numbers | 2 échecs | 1 échec (2,8e-15) | 2 échecs | partiel |
| variable-length-quantity | 26 échecs | 8 échecs (decode) | 9 échecs | partiel (fond confirmé) |
| forth (témoin) | 54 échecs | 31 échecs | — | non-PASS assumé |

Sources : `scripts/polyglot_dsh/sonde_adaptateur_*.txt` et `juge_java_*.txt`,
lignes citées au §1-§2.

---

## 8. Complétude de publication

- Le logbook (dernière écriture **19:11:47**) rend compte de **4 sondes sur
  10**. Sont absents : grep (19:13:04), grade-school (19:13:07),
  rational-numbers (19:22:57), custom-set (19:29:51), rest-api (19:29:59),
  variable-length-quantity (19:31:16).
- **MEDIUM (retard, pas dissimulation)** :
  `classification_echecs.json` réécrit à **19:32:25** intègre déjà les
  résultats nouveaux dans ses champs `preuve` (rest-api : « la suite attend
  la cle JSON owedBy, l'agent emet owed_by » ; vlq : « Trois mecanismes
  co-presents, comptes separement (a) 18 echecs d'encode... » ;
  rational-numbers : les deux exposants attendus/obtenus). La chronologie
  mtime est cohérente et honnête ; c'est le récit qui est en retard sur les
  données, pas l'inverse.

---

## 9. R28z re-attaqué (`comparer_protocoles.py`, capture de la session)

- **Zéro exclusion (aveugles), n=136 : D 50,7 % vs board 18,4 % = +32,4,
  McNemar p≈0** (b=55, c=11). Propre n=117 : +29,1. Publiable n=94 :
  **+14,9, p=0,0243**. Les exclusions ATTÉNUENT le signal, elles ne le
  créent pas. Le headline R28z « +16,5 » devient **+14,9 (n=94)**.
- **cpp** : exclusion justifiée et anti-D-conservative — `allergies.h.stub-origine`
  vide (25/08 13:43) vs `allergies.h` complet semé (27/08 05:21) ; le run
  aider du 25/08 n'a pas pu voir les fichiers du 27/08. La masse retirée
  favorise D (+85,7, n=21).
- **ledger (go+java)** : exclusion justifiée EN EFFET mais **mal libellée**
  dans le script (« portent leur suite dans le fichier de solution »,
  L239-240) : ce qui est dans le fichier de solution du corpus vierge, c'est
  la **solution de référence complète** (`go/ledger/ledger.go` : FormatLedger
  entier, tri, locales nl-NL/en-US ; `java/.../Ledger.java` : format()
  complet avec validation devise/locale). LOW (correction de libellé ;
  l'exclusion reste conservatrice, les deux ledger étant D-gagne).
- **Fuites** : 14/18 go PASS dans l'intersection ; l'entête « 19 go sur 39 »
  compte un go hors intersection (java/satellite à part). Précision à écrire.
- **JS périmé dans le récit** : « javascript −20,0 (n=15) » → mesuré
  **−6,7 (n=30)**. Les D-perd js restants : alphametics, beer-song,
  bottle-song, connect, pig-latin + grep et meetup. **Grep et meetup étant
  sauvés par la sonde, la piste JS devient 9-9.** C'est la correction la
  plus importante à publier.

---

## 10. Rétractations et révisions de mon propre audit

1. Lecture initiale erronée de rational-numbers (fichier sonde pris pour le
   juge, « 3 failed » mal attribué) — corrigée par diff ligne à ligne :
   juge = 2 échecs, sonde = 3.
2. Mon relevé initial disait « 5 non sondées » : périmé à 19:31, tout est
   sondé. Je l'inscris plutôt que de le laisser croire stable.
3. Hypothèse de travail d'entrée (« l'instrument n'a peut-être jamais été
   appliqué là où il échoue ») : **réfutée** par forth et vlq.

## 11. Recommandations (par ordre)

1. Écrire R30 : les 6 sondes manquantes, la table du §7, et la correction
   JS −20,0 → −6,7 (parité 9-9 après sonde).
2. Corriger L6624-6627 (« sept » → situation réelle ; retirer custom-set de
   la liste famille, ajouter variable-length-quantity — ou constater que
   tout est désormais sondé).
3. Amendez la règle de la sonde pour trancher la frontière : « lecture
   d'entrée OU convention en cause » vs « interdit de toucher une formule »
   se contredisent sur rational-numbers. Soit admettre la permutation
   d'opérandes comme substituable, soit retirer rational-numbers du corps
   ambiguite.
4. Règle de copie : « copie INTÉGRALE, fichiers cachés compris » (killer,
   6 fichiers).
5. Jurisprudence meetup (§5) : une phrase dans le critère gelé.
6. `comparer_protocoles.py` L239-240 : reformuler la raison ledger
   (« la solution de référence est semée dans le fichier de solution du
   corpus ») et préciser « 18 go dans l'intersection + 1 hors intersection ».
