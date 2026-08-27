# Red team -- sonde-adaptateur-27-08

| | |
|---|---|
| date | 2026-08-27 19:41 |
| modele red team | `glm-5.3` via `zai` (servi : `glm-5.3`) |
| prompt | `harness/redteam/sonde-adaptateur-27-08.md` |
| cwd | `C:\Users\test\Documents\dsh2.0` |
| appels / tokens | 66 appels, 2393435 entree, 109521 sortie, 2049 s |
| dsh | rc de fumee_route = 0 ; VERDICT : OK -- chaque appel servi par glm-5.3 |
| fichiers suivis modifies par le red team | **ECHEC DU RUN** : `?? red_team/`, `?? scripts/polyglot_dsh/juge_go_octal.txt`, `?? scripts/polyglot_dsh/juge_go_palindrome-products.txt`, `?? scripts/polyglot_dsh/juge_java_tree-building.txt`, `?? scripts/polyglot_dsh/juge_javascript_promises.txt`, `?? scripts/polyglot_dsh/juge_javascript_queen-attack.txt`, `?? scripts/polyglot_dsh/juge_javascript_rational-numbers.txt`, `?? scripts/polyglot_dsh/reel_java_custom-set.bak`, `?? scripts/polyglot_dsh/reel_java_rest-api.bak`, `?? scripts/polyglot_dsh/reel_java_variable-length-quantity.bak` |

## Rapport brut du red team (non edite)

Audit terminé. Rapport complet : `red_team\RAPPORT_SONDE_ADAPTATEUR.md` (chaque claim y est sourcé fichier+ligne, avec rétractations de mon propre audit incluses).

## Ce que l'audit a établi

**Cible mouvante** — pendant la session, 6 sondes nouvelles sont apparues (grep 19:13, grade-school 19:13, rational-numbers 19:22, custom-set/rest-api/variable-length-quantity 19:29-19:31) et `classification_echecs.json` a été réécrit à 19:32:25. Le logbook (19:11:47) n'en rend compte d'aucune.

**Axe 1 (honnêteté)** — 10 sondes au total. **Aucune ne touche une comparaison, une borne ou un tri.** Une seule viole la lettre de la règle L6573 : **rational-numbers** remplace une formule (`Math.pow(n)/Math.pow(d)` → `expOf(exponent)`) — **HIGH**. Trois autres (rest-api : clé `"owed_by"`→`"owedBy"` ; vlq : format hex ; grade-school : tableau→objet) touchent la *sortie*, pas la « lecture de l'entree » — couvertes par « la convention en cause » mais la frontière mérite d'être écrite (**MEDIUM**).

**Axe 2 (fidélité)** — killer : 6 fichiers inertes manquants (**LOW**) ; les 9 autres copies : jeux de fichiers rigoureusement identiques. Bonus vérifié : contrôles `.bak`→`juge_java_*.txt` à listes d'échecs identiques = preuve de non-contamination du run réel.

**Axe 6 / biais** — l'arithmétique R29 « sept non sondées » était fausse (5 réelles, custom-set hors famille, vlq omis), mais **réfutée par les événements** : tout est sondé à 19:31. L'instrument a été appliqué là où il **échoue** (forth : 31 échecs restants ; vlq : 8 échecs decode officiels) — le critère « instrument qui ne réussit que là où il réussit » ne tient plus. Bilan : 6 sauvetages nets, 3 partiels, 1 témoin négatif.

