# Red team -- les 75 PASS sont-ils reels ?

Tout ce qui a ete audite jusqu'ici porte sur les ECHECS : leur classement
(audit du 27/08 matin), puis l'instrument qui les sonde (audit du 27/08 soir).

**Personne n'a encore regarde les reussites.** C'est la surface la plus
dangereuse du dossier, parce qu'un faux PASS gonfle directement le chiffre
publie, et qu'aucun de mes garde-fous ne le verrait.

Ta tache : essayer de casser les PASS. Pas de les confirmer.

## Le chiffre attaque

Mesure du 27/08, 20 h, `comparer_protocoles.py pi_D_t1_dflash2
2026-08-25-11-54-27--dsh-q8q4-160k-dflash2`, 147 exercices juges sur 225 :

| cellule | n | D | board | ecart | p |
|---|---|---|---|---|---|
| zero exclusion | 141 | 50,4 % | 17,7 % | +32,6 | ~0 |
| **publiable** | **99** | **34,3 %** | **18,2 %** | **+16,2** | **0,011** |

Par piste, cellule publiable : go +35,0 (n=20), java +20,5 (n=44),
javascript +0,0 (n=35).

Le protocole est la **variante D** : l'agent ecrit ses propres tests et ne voit
jamais la suite officielle. Le juge est le meme conteneur docker des deux
cotes. La verite d'un exercice est `.dsh.results.json` cote D,
`.aider.results.json` cote board.

## Ce que je te demande d'attaquer, dans cet ordre

**1. Un PASS peut-il etre faux ?** Prends le chemin du verdict :
`scripts/polyglot_dsh/pilote.py` ecrit `.dsh.results.json`. Lis comment
`tests_outcomes` est calcule. Un exercice peut-il etre marque PASS si :
- la suite officielle n'a pas tourne du tout (build vide, aucun test collecte) ?
- l'agent a supprime, vide ou reecrit le fichier de test officiel avant le juge ?
- le juge a restaure une suite differente de celle du corpus vierge ?
- zero test a ete execute mais le processus est sorti avec le code 0 ?
Cherche la reponse dans le code, pas dans mes affirmations. Si l'un de ces
chemins existe, **nomme les exercices concernes**, pas seulement le risque.

**2. Les 8 PASS que je declare suspects et que je n'ai jamais verifies.**
Le carnet (`docs/DSH_QWEN_LOCAL_LOGBOOK.md`) porte depuis plusieurs jours la
mention de 8 PASS a rejouer a la main avant publication (7 cpp, 1 go). Ils ne
l'ont jamais ete. Retrouve-les, dis ce qui les rend suspects, et dis si les
laisser dans la cellule est defendable. **cpp est deja exclu de la cellule
publiable** ; verifie si le go, lui, y est encore.

**3. cpp a 100 %.** Sur l'appariement, cpp fait **21/21 contre 3/21** pour le
board. Un taux de 100 % sur 21 exercices n'est pas un resultat, c'est un
symptome. cpp est exclu de la cellule publiable comme confondu documente
(des stubs ont ete semes le 27/08 alors que le run aider date du 25/08).
Attaque ce diagnostic : est-ce vraiment la cause, ou y en a-t-il une autre
(chaine de compilation, juge cpp permissif, tests non collectes) ? **Un juge
cpp qui ne collecte rien et sort 0 produirait exactement ce tableau.** Verifie.

**4. La fuite de masquage F1 a-t-elle fabrique des PASS ?** 19 exercices de
l'intersection avaient un fichier de test officiel visible pendant le tour de
l'agent (go range `cases_test.go` sous `files.editor`). Parmi eux **14 sont
PASS pour D** et 4 pour le board. Ces 14 sont retires de la cellule publiable.
Verifie que le retrait est complet et qu'il n'existe pas d'autres exercices,
sur d'autres pistes, ou un fichier de test est reste visible. `pilote.py` a
ete corrige le 27/08 (`tests_hors_config`) mais **la correction n'a pas
sauve le run en vol** : le processus avait deja importe le module.

**5. Le board est-il traite equitablement ?** Le board tourne a
`pass_rate_1` dans l'appariement, sans sortie d'erreur. Verifie que je ne lui
inflige pas une condition que je m'epargne : meme corpus, meme juge, meme
conteneur, memes exercices. Regarde en particulier
`2026-08-25-11-54-27--dsh-q8q4-160k-dflash2` : combien de ses echecs sont des
coupes, des pannes d'infra ou des exercices ou il n'a rien rendu ? **Si le
board a des coupes que je compte en echec alors que je retire les miennes,
la comparaison est truquee et il faut le dire ainsi.** C'est le point le plus
important de cet audit.

**6. Les exclusions taillent-elles la cellule ?** La cellule publiable retire
cpp, les deux `ledger`, et les 19 de la fuite. On passe de n=141 a n=99 et de
+32,6 a +16,2. Chaque exclusion est-elle defendable **prise seule**, et le
resultat serait-il different si on retirait ces memes exercices AU BOARD
plutot qu'aux deux ? Donne le chiffre sous les variantes d'exclusion que tu
juges honnetes, y compris celles qui me sont defavorables.

## Regles

- **Ne touche pas au GPU** et ne lance aucun processus long. Le run est en vol ;
  le tuer detruirait plusieurs heures de calcul.
- **Ne modifie aucun fichier suivi par git.** Lecture seule. Tu peux lancer le
  juge docker en lecture (`rejuger.py`), il est sur CPU.
- Les fichiers `juge_*.txt`, `sonde_adaptateur_*.txt` et `*.bak` de
  `scripts/polyglot_dsh/` sont des sorties que je produis en continu : s'ils
  changent pendant ton audit, ce n'est pas toi, et ce n'est pas une anomalie.
  Il en va de meme du contenu de `tmp.benchmarks/pi_D_t1_dflash2` : le run
  ecrit dedans pendant que tu lis.
- Cite tes pieces : chemin et numero de ligne. Une affirmation sans piece est a
  retirer, pas a garder par confort.
- Classe chaque trouvaille HIGH / MEDIUM / LOW.
- Si une de tes trouvailles s'effondre en cours d'audit, dis-le et retire-la :
  la liste des trouvailles retirees fait partie du rapport.
- **Un audit qui ne trouve rien sur les PASS est un audit qui n'a pas cherche.**
  Si tu conclus que tout va bien, dis explicitement ce que tu as essaye de
  casser et pourquoi ca a tenu.
