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

## Partie 1 — Monter le banc : sept pièges qui ne préviennent pas

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

### 1.5 · Un délai d'expiration ne tue que le fils direct — et la campagne se fige derrière l'orphelin

Le plus cher des cinq, mesuré le 22/08 en pleine campagne. `subprocess.run(…,
timeout=)` tue le processus qu'il a lancé, **pas ses descendants**. Or le fils
direct ici est `dsh.cmd` ; l'agent lui-même est le *petit-fils*.

Ce qui se passe à l'échéance :

1. le `.cmd` meurt ;
2. l'agent survit, **orphelin**, et continue d'appeler le modèle — donc d'occuper
   la carte, et de fausser le débit de tout ce qui tournera ensuite ;
3. il garde le tuyau de sortie ouvert, donc le `communicate()` que Python
   enchaîne après le kill attend sa fermeture — **indéfiniment**.

Relevé sur `r2/high/t11` : échéance de 900 s, **durée 1588,9 s**, aucun essai
suivant pendant tout ce temps. Diagnostic confirmé sans ambiguïté par trois
mesures indépendantes : le parent de l'agent n'existait plus (orphelin), Python
totalisait 0,4 s de calcul et n'en prenait pas un centième de plus en 5 s
(bloqué, pas lent), et le journal du proxy montrait l'agent **encore en train
d'écrire**. La campagne est repartie seule dès l'arbre tué.

Remède, dans `bench.py` : `lancer_borne` + `tuer_arbre` — `taskkill /F /T` sous
Windows, `killpg` ailleurs — puis une **seconde** échéance courte, parce qu'un
descendant peut encore échapper au kill et qu'un run perdu se remesure alors
qu'une campagne figée, non.

> **Pour le tutoriel.** Le nombre qui l'a montré n'est pas dans le verdict : le
> verdict disait `FAIL / timeout 900s`, ce qui est exact. C'est la **durée** qui
> était impossible — 1588,9 s pour une échéance de 900 s. Un run ne peut pas
> durer plus longtemps que sa propre échéance ; ce contrôle est désormais câblé
> en fin d'`analyse.py` et il tourne à chaque analyse.

---

### 1.6 · Le banc qui tourne n'est pas celui qu'on répare

Deux heures de réparations ce matin — le correctif de l'orphelin (1.5), les
paliers `t21..t36` (3.7), trois contrôles câblés dans `analyse.py` — et
**aucune** n'était dans le processus en cours d'exécution.

La campagne avait été lancée depuis une **copie** du banc, dans le répertoire de
travail temporaire d'une session déjà terminée. Mesuré le 22/08 à 11:30 :

| fichier | dépôt | copie qui tourne |
|---|---|---|
| `bench.py` | 21 188 o, 11:27 | 11 962 o, **09:16** |
| `analyse.py` | 19 785 o, 10:57 | 9 424 o, **09:16** |
| `tuer_arbre` / `lancer_borne` | présents | **0 occurrence** |
| `TACHES_EXPERT` / `TACHES_LIMITE` | présents | **0 occurrence** |

Rien n'était perdu — la campagne 1 s'était terminée **90/90** et s'était
archivée proprement. Mais les douze tâches calibrées ce matin étaient
**inatteignables** par le processus censé les exécuter, et le correctif de
l'orphelin n'y était pas non plus : le même gel pouvait se reproduire.

> **Pour le tutoriel.** Le piège n'est pas d'avoir copié — c'est que rien dans la
> sortie ne dit *depuis où* on tourne. Un banc doit annoncer son propre chemin à
> chaque lancement ; sinon « j'ai corrigé bench.py » et « le correctif tourne »
> restent deux affirmations différentes qu'on prend pour une seule. C'est la même
> règle qu'en 2.2 et 2.5 : « le code fait X » et « X a tourné » demandent des
> preuves différentes.

---

### 1.7 · Un routeur qui agrège BASCULE — et une route montée n'est pas une route qui répond

Le 22/08 le banc a reçu une **seconde dorsale** : FreeLLMAPI, un routeur local
qui met 16 fournisseurs gratuits derrière un seul point d'entrée compatible
OpenAI. Il ouvre `deepseek-v4-pro` — le modèle natif de dsh — sans clef
DeepSeek. Sept choses ont dû être mesurées avant que le premier run passe, et
aucune ne prévient.

