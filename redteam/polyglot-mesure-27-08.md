# Red team -- polyglot-mesure-27-08

| | |
|---|---|
| date | 2026-08-27 18:07 |
| modele red team | `glm-5.3` via `zai` (servi : `glm-5.3`) |
| prompt | `harness/redteam/polyglot-mesure-27-08.md` |
| cwd | `C:\Users\test\Documents\dsh2.0` |
| appels / tokens | 75 appels, 2840884 entree, 122589 sortie, 2285 s |
| dsh | rc de fumee_route = 0 ; VERDICT : OK -- chaque appel servi par glm-5.3 |
| fichiers suivis modifies par le red team | **ECHEC DU RUN** : `?? scripts/polyglot_dsh/juge_java_variable-length-quantity.txt`, `?? scripts/polyglot_dsh/juge_java_wordy.txt`, `?? scripts/polyglot_dsh/juge_javascript_bottle-song.txt`, `?? scripts/polyglot_dsh/juge_javascript_bowling.txt`, `?? scripts/polyglot_dsh/juge_javascript_complex-numbers.txt` |

## Rapport brut du red team (non edite)

Toutes les vérifications sont terminées. Le diff twelve-days confirme (« expected: "…Pear Tree.␊" but was: "…Pear Tree." », 19 285 caractères, 15/15 officiels tombés, 0/7 maison), et `RationalTest` est **la seule suite du run** avec le helper à arguments inversés. J'assemble le rapport final.

---

# Rapport d'audit — claim R28w/R28x (« l'agent local qui écrit ses tests bat le modèle seul, 46,3 % vs 15,9 % »)

## Verdict en une ligne

**Aucune erreur unique n'inverse la conclusion : la direction du gap tient (sous-ensemble propre : 36,1 % vs 11,5 %, p = 1,5 × 10⁻³).** Mais la **prémisse publiée** — « never sees the official suite » — est **factuellement fausse pour 21 des 82 exercices**, et la **magnitude publiée est un artifact de cette fuite**. Par ailleurs, une entrée de classification sur huit auditées contient une inversion matérielle attendu/obtenu.

---

## F1 — Grave : trou de masquage go/java (prémisse violée, magnitude publiée fausse)

