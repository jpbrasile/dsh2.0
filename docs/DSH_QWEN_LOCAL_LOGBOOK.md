# Log book — dsh + Qwen3.8-27B servi localement

Journal de ce qu'on a **mesuré** en montant un agent de code sur un modèle servi
en local, sur une seule RTX 4090. Destiné à devenir un tutoriel : chaque entrée
dit ce qu'on croyait, ce que l'instrument a répondu, et ce que ça change pour
quelqu'un qui refait le montage.

Règle du journal : **aucune entrée sans son instrument.** Si une ligne n'indique
pas d'où vient le nombre, elle n'a pas sa place ici.

Matériel et logiciel de référence pour tout ce document :
RTX 4090 24 Go · llama-server b10488 · Qwen3.8-27B Q4_K_M ·
`--ctx-size 65536 --parallel 1 --batch-size 2048 --ubatch-size 512`
`--spec-type draft-mtp --spec-draft-p-min 0.75 --spec-draft-n-max 2 --spec-draft-n-min 1`
· sans projecteur vision · 21 190 Mio de VRAM sur 24 564 · dsh 0.1.1-rc.2.

---

## Partie 1 — Monter le banc : quatre pièges qui ne préviennent pas

### 1.1 · Un seul format de pensée transmet un *niveau*