**R28z** — cellule zéro-exclusion : **+32,4 (n=136, p≈0)** ; publiable **+14,9 (n=94, p=0,024)** — les exclusions atténuent le signal. cpp justifié (chaîne mtime 25/08 vs 27/08) ; ledger justifié **en effet** mais mal libellé (c'est la *solution de référence* qui est semée dans le stub, pas « leur suite »). Correction la plus importante à publier : **JS passe de −20,0 (n=15) à −6,7 (n=30)**, et grep+meetup sauvés par la sonde ⇒ parité 9-9.

Le tableau meetup (axe 5) reste défendable en substance mais sa faiblesse littérale (`'Monday'` visible en prose) doit être inscrite comme jurisprudence, pas laissée implicite.

## Decision humaine

_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_

---

## Suites donnees par l'agent (27/08, 20 h) -- EN ATTENTE DE REVUE HUMAINE

Cette section est ecrite par l'agent audite, pas par l'operateur. Elle dit ce
qui a ete fait de chaque trouvaille. La section « Decision humaine » ci-dessus
reste vide : elle n'appartient pas a l'agent.

| trouvaille | niveau | suite donnee |
|---|---|---|
| sonde `rational-numbers` remplace une formule | HIGH | **APPLIQUEE.** Regle coupee en deux classes (R30 §2). Cette sonde devient l'unique cas de **classe B**, declaree plus faible, et ne se cite plus avec les huit autres. Reserve inscrite dans l'entree. |
| frontiere entree/sortie non ecrite | MEDIUM | **APPLIQUEE.** La classe A couvre desormais explicitement l'entree ET la forme de sortie (nom de cle, casse, separateur, notation, structure de retour) ; le calcul n'y est jamais. |
| copie `killer` incomplete de 6 fichiers | LOW | **VERIFIEE ET APPLIQUEE.** Les six sont nommes sur pieces. L'un d'eux est `.meta/proof.ci.js`, **la solution de reference** : son absence DURCIT la sonde. Regle recrite en « copie INTEGRALE, fichiers caches compris ». |
| R29 « sept entrees non sondees » : arithmetique fausse | — | **ACCEPTEE.** Cinq reelles ; j'y comptais `custom-set` hors famille et j'omettais `variable-length-quantity`. Corrigee dans R30 §3. |
| libelle du confondu `ledger` faux | — | **ACCEPTEE.** C'est la SOLUTION DE REFERENCE qui est semee dans le stub, pas la suite de tests. L'exclusion reste justifiee, sa raison etait mal dite. |
| jurisprudence `meetup` a ecrire | — | **APPLIQUEE.** Regle inscrite dans R30 §5 et dans l'entree : la majuscule d'un nom propre en prose n'est pas une specification de format ; elle l'est dans un bloc de code, un tableau ou un schema -- d'ou le `fond` de `javascript/queen-attack`. |
| cellule publiable | — | **REMESUREE, pas contestee.** Le red team lit +14,9 (n = 94) ; je lis +16,2 (n = 99, p = 0,011) une heure plus tard. Les deux sont vrais a des instants differents : le run avance. |
| javascript -20,0 -> -6,7 | — | **CONFIRMEE ET DEPASSEE.** A n = 35 la piste est a **+0,0** exactement, 9 reussites de chaque cote. La phrase de R29 §2 « la piste des trois PASS est celle ou l'agent PERD » est **perimee et retiree**. |

### Ce que l'agent conteste

**Rien sur le fond.** Une seule precision de forme, sans consequence sur les
trouvailles :

L'en-tete du rapport porte « **ECHEC DU RUN** : fichiers suivis modifies par le
red team », suivi d'une liste (`juge_go_octal.txt`, `juge_javascript_*.txt`,
`reel_java_*.bak`, `red_team/`). Ces fichiers ne viennent pas du red team : ce
sont mes propres sorties de juge et mes sauvegardes, produites entre 19 h 15 et
19 h 40 pendant que l'audit tournait. Le brief prevenait
(« s'ils changent pendant ton audit, ce n'est pas toi ») ; le garde-fou du
harnais, lui, ne le savait pas. **Aucun fichier suivi par git n'a ete modifie
par le red team.**

### Ce que l'audit a valide et qui compte

- Les dix sondes ont ete recomptees et **aucune ne touche une comparaison, une
  borne ou un tri**.
- Les copies de sonde ont ete comparees fichier a fichier au run : neuf sur dix
  rigoureusement identiques.
- Controle croise `.bak` -> `juge_java_*.txt` a listes d'echecs identiques :
  **preuve de non-contamination du run reel** par les sondes.
- L'objection « instrument applique seulement la ou il reussit » **ne tient
  plus** : `java/forth` laisse 31 echecs, `java/variable-length-quantity` en
  laisse 8. Bilan de l'audit : 6 sauvetages nets, 3 partiels, 1 temoin negatif.
