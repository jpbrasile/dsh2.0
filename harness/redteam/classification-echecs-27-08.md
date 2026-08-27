# Red team — la classification des échecs, et le soupçon qui pèse dessus

Tu attaques un **jugement**, pas une mesure. Le dépôt est en lecture ; tu peux
lancer des lectures et des comptages, tu ne dois **modifier aucun fichier
suivi** (un fichier suivi modifié est un échec du run, pas une trouvaille).

**INTERDIT ABSOLU : ne touche pas au GPU.** Un run de mesure est en vol
(`pilote.py`, PID 51944). N'appelle aucun `llama-server`, ne lance aucun
`pilote.py`, ne redémarre rien, ne tue aucun processus. Tout ce qui suit
s'établit par lecture de fichiers et comptage statique.

## Le conflit d'intérêts, énoncé d'entrée

C'est **moi** qui ai produit la revendication « +30,5 points en faveur du
protocole agentique ». C'est **moi** qui classe ensuite chaque échec en
`ambiguite` (l'énoncé ne donnait pas l'information) ou `fond` (l'agent a mal
fait). Le premier disculpe le modèle, le second l'accable. Personne d'autre n'a
relu ces 46 jugements.

**Le résultat à ce jour : 35 `ambiguite`, 10 `fond`, 1 `livraison_incomplete`.**
Soit **76 % des échecs imputés à l'énoncé**, pas au modèle.

C'est exactement la forme que prendrait un biais si j'en avais un. Ta mission
est de déterminer si c'en est un.

## Le critère que je prétends appliquer

Gelé, et invoqué dans presque toutes les entrées :

> L'échec est une **ambiguïté** si et seulement si l'élément sur lequel la
> solution diverge est **ABSENT** de tout ce que l'agent peut voir : l'énoncé
> (`TASK.md`), le stub, et les fichiers de l'exercice. S'il est présent quelque
> part dans le visible, c'est du **fond**.

L'agent ne voit **jamais** la suite officielle (variante D).

## Les pièces

| fichier | ce qu'il porte |
|---|---|
| `scripts/polyglot_dsh/classification_echecs.json` | les 46 jugements, avec preuve et motif |
| `scripts/polyglot_dsh/PREDICTION_PISTES_RESTANTES.md` | pré-enregistrement P3–P7 + errata du 27/08 |
| `scripts/polyglot_dsh/rejuger.py` | comment la sortie du juge est obtenue |
| `scripts/polyglot_dsh/juge_*.txt` | les sorties de juge brutes, non éditées |
| `~/tools/aider-bench/aider/tmp.benchmarks/pi_D_t1_dflash2/` | les solutions rendues, les `TASK.md`, les tests maison |
| `~/tools/aider-bench/aider/tmp.benchmarks/polyglot-benchmark/` | le corpus vierge : stubs et suites officielles |

## Ce que tu dois attaquer, dans cet ordre

### 1. Le critère est-il réellement appliqué, ou récité ?

Prends un échantillon des 35 `ambiguite` — **au moins 8, choisis par toi, pas
les plus faciles**. Pour chacune : va lire le `TASK.md` et le stub d'origine
dans le corpus vierge, et cherche toi-même la chaîne, la borne, le séparateur ou
le contrat que je déclare absent.

**Une seule contre-preuve suffit à faire tomber l'entrée** : si l'élément
divergent est visible quelque part et que j'ai écrit « absent », c'est une
erreur de classement, et elle va dans le sens qui m'arrange. Cite le fichier et
la ligne.

Fais le test symétrique sur les 10 `fond` : y en a-t-il un où l'élément est en
réalité **absent** du visible, et que j'aurais durci pour paraître impartial ?

### 2. La frontière `separateur` tient-elle debout ?

`java/house` est classé **ambiguite** parce que « le visible induit en erreur ».
`javascript/beer-song` et `javascript/bottle-song` sont classés **fond** parce
que « le visible dit vrai ». Trois exercices, même famille de symptôme, deux
classes opposées.

Va lire les trois énoncés. Cette distinction est-elle dans les fichiers, ou
est-ce une glose que j'ai construite après avoir vu les verdicts ? Si elle ne
tient pas, dis quelle classe unique s'impose — et note qu'elle déplacerait le
ratio 35/10.

### 3. La règle de la « famille candidate » est-elle une trappe ?

Deux entrées portent `"famille_candidate": true` : `javascript/binary`
(`forme_du_rejet`) et `javascript/complex-numbers` (`zero_negatif_ieee754`).
La règle 4 du pré-enregistrement les fait compter **dans aucune prédiction**.