dsh propose une dizaine de `thinkingFormat`. Un seul, **`chat-template`**,
transmet le niveau d'effort au gabarit du modèle. `qwen-chat-template` n'envoie
qu'un booléen `enable_thinking` : avec lui, les cinq niveaux `off/low/medium/
high/xhigh` sont **une seule et même requête**, et une étude paramétrique
mesurerait cinq fois la même chose sans que rien ne le signale.

> **Pour le tutoriel.** Avant de faire varier un réglage, vérifier qu'il *arrive*
> au modèle. Le test coûte une requête : `/apply-template` sur llama-server rend
> le prompt final, on le hache et on compare.

### 1.2 · YAML 1.1 : `off:` non quoté est le booléen `false`

Dans la liste `reasoningEfforts` de `~/.dsh/settings.yaml`, la clé `off` **doit**
être écrite `"off"`. Sans guillemets, YAML 1.1 la relit comme `false` et le
niveau disparaît silencieusement. Même piège pour `on`, `yes`, `no`.

### 1.3 · `cmd.exe` mange les prompts multi-lignes

Un énoncé passé en `argv` à travers `cmd.exe` arrive **tronqué, voire vide**.
Constaté en clair : dsh a reçu une tâche vide et le modèle a inventé un problème
de Project Euler qu'on ne lui avait jamais demandé — et il l'a résolu.

> **Pour le tutoriel.** L'énoncé s'écrit dans un fichier (`TASK.md`) dans
> l'espace de travail ; la ligne de commande ne porte qu'un pointeur vers lui.
> Un agent qui répond à une question qu'on ne lui a pas posée est le symptôme.

### 1.4 · Ouvrir un fichier en écriture le tronque avant que l'écriture puisse échouer

Le banc réécrit trois lignes de `~/.dsh/settings.yaml` à chaque niveau. Écrit
naïvement, un plantage entre l'ouverture et l'écriture laisse la configuration de
l'utilisateur **vide**. On sérialise dans un fichier voisin puis `os.replace`.

---

## Partie 2 — Lire l'instrument avant sa sortie

### 2.1 · Le gabarit de Qwen3.8 aliase `high` sur `xhigh` — c'est un cadeau

Le gabarit contient `if resolved == 'high' -> 'xhigh'`. Vérifié côté serveur :
les deux niveaux produisent un prompt **identique au caractère près**,
sha256 `15c034577114cced`, 352 caractères. Le gabarit n'accepte d'ailleurs que
`low`, `medium`, `xhigh` ; toute autre valeur lève `raise_exception` et le
serveur rend 400. Et **`medium` n'ajoute aucune instruction** : la branche est
absente du gabarit.

Faire tourner `high` **et** `xhigh` ne donne donc pas deux points de mesure. Ça
donne le **plancher de bruit du banc**, gratuitement, dans la campagne elle-même.

> **Pour le tutoriel.** C'est la leçon la plus rentable du projet : *un témoin
> négatif intégré vaut mieux qu'une analyse statistique après coup.* Deux
> configurations qu'on sait identiques, courues comme les autres, mesurent
> directement le bruit auquel tout le reste doit être comparé.

### 2.2 · `prompt_n` n'est **pas** la longueur du contexte — mesuré le 22/08

Le bloc `timings` de llama-server rend `prompt_n`. On le lit spontanément comme
« la taille du prompt ». C'est faux : c'est le nombre de jetons **réellement
évalués**, donc *hors préfixe déjà en cache*. Le champ qui donne le contexte est
`usage.prompt_tokens` ; `timings.cache_n` donne la part réutilisée.

L'erreur n'est pas cosmétique. Sur le même run :

| champ lu | pic annoncé | % de 65 536 | conclusion tirée |
|---|---:|---:|---|
| `timings.prompt_n` | 23 007 | 35 % | « la compaction n'a jamais tiré » — **faux** |
| `usage.prompt_tokens` | **52 228** | **80 %** | la compaction a tiré **deux fois** |

> **Pour le tutoriel.** Un champ nommé `prompt_n` dans un bloc nommé `timings`
> est un champ de *chronométrage*, pas de *comptabilité*. Les deux nombres se
> lisent aussi bien l'un que l'autre, et rien dans la sortie ne dit lequel
> répond à la question posée.

### 2.3 · La compaction de contexte est automatique, seuil ≈ 80 %

Mesuré sur un run entièrement non-interactif — personne au clavier, donc aucune
compaction manuelle possible. Le contexte **recule** de lui-même :

| | avant | | après | |
|---|---:|---:|---:|---:|
| 1ʳᵉ compaction | 52 228 | 79,7 % | 33 758 | 51,5 % |
| 2ᵉ compaction | 52 122 | 79,5 % | 35 696 | 54,5 % |

Deux déclenchements indépendants à 79,7 % et 79,5 %, et **aucun appel de toute la
campagne n'a jamais dépassé 52 228 jetons** : le plafond est un déclencheur, pas
une coïncidence. Il ramène le contexte autour de 52 %, soit environ deux tiers
conservés.

Conséquence pratique : avec `--ctx-size 65536`, **la fenêtre n'est pas la
contrainte**. Le modèle est recyclé avant d'y buter. Ce qui arrête une tâche
longue, c'est le délai d'expiration.

Côté code, la logique vit dans `@deepseek-ai/dsh-compaction` (moteur
`CompactionEngine`), avec `dsh-compaction-basic` et
`dsh-compaction-tool-result-pruner` comme stratégies.

### 2.4 · Le débit MTP dépend de ce qu'on lui donne à deviner

Le décodage spéculatif auto-brouillon (`--spec-type draft-mtp`) ne gagne que sur
les jetons que la tête brouillon devine **juste**. Deux mesures du même serveur :

| trafic | débit |
|---|---:|
| prompts synthétiques de longueur fixe | 72 – 84 t/s |
| trafic d'agent réel (215 appels, 39 311 jetons, 626,7 s de décodage) | **62,7 t/s** agrégé |

Médiane 62,9 · quartiles 44,7 – 83,9 · maximum 101,5.

L'écart entre 84 et 62,7 n'est pas du bruit : c'est la différence entre du texte
prévisible et du texte qui ne l'est pas.

> **Pour le tutoriel.** Un débit annoncé sur des prompts synthétiques ne prédit
> pas le débit en usage agent. Mesurer sur le trafic réel, ou ne pas annoncer.

### 2.5 · Le contrôle qui peut contredire l'attribution

Le proxy enregistreur écrit `wire.jsonl` **en ajout** et ne sait rien des
campagnes. Deux campagnes successives y déposent deux fenêtres portant le même
marqueur, et un parcours naïf attribue au premier bras les appels de la campagne
précédente. Rien dans les nombres ne le montre : `off` annonçait **55,2 t/s**, le
plus lent des cinq niveaux, ce qui se lit parfaitement.

Le seul contrôle capable de le contredire : **un run ne peut pas passer plus de
temps en appels réseau qu'il n'a duré.** `off/t06` déclarait 226,9 s de décodage
dans un run de 47,5 s. Six runs sur cinquante, tous dans le premier bras.

Après correction (on retient la **dernière** fenêtre de chaque marqueur) :
50/50 runs cohérents, et `off` passe de 55,2 à **88,0 t/s** — le plus **rapide**.

> **Pour le tutoriel.** Les autres nombres d'une table sont d'accord avec
> l'attribution *par construction* : ils ne peuvent pas la démentir. Il faut
> une grandeur qui vienne d'ailleurs — ici l'horloge du client — et le contrôle
> doit être **câblé dans l'analyse**, pas fait une fois à la main.

### 2.6 · Un verdict s'imprime sur une ligne, une erreur Julia sur plusieurs

Le harnais imprimait le verdict et le lecteur faisait `tail -1`. Un `showerror`
Julia tient sur plusieurs lignes : `tail -1` attrapait
`in expression starting at ...` au lieu de la cause. Le bras known-BAD du
vérificateur rendait **0/10 attrapées** alors qu'il les attrapait toutes.

Correction : le harnais aplatit le message, et le lecteur filtre sur `^VERDICT`.

---

## Partie 3 — Ce que le modèle fait réellement

### 3.1 · La table des cinq niveaux, 50 runs, corpus de base

| effort | réussite | temps méd. | temps moy. | jetons/tâche | débit | appels |
|---|---:|---:|---:|---:|---:|---:|
| off | 9/10 | 10,1 s | 15,1 s | 624 | **88,0 t/s** | 5,8 |
| low | 9/10 | 17,5 s | 35,5 s | 1 599 | 72,5 t/s | 6,2 |
| medium | **10/10** | 41,0 s | 68,9 s | 3 940 | 73,2 t/s | 10,9 |
| high | 9/10 | 36,5 s | 74,6 s | 4 357 | 75,4 t/s | 12,1 |
| xhigh | 7/10 | 45,4 s | 69,0 s | 4 012 | 75,1 t/s | 12,3 |

**Le témoin se lit avant la table** (`high` ≡ `xhigh`, cf. 2.1) :

| grandeur | plancher de bruit | écart off → medium | rapport |
|---|---:|---:|---:|
| réussite | **2 / 10** | 1 / 10 | **< 1** |
| jetons | 8 % | +531 % | 66× |
| temps moyen | 8 % | +356 % | 45× |
| débit | 0,4 % | −17 % | 42× |

Trois conclusions, dans cet ordre :

1. **Sur la réussite, ce banc ne sépare rien.** Deux configurations *identiques*
   diffèrent de 2 sur 10 ; l'étendue entre les cinq niveaux est de 3 sur 10. Le
   `10/10` de `medium` et le `7/10` de `xhigh` sont dans le bruit. Ce n'est pas
   un échec du banc, c'est son résultat le plus solide.
2. **Sur le coût, il sépare massivement.** Activer le raisonnement multiplie les
   jetons par 2,6 à 7 et le temps par tâche par 2,4 à 5 : 45 à 66 fois le
   plancher de bruit.
3. **Le raisonnement coûte aussi 17 % de débit** — 88,0 t/s sans, 72–75 t/s avec
   (mécanisme : cf. 2.4).

Autrement dit, sur ce corpus, l'effort de raisonnement **achète du coût sans
acheter de réussite mesurable**.

### 3.2 · En un coup, le modèle n'exécute jamais son code — et dit l'avoir vérifié

Un shim `julia.cmd` journalise chaque invocation de Julia par l'agent. Sur les
**50 espaces de travail** de la campagne en un coup : **zéro** fichier de test
écrit, **zéro** exécution de Julia. Le modèle écrit la solution et annonce
« écrite et vérifiée ».

### 3.3 · Se forcer à écrire un test bat le fait de réfléchir plus fort

Le mode itératif oblige le modèle à écrire ses propres tests, à lancer Julia et à
corriger jusqu'à ce que ça passe. Des tâches que le raisonnement seul ne sauvait
pas passent alors — parce qu'écrire un test **fait énumérer les cas**, ce que
« réfléchir plus fort » ne fait pas.

C'est cohérent avec 3.1 : le levier n'est pas dans la profondeur de réflexion,
il est dans la **boucle de retour**.

### 3.4 · Le défaut typique est une hallucination qu'aucune réflexion ne révèle

Exemple relevé sur le corpus dur, niveau `off`, tâche t13 :

```
LoadError: UndefVarError: `cdiv` not defined in `Main.Sol`
```

Julia n'a pas de `cdiv` ; la fonction s'appelle `cld`. Aucun niveau d'effort ne
peut découvrir ça — c'est une croyance sur le monde, pas un raisonnement — mais
**une seule exécution** le révèle instantanément. C'est l'hypothèse centrale que
teste la paire de campagnes un-coup / itératif.

### 3.5 · Le modèle a des outils web et ne s'en sert jamais

`dsh-tool-web` déclare `web_search` et `web_fetch`, tous deux à **`true` par
défaut** — ils font partie des 27 outils envoyés au modèle à chaque appel. Les
journaux de session de dsh (zstd, un répertoire par répertoire de travail)
donnent, sur les **91 sessions** du banc :

| outil | appels |
|---|---:|
| `write` | 6 308 |
| `pwsh` | 2 429 |
| `edit` | 1 057 |
| `read` | 597 |
| `glob` | 4 |
| **`web_search` / `web_fetch`** | **0** |

10 395 appels d'outils, zéro appel web. Ce n'est pas une restriction : c'est un
comportement. Laissé seul, ce modèle ne cherche pas.

> **Pour le tutoriel.** Deux conséquences opposées et toutes deux utiles. (1) Les
> résultats déjà publiés sont **purement locaux en pratique**, ce qui n'allait
> pas de soi et qu'il fallait vérifier. (2) Une campagne « avec / sans recherche
> web » ne peut pas se contenter d'activer l'outil : sans instruction explicite,
> les deux bras sont le même bras. Et le seul moyen de le savoir est de
> **compter les appels réellement passés**, par run.

Attention au piège de mesure sur le chemin : un `grep web_search` sur les
fichiers de session rend **0**, parce qu'ils sont compressés. Un zéro qui ne
mesure rien ressemble exactement à un zéro qui mesure.

### 3.6 · Le corpus de base était trop facile

Mesuré avant de durcir : **6 des 10 tâches ne tombent à aucun niveau d'effort**.
Une tâche qui réussit partout ne contribue rien à une étude paramétrique — elle
gonfle le dénominateur et rétrécit l'étendue observable.

D'où un palier dur, `t11..t16`, dont chaque tâche vise un piège nommé :

| tâche | piège |
|---|---|
| t11 | variance en flux (Welford) — la somme des carrés naïve rend 0,0 au lieu de 1,0 sur `[1e8, 1e8+1, 1e8+2]` |
| t12 | `axpy!` en place, **zéro allocation**, avec des vues |
| t13 | itérateur `Chunks` — `cld` contre `div` dans `length` |
| t14 | `CIStr` — contrat `hash`/`isequal` |
| t15 | `horner` — stabilité de type |
| t16 | `Circulant <: AbstractMatrix` — interface complète |

Chaque tâche a un bras known-GOOD et un bras known-BAD, et le banc **exige que
chaque known-BAD tombe sur *son propre* défaut nommé**. Un vérificateur cassé —
qui ne charge rien, qui se trompe de chemin — rend lui aussi « tout attrapé » ;
ce qui distingue celui qui mesure, c'est le nom de l'assertion qui a tiré.

Calibrage mesuré le 22/08 : 6/6 GOOD, 6/6 BAD, chacune par son défaut.

> **Aparté honnête.** Sur t13, j'avais prédit que mon assertion sur `length`
> attraperait l'écart `div`/`cld`. C'est le `collect` de Julia qui l'a attrapé
> d'abord (« destination has fewer elements than required »). Le bras known-BAD
> tirait, mais pas par où je l'avais prévu — raison de plus pour imprimer *par
> quelle assertion* chaque échec tombe, plutôt que de compter les échecs.

---

## Partie 4 — Trois grandeurs qui ne se remplacent pas

| grandeur | instrument | ce qu'elle inclut |
|---|---|---|
| **réussite** | Julia exécute la solution contre des assertions que le modèle n'a jamais vues | binaire |
| **débit (t/s)** | bloc `timings` de llama-server, relevé par un proxy | décodage seul |
| **temps / tâche** | chrono client, lancement → verdict | agent + outils + Julia |

Le débit est une propriété du **serveur**. Le temps par tâche est une propriété
du **système**, et c'est lui qui décide si un réglage est utilisable. Un niveau
peut décoder plus vite **et** finir plus tard, parce qu'il génère plus de jetons
ou passe plus d'appels d'outils — c'est exactement ce que fait `medium` ici.

---

## Journal chronologique

| date | entrée |
|---|---|
| 2026-08-22 | Campagne de base, 50 runs, cinq niveaux. Table 3.1. |
| 2026-08-22 | Défaut d'attribution attrapé par le contrôle d'horloge ; `off` 55,2 → 88,0 t/s (2.5). |
| 2026-08-22 | Zéro exécution de Julia sur 50 espaces de travail en mode un coup (3.2). |
| 2026-08-22 | Débit agrégé sur trafic agent réel : 62,7 t/s, contre 72–84 en synthétique (2.4). |
| 2026-08-22 | Palier dur `t11..t16` construit et calibré 6/6 GOOD, 6/6 BAD (3.5). |
| 2026-08-22 | `prompt_n` ≠ contexte ; le pic réel est 52 228, pas 23 007 (2.2). |
| 2026-08-22 | Compaction automatique établie par la mesure : seuil ≈ 80 %, retour à ≈ 52 % (2.3). |
| 2026-08-22 | Étude paramétrique sur corpus dur lancée : un-coup puis itératif, 3 répétitions, 90 runs chacune. |

---

## Ce que le banc ne dit pas encore

- **Réussite à n plus grand.** Le plancher de bruit est de 2 sur 10. Pour
  trancher un écart de 1 sur 10, il faut soit des tâches assez dures pour que
  `off` décroche, soit assez de répétitions pour descendre le plancher sous 1.
  Les deux sont en cours.
- **Taux d'acceptation MTP par type de texte.** Le mécanisme de 2.4 est cohérent
  avec les débits mesurés mais n'a **pas** été ré-instrumenté ici. *Unverified.*
- **Tâches à phase de planification, avec et sans recherche web préalable.**
  Corpus écrit (t21..t26 et t31..t36), bras web câblé, **non encore calibré** :
  les douze bras known-GOOD/known-BAD n'ont pas tourné. À noter que la recherche
  passe par l'API DeepSeek (`dsh-web-search-deepseek`, `https://api.deepseek.com`),
  donc **hors du modèle local** : la comparaison doit dire ce qui est local et ce
  qui ne l'est pas.

---

## Fichiers

Le banc lui-même vit dans `scripts/bench_julia_effort/` ; son `README.md` donne
le mode d'emploi. Les fenêtres de mesure sur le serveur sont dans
`docs/SPECDEC_4090_BENCH.md`.
