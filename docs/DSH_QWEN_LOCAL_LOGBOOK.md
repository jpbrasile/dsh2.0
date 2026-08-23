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

### 3.10 · Le plafond d'un banc gratuit n'est pas le débit, c'est le quota du jour

La campagne externe devait placer un point entre le Qwen local et la référence
Opus 5. Elle a rendu **1 PASS et 28 échecs**, et pas un seul de ces échecs ne
porte sur une tâche : ils portent tous sur un quota. C'est une mesure, pas un
raté — elle dit où est réellement le plafond de cette dorsale.

| modèle épinglé | ce qu'il a fait | comment il est mort |
|---|---|---|
| `deepseek-v4-pro` | 1 run témoin PASS (49,8 s) | `out_of_credits`, **HTTP 402** côté HuggingFace, remise à zéro annoncée le 23/08 à 12:59 |
| `gemini-3.7-flash` | **t21 PASS en 109,4 s** | 429 `rate_limit_exceeded` sur tous les runs suivants, « 1 route checked » |
| `gemini-3.6-flash` | rien | **502** amont, puis 429, refroidissement ~7 h |
| `nemotron-3-super-120b` | répond encore à la dernière sonde (1,2 s, sans bascule) | — |
| `glm-5.2`, `qwen3-coder-480b`, `deepseek-v4-flash`, `kimi-k3`, `llama-4-maverick`, `mimo-v2.5`, `ling-2.6-1t`, `gemini-2.5-flash` | rien | 429 dès la sonde, ou « no usable key configured » |

**Six modèles sur huit sondés étaient déjà morts**, et les deux vivants le sont
restés le temps d'un run. Le compte final : 29 runs lancés, **1 réussi**,
452 + 121 secondes de mur.

**Ce que ça règle sur la question « et si on parallélisait ? »** Le banc externe
tourne aujourd'hui en séquentiel, une tâche après l'autre. Il *pourrait* tourner
en parallèle — contrairement à la campagne locale, qui partage une seule carte
et ne doit jamais être découpée en tranches ; le routeur, lui, accepte
120 requêtes par minute. Mais **paralléliser ne ferait qu'atteindre le mur plus
vite** : le facteur limitant n'est pas le débit, c'est le plafond **journalier**
par fournisseur. Un run d'agent sur une tâche dure — plusieurs dizaines d'appels
à gros contexte — suffit à épuiser un modèle gratuit pour la journée. Douze
tâches en même temps auraient rendu les mêmes 429 en deux minutes au lieu de
huit.

**Le levier n'est donc pas la concurrence, c'est le nombre de clefs.** Trois
routes possibles, par ordre de coût :

1. **attendre la remise à zéro** (~23/08 13:00) et relancer sur un seul modèle
   épinglé — c'est la mesure propre, un exécutant, comparable d'un bout à
   l'autre ;
2. **ajouter des clefs gratuites** dans le tableau de bord FreeLLMAPI : c'est ce
   qui relève le plafond journalier, et c'est le seul geste qui change l'ordre
   de grandeur ;
3. **tourner sur des modèles DISTINCTS**, un run par modèle. Ça finit dans
   l'heure, mais chaque tâche est alors répondue par un exécutant différent : la
   campagne ne mesure plus un modèle, elle mesure un mélange. C'est une autre
   expérience, et elle n'est lisible que parce que chaque ligne porte désormais
   `provider` et `modele`.

**Le seul point de mesure réel qui en sort** : `t21` (matrice bande, stockage
LAPACK) réussie en 109 s par Gemini 3.7 Flash, sans recherche web et sans avoir
exécuté Julia. Une case sur vingt-quatre — c'est peu, mais c'est une case, et
elle est attribuée.

---

### 3.11 · Douze ouvriers en parallèle : ce que ça achète, et ce que ça casse

**Instrument.** `bench.py --par 12`, dorsale FreeLLMAPI en mode `auto`. Chaque
ouvrier a son propre accueil dsh (`DSH_HOME`), donc son propre `settings.yaml`,
ses propres sessions, **son propre port d'enregistreur**. 24 runs, corpus dur
t21..t36, deux bras, `medium`.

**Le port, pas le chemin.** Première tentative d'attribution : une voie dans
l'URL, `http://127.0.0.1:8020/w3/v1`. **Mesurée fausse** — le client dsh
normalise la `baseURL` et jette le chemin : 47 appels sur 47 sont arrivés sans
voie, avec un proxy pourtant correct (le même préfixe passe en `curl`). Le seul
discriminant qu'un client ne peut pas normaliser est le **port**. Vérifié à la
sonde : `PROXY_SLOT=7`, l'enregistrement porte `slot: 7`.

**Ce que ça achète.** 4 308 s de temps machine cumulé, rendus en ~20 min de mur
(second bras : 526 s du premier au dernier appel). Facteur ~3,5, borné par la
tâche la plus lente de chaque lot (609 s). 55 bascules de fournisseur sur les 24
runs : sans elles, la campagne serait morte au premier quota, comme la campagne
épinglée du même jour (29 lancements, 1 réussite).

**Ce que ça casse, et c'est le résultat principal.** En `auto`, le routeur sert
ce qui est libre — et sous charge parallèle, ce qui est libre est ce qui est
faible. Huit modèles différents ont répondu :

| modèle réellement servi | PASS |
|---|---|
| nemotron-3-ultra | **5/5** |
| agnes-2.5-flash | 2/4 |
| gemini-3.1-flash-lite | 1/3 |
| dots-3-note-preview | **1/8** |
| quatre autres | 0/4 |

Le bras « avec web » sort à 6/12 contre 3/12 pour « sans web ». **Cet écart n'est
pas un effet du web** : le bras avec web a tiré `nemotron-3-ultra` cinq fois, le
bras sans web zéro fois. En mode `auto`, **la comparaison entre bras n'est pas
interprétable** — c'est le tirage de l'exécutant qui domine, et seul le journal
du fil le montre. Un banc parallèle sans attribution aurait publié « la
recherche web double la réussite ».

**Et le même axe que partout ailleurs.** Sur les 24 runs, avec le shim désormais
posé dans les deux modes :

| | runs | PASS |
|---|---|---|
| a lancé Julia avant de rendre | 9 | **7 (78 %)** |
| ne l'a pas lancé | 15 | **2 (13 %)** |

