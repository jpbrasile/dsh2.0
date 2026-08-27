# Red team — la mesure du polyglot agentique et ce qu'elle prétend établir

Tu attaques une **revendication chiffrée** et l'appareil qui la produit. Le
dépôt est en lecture ; tu peux lancer des lectures et des comptages, tu ne dois
**modifier aucun fichier suivi** (un fichier suivi modifié est un échec du run,
pas une trouvaille).

**INTERDIT ABSOLU : ne touche pas au GPU.** Un run de mesure est en vol
(`pilote.py`, PID 51944). N'appelle aucun `llama-server`, ne lance aucun
`pilote.py`, ne redémarre rien, ne tue aucun processus. Tout ce qui suit
s'établit par lecture de fichiers et comptage statique.

## La revendication attaquée

> Sur le corpus aider polyglot, un agent local (pi + Qwen3.8-27B Q4_K_M, 4090)
> qui **écrit ses propres tests** et **ne voit jamais la suite officielle**
> réussit **46,3 %** de 82 exercices, contre **15,9 %** pour le même modèle seul
> sous le protocole du board à **information égale** (`pass_rate_1`). Écart
> +30,5 points, 29 gains contre 4 pertes, McNemar exact bilatéral p ≈ 1,1e-5.

## Les pièces

| fichier | ce qu'il porte |
|---|---|
| `scripts/polyglot_dsh/comparer_protocoles.py` | l'instrument d'appariement |
| `scripts/polyglot_dsh/pilote.py` | le harnais : masquage, tours, verdict |
| `scripts/polyglot_dsh/lancer_polyglot_complet.ps1` | les ordres opérateur datés |
| `scripts/polyglot_dsh/etat_run.py` | les populations et l'alerte d'hétérogénéité |
| `scripts/polyglot_dsh/classification_echecs.json` | 38 échecs jugés classés |
| `scripts/polyglot_dsh/PREDICTION_PISTES_RESTANTES.md` | pré-enregistrement P3–P7 déposé aujourd'hui |
| `scripts/polyglot_dsh/AUDIT_PASS_20260827.txt` | 8 PASS suspects |
| `docs/DSH_QWEN_LOCAL_LOGBOOK.md` | repères R28w (erroné, corrigé) puis R28x |
| `~/tools/aider-bench/aider/benchmark/benchmark.py` | le harnais aider de référence |
| `~/tools/aider-bench/aider/tmp.benchmarks/` | les deux runs, `.dsh.results.json` et `.aider.results.json` |

## Ce que je crois avoir établi — attaque chaque ligne

1. **L'essai 1 du board est aveugle** (le modèle a l'énoncé et le stub, pas le
   fichier de test). Fondé sur `benchmark.py:744` et sur le fait que le modèle
   émet `verse`/`verses`/`sing`/`fromPov`/`isSubset`, absents des énoncés.
2. **Le tour 2 de la variante D n'est pas un défaut** : ordre opérateur du 27/08
   inscrit dans le lanceur, c'est la définition de `pass_rate_2`.
3. **Le bras est hétérogène** : 107 exercices à 1 tour, 5 cpp à 2 tours. Isolés.
4. **cpp est exclu** : son stub d'origine est un namespace vide, semé le 27/08
   dans le corpus vierge, alors que le run aider date du 25/08.
5. **`go/ledger` et `java/ledger` sont exclus** : stub vierge = solution
   complète qui passe.
6. **Le masquage des corrigés a bien eu lieu** : `sans_corriges: True` inscrit
   par le pilote sur 106/106 au moment du tour.

## Ce que je te demande, dans cet ordre

**A. Cherche l'erreur qui inverserait la conclusion.** Pas les imprécisions —
ce qui ferait tomber le +30,5 sous zéro, ou le rendrait ininterprétable.
Candidats à creuser, sans t'y limiter : le dénominateur (coupes et infra sont
retirés du dénominateur côté D — le sont-ils côté board ?) ; l'appariement
exercice à exercice ; le fait que l'agent ait un shell et le modèle non ; les
exercices où le stub vierge fait déjà passer les tests, au-delà des deux
`ledger` ; les échecs d'infrastructure comptés d'un seul côté.

**B. Le pré-enregistrement déposé aujourd'hui est-il honnête ?** Une prédiction
qui ne peut pas échouer n'est pas une prédiction. Pour chacune de P3 à P7 : est
elle falsifiable, son seuil est-il choisi avant ou après avoir regardé, et
l'effectif attendu permet-il de la trancher ? Signale toute prédiction dont le
résultat est déjà déterminé par les données existantes.

**C. La classification des 38 échecs.** Un audit a déjà trouvé une entrée fausse
(`java/pov`, classée « chaîne absente de tout le visible » alors que l'append la
publiait). Cherches-en d'autres : prends au moins six entrées, va lire l'énoncé,
le stub, la suite et la solution rendue, et dis lesquelles ne tiennent pas.

**D. Ce que la mesure devrait mesurer et ne mesure pas.** Une phrase par
manque, avec le coût de le combler.

## Forme du rapport

Trouvailles classées par gravité décroissante. Pour chacune :
**gravité** (HIGH = la conclusion publiée est fausse ou ininterprétable) ·
**où** (fichier:ligne) · **le défaut** · **le scénario d'échec concret** ·
**quoi faire à la place** · **comment le tester à peu de frais**.

Une trouvaille sans pièce citée ne vaut rien. Si tu ne peux pas vérifier un
point, écris « non vérifié » — ne le devine pas. Si tu penses que la
revendication tient, dis-le et dis pourquoi ; un red team qui invente un défaut
pour justifier son existence est pire qu'inutile.
