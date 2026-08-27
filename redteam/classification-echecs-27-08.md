# Red team -- classification-echecs-27-08

| | |
|---|---|
| date | 2026-08-27 18:48 |
| modele red team | `glm-5.3` via `zai` (servi : `glm-5.3`) |
| prompt | `harness/redteam/classification-echecs-27-08.md` |
| cwd | `C:\Users\test\Documents\dsh2.0` |
| appels / tokens | 98 appels, 2752866 entree, 129843 sortie, 1606 s |
| dsh | rc de fumee_route = 0 ; VERDICT : OK -- chaque appel servi par glm-5.3 |
| fichiers suivis modifies par le red team | **ECHEC DU RUN** : ` M scripts/polyglot_dsh/juge_java_rational-numbers.txt`, `?? scripts/polyglot_dsh/juge_javascript_alphametics.txt`, `?? scripts/polyglot_dsh/juge_javascript_beer-song.txt`, `?? scripts/polyglot_dsh/juge_javascript_binary.txt`, `?? scripts/polyglot_dsh/juge_javascript_connect.txt`, `?? scripts/polyglot_dsh/juge_javascript_forth.txt`, `?? scripts/polyglot_dsh/juge_javascript_go-counting.txt`, `?? scripts/polyglot_dsh/juge_javascript_grade-school.txt`, `?? scripts/polyglot_dsh/juge_javascript_grep.txt`, `?? scripts/polyglot_dsh/juge_javascript_house.txt`, `?? scripts/polyglot_dsh/juge_javascript_killer-sudoku-helper.txt`, `?? scripts/polyglot_dsh/juge_javascript_meetup.txt`, `?? scripts/polyglot_dsh/juge_javascript_palindrome-products.txt` |

## Rapport brut du red team (non edite)

The kindergarten-garden citation is **exact** against the run's TASK.md (80 lines, table at l.19-22 precisely) — my earlier "wrong line numbers" suspicion was checked against the wrong artifact (the virgin corpus file). That finding dies. All evidence is in; the audit is closed. Here is the verdict.

---

# Verdict — audit de la classification des échecs (commission `harness\redteam\classification-echecs-27-08.md`)

**Méthode.** Critère gelé appliqué à la lettre sur 19 entrées vérifiées sur pièces (TASK.md du run, stubs, corpus vierge, suites officielles relues), test de symétrie sur les `fond`, chronologie par git (e9c4515 → 32dd381), recomptage statique en lecture seule des `.dsh.results.json`. GPU jamais touché ; aucun fichier modifié.

## Trouvailles