**Défaut d'instrument réparé au passage.** Le shim n'était posé qu'en mode
itératif : en un coup, `BENCH_JULIA_LOG` n'existait pas, et `julia_runs` valait
0 **par construction** pour toute la population. Ce zéro avait été publié comme
un résultat (« les modèles frontière n'exécutent jamais Julia »). Calibré depuis
aux deux bras : shim dans le PATH, 1 ligne journalisée ; sans, 0.

### 3.12 · Épingler sur un routeur à quotas, c'est se priver de la seule chose qui le rend utilisable

**Ce qui a motivé l'essai.** En §3.11, `nemotron-3-ultra` sortait **5/5** — le seul
des huit modèles servis à n'avoir jamais échoué. Conclusion apparente : l'épingler
et l'axe web redevient mesurable.

**Ce que l'épinglage a mesuré.** Deux campagnes, 12 ouvriers puis 2 :

| régime | résultat | ce que dit le journal du fil |
|---|---|---|
| épinglé, 12 ouvriers | **0/12** | `All models exhausted: 2 routes checked (2 rate-limited or on cooldown)` |
| épinglé, 2 ouvriers | **2/24** | la plupart des runs : aucun appel abouti, mort en ~17 s |

**Et ce chiffre ne dit rien sur le modèle.** Une campagne tuée par le quota mesure
le quota. Le 2/24 n'est pas un verdict sur `nemotron-3-ultra` — pas plus que le 5/5
n'en était un. **Les deux sont des artefacts de file d'attente** : en mode `auto`,
le routeur ne tirait ce modèle que 5 fois sur 24 *parce que c'est tout ce que sa
file gratuite permet*. Le 5/5 était un artefact de **rareté**. Le seul énoncé
soutenable est : la file gratuite de `nemotron-3-ultra` ne tient pas ce banc.

**Le mécanisme, vérifié dans la documentation du routeur.** Sur 429/5xx/timeout, la
clé part en refroidissement et l'escalade peut aller jusqu'à une quarantaine de
24 h ; la requête est reprise sur **l'entrée suivante de la chaîne de repli**,
jusqu'à 20 tentatives. Une requête **épinglée n'a pas de chaîne** : 429, et l'agent
abandonne sans avoir rien écrit — d'où les douze `aucun solution.jl ecrit`.

**Ce qu'on aurait dû utiliser.** Le routeur n'a pas *un* mode auto mais **six
stratégies de classement** de la chaîne — `priority`, `balanced`, `smartest`,
`fastest`, `reliable`, `custom` — choisies **par requête** via `auto:<profil>`.
Le réglage global de cette installation est `balanced` (table `settings`).
`auto` nu prend « le modèle de plus haute priorité qui a une clé saine et de la
marge » : disponibilité, pas capacité. D'où les 8 runs sur 24 attribués à
`dots-3-note-preview` (1/8) en §3.11. **`auto:smartest` classe par capacité** et
garde la bascule — c'est le réglage correct pour cette dorsale, et l'épinglage
n'en est pas un.

### 3.13 · Un préfixe de chemin traversé par un shell MSYS n'est plus un chemin

**Instrument.** Campagne `stealth/ox-alpha` (OpenRouter, gratuit, 1 M de contexte,
déclare `tools` et `reasoning_effort`), routée par l'enregistreur en amont TLS.

Premier lancement : **quatre ouvriers morts en 1,7 s**, `PI_AI_ERROR: Invalid URL`.
La `baseURL` écrite dans la configuration de l'ouvrier était :

```
http://127.0.0.1:8050C:/Program Files/Git/api/v1
```

`BENCH_PAR_CHEMIN=/api/v1` a traversé Git Bash, qui **convertit toute valeur
d'environnement ressemblant à un chemin Unix en chemin Windows**. Même famille que
le heredoc qui mange les antislash : le canal transforme la valeur en silence, et la
panne ne nomme pas sa cause — quatre `Invalid URL` se relisent comme un défaut du
modèle ou de dsh.

**Réparé aux deux bouts.** Le banc prend désormais le préfixe **sans barre de
tête** (`api/v1`) — la forme ne ressemble plus à un chemin, donc rien ne la
convertit — et un garde refuse toute `baseURL` fabriquée portant une lettre de
lecteur, un espace ou un antislash. Le garde est **né câblé** : son appelant est
dans le même changement, `preparer_voies`.

**Son bras known-BAD a tiré avant qu'il ne serve, deux fois.**
Première version du motif : `[A-Za-z]:[/\]` sur l'URL entière — il matche
`http://` lui-même et refusait **tout**, y compris le known-GOOD. Corrigé en
ancrant sur l'hôte et le chemin séparément. Deuxième tir : `urlsplit(...).port`
**lève** `ValueError` sur une autorité abîmée (`8050C:`) au lieu de rendre `None`
— sans le `except`, le garde tuait la campagne avec une trace `urllib` au lieu du
message qui nomme la cause. Calibré depuis sur cinq URL, 2 PASSE / 3 REFUSE.

**Isolation des sorties, pas du code.** Deux campagnes lancées du même répertoire
écrivaient dans les mêmes espaces de travail et le même `resultats.jsonl` : la
seconde écrasait la solution que la première allait faire juger. La parade
évidente — copier le banc ailleurs — est exactement celle qui a coûté deux heures
le 22/08 (une campagne tournant depuis une copie figée où aucun correctif du jour
n'existait). `BENCH_ETIQUETTE` isole donc `runs/<étiquette>/` et
`resultats_<étiquette>.jsonl`, **jamais le code**.

### 3.14 · Deux campagnes qui partagent un répertoire ne partagent pas que des journaux

`BENCH_ETIQUETTE` isolait `runs/` et le fichier de résultats. Pas la racine des
ouvriers. Le 22/08, une campagne épinglée sur `stealth/ox-alpha` (OpenRouter en
direct, ports 8050-8053) et une campagne FreeLLMAPI en `auto:smartest` (douze
ouvriers, ports 8020-8031) se sont donc partagé `_par/w0..w3`.

Ce n'était pas seulement les journaux de fil qui se mélangeaient. `preparer_voies`
**écrit** un `settings.yaml` par ouvrier. La seconde campagne a donc basculé les
ouvriers 0 à 3 de la première sur le fournisseur `freellm`, **en pleine course**.
Trois runs épinglés (t22, t31, t36) ont été servis par nemotron-3-super,
mistral-small et laguna — et j'avais publié cela comme « OpenRouter bascule tout
seul ». Il ne basculait pas. Sa configuration avait été remplacée sous lui.

Puis, en nettoyant `_par/w*`, j'ai retiré leur configuration aux ouvriers encore
en vol : sept runs morts en 1,3 s sur `MISSING_CREDENTIAL`, une connexion coupée.

Les **verdicts** restaient justes — ils viennent des espaces de travail, qui
étaient bien isolés. Seule l'attribution était fausse. La leçon n'est pas
« isoler les journaux » mais : **un répertoire de travail partagé partage tout ce
qu'on y écrit, y compris ce qu'on n'avait pas prévu d'y écrire.**

Deux réparations, la seconde née câblée :

- La racine des ouvriers porte l'étiquette. Calibré : deux étiquettes rendent
  deux journaux distincts ; l'ancien code n'en rendait qu'un.
- Garde `_ports_libres`, appelée depuis `lancer_enregistreurs` dans le même
  commit : refuse de démarrer si un port d'enregistreur est déjà en écoute.
  Sans elle, `_ecoute` répond vrai sur le proxy de l'**autre** campagne et les
  appels sont journalisés sous le mauvais nom. Calibration 5/5 — trois bras
  known-BAD (deux campagnes réellement en cours, un port tenu par le test),
  deux known-GOOD. Fatale d'emblée : bras known-BAD **plus** une prise réelle.

### 3.15 · Le routeur ne sert que ce qu'il a en catalogue — et il le dit

`stealth/ox-alpha` demandé au routeur FreeLLMAPI sous quatre formes de nom :
quatre fois 404, avec un message explicite, « is not in the catalog ». La clé de
plateforme `openrouter` était pourtant saine et le modèle bien vivant en amont.
**Le catalogue est la porte, pas la clé.**

Ce qui m'avait fait croire l'inverse la veille — « `auto:smartest` sert de
l'ox-alpha » — était le même artefact de journal partagé que §3.14.

Le catalogue est une table SQLite de l'application de bureau. Deux lignes
ajoutées, et **le routeur les a prises à chaud, sans redémarrage** :

| plateforme | identifiant | vérifié par |
|---|---|---|
| `openrouter` | `stealth/ox-alpha` | `X-Routed-Via: openrouter/stealth/ox-alpha` |
| `opencode` | `x-preview-f-free` | `X-Routed-Via: opencode/x-preview-f-free` |

`X-Routed-Via` est le champ décisif, et le corps ne le remplace pas : une demande
`x-preview-f-free` a répondu 200 en se **nommant** `stealth/ox-alpha`. Sur le seul
corps, impossible de dire si OpenCode Zen renvoyait l'identifiant canonique ou si
le routeur avait basculé de plateforme. Il avait basculé — et la bascule inverse
a été observée ensuite. Les deux routes vivent : même modèle, deux files.

Relevé du catalogue amont, lu par l'API OpenRouter et non par une page : 421
modèles annoncés, 22 à coût nul, **19 à coût nul et outillés**. Le routeur en
avait déjà 17. Le critère retenu est « coût nul ET outils », pas « les plus
utilisés » : le classement d'usage d'OpenRouter mesure du volume, et un modèle
gratuit y monte mécaniquement.

### 3.16 · Ce que mesure le compteur `julia=`, et le seul écart qui compte

`julia=` compte les fois où **l'agent** a lancé Julia pendant son run, via un
substitut placé en tête du `PATH`. `julia=0` ne dit pas « le code est faux ». Il
dit : *l'agent a rendu sa solution sans jamais l'exécuter.*

Bras sans web, 12 tâches du corpus expert+limite, même banc, même jeu d'outils
(25 outils offerts des deux côtés), campagnes simultanées :

| | `auto:smartest` | ox-alpha épinglé |
|---|---|---|
| réussites | 4/12 | **9/12** |
| exécutions de Julia | 7 | **104** |
| runs n'ayant jamais lancé Julia | **11/12** | **0/12** |
| tours d'agent par tâche | 3,6 (de 1 à 8) | **17,3** (de 8 à 32) |
| modèle dominant | nemotron-3-super, 33 % | lui-même, **100 %** |

Un appel d'outil relance un tour : le nombre d'appels **est** la longueur de la
boucle. Ox-alpha lit, écrit, exécute, lit l'erreur, corrige. Smartest écrit et se
déclare fini — sur t31, t33 et t35, en **un seul tour**, sans même produire de
fichier.

Ce n'est donc pas dsh qui refuse de lancer Julia. **Dsh n'a jamais reçu l'ordre
de le lancer.**

Conséquence sur le banc, qui compte plus que le classement : tant qu'une dorsale
ne boucle pas, l'axe « avec ou sans recherche web » **ne mesure rien** chez elle.
On ne compare pas deux stratégies de recherche, on compare un agent qui itère à
un agent qui fait un tour.

**Hypothèse avancée puis retirée** : j'ai cru voir le préambule web pousser ces
modèles à boucler (le bras web montrait 20 exécutions de Julia contre 7). Une
fois retirés les runs touchés par ox-alpha — arrivé dans le tirage parce que je
venais de l'ajouter au catalogue en pleine campagne — il reste 5 exécutions sur
8 runs contre 7 sur 12. L'effet disparaît. C'était ox-alpha, pas le préambule.

Et le piège de lecture qui allait avec, noté parce qu'il resservira : les runs
touchés par ox-alpha étaient les runs **longs** (41, 30 et 26 appels). Plus un
agent boucle, plus il appelle, donc plus il a de chances de tomber sur un modèle
donné dans la chaîne de repli. La participation peut être la **conséquence** de
la boucle et non sa cause. Ce bras-là ne pouvait pas trancher ; seule une
campagne épinglée le peut.

### 3.17 — Le levier 1 n'a pas mesuré une route, il a mesuré un quota

**Instrument :** `_par/oxalpha/w*/wire.jsonl` et `_par/oxviafree/w*/wire.jsonl`,
champ `status` de chaque appel ; `resultats_oxalpha.jsonl`,
`resultats_oxviafree.jsonl`.

Le levier 1 épinglait ox-alpha **à travers FreeLLMAPI** au lieu de l'appeler en
direct, pour profiter de la mutualisation des 16 plateformes. Les verdicts, à
première lecture, condamnent la route :

| ox-alpha | sans web | avec web | julia total | runs à julia=0 |
|---|---|---|---|---|
| **direct** | 9/12 | 11/12 | 104 / 66 | 0/12 et 0/12 |
| **via FreeLLMAPI** | 5/12 | 4/12 | 46 / 6 | 6/12 et 9/12 |

Même modèle des deux côtés — `servis` dit `ox-alpha` sur les 420 appels. La
tentation est de conclure que la route dégrade le modèle, et la signature
`julia=0` semble le confirmer : l'agent cesse d'exécuter son code.

**Le fil dit autre chose.** Sur 159 appels passés par le routeur, **108 rendent
429** et 43 seulement rendent 200 ; en direct, 196 appels sur 196 rendent 200.
Les deux tiers des appels n'ont jamais eu lieu. `julia=0` n'est pas un modèle
qui renonce à exécuter, c'est un agent coupé au milieu de sa boucle.

Et le fil écarte l'explication qu'on aurait retenue par défaut : les outils
passent **à l'identique**. `n_tools = 25` sur 184 appels en direct, sur 147 via
le routeur. Le routeur ne rabote pas les définitions d'outils.

**Ce que le levier 1 établit donc :** rien sur la qualité de la route, et un
plafond dur sur son usage — la clef OpenRouter du routeur ne tient pas 6
ouvriers en parallèle. La campagne suivante reste sur l'épinglage direct. La
question ouverte n'est pas « la route est-elle bonne » mais « à quel
parallélisme le quota tient-il », et elle se mesure en faisant varier `--par`.

**La forme, une fois de plus :** deux nombres comparables produits par deux
instruments qui ne l'étaient pas. 5/12 contre 9/12 se lit comme un écart de
compétence tant qu'on ne regarde pas ce qui est parti sur le fil.

### 3.18 — `web_search` n'est pas une recherche : c'est un appel à un autre modèle

**Instrument :** journal de session dsh du run `localv1/r01/off/t21`, décompressé
(`session.jsonl.zstd`), enregistrements `type = "web/deepseek-search-llm-request"`.

Un run local a rendu `PASS 54,0 s julia=0 web=11`. Trois nombres invraisemblables
ensemble : onze recherches, aucune exécution, cinquante-quatre secondes sur un
27B local. Le journal explique les trois, et aucune des explications n'était
celle qu'on attendait.

**Ce que `web_search` fait réellement.** Chaque requête part vers
`https://api.deepseek.com/anthropic/v1/messages`, corps `{"model":
"deepseek-v4-flash", ...}`, avec le prompt *« Perform a web search for the
query: … »*. L'outil « recherche web » de dsh est un **appel à un second
modèle**, distant. Conséquence directe : **le bras « avec web » d'une campagne
locale n'est pas local.** Une partie du raisonnement est faite ailleurs, par un
autre modèle, et rien dans la colonne `web=` ne le disait.

**Pourquoi 54 s.** Les trois requêtes du premier appel partent à la même
milliseconde (`seq` 129, 130, 131, même `time`) : elles sont émises en parallèle
et servies par un modèle distant rapide. Le modèle local n'a fait que 7 étapes.

**Pourquoi `web=11` était faux.** Le compteur retenait tout enregistrement dont
le `type` contient `tool`. Le journal en a trois sortes : `tool/call`,
`tool/result` et `tool-call-chunks`. Décompte sur ce run :

| type retenu | nombre |
|---|---|
| `tool-call-chunks` (fragments de flux) | 9 |
| `tool/call` (vrais appels) | 2 |
| **total rendu par le banc** | **11** |

Deux appels, contenant cinq requêtes. Le compteur additionnait les fragments du
flux aux appels — et le facteur n'est pas constant, il dépend du bavardage du
flux. **Deux colonnes `web=` de deux runs n'étaient donc pas comparables**, ce
qui est plus grave que d'être faux d'un facteur fixe. Corrigé : seul `tool/call`
compte, vérifié sur le même run, 11 → 2.

**Et le troisième défaut, celui qui rendait l'enquête nécessaire.** `--par 1`
sautait `preparer_voies` : pas d'enregistreur, pas de journal de fil, et
`set_default` écrivait dans le **vrai** `~/.dsh/settings.yaml`. La campagne
locale tournait sans instrument — impossible de dire quel modèle avait répondu.
Un ouvrier est maintenant un *pool d'un*, avec son port, son journal et sa
configuration isolée, comme les autres.

**La forme.** Trois nombres invraisemblables ensemble valaient mieux qu'un
seul : un nombre isolé se rationalise, un triplet incohérent force à ouvrir
l'instrument. Ici il en cachait trois défauts, dont un — la délégation à un
modèle distant — qui change ce que « banc local » veut dire.

### 3.19 — La recherche différée ne s'est jamais déclenchée : 12 runs, 0 appel web

**Instrument :** `resultats_v3web.jsonl` et `resultats_oxalpha.jsonl` ;
`_par/*/w*/wire.jsonl` pour l'attribution. Instrument égal entre les trois bras
— même fournisseur (`openrouter-banc`), même modèle (`stealth/ox-alpha`), même
effort `medium`, même corpus expert+limite, `--par 4`. Seul le préambule change.

| bras | PASS | exécutions Julia | appels web | médiane |
|---|---|---|---|---|
| sans web | 9/12 | 104 | 0 | 173 s |
| web V1 — cherche avant d'écrire | 11/12 | 66 | 21 * | 184 s |
| **web V3 — cherche après deux échecs** | **10/12** | **92** | **0** | 303 s |

\* compteur d'avant la correction §3.18 : c'est une **borne supérieure**, pas
une mesure. Un 0 reste un 0.

**Le résultat n'est pas 10/12. Le résultat est 0.** Sur douze runs, le modèle
ne s'est jamais jugé bloqué deux fois de suite, donc il n'a jamais cherché. Le
bras V3 n'est pas une condition intermédiaire entre « sans web » et « V1 » : il
**est** le bras sans web, avec un préambule plus long. Ses 10/12 contre 9/12 sont
un écart d'une tâche sur douze, en une répétition — du bruit.

**Et les deux échecs sont précisément les cas où la recherche aurait dû partir.**
t32 échoue sur une `MethodError` après 10 exécutions ; t31 tourne encore au
plafond de 900 s après 16 exécutions. Deux situations où le modèle boucle sur le
même point sans se déclarer bloqué.

**Ce que ça dit de la consigne, et pas du modèle.** « Tu es bloqué quand le même
point t'a défait deux fois » est un critère que le modèle s'applique à
lui-même. Un modèle qui progresse à chaque tour — nouvelle erreur, nouveau
correctif — ne se déclare jamais bloqué, même quand il tourne en rond à
l'échelle de la tâche. **Un déclencheur auto-évalué ne se déclenche pas.**

**Conséquence de conception.** Pour mesurer l'idée — chercher tard plutôt que
tôt — le déclencheur doit être **mécanique et extérieur** : le banc compte les
exécutions échouées et injecte la consigne de recherche après la deuxième. Cela
demande le mode itératif, pas le mode one-shot. C'est le prochain bras à
construire ; V3 tel quel ne mesure pas la question qu'il pose.

### §3.20 — `julia=0` disait deux choses opposées, et le contrôle qui l'a prouvé a d'abord refusé un shim sain

**Déclencheur : une question de l'utilisateur** — « julia 0 ça bugge ». Sur la
campagne locale, t22 affichait `julia=0 web=26` après 900 s de plafond.

**Mesure.** Le zéro était **vrai pour ce run** : la session n'appelle que
`read` ×1 et `web_search` ×26, aucun outil d'exécution. Mais le journal du
shim était **absent**, et le code rendait 0 dans les deux cas :

| état du journal | ce que ça veut dire | ce que le compteur rendait |
|---|---|---|
| présent, 0 ligne | l'agent n'a rien exécuté | `0` |
| **absent** | **le shim n'a jamais été appelé — l'instrument manquait** | `0` |

La seconde panne s'était déjà produite ici, en mode itératif : `BENCH_JULIA_LOG`
n'existait pas, le shim n'était pas dans le PATH, et `julia_runs` valait 0 pour
**toute la population**. Cela s'était lu comme un résultat.

**Réparation.** `compter_julia` rend `-1` quand il n'y a pas eu de mesure et
l'affichage la note `n/a` — la convention déjà en place pour `compter_web`
(§3.18). Une absence de mesure n'est pas un zéro, et l'analyse doit pouvoir
les distinguer.

**Le contrôle, câblé à la naissance.** `preparer_shim` tourne au démarrage de
chaque campagne ; il tire désormais un `julia --version` **à travers le PATH de
l'agent** et exige qu'une ligne exactement atterrisse dans le journal. Sinon la
campagne est refusée. Sans lui, toutes les colonnes `julia=` d'une campagne
peuvent valoir 0 sans qu'aucune ne soit fausse à la lecture.

**Et son premier bras known-GOOD a REFUSÉ un shim sain.** C'est le contrôle qui
était faux, pas le shim : appelé en liste avec `shell=False`, `CreateProcess`
résout le nom avec le PATH du **processus parent** — pas celui qu'on lui
passe — et ne sait pas lancer un `.cmd`. Le contrôle mesurait le `julia` du
banc et n'avait jamais touché le shim. Corrigé en passant par le shell, la
forme qu'emploie réellement l'agent.

> Un contrôle qui refuse au premier tir apprend davantage qu'un contrôle qui
> passe : le premier vert est ce qu'il produira de moins informatif.

**Bras known-BAD tenus**, tous deux rendant `n/a` et refusant la campagne :
shim présent mais qui n'écrit pas son journal ; shim absent du PATH — la panne
réelle du mode itératif.

**Instrument :** `bench.py::compter_julia`, `fj`, et le bloc de contrôle de
`preparer_shim`. Commit `af3ae8d3`.

### §3.21 — Le déclencheur passe des tours aux exécutions, et les recherches sont plafonnées

§3.19 avait conclu qu'un déclencheur auto-évalué ne se déclenche pas, et que le
banc devait compter lui-même. Restait à choisir **ce** qu'il compte. La première
version comptait les **tours**. La campagne locale a montré pourquoi c'est faux :

| tâche | exécutions Julia | appels web | verdict |
|---|---|---|---|
| t22 | **0** | **26** (35 requêtes) | plafond 900 s |
| t24 | **0** | **21** | échec |
| t25 | 0 | 1 | PASS |

**Un tour peut se terminer sans aucune tentative.** t22 a brûlé 900 s en
cherchant, sans lancer Julia une seule fois. Un seuil en tours aurait compté ce
tour comme un essai infructueux alors que **rien n'avait été essayé**. Le seuil
est donc en **exécutions** (`--web-apres-julia`, 2 par défaut) : il compte des
tentatives réelles.

**Deux plafonds, pas un.** Le banc s'arrête à `--max-rech` recherches par run
(2 par défaut). Et le mode boucle a son propre préambule, qui **dissuade** le
modèle de chercher : c'est le banc qui cherche, au moment qu'il choisit et sur
la requête qu'il construit. Le compteur `appels_web` reste lu — un modèle qui
cherche quand même se voit ; la consigne n'est pas supposée respectée.

**La branche d'injection a enfin été parcourue.** Le fixture de bout en bout
était passé au premier tour (`tours=1 rech=0`) : la branche n'avait jamais rien
construit, et un chemin de repli jamais parcouru échoue en position permissive.
`fixture_injection.py` rejoue la construction sur un vrai message de juge, écrit
`TASK.md` comme la boucle l'écrit, et **relit le fichier** : la requête garde le
type d'erreur et les mots de l'assertion, les trois URL sont dans ce que l'agent
lit. Deux bras known-BAD : sans recherche aucun extrait ne se glisse ; le
plafond bloque à deux.

**Un cran de fixture a été écrit puis retiré.** Il forçait les N premiers tours
à échouer pour parcourir la branche — mais son propre message d'échec devait
être exclu de la recherche (sinon la requête interrogeait le banc), donc il
forçait un tour **sans** injection : il ne parcourait pas ce qu'il prétendait
parcourir. Le fixture direct prouve la même chose sans toucher à la logique de
décision du banc.

**Instrument :** `bench.py::un_run_boucle`, `PREAMBULE_BOUCLE`,
`fixture_injection.py`. Commit `bff4e3f3`.

### §3.22 — La recherche du banc a injecté un blog de mots croisés, et le score l'a validée

**Ce qui est arrivé.** Boucle locale, t24, tour 2, après 42 exécutions : le banc
cherche et colle dans l'énoncé du tour suivant

```
requête : Julia check: LoadError: AssertionError: float64 gros-boutiste | in expression starting at
   - https://github.com/JuliaLang/julia/issues
   - https://connectionssports.com/blog/nyt-connections-words-meaning-august-20-2026
   - https://translate.google.com/
```

**Le run a réussi au tour 3.** Lu par le score seul — « une recherche, puis
PASS » — cette injection passait pour de l'aide.

**La cause n'était pas la requête.** Rejouée telle quelle, la page reçue ne
contient **aucune** classe de résultat, et porte les marqueurs `anomaly`,
`challenge`, « Unfortunately, bots use DuckDuckGo too », avec un canonical vers
la page d'accueil. **Le moteur nous avait bloqués comme robot.** L'analyseur a
lu les liens de *cette page-là* — Google Traduction, Coach, le festival de
Sundance — comme des résultats. Aucune recherche n'avait eu lieu ; le banc a
fait comme si.

> Troisième fois dans la même journée qu'une **absence de mesure est rendue
> comme un résultat**, après `julia=0` (§3.20) et `rech=1` (§3.21). Les trois
> fois, le nombre était lisible, plausible, et faux par construction.

**Réparation, en deux temps.** D'abord un refus explicite : le moteur rend
`(résultats, état)` et un blocage donne une liste **vide** plus l'état `bloque`.
Puis l'abandon du grattage : sans clef, on ne peut distinguer un blocage d'un
résultat qu'en lisant le HTML du bloqueur — course perdue à chaque changement
de page.

**Ce qui l'a remplacé existait déjà dans le dépôt** : les étages de
`.opencode/mcp/web_search.py`, mesurés ailleurs. Ordre retenu : **Z.AI
`web_search_prime`** (gratuit sur l'abonnement, résultats bruts) puis
**OpenRouter** (payé, il fait résumer un modèle par-dessus le même index Exa).
Le banc les réutilise au lieu d'en refaire une version à lui.

| message d'échec réel | ce que le nouvel étage rend |
|---|---|
| `AssertionError: float64 gros-boutiste` | StackOverflow-Julia · docs Julia · jlHub |
| `MethodError: no method matching similar` | **JuliaLang/julia#34661** (l'erreur exacte) · #31426 · discourse |
| `les négatifs sortent avant les positifs` | discourse **« Negative zeros and sorting »** |

**Deux faits que l'instrument porte désormais lui-même.** Z.AI répond
`Insufficient balance or no resource package` : c'est l'étage **payant** qui
sert, entre 27 et 107 s par recherche. L'état enregistré n'est donc pas
`openrouter` mais `openrouter (replis : zai: …)` — sans quoi un repli se lit
comme un choix, et le journal laisse croire que la recherche est gratuite.

**Le filtre a dû être resserré deux fois.** Un résultat n'est retenu que s'il
nomme Julia, ou vient d'un domaine propre à Julia. Un hébergeur générique ne
suffit pas : le charabia `xqzptr vlmnk wwzz qqjj` ramène `github.com/WWZZ` — un
compte au hasard — et deux pages sur un rançongiciel. Tant que `github.com`
figurait dans les sources acceptées, le compte au hasard passait le filtre.
Les écartés sont **enregistrés à côté des retenus** : un filtre qui jette sans
le dire remplace un défaut visible par un défaut invisible.

**Instrument :** `bench.py::recherche_basique`, `_pertinent`, `_etages` ;
`fixture_injection.py` §7 et §8, tenus sur les cinq résultats réels.
Commits `a7284afe`, `3e3a346f`.

### §3.23 — Sur le corpus difficile, la relance débloque un exercice que la tentative unique ne débloque pas

**Instrument égal :** même modèle (`stealth/ox-alpha`, effort `medium`), même
correcteur, même corpus t31–t36, `--par 3`. Une seule différence : une
tentative contre trois.

| bras | PASS | détail |
|---|---|---|
| une seule tentative | **5/6** | t31 meurt au plafond de 900 s après 9 exécutions |
| **boucle du banc** | **6/6** | t31 passe au **tour 2**, 11 exécutions |

**Ce n'est pas la recherche qui l'a débloqué.** Le tour 1 de t31 échoue sur
`AssertionError: derivee d'une constante` ; la recherche part et injecte trois
vraies pages Julia — `julia#27770`, `PackageCompiler.jl#277`, `PETSc.jl#176` —
dont **aucune ne parle de dérivée d'une constante**. Le moteur a accroché
« AssertionError » et « Julia », pas le fond : la requête est en français,
l'index ne l'est pas.

> Piège sous sa forme la plus convaincante : un vrai déclenchement, de vraies
> sources, un vrai succès derrière. Le score seul aurait crédité la recherche.

**Le bras qui tranche** est la même boucle sans recherche. S'il rend 6/6, le
gain entier vient de la relance, et l'apport de la recherche est nul sur ce
corpus — résultat utile, pas échec.

**Instrument :** `resultats_dur_uncoup.jsonl`, `resultats_dur_boucle.jsonl`,
`resultats_dur_bcl_noweb.jsonl`.

### §3.24 — Un tour coupé n'a pas été jugé, et le banc lui répondait comme s'il l'avait été

Sur t31 répété, un run sans recherche a vu ses **trois** tours tomber sur le
délai de 600 s. Voici, mot pour mot, ce que le tour 3 a lu dans son énoncé :

```
HARNESS FEEDBACK -- attempt 2 failed.

The checker ran your solution.jl and reported:

    timeout tour 600s

Already tried, and still failing -- do not repeat these:
  - attempt 1: timeout tour 600s

THIS IS THE SAME FAILURE AS ATTEMPT 1. Your last change did
not affect it. Do not adjust the same line again -- change
your approach, or test a smaller case first to locate it.
```

Trois affirmations, trois faussetés. Le vérificateur n'a **pas** lancé la
solution — il n'a jamais tourné. Rien n'a « encore échoué », puisque rien n'a
été jugé. Et le dernier correctif n'a pas « été sans effet » : personne ne l'a
regardé. Le banc poussait un modèle à abandonner une approche qu'aucun juge
n'avait évaluée.

Pendant ces trois tours, le journal du shim comptait **25 exécutions de
Julia**, la dernière sur le script de débogage écrit par l'agent lui-même. Il
manquait de temps, pas d'idées — et le seul message qui lui parvenait lui
disait le contraire.

> **Quatrième instance de la même forme cette semaine.** `julia=0` pour un
> journal absent (§3.20), `rech=1` pour un refus enregistré (§3.21), dix
> « résultats » moissonnés sur une page de blocage (§3.22), et maintenant un
> verdict annoncé là où aucun juge n'a tourné. À chaque fois, une **absence de
> mesure rendue comme un résultat** — jamais une valeur fausse, toujours une
> valeur là où il ne devait rien y avoir.

**Ce qui change.** Le tour coupé a désormais sa propre tête : la coupure est
nommée, l'absence de verdict est dite explicitement (« nothing here says your
approach is wrong »), et ce qui est transmis vient de l'instrument — nombre
d'exécutions et **dernière commande julia lancée**, lus dans le journal du
shim. Journal absent ⇒ aucun compte affirmé. Zéro exécution est dit comme un
signal, pas comme un blanc. En amont, l'historique étiquette une coupure au
lieu de la ranger parmi les essais qui ratent, et la désignation de répétition
ne tire plus dessus : deux coupures partagent la même empreinte sans être deux
fois la même erreur.

**Combien de tours étaient concernés.** 12 tours coupés sur 58 joués (21 %) et
**7 runs sur 34 perdent leur premier tour** — celui dont le successeur ne
recevait, jusque-là, qu'un faux verdict. Réserve : 5 de ces 12 coupures
viennent du seul bras local, où la lenteur du modèle domine ; hors bras local,
7 coupures sur 29 runs, dont 4 au premier tour.

**Ce qui reste non mesuré.** Que ce message-là change une issue. La campagne en
cours tourne sur le code d'avant ; la comparaison demandera une reprise. Ce qui
est vérifié est le contenu du message, par dix bras de fixture dont quatre
known-BAD — dont celui qui exige que la phrase « The checker ran your
solution.jl » ait disparu du cas coupé.

**Instrument :** `scripts/bench_julia_effort/fixture_injection.py` (§9bis),
la section « tours coupés par le délai » de `analyse.py`, et l'énoncé conservé
`runs/t31_noweb/r02/medium/t31/TASK.md`.

### §3.25 — Le bras « avec recherche » a gagné 3–1 en ne cherchant qu'une seule fois

Six runs sur t31, énoncé corrigé, mêmes réglages :

```
  t31b_web   r1 PASS [CCP] rech=0    r2 PASS [FP] rech=1    r3 PASS [CCP] rech=0
  t31b_noweb r1 FAIL [CFC] rech=0    r2 FAIL [CCC] rech=0   r3 PASS [FCP] rech=0
  (P=passé  F=jugé et raté  C=coupé au délai, jamais jugé)
```

Trois sur trois contre un sur trois — et **une seule recherche sur les trois
runs**. Les deux autres réussites se sont faites avec zéro. L'écart ne peut
donc pas être attribué à l'information injectée : dans deux cas sur trois, il
n'y en a pas eu.

Ce qui distingue alors ces runs est une **phrase du préambule**, présente dans
le seul bras web :

> *If you get stuck, the harness runs one for you and puts the excerpts in the
> next attempt statement.*

Le bras « avec recherche » est aussi le bras à qui on a dit **qu'un secours
viendrait**. L'hypothèse qui reste debout après ces six runs n'est plus
« chercher aide » mais « savoir qu'on peut être aidé change la façon de
dépenser son temps ». Elle se teste, et pas cher : il suffit de donner la
phrase sans jamais fournir la recherche.

> **Ce que la comparaison a coûté avant d'être lisible.** Le préambule de
> boucle n'allait qu'au bras avec recherche : le bras sans ne savait même pas
> qu'il aurait plusieurs tentatives. Une comparaison publiée a dû être retirée
> à la main. Depuis, chaque run enregistre l'empreinte de l'énoncé reçu, et
> `analyse.py --comparer` affiche l'avertissement de provenance **avant** le
> score.

**Le budget mord plus fort que l'information.** Sur les 17 tours joués, **10
n'ont reçu aucun verdict** — coupés à 10 minutes. Un run n'a été jugé aucune
fois sur ses trois tours, avec 30 exécutions de Julia derrière : il travaillait,
il n'avait pas le temps. La mesure suivante est donc le budget à somme
constante — 3 tours de 600 s contre 2 tours de 900 s — et non un axe de plus.

**Ce que le message corrigé a changé, et ce qu'il n'a pas changé.** Il n'a pas
réduit les coupures (4 tours sur 8 dans le bras web, contre 1 sur 7 avant). Il
a changé leur coût : deux runs se sont relevés de **deux coupures
consécutives**, cas qui ne s'était produit aucune fois auparavant, quand le
seul run à trois coupures n'était jamais revenu. Mais il ne suffit pas — un
`C C C` a de nouveau eu lieu, avec le bon message sous les yeux.

**Instrument :** `resultats_t31b_web.jsonl`, `resultats_t31b_noweb.jsonl`,
`analyse.py --comparer`, et la vérification au codepoint que `bench.py` n'a
changé entre les deux bras que par l'ajout de l'empreinte (`git diff
f690a051..8dd928bb`).

### §3.26 — Context7 : 1 requête sur 6, et la raison est structurelle, pas technique

Le banc paie OpenRouter pour chercher (Z.AI est à sec) et attend **27 à 107 s**
par requête. Context7 répond en **0,5 s**, gratuitement, sans clé, et ne peut
pas servir une page de blocage — le mode d'échec le plus cher rencontré ici
(§3.22). La question méritait d'être posée avec des chiffres.

**Rejeu des six requêtes réellement parties** du banc, critère déclaré avant la
mesure : le terme qui **nomme le correctif**, pas celui qui nomme le sujet.
« Dual » apparaît dans toute la doc de ForwardDiff et ne discrimine rien ;
« tag » nomme la réparation de la confusion de perturbation.

```
  1. float64 gros-boutiste            attendu bswap/ntoh/endian   -> RIEN
  2. derivee d'une constante          attendu partials/seed       -> RIEN
  3. confusion de perturbation        attendu tag/nested          -> RIEN
  4. has no field `partial`           attendu partials            -> RIEN
  5. ^(::Dual, ::Int64) is ambiguous  attendu ambigu              -> ambigu
  6. no method matching partial       attendu partials            -> RIEN
```

**Une sur six.** Et deux requêtes ont résolu vers des bibliothèques absurdes —
`umicro/uview1.0-doc`, `kunchenguid/no-mistakes` : comme le moteur de §3.22,
l'API de résolution rend toujours quelque chose, même pour un message d'erreur
qui ne nomme aucune bibliothèque.

**L'instrument a été disculpé avant de conclure.** L'étape de résolution est
une invention du rejeu ; le corpus interdit les paquets (« Use only Julia Base
»), donc la bonne bibliothèque est connue d'avance. Variante B, bibliothèque
**fixée** à `julialang/julia` : toujours **1 sur 6**. Puis lecture à l'œil des
deux cas décisifs, pour vérifier que le comptage par termes n'était pas
aveugle : sur la confusion de perturbation il rend des bizarreries de macros et
une note de `HISTORY.md` ; sur `no method matching partial`, la section du
manuel qui explique **ce qu'est** une `MethodError`. Le critère voyait juste.

**La raison est structurelle.** Context7 indexe la *documentation de
bibliothèques*. Nos requêtes sont des erreurs d'exécution dans du code que le
modèle vient d'écrire, dans un corpus qui **interdit les bibliothèques**. Le
seul succès (#5) est précisément le cas où l'erreur porte sur un mécanisme
documenté du langage lui-même. Ce qui a réellement débloqué les runs, à
l'inverse, ce sont un fil Discourse et un ticket GitHub (§3.25) — deux sources
que Context7 n'indexe pas.

> **Ce n'est pas un défaut de Context7, c'est un désaccord de vocation.** Sur
> un corpus dont les tâches *utilisent* des paquets, il serait meilleur que ce
> qu'on a sur les trois axes à la fois : gratuit, cinquante fois plus rapide,
> et incapable de servir du charabia. Sur celui-ci, il n'a rien à dire.

**Instrument :** `scripts/bench_julia_effort/rejeu_context7.py`,
`_requetes_reelles.json` (les six requêtes extraites des campagnes),
`_rejeu_context7.json`.

### §3.27 — Vingt-quatre tours n'ont jamais atteint le modèle, et le banc les comptait comme des échecs

Sixième fois que la même forme passe : **une absence rendue comme un résultat.**
Quand la dorsale coupe, `dsh` meurt en deux lignes. Le banc, lui, regarde ce
qui reste au sol et écrit un verdict parfaitement crédible.

Deux façons de mentir, les deux mesurées le 23/08 :

| ce que le banc a écrit | ce qui s'est passé |
|---|---|
| `FAIL — aucun solution.jl ecrit` | le modèle n'a jamais reçu la question (`t31d_promesse` r2 : **12 appels modèle**, contre 36 à 66 dans le témoin) |
| `FAIL — MethodError: ^(::Dual, ::Int64) is ambiguous` | le juge a tourné sur le **brouillon que le modèle était en train de remplacer** (`t31_web` r3 tour 2, coupé net sur la phrase *« Fixing both files: »*) |

La seconde est la dangereuse : le verdict porte une vraie erreur Julia, d'un
vrai fichier, produite par un vrai juge. Rien ne dépasse.

**La liste nominative**, sur toutes les campagnes du dépôt — 24 tours, 5 causes :

```
  RATE_LIMIT 12 · MISSING_CREDENTIAL 7 · QUOTA 3 · PI_AI_ERROR 1 · INVALID_REQUEST 1
```

Deux campagnes entières n'étaient donc pas des mesures : **`oxviafree`**
(10 tâches, 10 tours morts — 100 %) et **`runs/r01`** (7 tâches lancées sans
identifiant valide).

**Ce que le garde a lavé, et ce qu'il n'a pas eu à laver.** Passé sur les
comparaisons déjà publiées : le 3–1 de §3.25 (`t31b`) est **propre**, dans les
deux bras ; `t31c` aussi. Le seul tour mort tombe dans `t31_web` — la première
comparaison, déjà retirée pour une autre raison (le préambule n'était donné
qu'au bras web). Aucune conclusion publiée ne bouge ; c'est le garde qui le
dit, plus la mémoire.

**Trois valeurs, pas deux.** Un tour tué reçoit sa propre lettre, **X** — ni
`P` ni `F` — et son run sort de la mesure, le nombre de mis-de-côté écrit à
côté plutôt que retiré en silence. Et l'absence de trace au sol reçoit encore
une autre valeur, `SANS TRACE` : *pas regardé* n'est pas *aucun*.

**Le garde est né câblé** : `_morts_fournisseur` est appelé par `--comparer`.
Aucune comparaison ne se publie sans que ses morts remontent, en tête, avant
le score. Effet immédiat sur la campagne en cours : le bras promesse passe de
trois runs à **un seul utilisable**. `n=1`, donc rien n'y est séparable — ce
qui est vrai, alors que « 2 sur 3 » ne l'était pas.

**Le bras known-BAD a trouvé un défaut dans le garde lui-même.** Avec une clé
`(run, tour)`, les dix morts d'`oxviafree` s'écrasaient en une seule : dix
tâches sous le même `r01`, un `_dsh.out` chacune. Clé corrigée en
`(run, effort, tâche, tour)`. La paire décisive du contrôle : le même run se
lit `FP` sans le garde, `XP` avec.

**Et un défaut de plan que l'incident révèle.** Les trois bras tournent l'un
après l'autre. Les douze `RATE_LIMIT` ont visé le bras promesse **et lui
seul** — pas parce que c'est le bras promesse, mais parce que c'est celui qui
tournait à ce moment-là. Tant que les bras se suivent au lieu de s'entrelacer,
« le bras » et « le moment » sont indiscernables, et aucune quantité de
répétitions ne les sépare.

**Instrument :** `scripts/bench_julia_effort/analyse.py`
(`_morts_fournisseur`, `_type_fatal`, lettre `X` dans `_marques`), câblé dans
`--comparer` ; bras known-BAD dans `fixture_injection.py` §9octies
(8 assertions : 3 known-BAD, 1 known-GOOD, 2 known-ABSENT, 2 sur la lecture).

### §3.28 — Trois bras propres : la recherche a servi une fois, et le sort de la tâche se joue ailleurs

Campagne `t31d`, trois bras, énoncés vérifiés au codepoint (§3.27 pour le
garde). Le bras promesse a été **relancé** (`t31d_promesse2`) après que la
dorsale eut tué deux de ses trois runs ; les quatre runs propres du bras sont
poolés sur `(empreinte, bras)` — jamais sur l'empreinte seule, puisque web et
promesse la **partagent** par construction.

```
  témoin    n=3   2 PASS   tour 1 : 1/3   julia 56   2617 s   [FP] [P]  [FF]
  promesse  n=4   3 PASS   tour 1 : 2/4   julia 84   3100 s   [CP] [P]  [FF] [P]
  web       n=3   3 PASS   tour 1 : 2/3   julia 35   1876 s   [P]  [FP] [P]
  (zéro coupure dorsale dans les trois bras — cette campagne est une mesure)
```

**L'ordre est le même sur les quatre colonnes, et ce n'est pas un faisceau.**
Passer au tour 1, dépenser moins de Julia et finir plus vite sont largement la
même chose vue trois fois : un run qui réussit d'emblée est mécaniquement court
et sobre. Compter quatre accords dépendants comme quatre confirmations est une
amplification, pas une preuve. `n` vaut 3 à 4 ; l'instrument écrit de lui-même
« aucun écart n'est séparable ici ».

**Une seule recherche a été faite dans tout le bras web**, et elle a servi :
`web r2`, bloqué sur `DualN(::DualN) is ambiguous`, a reçu deux fils Discourse
portant exactement sur l'ambiguïté de dispatch, et il est passé au tour
suivant. Le mécanisme fonctionne. Ce n'est pas lui qui manque.

**Ce qui décide réellement de t31 est un piège unique**, et il n'est pas
cherchable. Après avoir échoué sur X, un run finit-il par passer (toutes
campagnes t31, coupures exclues) ?

```
  confusion de perturbation    2/6   ##....
  ambiguïté de dispatch        1/4   #...
  dérivée d'une constante      2/2   ##
```

La confusion de perturbation est à la fois le blocage le plus fréquent et
celui dont on se relève le moins. Dans `t31d` elle a été fatale 2 fois sur 2 :
tout run qui y tombe échoue, tout run qui l'évite passe. Et c'est une erreur de
**raisonnement** sur les duaux imbriqués, pas une erreur de langage — au tour 1,
au moment où le sort se joue, rien n'a encore été livré. **On ne cherche pas
pour éviter un bug qu'on ne sait pas encore avoir.**

> **Conséquence pour le banc, et c'est le livrable.** t31 n'a pas la résolution
> nécessaire pour mesurer un effet de recherche : son issue est décidée par un
> piège conceptuel insensible à la documentation. Mesurer la recherche demande
> des tâches dont les blocages sont *cherchables* — dispatch, API, versions.
> C'est un critère de **sélection de tâches**, pas un réglage.

**Le biais qui survit à la relance.** Les trois bras se sont succédé sur trois
heures, la relance une demi-heure plus tard encore. Les douze `RATE_LIMIT` du
matin prouvent que la dorsale change d'état dans cette fenêtre. « Le bras » et
« l'heure » restent donc indiscernables, et **aucune quantité de répétitions ne
les sépare** — seul l'entrelacement le fait. Prochain chantier : boucler sur
`(répétition, bras)` au lieu de `(bras, répétition)`.

**Instrument :** `resultats_t31d_{sans,promesse,promesse2,web}.jsonl` ;
`analyse.py --comparer` (provenance groupée par empreinte, morts dorsale,
mesure hors runs écartés).

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
| 2026-08-22 | Campagne externe : **29 runs lances, 1 PASS** (t21, Gemini 3.7 Flash, 109 s). Les 28 autres sont des 429/402, pas des echecs de tache. Le plafond d'un banc gratuit est le **quota du jour**, pas le debit : paralleliser atteindrait le mur plus vite (3.10). |
| 2026-08-22 | Six modeles sur huit sondes etaient deja morts ; les deux vivants le sont restes le temps d'un run. Le levier est le NOMBRE DE CLEFS, pas la concurrence (3.10). |

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
