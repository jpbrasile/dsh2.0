> **Transmission (2026-08-23, session `agentic-flow-fresh-07` → dsh2.0).** À lire avant toute
> campagne ; P1 et P2 sont à faire d'abord.
>
> État des points du §4 au commit `15fed4d` de ce dépôt (mesuré, pas déclaré — chaque réparation
> a son bras known-BAD sous `scripts/bench_julia_effort/fixtures/`) :
> 4.1 **fait** (`horloge_bad_boucle`) · 4.2 **fait** (enregistrement de secours affiché `-`, exclu
> des moyennes) · 4.3 **fait** (`_sans_chemins`) · 4.4 **fait** (juge = max(600, tour) sauf `BENCH_JUGE_TIMEOUT` explicite, alors signalé) · 4.5 **ouvert** ·
> 4.6 **ouvert** (la table « bras web » lit encore `bras_web` ; `--comparer` lit `bras`) ·
> 4.7 **ouvert** · 4.8 échéance : **fait** (lit `timeout_tour × tours_max` de l'enregistrement),
> le reste **ouvert** · §2.2 débit depuis `usage` : **fait** (colonne `~`, t31e = ~30,6 t/s, le
> chiffre ci-dessous) · en plus : bras + slot dans la clé d'attribution (`bras_melanges_bad`),
> `analyse.py _par/<etiq>` assemble les fils des ouvriers.
> Le corps ci-dessous est le document du pair, inchangé.

# Passer de Claude Code à dsh + LLM locaux ou gratuits

État des lieux au 23/08 et to-do, pour transmission à la session **dsh2.0**.
Tous les chiffres ci-dessous sont mesurés et reproductibles ; les rares qui ne
le sont pas sont marqués *non vérifié*.

---

## 0. Le fait le plus important

**La question de la migration n'a jamais été mesurée.**

Le banc compare des dorsales de dsh **entre elles** (locale, gratuite, avec ou
sans recherche web). Il n'a **jamais** comparé dsh à Claude Code sur les mêmes
tâches. La seule ligne du dépôt qui réclame cette comparaison —
`docs/SPECDEC_4090_BENCH.md`, « Coding-agent A/B (OpenCode vs DSH) » — est
encore marquée **NOT-RUN**, et son harnais `scripts/run_harness_ab.ps1` est
déclaré prêt depuis le 20/08.

Tout le reste est de l'instrumentation autour d'une question encore non posée.

**Second fait, découvert le 23/08 :** l'instrument d'analyse principal
(`analyse.py`, table par run) **n'a jamais tourné sur une vraie campagne en
mode boucle**. Il plante, et quand on contourne le plantage, deux de ses gardes
affichent « vert » parce qu'ils mesurent le vide. Détail en §4.

---

## 1. Ce qui marche

### Le harnais dsh
- `bench.py --selftest` : **CALIBRÉ**. 10/10 known-GOOD, 10/10 known-BAD,
  palier dur 6/6 + 6/6. Chaque mauvaise solution est attrapée par **son**
  défaut nommé, pas par un total.
- `fixture_injection.py` : **51 assertions**, avec bras known-BAD réels.
- Mode BOUCLE (2 tours, l'erreur du juge réinjectée) : **6/6 contre 5/6** en
  un-coup. Le second tour est un levier réel.
- Recherche web réelle et fonctionnelle (étages du dépôt : Z.AI puis
  OpenRouter). Vraies pages, vrais liens. Latence **27 à 107 s par requête**.

### La dorsale LOCALE
- llama-server sur 8005, sert exactement **un** modèle : `specdec-q38-mtp`.
- Débit décode médian **≈ 90 t/s**.
- **Aucun quota, aucune coupure fournisseur.** Seule dorsale dont le débit soit
  mesurable (voir 2.2).
- Score connu : **11/18** sur t21–t26. Jamais tournée sur t31 ni sur le corpus
  complet.

---

## 2. Ce qui ne marche pas, chiffré

### 2.1 Les dorsales gratuites distantes meurent
Compte nominatif des tours qui n'ont **jamais atteint le modèle** :

    RATE_LIMIT 12 · MISSING_CREDENTIAL 7 · QUOTA 3 · PI_AI_ERROR 1
    INVALID_REQUEST 1   =   24 tours

Et **deux campagnes entières à 100 % mortes** : `oxviafree` (10/10),
`runs/r01` (7 tâches). Elles avaient été publiées comme des mesures. Un garde
les marque désormais `X` — ni échec ni réussite — et les retire.

> **Pour la migration : une dorsale gratuite distante ne peut pas porter une
> session de travail. Secours, pas base.**

### 2.2 Le débit distant était mesurable depuis le début
803 appels sur le fil des campagnes t31e : **zéro** ne porte de bloc `timings`
(seul llama-server en renvoie) — mais **799 portent `usage.completion_tokens`**,
et l'enregistreur note déjà la durée de chaque appel. Le débit se calcule :

    distant ox-alpha   443 132 jetons / 14 462 s = 30,6 t/s
    local Qwen         181 018 jetons /  2 600 s = 69,6 t/s

Le banc affichait `0.0 t/s` sur chaque run distant. La correction du 23/08 le
remplace par `-` (non mesuré) : mieux que le zéro, mais encore faux — la donnée
était là. **À faire : calculer le débit depuis `usage` quand `timings` manque.**

> **Cette correction inverse une conclusion.** La dorsale locale n'est **pas**
> un levier de vitesse. Trois ouvriers distants à 31 t/s font 93 t/s agrégés ;
> le local n'admet qu'un ouvrier (une carte, un serveur) et fait 70 t/s. **Le
> local est ≈ 25 % plus lent au total.** Ce qu'il apporte réellement : aucun
> quota, et un tour qui tombe de ~620 s à ~220 s — donc le plafond de 900 s ne
> mord plus, alors qu'il élimine aujourd'hui 25 % des runs du bras web.

### 2.3 La recherche web n'a aucun effet mesurable
- Meilleur écart honnête jamais obtenu : **0 point sur n = 12** (12/12 avec web
  contre 12/12 sans).
- Plancher de bruit du banc sur la réussite : **20 points** (témoin high/xhigh,
  prompts identiques au caractère près).
- Le modèle ne cherche **jamais** de lui-même : **0 appel web sur 10 395**
  appels d'outils, sur 91 sessions.
- 8 mesures sur cet axe, dont **7** rendent « rien de séparable ».
- En mode boucle, le préambule dit d'ailleurs au modèle : *« Do NOT run a web
  search yourself »* — c'est le banc qui cherche.

### 2.4 Le corpus a été mal choisi
`t31` est classée **témoin** par le générateur du banc lui-même
(`_generer_palier_limite.py` : *« témoins : t31, t35, t36 — rien à chercher,
tout à déduire »*). Elle a pourtant absorbé **57 % du temps de banc**
(13,2 h sur 23,3 h) pour mesurer un effet de recherche.

Sur t31, la première cause d'échec au tour 1 n'est pas le raisonnement :

| issue du tour 1 | n / 40 | |
|---|---|---|
| **coupé au délai** | **13** | **33 %** |
| passe au tour 1 | 8 | 20 % |
| erreur Julia banale | 8 | 20 % |
| confusion de perturbation | 7 | 18 % |
| autre assertion | 4 | 10 % |

### 2.5 Deux bras sur trois sont le même bras
Empreintes d'énoncé mesurées sur t31e :

    sans      e8148e43dff6
    promesse  099d752caa1c
    web       099d752caa1c    ← identique, à l'octet près

`web` et `promesse` ne divergent qu'au tour 2, et seulement si une recherche
est livrée : **1 fois sur 4**. Le design est bon — il isole « être aidé » de
« savoir qu'on peut l'être » — mais l'analyse ne l'imprime jamais (voir §4.7).

---

## 3. Le seul axe qui ait jamais dépassé le bruit

**Exécuter le code.**

    runs qui ont lancé Julia     : 7 PASS / 9    (78 %)
    runs qui ne l'ont pas lancé  : 2 PASS / 15   (13 %)

**65 points contre un plancher de 20.** Confirmé deux fois de plus,
indépendamment : 9/12 avec 104 exécutions contre 4/12 avec 7 ; 6/6 en boucle
contre 5/6 en un-coup.

C'est le résultat le plus solide du chantier, et il n'a jamais été exploité
comme levier de conception — seulement observé.

---

## 4. Défauts ouverts, à réparer AVANT toute nouvelle campagne

### 4.1 — BLOQUANT — l'analyse n'attribue aucun appel en mode boucle
```
bench.py:1382  pose   "medium|t31|r1|t1|debut"     → 5 champs
analyse.py     _cle   ne gère que 4 champs, ou 3   → (None, None)
```
**Vérifié : 54 marques au sol, toutes à 5 champs ; 743 appels attribués à
rien.** Conséquences : `appels 0` sur toutes les lignes, et surtout **deux
gardes câblés qui passent au vert sur une liste vide** — contrôle d'horloge
(« 11/11 runs cohérents ») et contrôle de partage (« aucune conversation ne
traverse deux runs »). Leurs bras known-BAD tirent sur des marques à 4 champs
et n'ont jamais parcouru le chemin réel.
**Réparation : `_cle` doit accepter 5 champs.** Une ligne.

### 4.2 — BLOQUANT — la table principale plante
`KeyError: 'wall_s'` : l'enregistrement de secours écrit quand un ouvrier
explose ne porte pas ce champ. C'est ce plantage qui a caché 4.1 pendant tout
le chantier.

### 4.3 — VALIDITÉ — le chemin de l'oracle fuit dans l'énoncé
Le message du juge est recopié brut au tour 2, **avec le chemin absolu de
`tasks/t31_checks.jl`**. Le modèle a un outil de lecture de fichiers ; une
lecture donnerait les 11 assertions avec les valeurs attendues.
**5 espaces de travail** portent ce chemin. **Vérifié : jamais exploité** —
c'est un trou, pas un résultat corrompu.
La fuite est **asymétrique** : elle survient surtout dans le bras témoin, et un
témoin qui triche fait passer le traitement pour inutile.
**Réparation :** appliquer à `why` le nettoyage de chemins qui existe déjà pour
la requête de recherche (`bench.py:1147-1149`). Le banc protège le moteur de
recherche et laisse l'oracle exposé.

### 4.4 — le juge a moins de temps qu'un tour
`JUGE_TIMEOUT = 600` contre `BENCH_TIMEOUT_TOUR = 900`. Une solution
pathologique fait perdre le run entier. A tué 1 run sur 12 en t31e.
**Réparation :** juge ≥ tour.

### 4.5 — les mises de côté ne sont pas neutres
Taux de retrait par bras : **sans 0/4 · promesse 1/4 · web 2/4** — gradient
monotone dans le sens de la verbosité du traitement.
Effet mesuré sur t31e : le retrait a sorti du bras web **un FAIL et un PASS**,
ramenant son n à **1**, après quoi le rapport conclut « rien n'est séparable ».
L'instrument produit lui-même l'absence qu'il constate ensuite.
**Réparation : ne pas jeter — facturer le budget au bras qui l'a dépensé.**
Le verdict devient « résolue **dans le budget** ». C'est mot pour mot la
métrique que réclame `SPECDEC_4090_BENCH.md`.

### 4.6 — `promesse` est compté dans « sans web »
`analyse.py` lit `bras_web` (booléen) et ignore le champ `bras`. Les PASS du
bras promesse gonflent le bras « sans ». Et l'enregistrement de secours ne
porte pas `bras_web` du tout.

### 4.7 — le bloc de provenance ne s'imprime jamais
Un seul enregistrement court suffit à emprunter la branche « énoncé INCONNU »,
qui donne **la mauvaise cause** et **étouffe** la ligne la plus utile du
rapport : celle qui montre que `web` et `promesse` partagent leur énoncé.

### 4.8 — quatorze autres, moindres
Dénominateurs qui rétrécissent en silence, `wall_s or 0` affichant `0.0s` pour
un run d'au moins 600 s, `julia=-1` affiché brut, un contrôle d'échéance qui
compare à une constante de module au lieu du budget enregistré (7 fausses
alertes). Liste nominative complète disponible sur demande.

> **Diagnostic de fond.** Onze endroits du code nomment déjà correctement
> l'absence (`-1`, `n/a`, `None ≠ {}`, `SANS TRACE`, `inconnu`). Les défauts ne
> sont pas dans les fonctions qui **produisent** la valeur — ils sont dans les
> lignes qui la **lisent**. La réparation qui ferme la famille d'un coup : un
> bloc en tête de chaque rapport disant, pour chaque champ qu'il s'apprête à
> utiliser, **combien des N enregistrements le portent**.

---

## 5. À FAIRE, par ordre de valeur

### P0 — Poser enfin la question de la migration
Faire tourner `run_harness_ab.ps1` : **dsh contre l'agent de référence**, même
corpus, même juge, même budget. Seule mesure qui réponde à « peut-on remplacer
Claude Code par dsh ». Jamais faite, outillage prêt depuis le 20/08.
Sortie attendue : **temps mur médian par tâche réellement résolue**, par agent.

### P1 — Réparer 4.1 et 4.2 (une heure)
Sans ça, aucune campagne ne produit de mesure de débit ni de garde valide.
Ensuite **relire les campagnes déjà au sol** : les données sont sur le disque,
743 appels attendent d'être attribués. Aucune campagne à relancer.

### P2 — Réparer 4.3 et 4.4 (validité)
Toute campagne lancée avant est à refaire.

### P3 — Mesurer la dorsale locale sur le corpus complet
`specdec-q38-mtp`, mode boucle, 12 tâches, 3 répétitions, `--par 1`
(obligatoire : N ouvriers sur la dorsale locale mesurent la file, pas le
modèle). Seule dorsale sans quota — et non pas, contrairement à ce qui a été
écrit d'abord, la seule au débit mesurable (voir 2.2).
**C'est le chiffre qui manque pour décider.**

Deux raisons de plus, chiffrées, de la préférer malgré sa lenteur agrégée :
le plafond de 900 s ne mord plus, et le modèle local est ~29 points sous le
distant — ce qui le place plus près de 50 % de réussite, **là où chaque run
porte le maximum d'information** (0,244 contre 0,203, soit +20 %).

### P4 — Exploiter le seul levier qui sépare : forcer l'exécution
78 % contre 13 %. Rendre l'exécution obligatoire avant `DONE` dans le préambule
de boucle, et mesurer. Seul axe à 65 points ; tout le reste du chantier a couru
après des effets de 0 point.

### P5 — Abandonner l'axe web sur les tâches témoins
S'il est conservé : le courir sur `t32`, `t33`, `t34` (tâches à fait externe,
déjà listées par le banc dans `tasks/limite_faits_externes.txt`), **apparié par
tâche**. 6 tâches × 2 bras × 3 répétitions = 36 runs, ≈ 2,9 h ; 6 bascules dans
le même sens sur 18 paires suffisent (p = 0,031). Non apparié, il faudrait
+39 points — hors d'atteinte.

### P6 — Dorsales gratuites en secours seulement
Garde de mort-fournisseur en place et câblé ; pré-vol du modèle servi en place.
Reste à faire : détection à chaud, **en signal seul** — jamais de reprise
automatique, qui donnerait à un bras un budget que les autres n'ont pas eu.

---

## 6. Ce qu'on ne sait pas

- Si dsh + Qwen local tient une **vraie session de travail** : 18 runs de
  tâches mesurés, jamais un chantier réel.
- Le coût en jetons d'une session dsh contre une session Claude Code : jamais
  comparé.
- Si le corpus de 12 tâches Julia ressemble au travail réel. Il a été construit
  pour séparer des niveaux d'effort, pas pour ressembler à une journée.
- *Non vérifié* : les runs du bras web sans recherche passeraient 7/8, ceux
  avec une recherche 4/6.

---

## 7. Ce que ce chantier a coûté, et ce qu'il a rendu

À lire avant de reprendre le travail : la part utile est faible, et la façon
dont elle est faible est instructive.

**Le nombre qui ne dépend d'aucun jugement : 57 %.** 13,2 h de banc sur 23,3
ont été dépensées sur `t31` — la tâche que le générateur du banc classe
lui-même comme *témoin, rien à chercher, tout à déduire* — pour y mesurer un
effet de recherche web. Plus de la moitié du temps machine a servi à chercher
un effet sur une tâche choisie pour y être insensible.

**Sur les commits, environ 30 %, et ce chiffre dépend de son critère.**
Sur 69 commits : 16 publient un nombre, 53 réparent l'instrument. Des 16
mesures, **six** portent une ligne de ce document (exécution du code,
recensement des morts fournisseur, zéro appel web sur 10 395, plancher de
bruit, score local, boucle contre un-coup). **Sept** des dix autres disent
« rien de séparable » sur l'axe web — la première fois c'est un résultat, la
septième c'est de l'entêtement. Avec la douzaine de réparations qui rendent ces
six mesures dignes de confiance : une vingtaine de commits sur 69.

**Le vrai coût n'est pas dans le pourcentage.** Les trois trouvailles qui
recadrent tout le chantier étaient **lisibles dans le dépôt depuis le début** :

1. la ligne `NOT-RUN` de `SPECDEC_4090_BENCH.md` — la question jamais posée ;
2. la liste des tâches témoins dans `_generer_palier_limite.py` — le corpus
   mal choisi ;
3. le décalage entre le repère à 5 champs posé par `bench.py` et le repère à
   4 champs lu par `analyse.py` — l'analyse qui n'attribue rien.

Aucune ne demandait une campagne. Aucune ne demandait une heure. Elles
demandaient de reculer d'un pas et de relire ce qui était déjà écrit. Quatre
agents en lecture seule les ont trouvées en vingt-cinq minutes.

> **La leçon opératoire pour dsh2.0 :** avant d'ouvrir un chantier, relire ce
> que le dépôt affirme déjà de lui-même — les lignes `NOT-RUN`, les
> classifications que les générateurs écrivent, les formats que deux modules
> échangent. Un banc qui tourne est plus convaincant qu'un fichier qu'on relit,
> et c'est précisément pour ça qu'il fait perdre plus de temps.

---

## 8. Méthode, en une ligne

Neuf fois sur ce chantier, une **absence** a été publiée comme un **résultat** :
`julia=0` pour « jamais lancé », `rech=1` pour un refus, `web=11` pour une page
de blocage, un verdict sans juge, `0.0 t/s` pour « non mesuré », un garde vert
sur une liste vide. La variante la plus coûteuse est celle où le défaut est
dans **l'appareil** — un délai, un budget, un canal de livraison — parce qu'elle
ne ressemble pas à un bug : elle ressemble à une donnée sur le sujet.

Le test à passer sur chaque nombre publié :
**est-ce une propriété du sujet, ou de mon appareil ?**