- **gravité** : HIGH — la phrase publiée est fausse telle quelle ; la conclusion corrigée survit.
- **où** : `scripts/polyglot_dsh/pilote.py:852-922` (le masquage ne couvre que `files.test` de `.meta/config.json`) ; config des exercices go (où `cases_test.go` n'est pas dans `files.test`) ; claim `docs/DSH_QWEN_LOCAL_LOGBOOK.md:6201-6330`.
- **le défaut** : pendant le tour de l'agent, 21/82 exercices (20 go + java/satellite) gardaient dans l'espace de travail du matériel officiel de test — tables de cas (`cases_test.go`), specs secondaires (`bonus_test.go`, `TreeTest.java`…). L'agent a **cité** `cases_test.go` dans sa file de sortie pour 9 d'entre eux ; go/word-search : *« verified against all 24 cases in the provided cases_test.go »*.
- **scénario concret** : word-search — l'agent lit les 24 cas officiels, s'y auto-vérifie, puis livre. Il a vu la suite ; l'énoncé publié du protocole est faux pour cet exercice.
- **impact chiffré** : 11 des 29 victoires discordantes de D sont dans l'ensemble fuité. Sous-ensemble propre (82−21 = 61) : D = 22/61 = **36,1 %**, board = 7/61 = 11,5 %, b = 18, c = 3, **p = 1,49 × 10⁻³**. Le gap tombe de +30,5 à +24,6 points.
- **quoi faire à la place** : masquer par motif (`*_test.go`, `*Test.java`, `*.spec.js`, `tests/*.rs`) au-delà de `files.test` ; publier la cellule corrigée en errata ; reformuler la prémisse (« l'agent n'est pas *jugé* sur la suite officielle » ≠ « il ne la *voit* jamais »).
- **test pas cher** (déjà exécuté) : `grep -l cases_test` sur les files de sortie du run → 9 hits ; re-McNemar sans les 21 → chiffres ci-dessus.

## F2 — Moyennement grave : audit d'honnêteté de la préinscription `PREDICTION_PISTES_RESTANTES.md` (P3–P7)

- **gravité** : MEDIUM-HIGH — ne touche pas le 82 publié, mais détermine ce que le run en cours pourra « prouver ».
- **où** : `scripts/polyglot_dsh/PREDICTION_PISTES_RESTANTES.md` (lignes 15-20 : divulgation des 2 verdicts js déjà rendus).
- **le défaut, prédiction par prédiction** :
  - **P5 (js < java sur exigence_de_rejet)** : (a) *quasi-pré* — déposée après avoir vu affine-cipher (PASS) et alphametics (FAIL), deux points directement pertinents ; honnêtement divulgué, mais le biais de sélection d'attention reste ; (b) **dénominateur non figé** : la part java de la comparaison est un compte qui croît pendant le run — aucun n_java gelé à la date de dépôt. Le test « strictement inférieur » compare donc un nombre à une moyenne mobile.
  - **P6 (spec_deleguee ≥ moitié des échecs sur 6 exercices nommés)** : conditionnel élastique — la clause « effectif nul → non évaluable » + classification contrôlée par l'analyste + n = 6 rend la prédiction infalsifiable en pratique dans les scénarios défavorables.
  - **P7 (affine-cipher passera)** : échappatoire asymétrique — falsifiée *seulement* si l'échec porte sur le libellé précis ; tout autre motif d'échec = « void ». La prédiction ne peut jamais perdre.
  - **P4** : quasi déterminée par avance par la mesure de corpus (zéro énoncé python muet sur un rejet exigé) — valide comme contrôle d'intégrité, informationnelle quasi nulle.
  - **P3** : propre (falsifiable, seuil 10 % sur python seul, contraste 33,3 %, errata E1 correcte et divulguée).
  - **Bonferroni 5 → 0,01** : décoratif — aucun test statistique n'existe pour P3–P7 (seuils de comptage), le seuil ajusté ne s'applique à rien.
  - **Bonnes pratiques relevées** : divulgation des lignes 15-20, errata E1/E2 datées, ring-fencing de la divergence post-dépôt (E2). C'est au-dessus des usages du domaine.
- **quoi faire** : geler n_java à la date de dépôt et réécrire P5 contre ce gel ; rendre P7 symétrique (échec = falsification, quelle qu'en soit la cause) ; double codage à l'aveugle de la classification avant tout dépouillement.
- **test pas cher** : pour P5, recalculer le taux java sur les seuls échecs datés d'avant le dépôt ; pour la classification, faire coder à l'aveugle 10 entrées par une seconde personne et mesurer l'accord.

## F3 — Moyennement grave : mémorisation des solutions publiques Exercism (confondant symétrique)

- **gravité** : MEDIUM — n'invalide pas la comparaison à information égale, mais rend les **taux absolus** (« passe 46,3 % des exercices ») non interprétables comme du codage à froid.
- **où** : solutions D du run (go/paasio similarité canon 1,000 vs `.meta/example.go` ; go/matrix ; go/dnd-character 0,978) ; contrôle décisif : le **board sans shell** rend dnd-character à 0,958 et le passe.
- **le défaut** : les `.meta` des exercismes publics (solutions canoniques) sont dans le corpus d'entraînement probable du modèle ; les deux bras bénéficient de la même mémoire paramétrique.
- **scénario concret** : un lecteur cite « 46,3 % » comme compétence générale de l'agent ; en réalité une part inconnue mais non nulle est de la restitution de solutions publiques — symétrique entre bras, donc le gap (+24,6 propre) reste une mesure de *traitement* (boucle de tests), pas de *connaissance*.
- **quoi faire** : muter les exercices (renommage des identifiants, changement des tables de cas, énoncés reformulés) et relancer les deux bras ; ou ne publier que la comparaison relative.
- **test pas cher** : la similarité canon est déjà calculée ; étendre le contrôle-board à 10 exercices passés des deux côtés (script statique, ~2 h).

## F4 — Moyennement grave : entrée `rational-numbers` de la classification — inversion matérielle attendu/obtenu

- **gravité** : MEDIUM — erreur factuelle dans l'artifact qui alimente les dépouillements P* ; sans effet numérique sur P3–P7 (entrée java, famille `orientation_de_la_relation`).
- **où** : `scripts/polyglot_dsh/classification_echecs.json` (entrée `java/rational-numbers`) ; cause racine : `RationalTest.java` — `void assertDoublesEqual(double x, double y) { assertThat(x).isEqualTo(y, …) }` appelé `(expected, actual)` : assertj imprime donc **le paramètre attendu** comme « actual ».
- **le défaut** : l'entrée affirme « attendu 9,9887…, l'agent rend 16,0 — la suite calcule r^x, l'agent x^r » et en tire un contre-argument (« le nom du test contredit son propre calcul »). Le XML du juge (`build/test-results/…/TEST-RationalTest.xml`) prouve l'inverse : **la suite attend x^r** (littéraux `16.0` et `1.0/3` dans la source, identiques côté board) et **l'agent a rendu r^x** (9,9887 = (4/3)⁸ ; −0,001953125 = (−1/2)⁹). Le nom du test (`testRaiseARealNumberToAPositiveRationalNumber`), ses littéraux et son assertion concordent tous sur x^r. La classification AMBIGUITE reste défendable — plus nettement même : l'énoncé ET le stub (`double exp(double exponent)`, paramètre nommé `exponent`) orientent vers r^x, la suite assigne x^r à `exp` — mais le texte publié inverse les rôles et son argument central est faux.
- **scénario concret** : un dépouillement futur utilise « le test contredit son nom » comme précédent de suite incohérente → fausse famille de divergences.
- **quoi faire** : corriger l'entrée (sens + argument) ; noter le piège assertj dans le protocole de lecture des XML.
- **test pas cher** : `grep -r "void assert\w*Double" sur les suites du run` → un seul hit (RationalTest), le piège est circonscrit à cette entrée. **Fait.**

### F4bis — Tâche C, solde de l'audit : 7 entrées sur 8 exactes

| Entrée | Vérification |
|---|---|
| java/rest-api | **Exacte au caractère près** : `.docs/instructions.md` ligne 21 `"owed_by": {` ; suite `owedBy`×14 ; agent : 20 usages internes `owedBy`, 1 seule bascule `owed_by` à `RestApi.java:158` ; 9 tests, 8 tombés, `noUsers` passe. |
| java/affine-cipher | Exacte : 16 tests, 2 tombés (les deux `…ThrowsMeaningfulException`), attendu « Error: keyA and alphabet size must be coprime. » absent des .docs, agent jette « a and m must be coprime. », maison 20/20. |
| java/twelve-days | Exacte : 15/15 officiels tombés, 0/7 maison ; énoncé 2 752 car., zéro mention des méthodes/newline/trailing ; couplets maison sans `\n` final ; diff du juge : attendu `…Pear Tree.\n` vs rendu `…Pear Tree.` |
| java/house | Exacte : 13/14 ; l'énoncé **montre** des couplets multi-lignes (bloc ```text), la suite attend une seule ligne (chaînes concaténées espacées) ; l'agent joint par `\n`. |
| javascript/complex-numbers | Exacte : 40 tests, 1 seul tombe (`Conjugate a purely real number`), diff `imag: -0` vs `imag: 0` (toEqual), énoncé ligne « `a - b * i` ». |
| javascript/binary | Exacte : l'agent valide et rend `0` (`binary.js` : `return 0;`), la spec attend `null` ; l'énoncé annonce le rejet (« handle invalid inputs ») sans jamais nommer `null` — distinction `forme_du_rejet` vs `exigence_de_rejet` justifiée. |
| java/all-your-base | Substance exacte (9 échecs tous sur le TEXTE : « Bases must be at least 2. » / « All digits mus… » / « Digits may not… », conversions au vert, énoncé sans aucun vocabulaire d'erreur, agent jette « base must be >= 2 ») ; **imprecision** : « l'énoncé fait 1 362 caractères » → **843** mesurés (run et vierge). |

## F5 — Candidats d'inversion éliminés (le claim tient sur ces axes — et pourquoi)

Inclut la **rétractation de mon propre candidat nº1 bis** :

1. **Asymétrie de juge js/rust — RÉFUTÉ.** Les specs js du run gardent `xtest` sur disque, mais le juge (`COMMANDES_TEST[".js"] = /aider/benchmark/npm-test.sh`, `pilote.py:130`) **exécute les tests skippés** : preuve empirique, le rejugement de bottle-song fait échouer « first two verses », déclaré `xtest` ligne 50 de la spec vierge en place ; cohérent avec le verdict binary=False (son unique test actif passe chez l'agent — c'est le test skippé « invalid inputs are null » qui le fait tomber). Rust : `cargo test -- --include-ignored` (`pilote.py:128`), et le board porte aussi `#[ignore]`×30/30 → symétrique et complet des deux côtés. Python : 0 skips. Go : aucun. Java : `@Disabled` retiré par `poser_tests` (`pilote.py:735-753`), pré-activé côté board. **Les deux bras jugent les mêmes suites complètes.**
2. **Dénominateurs** : les deux bras comptent infra/coupes comme échecs ; les 4 coupes D (crypto-square, octal, connect, tree-building) déflateurs pour D. Arithmétique des 3 cellules publiées (105/84/82) reproduite exactement au cutoff mtime `2026-08-27 17:02:03.766160`.
3. **Stubs livrés bruts** : aucun. **Altération du juge** : aucune (`rejuger.py` reproduit le juge à l'identique, docker exec même conteneur, restore vierge :101-109).
4. **Dérive de corpus** : zéro divergence réelle dans les 82 (seul formatage @Disabled/xtest, égalisé au jugement).
5. **Board aveugle aux tables go** : 0 mention de `cases_test` dans ses historiques de chat. **book-store essai 1** : échec algorithmique authentique (solution exponentielle auto-diagnostiquée par le modèle).
6. **Parité modèle/serveur** : même alias `specdec-q38-dflash2` des deux côtés.

## F6 — Tâche D : ce que la mesure devrait mesurer et ne mesure pas

1. Elle devrait distinguer **échec de compétence et échec d'outillage hôte** (cf. R28k : go/java absents du PATH au début du run) — coût : une colonne `verdict_infra` dans le pilote (1 ligne de code) + relance.
2. Elle devrait pondérer les réussites D par la **qualité des tests maison** (une réussite avec 2 tests faibles vaut une réussite avec 20 tests) — coût : scorer la couverture maison contre la suite officielle en statique (~1 j).
3. Elle devrait rapporter la **part des 6 pistes**, pas go+java seuls : « polyglot » dans le titre généralise une mesure faite sur 2 pistes — coût : finir le run en cours + re-McNemar par piste (déjà en vol).
4. Elle devrait mesurer le **codage à froid**, pas la restitution (F3) — coût : exercices mutés + relance GPU (~2 j de script).
5. Elle devrait permettre l'**audit des échecs sans rejugement** : les queues de 3 000 caractères tronquent l'assertion java (motif d'existence de `rejuger.py`) — coût : journaliser le stdout complet du juge (1 paramètre).
6. Elle devrait exposer la **fuite de masquage comme variable** (propre vs fuité) plutôt que de l'agréger — coût : nul, les chiffres ci-dessus (F1) existent déjà.

---

**Solde** : conclusion publiée — direction robuste, prémisse et magnitude à corriger (F1) ; protocole de juge propre et symétrique (F5.1, y compris rétractation motivée de l'hypothèse xtest) ; classification fiable à 7/8 avec une inversion à corriger (F4) ; préinscription honnête dans sa divulgation mais P5/P6/P7 structurellement faibles (F2).

## Decision humaine

_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_