**Le port n'est pas celui de la documentation.** L'amont annonce partout 3001 ;
c'est le port du déploiement serveur. L'application de bureau lit
`%APPDATA%\FreeLLMAPI\config.json`, qui porte `{"port": 31415}`. J'ai d'abord
démarré un conteneur Docker **vide** sur 3001 avant de sonder : il n'avait
aucune clef, pendant que l'instance réelle en avait seize. Démonté. Sonder
l'application avant de la réinstaller coûtait une commande.

**Les identifiants servis sont des slugs courts, et la forme longue est celle
qui REVIENT.** `/v1/models` sert `deepseek-v4-pro` ; `deepseek-ai/DeepSeek-V4-Pro`
est **absent** de la liste — c'est ce que le routeur écrit dans `body["model"]`
en réponse, pas ce qu'il accepte en entrée. Recopier la forme de la réponse dans
la configuration donne une route qui se monte et ne sert jamais.

**`auto` bascule, donc `auto` ne mesure rien.** Appel témoin du 22/08, avec
outils : parti sur le premier fournisseur, revenu servi par **DeepSeek-V4-Flash**,
en-tête `x-fallback-trail: huggingface/deepseek-ai/DeepSeek-V4-Flash-0731
key1=rate_limited`. Le modèle a changé sous la mesure sans qu'aucun code ne le
demande. Pour mesurer, on **épingle** un identifiant et on lit
`x-fallback-trail` pour prouver qu'aucune bascule n'a eu lieu. Le témoin nomme
donc le modèle **réellement servi**, jamais un HTTP 200.

**`apiKeyEnv` DÉCLARÉ n'est pas `apiKeyEnv` DÉFINI.** Une variable vide ne casse
qu'au premier appel, et sous une forme qui envoie chercher ailleurs :
`PI_AI_ERROR: No API key for provider`. La route est montée, visible dans
`/model`, et **échoue en permissif**. Le banc lit donc la clef au lancement et
**refuse de partir** si elle est illisible — garde câblé dans le même
changement, ses deux bras tirés : clef lue (59 caractères, préfixe
`freellmapi-`), base déplacée (`base introuvable`, code 1).

**dsh refuse un niveau d'effort que le modèle ne déclare pas.** Premier run
mort en **1,1 s** sur `UNSUPPORTED_REASONING_EFFORT`. Le routeur, lui, annonce
`reasoning_effort` dans `supported_parameters` : il fallait écrire la carte des
niveaux côté dsh. `xhigh` n'y est pas — l'ensemble accepté en amont n'est pas
vérifié, et un niveau refusé ferait 400 au premier appel. *Que le fournisseur
gratuit HONORE l'effort reste non vérifié : declarer n'est pas mesurer.*

**Marquer le proxy d'une autre campagne fabrique des appels qui n'ont pas eu
lieu.** `marquer()` pose des bornes dans `wire.jsonl` pour attribuer les appels
à une tâche. Sur une API externe il n'y a pas de proxy à marquer — et marquer
celui du modèle local aurait injecté des bornes étrangères dans le journal de la
campagne en cours, où `analyse.py` lit des fenêtres. `BENCH_PROXY` vide rend
maintenant `marquer()` muet.

**Deux campagnes se battaient pour les mêmes trois lignes.** `dsh_effort.py`
réécrit `provider` / `model` / `reasoningEffort` dans `~/.dsh/settings.yaml` ;
deux campagnes simultanées changent donc le modèle l'une de l'autre **en cours
de run**. dsh lit sa configuration sous `$DSH_HOME` : le banc respecte
maintenant cette variable, pour la configuration **et** pour les sessions d'où
sont comptées les recherches web. La campagne externe tourne dans
`~/.dsh-freellm`, à côté de la campagne locale, sans la toucher.

**Et chaque ligne de résultat porte désormais `provider` et `modele`.** Un banc
qui sert deux dorsales et n'écrit pas qui a répondu produit un seul tas de
chiffres.

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

### 2.7 · Un bras known-BAD peut tomber sans jamais toucher son défaut

Calibrage du palier limite, 22/08. Le compte disait :

```
known-GOOD 5/6   known-BAD attrapés 6/6
```

Lu comme un compte, c'est « le vérificateur attrape tout, et une référence a un
souci ». Lu par le **nom de l'assertion**, c'est autre chose : sur t31, les deux
bras tombaient sur **la même** erreur.

| bras | cause du refus |
|---|---|
| known-GOOD (référence) | `MethodError: no method matching derivative(::typeof(sin), ::Dual{1})` |
| known-BAD | `MethodError: no method matching derivative(::typeof(sin), ::Dual{1})` |