Question : ces deux-là auraient-elles **falsifié** une prédiction si elles
avaient été comptées dans une famille existante ? En particulier P5
(`exigence_de_rejet` en javascript). Si oui, la règle 4 fonctionne comme un
mécanisme d'évitement, quelle qu'ait été mon intention. Vérifie la date : la
règle 4 est-elle antérieure aux deux entrées, ou postérieure ?

Même question pour `java/variable-length-quantity`, où je déclare trois
mécanismes co-présents et n'en compte qu'un.

### 4. La prédiction nominative existe — et elle ne sépare pas

`scripts/polyglot_dsh/prediction_enonces_ambigus.json` (18 ko, déposé le 27/08
à 13 h 42) nomme **72 exercices** sur les 225, avec quatre signatures S1–S4.
`verifier_prediction.py` la dépouille en mesurant la **séparation** entre
signalés et non signalés, Fisher exact unilatéral, Bonferroni sur 4.

Sortie à 46 échecs jugés, que je te donne pour que tu l'attaques :

| lecture | S2 | S3 |
|---|---|---|
| tout, cas fondateurs compris | +19,9 pt, p×4 = 0,195 | +32,5 pt, p×4 = 0,197 |
| hors 3 cas fondateurs | +17,3 pt, p×4 = 0,338 | +30,4 pt, p×4 = 0,308 |
| hors fondateurs **et** hors échecs de fond | +10,5 pt, p×4 = 0,990 | +26,3 pt, p×4 = 0,621 |

S1 est **négative** (–39,4 pt). S4 est plate (+3,0 pt).

Deux choses à vérifier, et elles comptent plus que le reste :

**(a)** La troisième ligne — la plus fine, celle que ma propre méthode impose —
est la plus **faible**. Retirer les 10 échecs que j'ai classés `fond` fait
tomber S2 de +17,3 à +10,5 pt et son p×4 de 0,338 à 0,990. Or **5 de ces 10
`fond` étaient signalés par S2** (`java/pov`, `java/variable-length-quantity`,
`javascript/alphametics`, `javascript/beer-song`, `javascript/bottle-song`).

Autrement dit : **mes classements en `fond` retirent précisément les cas qui
faisaient paraître la signature prédictive.** Est-ce l'honnêteté du critère
appliqué sans regarder, ou la trace d'un ajustement ? Va lire les 5 entrées et
leurs `TASK.md`. Si l'une d'elles est un `fond` forcé, dis-le.

**(b)** Rien ne survit à Bonferroni, à aucune ligne. Est-ce que je le dis
clairement partout où je parle d'ambiguïté d'énoncé — ou est-ce que je m'appuie
ailleurs sur une séparation que ces chiffres ne soutiennent pas ? Cherche dans
`docs/DSH_QWEN_LOCAL_LOGBOOK.md` et dans les messages de commit.

Note aussi : **24 des 46 échecs n'étaient signalés par aucune signature**, dont
les trois premiers javascript. Le détecteur rate plus de la moitié.

### 5. Le compte lui-même

`etat_run.py` donne les populations. Recompte : le nombre d'entrées de
`classification_echecs.json` correspond-il au nombre d'échecs `juge` du run ?
Y a-t-il des entrées pour des exercices qui ne sont plus en échec, ou des
échecs jugés sans entrée ? Le total 35/10/1 est-il exact ?

### 6. La question de fond

Si 76 % des échecs relèvent vraiment de l'énoncé et non du modèle, alors le
corpus aider polyglot mesure en grande partie la **capacité à deviner des
conventions non publiées** — et le chiffre `pass_rate` de n'importe quel modèle
sur ce corpus, y compris ceux du board, est autant une mesure de devinette que
de compétence. Est-ce que mes propres pièces soutiennent cette conclusion, ou
est-ce que je l'ai surinterprétée ?

## Format de sortie

Pour chaque trouvaille : **HIGH / MEDIUM / LOW**, la pièce (fichier + ligne),
ce qui est faux, et ce qu'il faudrait écrire à la place.

Termine par une ligne unique : **le ratio 35/10 survit-il à ton examen — et si
non, quel ratio les pièces soutiennent-elles ?**

Ne me fais pas de compliments. Une trouvaille non étayée par un fichier et une
ligne ne vaut rien ; dis « je n'ai pas pu vérifier » plutôt que de supposer.
