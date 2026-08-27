# Red team -- la sonde d'adaptateur, et ce qu'elle autorise a dire

Tu attaques une piece que je viens de produire et qui, si elle tient, est
l'argument le plus fort du dossier. C'est exactement pour cela qu'elle doit
etre attaquee en premier.

**Conflit d'interet, declare d'emblee.** L'instrument ci-dessous a ete concu
par moi, applique par moi, sur des cas choisis par moi, et son resultat va
dans mon sens. Je n'ai pas d'audit externe. Tu es cet audit. Ta tache n'est
pas de confirmer.

## Ce que je pretends

Le banc mesure un agent local (variante D : il ecrit ses propres tests, ne voit
jamais la suite officielle) contre le meme modele sous le protocole du board
aider. Ma these est qu'une part importante des echecs de l'agent ne mesure pas
sa competence mais sa capacite a DEVINER des conventions que l'enonce ne
publie pas.

Pour trois exercices javascript, je pretends l'avoir demontre et non plus
argumente. Protocole : sur une COPIE hors du repertoire du run
(`~/tools/aider-bench/aider/tmp.benchmarks/_sonde_adaptateur/`), j'applique UNE
substitution -- uniquement la lecture des parametres d'entree -- et je relance
la suite officielle par le meme juge docker.

| exercice | substitution unique | avant | apres |
|---|---|---|---|
| `killer-sudoku-helper` | `(cage, ...)` lit desormais `{sum, size, exclude}` | 13 echecs / 23 | `PASS ./killer-sudoku-helper.spec.js` |
| `palindrome-products` | `{ min, max }` -> `{ minFactor: min, maxFactor: max }` | 9 echecs | `PASS ./palindrome-products.spec.js` |
| `meetup` | `dayIndex[weekday]` -> `dayIndex[String(weekday).toLowerCase()]` | 95 echecs / 163 | `Tests: 163 passed, 163 total` |

Sorties conservees : `scripts/polyglot_dsh/sonde_adaptateur_*.txt`.

**La conclusion que j'en tire** : dans ces trois cas l'algorithme de l'agent
etait entierement juste, et la totalite de l'echec tenait a un contrat d'entree
que ni `TASK.md` ni le stub ne publient. Pour `meetup`, il s'agit de la seule
CASSE d'une chaine ; le stub vierge est `export const meetup = () => {}`, sans
aucun parametre declare.

## Ce que je te demande d'attaquer, dans cet ordre

**1. La sonde est-elle honnete ?** Verifie sur piece que chaque substitution ne
touche QUE la lecture des parametres. Compare le fichier de `_sonde_adaptateur`
au fichier du run (`pi_D_t1_dflash2`) : `diff`. Si une seule de mes
substitutions touche a la logique -- une comparaison, une borne, un tri --,
la sonde est truquee et il faut le dire ainsi.

**2. La copie est-elle la meme chose que l'original ?** `_sonde_adaptateur` a
ete fabrique par copie. Verifie que le fichier de solution, les tests
officiels et la configuration y sont identiques a ceux du run. Une copie
partielle qui aurait perdu un fichier expliquerait un PASS sans rien prouver.

**3. La conclusion est-elle plus large que la mesure ?** Trois exercices, une
seule piste, choisis parce que je les soupconnais deja. Enonce precisement ce
que ces trois cas autorisent a dire et ce qu'ils n'autorisent pas. En
particulier : la piste javascript est celle ou l'agent PERD contre le board
(-20,0 points sur 15 exercices apparies, voir R28z). Une these qui explique
pourquoi l'agent echoue doit-elle etre construite sur la piste ou il echoue le
plus ? Dis si c'est un biais de selection.

**4. Le critere gele tient-il encore ?** Il exige DEUX conditions pour classer
un echec en `ambiguite` : (1) la logique passe les cas voisins, nommement ;
(2) l'element divergent est absent de TOUT ce que l'agent peut voir. Pour
`meetup`, AUCUN test officiel ne passait avant la sonde -- les 68 reussites
etaient les tests de l'agent lui-meme. J'ai utilise la sonde pour etablir (1).
Est-ce legitime, ou est-ce une extension du critere gele apres coup, du meme
genre que celle que tu m'as reprochee sur `java/poker` ? Tranche.

**5. L'argument a charge sur `meetup`.** L'enonce ecrit bien `Friday` et
`Thursday` avec une majuscule, dans sa prose. J'ai ecrit que la majuscule de
l'anglais courant n'est pas une specification de format. Est-ce une echappatoire
commode ? Un agent competent normalise-t-il la casse d'une chaine non
documentee ? Si oui, `meetup` est du fond et je dois le reclasser.

**6. Cherche les cas ou la sonde AURAIT ECHOUE et que je n'ai pas essayes.**
Il y a d'autres echecs classes `contrat_d_entree_mal_lu` ou voisins dans
`scripts/polyglot_dsh/classification_echecs.json`. Nomme ceux que j'aurais du
sonder et que je n'ai pas sondes. Un instrument applique seulement la ou il
donne le bon resultat n'est pas un instrument.

## La cellule publiable, a re-attaquer aussi

R28z (dans `docs/DSH_QWEN_LOCAL_LOGBOOK.md`) retracte un ecart de +30,5 points
publie le matin et le remplace par **+16,5 points** (n = 79, D 34,2 %, board
17,7 %, McNemar exact p = 0,024), hors confondus documentes (cpp, les deux
`ledger`) et hors les 19 exercices touches par la fuite de masquage F1. Par
piste : go +35,0 (p = 0,016), java +20,5 (p = 0,035), javascript **-20,0**
(p = 0,45).

Le run n'est pas fini (135 exercices juges sur 225 au moment ou j'ecris).
Attaque : ces chiffres survivent-ils a leur propre mode de lecture ? Le choix
des exclusions est-il defendable ou taille-t-il la cellule ? Que devient
l'ecart si l'on ne retranche RIEN ?

## Regles

- **Ne touche pas au GPU** et ne lance aucun processus long. Le run est en vol
  (`pilote.py`, PID 51944) ; le tuer detruirait plusieurs heures de calcul.
- **Ne modifie aucun fichier suivi par git.** Lecture seule.
- Les fichiers `juge_*.txt` et `sonde_adaptateur_*.txt` de
  `scripts/polyglot_dsh/` sont des sorties de juge que je produis en continu :
  s'ils changent pendant ton audit, ce n'est pas toi, et ce n'est pas une
  anomalie.
- Cite tes pieces : chemin et numero de ligne. Une affirmation sans piece est
  a retirer, pas a garder par confort.
- Classe chaque trouvaille HIGH / MEDIUM / LOW.
- Si une de tes trouvailles s'effondre en cours d'audit, dis-le et retire-la :
  la liste des trouvailles retirees fait partie du rapport.