Le `6/6 attrapés` de t31 ne mesurait donc rien : la mauvaise solution était
refusée **avant** que son défaut nommé — la confusion de perturbation — ait la
moindre chance d'être évalué. Un bras known-BAD dont on ne lit que le compte est
d'accord avec l'hypothèse par construction.

La cause était dans l'énoncé, pas dans le code : il imposait
`derivative(f, x::Real)` **et** l'imbrication. Or imbriquer passe un dual *en
tant que* `x`. Les deux voies ont été essayées et mesurées :

| dual déclaré | ce qui arrive |
|---|---|
| `<: Number` | `x::Real` ne s'applique plus → `MethodError` |
| `<: Real` | `<(::Dual, ::Int64) is ambiguous` contre `Base.<(::Real, ::Real)` |

L'énoncé dit désormais `derivative(f, x::Number)`, qui laisse passer les deux
conceptions. Après correction, le bras known-BAD tombe par son défaut :
`confusion de perturbation : 2.0 au lieu de 1.0`.

> **Pour le tutoriel.** Une tâche doit échouer par le piège qu'elle nomme. Un
> second piège non nommé — ici un choix de hiérarchie de types imposé par la
> signature — transforme la mesure en loterie, et le compte ne le montre jamais.

### 2.8 · Assouplir une exigence est une décision, donc ça se mesure

Deux modifications du juge attendaient, non commitées, et toutes deux dans le
sens de l'indulgence : une tolérance numérique divisée par dix (t22) et deux
témoins de primalité remplacés (t34). Le test qui tranche coûte deux appels à
Julia : faire tourner les deux bras contre les **anciennes** assertions.

| | ancien jeu | nouveau jeu |
|---|---|---|
| t22 référence | PASS | PASS |
| t22 known-BAD | FAIL `pas non adaptatif` | FAIL `pas non adaptatif` |
| t34 référence | PASS | PASS |
| t34 known-BAD | FAIL `jeu de témoins tronqué` | FAIL `jeu de témoins tronqué` |

Aucun des deux assouplissements ne réparait quoi que ce soit. Le second retirait
même un piège : `999999999989` au carré déborde de 64 bits, `2147483647` non.
Les deux sont annulés. (Vérifié au passage : les quatre constantes, ancienne et
nouvelle version, étaient factuellement justes — ce n'était pas une correction.)

> **Pour le tutoriel.** Un juge ne se desserre pas « pour être raisonnable ». Il
> se desserre contre une mesure qui montre qu'il refusait à tort, et cette mesure
> tient en une ligne : la référence passe-t-elle l'exigence stricte ?

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

`dsh-tool-web` déclare deux outils, `web_search` et `web_fetch`, et son schéma
met les deux à `true` par défaut. **Mais le paquet de base ne monte pas le
second** : `dsh-base/cordis.patch.yml` configure `tool-web` avec `fetch: false`,
et le greffon change alors sa propre consigne — il dit au modèle d'utiliser les
extraits rendus plutôt que d'aller chercher la page. Dans cette composition,
`web_fetch` **n'existe pas** ; seul `web_search` est offert. *(Vérifié dans la
configuration livrée le 22/08 ; non ré-observé sur le fil, celui-ci ayant été
supprimé — voir le journal.)* Les journaux de session de dsh (zstd, un
répertoire par répertoire de travail) donnent, sur les **91 sessions** du banc :

| outil | appels |
|---|---:|
| `write` | 6 308 |
| `pwsh` | 2 429 |
| `edit` | 1 057 |
| `read` | 597 |
| `glob` | 4 |
| **`web_search` / `web_fetch`** | **0** |

10 395 appels d'outils, zéro appel web. Ce n'est pas une restriction : c'est un
comportement. Laissé seul, ce modèle ne cherche pas. Le zéro porte sur
`web_search`, le seul outil web réellement offert.

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

### 3.7 · Douze tâches à phase de planification, calibrées 12/12 et 12/12

Le corpus dur `t11..t16` vise des pièges d'écriture. Les douze tâches suivantes
visent autre chose : il faut **décider plusieurs composants avant d'écrire**.
Deux paliers, et l'intention était que sur chacun la moitié des tâches dépende
d'un fait **externe vérifiable** — là où une recherche web peut aider — et
l'autre moitié pas du tout. Sans ces témoins, « le web aide » serait
indistinguable de « un énoncé plus long aide ». **L'étiquetage s'est révélé faux
sur deux tâches** : voir la correction sous la table.