**1. HIGH — `go/pig-latin` : le classement `ambiguite` est indéfendable, l'élément divergent était VISIBLE.**
`scripts\polyglot_dsh\classification_echecs.json` L244-247 (preuve L246 : « L'énoncé ne dit nulle part si un « y » initial est voyelle ou consonne »). Contre-pièces : (a) `polyglot-benchmark\go\exercises\practice\pig-latin\cases_test.go` L104-106 — `yellow → "ellowyay"`, publié noir sur blanc dans l'arbre de travail pendant le tour (fuite F1 : `cases_test.go` sous clé `editor`, jamais masqué) ; (b) `.docs\instructions.md` l.7-8 — voyelles « a, e, i, o, u », consonnes = « the other 21 letters » : 26−5=21, le y y est par soustraction. La phrase citée est fausse sur les deux chefs. À écrire : `fond`, divergence « convention du y initial tranchée par cases_test.go:104-106 (visible, F1) et dérivable de l'instruction (21 lettres) ». Aggravant : la fuite était établie depuis 18h21 (R28z, 42474af) et l'errata de classification 32dd381 (18h40) a corrigé rational-numbers sans réexaminer aucune entrée intersectée.

**2. MEDIUM — `java/poker` : le `fond` ne découle pas du critère gelé, mais d'une extension non gelée.**
L52-59 ; preuve L57 : « trou dans une specification publique, identique dans tous les casinos du monde ». L'échelle des mains est absente du visible (énoncé de 194 caractères, aucune hiérarchie) ; la LETTRE dit donc `ambiguite`. Le classement repose sur « universellement connu », critère jamais gelé. L'auteur l'a lui-même signalé (auto-flag `attention_ce_classement_arrange_la_prediction` + test de sévérité). À écrire : soit `ambiguite` sous la lettre, soit geler explicitement l'extension « universellement connu » — mais alors pig-latin, où le visible tranche, n'en bénéficie pas.

**3. MEDIUM — Le « 35/10/1 = 76 % » est un portrait mi-run à dénominateur mouvant.**
Recomptage statique au moment de l'audit : 131 jugés, 60 échecs (java 31, go 13, js 15, cpp 1) contre 46 classés — 14 non classés, concentrés en javascript, piste où la direction s'inverse (R28z). À HEAD (32dd381, 18h40), le fichier est déjà à 52 entrées : 41/10/1, dont +6 javascript toutes `ambiguite` que je n'ai pas pu vérifier à l'exception de `js/house` (conforme : TASK.md muet sur la forme du retour, grep de l'entrée L393). Le run vole encore (PID 51944). Toute citation du « 76 % » doit dater son instant et son dénominateur.

**4. MEDIUM — La fuite F1 est absente de toutes les entrées, et une preuve est factuellement fausse.**
Grep `cases_test|fuite|masquage` sur le fichier : 0 occurrence, à HEAD comme au dépôt. Chronologie compatible avec l'ignorance (entrées écrites 16h21-17h51, fuite trouvée 18h07-18h21), mais aucun errata post-R28z sur les entrées intersectées. Cas net : `go/robot-simulator` L260, « Rien n'etait cache » — FAUX, les suites step2/step3 étaient visibles (R28z L6461-6463). Le CLASSEMENT (`fond`, échec de build sur stub intact) tient — la fuite n'y change rien, l'échec n'étant pas une divergence de test — mais la phrase doit être réécrite. En revanche j'ai vérifié que les `ambiguite` sensibles survivent : `go/connect` (le strip des espaces vit dans connect_test.go masqué) et `go/poker` (cases_test.go n'a aucun champ erreur, 165 lignes lues).

**5. LOW — `robot-simulator` (`fond`) vs `sgf-parsing` (`livraison_incomplete`) : incohérence taxonomique.**
Même profil (build cassé sur stub intact, jamais testé), deux classes. Aligner robot-simulator en `livraison` monterait la part ambiguite à 36/46 — direction contraire à l'intérêt du narratif, ce qui est le signe d'une erreur, pas d'un arrangement.

**6. LOW — `all-your-base` : « 1362 caracteres » pour 843 réels.** Constat F4bis de l'audit mesure (`redteam\polyglot-mesure-27-08.md`) ; je n'ai pas pu vérifier moi-même, je l'attribue.

**7. LOW — P5 ne survit que par la règle 4.** Sans elle (nouvelles familles = `famille_candidate`, comptées dans aucune colonne), P5 serait falsifiée (1/6 contre seuil 2/29). La règle est pré-enregistrée au premier commit (e9c4515, 17h26) — pas post-hoc — mais son effet protecteur doit accompagner toute citation de P5.

## Trouvailles retirées en cours d'audit (les miennes)

- **`rational-numbers`, inversion F4** : corrigée À HEAD par l'auteur (errata_27_08, L136-137, commit 32dd381 18h40) avec cause racine (helper AssertJ aux arguments inversés) et contre-examen daté. Le classement discutable mais divulgué : l'entrée cite elle-même les DEUX formules textuellement présentes (TASK.md L25 et L27) ; l'ambiguïté réelle est le mapping stub→opération, granularité sur laquelle la lettre est muette.
- **`kindergarten-garden`, références de lignes** : les citations « prose ligne 6, tableau lignes 19-22 » sont EXACTES contre le TASK.md du run (80 lignes, vérifié à l'instant) ; je m'étais trompé de pièce (fichier vierge). Retiré.
- **`js/beer-song` / `js/bottle-song`** : la frontière du séparateur tient dans les fichiers, pas dans une glose — specs lues : séparateur `''` ENTRE les couplets uniquement, aucun en fin, et l'exigence visible (ligne vide inter-couplets) est vraie dans TASK.md → `fond` fondés ; symétriquement `java/house` et `js/house` : la forme exigée (une ligne / un tableau) est absente du visible → `ambiguite` fondés. `twelve-days` : `"\n"` terminal par vers, invisible en markdown → fondé.

## Le soupçon de biais systématique, pesé sur pièces

Une seule erreur dans le sens du narratif (pig-latin), une seule dans l'autre sens (poker) — signature d'erreur, pas de biais. Toutes les corrections découvertes ont été absorbées CONTRE l'intérêt du récit : pov retrogradé ambiguite→fond AVANT le dépôt de la commission (L108) ; 13 étiquettes `compilation` fausses corrigées d'office (28923cf) ; F4 auto-erraté le soir même ; +30,5 rétracté le jour même (« fausse sur sa premisse et fausse sur sa magnitude », R28z 18h21, avec cellules corrigées dont B = +16,5, p = 0,024, et l'aveu qu'aucun Bonferroni ne le laisserait vivant). Les 9 exercices citant les fichiers fuités passent tous — l'auteur ne l'a pas caché.

**Point 6 (« le corpus mesure la devinette »)** : soutenu, mais seulement scoped — ~35 échecs classés sur 46 portent sur un élément absent du visible, et le mécanisme est démontré sur pièces (`wordy` L315 : l'agent comble avec les mots de l'énoncé lui-même). La généralisation au corpus ou au pass_rate n'est pas établie : run inachevé, réussites confondues avec la mémorisation (F3), fuite F1 côté go, direction inversée en js.

---

**Ligne finale :** sous la lettre gelée, 35/10/1 SURVIT en agrégat — `go/pig-latin` doit passer `fond` (élément visible : cases_test.go:104-106 + « 21 lettres ») et `java/poker` doit passer `ambiguite` (extension « universellement connu » non gelée), les deux erreurs s'annulant ; si l'on accorde cette extension, le ratio soutenable est 34/11/1 (73,9 %) — et dans les deux lectures, aucune preuve de biais directionnel systématique : une erreur de chaque sens, toutes les corrections absorbées contre le narratif, et le +30,5 déjà rétracté par l'auteur le jour même.

## Decision humaine

_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_