| | tâche | piège nommé | fait externe | le fait est-il **dans l'énoncé** ? |
|---|---|---|---|---|
| EXPERT | t21 | matrice bande : écriture non nulle hors bande | non | — |
| | t22 | RK adaptatif : le pas doit vraiment s'adapter | **oui** | non — le tableau de coefficients manque |
| | t23 | analyseur de Pratt : `^` associe à DROITE | non | — |
| | t24 | décodeur MessagePack : entiers gros-boutistes | **oui** | non — ni les octets de type, ni le boutisme |
| | t25 | Tarjan + condensation : pas d'auto-boucle | non | — |
| | t26 | `gemm` 5 arguments : `beta = 0` écrase `C` **sans le lire** | ~~oui~~ **retiré** | **OUI, en entier** — les deux clauses du contrat sont écrites |
| LIMITE | t31 | confusion de perturbation en dérivation imbriquée | non | — |
| | t32 | `BroadcastStyle` + `similar(::Broadcasted)` | **oui**, faible | non, mais la voie est signalée |
| | t33 | tri radix conforme à `isless` (`-0.0` et `NaN` compris) | ~~oui~~ **retiré** | **OUI, en entier** — les quatre règles sont listées |
| | t34 | Miller-Rabin déterministe 64 bits : jeu de témoins | **oui**, partiel | le mode d'échec oui, le jeu de bases non |
| | t35 | arithmétique d'intervalles : produit sur **quatre** coins | non | — |
| | t36 | vecteur persistant : partage de structure réel | non | — |

**Correction du 22/08, mesurée après coup.** La colonne « fait externe » avait
été **décidée**, jamais vérifiée. Le contrôle est pourtant à deux minutes :
*le fait est-il imprimé dans la question ?* Relecture des six énoncés étiquetés
« oui » : **deux d'entre eux donnent la réponse en entier**. Sur `t26` le contrat
de `mul!` à cinq arguments est écrit clause par clause ; sur `t33` les quatre
règles de la conversion motif → clé sont listées. Aucune recherche web ne peut
rien y apporter, pour aucun modèle — ces deux tâches sont **structurellement
muettes sur l'axe web**. Le corpus a donc **quatre** tâches à fait externe, pas
six, et l'une est faible (`t32`) et une autre partielle (`t34`).

Les quatre faits qu'une recherche doit réellement apporter, nommément — c'est
l'attente vérifiable du bras web, et pas seulement « a-t-il cherché » :

| tâche | ce qu'une recherche doit rapporter |
|---|---|
| `t22` | un tableau emboîté (Dormand-Prince 5(4), Bogacki-Shampine 3(2)…) |
| `t24` | la table des octets de type MessagePack **et** le gros-boutisme |
| `t32` | `Base.BroadcastStyle` et `similar(::Broadcasted, ::Type)` |
| `t34` | un jeu de témoins prouvé suffisant sous 2⁶⁴ (les 12 premiers premiers) |

Calibrage mesuré le 22/08 : **12/12 known-GOOD, 12/12 known-BAD**, chacune par
son propre défaut nommé. Le chemin pour y arriver est en 2.7 et 2.8 : le premier
compte affiché était `6/6 attrapés` sur un bras qui ne mesurait rien.

Le bras « avec web » n'est pas un interrupteur : c'est un **préambule** qui
impose chercher-puis-planifier, parce que laissé seul ce modèle ne cherche
jamais (3.5). Et le banc **compte les appels web réellement passés par run**, en
relisant le journal de session du répertoire de travail — chaque run a le sien,
donc la correspondance est exacte. L'analyse refuse les deux façons d'être
trompé : un run « sans » qui cherche quand même, un run « avec » qui ne cherche
jamais. Quand la mesure n'a pas pu être faite, elle rend `-1`, pas `0`.

**Ce qui n'est pas local.** La recherche passe par l'API DeepSeek
(`dsh-web-search-deepseek`, `https://api.deepseek.com`) : le bras « avec web »
sort de la machine. Toute comparaison doit le dire.

---

### 3.8 · Une seule case sur quatre : le plafond « un coup, sans web »

Un chiffre de réussite ne veut rien dire seul. « 4 sur 12 » est un désastre si
la tâche est faisable en un coup, et un exploit si elle ne l'est pas. Il fallait
donc un **plafond mesuré sur le même corpus, par le même juge**.

Protocole, tel qu'il a été tenu : je (Claude Code, modèle par défaut) n'ai lu
que les **énoncés** `prompts/tNN.txt` — jamais `ref/`, jamais
`tasks/tNN_checks.jl` avant d'avoir rendu. Un fichier `solution.jl` par tâche,
**sans lancer Julia avant de rendre** et **sans aucune recherche web** : c'est
exactement le bras « un coup » du modèle local. Le verdict est rendu par le
même `tasks/harness.jl`.

| palier | tâche | verdict | essais | temps (s) | lignes | déjà vu avant d'écrire |
|---|---|---|---|---|---|---|
| EXPERT | t21 | **PASS** | 1 | 21 | 61 | — |
|  | t22 | **PASS** | 1 | 78 | 53 | les deux tolerances du juge vues |
|  | t23 | **PASS** | 1 | 34 | 118 | — |
|  | t24 | **PASS** | 1 | 22 | 87 | — |
|  | t25 | **PASS** | 1 | 21 | 97 | — |
|  | t26 | **PASS** | 1 | 16 | 31 | — |
| LIMITE | t31 | **PASS** | 1 | 68 | 79 | reference et assertions lues en entier |
|  | t32 | **PASS** | 1 | 47 | 37 | — |
|  | t33 | **PASS** | 1 | 21 | 62 | — |
|  | t34 | **PASS** | 1 | 19 | 56 | les deux temoins de primalite vus |
|  | t35 | **PASS** | 2 | 69 | 46 | — |
|  | t36 | **PASS** | 1 | 33 | 70 | — |

**12/12 réussies, 11 en un coup, 0 recherche web, 0 exécution de Julia avant de
rendre.** 447 s de production au total, 8 s de jugement.

**Le seul échec est instructif, et il va dans le sens contraire de l'intuition.**
Sur t35 (arithmétique d'intervalles) j'ai d'abord écrit la version *savante* :
détecter l'erreur d'arrondi exacte (TwoSum de Knuth pour la somme, `fma` pour le
produit et le quotient) et n'élargir la borne **que** si l'opération avait
réellement arrondi. Cette version **conserve la propriété de contenance** — elle
est juste — mais elle laisse la borne **égale** au résultat flottant, alors que
le contrat demande une borne strictement **à l'extérieur**. Le juge l'a dit en
un mot : `[0.3, 0.30000000000000004]`. La réparation a été de *retirer* la
finesse : `prevfloat` / `nextfloat` sans condition, 69 lignes tombées à 46. Un
raffinement peut échouer là où la version naïve passe.

**Ce que cette ligne ne mesure pas.** Trois tâches sont **contaminées** : au
cours de la même session j'avais lu la référence et les assertions de t31 en
entier (en réparant son bras known-BAD, 2.7), et vu les deux tolérances de t22
ainsi que les deux témoins de primalité de t34 (en annulant les deux
assouplissements, 2.8). Les neuf autres ont été faites à l'aveugle. Et je n'ai
**aucun accès à mon propre compte de jetons** : la colonne « temps » est un
chrono client qui inclut la latence du harnais, pas un débit. Les colonnes
comparables au modèle local sont **verdict** et **essais**, pas le temps.

À quoi ça sert : quand la campagne `t21..t36` tournera, chaque case aura un
plafond en face d'elle. Une tâche que le modèle local rate et que ce plafond
passe en un coup mesure le **modèle** ; une tâche que les deux ratent mesure
l'**énoncé**.

**Et ce que ça ne sert pas, dit sans détour.** Le banc a quatre cases — un coup
ou itératif, croisé avec sans web ou avec web. Cette ligne n'en remplit **qu'une**.
Elle a d'abord été publiée sous le titre « la référence », ce qui était trop
large : trois écarts la séparent de ce que reçoit l'agent dsh.

| | agent dsh | cette ligne |
|---|---|---|
| plan écrit avant le code | imposé par le préambule | aucun |
| exécution de Julia | shim + shell, boucle jusqu'à passer | jamais avant de rendre |
| `web_search` | disponible | non appelé |

Pire, **le bras « avec web » n'est plus courable sur ce même exécutant** : ayant
résolu les douze tâches sans chercher, le contrefactuel « aurais-je eu besoin
d'une recherche ? » est détruit. L'ordre correct était de courir le bras web
**d'abord**, ou de couper le corpus en deux moitiés disjointes. C'est une faute
d'ordonnancement, pas un oubli, et elle ne se rattrape pas après coup.

Ce qu'il en reste d'utilisable est réel mais borné : à 12/12 le plafond
**sature**. Il ne laisse aucune marge pour qu'un effet du web se voie sur la
réussite de cet exécutant-là — il ne sert qu'à attribuer les échecs du modèle
local. Ce qui a survécu de plus utile, c'est la **liste nominative des quatre
faits qu'une recherche doit rapporter** (3.7) : elle transforme la question
« a-t-il cherché ? » en « a-t-il cherché la bonne chose ? ».

---

### 3.9 · Vingt-quatre agents neufs, même énoncé à l'octet près : le web ne sépare rien à ce niveau

La ligne 3.8 ne remplissait qu'une case sur quatre, et son bras web était mort-né
— ayant résolu les douze tâches sans chercher, je ne pouvais plus répondre à
« aurais-je eu besoin d'une recherche ? ». La réparation n'est pas de recommencer
sur moi : c'est de faire tourner **vingt-quatre exécutants neufs**, un par
(bras, tâche), aucun n'ayant jamais vu le corpus.

**Ce qu'ils ont reçu, exactement.** Un dossier de travail contenant un seul
fichier, `TASK.md`, construit par un script qui fait `import bench` et
concatène `bench.PREAMBULE_WEB` et `prompts/tNN.txt` **par le même code que
`bench.py`** — l'énoncé est donc identique à l'octet près à celui que reçoit
l'agent dsh (2 141 octets avec préambule web, 1 285 sans, mesuré sur t22). La
consigne d'entrée est celle de dsh, mot pour mot : *« Read the file TASK.md in
the current directory and do exactly what it says. »* Chaque agent a écrit à
côté un `_journal.txt` déclarant ses exécutions de Julia, ses recherches et
**le texte de ses requêtes**. Le verdict est rendu par le même `tasks/harness.jl`.

| tâche | fait externe | web : verdict / julia / recherches / jetons / s | sans web : verdict / julia / recherches / jetons / s |
|---|---|---|---|
| t21 | — | **PASS** / 3 / 3 / 65837 / 224 | **PASS** / 3 / 0 / 56092 / 153 |
| t22 | OUI | **PASS** / 2 / 2 / 59276 / 170 | **PASS** / 4 / 0 / 73008 / 336 |
| t23 | — | **PASS** / 2 / 3 / 64346 / 205 | **PASS** / 3 / 0 / 56720 / 172 |
| t24 | OUI | **PASS** / 1 / 4 / 60237 / 149 | **PASS** / 2 / 0 / 52078 / 96 |
| t25 | — | **PASS** / 1 / 3 / 62661 / 201 | **PASS** / 2 / 0 / 56549 / 154 |
| t26 | — | **PASS** / 1 / 3 / 57802 / 141 | **PASS** / 4 / 0 / 60133 / 196 |
| t31 | — | **PASS** / 3 / 4 / 96182 / 538 | **PASS** / 1 / 0 / 64099 / 226 |
| t32 | OUI | **PASS** / 3 / 3 / 67460 / 250 | **PASS** / 2 / 0 / 56039 / 167 |
| t33 | — | **PASS** / 5 / 4 / 71751 / 288 | **PASS** / 1 / 0 / 55114 / 141 |
| t34 | OUI | **PASS** / 2 / 3 / 62130 / 217 | **PASS** / 2 / 0 / 53466 / 119 |
| t35 | — | **PASS** / 2 / 4 / 64799 / 196 | **PASS** / 4 / 0 / 56156 / 159 |
| t36 | — | **PASS** / 2 / 3 / 64670 / 231 | **PASS** / 1 / 0 / 53566 / 112 |
| **total** | 4 | **12/12** / 27 / 39 / 797151 / 2810 | **12/12** / 29 / 0 / 693020 / 2030 |

**24 sur 24.** Les deux bras réussissent les douze tâches, y compris les
**quatre à fait externe réel**. Le bras web a cherché — 39 recherches, sur
12 tâches sur 12 — et il a cherché **la bonne chose** : le tableau de
Dormand-Prince et les conventions de contrôle du pas pour t22, la table des
octets de préfixe MessagePack pour t24, `similar(::Broadcasted, ::Type)` et la
précédence des styles de diffusion pour t32, les douze premiers témoins de
Miller-Rabin et la borne de Sorenson-Webster pour t34. Ce sont mot pour mot les
quatre faits que 3.7 avait mesurés **absents des énoncés**.

Et ça n'a rien changé au résultat. Le bras sans web passe les quatre mêmes
tâches, sans une seule recherche. Ce que ça coûte est net : **+15,0 % de jetons,
+38,4 % de temps, 138 appels d'outils contre 97**, pour un gain de zéro case.

**Ce que ça corrige dans la lecture du corpus.** « Fait externe » est une
propriété **de l'énoncé** — le fait n'est pas écrit dedans, c'est mesuré — et
non une prédiction d'échec. Elle ne prédit un échec que pour un exécutant qui ne
**détient pas déjà** le fait. Un modèle de frontière détient les quatre. La
question que le corpus pose reste entière, mais elle ne se pose qu'au modèle
local : la campagne `t21..t36` sur Qwen3.8 est le seul endroit où l'axe web peut
encore séparer quelque chose.

**Ce que le bras sans web fait quand même, et qui compte.** Il exécute Julia :
29 lancements sur les douze tâches, contre 27 pour le bras web. C'est
exactement l'axe que 3.2 et 3.3 désignent comme décisif sur le modèle local — le
modèle local, lui, **n'exécute jamais son code en un coup et dit l'avoir
vérifié**. Ici l'axe est saturé : les vingt-quatre agents testent avant de
rendre, sans qu'on le leur demande. C'est le vrai écart avec dsh, et il est
déclaré ci-dessous, pas caché.

| | agent dsh, bras un coup | ces vingt-quatre agents |
|---|---|---|
| énoncé | `prompts/tNN.txt` + préambule | **le même, à l'octet près** |
| exécutions de Julia | aucun shim installé, donc non comptées | comptées, mais **auto-déclarées** dans `_journal.txt` |
| lecture hors du dossier | rien ne l'empêche techniquement | **interdite par consigne**, non par bac à sable |
| exécutant | Qwen3.8-27B servi localement | Opus 5 |
| délai | 900 s appliqué par le harnais | aucun |

La case remplie n'est donc **pas** « itératif » au sens de dsh : l'énoncé est
celui du bras un coup, seule la conduite a été itérative. Sur les quatre cases
du banc, 3.8 tient « un coup × sans web », 3.9 tient « énoncé un coup, exécutant
libre », dans les deux bras web. Reste vide : **un coup strict × avec web**.

**Et un obstacle matériel, mesuré.** `prompts_iter/` ne contient que
`t01..t16` — dans le dépôt **comme** dans la copie qui tourne. Les douze énoncés
`t21..t36` n'existent qu'en version un coup : aujourd'hui, dsh **ne peut pas**
courir le corpus dur en mode itératif. Écrire les douze énoncés itératifs est le
préalable, pas une option.

**Le défaut d'instrument trouvé au passage.** Le premier jugement annonçait
« 11 runs sur 12 ont cherché ». C'était faux : un des journaux portait une
**marque d'ordre d'octets** en tête, et le lecteur ouvrait en `utf-8` — la
marque reste collée à la première clé, qui devient illisible. La donnée
manquante était dans le **lecteur**, pas dans le run. Corrigé en `utf-8-sig`, le
compte passe à 12 sur 12. Lire l'instrument avant sa sortie, encore.

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
| 2026-08-22 | Palier expert `t21..t26` calibré 6/6 GOOD, 6/6 BAD (3.7). |
| 2026-08-22 | t31 : le bras known-BAD tombait par la même erreur que le bras known-GOOD — il ne mesurait rien. Énoncé corrigé, bras rendu à son défaut (2.7). |
| 2026-08-22 | Palier limite `t31..t36` calibré 6/6 GOOD, 6/6 BAD (3.7). |
| 2026-08-22 | Deux assouplissements du juge mesurés inutiles et annulés (2.8). |
| 2026-08-22 | Campagne figée 689 s par un agent orphelin : le délai ne tuait que le fils direct. Corrigé, et le contrôle d'échéance câblé dans `analyse.py` (1.5). |
| 2026-08-22 | Référence Claude Code sur les douze mêmes tâches, même juge : **12/12**, 11 en un coup, 0 recherche web (3.8). |
| 2026-08-22 | Campagne 1 du corpus dur terminée **90/90**, archivée ; campagne 2 (itérative) lancée derrière. |
| 2026-08-22 | **La copie du banc qui tourne n'est pas celle du dépôt** : elle est figée à 09:16 dans le répertoire de travail d'une session morte, sans le correctif de l'orphelin, sans les paliers `t21..t36`, et son `analyse.py` n'a aucun des trois contrôles câblés (1.6). |
| 2026-08-22 | Second bras known-GOOD `ref2/` câblé dans `--selftest` : **12/12**, et il tire — remis à sa première version de t35, il rend `!!! AVIS 5/6` (3.8). |
| 2026-08-22 | `web_fetch` n'est **pas** monté par le paquet de base (`fetch: false`) : le préambule du bras web demandait un outil inexistant. Corrigé, et 3.5 avec (3.5). |
| 2026-08-22 | L'étiquette « fait externe » n'avait jamais été vérifiée : sur les six tâches marquées, **deux impriment la réponse dans la question** (`t26`, `t33`) et ne peuvent rien mesurer sur l'axe web. Le corpus a quatre tâches à fait externe, pas six (3.7). |
| 2026-08-22 | **Vingt-quatre sous-agents neufs, même `TASK.md` à l'octet près que dsh** : web **12/12**, sans web **12/12** — y compris les quatre tâches à fait externe. Le web coûte +15,0 % de jetons et +38,4 % de temps pour zéro case gagnée (3.9). |
| 2026-08-22 | Le bras web a cherché **la bonne chose** sur les quatre tâches à fait externe (tableau Dormand-Prince, octets MessagePack, `similar(::Broadcasted, ::Type)`, témoins de Miller-Rabin) — et le bras sans web a réussi quand même (3.9). |
| 2026-08-22 | Une **marque d'ordre d'octets** en tête d'un journal rendait sa première clé illisible : le juge annonçait 11 runs sur 12 ayant cherché, la réalité était 12. Lecture en `utf-8-sig` (3.9). |
| 2026-08-22 | `prompts_iter/` ne contient que `t01..t16`, dépôt **et** copie qui tourne : le corpus dur `t21..t36` ne peut courir qu'en un coup sur dsh (3.9). |
| 2026-08-22 | **Seconde dorsale cablee** : FreeLLMAPI (routeur local, 16 fournisseurs gratuits, 380 modeles servis) monte dans dsh comme fournisseur `freellm`. Clef unifiee lue en base au lancement, jamais ecrite dans la configuration ; garde de lecture cable et **ses deux bras tires** (1.7). |
| 2026-08-22 | Le modele virtuel `auto` a **bascule sous la mesure** : appel temoin parti sur un fournisseur, revenu servi par DeepSeek-V4-Flash apres `key1=rate_limited`. Pour mesurer, epingler et lire `x-fallback-trail` (1.7). |
| 2026-08-22 | Les identifiants servis sont des **slugs courts** (`deepseek-v4-pro`) ; la forme longue `deepseek-ai/DeepSeek-V4-Pro` est ce que le routeur RENVOIE, et elle est absente de `/v1/models` (1.7). |
| 2026-08-22 | Le banc respecte `DSH_HOME` : deux campagnes tournent cote a cote au lieu de se reecrire les trois memes lignes de `settings.yaml`. Et chaque ligne de resultat porte desormais `provider` et `modele` (1.7). |
| 2026-08-22 | **Mur de quota mesure** : les credits HuggingFace gratuits sont a sec (`out_of_credits`, HTTP 402 sur deepseek-v4-pro), remise a zero ~24 h. Sur cinq modeles epingles, un seul repond avec outils **sans bascule** : `gemini-3.7-flash`. 7 runs FAIL archives comme mesure du mur (1.7). |

---

## Ce que le banc ne dit pas encore

- **Réussite à n plus grand.** Le plancher de bruit est de 2 sur 10. Pour
  trancher un écart de 1 sur 10, il faut soit des tâches assez dures pour que
  `off` décroche, soit assez de répétitions pour descendre le plancher sous 1.
  Les deux sont en cours.
- **Taux d'acceptation MTP par type de texte.** Le mécanisme de 2.4 est cohérent
  avec les débits mesurés mais n'a **pas** été ré-instrumenté ici. *Unverified.*
- **Tâches à phase de planification, avec et sans recherche web préalable.**
  Corpus écrit **et calibré** 12/12 GOOD, 12/12 BAD (3.7) ; bras web câblé et
  compté par run ; **plafond de référence mesuré 12/12** par Claude Code sur le
  même juge (3.8). Ce qui manque est la campagne elle-même : **aucun des douze
  énoncés n'a encore été soumis au modèle local**, ni avec ni sans recherche.
  **Bras web et sans web mesurés sur vingt-quatre sous-agents Claude, 12/12 des deux côtés (3.9)** : l'axe web ne sépare rien à ce niveau, il ne peut séparer que sur le modèle local. Elle attend que les deux campagnes du corpus dur libèrent la carte.

---

## Fichiers

Le banc lui-même vit dans `scripts/bench_julia_effort/` ; son `README.md` donne
le mode d'emploi. Les fenêtres de mesure sur le serveur sont dans
`docs/SPECDEC_4090_BENCH.md`.
