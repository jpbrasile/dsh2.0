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

---

## 2026-08-26 — Échantillonnage : ce que les agents envoyaient vraiment

### Le trou, et sa mesure

Un **serveur témoin** OpenAI-compatible (`scripts/polyglot_dsh/temoin_echantillonnage.py`)
répond lui-même et journalise le corps de chaque requête : aucun modèle chargé,
aucun crédit, aucun trafic vers le 4090 (occupé par le run GPQA). Accueils
isolés des deux côtés — `PI_CODING_AGENT_DIR` pour pi,
`~/.dsh-temoin-echantillonnage` pour dsh — parce que `pilote.py` réécrit
`agent-default-model` sans le restaurer.

Corps de requête réels, dsh et pi :

| clé | dsh | pi |
|---|---|---|
| `max_completion_tokens` | 4096 | 4096 |
| `reasoning_effort` | `"medium"` | `"medium"` |
| `stream` / `stream_options` / `store` | oui | oui |
| **`temperature`, `top_p`, `top_k`, `min_p`** | **absentes** | **absentes** |

Deux conclusions opposées. **La comparaison dsh contre pi n'était pas biaisée
par l'échantillonnage** — corps identiques au champ près, hypothèse tacite des
runs `dsh-dev-or` / `pi-dev-or`, maintenant vérifiée. Mais **le réglage Qwen
n'était appliqué nulle part** : les deux héritaient du défaut de l'amont
OpenRouter, inconnu, non journalisé, et susceptible de changer si le routeur
bascule d'amont.

Vérification annexe : `reasoning_effort: "medium"` **part bien** des deux côtés.
Un troisième appel dsh part avec `max_completion_tokens: 64` sans effort — c'est
`@deepseek-ai/dsh-session-title-llm`, à exclure de tout comptage de jetons.

### Le bouton : chez pi oui, chez dsh non

- **pi** — `samplingParams` dans `models.json` fonctionne, vérifié sur le fil.
- **dsh** — aucune voie. `samplingParams`, `temperature` au niveau du modèle,
  `temperature` au niveau de la route : **les trois ignorées en silence**. La
  construction du modèle (`dsh-llm-pi-ai/lib/index.js:639-657`) ne retient que
  id, name, api, provider, baseUrl, input, cost, contextWindow, maxTokens,
  reasoning, compat. Le transport existe (`index.js:1740`) et
  `CallConfig.temperature` est déclaré, mais **aucun paquet dsh ne le remplit**.
  Confirmé en amont : dsh est open source
  (`github.com/deepseek-ai/deepseek-harness`), `docs/user/guide/providers.md` ne
  liste aucun champ d'échantillonnage, et `packages/llm/llm-pi-ai/README.md` dit
  que les *sampling fields* arrivent par `GenerateOptions` à l'appel.

**PIÈGE À RETENIR : dsh ne rejette pas une clé de configuration inconnue, il la
jette sans un mot.** `temperature: 1.0` dans `settings.yaml` donne un fichier
qui a l'air réglé et une requête qui ne l'est pas.

### La correction : proxy d'injection

Régler pi seul aurait cassé le pied d'égalité. La correction est donc
**extérieure aux deux agents** : `scripts/bench_julia_effort/proxy.mjs` étendu
d'un `PROXY_INJECT` (objet JSON) qui pose les champs dans chaque corps
`chat/completions`, écrase en le **nommant** dans le journal (`ecrase`), et
refuse de démarrer sur un JSON illisible. Sans la variable, comportement
inchangé octet pour octet — le banc julia utilise le même fichier.

Piège traité : le corps change de taille, donc `content-length` est recalculé et
`transfer-encoding` retiré.

Câblage additif (`cabler_proxy_injection.py`) : route `openrouter-inject` à côté
de `openrouter`, pour dsh comme pour pi, `baseURL` en **`/api/v1`** (OpenRouter
ne sert pas `/v1` ; une baseURL en `/v1` rend un 404 HTML qu'on prend pour un
refus de champ). Aucune clé dans un fichier : `apiKeyEnv` côté dsh,
interpolation `"$OPENROUTER_API_KEY"` côté pi. Sauvegarde
`settings.yaml.avant-injection` écrite avant modification.

Vérifié bout en bout : les deux agents émettent les mêmes champs en flux, et
**OpenRouter les accepte tous** pour `qwen/qwen3.8-27b` (HTTP 200).

### Le réglage lui-même — et il aligne aussi sur aider

Carte de modèle Qwen3.8-27B, **thinking** : `temperature 1.0, top_p 0.95,
top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0`.
Non-thinking : `0.7 / 0.80 / 20 / 0.0 / 1.5 / 1.0`. **Aucune distinction
codage / raisonnement** n'est publiée : la seule qui existe est thinking vs
non-thinking, et nos deux bancs sont en thinking.

Ma première injection oubliait `presence_penalty` et `repetition_penalty` —
ajoutés, plutôt que supposés au défaut de l'amont.

Découverte dans l'en-tête de `pilote.py` : **le run aider de référence force
déjà ces valeurs** (`--read-model-settings`). L'injection n'harmonise donc pas
seulement dsh et pi entre eux, **elle les aligne sur le bras aider**. La
divergence n° 2 déclarée en tête de `pilote.py` est réécrite en conséquence.

Qwen recommande par ailleurs jusqu'à **262 144 jetons de raisonnement et
131 072 de réponse** pour l'agentique. Les agents envoyaient `4096`. À surveiller
dans le journal du proxy : une troncature ressemble à un agent qui échoue.

---

## 2026-08-26 — GPQA local : ce qui n'explique PAS l'écart 89,2 → ~70

État du run t=1,0, mesuré en cours : **227/792 appels**, 155/221 justes
= 70,1 % (parses), **69,4 % ± 4,9 par question** (erreur groupée, n = 57),
tronqués 5 (2,2 %). Le 74,6 % relevé à 128 appels était un mirage de début de
run — retour à la moyenne.

**Température : rien.** Comparaison appariée à 128 appels, même graine :
t=1,0 74,6 % contre t=0,6 79,2 %, écart **−3,9 pt ± 3,7, z = −1,04**, et
surtout **105 réponses identiques sur 128**. À ± 4,9 pt d'erreur groupée, rien
sous ~10 pt ne sera séparable.

**Deux hypothèses éliminées gratuitement, sur les données déjà acquises :**

- *Biais de position* : r0 76,3 / r1 71,2 / r2 75,0 / r3 67,2 (t=0,6, n≈59 par
  rotation, ±5,7 pt). Du bruit. La rotation ne pénalise pas le modèle.
- *Vote majoritaire* : ≥3/4 donne **73,2 %** contre 74,6 % en moyenne simple —
  *moins bien*. Un consensus ne sauve pas ce modèle. (≥2/4 monte à 80,4 %, mais
  ce n'est plus une majorité.)

Structure : **58,9 % des questions parfaites 4/4, 14,3 % nulles 0/4**, donc
**27 % instables selon la position des options** — de l'incertitude réelle, pas
un artefact de notation.

**L'effort de raisonnement est déjà au maximum.** Le gabarit lu sur `/props`
(aucune inférence, le serveur est occupé) porte
`reasoning_effort|default('xhigh')`, la branche est active dès que
`enable_thinking is undefined`, et l'instruction xhigh est bien émise dans notre
forme de requête (sans outils, sans système) par la branche
`elif reasoning_instructions`. Pourtant : **91 % des réponses contiennent
`<think>`, et le bloc de pensée fait ~382 jetons de médiane** (p90 568, max 724),
en style télégraphique. Justes 721 jetons contre faux 754 : le modèle ne
réfléchit pas plus sur les questions dures.

**Ce qui reste, non décomposé :** la quantification Q4_K_M, le protocole publié
(inconnu : passe unique ? consensus ? quel budget ?), et le décodage spéculatif
(`specdec-q38-dflash2` — censé préserver la distribution, ce qui est une
propriété à vérifier, pas à supposer). **Le seul test décisif est un bras bf16
sur le même harnais**, abandonné le 26/08 par décision explicite. L'écart reste
donc attribué à « Q4 + protocole », sans partage mesuré.

---

## 2026-08-26 — Banc polyglot : variante D et cas durs

**Variante D vérifiée** (fumée 2 exercices, pi, go + python) : `variante="D"`,
`tests_maison=true`, `sans_tests=true`, `sans_corriges=true`, 2/2 PASS, les deux
**au tour 1**, 5,8 min. La machinerie tient.

**Un seul tour est une condition de validité.** `pilote.py:620` fait
`texte = erreurs + TEST_FAILURES…` : au tour 2 l'agent reçoit la sortie d'échec
de la suite officielle **mot pour mot**. En variante D cette suite est la
recette d'acceptation cachée — un deuxième tour la fuite. Comparable côté
aider : `pass_rate_1` = **16,9 %**, pas 52,0 %, en disant ce que « 1 tour »
recouvre de chaque côté (aider : écriture aveugle, zéro exécution ; D : autant
d'itérations internes que l'agent en veut).

**Correction d'un chiffre porté à tort :** `dsh-dev-or` fait **8 exercices,
8 passes**, pas 7.

**Cas durs extraits des runs précédents** (`cas_durs.py`, pas choisis à la
main) :

| exercice | run | ce qui a cassé |
|---|---|---|
| java/book-store | pi **et** dsh | pi FAIL 1847,9 s, 2 tours coupés, artefact ; dsh coupé 910,4 s |
| go/beer-song | dsh | coupé à 901,1 s |
| go/crypto-square | dsh | coupé à 903,1 s |
| cpp/binary-search-tree | dsh | 869,8 s au ras du plafond, artefact effacé |
| cpp/dnd-character | dsh | artefact effacé |
| java/custom-set | pi | artefact effacé |

Trois coupures entre 901 et 910 s contre un plafond de 900 : **censure franche**,
la durée est une borne inférieure et `sortie_queue` revient vide. Passer à
`--tours 1` retire la moitié du temps d'horloge au moment où l'itération rentre
à l'intérieur du tour : `--delai-tour` relevé à **1800 s**, sinon on mesure le
chronomètre — et surtout chez dsh, le plus lent.

Quatre des six cas durs sont en cpp ou java, précisément les langages où la
variante D est déclarée structurellement plus dure (câbler un test maison
demande de toucher `CMakeLists.txt` / Gradle, interdits — **73 exercices sur
225**). La fumée teste donc D là où elle fait le plus mal.

Nouvelle option `--exercices langage/exercice,...` : rejoue exactement les
exercices nommés, court-circuite l'échantillonnage, et **arrête le run** si un
nom est absent du corpus — un cas dur qui disparaît sans bruit est exactement ce
qu'on essaie d'empêcher.

Crédit OpenRouter restant au lancement : **14,42 $**.

---

## 2026-08-26 — La guillotine à 512 jetons : le harnais bridait le modèle

### Ce qui a été trouvé

Le llama-server qui sert GPQA depuis le 25/08 20:57 tournait avec
`--reasoning-budget 512` et **sans** `--reasoning-budget-message`. Vérifié sur
la ligne de commande du processus vivant (PID 18812), pas sur un script.

**Ce n'était pas une décision de ce banc.** La valeur vient d'un copier-coller :
une soixantaine d'occurrences dans une douzaine de projets
(`af-improve`, `af-ci-verdict`, `agentic-flow-*`, `bench_llm.ps1`,
`start_27b.ps1`…), toutes héritées de la famille
`start_llama_qwopus_27b_coder_*.ps1`, dont l'un porte encore le commentaire
d'origine : *« …makes red-team passes superficial »*. L'intention initiale était
légitime — garder la pensée **agentique** courte et bon marché. Portée telle
quelle dans un banc de **raisonnement**, elle fait exactement l'inverse.

### La mesure, pas la lecture de code

Sur les 294 appels du bras t=1,0 :

| observable | valeur |
|---|---|
| blocs `<think>` analysables | 256 |
| finissant **en pleine phrase** | **212 (83 %)**, parfois en plein mot |
| `finish_reason: length` | 7 sur 294 (2,4 %) |

Le `finish_reason` innocente le plafond à 16384 : ce n'est pas lui qui coupait.

Puis le décisif — les blocs tokenisés par le **`/tokenize` du serveur lui-même**,
échantillon de 60 :

```
   96- 127 | # 1
  320- 351 | # 1
  352- 383 | # 1
  384- 415 | # 1
  416- 447 | # 1
  448- 479 | # 1
  480- 511 | # 1
  512- 543 | ##################################################### 53
```

Médiane 512, p75 512, p90 512, max 514. **53 blocs sur 60 tombent exactement sur
le budget.** Un mur, pas une distribution.

**CORRECTION D'UNE ERREUR À MOI.** J'avais écrit la veille que « l'histogramme ne
montre pas de mur à 512 », ce qui affaiblissait l'hypothèse. C'était un artefact
de ma propre approximation : je convertissais les caractères en jetons à
4 car/jeton, alors que ce texte télégraphique en fait ~3. Le mur était masqué
par l'estimation, pas absent. **Piège à retenir : ne jamais conclure sur une
longueur en jetons estimée quand un tokenizer est joignable en une requête.**

### Ce qu'en dit la littérature

Une coupure **nue** est pire que pas de raisonnement du tout. Sur Qwen3 9B /
HumanEval : 94 % sans bride, 88 % en mode non-thinking, **78 % avec coupure
forcée**. Un message de transition à budget 1000 remonte à 89 %. Si un budget
redevient souhaitable, il devra être **apparié** à
`--reasoning-budget-message`.

### Ce qui a été fait

- `scripts/start_llama_qwen38_27b_specdec.ps1` : le `512` codé en dur devient le
  paramètre `-ReasoningBudget`, **défaut `-1`** (le défaut de llama.cpp), avec
  le pourquoi écrit dans le fichier.
- Argv vérifié par **diff ligne à ligne** entre l'ancien serveur et le nouveau :
  **une seule ligne change**, `512` → `-1`. Même binaire (`src-dflash2/build-faq`,
  `b1-f7aadef`), même modèle, même draft, même ctx 163840, même KV q8_0/q4_0,
  mêmes six paramètres d'échantillonnage.
- Bras 512 **gelé** dans `local_q4_t1_budget512.jsonl` : 294 appels, 74 questions
  dont 72 complètes 4/4, **68,7 % ± 4,2** (erreur groupée). Ce n'est pas un
  déchet : c'est le bras qui chiffrera ce que la guillotine coûte.
- Bras illimité lancé dans un **fichier neuf**,
  `local_q4_t1_illimite.jsonl` — obligatoire, parce que `gpqa_diamond.py`
  reprend en sautant les couples `(Record ID, rotation)` déjà présents : écrire
  dans l'ancien fichier aurait sauté les 294 appels sous guillotine et mélangé
  deux régimes de serveur sans que rien ne le signale.

### Deux pièges rencontrés en chemin, tous deux silencieux

1. **La première relance n'a rien fait, et ça ressemblait à une réussite.** Le
   lanceur a refusé sur son propre garde-fou « GPU occupé » (il refuse *avant*
   sa section d'arrêt de port), l'ancien serveur a survécu, et `/props`
   répondait normalement. Je n'avais pas capturé la sortie du processus
   détaché. **Corrigé deux fois** : sortie redirigée, et
   `lancer_local_t1_illimite.ps1` refuse désormais de partir si le serveur
   vivant ne porte pas `--reasoning-budget -1` sur sa ligne de commande.
2. Le lanceur tee en **foreground** et meurt avec son terminal (déjà constaté le
   25/08) : relance obligatoirement détachée.

### Portée

- **GPQA local** : les chiffres du 26/08 (70,1 %, 74,6 %, 68,7 %…) mesurent
  « Q4 + guillotine à 512 », pas le modèle. La comparaison t=1,0 / t=0,6 reste
  *interne* valide — même serveur, même handicap des deux côtés — mais le
  **niveau absolu n'est pas opposable au 89,2 publié**.
- **Toute campagne passée par la route `local-think` (8006 → 8005)**, dont
  l'ancienne échelle d'effort — déjà invalidée pour une autre raison (`high`
  aliasé sur `xhigh`), qui en a maintenant une seconde.
- **Non affecté** : le banc polyglot dsh/pi, qui passe par OpenRouter et n'a
  jamais touché ce serveur. La sonde de mémorisation non plus.

---

## 2026-08-26 — Fumée sur les cas durs : le pire des six passe

`fumee-durs-dsh`, variante D, `--tours 1`, `--delai-tour 1800`,
échantillonnage injecté par le proxy 8009.

**java/book-store : PASS, 1434,0 s, 1 tour, aucune coupure.** C'était le pire
des six : pi avait **échoué** en 1847,9 s avec 2 tours coupés et un artefact ;
dsh avait été **coupé à 910,4 s**. Il passe maintenant, en variante D — où
l'agent écrit lui-même ses tests, sans voir la suite officielle — et du premier
tour.

Les 1434 s valident au passage `--delai-tour 1800` : sous l'ancien plafond de
900 s cet exercice aurait été censuré une troisième fois, et la durée publiée
aurait encore été une borne inférieure.

Injection vérifiée sur le fil : **32 enregistrements, tous injectés, 0 écrasé**,
`max_tokens` 16384 sur le travail réel (les valeurs 1 et 64 sont la sonde de
route et le `dsh-session-title-llm`, à exclure de tout comptage de jetons).

Cinq exercices restants au moment d'écrire.


---

## 2026-08-26 — Où passent les 1434 s d'un exercice, et à quel débit

### Le budget-temps de java/book-store, mesuré sur le fil

Le proxy d'injection horodate chaque appel et sa durée. Fenêtre 13:11:42 →
13:35:36 :

| poste | temps | part |
|---|---|---|
| dans le LLM (25 appels de travail) | 1028,1 s | **72 %** |
| hors LLM (Gradle, docker, git, agent) | 396,4 s | 28 % |
| appels de service (sonde de route, titreur) | 9,5 s | <1 % |

**Un seul appel a mangé 511,3 s — 36 % de l'exercice entier.** Douzième message,
**13 667 jetons de sortie dont 10 095 de raisonnement**, à 26,7 jetons/s. Les
24 autres appels de travail totalisent 517 s à eux tous.

Le hors-LLM n'est pas du bruit non plus : trou franc de **5 minutes sans aucun
appel** entre 13:24:22 et 13:29:24 — Gradle qui compile et teste du Java dans le
conteneur.

**La cause est de mon fait, et il faut l'écrire.** J'ai monté `max_tokens` de
4096 à 16384 en câblant l'injection. Sous 4096, cet appel aurait été **coupé** —
exactement la troncature qu'on cherchait à supprimer. Les 24 minutes ne sont pas
une panne : c'est le prix d'un agent qu'on ne tronque plus.

### Le coût, et ce qui le porte

| | valeur |
|---|---|
| coût de java/book-store seul | **0,2837 $** |
| jetons d'entrée cumulés (43 appels) | 1 074 947 |
| dont mis en cache | **10,6 %** seulement |
| part du coût due à l'**entrée** | **76 %** |
| part due à la sortie | 24 % |

L'entrée gonfle parce que la conversation se ré-envoie entière à chaque tour :
3 → 51 messages, 8 196 → 38 645 jetons d'entrée sur un seul exercice.

**Extrapolation, à traiter comme une estimation et pas comme une mesure :**
un run complet 225 exercices coûterait ~64 $ et ~90 h. Crédit restant :
**13,95 $**. Un run complet est **hors de portée** en argent comme en temps
tant que le cache de prompt ne mord pas mieux.

### Débit : les 24,6 t/s ne sont pas notre carte

Confusion à ne pas refaire : le banc polyglot passe par le proxy d'injection →
**openrouter.ai**. Le 4090 n'y participe pas.

Le bon point de comparaison dans le sweep synthétique n'est **pas** le
123,4 t/s @32k mais la ligne à contexte court, nos prompts GPQA faisant
~250 jetons :

```
~500   n_past=507   prefill=880,9 t/s   decode=109,61 t/s
```

| | débit médian | ce que le chiffre contient |
|---|---|---|
| sweep synthétique @~500 jetons | 109,6 t/s | décode pur, texte prévisible |
| GPQA local, serveur âgé de 17 h | **66,1 t/s** | HTTP + prefill + décode |
| GPQA local, **serveur relancé** | **84,2 t/s** | idem (n=2, faible) |
| OpenRouter bf16 (GPQA) | 33,2 t/s | — |
| OpenRouter qwen3.8-27b (polyglot) | 24,6 t/s | — |

**TROUVAILLE : l'âge du serveur coûte ~27 % de débit.** 66,1 t/s sur un serveur
en place depuis 17 h contre **84,2 t/s** après relance, sur des questions
**appariées**. Gratuit à récupérer, non anticipé. Conséquence de protocole : un
débit mesuré tard dans une session est **pessimiste**, et une table de vitesse
doit porter l'âge du serveur au moment de la mesure.

**Hypothèse éliminée : la température.** t=0,6 donne 70,2 t/s contre 66,1 à
t=1,0 sur les sorties longues — **−6 %**. L'échantillonnage chaud ne détruit
pas l'acceptation du brouillon dflash2. C'était plausible, c'est faux.

Le reste de l'écart 109,6 → 84,2 est l'aller-retour HTTP et le prefill inclus
dans notre chiffre, plus l'acceptation du brouillon sur du raisonnement
imprévisible contre du texte de remplissage prévisible.

**L'ancien effondrement KV est réglé et le reste.** C'était le KV quantifié sans
`GGML_CUDA_FA_ALL_QUANTS` : `36,6 / 8,3 t/s` avant, `2 324 / 122,2 t/s` après
rebuild. Le serveur vivant tourne bien sur `src-dflash2/build-faq`, vérifié sur
son argv. Ce n'est pas une régression de ce banc.

---

## 2026-08-26 — Arène Claude : « et en combien de temps, toi ? »

`arene_claude.py` monte un exercice en **variante D stricte**, à partir du
corpus **vierge** et non de la copie où dsh a travaillé :

- la suite officielle `src/test/java/BookStoreTest.java` **part**, `.meta/`
  (corrigé de référence) **part** ;
- `TASK.md` est copié **mot pour mot** du run dsh ;
- l'agent ne voit que : `.docs/instructions.md`, `TASK.md`, `build.gradle`,
  `gradle/wrapper/*`, `gradlew*`, `src/main/java/BookStore.java` ;
- juge : `juge_claude.py` écarte les tests maison de l'agent, restaure la suite
  officielle, exécute `./gradlew test` dans le conteneur, rend PASS/FAIL.

**Deux réserves, à porter avec le chiffre :**

1. **Cache Gradle froid.** Conteneur `claude-polyglot-tests` créé à l'instant :
   son premier `./gradlew test` télécharge JUnit et AssertJ, que le conteneur de
   dsh avait déjà depuis la veille. Handicap réel pour Claude, en secondes.
   Conteneur séparé obligatoire : les caches gradle vivent DANS le conteneur et
   deux `./gradlew test` simultanés se disputent les verrous de `~/.gradle`.
2. **Piles différentes.** dsh appelle un 27B via OpenRouter à 24,6 t/s ; Claude
   tourne sur son propre modèle. La comparaison répond à **« combien de
   temps »** et **« passe / ne passe pas »**, pas à « qui est le meilleur agent
   à modèle égal ».


---

## 2026-08-26 — Claude sur java/book-store : 185,3 s contre 1434,0 s

Même exercice, même consigne mot pour mot, même variante D, même juge.

| | dsh (Qwen3.8-27B via OpenRouter) | Claude |
|---|---|---|
| temps de bout en bout | **1434,0 s** | **185,3 s** |
| tours | 1 | 1 |
| verdict suite officielle | PASS 18/18 | **PASS 18/18** |
| tests maison écrits | oui | 21, tous verts au 1er jet |

**7,7× plus rapide, même verdict.** Claude a résolu le problème par mémoïsation
exhaustive sur le vecteur de comptes trié — pas de cas particulier « 5+3 → 4+4 »
codé en dur — et a vérifié le panier 4,4,4,2,2 où quatre groupes de quatre à
102,40 battent 5+5+3+3 à 103,20. Arithmétique en centimes entiers, division par
100 seulement à la fin, donc pas de tolérance flottante nécessaire.

**Réserves, à porter avec le chiffre :**

- **Cache Gradle froid** côté Claude (conteneur créé à l'instant) contre cache
  chaud côté dsh. Le handicap joue CONTRE Claude, il ne gonfle pas son score.
- **Piles différentes** : dsh appelle un 27B distant à 24,6 t/s, Claude tourne
  sur son propre modèle. La comparaison répond à « combien de temps » et
  « passe / ne passe pas », **pas** à « quel agent est le meilleur à modèle
  égal ». Un seul exercice, aussi.

### LE PIÈGE ÉVITÉ DE JUSTESSE, ET IL AURAIT ÉTÉ GRAVE

Mon premier juge a rendu **PASS** sur `BUILD SUCCESSFUL`. Le XML JUnit disait :

```
tests="18" skipped="17" failures="0" errors="0"
```

**Un seul test avait tourné, 17 étaient sautés.** Les suites Java d'Exercism
portent `@Disabled` sur tout sauf le premier test — c'est la pratique normale du
site, les élèves les activent un par un. Un juge qui ne les retire pas rend
« réussi » pour n'importe quel code qui compile.

`pilote.py` le fait depuis toujours (ligne 377,
`re.sub(r"@Disabled\([^)]*\)\s*\n", "", t)`) et le run dsh montre bien
`skipped="0"` sur ses 18 tests : **le PASS de dsh est authentique, il n'est pas
touché par ce défaut.** C'est mon juge à moi qui était faux, pendant dix
minutes.

**Deux corrections, pas une :**
1. retrait des `@Disabled`, même geste que `pilote.py` ;
2. et surtout, **le verdict ne lit plus le code de retour**. Il lit le XML
   JUnit, compte les `@Test` de la suite officielle, et rend **INVALIDE** —
   ni PASS ni FAIL — si un seul test a été sauté ou si le nombre exécuté ne
   correspond pas. `BUILD SUCCESSFUL` est vrai aussi quand rien n'a tourné.

**Règle générale à retenir : un code de retour vert n'est pas une mesure.** Il
faut compter ce qui a réellement été exécuté et comparer ce compte à ce qui
était attendu. Un juge qui ne sait pas dire « INVALIDE » ne sait pas dire
« PASS » non plus.



---

## 26/08/2026 — `reasoning_effort` n'est PAS mort, et c'est une plus mauvaise nouvelle

**La question posée : l'écart avec Claude (185 s contre 1434 s, 7,7×) est
anormalement grand.** La piste venue du web était nette — Qwen3.8-27B part en
`xhigh` par défaut et sur-réfléchit massivement (21 min et 22 276 jetons de
raisonnement pour un SVG ; ~60 K jetons de pensée par tour) — et le correctif
documenté est le paramètre d'effort. Nos deux agents envoient déjà
`reasoning_effort: "medium"`. D'où l'hypothèse commode : **le drapeau ne
franchit pas OpenRouter**, il tombe dans le vide et le modèle tourne à son
défaut.

**Mesuré, `test_effort_openrouter.py`, même question, seul l'effort change :**

| variante envoyée | jetons de raisonnement | durée | coût |
|---|---|---|---|
| aucun effort | **4787** | 96,7 s | 0,0152 $ |
| `reasoning_effort: "medium"` | **870** | 40,9 s | 0,0043 $ |
| `reasoning_effort: "low"` | 1307 | 54,5 s | 0,0062 $ |
| `reasoning: {"effort": "low"}` | 0 (non compté) | 61,4 s | 0,0076 $ |

**L'hypothèse commode est fausse.** `reasoning_effort` traverse bien
OpenRouter : 4787 → 870, un facteur 5,5. Le banc n'envoie pas un drapeau mort.

**Réserves, à porter avec le tableau.** Un seul appel par cellule. `low` (1307)
au-dessus de `medium` (870) est non monotone : c'est du bruit, et ces deux
cellules ne se départagent pas. Seul l'écart 4787 vs 870 est assez gros pour
conclure. La ligne 4 ne mesure pas moins de raisonnement, elle mesure un
**comptage différent** : 2766 jetons de sortie mais `reasoning_tokens: 0` — la
forme native ne remonte pas le même champ, on ne peut pas la comparer aux
autres.

**Ce qui reste donc sur la table.** Le drapeau est honoré, et l'appel du banc a
quand même brûlé 10 095 jetons de raisonnement en 511 s. `medium` est appliqué
et reste insuffisant sur une tâche agentique dure. L'écart avec Claude n'a pas
d'explication de plomberie : c'est le comportement du modèle.

### La conséquence opérationnelle est arrivée pendant que je mesurais

`go/beer-song`, fumée « cas durs » dsh :

```
secondes : 1800.3   coupe : True   rc : 1   sortie_queue : (vide)
```

**Mur du `--delai-tour 1800`.** Ce n'est pas un échec du modèle, c'est une
**non-mesure** : l'agent n'a jamais rendu sa copie. La sur-délibération vient de
franchir la frontière entre « lent » et « détruit l'exercice ». À 1434 s pour un
exercice réussi, la marge avant le mur était de 20 %.

État de la fumée à 14:16 — `java/book-store` PASS en 1434,0 s ;
`go/beer-song` NON-MESURE (coupé à 1800 s) ; `go/crypto-square` en cours ;
trois restants ; le run pi est chaîné derrière (PID 26336).

---

## 26/08/2026 — Budget de pensée 8192 apparié à un message : le bras est en vol

**Pourquoi.** Le bras illimité tronquait 17 % de ses appels. Sa distribution est
bimodale et le creux est **total** : les appels qui aboutissent font médiane
1111 jetons de pensée, p90 2695, **max 4371** ; ceux qui échouent tapent 16384,
tous, exactement. Rien entre les deux. Ce n'est pas un manque de marge, c'est un
régime d'emballement. **8192 = 1,9× le pire appel sain.**

**Jamais nu.** Une coupure sans message de transition mesure *pire* que pas de
raisonnement du tout (Qwen3 9B / HumanEval : 94 % sans bride, 88 % sans
raisonnement, **78 % coupure nue**, 89 % avec message à budget 1000). C'est le
défaut qu'on venait de retirer du lanceur ; on ne le réintroduit pas par la
fenêtre. Le lanceur **refuse désormais (exit 8)** un budget > 0 sans message.

### Le canal shell a mangé le message, exactement comme le garde-fou l'annonce

Premier essai de relance : le message multi-ligne passé dans le
`-ArgumentList` de `Start-Process`. PowerShell rejoint le tableau par des
espaces puis re-découpe. Résultat :

```
Impossible de traiter la transformation d'argument sur le paramètre «Port».
Impossible de convertir la valeur «is» en type «System.Int32».
```

Le mot **« is »** du message avait été lié à `-Port`. Le serveur est resté à
terre, le 4090 vide, aucun bras en vol. Correction : une **enveloppe fichier**
(`_relance_budget8192_fils.ps1`) appelée sans argument, où le message est une
**variable PowerShell** — `& $script -ReasoningBudgetMessage $msg` lie une seule
valeur, aucun re-découpage. Message ramené sur **une ligne** au passage : un
saut de ligne survit à PowerShell mais pas forcément à la ligne de commande
native que CreateProcess reconstruit.

**Vérifié sur l'argv du processus vivant**, pas sur le script :

```
budget  : 8192
message : "My thinking budget is now exhausted. I will stop analysing, commit
           to the single most likely option, and finish my response with the
           required last line: Answer: $LETTER"
binaire : build-faq OK
```

`$LETTER` est arrivé **littéral**, non interpolé.

### Le dispositif est vérifié, pas supposé

`sonde_budget8192.py`, question ouverte choisie pour provoquer la
sur-délibération :

```
finish_reason      : stop
jetons sortie      : 11738
jetons de pensee   : 8228   (budget pose : 8192)
message de transition present dans la pensee : True
```

La pensée est coupée à 8228 jetons (8192 + le message), le message ferme le
bloc, et le modèle enchaîne derrière sur une réponse complète et structurée au
lieu de caler. **`finish_reason` reste `stop`** — c'est le piège du dispositif,
et c'est précisément ce qui a rendu la guillotine 512 invisible pendant vingt
heures : un budget de pensée ne lève **jamais** `length`. Le journal ne le dira
pas ; seul le texte le dit.

(Pas de ligne `Answer:` dans la sonde : elle n'envoie pas le gabarit GPQA.
Attendu, ce n'est pas un défaut.)

### En vol

`local_q4_t1_budget8192.jsonl`, fichier neuf — obligatoire, `gpqa_diamond.py`
reprend en sautant les couples (Record ID, rotation) déjà présents et
mélangerait deux régimes de serveur sans rien signaler. L'effet visé est visible
dès le cinquième appel : **8485 jetons et un verdict rendu** (C au lieu de A) là
où le régime illimité aurait tapé 16384 et compté comme non-mesure. Une mauvaise
réponse est une mesure ; une troncature n'en est pas une.

**Bras gelés :**

| bras | appels | questions | score | tronqués |
|---|---|---|---|---|
| `local_q4_t1_budget512.jsonl` | 294 | 74 | 68,7 % ± 4,2 | — |
| `local_q4_t1_budget_illimite.jsonl` | 30 | 8 | 81,2 % ± 12,3 | 17 % |
| `local_q4_t1_budget8192.jsonl` | en vol | — | — | — |

Le rattrapage symétrique à 32768 sur les appels tronqués reste **dû** sur les
deux bras gelés : règle de lecture pré-enregistrée, un appel tronqué est exclu
**et compté**.


---

## 26/08/2026 — Correction : les « cas durs » n'étaient PAS des échecs

**Ma formulation était fausse et elle rendait le chiffre flatteur.** J'ai décrit
les six exercices de la fumée comme des exercices « précédemment en échec ou
tronqués ». Le second terme est juste, le premier ne l'est pas.

**Le critère réel**, `cas_durs.py:16` :

```python
dur = coupes > 0 or not ok or art > 0
```

Tour coupé **OU** échec **OU** artefact effacé. Relevé sur disque, l'état
d'avant côté dsh :

| exercice | dsh AVANT | pi AVANT |
|---|---|---|
| java/book-store | **PASS**, 1 tour coupé, 910,4 s | FAIL, 2 tours coupés, 1847,9 s |
| go/beer-song | **PASS**, 1 tour coupé, 901,1 s | PASS, 119,1 s |
| go/crypto-square | **PASS**, 1 tour coupé, 903,1 s | PASS, 190,1 s |
| cpp/binary-search-tree | **PASS**, 869,8 s | PASS, 451,7 s |
| cpp/dnd-character | **PASS**, 240,4 s | PASS, 159,0 s |
| java/custom-set | **PASS**, 537,0 s | PASS, 141,4 s |

**dsh passait les six.** Trois avaient un tour coupé au ras du plafond de 900 s ;
d'autres un artefact effacé. Aucun n'échouait.

### Ce que ça fait au 50 %

Le 2/4 de la fumée est donc **une chute depuis 6/6, pas une remontée depuis 0**.

Mais ce n'est pas la même tâche. Le run d'avant, `_run_dev_or_fils.ps1` :

```
python pilote.py dsh-dev-or --tours 2 --pas 6 --decalage 3 --par-langue 2
       --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b"
```

Variante **standard**, suite officielle visible, **deux tours** pour corriger.
Aujourd'hui : `--tests-maison --tours 1` — l'agent écrit ses propres tests, ne
voit jamais la suite officielle ni la solution de référence, et n'a pas de
second tour. Le tour unique n'est pas une économie : le tour 2 réinjecte la
sortie de la suite officielle, qui en variante D **est** la recette
d'acceptation cachée.

Trois facteurs ont changé d'un coup, et c'est assumé : une fumée cherche une
panne, pas un effet.

### La conclusion, qui n'est pas confortable

**50 % n'a aucune référence à laquelle se comparer.** Ce n'est ni bon ni
mauvais : c'est un nombre sans étalon, et le publier seul serait trompeur dans
les deux sens — flatteur si on sous-entend une remontée, accablant si on
sous-entend une régression du modèle.

Ce que la fumée a réellement produit tient en une ligne, et celle-là est
mesurée : **le mur des 1800 s est atteint** (`go/beer-song`, 1800,3 s,
`coupe: True`, sortie agent vide), donc la sur-délibération est passée du stade
« lent » au stade « détruit l'exercice ».

**Ce qui rendrait le 50 % lisible** : rejouer les six en variante **standard,
1 tour, délai 1800**. Un seul facteur changerait alors par rapport à
aujourd'hui, et l'écart deviendrait attribuable. Coût ~2 $ sur les 13,33 $
restants. **Non lancé** — hors de la demande, et la file est occupée par pi.


---

## 26/08/2026 — « pi est plus rapide, on a un problème de harnais dsh » : oui, mais pas celui-là

Hypothèse à tester : la lenteur de dsh vient de la plomberie. Le journal de fil
du proxy 8009 (`wire_fumee_durs.jsonl`) permet de trancher, parce qu'il porte
`t0` et `ms` par appel : la somme des `ms` est le temps LLM, l'empan est le
temps total, la différence est tout le reste.

### Où passe le temps — `scripts/polyglot_dsh/ou_passe_le_temps.py`

| | dsh (6 exercices, terminé) | pi (partiel) |
|---|---|---|
| appels | 189 | 24 |
| empan 1er→dernier | 7541 s | — |
| **temps DANS le LLM** | **6404 s = 85 %** | — |
| temps HORS LLM | 1137 s = 15 % (borne inf.) | — |
| durée d'appel | méd 15,4 s, p90 68,8 s, max 511,3 s | méd 3,2 s |
| messages/appel | méd 32, max 91 | méd 10 |
| jetons | 4 919 856 entrée / 149 075 sortie | — |
| coût | 1,8723 $ | — |

**85 % du temps de dsh est passé à attendre le modèle.** L'hypothèse « plomberie »
est réfutée : il n'y a pas 6000 s d'entrées-sorties à récupérer. La fraction
hors-LLM est en outre une **borne inférieure** — l'empan démarre au premier
appel, donc le démarrage du conteneur n'y est pas.

### Ce que la régression a REFUSÉ de dire — `cout_du_prefixe.py`

Régression `ms ~ entrée non cachée + entrée cachée + sortie + constante` :
R² = 0,86, et un coefficient de **−0,42 s / 1000 jetons** sur l'entrée cachée.
Du temps négatif n'existe pas. Un R² élevé n'est pas un permis d'interpréter :
les régresseurs sont colinéaires, le terme dominant (la génération) capte tout,
les autres absorbent du bruit de signe libre.

**L'imputation et la contrefactuelle ont été refusées par garde-fou de signe**,
ajouté au script. La version qui aurait été publiée sans ce garde-fou annonçait
« 1270 s économisables grâce au cache » — un nombre inventé, bâti sur un
préfill négatif.

### Mesure directe, sans modèle — `vitesse_par_contexte.py`

Vitesse apparente = jetons de sortie / durée, par tranche de contexte, appels de
moins de 200 jetons de sortie écartés (la constante par appel les écrase).

| contexte | dsh n | dsh jet/s | pi n | pi jet/s |
|---|---|---|---|---|
| 8–20k | 24 | 43,8 | — | — |
| 20–40k | 71 | **20,2** | 6 | **53,3** |
| 40–80k | 25 | 25,1 | 2 | 77,1 |
| toutes | 121 | **22,7** | 8 | **58,1** |

dsh ralentit bien avec le contexte (43,8 → 20,2 de 8–20k à 20–40k). Mais **à
tranche de contexte égale (20–40k), pi décode 2,6× plus vite.** La longueur de
conversation n'explique donc pas tout. Confondants non levés : n = 6 côté pi,
routage amont OpenRouter non enregistré (`servi` ne porte que le nom du modèle,
pas le fournisseur — c'est la faille que le red team relève par ailleurs).

### Le défaut de harnais, lui, est net et sans confondant

Paramètres réellement émis sur le fil, mêmes modèle / fournisseur / effort :

| | dsh | pi |
|---|---|---|
| `n_tools` | **25** | **4** |
| `sys_chars` | 4367 | 2718 |
| plancher d'entrée observé | **8113 jetons** | **1580 jetons** |
| jetons en cache | **24,7 %** | 78,3 % (66,9 % à 24 appels) |

**dsh paie 8113 jetons d'entrée avant d'avoir commencé à travailler, pi 1580 —
5,1×.** Vingt-cinq définitions d'outils contre quatre, un prompt système 1,6×
plus long. Ça, c'est du harnais, c'est mesuré, et c'est réparable sans toucher
au modèle.

### Conclusion, en séparant ce qui est établi de ce qui ne l'est pas

- **Établi** : le temps de dsh est dans le LLM (85 %), pas dans la plomberie.
- **Établi** : dsh envoie 25 outils et 8113 jetons de socle contre 4 et 1580.
- **Établi** : dsh ne récupère que 24,7 % de son entrée en cache contre ~67–78 %.
  Effet certain sur le **coût** (3 704 032 jetons repayés plein tarif).
- **NON établi** : que ce déficit de cache coûte du *temps*. La régression qui
  devait le chiffrer a rendu un signe faux ; rien n'a été publié à la place.
- **NON établi** : les 2,6× de vitesse de décodage à contexte égal — n = 6 côté
  pi, et le fournisseur amont n'est pas enregistré.
- **Non mesuré** : pi n'a pas fini. Toute comparaison de bout en bout attend
  son run complet sur les six mêmes exercices.

---

## 26/08/2026 — Suite : « 20,2 contre 53,3 jet/s, c'est pas normal » — non, et la cause est le cache

Trois hypothèses écartées par la mesure, dans cet ordre, avant de trouver.

**1. Concurrence — écartée.** Compte des appels en vol simultanément :
dsh 167 appels sur 189 étaient **seuls**. À un seul appel en vol, dsh reste à
22,5 jet/s contre 58,1 pour pi. Ce n'est pas de la contention.

**2. Dérive du fournisseur — écartée, après une lecture trop rapide de ma
part.** dsh passe de 19,3 jet/s (14h) à 52,5 (15h) toutes tranches confondues,
et j'ai d'abord lu ça comme une dérive côté OpenRouter. C'était faux : dans la
tranche 20–40k à 15h, dsh est à **22,5**, pas 52,5. Le 52,5 était un effet de
composition — d'autres tranches. Correction faite avant publication.

**3. Longueur du contexte — écartée, et c'est elle qui met sur la piste.**
La vitesse de dsh n'est pas monotone en contexte :

| dsh 15h00–15h16 | n | jet/s |
|---|---|---|
| 8–20k | 11 | 51,0 |
| 20–40k | 19 | **22,5** |
| 40–80k | 9 | **64,2** |

40–80k plus rapide que 20–40k : le contexte n'est pas la variable. dsh a
**deux populations d'appels**, des rapides et des lents.

### La variable, c'est la fraction déjà en cache

| | contexte méd | à préfiller | durée méd | jet/s méd | n |
|---|---|---|---|---|---|
| dsh cache 0–25 % | 29 062 | **29 062** | 29,4 s | **19,7** | 87 |
| dsh cache 75–100 % | **32 618** | 2 075 | 11,3 s | **54,4** | 32 |
| pi cache 75–100 % | 28 318 | 1 659 | 9,2 s | 58,6 | 18 |

Le contrôle est meilleur que prévu : les appels **cachés** de dsh ont un
contexte **plus gros** (32 618 contre 29 062) et vont pourtant **2,8× plus
vite**. Le contexte est donc écarté par la mesure elle-même, pas par
hypothèse.

Et les appels cachés de dsh (54,4) rejoignent pi (58,6). **Il n'y a jamais eu
d'écart de vitesse entre les deux agents.** Il y a un écart de taux de cache :
24,7 % contre 78,3 %.

### Ce que ça corrige dans l'entrée précédente

L'entrée du jour concluait « effet du déficit de cache sur le TEMPS : non
établi », parce que la régression avait rendu un coefficient négatif. Elle
avait raison de refuser, et tort de s'arrêter là : la régression était le
mauvais instrument (colinéarité), pas la mauvaise question. **Mesuré
directement par stratification, l'effet est établi** : à contexte comparable,
un appel non caché de dsh met 29,4 s là où un appel caché en met 11,3 —
**~18 s par appel**, sur 189 appels.

Ce n'est pas une vitesse de décodage : c'est du **temps de premier jeton**,
passé à préfiller ~29 000 jetons que pi ne repaie pas. La métrique
« jetons de sortie / durée » les mélangeait, d'où le mot « vitesse » impropre
dans l'entrée précédente.

### Statut

- **Établi** : les appels lents de dsh sont ses appels non cachés, à contexte
  contrôlé (et même défavorable).
- **Établi** : dsh caché (54,4) ≈ pi caché (58,6). Pas d'écart d'agent à agent
  une fois le cache égalisé.
- **Non établi** : le total de secondes récupérables. Les ~18 s/appel viennent
  de médianes observationnelles sur deux populations que dsh n'a pas tirées au
  hasard ; le chiffre agrégé demande de savoir POURQUOI le préfixe casse.
- **Non mesuré** : la cause de la casse du préfixe. C'est la prochaine question,
  et elle est dans le code de dsh, plus dans le journal de fil.

---

## 26/08/2026 — Sonde cache : le marqueur n'était pas la cause, je m'étais avancé

**Ce que j'avais annoncé et qui est faux.** Après recherche web, j'ai écrit
« le web donne la cause, et le code la confirme » : Qwen figure chez OpenRouter
dans les fournisseurs à cache **explicite** (`cache_control: {"type":
"ephemeral"}` sur les blocs), le cache automatique ne couvrant qu'OpenAI, Grok,
Moonshot, Groq, DeepSeek, Z.AI et Gemini — et `cache_control` n'apparaît nulle
part dans le dépôt. La déduction était propre et elle est fausse.

**Le test direct la réfute.** `sonde_cache_openrouter.py`, trois conditions,
même préfixe stable de 37 763 jetons, hors proxy pour ne pas polluer la fenêtre
de mesure du run pi en cours :

| cas | 2ᵉ appel, entrée servie par le cache | fournisseur |
|---|---|---|
| **A — sans aucun marqueur** | **86,9 %** | Phala |
| B — `cache_control` sur bloc | 99,8 % | Phala |
| C — `cache_control` racine | 99,8 % | Phala |

**Le cache est automatique sur cette route.** Un préfixe stable revient caché à
86,9 % sans que le client demande quoi que ce soit.

Deux réserves sur ce tableau, pour qu'il ne soit pas sur-lu :
- B et C sont **confondus par l'ordre** : ils réutilisent le préfixe déjà écrit
  en cache par A. Leur 99,8 % ne mesure pas le gain d'un marqueur.
- Le premier appel de A rend 64 jetons cachés, le second 32 832 : la
  construction du cache prend quelques secondes, conformément à la doc.

**Pourquoi la doc ne s'appliquait pas.** Le modèle est servi par **Phala**, pas
par Alibaba. La règle « Alibaba exige des points explicites » vise le
fournisseur, pas le modèle, et le routage OpenRouter décide du fournisseur à
chaque requête. Le journal de fil n'enregistre PAS le fournisseur (`servi` ne
porte que le nom du modèle) : rien ne garantit à ce stade que dsh et pi aient
été servis par le même. C'est un confondant ouvert, pas une hypothèse écartée.

**Ce qui reste établi.** Le cache étant automatique et disponible, les 24,7 %
de dsh contre 78,3 % de pi ne s'expliquent pas par un marqueur manquant :
**dsh casse son propre préfixe.** La séquence de rôles étend bien la précédente
(185/189), donc la structure est en ajout — c'est le CONTENU réémis en tête qui
bouge. Le prompt système varie (4364 / 4367 / 4368 / 4369 caractères) et
donne 0 % de cache à coup sûr quand il change, mais ne couvre que 20 appels
sur 189.

**Prochain pas, décidé** : instrumenter le proxy 8009 pour journaliser une
empreinte du début de requête sérialisée et la position du premier octet qui
diffère de l'appel précédent. À poser **après** la fin du run pi. Cette sonde
doit aussi enregistrer le **fournisseur servant**, qui manque et qui est un
confondant de tout ce qui précède.

---

## 26/08/2026 — Correction : mon test « la séquence de rôles étend la précédente » ne prouvait rien

**Ce que j'ai écrit deux fois aujourd'hui, et qui est sans valeur** : « la
séquence de rôles de dsh ÉTEND bien la précédente (185/189), donc la structure
est en ajout et c'est le contenu réémis en tête qui bouge. »

**Le défaut**, `proxy.mjs:155` :

```js
roles: Array.isArray(p.messages) ? p.messages.slice(0, 3).map(...) : null,
```

Le proxy ne journalise que les **trois premiers rôles**. Sur une conversation
de 32 messages en médiane, comparer trois rôles entre deux appels successifs ne
peut évidemment que rendre « extension » : les trois premiers messages d'une
conversation ne changent pas de rôle. Le 185/189 mesurait cette tautologie, pas
la structure de la requête.

**Ce que ça retire, et ce que ça ne retire pas.** Retiré : l'affirmation que
dsh construit son historique en ajout. Elle n'est ni infirmée ni confirmée —
elle n'est **pas mesurée**. Conservé : les 25 outils sont stables (les 181
appels outillés de dsh partagent une seule empreinte de la liste de noms
journalisée en `proxy.mjs:149`), et le prompt système bouge sur 20 appels sur
189 avec 0 % de cache à chaque fois qu'il bouge.

**Ce que l'instrumentation doit donc porter**, en plus de ce qui était prévu :

1. `roles` **complet**, plus `slice(0, 3)`.
2. La longueur de contenu **par message**, pour voir lequel enfle ou change.
3. Une empreinte du préfixe sérialisé **cumulée message par message** : deux
   appels successifs se comparent alors par recherche du premier indice qui
   diverge — c'est-à-dire l'endroit exact où le préfixe casse.
4. Le **fournisseur servant**, absent du journal (`servi` ne porte que le nom
   du modèle). Sans lui, tout écart dsh/pi reste confondu par le routage — la
   sonde du jour a montré que ce modèle est servi par Phala, pas par Alibaba,
   et que cette différence-là décide du comportement de cache.

**Non posé pour l'instant** : le run pi est en cours (3 exercices sur 6) et
`proxy.mjs` le sert. On ne modifie pas un instrument pendant la mesure.

---

## 26/08/2026 — Bilan des deux côtés : verdicts identiques, temps 3,2× — le surcoût de dsh n'achète rien

Fumée « cas durs », variante D (`--tests-maison --tours 1`), même modèle
`qwen/qwen3.8-27b`, même fournisseur, même proxy, configurations identiques à
`--agent` et `--conteneur` près.

| exercice | dsh | s | pi | s |
|---|---|---|---|---|
| cpp/binary-search-tree | FAIL | 1370,7 | FAIL | 182,3 |
| cpp/dnd-character | FAIL | 1101,8 | FAIL | 159,5 |
| go/beer-song | **NON-MESURE** (mur) | 1800,9 | FAIL | 211,0 |
| go/crypto-square | PASS | 1306,3 | PASS | 1084,6 |
| java/book-store | PASS | 1434,0 | PASS | 586,0 |
| java/custom-set | FAIL | 495,9 | FAIL | 132,3 |

**Sur les 5 exercices mesurés des deux côtés : dsh 2/5, pi 2/5.** Et pas
seulement le même score — **le même verdict, exercice par exercice, 5 fois sur
5**. Les deux agents réussissent crypto-square et book-store, échouent sur
binary-search-tree, dnd-character et custom-set.

### Ce que cette concordance dit

Les échecs sont ceux du **modèle**, pas du harnais. Deux pilotes différents, une
même liste de succès et d'échecs : ce qui décide, c'est
`qwen/qwen3.8-27b` en variante D à un tour, pas la façon dont on l'appelle.

Ça recadre définitivement le « 50 % » d'hier, que j'avais déjà signalé comme
sans étalon : il ne mesurait aucune faiblesse propre à dsh.

### Ce qui sépare vraiment les deux

Le temps, et lui seul : **7510 s pour dsh contre 2356 s pour pi, soit 3,2×**
(médianes 1371 s contre 211 s). Le seul écart de résultat va dans le même sens :
`go/beer-song`, que dsh ne rend jamais parce qu'il tape le mur des 1800 s, pi le
rend en 211 s — pour un échec, mais un échec **mesuré**.

**Le surcoût de temps de dsh n'achète donc aucune qualité.** C'est le point
qui rend la correction du cache prioritaire et non cosmétique : à qualité
strictement égale, dsh paie 3,2× le temps, et ce surcoût lui coûte en plus un
exercice entier en non-mesure.

### Réserve de taille

Cinq exercices. Un écart de moins d'un exercice ne veut rien dire, et cette
fumée sert à trouver des pannes, pas à classer deux agents. Ce qui est solide
ici n'est pas le 2/5 — c'est la **concordance exercice par exercice**, qui ne
tient pas au hasard de la même façon qu'un taux.

### État de la sonde

Sonde de préfixe **posée** dans `proxy.mjs` (`node --check` ok, sauvegarde en
`proxy.mjs.avant-sonde`). Elle n'est PAS active : un node ne relit pas son
fichier, et le processus proxy en cours n'a pas été lancé par moi — il sera pris
au prochain démarrage du proxy.


## 26/08/2026 — Soirée : la règle 4 était aveugle, le specdec n'est pas sans perte, et le cache ne vaut que 1,37×

Quatre choses tranchées le même soir. Elles n'ont rien à voir entre elles sauf
qu'aucune n'était mesurée jusqu'ici, et que trois des quatre contredisent ce que
j'avais écrit plus tôt dans la journée.

### 1. La règle 4 du pré-enregistrement classait à l'envers, pas approximativement

J'avais écrit ce matin que « le bras 512 n'a jamais existé — c'est une copie
renommée », parce qu'aucun de ses 293 enregistrements ne portait le marqueur de
transition. **C'est faux.** Le carnet (l. 1855-1975) montre que le run est bien
passé sous `--reasoning-budget 512` ; le marqueur manquait parce que **ce
serveur-là n'avait pas de `--reasoning-budget-message`**. Un serveur lancé sans
message n'injecte rien : le témoin par marqueur est alors muet par construction,
pas parce que rien n'a été coupé.

Le second témoin, lui, parle : **le mur de jetons**. Une coupure de budget tombe
sur une frontière de jeton, donc une pensée coupée mesure `budget − 2` au moins
(maximum constaté : 514 pour un budget de 512). Sur le bras 512 nu :

| témoin | coupures détectées sur 293 appels |
|---|---|
| message de transition | **0** |
| mur de jetons | **248** — soit 84,6 % |

La règle 4 telle qu'écrite déclarait donc « 100 % libres, pensée courte » un
bras coupé à 84,6 %. Ce n'est pas une imprécision, c'est une **inversion**. La
règle 4 est réécrite en **disjonction des deux témoins**, aucun subordonné à
l'autre, et `gpqa_diamond.py` porte le bloc « NÉCESSAIRE ET INSUFFISANT » qui
dit pourquoi. Révision 4 du pré-enregistrement, commitée avant que le bras B
existe.

### 2. Le balayage de budget comparait deux guillotines, pas une pensée à une pensée

`courbe_de_coupure.py`, écrit pour ça, rend P(pensée > t) sous **censure à
droite** : pour t ≤ B la probabilité est exacte, au-dessus elle est
inestimable et sort en encadrement, jamais en point.

| budget t | P(pensée > t) sur 55 questions |
|---|---|
| 512 | 89,1 % |
| 1024 | 78,2 % |
| 2048 | **63,6 %** |
| 4096 | 52,7 % |
| 8192 | **45,5 %** |
| ≥ 12288 | inestimable — [0,0 ; 45,5] |

La calibration de 8192 sur **8 questions** est donc caduque : le vrai taux de
coupure est 45,5 %, et le balayage 2048 contre 8192 opposait 63,6 % de coupure à
45,5 %. Il ne mesurait pas « ce que la pensée apporte », il mesurait le coût de
couper plus fort.

**Où sont les erreurs**, par population :

| population | exactitude |
|---|---|
| appels qui finissent de penser seuls | 30/30, 25/25, 34/38 (89,5 %) |
| appels coupés par le budget | 16/25 (64,0 %) et 167/248 (67,3 %) |
| appels qui butent sur le plafond de sortie | **0/12** |

Le 0/12 est le chiffre qui a décidé du plafond 32768 : ce n'est pas une queue
négligeable qu'on tronque, c'est une population entière perdue.

Réserve explicite : cet écart est un effet de **sélection** (les questions
faciles finissent de penser tôt), pas la preuve qu'une coupure abîme une
réponse. La règle 5 gagne quand même son échelon manquant — un bras dont
l'exactitude sur ses appels coupés est à plus de 15 points sous son exactitude
sur ses appels libres, avec n ≥ 30 coupés, est écarté. **Les deux bras gelés
sont éliminés par leur propre critère** (36 et 22 points d'écart).

Le comparateur « pensée libre » qui manquait était déjà sur le disque : 55
paires (id, rotation) communes au bras 512 nu et au bras 8192 + message,
**34/55 = 61,8 % contre 46/55 = 83,6 %**, table 33/8/1/13, McNemar exact
p = 0,0018. Confondu, et déclaré tel : le budget ET le message ont changé
ensemble.

### 3. B1 — le décodage spéculatif n'est pas sans perte en glouton

La dette déclarée de la campagne (`SPECDEC_4090_BENCH.md` :18, :184, :672) est
payée. En glouton la question devient binaire : une seule suite de jetons est
correcte, donc l'égalité octet à octet est testable. 12 questions, `temperature
0`, `top_k 1`, graine 1234, **même binaire des deux côtés** (build `src-dflash2`
y compris en `q38-plain`).

Le plan prévoyait deux jambes. Il en fallait **trois** : sans témoin, une
divergence entre specdec et sans-specdec ne se distingue pas d'un serveur
simplement non reproductible — même symptôme, cause opposée.

| comparaison | ce qu'elle isole | résultat |
|---|---|---|
| A1 contre A2 — plain, deux **processus** | bruit de redémarrage | **12/12 identiques** |
| B1 contre B2 — dflash2, **même** processus | bruit d'instrument | **12/12 identiques** |
| A1 contre B1 — plain contre dflash2 | le spéculateur | **12/12 DIVERGENTS** |

Les deux témoins sont muets, donc la troisième ligne accuse bien le
spéculateur. Le premier octet qui diffère tombe entre 58 et 1113 : divergence
**précoce**, pas une dérive numérique de queue.

Conséquence actée : **le bras de production GPQA tourne sans spéculation.** Coût
mesuré du choix — 46,9 t/s au lieu de 103,6 (2,2×), soit une nuit au lieu d'une
demi-nuit. Un chiffre d'exactitude ne se paie pas d'un décodeur dont on vient de
montrer qu'il change la sortie là où la sortie est décidable.

### 4. Voie A — le cache ne peut pas rendre le rapport 7

`ou_passe_le_temps.py` avait déjà tranché « harnais ou LLM » : sur l'exercice
sondé, **1223 s d'appels LLM sur 1383 s de paroi, soit 88,4 %**. La plomberie
est hors de cause. Restait à savoir, dans ces appels, si le temps part en
prefill ou en décode — les deux corrections n'ont rien à voir.

`prefill_ou_decode.py` ajuste `ms = a·(entrée non cachée) + b·sortie` par
moindres carrés sans constante, sur 24 appels dont l'entrée va de 8 k à 50 k et
la sortie de 72 à 13 435 jetons. Cette dispersion suffit à séparer les deux
pentes.

| | débit ajusté | temps | part |
|---|---|---|---|
| prefill | 1 825 jetons/s | 412 s | 33,7 % |
| décode | 33,3 jetons/s | 825 s | 67,5 % |
| **résidu** | | **−14 s** | **−1,2 %** |

Deux paramètres expliquent la paroi à 1,2 % près. Le résidu est publié pour
qu'on puisse juger l'ajustement plutôt que le croire.

**Contrefactuel.** Avec la part réutilisable de 80,8 % mesurée par
`ou_casse_le_prefixe.py`, un cache **parfait** rendrait 333 s sur 1223 s :
**facteur 1,37×**. Pas 7. Pas même 2.

Ce qui reste est du **décode** : 27 461 jetons de sortie sur un seul exercice,
dont **13 435 en un seul appel** (388 s, 32 % de la paroi LLM à lui tout seul).
Le levier est le volume que l'agent génère, pas le routage. **La voie A change
de cible** : ce n'est plus « réparer le cache », c'est « pourquoi dsh écrit
13 000 jetons d'affilée ».

Fausse piste fermée au passage : AkashML sert 24 appels sur 24 et n'en cache que
2. Ce n'est pas « AkashML ne cache pas » — quand il cache, il cache à **97,7 %**
et **99,4 %**, ce qui prouve que notre préfixe est parfaitement réutilisable.
C'est la réplique atteinte qui varie. Rien de corrigeable côté client.

### 5. Un bras a failli sortir mal étiqueté

Le lanceur de production ne passait pas `--modele` : `gpqa_diamond.py` écrivait
son défaut, et le bras joué sur le serveur **plain** sortait étiqueté
`specdec-q38-dflash2` dans chacun de ses 198 enregistrements. llama-server sert
la requête quel que soit le champ `model`, donc **rien ne lève à l'exécution** —
l'erreur n'apparaît qu'au dépouillement, quand le bras est fini. Constaté à
17:43 après une question jouée ; sortie mise de côté en
`.avorte-mauvais-nom-modele`, pas supprimée. Le lanceur lit désormais l'alias
sur le **processus vivant** et refuse (exit 6) s'il n'y en a pas.

### État à la fin de la soirée

Bras de production GPQA en vol : `local_q4_t1_libre_tournant.jsonl`,
`specdec-q38-plain`, budget −1, plafond 32768, 198 questions en position
tournante, un appel par question. Limites déclarées et non levées : Q4_K_M,
KV q8_0/q4_0, et pas de comparaison au BF16 publié.


## 26/08/2026 — Le rapport dsh/pi est élucidé : c'est la pensée, pas le cache

Mesure appariée, enfin. **Même exercice** (`go/beer-song`), même modèle
(`qwen/qwen3.8-27b`), même fournisseur, même variante D, `--tours 1`, même
effort nominal (`medium` des deux côtés), même proxy instrumenté.

| | dsh | pi | rapport |
|---|---|---|---|
| **paroi de l'exercice** | **1383,0 s** | **282,5 s** | **4,9×** |
| paroi dans les appels LLM | 1366 s (98,8 %) | 270 s (95,6 %) | 5,1× |
| verdict | FAIL | FAIL | — |

Verdict identique des deux côtés : **le surcoût de dsh n'achète toujours
rien.** C'est la troisième fois que ce constat tombe, et cette fois il est
apparié à l'exercice près.

### Ce qui n'est PAS la cause : le cache

C'était l'hypothèse de travail depuis ce matin. Elle est fausse.

| | dsh | pi |
|---|---|---|
| taux de cache servi | **8,0 %** | **7,3 %** |
| part prefill de la paroi LLM | **34,9 %** | **35,0 %** |
| part décode de la paroi LLM | **65,8 %** | **66,6 %** |

Les deux agents subissent le **même** mauvais cache chez le même fournisseur, et
répartissent leur temps entre prefill et décode à 0,1 point près. Le cache ne
peut donc pas expliquer un écart entre eux — il est commun aux deux.

Le contrefactuel le confirme côté dsh : avec la part réutilisable de 80,8 %
mesurée par `ou_casse_le_prefixe.py`, un cache **parfait** ne rendrait que
385 s sur 1366, soit **1,39×**. Pas 5, encore moins 7.

Fausse piste fermée au passage : AkashML sert 29 appels sur 29 pour dsh et n'en
cache que 2 — mais quand il cache, il cache à **97,7 %** et **99,4 %**. Notre
préfixe est parfaitement réutilisable ; c'est la réplique atteinte qui varie.
Rien de corrigeable côté client.

### Ce qui EST la cause : le volume généré, et surtout la pensée

| | dsh | pi | rapport |
|---|---|---|---|
| appels | 29 | 14 | 2,1× |
| entrée cumulée | 1 074 288 | 106 931 | 10,0× |
| **sortie générée** | **29 632** | **4 813** | **6,2×** |
| dont **pensée** | **17 722 (59,8 %)** | **1 336 (27,8 %)** | **13,3×** |
| dont texte visible | 11 910 | 3 477 | 3,4× |
| pensée par appel | **611 jetons** | **95 jetons** | **6,4×** |
| coût de la pensée au débit ajusté | **537 s** | **50 s** | — |

**487 s d'écart sur la seule pensée, pour un écart total de 1096 s : la pensée
porte 45 % du surcoût de dsh à elle seule.** Le reste vient du nombre d'appels
et du poids de chacun.

Et cela au **même effort nominal**. Ce qui n'est pas établi : si dsh pense
6,4× plus par appel parce que son invite l'y pousse (25 outils, 4335 caractères
de système) ou parce que `medium` ne se traduit pas par la même valeur sur le
fil. Le proxy ne journalise pas encore le champ de raisonnement ; je ne l'ai pas
modifié, le processus en cours n'ayant pas été lancé par moi.

### Le préfixe fixe, mesuré des deux côtés

| | dsh | pi |
|---|---|---|
| outils offerts | **25** | **4** |
| prompt système | 4 335 car. | 2 686 car. |
| entrée du 1er appel | **8 196 jetons** | **1 695 jetons** |

dsh porte `subagent`, `subagent_fork`, `workflow`, `ralph`, `send_message`,
`list_agents`, `interrupt_agent`, `job_kill/list/output`,
`create_goal/get_goal/update_goal`, `skill` — de la machinerie multi-agents dont
un kata exercism n'a aucun usage. **4,8× l'addition d'entrée avant le premier
mot**, payée à chaque appel non caché, c'est-à-dire 90 % du temps.

C'est un levier réel, mais borné : le prefill ne pèse que 34,9 % de la paroi.

### Ce que ça change pour la suite

Le livrable 3 (comparaison pi/dsh) était conditionné à l'élucidation du rapport.
**Il est élucidé** : mécanisme nommé (volume de décode, dominé par la pensée),
cause du cache écartée par mesure appariée, borne haute du gain par cache
chiffrée à 1,39×. Le livrable 3 s'ouvre.

La voie A change de cible : ce n'est plus « réparer le cache », c'est **réduire
ce que dsh génère** — moins d'outils offerts, et comprendre pourquoi son
`medium` vaut 6,4 fois celui de pi.

### Réserve de taille

**Un exercice.** Le rapport 4,9× ici, 3,2× sur cinq exercices ce matin, ~7×
contre un agent Claude : ces trois chiffres ne sont pas le même et ne se
moyennent pas. Ce qui est solide n'est pas le facteur, c'est la **décomposition**
— elle est appariée, le résidu de l'ajustement est de −0,7 % côté dsh et −1,6 %
côté pi, et les deux parts prefill/décode coïncident à 0,1 point, ce qu'un
artefact n'aurait aucune raison de produire.

### Note de harnais

`pilote.py --agent pi` demande **deux** drapeaux que le run dsh n'exige pas :
`--accueil-pi` (sinon pi lit sa config personnelle, qui ignore la route du
proxy) et `--dotenv` (sinon `$OPENROUTER_API_KEY` ne s'interpole pas et pi
refuse au pré-vol). Les deux échecs sont explicites et le pré-vol les attrape
avant de jouer — c'est exactement ce à quoi il sert.

### Correction, une heure plus tard : le proxy journalisait déjà le champ d'effort

Dans l'entrée ci-dessus j'ai écrit que « le proxy ne journalise pas encore le
champ de raisonnement ». **C'est faux.** `proxy.mjs` pose depuis le 23/08
`reasoning_effort`, `enable_thinking`, `thinking` et `chat_template_kwargs`
dans chaque enregistrement (l. 155-158). Je l'avais conclu de l'absence de ces
clés dans un enregistrement — mais `JSON.stringify` **supprime les clés dont la
valeur est `undefined`** : leur absence ne dit pas que le proxy ne les écrit
pas, elle dit que **l'agent ne les a pas envoyées**. C'est une mesure, et je
l'avais lue comme un trou d'instrument.

La mesure était donc déjà sur le disque. La voici.

| champ envoyé | dsh (29 appels) | pi (17 appels) |
|---|---|---|
| `reasoning_effort` | **`"medium"`** | **`"medium"`** |
| `enable_thinking` | absent du corps | absent du corps |
| `thinking` | absent du corps | absent du corps |
| `chat_template_kwargs` | absent du corps | absent du corps |
| `max_tokens` | 16384 | 16384 |
| `temperature` / `top_p` / `top_k` / `min_p` | 1 / 0,95 / 20 / 0 | 1 / 0,95 / 20 / 0 |

**Les deux agents envoient des paramètres identiques, champ par champ.** Le
`medium` de dsh et celui de pi sont le même mot sur le fil, pas deux réglages
qui se ressembleraient.

### Ce que ça change au verdict

L'écart de pensée — **611 jetons par appel contre 95, soit 6,4×** — n'est **pas
un effet de réglage**. Il ne reste qu'une cause possible : **l'invite**. Même
modèle, mêmes paramètres de décodage, même demande d'effort ; ce qui diffère est
ce que l'agent met dans le contexte.

Et cela rend le levier « 25 outils contre 4 » nettement plus intéressant qu'il
ne paraissait. Je l'avais classé comme un coût de prefill, donc borné à 35 % de
la paroi. S'il pousse aussi le modèle à penser plus longtemps, il agit sur les
65 % restants — c'est-à-dire sur la part qui porte réellement l'écart.

**Ce qui n'est pas établi, et ne doit pas être présenté comme tel :** *quelle*
partie de l'invite produit l'effet. Le nombre d'outils, les 4 335 caractères de
système contre 2 686, la structure des messages et la formulation de la tâche
varient tous ensemble entre les deux agents. La mesure dit « c'est l'invite »,
pas « c'est le nombre d'outils ». Isoler demanderait un bras où l'on ne change
que la liste d'outils — faisable, non fait.

## 26/08 18:49 — Le fournisseur déplace la paroi de 42 %, et le rapport de 0,4 %

### La question, et l'erreur qu'elle corrige

« As-tu essayé un autre fournisseur sur un cas dsh représentatif ? » **Non.** Les
29 appels de `go/beer-song` sont tous partis chez **AkashML**, sans épinglage,
parce que c'est ce qu'OpenRouter a choisi. Tout le rapport dsh/pi repose sur ce
routage-là.

J'avais écarté le routage plus tôt dans la journée en montrant qu'un cache
parfait ne rendrait que 1,39×. **Cet argument ne portait que sur le cache.** Le
décode pèse 65,8 % de la paroi, et un fournisseur peut y changer un facteur.
L'écarter sur la base du cache était une **erreur de portée**, pas une erreur de
calcul.

### La sonde de débit — 10 fournisseurs, 0,0187 $

Un appel de longueur fixe chacun, épinglé sans repli, le fournisseur **servi**
relu dans la réponse.

| fournisseur | quantif | jetons/s | contexte | $/M sortie | cache |
|---|---|---|---|---|---|
| **Venice** | fp8 | **94,0** | 262 144 | 3,200 | — |
| Alibaba | — | 70,0 | 1 000 000 | 2,550 | oui |
| Io Net | fp8 | 63,3 | 65 500 | 3,400 | oui |
| Parasail | fp8 | 53,5 | 262 144 | 3,200 | — |
| Phala | — | 46,0 | 262 144 | 3,000 | oui |
| CoreWeave | fp8 | 41,3 | 262 144 | 3,000 | oui |
| **AkashML** | bf16 | **33,9** | 262 144 | 2,550 | oui |
| Reka | fp8 | 25,5 | 262 144 | 3,200 | oui |
| Chutes | fp8 | 21,8 | 262 144 | 2,750 | oui |
| Cloudflare | — | 3,3 | 262 144 | 3,200 | oui |

**Facteur 28 entre les extrêmes.** AkashML est **7ᵉ sur 10**.

**Ce que la sonde vaut, et ce qu'elle ne vaut pas.** Un appel par fournisseur ne
donne aucun intervalle : la charge varie d'une minute à l'autre. Un écart de
10 % ici ne veut rien dire ; un facteur 2,77× en veut un. Les capacités de
contexte sont des **déclarations** du catalogue, pas des mesures.

### La validation croisée, qui n'était pas prévue

| méthode | débit de décode d'AkashML |
|---|---|
| moindres carrés à deux pentes sur 29 appels de dsh | **33,0 jetons/s** |
| sonde directe, un appel dédié | **33,9 jetons/s** |

**3 % d'écart entre deux méthodes indépendantes.** L'ajustement lisait bien le
débit du *fournisseur*, pas un artefact de l'agent. C'est la première
vérification externe de l'instrument.

### Ce que le fournisseur change — et ce qu'il ne change pas

Les deux agents ont des parts prefill/décode identiques à 0,1 point près
(34,9/65,8 chez dsh, 35,0/66,6 chez pi). Un facteur sur le décode s'applique
donc **à la même fraction des deux**.

| | prefill | décode | paroi AkashML | paroi si décode ×2,77 |
|---|---|---|---|---|
| dsh | 477 s | 898 s | **1 375 s** | **801 s** (−42 %) |
| pi | 94 s | 180 s | **274 s** | **159 s** (−42 %) |
| **rapport dsh/pi** | | | **5,02×** | **5,04×** |

**Le fournisseur déplace fortement la paroi et pas du tout le rapport.** Les
« 1 383 s » et « 282 s » publiés sont des chiffres **d'AkashML**, pas du modèle
— c'est à corriger partout où ils apparaissent. Le **4,9×**, lui, tient : il est
porté par le **volume** de génération, pas par la vitesse à laquelle on le
génère.

Conséquence pratique : le décode local sans spéculation (46,9 t/s) et avec
dflash2 (103,6 t/s) encadrent Venice. Le local n'est donc pas seulement moins
cher, il est **au niveau du meilleur fournisseur du catalogue** — ce qui renforce
la décision de jouer le polyglot complet en local, prise sur le coût.

---

## 26/08 18:52 — Bras à outils réduits : la machinerie n'est pas la cause

### Ce qui a été fait varier

`cordis.patch.yml` désactive 11 rangées de machinerie multi-agents. Témoin
**direct sur le fil**, pas une déclaration : `n_tools` passe de 25 à 10, et le
prompt système de 4 335 à 1 765 caractères. dsh reste dsh ; même exercice, même
variante D, même effort `medium`, même modèle.

### Le résultat

| | 25 outils (référence) | 10 outils (allégé) |
|---|---|---|
| appels | 29 | **45** |
| jetons de sortie | 29 632 | 55 637 |
| dont pensée | 17 722 (59,8 %) | 38 308 (68,9 %) |
| **pensée par appel** | **611** | **851** (+39 %) |
| cache servi | 8,0 % | 19,4 % |
| verdict | FAIL | FAIL |

**Retirer 15 outils et 2 570 caractères de système fait penser dsh PLUS, pas
moins** : +39 % de pensée par appel, +55 % d'appels. L'hypothèse « la machinerie
gonfle la pensée » est **réfutée dans le sens où elle était posée**.

Le cache, lui, a bien doublé (8,0 → 19,4 %) : un préfixe fixe plus court se
recache mieux. Et l'exercice a quand même échoué et coûté plus cher — nouvelle
confirmation, par un autre chemin, que **le cache n'est pas le levier**.

### Ce qui n'est PAS lisible dans ce bras

La paroi. Le bras allégé a tourné **18:21–18:50**, en même temps que
l'échantillon pi (17:55–18:51) ; la référence à 25 outils avait tourné **seule**
(17:21–17:42). Les deux runs partagent le CPU de la machine et les verrous du
conteneur juge — `pilote.py` le déclare lui-même. **Les 1 805,9 s ne se
comparent donc pas aux 1 383,0 s**, et l'ajustement prefill/décode de ce bras
sort à **11,9 % de résidu**, au-delà de la barre de 10 % que l'outil s'impose :
son verdict de répartition n'est pas lisible non plus.

Ce qui reste lisible est ce qui ne dépend pas de cette machine : **les comptes
de jetons et le nombre d'appels**, relevés sur le fil appel par appel.

### La réserve qui compte

**Un seul tirage, à température 1,0.** +39 % sur une génération unique n'est pas
un intervalle. Ce bras autorise à dire « la machinerie n'explique pas l'écart »,
et interdit de dire « la retirer coûte 39 % ». Pour l'affirmer il faudrait
rejouer les deux bras plusieurs fois, séquentiellement — ce qui n'a pas été fait.

### Où cela laisse la cause

L'écart de pensée dsh/pi (611 contre 95 par appel, **6,4×**) n'est ni un effet de
réglage (les deux agents envoient des corps identiques champ pour champ), ni un
effet de la machinerie d'outils (ce bras), ni un effet du cache (mesure appariée
du 26/08), ni un effet du fournisseur (invariance ci-dessus). Restent la
**formulation de la consigne** et la **structure des messages** — non isolées.

## 26/08 18:55 — Venice : le débit est confirmé, la paroi ne veut rien dire

### Le montage

dsh n'a **aucune voie de configuration** pour le champ `provider` d'OpenRouter :
l'épinglage doit donc être extérieur à l'agent. `PROXY_INJECT` du proxy
enregistreur pose `{"provider": {"order": ["Venice"], "allow_fallbacks": false}}`
dans chaque corps. Un second enregistreur (port 8012) a été posé plutôt que de
réutiliser le 8009, qui journalisait un bras en vol.

**L'épinglage est vérifié sur la réponse avant d'engager** — un appel témoin de
8 jetons, `servi par Venice`. Épingler dans une requête ne prouve rien.

### Ce que la paroi disait, et pourquoi il ne fallait pas la lire

`go/beer-song`, variante D, effort `medium`, 10 outils : **187,2 s**, FAIL.
Contre 1 805,9 s pour le même montage chez AkashML. **9,6×.**

Le fil dit autre chose. Huit appels, et le huitième rend **16 384 jetons de
sortie** — c'est-à-dire le **plafond exact**, en 180 s à lui seul, soit 96 % de
la paroi. Le tour n'a pas fini : il est mort sur le mur de jetons.

| | AkashML @10 outils | Venice @10 outils |
|---|---|---|
| appels | 45 | **8** |
| jetons de sortie | 55 637 | 16 614 |
| pensée par appel | 851 | **2 708** |
| dernier appel | — | **tronqué au plafond** |
| verdict | FAIL | FAIL |

**Publier « Venice va 9,6× plus vite » aurait été fabriquer un résultat.**
L'exercice n'a pas été joué plus vite : il a été joué **moins**, puis coupé.

### Ce que ce bras établit quand même, et proprement

L'ajustement sur ces 8 appels sort à **0,3 % de résidu** — le meilleur des trois
bras — et donne :

| | prefill | décode |
|---|---|---|
| Venice, ajusté sur l'exercice | 8 106 j/s | **91,5 j/s** |
| Venice, sonde dédiée | — | **94,0 j/s** |

**2,7 % d'écart** entre un exercice agentique réel et un appel de sonde. C'est la
deuxième validation croisée de l'instrument après AkashML (33,0 ajusté contre
33,9 sondé, 3 %). **La méthode des deux pentes tient.**

### L'anomalie, qui n'était pas cherchée

Même modèle, même corps de requête au champ près, même consigne, même liste de
10 outils : **2 708 jetons de pensée par appel chez Venice contre 851 chez
AkashML, soit 3,2×.** Le seul facteur qui change est le fournisseur — donc la
quantification (fp8 contre bf16) et le moteur d'inférence.

**Ce qui n'est pas établi.** Un seul exercice, huit appels, à température 1,0 :
aucun intervalle. Trois lectures restent ouvertes et ce bras ne les sépare pas —
(a) la quantification fp8 dégrade la génération et le modèle tourne en rond ;
(b) Venice ignore silencieusement `top_k` ou `min_p`, que le corps envoie, et
l'échantillonnage n'est pas celui qu'on croit ; (c) tirage malheureux.

La lecture (b) est **testable et pas chère** : rejouer la sonde de débit avec et
sans `top_k`/`min_p` et comparer les longueurs. Non fait.

### Conséquence pratique

Un fournisseur rapide **au jeton** peut être plus lent **à la tâche** s'il en
génère trois fois plus. Le classement de débit du soir ne se traduit donc pas
directement en classement de coût ou de temps d'exercice, et je ne l'utiliserai
pas comme tel. Il fallait un exercice réel pour le voir : la sonde à 0,0187 $ ne
pouvait pas le montrer, elle imposait la longueur.

## 26/08 19:15 — Trois amonts, un seul exercice : le local gagne par le volume, pas par la vitesse

### Le montage

`go/beer-song`, variante D, `--tours 1`, effort `medium`, **10 outils des trois
côtés**, **plafond de sortie 16 384 des trois côtés**. Seul l'amont change. Le
bras GPQA a été mis en pause à 21/198 pour libérer la carte (reprise
automatique par `deja_fait()`, rien perdu), et le local a donc tourné **seul sur
le slot unique**.

| | AkashML bf16 | Venice fp8 | **local Q4_K_M** |
|---|---|---|---|
| paroi de l'exercice | 1 805,9 s | 187,2 s | **547,0 s** |
| paroi LLM | 1 775 s | 187 s | **535 s** |
| appels | 45 | 8 | **29** |
| jetons de sortie | 55 637 | 16 614 | **21 942** |
| débit plancher (sortie / paroi) | 31,3 j/s | 89,0 j/s | **41,0 j/s** |
| décode | 33,0 j/s *(ajusté)* | 91,5 j/s *(ajusté)* | **43,5 j/s *(mesuré serveur)*** |
| cache servi | 19,4 % | 0,0 % | **93,0 %** |
| troncature au plafond | non | **oui, 8ᵉ appel** | non |
| coût | 0,5731 $ | 0,0695 $ | **0,0000 $** |
| verdict | FAIL | FAIL | FAIL |

**Le bras Venice ne compte pas comme comparaison de paroi** : son 8ᵉ appel rend
16 384 jetons — le plafond exact — et le tour meurt dessus. Restent deux runs
complets : AkashML et le local.

### Le résultat

**Le local joue le même exercice 3,3× plus vite qu'AkashML** (1 775 s → 535 s),
et **gratuitement**. Mais pas pour la raison qu'on attendrait :

| facteur | valeur |
|---|---|
| il décode plus vite | **1,32×** (43,5 contre 33,0 j/s) |
| il génère moins | **2,54×** (21 942 contre 55 637 jetons) |
| produit | **3,35×** — et la paroi observée donne 3,32× |

**Les deux tiers du gain viennent du volume généré, pas du débit.** C'est
exactement le mécanisme déjà identifié sur le rapport dsh/pi, retrouvé ici par
un autre chemin : ce qui coûte, c'est le nombre de jetons qu'on décide
d'écrire.

Le cache est spectaculaire — **93,0 % contre 19,4 %** — mais il ne pèse que
**6,0 %** de la paroi locale : une boucle agentique sur un slot unique recache
presque tout, et cela ne rapporte presque rien parce que le prefill n'était déjà
pas le problème. Troisième confirmation indépendante que **le cache n'est pas le
levier**.

### Ce que le local donne en plus — et ce qu'il donne en moins

**En plus.** llama-server renvoie un bloc `timings` par requête. On lit
*mesurés*, non ajustés : `prompt_n / prompt_ms / prompt_per_second` et
`predicted_n / predicted_ms / predicted_per_second`. D'où, sur les 29 appels :
prefill **50 635 jetons en 26 s = 1 962 j/s**, décode **22 078 jetons en 508 s =
43,5 j/s**, décode = **95,2 %** de la paroi serveur. Le débit de décode tient
entre 45,4 et 46,9 j/s appel par appel, soit **±1,6 %** — chez OpenRouter je
n'avais qu'une pente moyenne, avec un résidu allant de 0,3 % à 11,9 % selon le
bras.

**Troisième validation croisée de l'instrument**, la première contre une vérité
terrain plutôt que contre une autre estimation :

| | ajustement à deux pentes | `timings` du serveur | écart |
|---|---|---|---|
| décode | 44,6 j/s | 43,5 j/s | **2,5 %** |
| prefill | 1 576 j/s | 1 962 j/s | 20 % |

Le décode, qui porte 92 % de la paroi, est retrouvé à 2,5 %. Le prefill l'est
mal — attendu : il ne pèse que 6 % et la pente est donc mal identifiée. **À
publier tel quel : l'ajustement est fiable là où il compte, et fragile
ailleurs.**

**En moins, et c'est une vraie perte.** Le serveur tourne en
`--reasoning-format none` : les balises `<think>` restent dans le contenu et
`usage` ne porte **aucun compte de jetons de raisonnement**. La séparation
pensée / visible — celle qui a porté tout le diagnostic dsh contre pi (611
contre 95 jetons par appel) — **n'existe pas en local**. Le local est meilleur
sur le temps et le cache, aveugle sur la composition.

Conséquence : la colonne « pensée par appel » du tableau ci-dessus est vide pour
le local, et je ne l'estimerai pas par différence.

### Les réserves, qui ne sont pas des détails

**Un seul tirage par bras, à température 1,0.** Le facteur 2,54 sur le volume
généré est mesuré une fois. Il autorise « le local a généré 2,5× moins sur cet
exercice », pas « le local génère 2,5× moins ».

**Trois quantifications différentes** : Q4_K_M en local, bf16 chez AkashML, fp8
chez Venice. Ce tableau compare des **débits et des volumes**, pas des qualités.
Les trois verdicts sont FAIL, ce qui n'autorise aucune conclusion de qualité
dans un sens ou dans l'autre.

**La part locale de la paroi est négligeable, et cela lève une réserve posée
plus tôt.** J'avais écrit que la paroi du bras AkashML à 10 outils n'était pas
lisible parce qu'un échantillon pi tournait en même temps. Vérification : la
paroi LLM fait 1 775 s sur 1 805,9 s, soit **98,3 %** ; côté local, 535 s sur
547,0 s, soit **97,8 %**. La contention CPU ne peut donc déplacer que ~2 % des
chiffres. **La réserve tient, mais elle est petite** — j'avais été trop prudent
en refusant la comparaison.

### Ce que cela décide

Le polyglot complet tournera **en local**. La décision était déjà prise sur le
coût (225 exercices × 0,47 $ = 106 $ contre 11,28 $ de crédit) ; elle est
maintenant prise aussi sur le **temps** — 3,3× plus rapide qu'AkashML sur un run
complet, et au-dessus de tous les fournisseurs sauf Venice au débit brut, sans
le mur de jetons de Venice.

### Correction, 19:22 : la pensée n'est pas perdue en local, c'est mon proxy qui ne la comptait pas

Dans l'entrée ci-dessus j'ai écrit, en gras, que la séparation pensée / visible
« **n'existe pas en local** », et je l'ai présentée comme « une vraie perte » de
l'essai local. **C'est faux.** L'aide du binaire est explicite :

```
--reasoning-format FORMAT
  - none: leaves thoughts unparsed in `message.content`
  - deepseek: puts thoughts in `message.reasoning_content`
  - deepseek-legacy: keeps <think> tags in `message.content` while
    also populating `message.reasoning_content`
```

`none` ne supprime rien. Il **laisse la pensée dans `message.content`**, entre
`<think>` et `</think>`. Ce qui manque dans `usage`, c'est un **compteur
pré-calculé** — pas l'information. Le banc GPQA le sait depuis toujours et vit
très bien avec : `pensee_de()` de `depouiller_gpqa.py` va chercher les balises
dans le texte, et c'est de là que sortent les `pensee_car` de tous les
enregistrements du bras.

**C'était donc un trou de mon instrument, que j'ai lu comme une limite de la
pile locale.** Exactement la même erreur qu'avec `JSON.stringify` et les clés
`undefined`, quelques heures plus tôt : une absence dans mon journal prise pour
une absence dans le monde.

### Ce qui a été fait, et ce qui n'a surtout pas été fait

Le proxy mesure désormais `pensee_car` et `visible_car` sur la réponse — des
**longueurs uniquement**, jamais le texte, même règle que la sonde de préfixe.
Il lit aussi `reasoning_content` quand un amont sépare déjà la pensée, pour
qu'elle ne compte pas pour zéro.

**Le serveur n'a pas été touché.** Basculer en `--reasoning-format deepseek`
sortirait la pensée de `content` et casserait `pensee_de()`, donc le
dépouillement du bras GPQA qui reprend juste après. La bonne correction était
côté instrument, pas côté serveur — et elle ne coûte pas un redémarrage.

### Ce que ça change au tableau des trois amonts

Rien aux chiffres publiés : la colonne « pensée par appel » du bras local @10
reste vide, parce que ce bras a tourné avant la correction et que le contenu
n'a jamais été stocké. **Elle ne sera pas estimée par différence.** Elle sera
remplie par une nouvelle mesure, pas par un calcul.

Et la phrase « le local est meilleur sur le temps et le cache, aveugle sur la
composition » est retirée. Le local n'est pas aveugle ; c'était le proxy.

### Et une deuxième fois, dans la même heure : le compteur posé mais muet

La première version de ce compteur lisait `choices[0].message.content`. Elle ne
s'est **jamais déclenchée**. dsh appelle avec `stream: true` : le contenu arrive
en fragments `delta`, et le dernier fragment ne porte que `usage`. Quatre appels
ont été journalisés sans un seul `pensee_car`.

C'est la troisième fois de la journée que la même faute revient sous une autre
forme — un instrument qui a l'air posé et qui ne mesure rien, dont le silence
ressemble à une mesure nulle. Elle n'a été vue que parce que j'ai **regardé un
enregistrement entier** au lieu de faire confiance à la présence du code.

Corrigé : le texte est reconstitué à partir des `delta`, mesuré, et non conservé.
La raison d'arrêt est cherchée **à rebours** dans les fragments pour la même
raison — le fragment qui porte `usage` a souvent `choices: []`, et un bras coupé
au plafond passerait sinon pour un bras fini. Les quatre appels du bras avorté
ont été retirés plutôt que gardés à côté d'appels instrumentés : un journal qui
mélange deux instruments ne se dépouille pas.

## 26/08 19:38 — Un réplicat, et la moitié des conclusions du soir tombe

### Ce qui s'est passé

Le bras local @10 outils a été rejoué, uniquement pour récupérer la mesure de
pensée que mon proxy ne prenait pas. Même exercice, même serveur, même
configuration, à une demi-heure d'intervalle :

| local @10 outils | appels | jetons de sortie | paroi LLM |
|---|---|---|---|
| tirage 1, 19:01–19:10 | 26 | **21 942** | 535 s |
| tirage 2, 19:29–19:34 | 28 | **11 101** | 269 s |

**Facteur 2,0 entre deux tirages identiques.** Les deux FAIL.

Ce n'est pas surprenant après coup — température 1,0, tâche agentique où chaque
tour dépend du précédent, donc un choix précoce se propage sur tout le run. Mais
je ne l'avais pas mesuré, et j'ai publié des facteurs plus petits que ça.

### La partition, qui est le vrai résultat

Sur les deux mêmes tirages :

| grandeur | tirage 1 | tirage 2 | écart |
|---|---|---|---|
| **débit de décode** | 43,4 j/s | 44,5 j/s | **2,5 %** |
| **taux de cache** | 93,0 % | 94,0 % | **1 point** |
| jetons de sortie | 21 942 | 11 101 | **×2,0** |
| paroi LLM | 535 s | 269 s | **×2,0** |

**Ce qui se mesure en un tirage : les TAUX.** Débit, part de cache, part de
prefill — ils agrègent des centaines d'événements à l'intérieur d'un même run,
et deux runs les retrouvent à quelques pour cent.

**Ce qui ne se mesure pas en un tirage : les VOLUMES et les PAROIS.** Le nombre
de jetons générés est une décision de l'agent, prise une fois, propagée partout.
Un run en donne un échantillon de taille 1.

### Ce qui tombe

| affirmation publiée ce soir | statut |
|---|---|
| « retirer 15 outils fait monter la pensée de 611 à 851 jetons/appel » (+39 %) | **NON ÉTABLI** — un tirage par bras, effet plus petit que la dispersion |
| « le local génère 2,54× moins de jetons qu'AkashML » | **magnitude non établie**. Direction plausible : les deux tirages locaux (21 942 et 11 101) sont sous AkashML (55 637), mais AkashML n'a lui aussi qu'un tirage |
| « le local joue l'exercice 3,3× plus vite » | **magnitude non établie** — 3,3× ou 6,6× selon le tirage local retenu |
| « Venice pense 3,2× plus qu'AkashML » | **NON ÉTABLI** — un tirage chacun |

### Ce qui tient

| affirmation | pourquoi elle tient |
|---|---|
| débits de décode par fournisseur (33,9 / 94,0 / 43,5 j/s) | mesurés sur des centaines de jetons par appel, retrouvés à 2–3 % par deux méthodes indépendantes et par deux tirages |
| l'ajustement à deux pentes lit bien le débit du fournisseur | trois validations croisées, 2,5 à 3,0 % |
| le cache local vaut 93–94 % contre 19,4 % chez AkashML | taux, stable au point près entre tirages |
| le cache n'est pas le levier | il ne pèse que 6 % de la paroi locale — c'est un rapport de taux, pas de volumes |
| le bras Venice s'est arrêté au plafond au 8ᵉ appel | fait déclaré par `finish_reason`, pas une comparaison |
| dsh et pi envoient des paramètres identiques champ pour champ | lecture directe du fil, pas une moyenne |

### Ce que ça coûte, et ce que ça change à la suite

Trois tirages par configuration sont lancés — @25 ×3, @10 ×1 de plus pour en
avoir trois — soit ~30 minutes de carte prises au bras GPQA, une seule fenêtre
de pause. Le nombre est fixé **avant** de voir les résultats et ne sera pas
révisé après ; les six tirages seront publiés, y compris ceux qui dérangent.

Trois tirages ne donnent pas une précision, ils donnent un ordre de grandeur de
la dispersion. Avec une dispersion à ×2, **aucun facteur sous ~1,5 ne sera
lisible**, et il faudra le dire plutôt que de le publier.

### La leçon, qui n'est pas nouvelle

J'ai passé la soirée à vérifier des instruments — l'épinglage sur la réponse et
pas sur la requête, le plafond sur `finish_reason` et pas sur une égalité, la
pensée mesurée et pas déduite — et j'ai publié des comparaisons **à un tirage**
sans jamais mesurer la dispersion. L'instrument était bon ; l'échantillon
valait 1. Les réserves étaient écrites (« un seul tirage à température 1,0 »)
mais elles étaient en bas de page, et les facteurs étaient en gras.

---

## 26/08 20:16 — Les six tirages sont rentrés : le tableau de dispersion

Six tirages du même exercice (`go/beer-song`, variante D, un tour, plafond
16 384) sur le même serveur local, à deux configurations d'outils. Tous
publiés, y compris celui qui est mort au plafond.

| tirage | outils | systeme | appels | jetons sortis | paroi (s) | décodage (j/s) | cache | arrêt |
|---|---|---|---|---|---|---|---|---|
| `local_mesure` | 10 | 1 765 | 26 | 21 942 | 534,9 | 43,4 | 93,0 % | — (compteur absent) |
| `local_10` | 10 | 1 765 | 28 | 11 101 | 269,3 | 44,5 | 94,0 % | stop |
| `r10c` | 10 | 1 755 | 34 | 27 330 | 664,2 | 43,1 | 95,1 % | stop |
| `r25a` | 25 | 4 327 | 5 | 16 769 | 404,9 | 43,0 | 56,3 % | **length** |
| `r25b` | 25 | 4 327 | 28 | 22 373 | 546,9 | 43,2 | 93,6 % | stop |
| `r25c` | 25 | 4 327 | 34 | 19 268 | 485,5 | 42,8 | 94,3 % | stop |

**La partition tient, et elle est maintenant chiffrée sur six tirages.**

- **Taux — reproductibles.** Le décodage tient dans **42,8 à 44,5 j/s** sur les
  six, soit **±1,9 %** autour de 43,7. Le cache tient dans 93,0 à 95,1 % sur les
  cinq tirages qui ont vécu. Ce sont des grandeurs qui agrègent des centaines
  d'événements *à l'intérieur* d'un tirage.
- **Volumes — non reproductibles.** Les jetons sortis vont de **11 101 à
  27 330** à configuration identique (**×2,46**), la paroi de **269 à 664 s**
  (**×2,47**). Ce sont des décisions d'agent propagées sur tout le tirage.

**Ce que ça tue, définitivement.** Les intervalles @10 et @25 se recouvrent
entièrement sur toutes les grandeurs de volume :

| grandeur | @10 outils | @25 outils | verdict |
|---|---|---|---|
| jetons sortis | 11 101 – 27 330 | 19 268 – 22 373 | recouvrement total |
| paroi (s) | 269 – 664 | 485 – 547 | recouvrement total |
| pensée (car/appel) | 564 – 1 847 | 1 051 – 1 711 | recouvrement total |

L'affirmation « retirer 15 outils fait monter la pensée de +39 % » est
**abandonnée** : à 10 outils la pensée par appel vaut 564 puis 1 847 selon le
tirage — un facteur 3,3 *à l'intérieur d'une même configuration*, contre le
1,39 qu'on prétendait mesurer entre configurations.

**Un tirage sur trois meurt au plafond, et c'est du local.** `r25a` porte
`finish_reason: length` au 5ᵉ appel, 16 384 jetons pile, et son cache tombe à
56,3 % — il n'a pas eu le temps d'en construire. Ce mode d'échec avait été
attribué à Venice le 26/08 18:55 ; il est de dsh, pas du fournisseur.

---

## 26/08 20:20 — Le bras « minimal » : témoin pris sans toucher la carte

Question posée : dsh a-t-il une version *minimale*, et que donne-t-elle ?

**Oui, et c'est le bras qui manquait.** dsh livre un preset d'agent `minimal`,
lu dans le source installé et non sur une page
(`…/@deepseek-ai/dsh/config/agent-presets/minimal/agent.cordis.yml`) : persona
d'**une phrase** avec `complete: true` et `includeRuntimeContext: false`, plus
exactement **deux outils** — le shell persistant et `str_replace_editor`. La
compaction est absente.

**Reproduction, pas invocation, et la raison est écrite.** `--dump-config` le
montre : ce profil headless ne monte pas `@deepseek-ai/dsh-agent-presets` —
déploiement sans roster, les outils viennent des bundles — et l'application
headless n'expose aucun drapeau de preset. Y greffer le roster changerait le
*montage* en plus de la *composition*. On reproduit donc la composition par
`cordis.patch.yml`, et le témoin est le même que pour tous les bras du soir :
`n_tools` et `sys_chars` **sur le fil**.

**Témoin pris contre le serveur témoin du port 8007, carte intacte.** Le bras
GPQA gardait le 4090 ; l'enregistreur 8013 a été pointé sur
`temoin_echantillonnage.py`, qui répond lui-même sans charger de modèle. dsh
compose sa requête entière, le fil la journalise, le témoin répond une phrase.

|  | outils | système (car.) |
|---|---|---|
| dsh standard | 25 | 4 327 |
| dsh @10 (bras d'isolement) | 10 | 1 765 |
| **dsh minimal** | **2** | **357** |
| pi (pour référence) | 4 | 2 686 |

Outils restants : `pwsh`, `str_replace_editor`. C'est le premier bras qui passe
**sous pi sur les deux axes à la fois**.

**Ce témoin n'a pas confirmé, il a attrapé.** Premier essai : rc=1, aucun appel.

    dsh: plugin tree failed to load: 1 entry did not activate
    @deepseek-ai/dsh-command-compact: pending (waiting for service: compaction)

Désactiver `compaction-basic` sans désactiver `command-compact` laisse ce
dernier en attente d'un service qui n'existe plus, et dsh ne démarre pas. Sur la
carte, ça aurait coûté **trois tirages morts** et la fenêtre de pause du bras
GPQA avec. Le chargeur a aussi refusé une rangée que j'avais copiée depuis
l'autre accueil (`patch: entry "tool-subagent-vision" not found`) — ligne
retirée : une rangée qui n'existe pas n'est pas désactivée, elle est ignorée.

**Ce qui n'est pas reproduit, et il faut le dire.** `complete: true` appartient
au greffon `dsh-persona`, que ce profil ne monte pas : ici on écrase le texte de
`system-prompt`, ce qui n'empêche pas d'autres rangées d'ajouter leur section.
Les 357 caractères restants le disent — la persona en fait 46. Et le preset
utilise le shell **persistant** là où ce profil monte le tir unique : l'état ne
survit pas entre appels.

**Le bord tranchant, signalé plutôt que supposé.** Le preset minimal d'amont
monte `dsh-fs-local` à la place du fournisseur en bac à sable : son éditeur
adresse n'importe quel chemin absolu. **On ne l'a pas monté** — le bras garde
`fs-sandbox`. Le noter quand même, parce que quiconque invoquerait le vrai
preset l'aurait, et parce que ce banc donne déjà `pwsh` sur l'hôte : le risque
marginal est nul *ici*, ce qui n'en fait pas un détail *ailleurs*.

**Restauration du bras @25 vérifiée sur le fil, pas sur le fichier.** `r25a`,
`r25b` et `r25c` portent tous 25 outils et 4 327 caractères de système au
premier appel. Le patch avait bien été déposé.

---

## 26/08 20:47 — Douze tirages, même serveur : le rapport dsh/pi est établi, et c'est du volume

Le bras qui manquait a tourné. **pi et dsh sur le même 4090, le même exercice,
le même enregistreur, le même plafond de 16 384 jetons**, trois tirages chacun,
trois compositions de dsh. Douze tirages, tous publiés.

| bras | outils | système | appels | jetons | paroi (s) | décodage | cache | pensée/appel | plafond |
|---|---|---|---|---|---|---|---|---|---|
| dsh @25 | 25 | 4 327 | 5 | 16 769 | 404,9 | 43,0 | 56,3 % | 71 | **mort** |
| dsh @25 | 25 | 4 327 | 28 | 22 373 | 546,9 | 43,2 | 93,6 % | 1 711 | |
| dsh @25 | 25 | 4 327 | 34 | 19 268 | 485,5 | 42,8 | 94,3 % | 1 051 | |
| dsh @10 | 10 | 1 765 | 26 | 21 942 | 534,9 | 43,4 | 93,0 % | — | |
| dsh @10 | 10 | 1 765 | 28 | 11 101 | 269,3 | 44,5 | 94,0 % | 564 | |
| dsh @10 | 10 | 1 755 | 34 | 27 330 | 664,2 | 43,1 | 95,1 % | 1 847 | |
| dsh min | **2** | **357** | 5 | 16 848 | 387,1 | 44,4 | 69,0 % | 54 | **mort** |
| dsh min | **2** | **357** | 5 | 16 866 | 387,4 | 44,5 | 61,9 % | 10 118 | **mort** |
| dsh min | **2** | **357** | 24 | 14 830 | 352,7 | 44,4 | 92,8 % | 1 076 | |
| **pi** | 4 | 2 681 | 15 | **5 491** | **127,9** | 45,7 | 89,9 % | 337 | |
| **pi** | 4 | 2 681 | 23 | **6 163** | **144,4** | 45,6 | 93,9 % | 314 | |
| **pi** | 4 | 2 681 | 15 | **4 028** | **94,7** | 45,8 | 90,8 % | 311 | |

### 1. L'écart est réel : les deux nuages ne se touchent pas

| | dsh (9 tirages) | pi (3 tirages) | recouvrement |
|---|---|---|---|
| paroi (s) | 269 – 664 | 95 – 144 | **aucun** |
| jetons produits | 11 101 – 27 330 | 4 028 – 6 163 | **aucun** |

C'est la première différence d'agent de toute la campagne qui **survit à la
dispersion**. Toutes les précédentes étaient dedans.

**Médianes : 405 s contre 128 s, soit 3,16× ; 16 866 jetons contre 5 491, soit
3,07×.** Le 3,2× mesuré chez AkashML sur six exercices se reproduit à l'identique
sur le 4090, sur un seul exercice et avec des répliques. Deux amonts, deux
protocoles, même facteur.

### 2. Et c'est du volume, entièrement — le débit et le cache sont innocents

| grandeur | dsh | pi | écart |
|---|---|---|---|
| décodage (j/s) | 42,8 – 44,5 | 45,6 – 45,8 | 3 % en faveur de pi |
| **cache d'invite** | **92,8 – 95,1 %** | **89,9 – 93,9 %** | **en faveur de dsh** |
| jetons produits | 11 101 – 27 330 | 4 028 – 6 163 | **3,07×** |

Le rapport de paroi (3,16×) et le rapport de jetons (3,07×) coïncident à 3 %.
**dsh est 3× plus lent parce qu'il génère 3× plus, point.**

Et il faut le dire dans ce sens-là : **dsh cache MIEUX que pi** (93–95 % contre
90–94 %) et reste 3× plus lent. L'hypothèse « le surcoût de dsh vient de son
cache d'invite », qui a porté le plan du 26/08 §7.1 et qui faisait de la
correction du cache une priorité, est **morte**. Elle n'était pas approximative,
elle était à l'envers.

### 3. pi est stable là où dsh ne l'est pas

| | dsh @10 | pi |
|---|---|---|
| paroi | ×2,47 | ×1,52 |
| jetons | ×2,46 | ×1,53 |
| **pensée par appel** | **×3,3** (564 → 1 847) | **×1,08** (311 → 337) |

La pensée par appel de pi tient à **8 %** sur trois tirages. Celle de dsh varie
d'un facteur 3,3 *à configuration identique*. Ce n'est pas seulement que dsh
pense plus : sa quantité de pensée n'est pas déterminée par sa configuration.

### 4. La composition de l'invite n'y est pour rien — trois points, aucun effet

| bras | outils | système | paroi médiane |
|---|---|---|---|
| dsh standard | 25 | 4 327 | 486 s |
| dsh réduit | 10 | 1 765 | 535 s |
| dsh **minimal** | **2** | **357** | 387 s |
| pi | 4 | 2 681 | **128 s** |

Un facteur **12,5 sur le nombre d'outils** et **12 sur la taille du prompt
système** déplacent la médiane de 486 à 387 s — dans la dispersion, et toujours
**2,7× au-dessus de pi**. Et le bras minimal, qui offre *moins* d'outils et
*moins* de système que pi, reste 3× plus lent que lui.

**La piste « un réglage de composition rendra dsh aussi rapide que pi » est
fermée sur ces trois points.** Ce qui reste et qui n'a pas été isolé : la
formulation du prompt système, la structure des messages, et la boucle d'agent
elle-même. Ces trois-là varient ensemble entre les deux agents, et aucun des
deux ponts d'écosystème publiés (`pi-dsh`, `pi2dsh`) ne les sépare — le premier
laisse dsh posséder prompt et boucle, le second dit explicitement ne toucher ni
l'un ni l'autre.

### 5. La fugue au plafond est de dsh, et elle empire quand on allège

**Quatre tirages de dsh sur neuf** meurent en `finish_reason: length`, 16 384
jetons pile, en **un seul appel** de ~370 s. Le bras minimal en meurt **2 fois
sur 3** — le plus léger des trois est le plus atteint. Aucun tirage de pi n'en
meurt.

Forme invariante : quatre appels courts, puis la fugue. Les deux canaux peuvent
fuguer, ce qui interdit une explication simple :

| tirage | jetons | pensée (car.) | visible (car.) |
|---|---|---|---|
| `m1` | 16 384 | **0** | **54 334** |
| `m2` | 16 384 | **50 225** | 138 |

`m1` ne pense pas du tout et déverse 54 000 caractères de contenu ; `m2` pense
50 000 caractères et ne rend rien. Même mort, même plafond, canaux opposés.

Ce mode avait été attribué à Venice le 26/08 18:55 sur un tirage unique. **C'est
faux** : il est de dsh, sur le serveur local, et le fournisseur n'y est pour
rien.

### 6. Ce que ces douze tirages ne disent pas

- **Un seul exercice.** `go/beer-song` est précisément celui que dsh n'a jamais
  rendu au banc des cas durs (mur des 1 800 s) et que pi rend en 211 s. C'est
  le **pire cas de dsh**, choisi pour ça. Le 3,07× ne se généralise pas depuis
  ici — il se *confirme* ici, parce que le 3,2× venait d'un autre corpus.
- **Aucune qualité.** 12 tirages, 12 FAIL. Sur la qualité, ce qui tient reste le
  banc des cas durs : **verdict identique exercice par exercice, 5 fois sur 5**,
  dsh 2/5 et pi 2/5. Les échecs sont ceux du modèle.
- **Le mécanisme reste ouvert.** On sait *que* dsh génère 3× plus. On ne sait pas
  *pourquoi*.

---

## 26/08 23:50 — Correction : le bras GPQA n'est pas à 4 h, il est à 12 h. Et 44 % de sa paroi n'achète rien.

J'ai annoncé « ~4 h » pour ce bras, et l'ordre de carte a été tranché sur ce
chiffre. **Il est faux, et ce n'est pas une dérive : je l'ai pris sur le mauvais
bras.** Les 80 s par question et les 4,41 h du plan (§B5) sont celles du bras
**budget 8192**. Celui qui tourne est le bras à **pensée libre**
(`--reasoning-budget -1`) au plafond 32 768. C'est la coupure du budget qui
bornait le temps ; sans elle il n'y a plus de borne.

Tout ce qui suit est relu ce soir dans le fichier et dans le journal client,
pas repris d'un message antérieur.

### L'allure réelle, à l'horloge

Le journal client porte sa propre colonne d'écoulé — c'est le témoin le plus
propre, il inclut les frais de bout en bout, pas seulement le temps d'appel :

    30/179 ... [70.0 % | 2.5 h ecoulees]      ->  12,0 appels/h

| | bras 8192 (plan §B5) | bras libre (celui qui tourne) |
|---|---|---|
| secondes médiane | 80,1 | **164,5** |
| secondes moyenne | 73,6 | **262,8** |
| secondes max | 137,6 | **746,9** |
| jetons sortie médiane | 6 018 | **7 518** |
| jetons sortie moyenne | 5 090 | **11 856** |

**51/198 faits. 147 restants à 12,0 appels/h = 12,2 h.** Fin vers **midi le
27/08**, pas vers 1 h du matin. La moyenne écrase la médiane parce que la
distribution a une queue lourde — précisément ce que la coupure supprimait.

### Le vrai problème : le plafond mange 44 % de la carte et ne rend rien

**8 appels sur 51 (15,7 %) sortent à 32 768 jetons pile.** Ils rendent
`finish_reason: length` et, au journal client, `donne NON-PARSE` : aucune lettre
analysable. Et ce sont les plus chers :

| population | n | coût moyen | part de la paroi |
|---|---|---|---|
| libres | 43 | 175 s | 56,0 % |
| **tronqués au plafond** | **8** | **737 s** | **44,0 %** (5 897 s sur 13 400) |

**44 % du temps de carte de ce bras est dépensé à produire des réponses qui ne
contiennent pas de réponse.** Un tronqué coûte 4,2× un libre. C'est le fait
dimensionnant de ce bras, et il ne figure nulle part dans le plan.

### Ce que le chiffre vaut aujourd'hui, et pourquoi 90,7 % ne doit pas être publié

    exactitude sur les 43 LIBRES        : 90,7 %  +/- 8,7 pt
    encadrement sur les 8 tronqués      : [76,5 % ; 92,2 %]   largeur 15,7 pt

**90,7 % est trop beau, et la raison en est structurelle, pas anecdotique.** La
population « libre » n'est pas un échantillon : c'est le sous-ensemble des
questions sur lesquelles le modèle a **fini de penser tout seul**. Il tronque
précisément là où il peine. Conditionner sur « a fini » sélectionne donc les
questions résolues. Le 90,7 % ne mesure pas GPQA Diamond, il mesure la partie de
GPQA Diamond que ce modèle trouve facile — et un 27B Q4 au-dessus des modèles de
frontière publiés est le signal que ce biais est gros, pas petit.

La largeur de 15,7 pt est donc le fait, et `depouiller_gpqa.py` le dit déjà de
lui-même : *« LARGEUR > 5 pt : ce bras N'A PAS de chiffre d'exactitude
publiable »*. J'ai vérifié que le harnais n'y est pour rien : `rotations()`
mélange les distracteurs sur une graine dérivée de l'id puis insère la bonne
réponse à la position visée (`gpqa_diamond.py:142-157`) — aucune fuite ;
`extraire()` retire `<think>`, ne lit que les 2 000 derniers caractères et garde
la **dernière** occurrence (`:160-169`). Le biais est dans la sélection, pas dans
le code.

### Et le rattrapage prévu ne sauve pas ce bras

L'étape **B2** du plan prévoyait un « rattrapage à plafond 32768 » des appels
tronqués. Ce bras **est déjà à 32 768** et tronque quand même à 15,7 %. B2 est
donc **sans objet pour lui** : il faudrait un plafond plus haut, donc en nommer
un, donc changer de protocole — ce n'est plus un rattrapage. À reformuler avant
toute publication.

### Ce que je fais, et ce que je ne fais pas

- **Je laisse le bras tourner.** L'ordre de carte a été tranché explicitement ;
  je ne le renverse pas seul, même si la prémisse que j'avais fournie était
  fausse. La correction se publie, la décision reste à l'opérateur.
- **Je ne touche pas au plafond d'un bras en cours** : deux régimes dans un même
  fichier, c'est exactement ce que le plan interdit.
- **Je ne publie pas 90,7 %**, ni comme chiffre ni comme ordre de grandeur.

### La leçon

J'ai repris un chiffre du plan sans vérifier qu'il portait sur le bras dont je
parlais. Les deux bras ont le même modèle, le même serveur, le même nom de
famille — et un facteur 3 sur la paroi. **Un chiffre n'appartient pas à une
campagne, il appartient à une configuration.**

---

## 27/08 03:45 — Le bras GPQA à 100/198 : la troncature est un phénomène de chimie, et le vrai livrable est une comparaison, pas un score

Analyse faite **sans toucher la carte** — que des fichiers déjà produits, pendant
que le bras tourne. Quatre résultats, dont deux renversent ce que j'écrivais il
y a quatre heures.

### 1. La troncature n'est pas une queue lourde générique : c'est la chimie

    Chemistry   17/49  =  34,7 %  tronqués
    Physics      0/42  =   0,0 %
    Biology      1/9   =  11,1 %
    Fisher exact unilatéral : p = 5,7e-06

Zéro sur quarante-deux en physique. Et même quand elle **finit**, la chimie pense
4× plus long : médiane **8 939** jetons contre **2 274** en physique.

**Je m'étais trompé de mécanisme.** Hier soir j'ai écrit que le plus long des
libres s'arrêtait à 32 449 jetons, soit 319 sous le plafond, et j'en ai conclu à
une queue continue coupée par le plafond. C'est vrai de la *forme* et faux de la
*cause* : la distribution n'est pas une seule queue, c'est **deux populations**
dont une seule court.

### 2. La fugue appartient au MODÈLE, pas au déploiement local

Le contrôle était déjà sur le disque : `or_bf16.jsonl`, même modèle en **BF16**,
chez **OpenRouter**, harnais identique.

| bras | chimie | physique |
|---|---|---|
| BF16 (OpenRouter) | **41/104 = 39,4 %** | 1/57 = 1,8 % |
| Q4 local (4090) | **17/49 = 34,7 %** | 0/42 = 0,0 % |

Même motif, deux fournisseurs, deux précisions. **Ni la quantification, ni le KV
q8/q4, ni le 4090 n'y sont pour quoi que ce soit.**

### 3. Monter le plafond n'achèterait rien — B2 n'a pas de bon plafond

    plafond 16 384 (bras illimité)    5/30  = 16,7 % +/- 13,3 pt
    plafond 32 768 (bras libre)      18/100 = 18,0 % +/-  7,5 pt
    écart : +1,3 pt +/- 15,3 pt  ->  DANS LE BRUIT

**Doubler le plafond n'a pas réduit la troncature d'un point mesurable**, alors
qu'il double le coût de chaque fuite : un tronqué coûte déjà **736 s** contre
170 s pour un libre, et absorbe **48,7 % de la paroi du bras** (13 255 s sur
27 197) sans rendre une seule lettre analysable. À 65 536 on paierait ~1 470 s
par fuite pour, selon toute apparence, le même taux.

**Conclusion pour B2 : il n'existe pas de plafond raisonnable qui ferme
l'encadrement.** La bonne réponse n'est pas un plafond plus haut, c'est de
publier la troncature comme un résultat.

### 4. Le vrai livrable : Q4 local reproduit BF16

Et c'est immune au doute sur le niveau absolu, parce que c'est une **comparaison**.

Attention au dénombrement : `or_bf16` a joué **37 questions × 4 rotations**. Une
barre sur 133 appels serait fausse — les 4 appels d'une question ne sont pas
indépendants. Agrégé par question :

| | exactitude (libres) | n |
|---|---|---|
| BF16, OpenRouter | 89,2 % ± 9,2 pt | **37 questions** |
| Q4 local, 4090 | 92,7 % ± 5,7 pt | **82 questions** |

Écart **+3,5 pt**, très à l'intérieur des barres. **Le chemin local — Q4_K_M +
KV q8_0/q4_0, sans specdec — reproduit la référence BF16.** C'est ce que la
campagne avait besoin d'établir, et c'est établi dès maintenant, à 100/198.

### 5. Ce qui NE se publie pas : le niveau absolu

~90 % sur GPQA Diamond placerait un 27B au-dessus des modèles de frontière
publiés. Ce n'est pas crédible. Et comme le chiffre **se reproduit en BF16 chez
un autre fournisseur**, la cause est en amont du montage local — jeu de données,
gabarit, ou contamination du corpus d'entraînement.

**Non vérifié** : je n'ai pas mesuré la contamination, c'est l'hypothèse
principale et rien de plus. Le harnais, lui, a été relu et il est hors de cause
(`rotations()` mélange sur graine dérivée de l'id, `extraire()` garde la dernière
occurrence hors `<think>`).

**Donc : la comparaison Q4/BF16 se publie, le score GPQA absolu ne se publie
pas.** Une contamination inflate les deux côtés de la même manière et laisse
l'écart interprétable ; elle rend le niveau ininterprétable.

### 6. Ce que valent les 8 h de carte restantes

Le bras est à 100/198, **12,3 appels/h, ~8 h restantes**. Ce qu'elles achètent :
la barre du Q4 passerait d'environ ±5,7 pt à ±4 pt. Elles n'achètent **ni** un
score absolu publiable (§5), **ni** la fermeture de l'encadrement (§3). Le
résultat structurel de §4 est déjà acquis.

Je laisse néanmoins le bras tourner : l'ordre de carte a été tranché
explicitement, et huit heures d'une nuit déjà productive ne valent pas que je
renverse seul une décision humaine. La fenêtre de ~45 min pour
`dimensionner_pi_polyglot.ps1` reste ouverte au réveil, et coûte ~9 appels
différés, rien de perdu.

---

## 27/08 04:45 — CORRECTION : le niveau absolu était bon, c'est mon a priori qui était périmé. Et la fugue chimie a un mécanisme

Deux choses dans cette entrée : je retire une affirmation fausse que j'ai
commitée cette nuit (`d201462`), et j'établis le mécanisme de la fugue.

### 1. RETRAIT — « ~90 % n'est pas crédible, contamination probable »

J'ai écrit cette nuit que ~90 % sur GPQA Diamond « mettrait un 27B au-dessus des
modèles de frontière » et que la cause était donc en amont, contamination en
tête. **C'est faux.** Recherche faite : **le chiffre publié par Qwen pour
Qwen3.8-27B est 89,2 sur GPQA Diamond** (Qwen3.7-Plus est donné à 90,3).

Je jugeais sur des a priori d'une génération en retard — Qwen3-32B à ~65-70 %.

| | GPQA Diamond |
|---|---|
| **publié (Qwen, officiel)** | **89,2** |
| BF16 OpenRouter, mesuré ici | 89,2 % ± 9,2 pt (37 q) |
| Q4 local 4090, mesuré ici | 92,7 % ± 5,7 pt (82 q) |

**Le harnais reproduit donc le chiffre constructeur**, et le Q4 local le
reproduit aussi. C'est un bien meilleur résultat que ce que j'écrivais.

**Deux réserves qui, elles, tiennent.** (a) 89,2 est un chiffre constructeur, pas
une réplication indépendante. (b) Mes 92,7 % **excluent** les 18 % d'appels
tronqués ; comptés faux, le bras tombe à 76,0 %. L'encadrement honnête reste
**[76,0 % ; 94,0 %]**, et il *contient* 89,2 sans le discriminer. La comparaison
ne sera à armes égales qu'une fois la troncature traitée — d'où la suite.

### 2. LE MÉCANISME DE LA FUGUE — mesuré, pas supposé

Trois causes possibles s'excluaient. Les trois sont départagées sur le disque.

**Ce n'est pas une boucle dégénérée.** Répétition en 12-grammes :

    tronqués : 0,2 %        libres (témoin) : 0,7 %

Les appels qui fuient se répètent **moins** que ceux qui finissent. Une pénalité
de répétition ou un échantillonneur DRY traiterait un symptôme qui n'existe pas.

**Ce n'est pas un manque de place.** Doubler le plafond de 16 384 à 32 768 :
16,7 % → 18,0 % de troncature, écart +1,3 ± 15,3 pt, **dans le bruit**. Et la
chimie qui finit tient large : médiane 8 614, p90 23 226, max 30 416 jetons.

**C'est la pensée qui ne se referme jamais :**

    balise </think> présente     libres : 94/94        tronqués : 0/20

Cent pour cent d'un côté, zéro de l'autre. Le modèle raisonne — sans se répéter —
pendant 32 768 jetons et **n'émet jamais la transition vers la réponse**. Le
champ `pensee_car` vaut `-1` sur tous les tronqués : la pensée n'a pas de fin à
mesurer.

### 3. LA FUGUE APPARTIENT À DES QUESTIONS PRÉCISES, ET LE Q4 LOCAL S'EN SORT MIEUX

40 questions ont été jouées des deux côtés (BF16 OpenRouter et Q4 local) :

| | local finit | local FUIT |
|---|---|---|
| **BF16 finit** | 26 | **0** |
| **BF16 fuit** | 9 | 5 |

**La case décisive est le zéro.** Aucune question que le BF16 mène à terme ne
fuit en local. L'ensemble des fuites locales est **strictement inclus** dans
celui du BF16 — et le Q4 local en récupère 9 sur 14. Le déploiement quantifié
n'est pas la cause de la fugue ; il y est **moins** sujet que la référence.

C'est une propriété de **questions identifiées**, reproductible à travers deux
précisions et deux fournisseurs.

### 4. QUE FAIRE — quatre options, deux écartées par la mesure

| option | verdict |
|---|---|
| pénalité de répétition / DRY | **écartée** : ils se répètent moins que les autres (0,2 % contre 0,7 %) |
| monter le plafond à 65 536 | **écartée** : 16k→32k n'a rien acheté, et le coût double (736 s → ~1 470 s par fuite) |
| forcer la transition (`--reasoning-budget N`) | **retenue** : c'est le seul levier qui vise la panne réelle — l'absence de `</think>` |
| publier la fugue comme résultat | **retenue, et gratuite** |

**Recommandation, dans cet ordre.**

**(a) Publier le couple, tout de suite et sans carte.** Pas un nombre unique :
« exactitude quand le modèle conclut seul » **et** « part des questions où il ne
conclut pas », avec la liste des questions concernées. C'est honnête, c'est
complet, et c'est déjà mesuré.

**(b) Rattrapage ciblé, budget choisi sur la mesure.** Rejouer **seulement** les
questions tronquées avec `--reasoning-budget 24000` — valeur prise sur le p90 de
la chimie qui finit (23 226), donc elle ne mord que sur la queue qui fuit. Le
budget injecte `</think>` et force la conclusion : c'est exactement la panne
constatée. Population **étiquetée** (`marque` existe déjà au journal), jamais
fusionnée avec le bras principal.

  Coût : ~36 questions sur 198 × ~600 s ≈ **6 h de carte**.
  Effet secondaire déjà mesuré par la campagne : un appel coupé au budget
  répond juste **64,0 %** du temps contre 100 % pour un appel qui conclut seul.
  Donc le rattrapage **ferme l'encadrement mais introduit un biais connu** — il
  se publie comme troisième population, pas fondu dans le chiffre.

**(c) Ce que je n'ai pas retenu, et pourquoi.** Reprendre le raisonnement déjà
produit pour ne demander que la conclusion coûterait 10 min au lieu de 6 h — mais
le journal ne conserve que 40 000 des 101 344 caractères produits. L'idée
redevient bonne si l'on relève d'abord la queue de journalisation ; en l'état
elle travaillerait sur un raisonnement amputé des deux tiers.

## 27/08 05:25 — Le premier FAIL du polyglot n'était pas de la programmation : les 26 stubs cpp cachaient le contrat d'API

Ordre : « lis le premier fail pour voir si ce n'est pas une question de setting ».
C'en était une, et elle touche **tout le cpp**.

### Ce que dit l'artefact

`pi_dimD/cpp/exercises/practice/gigasecond/.dsh.results.json` :

| champ | valeur |
|---|---|
| `tests_outcomes` | `[False]` |
| `duration` | **1 508,2 s** (laisse 1 800 s — 16 % de marge) |
| `num_turns` | 1, `coupe: false` |
| queue de sortie de l'agent | « all 5 tests pass » |
| `tests_ecrits_par_l_agent` | `gigasecond_test.cpp`, `maison_test.cpp` |

L'agent a écrit `gigasecond::anniversary(...)`, avec une logique juste, et ses
propres tests passaient. Le test officiel appelle `gigasecond::advance(...)`.
Le stub livré était un **namespace vide**, et `TASK.md` ne nomme aucune fonction.

En variante D la suite officielle est masquée — **donc le nom attendu n'était
écrit nulle part que l'agent puisse lire.** Ce FAIL mesure de la divination, pas
de la programmation.

### L'ampleur, re-mesurée sur les sauvegardes

Sur les 225 exercices, combien de stubs éditables ne déclarent **rien** ?

| langue | stubs muets | total |
|---|---|---|
| **cpp** | **26** | **26** |
| go, java, javascript, python, rust | 0 | 199 |
| **TOTAL** | **26** | **225** (11,6 %) |

Ce n'est pas « 26 exercices cpp sur 26 » par hasard : **c'est 100 % du cpp**.
Les cinq autres langages livrent leur signature dans le stub (`pub fn after(...)
-> ... { todo!() }` en rust, `void open() throws ... { }` en java). Le cpp
d'Exercism, lui, livre `namespace X {}`.

**Fausse mesure corrigée au passage** : un premier comptage annonçait 26/47 java
muets (55 %). Artefact de motif — les stubs java d'Exercism déclarent leurs
méthodes **sans modificateur d'accès**, et un motif exigeant `public|private|
static` les rate toutes. Java est à **0/47**. Le chiffre publié ci-dessus est
celui d'après correction.

### La correction : semer la SIGNATURE, jamais le CORPS

`semer_signatures.py` écrit dans chaque stub cpp les **déclarations** de
`.meta/example.h`, corps de fonction retirés. Sauvegarde en
`<ex>.h.stub-origine` avant écriture (26 créées, aucune écrasée).

```cpp
// gigasecond.h, après
namespace gigasecond {
boost::posix_time::ptime advance(const boost::posix_time::ptime& start);
}
```

Ce qui est semé : le nom, les types, la structure (namespace/class/enum).
Ce qui ne l'est pas : aucun corps — 6 des 26 en-têtes en contiennent (inline),
ils **seraient** la solution.

**L'extracteur s'est trompé trois fois, dont deux en silence.** Consigné parce
qu'un extracteur qui produit du C++ *plausible* est plus dangereux qu'un qui
plante :

1. la liste d'initialisation de constructeur restait accrochée → C++ invalide
   **et** fuite de `_data(std::forward<TParam>(data))` ;
2. le balayage arrière des parenthèses s'arrêtait à la première `(`, prenant
   `_right(` pour la liste de paramètres ;
3. un `break` sur profondeur négative faisait renoncer le balayage : plus rien
   n'était retiré, `{return _data;}` survivait — **et l'essai à blanc disait OK**.

Règle finale, une seule, ancrée sur la fin de la signature :

```python
mm = re.search(r"\)[\s\w]*(?::[^;{}]*)?\s*$", avant)
```

Contrôle : **0 corps survivant sur les 26**. Le seul `{` restant repéré au grep
était un faux positif — `enum class Plants : char { grass = 'G', … }`, une
déclaration de type qui doit rester.

### Ce que ça change, et ce que ça ne change pas

Ça ne « répare » pas un score : le tirage `pi_dimD` (4 FAIL : cpp/gigasecond
1 508 s, go/simple-linked-list 83 s, java/sgf-parsing 528 s, javascript/say
172 s) a été **arrêté et relancé** sous `pi_dimD2`, protocole neuf, répertoire
neuf (`-Nom` ajouté au lanceur pour ne pas mélanger deux protocoles). Les deux
tirages ne se concaténeront pas.

Ça change la **portée déclarée de la variante D** : sans ce semis, elle est
injouable en cpp par construction. La limite déjà écrite au lanceur (« en cpp et
java, câbler un test maison demande de toucher CMakeLists.txt / Gradle, qui sont
interdits — D y est structurellement plus dur, 73 exercices sur 225 ») en reçoit
une seconde, indépendante, et désormais corrigée.

## 27/08 05:40 — Le semis marche ; et il révèle le défaut d'en dessous

### Le semis est confirmé sur pièce

| tirage | cpp/gigasecond |
|---|---|
| `pi_dimD` — stub à namespace vide | **FAIL, 1 508,2 s** |
| `pi_dimD2` — signature semée | **PASS, 459,7 s** |

Même modèle, même effort, même laisse. Ce n'était pas de la programmation : trois
fois moins de temps dès que le nom attendu est lisible.

### Et l'exercice suivant montre que le nom n'était que la moitié du problème

`go/simple-linked-list` — **FAIL, 141,1 s**. Le semis n'y est pour rien : le stub
go déclare déjà tout, noms, receveurs et types de retour compris.

Le test officiel exige :

```go
list := New([]int{1, 2, 3}); list.Push(4)
list.Array() == []int{1, 2, 3, 4}     // Push ajoute EN FIN
```

L'énoncé parle de playlist, de liste simplement chaînée et de `Reverse`. Il **ne
nomme ni `Push` ni `Pop`**, et ne dit pas de quel côté on empile. L'agent a
empilé **en tête**, avec un `New` qui parcourt à l'envers pour compenser : il
passe New / Size / Array / Pop, et tombe sur les deux seuls tests qui exercent
`Push` sur liste non vide. Sa `Reverse` est juste, son `Pop` est juste, son
erreur sur liste vide est juste.

**La variante D ne cache pas seulement le nom. Elle cache la convention.**

### Ampleur — un plancher, annoncé comme tel

Question mécanisable : l'énoncé cite-t-il au moins **un** des identifiants que le
stub déclare ?

| langue | aucun cité | total | part |
|---|---|---|---|
| cpp | 6 | 26 | 23 % |
| go | 11 | 39 | 28 % |
| java | 20 | 47 | 43 % |
| javascript | 16 | 49 | 33 % |
| python | 7 | 34 | 21 % |
| rust | 10 | 30 | 33 % |
| **TOTAL** | **70** | **225** | **31 %** |

**Ce chiffre sous-compte, et il faut le dire** : `go/simple-linked-list` n'y
figure pas, puisque l'énoncé cite `Reverse`. Citer un nom ne dit pas ce qu'il
fait. Le défaut réel est **au-dessus de 31 %**.

### Ce qu'on ne fera pas

Semer le comportement serait semer le test. La barre cesserait de mesurer. Le
défaut reste donc en place et passe dans les **limites publiées** — c'est la
seule issue honnête.

Conséquence sur la comparabilité, maintenant complète : le taux de la variante D
n'est pas comparable au `pass_rate_2 = 52,0 %` de la fenêtre 7quater, ni au
tableau public, pour **trois** raisons distinctes — le test masqué (voulu), le
contrat d'API masqué en cpp (corrigé le 27/08), la sémantique masquée sur au
moins 31 % des exercices (non corrigeable sans tricher). Dans le banc officiel
le fichier de test est visible : la convention y est donnée et l'ambiguïté
n'existe pas. C'est la variante D qui la crée.

### Défaut d'instrument, corrigé

Le premier moniteur armé sur ce tirage filtrait `OK|FAIL|COUPE` — il ne
contenait **pas** `PASS`. Le seul succès de la série n'a donc pas été notifié, et
le silence ressemblait à un échec. Filtre corrigé. Consigné parce que c'est
exactement la faute que le mode d'emploi du moniteur décrit : « si ce processus
plantait maintenant, mon filtre émettrait-il quelque chose ? » — ici la question
symétrique, « et s'il réussissait ? », n'avait pas été posée.

## 27/08 05:50 — Le dimensionnement est rendu : **≈ 20 h** pour les 225, et les 5 verdicts disent pourquoi

### La mesure

`pi_dimD2`, variante D, `--tours 1`, laisse 1 800 s, `specdec-q38-plain`,
5 exercices tirés à `--pas 45 --decalage 10`.

| langue | exercice | verdict | secondes |
|---|---|---|---|
| cpp | gigasecond | **PASS** | 459,7 |
| go | simple-linked-list | FAIL | 141,1 |
| java | sgf-parsing | FAIL | 372,4 |
| javascript | say | FAIL | 105,2 |
| python | two-bucket | **PASS** | 495,7 |

**5 joués, 2 passés, 1 574,1 s au total — 26,2 min.** Moyenne **314,8 s** par
exercice.

### Le chiffre qui manquait

    225 x 314,8 s = 70 830 s = 19,7 h

Le plan encadrait entre **8 h et 53 h** — un intervalle sur lequel aucune
décision ne se prend. Il se referme sur **≈ 20 h** : une nuit et une matinée.

**Sensibilité au taux, parce qu'elle joue dans le mauvais sens.** Un PASS coûte
**2,3×** un FAIL : 477,7 s de moyenne (n=2) contre 206,2 s (n=3). Un taux plus
élevé rend donc le run **plus long**, pas plus court.

| taux supposé | durée/exercice | 225 exercices |
|---|---|---|
| 40 % (celui de l'échantillon) | 314,8 s | **19,7 h** |
| 52 % (`pass_rate_2` de 7quater) | 347,4 s | **21,7 h** |

Fourchette de travail : **20 à 22 h**.

### Ce que ce 2/5 n'est pas

**Ce n'est pas un `pass_rate`.** Cinq exercices n'en rendent pas un, et le plan
le disait avant la mesure. Il est publié comme durée, et rien d'autre.

Et il est en plus **déprimé par le protocole** : sur les trois échecs, **un seul**
tient au modèle sur le fond.

| exercice | ce qui s'est passé | imputable à |
|---|---|---|
| java/sgf-parsing | 368 s de délibération, **rien écrit** dans le fichier noté ; il essayait de se *souvenir* du test caché | **le modèle** |
| javascript/say | **14 tests sur 16 passent** (vérifié par exécution). Les 2 échecs : le message d'erreur exact `Number must be between 0 and 999,999,999,999.`, littéral qui n'existe que dans la spec cachée | **le protocole (R22)** |
| go/simple-linked-list | logique juste, mais `Push` empile **en tête** quand le test le veut **en fin** — convention écrite nulle part de lisible | **le protocole (R22)** |

### Le câblage du test maison est ouvert en cpp — sur ordre, et avec sa contrepartie

Constat : la consigne « pose tes tests dans `maison_test.cpp` et nulle part
ailleurs » était **inapplicable**. `CMakeLists.txt` code en dur `${file}_test.cpp`
comme unique source de test — un `maison_test.cpp` n'est jamais compilé. L'agent
contournait en écrivant **au nom du test officiel**. Il désobéissait à une
consigne impossible.

Portée **lue dans les fichiers de construction, pas supposée** :

| langue | ce que la construction ramasse | ouverture nécessaire |
|---|---|---|
| **cpp** | `${file}_test.cpp` en dur | **oui — 26 exercices** |
| java | `build.gradle` = plugin `java` seul, tout `src/test/java/**` | non |
| go | `go test ./...` | non |
| python | `pytest` collecte `test_*.py` | non |
| javascript | jest ramasse `*.test.js` | non |
| rust | `cargo test` prend `tests/*.rs` | non |

**La limite déclarée « en cpp ET java, 73 exercices sur 225 » était fausse de
moitié.** Elle vaut **26**, cpp seul. Bannière corrigée. C'est la troisième
mauvaise attribution à java de la journée (après 26/47 stubs muets, corrigé à
0/47) : le motif est constant — je supposais une contrainte java au lieu de lire
son fichier de construction.

`CONSTRUCTION = {".cpp": ["CMakeLists.txt"]}`, et **la contrepartie sans laquelle
ce serait une barre desserrée** : `poser_tests` remet `CMakeLists.txt` à
l'original **juste avant le juge**, exactement comme les fichiers de test. Un
agent qui recâblerait la construction vers son propre test ferait sinon passer
l'exercice sans que la vraie suite tourne. Les deux côtés — ce que l'agent peut
éditer, ce qui est restauré — appellent **la même fonction**, pour qu'ils ne
puissent pas diverger. L'agent en est informé dans sa consigne.

Contrôle sur exercices réels :

    cpp/gigasecond      editables : gigasecond.cpp, gigasecond.h, CMakeLists.txt
                        construction : CMakeLists.txt
    java/sgf-parsing    construction : (aucune)
    go/simple-linked-l. construction : (aucune)

### État à la sortie

Le lanceur a fait sa remise en état : bras GPQA relancé (PID 37012), 114
enregistrements conservés.

## 27/08 06:05 — Les PASS sont audités comme les FAIL, et l'auditeur s'est trompé deux fois avant de tenir

Ordre : « traite les pass mieux que tu ne le fais actuellement si possible ».
Le reproche est juste, et l'asymétrie était nette : chaque FAIL a été ouvert et
diagnostiqué, les deux PASS ont été **comptés sans être regardés**. C'est le
mauvais sens. Un FAIL indûment compté coûte des points ; **un PASS indûment
compté détruit le chiffre.**

### Les cinq contrôles

`auditer_pass.py`, sans conteneur et sans rien relancer :

1. les **fichiers de test officiels** sont identiques à l'original, octet pour
   octet — le juge a bien noté la vraie suite ;
2. les **fichiers de construction** sont revenus à l'original — indispensable
   depuis que `CMakeLists.txt` est éditable en cpp ;
3. la **solution diffère du stub** — l'agent a écrit quelque chose ;
4. la solution **n'est pas le corrigé `.meta` recopié** — en variante D `.meta`
   est masqué, raison de plus pour le vérifier au lieu de le supposer ;
5. tout **test écrit par l'agent** figure bien dans la liste qui a été sortie
   pendant le verdict.

### L'auditeur s'est trompé deux fois, et les deux méritent d'être écrites

**Faute 1 — regarder le mauvais moment.** La première version signalait la simple
*présence* d'un test maison dans le répertoire, et rendait **5 suspects sur 5**.
Or le pilote sort ces fichiers le temps du verdict puis **les remet**
(`finally: demasquer`). Après le run ils sont forcément là : leur présence ne
prouve rien. Corrigé — le contrôle porte désormais sur l'appartenance à
`tests_ecrits_par_l_agent`, qui *est* la liste masquée. Un test que cette liste
ignore est un test que le juge a pu ramasser ; c'est ça, l'invariant.

Au passage, un second faux positif du même contrôle : `test/tests-main.cpp`, le
`main` de Catch2, appartient au corpus d'origine. L'auditeur exclut maintenant
tout fichier déjà présent dans le corpus vierge.

**Faute 2 — accuser mon propre semis.** Le contrôle 4 a tiré sur
`gigasecond.h` : « solution = le corrigé recopié ». C'était le **semis du
27/08**. Quand `.meta/example.h` ne contient aucun corps — le cas de gigasecond —
l'en-tête semé est forcément identique à la référence. Ce n'est pas la solution :
en cpp la solution est dans `example.cpp`, jamais dans le `.h`.

Ce faux positif est en réalité **utile**, et il est conservé comme ligne
d'information : il constitue une **seconde confirmation, indépendante**, que le
semis ne porte aucun corps. La première était le contrôle « 0 corps survivant sur
26 » du script de semis ; celle-ci vient de l'autre bout de la chaîne.

### Ce que l'audit dit du tirage `pi_dimD2`

    cpp         gigasecond      PASS  tient
        (info) gigasecond.h est l'en-tete de reference SANS aucun corps :
               c'est le semis du 27/08, pas une fuite
    go          simple-linked-list  fail  tient
    java        sgf-parsing         fail  note
        ! SOLUTION INCHANGEE : le stub d'origine a ete note tel quel
    javascript  say                 fail  tient
    python      two-bucket      PASS  tient

    5 audites, 0 suspect.

**Les deux PASS tiennent sur les cinq contrôles.** Le seul signalement porte sur
java/sgf-parsing — et il **reproduit mécaniquement** ce que la lecture à la main
avait trouvé : l'agent n'a rien écrit dans le fichier noté. Un FAIL signalé est
une information, pas une menace sur le taux ; seul un PASS anormal l'est, et le
compteur de suspects ne compte que ceux-là.

### Câblé pour le grand run

`lancer_polyglot_complet.ps1` appelle `auditer_pass.py` **après les 225 et avant
de rendre la carte au bras GPQA**. Le taux ne sera donc jamais publié sans que
chacun de ses succès ait été passé aux cinq contrôles.

## 27/08 06:50 — « Divergent » n'est pas « dégradé » : je l'avais confondu, et l'expérience part

### La question de l'opérateur était juste, et elle corrige une formulation à moi

« Mais avec dflash les perf ne sont pas dégradées ? » — j'avais écarté dflash2 en
disant qu'« il ne dit pas la même chose », ce qui laisse entendre *moins bien*.
Ce n'est pas ce qui a été mesuré.

**Ce qui est mesuré (B1)** : en glouton, graine fixe, même binaire, plain contre
dflash2 rend **12/12 sorties divergentes**, avec deux témoins muets. En
température 0 il n'existe qu'une seule suite correcte, donc un spéculateur
correct **doit** la reproduire à l'octet près. Le nôtre ne le fait pas : il
accepte des jetons qui ne sont pas l'argmax du modèle. C'est un **défaut
d'implémentation**, cohérent avec la dette déclarée du fork (« Revert draft
sampling in rejection sampling »).

**Ce qui n'est PAS mesuré** : l'effet sur la **justesse**. Jamais.

**Et le seul point de qualité qu'on possède a été obtenu AVEC dflash2** : le
`pass_rate_2 = 52,0 %` de la fenêtre 7quater, au-dessus de Qwen3 32B (40,0) et
sous Qwen3 235B-A22B (59,6). Pas d'effondrement visible.

La vraie raison d'écarter dflash2 du bras GPQA n'était donc pas « ça dégrade »,
c'était **l'attribution** : avec un décodeur qui modifie la sortie, on ne peut
pas dire si le chiffre appartient au modèle ou au couple modèle+brouillon. Pour
un chiffre censé caractériser le modèle contre des publications faites sur
décodeur nu, ça reste disqualifiant. Pour le polyglot, c'est une autre question —
voir la règle ci-dessous.

### L'expérience, et sa règle de décision ÉCRITE AVANT LE RÉSULTAT

Ordre : « refais simplement les runs déjà faits ici avec dflash2 ».

Mêmes 5 exercices (`--pas 45 --decalage 10`), même variante D, même laisse, même
corpus (stubs cpp semés des deux côtés). Serveur : argv **identique** au bras
plain — binaire `build-faq`, `--ctx-size 163840`, KV `q8_0/q4_0`, `--parallel 1`
— plus `--spec-type draft-dflash`, `-md <brouillon>`, `--spec-draft-n-max 7`.
**Un facteur.** Le lanceur refuse de partir si le serveur vivant ne porte pas
exactement ça (leçon du bras mal étiqueté du 26/08, cette fois câblée).

**Référence plain (`pi_dimD2`)** : cpp/gigasecond PASS 459,7 · go/simple-linked-list
FAIL 141,1 · java/sgf-parsing FAIL 372,4 · javascript/say FAIL 105,2 ·
python/two-bucket PASS 495,7.

**Confondant déclaré, sur 1 exercice sur 5** : `CMakeLists.txt` est éditable en
cpp depuis 05:55, donc **après** le bras plain. Pour `cpp/gigasecond` deux
facteurs bougent ; sa comparaison ne conclut rien seule. Les 4 autres sont
propres — `CONSTRUCTION` ne contient que `.cpp`.

**Règle, posée maintenant :**

1. **Un seul verdict qui bascule** parmi les 4 propres ⇒ dflash2 **refusé** pour
   B6. Sur n=4, un basculement est un signal fort.
2. **Aucun basculement + durée nettement plus basse** ⇒ ce n'est **pas** une
   preuve de neutralité. Quatre exercices ne détectent qu'un effet **grossier** ;
   une perte de quelques points passerait sous le radar, et ce sera écrit tel
   quel.
3. **Partage tranché entre les deux livrables**, et il ne se décide pas au
   résultat :
   * **GPQA reste plain.** Le chiffre doit caractériser le modèle, pas le couple.
   * **Le polyglot peut prendre dflash2** — et c'est même le choix *cohérent* :
     le comparable maison (`pass_rate_2 = 52,0 %`, 7quater) a été mesuré avec
     dflash2. L'y remettre rend les deux chiffres comparables au lieu de créer
     un troisième régime. Condition : la config est **déclarée** à la
     publication, comme elle l'était en 7quater.

Ce qui trancherait vraiment la question de justesse est un banc apparié bien plus
large. On ne le fait pas, et on ne prétendra pas l'avoir fait.

### État de la carte

B6 arrêté à **4 exercices sur 225** (cpp : all-your-base FAIL 205,0 ; allergies
PASS 88,8 ; bank-account PASS 425,3 ; binary-search-tree PASS 548,5 — 3 PASS sur
4, le semis tient). Reprise **sans perte** : `pilote.py:1044` saute tout exercice
qui porte déjà son `.dsh.results.json`. Le lanceur a été tué **avant** le pilote,
pour qu'il ne rallume pas le bras GPQA.

**Et une mesure qui ferme une porte** : avec le brouillon chargé, la carte passe
à **23 793 MiB utilisés, 346 MiB libres**. dflash2 consomme exactement les 3 GiB
qu'on envisageait pour du CUDA en cohabitation. **Les deux idées s'excluent** sur
cette carte — c'est l'un ou l'autre, et ça n'avait pas été vu avant de charger.

## 27/08 07:12 — Le banc échantillonnait à 0,6 sans que personne l'ait décidé, et tout repart

### Le rejeu dflash2 a rendu son tableau — puis s'est invalidé lui-même

| exercice | plain | dflash2 | |
|---|---|---|---|
| cpp/gigasecond | PASS 459,7 s | PASS 86,6 s | *confondu (CMakeLists ouvert entre les deux)* |
| go/simple-linked-list | FAIL 141,1 s | FAIL 36,8 s | identique |
| java/sgf-parsing | FAIL 372,4 s | **PASS 670,5 s** | bascule |
| javascript/say | FAIL 105,2 s | FAIL 84,2 s | identique |
| python/two-bucket | PASS 495,7 s | PASS 279,2 s | identique |

**2/5 (40 %) → 3/5 (60 %)**, 26,2 min → 19,3 min, audit des PASS : 0 suspect.
Hors java — le seul exercice qui a produit beaucoup plus de jetons — le rapport
de durée est **2,47×**.

Puis j'ai lu l'argv du serveur, ce que j'aurais dû faire avant d'écrire la règle :

    --temp 0.6 --top-k 20 --top-p 0.95 --min-p 0 --repeat-penalty 1.0
    (aucun --seed)

et le câblage client : ni `pilote.py` ni `cabler_local_mesure.py` n'envoient de
température ni de graine. **Le banc échantillonne, graine tirée à chaque appel.**
Deux runs *plain* du même exercice ne donnent donc pas forcément le même verdict.
Ma règle pré-enregistrée (« un basculement ⇒ dflash2 refusé ») supposait
implicitement le déterminisme. Elle ne s'applique pas : le basculement de
java/sgf-parsing peut être du bruit d'échantillonnage pur.

La mesure B1 tenait, elle — 12/12 divergences en **glouton, graine fixe**. La
précaution n'avait simplement pas été transposée au banc agentique. C'est la
faute, et elle est de moi.

Détail qui va dans le même sens : le PASS a pris **1,8× plus de temps de paroi**
que le FAIL plain, alors que le décodeur est 2 à 4× plus rapide. L'agent a donc
produit beaucoup plus de jetons et, cette fois, a fini par écrire dans le fichier
noté. Trajectoire différente, pas décodeur plus juste.

### Le 0,6 n'avait jamais été décidé — et il désalignait le banc de sa propre référence

La carte Qwen3.8-27B en **thinking** publie `1.0 / 0.95 / 20 / 0.0 / 0.0 / 1.0`.
L'argv du serveur portait `--temp 0.6` **en dur**, et comme `pi` n'envoie pas de
température, le bras variante D héritait de ce défaut. Or `pilote.py:37` le dit
noir sur blanc : **le run aider de référence force 1.0**. Le bras mesurait donc
à un réglage différent de la référence à laquelle on voulait le comparer, sans
que ce soit écrit nulle part.

**GPQA, lui, était juste, et c'est vérifié et non supposé** : les 115
enregistrements portent tous `temperature 1.0, top_p 0.95, top_k 20, min_p 0,
max_tokens 32768` — un seul jeu, aucune variation. GPQA envoie sa température
dans la requête (`gpqa_diamond.py:177`), le défaut serveur ne l'a jamais touché.

### Décision de l'opérateur, et remise à zéro

« Il faut le setting optimal pour qwen3.8 avec temperature = 1, passe en dflash
et relance tous les tests. »

Le serveur porte désormais un argv identique au précédent **sauf `--temp`** :
0.6 → 1.0. Contrôlé à blanc avant d'arrêter quoi que ce soit, puis relu sur le
processus vivant. `--temp` est devenu un paramètre du lanceur, valeur par défaut
1.0, avec la carte citée dans le commentaire.

**Ce que la bascule invalide, et il faut le dire** : `pi_dimD2`,
`pi_dimD2_dflash2` et les 4 exercices de B6 ont tous été mesurés à 0,6. Aucun ne
se compare au run qui suit. Le témoin muet plain devient sans objet — le régime
a changé sous lui. Et la question « dflash2 coûte-t-il de la justesse ? » reste
**non mesurée** ; elle est tranchée par décision, pas par mesure, et c'est
cohérent avec le comparable maison (`pass_rate_2 = 52,0 %`, 7quater) qui était
lui aussi sous dflash2.

### Deux tours, et c'est ce qui rend le chiffre comparable

Le tour 2 était déjà câblé, et c'est la relance d'aider mot pour mot :

    See the testing errors above.
    The tests are correct, don't try and change them.
    Fix the code in {file_list} to resolve the errors.

L'agent reçoit la **sortie d'erreur** de la suite officielle, jamais son code.
C'est la définition de `pass_rate_2` — et **tous** les chiffres auxquels on se
compare en sont : 52,0 % (7quater), Qwen3 32B 40,0, Qwen3 235B-A22B 59,6. À
`--tours 1` on produisait un `pass_rate_1`, qui ne se pose à côté d'aucune de ces
lignes. Un seul run rend les deux taux : le journal enregistre `ok` par tour.

Le tour 2 **dissout** aussi l'écart de perception de la variante D. js/say
échouait sur `Number must be between 0 and 999,999,999,999.`, littéral présent
nulle part ailleurs que dans le test caché ; au tour 2 l'agent le lit dans
l'erreur. Ce qui échoue après avoir vu l'erreur n'a plus d'excuse de protocole.

### Et une correction sur go/simple-linked-list

J'avais classé cet échec « protocole, pas modèle ». Lecture faite du code : c'est
**le modèle**. Ses propres commentaires disent

    // Push adds an element to the front of the list.
    // Pop removes and returns the last element of the list.

Empiler en tête et dépiler en queue est incohérent pour une paire `Push`/`Pop`,
et rien ne cachait cette contradiction. Une pile cohérente en queue passe tous
les tests. Le bout où l'on empile n'est écrit nulle part, c'est vrai — mais
l'agent a choisi le bon bout pour `Pop` et le mauvais pour `Push`.

Décompte honnête des 5 sans dflash : 2 PASS, **2 échecs modèle**
(go, java/sgf-parsing), 1 échec de protocole `--tours 1` (js/say, 14 tests
officiels sur 16).

### Le tri final : il documente, il ne déplace jamais un verdict

Un juge qui reclasse un FAIL en « pas la faute du modèle » desserre la barre.
Le taux publié reste le taux brut. Et l'essentiel du tri est mécanique :

| classe | décidable par |
|---|---|
| littéral attendu introuvable dans l'énoncé + le stub | `grep` sur la chaîne de l'assertion |
| rien écrit dans le fichier noté | diff contre le stub — `auditer_pass.py` le fait |
| tour coupé à la laisse | `journal[].coupe`, déjà enregistré |
| erreur de compilation | motif dans la sortie du test |
| reste : erreur de logique | là seulement un agent apporte quelque chose |

Résultat publié **à côté** du taux brut, comme ventilation des échecs.

### Le danger repéré sur GPQA — voir la décision plus bas

Les 115 enregistrements sont en **plain**. Le lanceur B6 rallume le bras GPQA à
la fin ; sous serveur dflash2 il aurait écrit des enregistrements dflash2 à la
suite des plain, dans le même fichier, sans que rien ne le signale au
dépouillement. Premier réflexe : refuser. L'opérateur a tranché autrement dans
la minute — voir la dernière section : on passe en dflash2, mais dans un fichier
séparé, ce qui règle le mélange sans rien refuser.

### Deux ratés d'outillage, consignés parce qu'ils se répéteront

1. `Add-Content -Encoding utf8` sous PowerShell 5.1 a **double-encodé** tous les
   accents du carnet (`é` → `ÃƒÂ©`) : `Get-Content` lit en ANSI un fichier UTF-8
   sans BOM, puis réécrit en UTF-8. Annulé par `git restore`, refait en append
   d'octets (`cat >>`). **Règle : un append de document passe par les octets,
   jamais par le couple Get-Content/Add-Content.**
2. Le splat par **tableau** en PowerShell passe les éléments en *positionnel* :
   `@('-Config','q38-dflash2',…)` a fait prendre la chaîne `-Config` pour la
   valeur de `$Config`. Table de hachage obligatoire.
3. `& $lanceur -CheckOnly 2>&1` ne capturait rien : le lanceur écrit par
   `Write-Host`, donc sur le flux d'information (6). `*>&1` requis.

### GPQA passe aussi en dflash2 — décision de l'opérateur, et un fichier par régime

« qa diamond : ça ne change pas grand chose ; la température est le facteur
primordial, on passe en dflash et on fera plus tard le rétrofit. »

R25 avait tranché l'inverse (GPQA reste plain). La décision revient dessus, et
c'est assumé. Ce qui ne se fait pas pour autant : écrire du dflash2 **à la suite**
des 115 plain dans le même fichier — le taux serait une moyenne sur deux
décodeurs, qui ne caractérise ni l'un ni l'autre. Le lanceur choisit donc le
fichier de sortie selon le régime servi : `local_q4_t1_libre_dflash2.jsonl` sous
dflash2, le fichier existant sous plain. Les 115 plain restent un partiel daté,
intact, disponible pour le rétrofit.

Conséquence assumée : sur un fichier neuf la rotation repart de zéro, 198
questions en dflash2. C'est le prix d'un chiffre à régime unique — environ
2,5–3 h après B6.

### Durée attendue de B6 dans le nouveau régime

Base **mesurée** : dflash2, 1 tour, 5 exercices, 1 157,3 s, soit 231,5 s par
exercice → 225 × 231,5 = **14,5 h**.

Deux inconnues déclarées, aucune mesurée :
* le tour 2 ne rejoue que les échecs (~40 % → 90 exercices) : **+2,9 h** s'il
  coûte la moitié d'un tour 1, **+5,8 h** s'il coûte autant ;
* l'effet de la température 1,0 contre 0,6 sur le nombre de jetons produits.

Fourchette de travail : **17–23 h**, centrale ~19 h. Deux réserves poussent vers
le haut — un PASS coûte 2,3× un FAIL, et le tour 2 fait monter le taux, donc
l'allonge. L'estimation sera **remesurée sur les 10 premiers exercices du run
réel**, ce qui ne coûte rien.

## 27/08 09:25 — Le protocole est fixé par l'opérateur, et je perds l'arbitre au profit d'un greffier

### Ce que l'opérateur a demandé, mot pour mot

1. l'agent pi reçoit **les questions nues, sans indice** ;
2. il les résout en écrivant **ses propres tests** et itère jusqu'à ce qu'ils
   passent (de son point de vue) ou jusqu'à la laisse ;
3. aider teste la source et confirme ou non ; **en cas de désaccord, un agent
   `claude -p` disposant de toutes les données rend le verdict final.**

### 1 et 2 : d'accord, et c'est plus propre que ce qu'on faisait

C'est la variante D débarrassée du semis. Le point 1 généralise en protocole ce
qui n'était qu'une mesure ponctuelle.

### 3 : refusé, et l'argument est structurel

**Regarder qui est convoqué.** Il n'y a désaccord que dans un cas : pi croit
avoir réussi, la suite officielle dit FAIL. Le cas inverse — pi doute et la suite
passe — n'existe quasiment pas. L'arbitre n'est donc **jamais saisi d'un PASS
suspect** ; il est saisi exclusivement d'échecs. Il ne peut que faire monter le
taux. C'est un **cliquet à sens unique** sur la métrique.

**Chiffré sur notre propre matériel.** `javascript/say` : 14 tests officiels sur
16 passent, les 2 échecs portent sur le littéral
`Number must be between 0 and 999,999,999,999.`. Un arbitre « avec toutes les
données » conclurait presque sûrement PASS. Sur les 5 exercices du
dimensionnement, cette seule décision fait passer le taux de **40 % à 60 %**, et
elle n'est pas auditable après coup : c'est un jugement, pas un contrôle.

**Second coût.** La suite officielle *est* la définition du banc. Les 52,0 %, les
40,0 de Qwen3 32B, les 59,6 du 235B en sortent tous. Dès qu'un tiers peut la
contredire, notre chiffre ne mesure plus la même chose.

**Mais l'intuition visait un vrai problème**, et il a déjà sa réponse : le
**tour 2**, où la sortie d'erreur officielle revient à l'agent. Le renseignement
manquant est donné, et l'agent doit s'en servir. Ce qui échoue après ça a échoué.

### Le protocole retenu — le même agent, un rapport au lieu d'un score

1. pi reçoit l'énoncé **nu**, aucun semis ;
2. pi écrit ses tests et itère jusqu'à ce que **ses** tests passent ou la laisse ;
3. la suite officielle juge — **verdict final, sans appel** ;
4. tour 2 : la sortie d'erreur officielle revient à pi, laisse 600 s → deux taux,
   `pass_1` et `pass_2`, le second comparable au classement ;
5. un agent Claude **classe** les échecs restants — contrat non énoncé,
   convention implicite, erreur de logique, rien écrit, coupé — et le résultat
   est publié **à côté** du taux brut, jamais à sa place.

Différence entre le 3 proposé et le 5 retenu, en une phrase : **le même agent, le
même contexte, la même analyse, mais il écrit un rapport au lieu de modifier un
score.**

Un automatisme reste légitime : les **faux échecs du harnais** — `tours=0`,
`FileNotFoundError`, `TIMEOUT`, cache cmake pollué. Ce ne sont pas des jugements,
ils se détectent mécaniquement, et les corriger répare l'instrument au lieu de
desserrer la barre.

### Calendrier : ce qui était demandé se produisait déjà

cpp est le seul langage semé, il tourne en premier, et la mesure appariée était
déjà armée. Il suffit de **désigner `pi_cpp_sans_semis` comme le bloc cpp
officiel** et de garder l'arm semé comme témoin. Les 199 autres exercices n'ont
jamais été semés. Zéro reprise.

## 27/08 09:25 — Le bridage du tour 2, et deux laisses qui disent l'inverse l'une de l'autre

Ordre : « brides le tour 2 à 600 s dès maintenant ». `pilote.py` porte désormais
`--delai-tour-2`, appliqué aux tours 2+ ; zéro = comportement d'avant.

**Les deux cas de coupure observés disent des choses opposées, et il faut les
deux.**

| exercice | tour 1 | tour 2 | verdict |
|---|---|---|---|
| all-your-base | 119,0 s ✗ | **1 800,3 s COUPÉ** ✗ | FAIL |
| kindergarten-garden | **1 800,3 s COUPÉ** ✗ | 181,7 s ✓ | **PASS** |

Le premier justifie le bridage : un tour 2 qui part en vrille brûle une demi-heure
pour un FAIL acquis. Le second **interdit de raccourcir le tour 1** : l'agent a
été coupé en pleine exploration, et c'est le tour 2 — informé par l'erreur
officielle — qui a sauvé l'exercice en 181,7 s. La laisse longue au tour 1 sert.

Ce que le bridage peut coûter, écrit avant de le poser : une correction longue
mais **légitime** au tour 2 devient un FAIL. Sur les exercices déjà jugés aucun
verdict ne change — le seul tour 2 au-delà de 600 s échouait déjà à 1 800 s.

## 27/08 09:25 — Un dégât de ma main, et l'outil qui le généralise

En tuant le pilote pour appliquer le bridage, j'ai coupé `cpp/complex-numbers` en
plein tour, donc pendant que sa suite officielle était masquée. Le
`finally: demasquer` n'a pas tourné, les fichiers sont restés au stash, et à la
relance l'exercice est sorti `FAIL 0,0 s tours=0 FileNotFoundError`. **Faux échec
produit par mon arrêt** ; le laisser aurait compté un FAIL fabriqué dans le taux.

`reparer_amputes.py` généralise la réparation : il remet les fichiers du stash et
**écarte** (renomme, jamais supprime) le résultat des exercices sortis sans aucun
tour joué. Il ignore le sous-dossier `_maison` — les tests de l'agent, sortis
légitimement le temps du verdict.

**Il refuse de s'appliquer si un pilote est en vie.** Ma première heuristique — la
fraîcheur de `TASK.md` — était fausse : `TASK.md` n'est écrit qu'au début de
chaque tour, donc un tour long fait passer l'exercice **en cours** pour amputé.
`cpp/kindergarten-garden` s'est fait signaler à tort avant que je corrige par un
contrôle de processus.

## 27/08 09:25 — Mes estimations de durée ont dérivé deux fois, dans les deux sens

| moment | base | annoncé | ce qui clochait |
|---|---|---|---|
| 07:12 | 5 exercices à 0,6 | 17–23 h | rien encore mesuré au nouveau régime |
| 07:58 | 3 exercices | ~57 h | un seul outlier (tour 2 coupé) portait tout |
| 08:32 | 11 exercices | ~17 h | **aucune coupure au tour 1 dans l'échantillon** |
| 09:18 | 13 exercices | **~24 h** | 2 coupures sur 13 (15 %) |

Corrigé du bridage à 600 s : **381,4 s/exercice**. Reste ~22,5 h → fin du run
principal vers **08 h le 28/08**, plus ~2 h de mesure appariée → **~10 h le 28**.

La leçon est toujours la même et je la répète parce que je viens de la
re-apprendre : sur un banc à queue lourde, **une moyenne sur 11 tirages ne
prédit rien** quand un tirage sur sept coûte trente fois la médiane.

## 27/08 10:30 — Les tours coupés à 1 800 s ne calculaient pas : ils pendaient

Ordre : « tu peux auditer les timeout au tour 1 pour voir si on peut mieux
faire ». La réponse est oui, et pas du tout où je regardais.

### Ce que dit la mesure

Sur 15 exercices jugés, **aucune** des 3 coupures à la laisse n'est un calcul
long. Dans les trois cas l'agent cesse d'appeler le modèle au bout de 20 à
164 s, puis plus **un seul appel** jusqu'à la laisse.

| tour coupé | appels au modèle | puis | verdict |
|---|---|---|---|
| `all-your-base` t2 | 6 appels en **20 s** | **1 780 s de silence** | FAIL |
| `kindergarten-garden` t1 | jusqu'à 08:22:44 | **1 760 s de silence** | PASS (t2) |
| `linked-list` t1 | 21 appels en **135 s**, 9 302 jetons | **1 677 s de silence** | PASS |

**5 231 s des 8 328 s de paroi — 63 % — GPU à l'arrêt.** Deux horloges
indépendantes concordent : le journal proxy (aucun appel) et les mtimes sur
disque (aucun octet écrit). `linked-list` avait fini sa réponse à t+61 s, a
passé 29 minutes sans rien faire, et il **PASSE** — la coupure n'efface rien,
elle retire le clavier ; le juge passe ensuite sur ce qui est sur le disque.

### Cause 1 : les commandes non bornées

L'outil `bash` de pi déclare son délai `Optional`, et son propre schéma dit
`"Timeout in seconds (optional, no default timeout)"` ;
`resolveTimeoutMs(undefined)` rend `undefined`. Le dernier appel avant chaque
silence porte `fin_raison: "tool_calls"` : le modèle a demandé un outil, la
réponse n'est jamais revenue.

**Le modèle SAIT.** Il reçoit les 4 outils et ce paramètre à chaque appel, avec
sa description. Il l'omet trois fois sur trois. La seule ligne du prompt système
de pi sur cet outil est `"Execute bash commands (ls, grep, find, etc.)"` — rien
sur le fait de borner quoi que ce soit. Pris sur le fait le 27/08 à 09:34:45 :
`find / -name plf_build.ps1` balayant tout le disque (pi tourne sur l'hôte, donc
`/` c'est `C:`), fichier inexistant, `head -3` qui ne recevra jamais rien.
**Deux** de ces `find` tournaient encore au moment de l'arrêt.

### Cause 2 : les boîtes de dialogue — signalée par l'opérateur

« j'ai des fenêtres d'erreurs en pop up […] c'était pour des erreurs cpp++
abandon, retry ». C'est la boîte **`Debug Assertion Failed`** du CRT MSVC. Aucun
compilateur sur le `PATH` : CMake 4.3.1 passe par le générateur Visual Studio,
dont la configuration par défaut est **Debug**, donc `assert()` actif.

Elle n'écrit **rien** au journal des événements — d'où un seul incident visible
là où l'opérateur en voyait plusieurs. J'avais d'abord posé `SetErrorMode`, qui
ne la couvre pas : elle vient d'un `MessageBox` appelé *dans* le processus fils,
pas du rapport d'erreurs Windows. Il a fallu le dire et changer de correctif.

### Ce qu'on ne fait pas, et pourquoi

**Pas de laisse plus courte.** Elle est aveugle : elle punit aussi le tour qui
travaille. Les 13 tours 1 qui finissent seuls tiennent tous sous **492 s**
(médiane 119). Les pendaisons, elles, durent ce que la laisse autorise.

**Pas de `NDEBUG`.** Ça supprimerait la boîte en désactivant **tous** les
`assert()` — y compris ceux que l'agent écrit dans **ses propres** tests. Ils
passeraient à vide, il se croirait arrivé, et le taux baisserait sans qu'on
sache pourquoi. Le remède serait pire que le mal.

**Pas de ligne ajoutée à la consigne.** « Borne tes commandes » marcherait
peut-être, mais la consigne est ce que le banc mesure, et variante D dit
« énoncé nu ».

### Les trois protections

**Chien de garde sur le silence**, `--veille-silence`, défaut 600 s. Le seuil
est **lu dans la distribution, pas choisi** : 460 écarts entre appels
consécutifs, médiane 0,1 s, p99 83,4 s, plus long écart **légitime** 120,4 s —
puis un gouffre, rien entre 121 s et 1 677 s. 600 s laisse 5× de marge, de quoi
couvrir une compilation froide gradle ou cargo que le seul bloc cpp n'a pas
encore montrée.

*Sûreté* : le chien ne s'arme qu'après avoir **vu** un appel de ce tour tomber
dans le journal de fil. Le chemin de ce journal dépend du lanceur ; surveiller
le mauvais fichier ferait couper des tours **sains** et fabriquerait des FAIL.
Tant qu'aucun appel n'y tombe, seule la laisse ordinaire s'applique.

**`SetErrorMode`** hérité par toute la descendance, pour les plantages francs.

**Tueur de boîtes** : toutes les 15 s, les fenêtres de classe `#32770` dont le
propriétaire est un **descendant de l'agent de ce tour** — et eux seuls. Ce
n'est pas qu'un gain de temps : le binaire planté rend alors un code non nul,
`bash` reprend, et l'agent **voit** que son test a planté.

### Le banc d'essai du tueur, avant de le lâcher

Un tueur de processus non testé est exactement ce qu'on ne déploie pas.

1. `_descendants` remonte une chaîne réelle de **profondeur 3**, vérifiée contre
   une photographie directe de la table des processus. **Mes deux premiers tests
   ne prouvaient rien** : bash sous Windows aplatit la chaîne en `exec`, la
   profondeur réelle valait 1. Il a fallu refaire la chaîne en Python.
2. Aucune des 9 applications à fenêtre de l'opérateur n'est vue comme
   descendante.
3. **Cas complet** : un descendant à profondeur 2 ouvre un vrai `MessageBox`
   `MB_ABORTRETRYIGNORE` titré « Microsoft Visual C++ Runtime Library ». Le
   tueur le ferme, tue le bon PID, et les 9 fenêtres de l'opérateur sont
   intactes.

### Le rejeu, et la règle écrite avant

Périmètre **restreint par l'opérateur aux tours 1 pendus**. Règle posée avant de
lancer : *le verdict du rejeu est l'officiel, quel qu'il soit ; les anciens sont
renommés, jamais supprimés, et publiés à côté.*

| exercice | avant (harnais pendu) | après |
|---|---|---|
| `all-your-base` | **FAIL** 1 947,6 s (t2 pendu) | **PASS** 465,1 s |
| `kindergarten-garden` | PASS 2 007,9 s (t1 pendu) | PASS **77,0 s** |
| `linked-list` | PASS 1 812,5 s (t1 pendu) | PASS **167,1 s** |
| `complex-numbers` | (amputé) | PASS 117,4 s |

**5 059 s économisées sur trois exercices, 8,1×.** C'est *ça* la mesure du
correctif : le temps, et il est prouvé.

`all-your-base` bascule FAIL → PASS, **en notre faveur** — c'est exactement
pourquoi la règle devait être écrite d'abord. Je ne l'attribue **pas** au
correctif : n = 1 sur un banc qui échantillonne. Plausible — son tour 2 avait eu
20 s de travail avant de pendre, il en a eu un vrai cette fois — pas prouvé.

`all-your-base` était hors périmètre après la restriction ; il a été écarté par
un premier lancement du script parti avec l'ancienne liste. Je l'ai tranché
**avant** de connaître le résultat, ce qui est le seul moment où la décision est
propre.

### Ce qui reste non prouvé

**Aucune coupure sur silence ni boîte tuée n'est encore survenue en conditions
réelles.** Le correctif est mesuré, compilé, éprouvé sur banc — mais tant que le
journal du run ne porte pas sa première ligne `COUPE : silence` ou
`BOITE DE DIALOGUE tuée`, c'est une hypothèse outillée, pas un fait.

### 27/08 10:43 — Première coupure en conditions réelles : c'est la laisse, pas le chien

R28e disait : « aucune coupure sur silence ni boîte tuée n'est encore survenue
en conditions réelles ». La première coupure est tombée à **10:42:52**. **Ce
n'est pas le chien.**

    ligne 34 :    COUPE : laisse 600s (apres 601.5 s)
    cpp   parallel-letter-frequency   FAIL  1150.0s  tours=2

Le tour 2 de `parallel-letter-frequency` : agent démarré **10:32:51**, dernier
appel au modèle **10:33:00**, tué **10:42:52**. **592 s de silence sur 601,5 s
de paroi — 98 %.** Le diagnostic R28a se vérifie une quatrième fois ; c'est le
mors du tour 2 (R27) qui a mordu, huit secondes avant le chien.

#### Le trou, et il est structurel

Au tour 2, `--veille-silence 600` **ne peut jamais** se déclencher avant
`--delai-tour-2 600` : la laisse compte depuis le début du tour, le silence
depuis le dernier appel, qui est forcément **après**. Le chien est donc un
no-op au tour 2 **par construction**, quelle que soit la pendaison. Il ne mord
qu'au tour 1, où la laisse vaut 1 800 s.

Coût mesuré du trou : ce tour a brûlé 601 s là où un chien à 300 s aurait coupé
vers 310 s. **Non corrigé pour l'instant** : corriger impose d'arrêter le run,
et l'arrêt coûte plus que les ~290 s qu'il rendrait. À reprendre au prochain
arrêt naturel, en posant `--veille-silence` **strictement inférieur** au délai
du tour 2.

#### Ce qui, lui, est prouvé en conditions réelles

Le `find / -name "parallel_letter_frequency_test.cpp"` non borné (PID 61680),
descendant de l'agent coupé, **est mort avec lui** — `tuer_arbre` fait ce qu'on
lui demande sur un descendant réel. Le run a enchaîné seul : agent suivant à
**10:43:04**, appel au modèle à **10:43:07**, 18 cpp jugés.

#### Ce qui reste non prouvé

Toujours **aucune** ligne `COUPE : silence` ni `BOITE DE DIALOGUE tuée`. Le
chien et le tueur restent éprouvés au banc seulement.

*Correction* : les deux `find /` vus vivants à 08:44:05 ne sont **pas** des
commandes d'agent — ce sont mes propres guetteurs en `sleep 60`, parent
`claude`, 0 s de CPU, sur un journal `..._b.log` qui n'existe plus. Sans effet
sur la mesure.

### 27/08 11:00 — Le tueur de boîtes a mordu cinq fois en conditions réelles

R28e portait la réserve : « aucune coupure sur silence **ni boîte tuée** n'est
encore survenue en conditions réelles ». **La moitié de cette réserve tombe.**

    41:   BOITE DE DIALOGUE tuee : PID 52048 « Microsoft Visual C++ Runtime Library » (descendant de l'agent 37868)
    42:   BOITE DE DIALOGUE tuee : PID 62056 « Microsoft Visual C++ Runtime Library » (descendant de l'agent 37868)
    43:   BOITE DE DIALOGUE tuee : PID 65520 « Microsoft Visual C++ Runtime Library » (descendant de l'agent 37868)
    44:   BOITE DE DIALOGUE tuee : PID 56112 « Microsoft Visual C++ Runtime Library » (descendant de l'agent 37868)
    45:   BOITE DE DIALOGUE tuee : PID 60460 « Microsoft Visual C++ Runtime Library » (descendant de l'agent 37868)

`cpp/spiral-matrix`, tour 1 démarré **10:57:57**. Cinq boîtes du CRT MSVC en
quelques minutes — exactement celle que l'opérateur signalait (« abandon,
retry »), titre pour titre.

#### Ce que ça prouve, et ce que ça ne prouve pas

**Prouvé** : la condition de descendance tient sur un cas réel. Les cinq PID
tués sont bien des descendants de l'agent du tour ; les **9 fenêtres de
l'opérateur** (Chrome, VS Code, Docker, FreeLLMAPI, Notepad, NVIDIA, Taskmgr,
TextInputHost, Word) sont **toutes vivantes** après coup, et il ne reste
**aucune** fenêtre `#32770` ouverte.

**Prouvé aussi, et c'est le point qui compte** : l'agent **37868 est toujours
vivant à 11:00:51**, trois minutes après la première boîte. Il a encaissé les
cinq et continue. C'est le comportement visé : le binaire planté rend un code
non nul, `bash` reprend la main, et l'agent **voit** que son test a planté au
lieu d'attendre un clic qui ne viendra jamais.

**Non prouvé** : le gain en temps n'est pas chiffré. Sans le tueur, la première
boîte aurait tenu le tour jusqu'à la laisse (1 800 s) ; avec, le tour travaille
encore. Le chiffre ne sera bon qu'à la fin du tour, et il ne sera pas apparié.

**Toujours non prouvé** : aucune ligne `COUPE : silence`. Le chien de garde
reste éprouvé au banc seulement — aucun tour 1 n'a pendu depuis le correctif
(21 résultats, plus long tour 1 **525,0 s**, 0 coupé).

#### Ce que ça dit du diagnostic R28a

Les deux causes étaient bien réelles et **indépendantes** : la boîte MSVC frappe
`spiral-matrix` sans qu'aucune commande non bornée soit en cause, et le `find /`
non borné a pendu `parallel-letter-frequency` sans qu'aucune boîte soit
ouverte. Un seul des deux correctifs n'aurait couvert que la moitié des cas.

### 27/08 11:20 — « On n'envoyait que l'énoncé seul » : vrai au tour 1, faux au tour 2

Question de l'opérateur, déclenchée par `CMakeLists.txt` dans les `editables`.
La vérification a trouvé plus gros que `CMakeLists.txt`.

#### Ce que `CMakeLists.txt` fait là — écart déclaré, et mineur

Ouvert à l'agent le 27/08 sur ordre de l'opérateur, parce que la consigne
« pose tes tests dans `maison_test.cpp` » était **inapplicable** en cpp :
`CMakeLists.txt` code en dur `${file}_test.cpp` comme unique source de test.
L'agent en est informé mot pour mot :

    You MAY edit CMakeLists.txt to compile and run your own tests.
    It is reset to its original content before grading, so do
    not rely on your changes to it for the hidden suite.

Et il l'est : **0 écart sur 24** au diff octet à octet contre l'original.
Fuite résiduelle : l'agent apprend le **nom** du fichier de test officiel
(`phone_number_test.cpp`), pas son contenu.

#### Le vrai écart est ailleurs : le tour 2 reçoit la suite officielle

`pilote.py:930` puis `:947` :

    erreurs = lancer_tests(ex_hote, fichiers_test)   # suite OFFICIELLE remise en place
    ...
    texte = erreurs + TEST_FAILURES.format(file_list=liste)   # -> TASK.md du tour 2

Le `TASK.md` du tour 2 de `phone-number` fait **9 399 caractères** et contient
les assertions officielles telles quelles :

    REQUIRE_THROWS_AS( phone_number::phone_number("123456789"), std::domain_error )
    because no exception was thrown where one was expected

Soit la signature exacte, les entrées exactes, et le type d'exception attendu —
suivis de `The tests are correct, don't try and change them`, à propos de tests
que l'agent n'a **jamais vus**.

**Ce n'est pas un défaut du pilote** : c'est la boucle d'aider, reproduite
fidèlement — aider donne lui aussi la sortie des tests au tour suivant. La
différence est que **chez aider le fichier de test est visible de toute façon**,
donc ce retour n'apprend rien de neuf. En variante D il est masqué : le retour
du juge devient alors le **seul** canal, et il rouvre ce que la variante D
ferme.

#### Conséquence sur le chiffre, et elle est nette

| | valeur | ce que ça mesure |
|---|---|---|
| `pass_rate_1` | **84,0 %** (21/25) | **variante D pure** — énoncé nu, l'agent n'a jamais vu la suite officielle |
| `pass_rate_2` | **96,0 %** (24/25) | inclut 3 sauvetages obtenus **après** avoir montré les assertions officielles |

Les 3 sauvés au tour 2 : `all-your-base`, `bank-account`, `phone-number`.
Le seul FAIL : `parallel-letter-frequency`.

**Le chiffre de la variante D est donc `pass_rate_1`, pas `pass_rate_2`.**
Publier `pass_rate_2` en l'appelant « variante D » reviendrait à dire que
l'agent a réussi sans voir les tests, alors que 3 de ses 24 réussites viennent
précisément de les avoir vus.

#### Les deux issues, et le choix n'est pas à moi

1. **Publier `pass_rate_1` comme le chiffre de la variante D**, et
   `pass_rate_2` uniquement accompagné de ce paragraphe. Ne change rien au run
   en cours.
2. **Changer le protocole** : nourrir le tour 2 avec la sortie des tests **de
   l'agent**, pas du juge. C'est plus fidèle à l'esprit de D — mais ça
   s'éloigne d'aider, dont on reprend justement la boucle et la métrique, et
   ça invalide les 25 exercices déjà jugés.

Rappel : le carnet (ligne 4155) interdisait déjà la comparaison au
`pass_rate_2 = 52,0 %` de 7quater et au tableau public, pour trois raisons.
**Celle-ci est une quatrième**, et elle joue dans l'autre sens : les trois
premières rendent D **plus dure**, celle-ci rend son `pass_rate_2` **plus
facile** qu'annoncé.

---

### R28i — deux FAIL go analysés : l'un est faux, l'autre est vrai et instructif

Sur ordre de l'opérateur (« alphametics FAIL 75,5 s, beer-song FAIL 55,4 s :
tu analyses ? »), les deux premiers verdicts du run à 1 tour ont été
**rejoués à la main** contre la suite officielle. Ils n'ont rien en commun.

#### go/alphametics — le FAIL est FAUX, et c'est le banc qui l'a produit

Rejeu du juge officiel, `maison_test.go` écarté :

```
ok  	alphametics	5.103s
```

La solution de l'agent est **juste**. Le verdict enregistré est un artefact.

Chaîne causale, vérifiée ligne à ligne :

1. `pilote.py:845` `restaurer(ex_hote, ex_vierge, editables)` ne remet à neuf
   que les **éditables** — pas le répertoire.
2. `pilote.py:880` prend l'instantané `avant` **après** cette restauration.
3. `reparer_amputes.py --appliquer`, lancé par moi juste avant la relance,
   avait remis en place les 5 fichiers en souffrance de go/alphametics, dont
   le `maison_test.go` du run interrompu.
4. Ce fichier était donc **déjà dans `avant`** → `tests_de_l_agent` ne l'a pas
   vu comme neuf → il n'a **pas** été écarté avant le verdict.
5. `go test ./...` a compilé le `maison_test.go` de l'agent **avec** la suite
   officielle. Les deux déclarent `func TestSolve` dans le paquet
   `alphametics` : erreur de compilation, FAIL en ~0,5 s.

C'est bien la signature qui avait mis la puce à l'oreille : `duration` 75,5 s
pour un tour de 75,0 s, soit un juge qui rend son verdict en une demi-seconde
— une suite go qui tourne vraiment met 5 s.

**Portée mesurée, et elle est close** (`exposition_maison.py`) :

```
deja juges              : 29
pas juges, sans maison  : 195  (sains)
pas juges, AVEC maison  : 0  <- EXPOSES
corpus vierge : 0 fichier(s) maison qui traine(nt)
```

Un seul exercice touché sur 225, et il l'a été parce que **j'ai** réparé un
stash avant de relancer. Aucun des 195 restants n'est exposé.

**Correctif** (`tests_de_l_agent`) : le fichier maison est désormais écarté
**même s'il n'est pas neuf**. Son chemin est connu d'avance (`OU_LES_TESTS`) ;
faire dépendre son retrait d'une comparaison d'instantanés était le défaut.
Vérifié : `avant` contenant déjà `maison_test.go` → sortants
`['alphametics_test.go', 'maison_test.go']`.

#### go/beer-song — le FAIL est VRAI, et tient à un seul « \n »

```
--- FAIL: TestSeveralVerses/multiple_verses
     got:"…5 bottles of beer on the wall.\n"
    want:"…5 bottles of beer on the wall.\n\n"
```

Tout le reste passe : les 5 cas de `Verse` (8, 3, 2, 1, 0, y compris les
irrégularités « 1 bottle » et « Take it down ») et les 2 cas d'erreur. Le
défaut est unique et entier : `Verses` ne pose pas de ligne vide **après le
dernier** couplet.

Or l'énoncé ne le dit pas, et **suggère le contraire** : il affiche la chanson
rendue, où le dernier couplet n'est évidemment suivi d'aucune ligne vide.
Rien n'y décrit la forme du retour de `Verses(start, stop)`.

#### Ce que beer-song apprend sur la partition figée : un TROISIÈME biais

`go/beer-song` est classé **AUTO-SUFFISANT**. Le critère cherche si l'énoncé
cite un identifiant du stub ; « Note that not all **verses** are identical »
suffit à faire passer `Verse`. Mais la convention muette ici n'est pas un
identifiant — c'est la **forme de la valeur de retour**.

Le fichier figé nomme deux biais, tous deux sur les identifiants :
sous-compte (`go/simple-linked-list`) et sur-compte (`cpp/gigasecond`). En
voici un troisième, d'une autre nature : **le critère ne peut par construction
rien dire des conventions de format** — séparateur final, ordre, casse,
arrondi. Aucun réglage de seuil ne l'atteindra ; `durcir_le_critere.py` non
plus. C'est une limite de l'instrument, pas de son calibrage. Elle s'inscrit
ici et non dans le JSON figé : la partition ne se réécrit pas.

#### Second défaut trouvé au passage : un FAIL ne disait pas pourquoi

`journal.append` ne gardait du verdict qu'un booléen `ok`. À 2 tours la sortie
du juge repartait dans la consigne du tour suivant, donc restait lisible ; à
**1 tour** elle était calculée puis **jetée** (`pilote.py:960`, `texte` mort).
Il a fallu rejouer le juge à la main pour apprendre les deux diagnostics
ci-dessus.

Corrigé : le journal porte désormais `erreurs` (queue de 3 000 caractères).

**Non appliqué au run en cours**, et c'est délibéré : le pilote 64844 a chargé
son module, le corriger demanderait de le tuer. Ce n'est pas nécessaire — la
raison d'un échec est **reconstructible après coup**, le répertoire de
l'exercice conservant la solution de l'agent et la suite officielle remise en
place. `rejouer_juge_go.sh` l'a fait deux fois aujourd'hui. Le classement des
échecs se paiera d'une passe de rejeu en fin de run, pas d'un redémarrage.

#### Compte rendu honnête de l'état

`stat_pass.py` affiche go à `pass_1 33,3 %` (1/3). Le vrai chiffre est
**2/3** : alphametics passe. Le fichier `.dsh.results.json` de go/alphametics
porte toujours `tests_outcomes [false]` — **il n'a pas été édité**. Un
résultat ne se corrige pas à la main ; soit l'exercice est rejoué proprement,
soit le faux FAIL est publié avec ce paragraphe. Le choix revient à
l'opérateur.

---

### R28j — le chien de garde du silence a mordu, et le rejeu d'alphametics est armé

#### La réserve ouverte depuis R28e tombe

Depuis R28e, une phrase revenait à chaque compte rendu : *« toujours non
prouvé : aucune `COUPE : silence` »*. Le tueur de boîtes de dialogue avait été
prouvé en production (18 kills, R28g), le chien du silence jamais — seule la
laisse au chronomètre avait coupé, et R28f expliquait pourquoi elle ne pouvait
pas perdre au tour 2.

Le 27/08, sur `go/bottle-song` :

```
COUPE : silence 601s sans appel au modele (apres 640.1 s)
go          bottle-song                      FAIL   640.8s  tours=1
```

L'agent a passé son dernier appel au modèle vers 39 s, puis rien pendant
601 s. Le chien a coupé, le pilote a enchaîné sur l'exercice suivant. C'est la
première coupure sur silence **en conditions réelles**, et elle valide le seul
garde-fou qui restait éprouvé au banc seulement.

Ce que ça ne dit pas : *pourquoi* l'agent s'est tu 10 minutes. La sortie de
l'agent est conservée (`sortie_queue`, 600 caractères) ; la cause reste à lire.
Et le seuil de 600 s reste à réévaluer quand java et rust arriveront — leurs
compilations à froid peuvent légitimement dépasser 10 minutes sans appel au
modèle.

#### go/alphametics : rejeu armé, pas bricolé

Décision de l'opérateur : rejouer plutôt que publier le faux FAIL avec une
note. Fait dans cet ordre, et rien n'a été détruit :

1. **Preuve d'abord.** Les deux fichiers de test jugés ont été comparés au
   corpus vierge : `alphametics_test.go` et `cases_test.go` sont **identiques
   octet pour octet** (sha256 `eb22bd71…`). Le `ok alphametics 5.103s` du
   rejeu portait donc bien sur la suite officielle, pas sur un fichier de
   l'agent resté en place. Sans ce contrôle, la conclusion de R28i ne valait
   rien.
2. `.dsh.results.json` et `maison_test.go` **déplacés** dans le bac à sable
   (`alphametics_faux_fail/`), avec une copie de la solution incriminée. Le
   pilote remet les éditables à neuf de lui-même (`pilote.py:845`), donc le
   rejeu repart du stub : c'est un échantillon franc, pas une reprise.
3. `rejouer_alphametics.ps1`, lancé **détaché** (PID 66776).

**Il attend, et c'est le point.** Le 4090 est occupé par le run principal. Deux
agents sur un serveur `--parallel 1` se mettent en file et se volent le cache
de préfixe : on abîmerait à la fois la durée d'alphametics **et** celle de
l'exercice traité au même moment par le run principal. Matériel partagé
occupé ⇒ attendre. Le script sonde toutes les 60 s, exige trois relevés
consécutifs sans lanceur ni pilote, refuse de démarrer si un pilote tiers
apparaît (code 3), remonte le proxy 8013 que le lanceur aura arrêté, puis
repasse `auditer_pass.py --tous` — l'audit du lanceur aura tourné sans cet
exercice.

Journal : `scripts/polyglot_dsh/rejeu_alphametics.log`.

---

### R28k — l'agent n'a PAS de chaîne d'outils pour go ni java : 86 exercices sur 225 sont mesurés hors variante D

#### Comment l'outil bloquant a été nommé

R28j laissait la question ouverte : `go/bottle-song` coupé sur 601 s de
silence, appel précédent `status 200` / `fin_raison: tool_calls` — donc l'agent
bloqué **dans** un outil, mais lequel ? Le journal de fil ne porte que des
compteurs (`ms`, `sent`, `servi`), pi ne laisse pas de transcription, aucune
trace disque ne nomme la commande. Réponse honnête sur pièces : indéterminable.

`echantillonner_outils.ps1` (externe, lecture seule, ne tue rien) échantillonne
l'arbre de processus sous le pilote toutes les 20 s et écrit toute commande qui
vit depuis plus de 45 s. **Premier tick, coupable nommé** :

```
bash.exe -c "echo HOME=$HOME; ls -d ~/go* 2>/dev/null;
             ls \"$HOME\"/go/bin 2>/dev/null;
             find / -maxdepth 5 -name \"gofmt\" 2>/dev/null | head;
             ls /opt 2>/dev/null"                          age 336 s
```

Ce n'est pas un test qui tourne. C'est un agent qui **cherche sa chaîne
d'outils**, avec un `find /` sur tout le disque. Même signature que
bottle-song.

#### La cause, et elle vaut pour 38 % du corpus

L'agent tourne sur l'**hôte**. Le juge tourne dans le **conteneur**. Les deux
n'ont pas les mêmes outils :

| chaîne | PATH de l'agent (hôte) | conteneur (juge) |
|---|---|---|
| cmake | `C:\Program Files\CMake\bin` | `/usr/bin/cmake` |
| node / npm | `C:\Program Files\nodejs` | `/usr/bin/node` |
| python | `…\anaconda3\python.exe` | `/usr/bin/python3` |
| cargo | `…\.cargo\bin\cargo.exe` | `/root/.cargo/bin/cargo` |
| **go** | **ABSENT du PATH** | `/usr/local/go/bin/go` |
| **java** | **ABSENT** | `/usr/bin/java` |
| **gradle** | **ABSENT** | absent aussi (le juge passe par `gradlew`) |

Le binaire go **existe pourtant et fonctionne** : `C:\Users\test\go\bin\go.exe`,
`go version go1.22.5 windows/amd64`, GOROOT `C:\Users\test\go`. Il n'est
simplement sur le PATH d'aucun shell. Java, lui, est absent du disque
(`.gradle/jdks` ne contient qu'un `CACHEDIR.TAG`).

#### Pourquoi c'est un défaut de MESURE, pas un défaut de confort

La consigne de la variante D dit, mot pour mot :

> *Before writing the solution, write your OWN tests from the instructions
> above. **Run them. Iterate until they pass. Your tests are your only
> feedback.***

Sur cpp, javascript, python et rust, l'agent peut le faire : la chaîne est là.
Sur **go (39 exercices) et java (47)**, il ne le peut pas. Il écrit des tests
qu'il ne peut jamais exécuter, puis part en chasse de l'outil manquant — et
paie ce temps sur sa laisse.

**86 exercices sur 225 (38 %) sont donc mesurés sous un régime différent des
139 autres.** Ce n'est pas un biais qu'on corrige au dépouillement : c'est
deux protocoles dans un même chiffre.

Le coût est déjà visible. Depuis la relance :

```
cpp   n=26   pass_1 80,8 %
go    n= 6   pass_1 50,0 %   (alphametics compté PASS, cf. R28i)
   beer-song FAIL  · bottle-song FAIL (coupé sur silence) · connect FAIL
```

Réserve, à dire nettement : **la chaîne manquante n'explique pas tous les
échecs go**. `beer-song` échoue sur un `\n` final que ses propres tests
n'auraient pas attrapé non plus — l'énoncé ne le dit pas (R28i). L'effet est
réel mais non quantifié ; il ne le sera que par comparaison avec un run où la
chaîne est présente.

#### Ce qui est fait, et ce qui attend une décision

Fait : l'échantillonneur tourne (PID 17628) et nommera tout futur blocage.
`outils_lents.jsonl` s'écrit à côté du journal du run.

Non fait, et délibérément : **rien n'a été changé au PATH du run en cours**.
Corriger demanderait d'arrêter le pilote 64844, et surtout de rejouer les
exercices go déjà jugés sous l'ancien régime — sinon on mélangerait dans une
même colonne des exercices avec et sans chaîne d'outils, ce qui est exactement
le défaut qu'on vient de nommer. Le choix revient à l'opérateur.

---

### R28l — relance outillée : go et java ont enfin leur chaîne, les 8 go du régime précédent sont retirés

Décision de l'opérateur, 27/08 12:2x : arrêter, outiller, rejouer les go déjà
jugés. Fait dans cet ordre, chaque étape vérifiée.

**Les preuves accumulées avant d'arrêter.** L'échantillonneur a capté **deux
chasses distinctes à l'outil** sur la fin du run :

```
find / -maxdepth 5 -name "go" -type f ...                     366 s
ls ~/go*; ls $HOME/go/bin; find / -maxdepth 5 -name "gofmt"   603 s
```

Sur une veille de silence à 600 s. C'est le mécanisme exact qui a tué
`go/bottle-song` (R28j, R28k), et il n'était pas isolé.

**Séquence exécutée.**

1. Veilleur de rejeu d'alphametics (66776) arrêté — alphametics repasse dans
   le lot général, son rejeu séparé n'a plus d'objet.
2. Pilote 64844 et lanceur 62028 arrêtés en arbre. Contrôle : aucun pilote
   résiduel.
3. `preparer_relance_outillee.py --appliquer` — **8** exercices go (et non 7 :
   `crypto-square` et `dnd-character` ont été jugés pendant la préparation).
   15 fichiers **déplacés**, rien détruit. Contrôle intégré : les tests
   officiels des 8 sont **tous identiques au corpus vierge**. Verdicts go
   restants : 0.
4. `reparer_amputes.py --appliquer` — `go/dominoes`, interrompu en vol,
   5 fichiers remis depuis son stash. Deuxième passe : aucun exercice amputé.
   Le script avait d'abord **refusé** d'y toucher, son `TASK.md` ayant moins
   de deux minutes : le garde-fou a fonctionné.
5. Relance. En-tête du journal :

```
chaine ajoutee au PATH de l'agent : C:\Users\test\go\bin
chaine ajoutee au PATH de l'agent : C:\Users\test\jdk21\jdk-21.0.12.1+1\bin
```

Et **aucune ligne « CHAINE D'OUTILS ABSENTE »** : le garde-fou ajouté au
pilote s'est tu parce que les six chaînes résolvent. Pilote **16168**.

**Ce que le run porte maintenant.** Les 26 cpp sont conservés et sautés — ils
sont valides, `cmake` était présent. Les 199 autres, go et java compris,
seront mesurés avec la chaîne. Une seule colonne, un seul protocole.

**Ce que ça ne rachète pas.** Les 8 verdicts go retirés ne sont pas effacés de
l'histoire : ils sont au bac à sable et restent citables comme mesure du coût
d'une chaîne absente — 3 FAIL sur 8, dont un par coupure sur silence, et deux
chasses de 366 s et 603 s facturées à la laisse. C'est le chiffre qui donne sa
valeur au garde-fou.

**Réserve tenue depuis R28i** : `go/beer-song` échouait sur un `\n` final que
la chaîne d'outils ne lui aurait pas appris — son énoncé ne le dit pas. Si le
rejeu le refait échouer, ce n'est pas l'outillage qu'il faudra accuser.

---

### R28m — trace des conventions muettes, et le refus explicite de la réinjecter

Ordre de l'opérateur : *« fait une trace des fails de ce type, on rejouera en
donnant ce type d'info pour améliorer les perf »*, puis, une heure plus tard,
le garde-fou qui va avec : *« non : fais simplement un fichier des best
practices, on l'utilisera plus tard ; sinon tu casses l'instrument de mesure. »*

Les deux ont été suivis, dans cet ordre : `tracer_conventions_muettes.py`
produit la trace, `BONNES_PRATIQUES_CONVENTIONS.md` l'accumule **à côté du
banc**, et rien ne repart vers l'agent.

#### Rien à rejouer : la matière était déjà là

Le correctif qui ajoute `erreurs` au journal (commit `41c9934`) est **antérieur
au redémarrage de 12:29**. Le pilote 16168 l'a donc chargé, et **chaque FAIL du
run porte la sortie du juge**. La trace se lit ; elle ne relance aucun
conteneur, ne touche à aucun fichier, ne sollicite pas le CPU du run. Les
verdicts antérieurs au correctif sont **signalés comme dépourvus du champ**
plutôt que devinés — un seul est concerné, `cpp/parallel-letter-frequency`.

#### Ce que la classification sait faire, et ce qu'elle ne sait pas

Mécanique, à partir du couple obtenu/attendu extrait de la sortie du juge :

| classe | test |
|---|---|
| `blancs` | identiques une fois **tous** les blancs retirés |
| `casse` | identiques une fois la casse ignorée |
| `ordre` | mêmes lignes, ordre différent |
| `fond` | rien de tout ça — l'échec n'est pas un problème de forme |

Les motifs d'extraction couvrent go (`got:`/`want:`), rust (`left:`/`right:`),
jest (`Expected:`/`Received:`), junit (`expected: <> but was: <>`) et pytest
(`assert X == Y`). Le **nom du motif qui a mordu** est enregistré : un échec
classé sans qu'on sache par quelle expression ne serait pas vérifiable.

Ce n'est pas `contrat_muet.py`. Celui-là demande si l'énoncé cite les
identifiants du stub, et ne peut **par construction** rien dire de la forme de
la valeur de retour — séparateur final, ordre, casse, arrondi. Celui-ci part de
l'échec réel au lieu de l'énoncé : c'est le troisième biais nommé en R28i,
enfin mesuré au lieu d'être supposé.

#### Deux champs, et la séparation est délibérée

- `injectable` — la **forme** de l'écart, jamais la valeur. Pour beer-song :
  *« La valeur attendue porte, APRÈS le dernier élément, un séparateur terminal
  que ta sortie n'a pas. »*
- `obtenu` / `attendu` — les valeurs réelles, pour le diagnostic humain.

#### Et l'injecteur n'a pas été écrit — décision, pas oubli

J'avais prévu un bras « D + conventions déclarées ». L'opérateur l'a arrêté, et
il a raison : **la variante D mesure ce qu'un agent trouve sans information
complémentaire.** Une convention extraite de la suite cachée *est* une
information complémentaire. La donner ne fait pas monter le score de l'agent,
elle supprime la question à laquelle le banc répond. Le fichier de bonnes
pratiques s'accumule, daté, hors du chemin du banc ; le jour où il servira, ce
sera dans un bras distinct et étiqueté.

#### Validation, puis deux confirmations que je n'ai pas eu à chercher

Le classeur a été passé sur la sortie du juge **réellement captée** le 27/08
pour beer-song. Verdict : `blancs`, *« l'attendu prolonge l'obtenu de 1
caractère : "\n" »*. Le cas fondateur est retrouvé exactement.

Puis le run outillé a rendu ses deux premiers verdicts go :

```
go   alphametics   PASS   155.4 s
go   beer-song     FAIL    65.3 s
```

1. **`alphametics` passe.** Le FAIL du matin était bien un artefact du banc
   (R28i) — confirmé non plus par un rejeu du juge que j'aurais conduit
   moi-même, mais par un **échantillon frais et indépendant**, agent reparti du
   stub. Au passage : 75,5 s avant, 155,4 s maintenant. L'écart est le temps
   qu'il passe désormais à **exécuter ses tests**, ce qu'il ne pouvait pas
   faire.
2. **`beer-song` échoue encore**, ramassé tout seul par la trace, classé
   `blancs`, même écart d'un `\n`. **C'est exactement la réserve posée en R28l**
   avant de relancer : *« si le rejeu le refait échouer, ce n'est pas
   l'outillage qu'il faudra accuser »*. Il a échoué, et ce n'est pas
   l'outillage. Une chaîne d'outils ne fait pas deviner une convention que
   l'énoncé ne porte pas.

**Ce qui n'est pas mesuré.** Un seul cas de convention muette à ce stade, sur
un run en cours. Les trois autres familles listées dans le fichier de bonnes
pratiques (ordre, casse, arrondi) sont des généralisations **sans cas observé**,
et le fichier le dit ligne à ligne.

**Addendum, 5 verdicts go plus tard — la relance se paie déjà.**

```
go   alphametics   PASS   155.4 s
go   beer-song     FAIL    65.3 s
go   book-store    PASS   320.3 s
go   bottle-song   PASS    65.4 s
go   bowling       PASS   200.4 s
```

`bottle-song` est le cas qui a tout déclenché : **coupé à 640,1 s sur veille de
silence** sous le régime sans chaîne (R28j), l'agent parti chasser `gofmt` avec
un `find /`. Avec `go` sur son PATH, il **passe en 65,4 s** — presque dix fois
moins que la seule coupure. Ce n'est pas un gain de qualité du modèle : c'est
le coût, enfin retiré, d'une chaîne d'outils absente.

4 PASS sur 5 à ce stade, contre 5 sur 8 sous le régime précédent. Trop peu pour
un taux ; assez pour dire que les deux régimes ne mesuraient pas la même chose.

---

### R28n — une deuxième famille : la forme *passée* n'est pas la forme *montrée*

`go/connect` échoue, et il n'entre dans aucune case existante. Ce n'est ni un
écart de forme du résultat, ni une signature inventée : **les 8 cas sur 8 sont
refusés avec le même message**, sorti de la validation de la solution
elle-même — `invalid board: unknown cell`. Elle n'a **rien calculé**. Elle n'a
pas su **lire**.

#### La cause, lue dans le harnais officiel et non supposée

`connect_test.go:8-16` :

```go
// Simply strip the spaces of all the strings to get a canonical
// input. The spaces are only for readability of the tests.
func prepare(lines []string) []string {
    newLines[i] = strings.ReplaceAll(l, " ", "")
}
```

Le harnais **retire tous les espaces** avant d'appeler `ResultOf` : il passe
`"....."`. L'agent avait écrit `strings.Fields(line)` — juste sur
`. . . . .`, mais sur `.....` cela rend **un seul champ**, ni `X`, ni `O`, ni
`.`. Rejet, huit fois.

**Et le message d'erreur oriente à l'opposé de la cause.** Le test affiche
`strings.Join(tc.board, "\n")`, c'est-à-dire le plateau **d'origine, espacé** —
pas celui qu'il vient de transmettre. Un agent qui lit ce message conclut que
son lecteur doit accepter les espaces. Il les accepte déjà. C'est le piège le
plus coûteux du lot : l'indice fourni est faux.

#### Ce que le traceur sait faire de plus

Trois familles au lieu d'une, chacune détectée mécaniquement :

| famille | signal | cas observé |
|---|---|---|
| **sortie** | couple got/want extrait, identiques aux blancs/casse/ordre près | `go/beer-song` |
| **entrée** | ≥ 3 cas refusés avec un message **identique**, issu de la solution | `go/connect` |
| **contrat** | la suite officielle ne compile pas : `undefined:`, `cannot find symbol`… | aucun à ce jour |

Le seuil de trois et l'unicité du message sont ce qui rend l'inférence
défendable : un bug de logique produit des écarts **variés** ; un refus
identique sur tous les cas, y compris les triviaux, ne peut venir que de la
lecture. En dessous de trois, le traceur ne conclut pas.

#### La règle qui couvre les trois

> **Tolérant à l'entrée, exact à la sortie, fidèle au stub.**

Un caractère de trop à la sortie coûte l'exercice (`beer-song`, 1 caractère).
Un rejet à l'entrée le coûte aussi, mais en masquant une logique peut-être
juste (`connect`, 8 échecs identiques). Les deux se corrigent en trois lignes,
et aucune des deux ne s'apprend de l'énoncé.

#### État du run

7 verdicts go sous le régime outillé : **5 PASS, 2 FAIL** (`beer-song`,
`connect`). 33 verdicts au total avec les 26 cpp conservés.

**Toujours pas de réinjection.** Ces deux bonnes pratiques vont dans
`BONNES_PRATIQUES_CONVENTIONS.md`, à côté du banc. Les donner à l'agent
pendant un run de la variante D supprimerait la question à laquelle ce run
répond.

**Non déterminé** : `cpp/parallel-letter-frequency` a échoué avant le
correctif qui journalise la sortie du juge ; son `.dsh.results.json` n'a pas de
champ `erreurs`. Retrouver sa cause demande un rejeu du juge dans le conteneur
que le run occupe — reporté, pas oublié.

---

### R28o — les motifs du traceur étaient faux aux trois quarts ; vérifiés sur des sorties réelles

Le traceur classait `go/beer-song` et `go/connect` correctement. Il ne l'aurait
fait pour **aucune autre langue** : trois de ses cinq motifs d'extraction
étaient écrits de mémoire, et faux pour ce corpus. Relevé sur le corpus, pas
supposé :

| langue | ce que j'avais écrit | ce que le corpus utilise vraiment |
|---|---|---|
| java | JUnit, `expected: <X> but was: <Y>` | **AssertJ** — 989 `assertThat`, format `expected: X` / `but was: Y` sur **deux lignes, sans chevrons** |
| python | pytest nu, `assert X == Y` | **unittest** — 735 `self.assertEqual`, format `AssertionError: X != Y` |
| rust | `left: \`X\`, right: \`Y\`` | rustup **non épinglé** dans le Dockerfile du juge → rustc récent, plus de guillemets obliques |

Un traceur qui ne mord pas rend « illisible » : il ne ment pas, mais il ne
mesure rien. Sur java (47), python (34) et rust (39), soit **120 exercices**,
il n'aurait rien vu.

#### Corrigé, puis vérifié en exécutant

`verifier_motifs.py` rejoue les motifs sur des sorties **capturées en
exécutant vraiment**, le 27/08 :

- **java** — `./gradlew test --offline` sur affine-cipher, solution de
  référence dont j'ai passé `GROUP_SIZE` de 5 à 4 : logique du chiffre intacte,
  groupement faux. Sortie obtenue :
  `expected: "rzcwa gnxzc dgt"` / `but was: "rzcw agnx zcdg t"`. Classée
  `blancs` — juste, les deux sont identiques une fois les espaces retirés.
- **rust** — `rustc --test` (rustc 1.95.0) sur des `assert_eq!`. Format
  confirmé : `assertion \`left == right\` failed`, puis `left:` / `right:` sur
  deux lignes, valeurs **sans** guillemets obliques.
- **python** — `unittest` (3.11.5) sur cinq formes d'`assertEqual` (str, list,
  dict, int, multiline). Les cinq mordent.
- **javascript** — **aucun échantillon réel**. jest n'existe que dans le
  conteneur du juge. Le motif js est donc **déclaré non vérifié**, pas supposé
  bon.

7 cas, 0 échec. Un défaut de plus corrigé au passage : le `repr` de python
entoure d'**apostrophes**, que `deguillemete` ne retirait pas — la classe
restait juste, la phrase d'écart perdait sa précision.

#### Audit d'outillage, fait avant que les blocs arrivent et non après

Le désastre de R28k — 86 exercices mesurés sans chaîne — venait d'un contrôle
absent. J'ai donc contrôlé **à l'avance**, pour chaque langue restante :

| langue | exigence du juge | état de l'hôte | verdict |
|---|---|---|---|
| java | `./gradlew test` | JDK 21.0.12.1 + `~/.gradle` **164 Mo**, `gradle-8.7-bin` (la version des 47 wrappers), jars AssertJ et JUnit présents | **prêt** — prouvé hors ligne : solution de référence, code de sortie **0** |
| go | `go test ./...` | go1.22.5 hôte contre go1.21.5 juge | **neutre** — les 39 `go.mod` déclarent `go 1.18`, la sémantique 1.22 des variables de boucle **ne s'applique pas** |
| javascript | `npm-test.sh`, jest global lié dans l'exercice | node 24, jest absent | **était un piège** — voir ci-dessous |
| python | `pytest` | 3.11.5 | présent |
| rust | `cargo test` | 1.95.0 | présent |

**Le piège javascript, mesuré et refermé.** Trois voies essayées sur
affine-cipher, solution de référence posée :

```
node --test, zero dependance ............... marche
jest global, sans node_modules local ....... Test Suites: 1 failed, Tests: 0 total
jest + NODE_PATH vers le node_modules global  16 tests, 2 passes, 14 sautes
```

Le juge lie `/npm-install/node_modules` dans le dossier de l'exercice
(`benchmark/npm-test.sh`). L'équivalent côté hôte est `NODE_PATH`. jest 29.7.0
et le preset babel d'Exercism ont donc été installés en global, **aux versions
du Dockerfile du juge**, et le lanceur pose `NODE_PATH`. Le garde-fou ne se
contente plus de chercher `node` : il vérifie que `NODE_PATH` **résout**
`@exercism/babel-preset-javascript`, puisque jest seul exécute zéro test.

**Vérifié aussi, et ce n'était pas un défaut** : les 47 exercices java portent
`@Disabled` sur tous les tests sauf le premier (48 fichiers). `pilote.py:696`
les retire déjà avant le verdict, comme `benchmark.py:1031` d'aider. Mon
premier essai en montrait 15 sautés uniquement parce qu'il tournait hors du
pilote.

#### La réserve qui reste, et elle est datée

Le pilote **en cours** (16168) a construit son environnement au démarrage de
12:29, **avant** ces correctifs. Il n'a donc pas `NODE_PATH`. Quand javascript
arrivera — après go (32 restants) et java (47), soit environ **4 heures** —
l'agent y sera dans la situation de la voie 2 : jest présent, zéro test
exécuté. Il lui restera `node --test`, qui marche, mais ce n'est pas la chaîne
du juge.

Relancer avant que javascript commence coûte **zéro verdict** : le pilote saute
tout exercice ayant déjà son `.dsh.results.json`. C'est la même manœuvre qu'en
R28l, et elle est à décider avant, pas après.

---

### R28q — le rejeu reformulé est armé, et il partira à la fin

Ordre de l'opérateur, 27/08 : *« tu as le droit d'optimiser les questions à
condition de tracer la raison, puis tu rejoues le test case »*, puis, sur le
créneau : *« on le fera à la fin, cela donnera deux métriques avec et sans
reformulation and best practices »*, degré **B d'abord, C si B échoue**.

**Pourquoi pas maintenant.** Le 4090 sert un slot. Un rejeu concurrent
fausserait les durées **des deux côtés**, et la durée est une grandeur mesurée
de ce banc. Le rejeu attend donc la fin du run, ce qui donne en prime la
comparaison la plus propre : mêmes exercices, même modèle, deux énoncés.

#### Trois degrés, parce que toutes les reformulations ne contaminent pas pareil

| degré | ce que c'est | ce que ça coûte à la comparabilité |
|---|---|---|
| **A** | désambiguïsation interne — l'énoncé se contredit, on ne garde que la forme qui fait foi | **rien n'entre** : tout était déjà écrit dans l'énoncé |
| **B** | mise en garde générique — une *classe* d'ambiguïté est signalée, sans dire de quel côté elle tombe ; ne cite aucun exercice | c'est une amélioration de **consigne**, pas une réponse |
| **C** | révélation — la convention attendue est donnée | vient de la **suite cachée** ; contamination maximale |

C'est la distinction qui manquait au projet initial. Le degré **B** est le seul
qui pourrait légitimement devenir la consigne par défaut du banc : il n'apporte
aucune information sur un exercice, seulement l'existence d'une ambiguïté. Si B
suffit à faire passer les échecs de forme, c'est le résultat le plus fort du
lot.

`questions_reformulees.json` porte 4 ajouts génériques (B) et 3 visés (1 A,
2 C), chacun avec son constat et sa raison sourcée. Le `.md` en est le rendu
généré — éditer le `.md` à la main ferait diverger la raison publiée de celle
qui a servi.

#### Ce qui rend le chiffre lisible plus tard

- `pilote.py --questions <f> --degres A,B,C`. **Sans `--degres`, rien n'est
  ajouté** : la variante D reste le défaut, à l'octet près.
- Chaque `.dsh.results.json` porte désormais `reformulations` — identifiant,
  degré, **texte exact reçu**. Deux runs ne peuvent plus être comparés à
  l'aveugle.
- `preparer_rejeu_reformule.py` **refuse** de préparer tant que la référence
  n'est pas terminée (comparer une colonne complète à une partielle), et
  **refuse** si la référence porte déjà une reformulation (elle ne peut pas
  tenir la colonne « sans »). `--partiel` lève le premier refus et l'écrit dans
  le fichier produit.
- `comparer_reformulation.py` **refuse** une colonne « avec » qui ne porte
  aucune reformulation, ne compare que les exercices joués des deux côtés, et
  distingue `FAIL→PASS` de `PASS→FAIL` — un ajout mal tourné peut détourner
  l'agent d'une solution qu'il avait.

#### Deux familles de plus au traceur, et un affichage qui ne cache plus rien

`go/kindergarten-garden` a ouvert les deux :

- **`lexique`** — mêmes mots, autre forme. Test volontairement étroit : même
  nombre de mots, même ordre, préfixe commun d'au moins trois lettres.
  `["Radish" "Clover"…]` contre `["radishes" "clover"…]`.
- **`exigence`** — la suite attend une **erreur** que l'énoncé ne demande
  jamais. Quatre cas ; les mots « error », « invalid », « duplicate », « odd »
  ne figurent pas dans l'énoncé. Signal **additif** : un exercice peut cumuler.

Et la sortie imprime maintenant la **répartition** des classes, pas seulement
la plus favorable retenue. Sans elle, `kindergarten-garden` s'affichait
« casse » alors que **6 de ses 7 cas sont `lexique`**, plus dur. Une classe
retenue sans sa répartition trompe.

#### État

41 verdicts (26 cpp + 15 go). 4 échecs, dont un — `cpp/parallel-letter-frequency`
— sans sortie du juge parce qu'antérieur au correctif : sa cause reste **non
déterminée**, et le rejeu la retrouvera puisqu'il le rejouera.

---

### R28r — une prédiction déposée avant que java tourne, et le défaut qu'elle a failli publier

**La question de l'opérateur**, 27/08 : *« est-ce que pendant ton temps libre tu
peux reformuler les questions mal posées, ou vaut-il mieux attendre les
fails ? »*

Ni l'un ni l'autre. **Reformuler d'avance** ferait de mon jugement le
sélecteur : je choisirais quels énoncés sont « mal posés », et un score en
hausse ne prouverait plus rien — 225 blocs de garde ajoutés font monter un taux
sans qu'on sache lequel a servi. **Attendre** gaspille l'attente.

Le troisième geste est de **déposer une prédiction**. Publier, avant que java,
javascript, python et rust jouent, la liste des exercices qui portent les
signatures structurelles des trois échecs déjà observés. Leurs échecs
**testeront** la prédiction au lieu de l'illustrer après coup.

État au dépôt : **44 verdicts** (cpp 26 + go 18). Les 181 restants n'ont pas été
joués, dont **la totalité de java, javascript, python et rust**.

#### Les quatre signatures, chacune tirée d'un échec réel

| id | signature | tirée de |
|---|---|---|
| **S1** | un tableau `code → libellé`, et le libellé ailleurs dans la prose sous une autre forme | `go/kindergarten-garden` (`Radish` / `radishes`) |
| **S2** | un bloc de sortie **rendue** sur plusieurs lignes, sans ponctuation de code — un séparateur terminal y est invisible | `go/beer-song` |
| **S3** | une entrée **alignée pour l'œil**, espacée ou indentée | `go/connect` |
| **S4** | le stub déclare un retour d'**erreur**, l'énoncé n'emploie aucun mot du champ de l'erreur | `go/kindergarten-garden` (4 validations muettes) |

#### Le défaut, trouvé avant publication et pas après

Première sortie : **118 exercices signalés sur 225**, dont S4 = 90, concentré
sur java (38) et javascript (34). C'est ce déséquilibre qui a déclenché la
vérification — et le détecteur mesurait **le gabarit du track, pas l'énoncé** :

- **javascript** : 124 occurrences de `throw` dans les stubs. Les 124 sont la
  **même** ligne — `throw new Error('Remove this statement and implement this
  function')`. Les 34 signalements valaient zéro.
- **java** : 46 stubs sur 47 portent `throw new UnsupportedOperationException`,
  même gabarit. **6 seulement** portent un vrai `throws` : `alphametics`,
  `bank-account`, `circular-buffer`, `dominoes`, `sgf-parsing`, `tree-building`.
- **cpp** : aucun stub ne porte `throw`. **python** : aucune déclaration
  d'erreur dans une signature.

S4 est donc **aveugle** sur trois langues sur six. Le tableau y imprime « **-** »,
jamais « 0 » : un zéro se lirait comme une absence de risque là où il n'y a
qu'une absence de mesure.

#### La prédiction déposée

```
=== PREDICTION : 72 exercice(s) signale(s) sur 225 ===
  S1    3  (1 % de 225)
  S2   55  (24 % de 225)
  S3   21  (9 % de 225)
  S4   21  (18 % de 116 -- go+java+rust seulement, S4 est aveugle ailleurs)

  langue       S1    S2    S3    S4
  cpp          1     4     0     -
  go           1     10    4     14
  java         1     13    6     3
  javascript   0     16    7     -
  python       0     8     2     -
  rust         0     4     2     4
```

Contrôle sur les trois échecs connus : `beer-song` → S2, `connect` → S2+S3,
`kindergarten-garden` → S1+S4. **Les trois sont retrouvés.** Une prédiction qui
rate ce qui a déjà échoué ne vaut rien.

**Ce que ces chiffres valent, dit franchement.** S1 (3 exercices, 1 %) et S3
(21, 9 %) sont **serrés** : s'ils échouent plus que la moyenne, l'écart sera
lisible. S2 (55, 24 %) est **large** — un quart du corpus signalé prédit peu de
chose a priori. S4 ne couvre que 116 exercices sur 225.

**Et comment elle se juge.** Pas au nombre de signalés qui échouent : à
l'**écart** entre le taux d'échec des signalés et celui des autres. Une
signature n'est pas une cause. `verifier_prediction.py` reste à écrire ; il
dépouillera après coup, sur la liste figée ici.

#### Addendum R28r — le dépouilleur, et ce qu'il a trouvé en tournant

`verifier_prediction.py` écrit dans la foulée. Il ne compte pas les signalés qui
échouent : il calcule l'**écart** entre le taux d'échec des signalés et celui
des non signalés, avec un **Fisher unilatéral exact** à côté — parce que S1 ne
porte que 3 exercices et qu'un « 50 % contre 5 % » sur 2 cas ne prouve rien.

Trois choses sont sorties de sa première exécution, et aucune n'était cherchée.

**1. `go/octal` n'est pas un échec de convention — c'est une coupure.**
`tours_coupes: 1` sur `num_turns: 1`, 635,6 s, et `octal.go` porte encore
`panic("Please implement the ParseOctal function")`. L'agent n'avait pas rendu ;
la laisse de silence l'a arrêté. Ce verdict mesure la laisse, pas l'énoncé.

**2. `cpp/parallel-letter-frequency`, « cause non déterminée » depuis R28q, est
déterminée** : coupure elle aussi, à 1 150 s. La question ouverte se ferme sans
avoir eu besoin du rejeu.

**3. Cinq verdicts sur 46 portent une coupure — mais trois d'entre eux ont
PASSÉ.** `cpp/zebra-puzzle` (843,5 s), `go/crypto-square` (710,6 s),
`go/ledger` (855,7 s) : l'agent avait fini, la coupure l'a pris pendant une
vérification. D'où la règle exacte, qui n'est pas celle que j'avais écrite en
premier : **on n'écarte que les coupures qui ont échoué**. Une coupure qui passe
reste un PASS — la laisse ne peut que nuire, jamais aider. Les écarter aurait
retiré trois succès du dénominateur et gonflé le taux d'échec des deux colonnes.

**La laisse ne bouge pas pour autant.** Elle a coupé cpp et go ; la relever
maintenant réglerait un paramètre en cours de route pour obtenir des PASS, et
rendrait java, javascript, python et rust incomparables aux 65 déjà joués. Les
deux coupures se rejouent à la fin, **bras séparé, D pur**.

`preparer_rejeu_reformule.py` sépare donc désormais **deux populations** :

| bras | contenu | degré | ce que son résultat dit |
|---|---|---|---|
| 1 | échecs **jugés** | B | le coût de l'ambiguïté de l'énoncé |
| 2 | tours **coupés** | **aucun** — D pur | ce que la laisse a coûté |

Les mélanger aurait fait passer des timeouts pour du coût d'ambiguïté : une
coupure qui passe au rejeu passe parce qu'elle a eu le temps, pas parce que
l'énoncé était plus clair.

#### Ce que le dépouilleur dit aujourd'hui : rien, et il le dit

```
depouilles      : 44   (46 verdicts - 2 coupures en echec)
echecs          : 3  (6.8 %)

=== HORS cas fondateurs -- c'est CE tableau qui teste la prediction ===
  NON CONCLUANT : 41 exercice(s) depouille(s), AUCUN echec.
```

Les **trois seuls** échecs jugés du run sont `beer-song`, `connect` et
`kindergarten-garden` — exactement les trois dont S1 à S4 ont été tirées. Un
tableau qui les inclut donne S4 à +42,9 points, p = 0,036 : **circulaire**. Une
règle retrouve toujours les exemples qui l'ont produite. Le script imprime donc
deux tableaux, marque le premier « à ne pas publier seul », et refuse de
conclure sur le second tant qu'il ne contient aucun échec.

État : **41 PASS sur 44 jugés** (cpp + go partiel), plus 2 coupures à rejouer.

---

### R28s — la prédiction prend ses deux premiers coups, un raté et une confirmation

Quatre échecs jugés sont arrivés pendant que j'écrivais le dépouilleur. Ils
sont le premier hors-échantillon de la prédiction déposée en R28r, et ils la
traitent durement — ce qui est exactement ce qu'on lui demande.

#### `go/pig-latin` — un RATÉ, non signalé

```
--- FAIL: TestPigLatin/y_is_treated_like_a_consonant_at_the_beginning_of_a_word
    pig_latin_test.go:11: Sentence("yellow") = "yelloway", want "ellowyay"
```

L'énoncé donne quatre règles et, en règle 1, trois exemples :
`apple` (voyelle), `xray` (préfixe `xr`), `yttria` (préfixe `yt`). L'agent a
codé cela au mot près :

```go
if isVowel(word[0]) || strings.HasPrefix(word, "xr") || strings.HasPrefix(word, "yt") {
```

`xray`, `yttria`, `my`, `rhythm`, `quick`, `square` passent. Seul `yellow`
tombe. **L'énoncé ne dit jamais si un `y` initial est voyelle ou consonne** ;
il ne donne que l'exception `yt`, et le seul mot en `y-` qu'il montre est
précisément celui que l'exception couvre.

C'est une **cinquième famille** : *l'énoncé énumère des exceptions préfixées
sans énoncer la règle générale dont elles dérogent*. Aucune de mes quatre
signatures ne la voit. **S5 n'est pas ajoutée à la liste figée** — l'ajouter
après avoir vu l'échec qu'elle doit attraper serait de l'ajustement après
coup, exactement ce que le pré-enregistrement sert à empêcher.

#### `go/poker` — une CONFIRMATION, signalée S4

```
--- FAIL: TestBestHandInvalid/♥_is_an_invalid_suit
    BestHand([2♡ 3♡ 4♥ 5♡ 7♡]) expected error, got: [2♡ 3♡ 4♥ 5♡ 7♡]
```

Le stub déclare `func BestHand(hands []string) ([]string, error)`. L'énoncé
fait **quatre lignes** et n'emploie ni « error », ni « invalid », ni « must ».
C'est le mécanisme de S4, littéralement. Et un second piège par-dessus : `♡`
(U+2661, cœur *blanc*) est valide, `♥` (U+2665, cœur *noir*) doit être rejeté —
deux points de code que l'œil ne sépare pas.

#### `go/palindrome-products` — ni l'un ni l'autre : une panne de banc

```
go: downloading go1.24 (linux/amd64)
go: download go1.24 for linux/amd64: toolchain not available
```

L'agent a réécrit `go.mod` en `go 1.24` ; le conteneur porte `go1.21.5` et n'a
pas de réseau. **La solution n'a jamais été compilée.** Cet exercice portait S4 :
le compter comme confirmation aurait été une **fausse confirmation**.

Le défaut est structurel, pas accidentel : `go.mod` n'est pas dans les
éditables, et `restaurer()` ne remet à neuf **que** les éditables. Un fichier
d'échafaudage modifié par l'agent survit donc jusqu'au juge. **Non corrigé en
cours de route** — changer ça maintenant rendrait les 176 exercices restants
incomparables aux 49 déjà joués.

#### Trois populations, et `classer()` les sépare

| population | ce qui s'est passé | rejeu | ce qu'il mesure |
|---|---|---|---|
| **jugé** | l'agent a rendu, le juge a dit non | degré **B** | le coût de l'ambiguïté |
| **coupé** | la laisse a arrêté l'agent | **D pur** | ce que la laisse coûte |
| **infra** | la chaîne du juge n'a pas construit | **D pur** | un défaut du banc |

Une erreur corrigée au passage, et elle allait dans le mauvais sens : j'écartais
**toutes** les coupures. Or 3 des 5 avaient **passé** (`cpp/zebra-puzzle`,
`go/crypto-square`, `go/ledger`) — l'agent avait fini, la coupure l'a pris en
vérification. Une coupure qui passe reste un PASS ; la laisse ne peut que nuire.
Les écarter retirait trois succès du dénominateur et gonflait le taux d'échec
des **deux** colonnes.

#### Où en est la prédiction, hors cas fondateurs

```
=== HORS cas fondateurs -- c'est CE tableau qui teste la prediction ===
  sig   perimetre        signales           non signales        ecart      Fisher
  S1    43 joues          0/1   =   0.0 %     2/42  =   4.8 %     -4.8 pt   p = 1.000
  S2    43 joues          0/9   =   0.0 %     2/34  =   5.9 %     -5.9 pt   p = 1.000
  S3    43 joues          0/2   =   0.0 %     2/41  =   4.9 %     -4.9 pt   p = 1.000
  S4    18 joues          1/5   =  20.0 %     1/13  =   7.7 %    +12.3 pt   p = 0.490
```

**Une confirmation, un raté, rien de conclu.** S4 est la seule signature qui
sépare dans le bon sens, et p = 0,490 ne conclut rien. S1, S2 et S3 n'ont
encore aucun échec signalé hors cas fondateurs. Le tableau « tout compris »
donne S4 à p = 0,047 — il est **circulaire** et le script le marque « à ne pas
publier seul ».

État : 49 verdicts, 46 dépouillés (2 coupures + 1 infra écartées), 5 échecs
jugés.

---

### R28t — deux bugs de fond diluaient la mesure ; le critère qui les sépare était déjà écrit

Deux échecs de plus, et **aucun des deux** n'est une convention muette.

**`go/react`** — panic `index out of range [3] with length 2`. Suppression par
échange, à `react.go:119-122` :

```go
e := cbs[c.idx]        // l'entree RETIREE
cbs[c.idx] = cbs[last] // le rescape arrive ici...
e.can.idx = c.idx      // ...mais c'est l'index du RETIRE qu'on corrige
```

Il fallait `cbs[last].can.idx = c.idx`. Le rescapé garde un index périmé.
Bug pur, rien à voir avec l'énoncé.

**`go/robot-simulator`** — `build failed`, `undefined: Action`, `undefined: N`.
Or le stub **nomme** ce qu'il faut définir : `// Define N, E, S, W here.`,
`// Define Action type here.` — et `instructions.append.md:22` le redit. L'agent
a utilisé `Action` et `Action3` dans ses signatures sans jamais déclarer les
types. **Rien n'était caché.**

Le contraste avec `go/protein-translation` est net et il fait la frontière de
la famille **contrat** : là-bas `ErrStop` et `ErrInvalidBase` n'existaient ni
dans l'énoncé ni dans le stub ; ici les noms étaient donnés deux fois.

#### Le problème que ça pose à la mesure

Le taux d'échec brut mélange deux populations : l'échec d'**ambiguïté**
(l'énoncé ne dit pas ce que la suite exige) et l'échec de **fond** (l'agent a
écrit un bug). **Aucune signature d'énoncé ne peut attraper un bug.** Les
laisser dans la colonne « non signalés » dilue mécaniquement tout écart —
c'est exactement ce qui a fait retomber S4 de +26,2 à +15,7 points en deux
exercices.

Les retirer parce que ça arrange la prédiction serait régler l'analyse pour
obtenir un résultat. Ce qui l'évite, c'est que **le critère était déjà écrit,
avant ces échecs** : c'est la barre du fichier des bonnes pratiques du 27/08,
point 2 — *« la preuve sur pièces que la logique était juste »*.

`classification_echecs.json` le fixe noir sur blanc :

> Un échec est classé **ambiguïté** si et seulement si (1) la logique passe les
> cas voisins — on peut nommer lesquels — **et** (2) l'élément divergent est
> absent de l'énoncé **et** du stub, c'est-à-dire de tout ce que l'agent peut
> voir. Sinon : **fond**.

Trois garde-fous, sans lesquels le classement fabriquerait l'écart qu'il
prétend mesurer :

- le classement se lit **sans regarder** si l'exercice était signalé ;
- il est **symétrique** — un exercice signalé qui échoue sur un bug sort du
  dépouillement comme les autres ;
- un échec **non classé** compte comme « ambiguïté » par défaut, donc du côté
  **défavorable** à la prédiction, et le script le signale par son nom.

#### Les trois lectures, à 54 verdicts

```
=== HORS cas fondateurs ===
  S4    23 joues          2/6   =  33.3 %     3/17  =  17.6 %    +15.7 pt   p = 0.392

  2 echec(s) de FOND retire(s) des DEUX colonnes : go/react, go/robot-simulator

=== HORS fondateurs ET hors echecs de FOND -- lecture la plus fine ===
  S1    46 joues          0/1   =   0.0 %     3/45  =   6.7 %     -6.7 pt   p = 1.000
  S2    46 joues          0/10  =   0.0 %     3/36  =   8.3 %     -8.3 pt   p = 1.000
  S3    46 joues          0/3   =   0.0 %     3/43  =   7.0 %     -7.0 pt   p = 1.000
  S4    21 joues          2/6   =  33.3 %     1/15  =   6.7 %    +26.7 pt   p = 0.184
```

**S4 sépare, les trois autres non, et rien n'atteint le seuil.** S1, S2 et S3
n'ont toujours **aucun** échec signalé hors cas fondateurs — leurs écarts
négatifs ne disent pas qu'elles se trompent, seulement qu'aucun des exercices
qu'elles désignent n'a encore échoué.

État : 54 verdicts, 51 dépouillés, 8 échecs jugés, go 28/39.

---

### R28u — le stub lui-même peut être faux, et le p qui traverse le seuil dans les deux sens

#### `go/tree-building` — troisième confirmation S4, mécanisme exact

L'énoncé fait **24 lignes** et ne contient **aucune** occurrence de « error »,
« invalid », « cycle », « continuous », « must » ni « fail ». Le stub déclare
`Build(records []Record) (*Node, error)`. La suite exige le rejet de trois
classes d'entrées : `non-continuous`, `cycle indirectly`,
`higher id parent of lower id` — toutes trois « returned … but was expected to
fail ». C'est le phénomène de `go/kindergarten-garden` 3b, à l'identique.

#### `go/trinary` — et une correction de ce que j'avais dit d'`octal`

Le stub **vierge** est :

```go
func ParseTrinary(arg string, want int64, ok bool)
```

Ce ne sont pas des paramètres : ce sont les **champs de la table de cas de
test**. Le stub est faux à la livraison. J'avais attribué la signature bizarre
d'`go/octal` à l'agent coupé en cours de travail — **c'était le stub**, qui
porte `ParseOctal(input string, expectedNum int64, expectErr bool)`.

L'agent doit donc inventer la signature, et tout ce qu'il voit pointe au
mauvais endroit : le stub suggère un `ok bool`, l'énoncé dit *« strings
specifying an invalid trinary as the value 0 »* — donc pas d'erreur du tout —
et la suite exige un `error` : `cannot use err (variable of type bool) as
error value`.

**Ampleur mesurée, pas supposée** : balayage des 225 exercices des six langues,
signature dont un paramètre porte `want` / `expected*` / `ok bool`. **Deux
cas** : `octal` et `trinary`, tous deux en go, **tous deux en échec**. Rien à
pré-enregistrer là-dessus pour les pistes restantes — aucun exercice non joué
ne porte le défaut. La pathologie est réelle, fatale à 2/2, et épuisée.

S4 ne l'avait pas signalé, et c'est un **angle mort nommé** : S4 exige que le
stub *déclare* un retour d'erreur ; ici le stub n'a aucun retour. Je ne le
comble pas après coup.

#### Deux fautes de méthode que je devais, et la preuve qu'elles mordent

À 60 verdicts, S4 en lecture fine donnait **p = 0,038**. Deux minutes plus
tard, un exercice signalé ayant réussi entre-temps : **p = 0,056**. Le seuil
a été franchi puis refranchi dans l'autre sens, sans qu'aucune signature ne
change.

C'est l'illustration exacte des deux fautes que je n'avais pas payées :

1. **Multiplicité.** Quatre signatures sont testées. Rapporter celle qui passe
   le seuil, c'est se donner quatre tirages. Le dépouilleur imprime désormais
   une colonne **`p*4`** (Bonferroni) à côté de `p`, et c'est elle qui se cite :
   à p = 0,038, `p*4 = 0,152`. **Rien n'est significatif.**
2. **Regards répétés.** J'ai relancé le dépouillement à chaque nouvel échec.
   Regarder des données qui s'accumulent et s'arrêter quand le chiffre plaît
   gonfle le taux de faux positifs bien au-delà de 5 %. Le pré-enregistrement
   avait figé la **liste**, pas la **règle d'arrêt**.

**Règle d'arrêt, posée maintenant et imprimée par le script** : l'analyse fait
foi **une seule fois**, sur les 225 verdicts du run terminé. Les lectures
intermédiaires pilotent le travail, jamais la conclusion. Tant que le run n'est
pas fini, le script encadre sa sortie d'un bandeau
« **LECTURE INTERMÉDIAIRE — NE PAS PUBLIER CE p** ».

#### Où en est le run

60 verdicts, 11 échecs jugés, go 34/39. Les quatre touches S4 hors cas
fondateurs sont `poker`, `protein-translation`, `tree-building` (mécanisme
exact) et `simple-linked-list` (mécanisme fortuit, enregistré comme tel).
Tout cela est **go seul** : java et rust, les deux autres langues du périmètre
de S4, n'ont pas commencé.

### R28v — la relance pour `NODE_PATH`, et les deux dégâts qu'elle a révélés

**La décision.** L'opérateur, 27/08 : *« Une décision à prendre avant ~4 h : le
pilote 16168 a figé son environnement à 12:29, donc sans NODE_PATH. Le relancer
avant que javascript commence coûte zéro verdict. »*

Le « zéro verdict » a été vérifié sur pièce avant d'agir, `pilote.py:1495` :

```python
if os.path.exists(res_f):
    continue                      # reprise : deja juge
```

Et ce que la relance embarquait **en plus** de `NODE_PATH` a été diffé commit
par commit (`0ca4ce4` en vol → `HEAD`), parce qu'une relance ne rejoue pas le
code d'origine :

| ce qui change | effet sur le protocole |
|---|---|
| `$env:NODE_PATH` posé | le but ; inerte pour java/python/rust |
| garde `_js_resolution_absente` | le banc **refuse de partir** si le preset babel ne résout pas |
| champ `reformulations: []` | additif, vide, discernable dans les données |
| `--degres` absent | `ajouts = reformulations or []` → énoncé identique à l'octet |
| juge | inchangé : même conteneur, mêmes commandes, même retrait des `@Disabled` |

Relance faite à 14:52. Confirmé au journal :
`NODE_PATH de l'agent : C:\Users\test\AppData\Roaming\npm\node_modules`.

**Effet de bord non anticipé, et il faut le dire.** Le lanceur met en pause le
bras GPQA par construction. Il en a trouvé un et l'a arrêté :
`bras arrete (PID 65360), 115 enregistrements conserves`. Il le reprend en fin
de run. Ce n'était pas dans mon « zéro verdict » — c'est le lanceur, pas moi,
mais je l'avais annoncé sans cette réserve.

#### Dégât 1 — un arrêt dur rend l'exercice en vol irrécupérable

`java/bowling` était masqué au moment de l'arrêt. En variante D le pilote SORT
la suite d'acceptation et `.meta/` pendant que l'agent travaille, et les remet
dans un `finally`. **Un `Stop-Process -Force` ne déroule pas le `finally`.**
L'exercice est resté amputé de `.meta/config.json` ; la reprise a levé
`FileNotFoundError` et **écrit un enregistrement de verdict** :

```json
{ "tests_outcomes": [], "exception": "FileNotFoundError(2, ...)", ... }
```

Sans `turns`. Un dépouillement naïf le compte en **échec jugé** — c'est-à-dire
qu'il *fabrique* un échec sur un exercice jamais joué.

Réparé par `reparer_exercice_interrompu.py`, qui appelle `demasquer()` du
pilote — jamais une copie — sur les **feuilles** du masque et non sur les
dossiers de tête : `src/` existe des deux côtés, et le déplacer en bloc aurait
effacé le code de l'agent. 5 fichiers remis, code de l'agent intact,
enregistrement de plantage **déplacé** en `.dsh.results.json.plantage`, pas
effacé. `java/bowling` n'a plus de verdict et le pilote est passé au-delà : il
se rejoue explicitement en fin de run, avec `-Exercices java/bowling`.

`etat_run.py` porte désormais une **quatrième population**, `plantage`, hors
dénominateur au même titre que `coupe` et `infra`.

#### Dégât 2 — j'ai lu le verdict au mauvais endroit, et publié un chiffre faux

J'ai lu `d["ok"]` à la **racine** de `.dsh.results.json`. Ce champ n'existe pas :
il vaut `None` partout, et tout exercice est alors compté en échec. J'en ai tiré
« java : 6 exercices, 6 FAIL » — **faux**. `java/book-store` est un PASS
(`turns[0].ok = True`, `rc = 0`). Le garde-fou de `rejuger.py` a crié « le juge
PASSE alors que le verdict enregistré est un échec » : il criait à cause de ma
liste, pas d'une divergence du juge.

Le verdict est dans `turns[-1]["ok"]`, doublé par `tests_outcomes`. Un seul
lecteur désormais, `etat_run.py`, pour que la faute ne se reproduise pas dans
trois scripts.

**État re-mesuré, 73 verdicts :**

| piste | rendus | pass | juge | coupe | infra | taux |
|---|---|---|---|---|---|---|
| cpp | 26 | 25 | 0 | 1 | 0 | 100,0 % |
| go | 39 | 26 | 11 | 1 | 1 | 70,3 % |
| java | 8 | 2 | 6 | 0 | 0 | 25,0 % |
| **TOTAL** | **73** | **53** | **17** | **2** | **1** | **75,7 %** |

Brut, coupures et infra comptées en échec : 53 / 73 = 72,6 %.

#### Trois échecs java classés, et une touche pré-enregistrée

**`java/bottle-song` — S2, mécanisme exact, et ce n'est pas un cas fondateur.**
La pré-inscription du 27/08, déposée **avant** que java commence, annonce pour
cet exercice : *« bloc de sortie rendue sur 40 lignes, sans ponctuation de
code : un séparateur TERMINAL y est invisible »*. Le juge : attendu et obtenu
sont identiques caractère pour caractère, l'agent ajoute **une ligne vide de
plus** avant la fermeture. Vérifié octet à octet (`cat -A`). C'est le mécanisme
de `go/beer-song`, reproduit dans une autre langue, sur un autre exercice, et
celui-ci compte.

**`java/alphametics` — S3, et la preuve est dans le code de l'agent.**
L'énoncé ne donne jamais le puzzle comme une chaîne : un bloc rendu en colonnes,
et en prose `SEND + MORE = MONEY` avec **un seul** `=`. La suite passe
`"I + BB == ILL"` avec `==`. L'agent écrit `userInput.split("=")`
(`Alphametics.java:15`) et ses propres tests emploient `"A + B = C"`,
`"AS + A = MOM"`, `"ABC + DEF = GHIJ"` — tous repris de l'énoncé, tous passants
(MaisonTest 4/4), donc **le solveur marche**. Sur `==`, `split` rend
`["I + BB ", "", " ILL"]` : membre droit vide, équation insoluble,
`UnsolvablePuzzleException` sur les 9 cas non triviaux. `testLeadingZero` passe
parce qu'il *attend* une exception — il passe pour la mauvaise raison.

**`java/bank-account` — S4 a renoncé, et elle avait raison.** Le stub déclare
bien `throws BankAccountActionInvalidException` sur ses cinq méthodes, mais S4
exige les **deux** conditions et l'énoncé n'est pas muet sur l'erreur : ligne 8,
*« operations against a closed account must fail »*. L'énoncé annonce **une**
erreur et la suite en exige **quatre** : montants négatifs (jamais mentionnés),
retrait supérieur au dépôt (pas davantage), et le texte exact `"Account closed"`
contre `"Account is closed"`. Tout le fond passe, y compris
`canHandleConcurrentTransactions`, le seul sujet réellement traité par l'énoncé.

**P1 prend un mauvais départ, et c'est enregistré tel quel.** Sur les trois
nouveaux échecs java jugés — hors les deux qui l'ont inspirée — **aucun** n'a
pour seule divergence un libellé : `separateur_d_entree`,
`exigence_et_libelle`, `separateur_terminal`. Aucun taux n'est calculé ici : la
règle d'arrêt du 27/08 tient, le dépouillement fait foi une seule fois, sur le
run terminé.

**Reste à faire :** `java/circular-buffer` (échec arrivé pendant la réparation)
n'est pas encore rejugé — le conteneur sert le pilote en vol, et deux gradle
concurrents dans un même conteneur peuvent se marcher dessus.

---

## R28w — 27/08 : l'appariement etait asymetrique. A information egale, l'ecart est de +30,5 points

**Ce qui etait faux.** `comparer_protocoles.py` comparait la variante D a
`pass_rate_2` du board, soit 52,0 %. C'est le taux du DEUXIEME essai : le modele
a d'abord vu le fichier de test officiel tomber, a recu **la sortie d'echec**,
puis a recommence. La variante D joue un tour et ne recoit aucun retour. On
mettait un bras sans retour face a un bras avec retour, et on publiait
« parite ». Defaut trouve par l'audit Fable du 27/08, verifie a la main.

**Le board publie les deux** (`reports/specdec_20260825_ctxsweep_dflash2/
aider_polyglot_stats.yml`) : `pass_rate_1 = 16,9 %`, `pass_rate_2 = 52,0 %`. Le
retour du juge vaut donc **+35,1 points pour ce modele meme**.

**L'essai 1 du board est-il aveugle ?** OUI, verifie deux fois.
 * Code : `benchmark/benchmark.py:744` `ignore_files.update(test_files)` puis
   `:747` `solution_files.difference_update(ignore_files)` -- seuls les stubs
   entrent dans `fnames`.
 * Empirique, et c'est la preuve qui compte : `verse`, `verses`, `sing`,
   `fromPov`, `isSubset` apparaissent **0 fois** dans les enonces et le modele
   les a emises avec leur signature exacte. Il avait le stub, pas le test.

### Le chiffre, appariement honnete (les deux bras aveugles)

| jeu | n | D 1 tour | board `pass_rate_1` | ecart | gagne/perd | p exact |
|---|---|---|---|---|---|---|
| tous les aveugles | 105 | 58,1 % | 15,2 % | +42,9 | 49 / 4 | 7,1e-11 |
| sans cpp (semis) | 84 | 47,6 % | 15,5 % | +32,1 | 31 / 4 | 3,5e-06 |
| **sans cpp ni ledger** | **82** | **46,3 %** | **15,9 %** | **+30,5** | **29 / 4** | **1,1e-05** |

Pour memoire, l'ancien appariement (D 1 tour contre `pass_rate_2`) : +7,6 sur
105, **0,0 sur 84**, -2,4 sur 82. C'etait la « parite » -- obtenue une main
attachee.

### Deux contaminations mesurees le meme jour

**1. cpp : le semis n'est pas un supplement, c'est la difference entre rien et
tout.** Le stub d'origine cpp est un NAMESPACE VIDE de 8 lignes (conserve en
`*.stub-origine`, 26 fichiers) ; le semis du 27/08 y a mis la declaration de
classe complete, DANS LE CORPUS VIERGE que le pilote lit en direct. Le run aider
date du **25/08** : il est anterieur. Sur cpp les deux bras n'ont donc pas recu
le meme stub. Le 100 % cpp est INUTILISABLE et n'entre dans aucun chiffre
publie.

**2. 5 exercices cpp ont joue DEUX tours -- ils ne sont pas aveugles.**
`pilote.py:1071` reinjecte `erreurs`, qui sort de `lancer_tests()` sur les
fichiers de test OFFICIELS. Sequelle de l'etape « complement » de
`mesurer_valeur_du_semis.ps1:136-141`, qui rejoue en `--tours 2`.
    cpp/all-your-base   PASS au tour 2       cpp/phone-number   PASS au tour 2
    cpp/bank-account    PASS au tour 2       cpp/zebra-puzzle   PASS au tour 2
    cpp/parallel-letter-frequency  FAIL
**4 PASS sur 25 en cpp ont ete obtenus avec la sortie d'echec officielle en
main** : c'est le protocole du board, pas la variante D. Isoles par le script.

### Ce que le chiffre autorise, et ce qu'il n'autorise pas

 * **Autorise** : a information egale, l'agent local est tres au-dessus du
   modele seul. +30,5 points, 29 gains contre 4 pertes, p ~ 1e-5.
 * **NON autorise** : « a capacite egale ». L'asymetrie restante est le
   protocole agentique lui-meme -- l'agent compile, execute, itere ; le modele
   du board ne peut rien executer. C'est le SUJET de la mesure, pas un biais,
   mais ca s'ecrit.
 * Handicap reel en face : l'agent ecrit ses propres tests et ne voit jamais la
   suite officielle.
 * **Dette non deduite** : le modele local tourne sous un fork portant
   « Revert draft sampling in rejection sampling », echantillonne a t=1,0. La
   losslessness du specdec n'est PAS mesuree (`SPECDEC_4090_BENCH.md:588`).
 * **Le bras symetrique de `pass_rate_2` (D a 2 tours) n'existe pas.**

### Classification

`java/pov` RECLASSE `ambiguite/libelle_seul` -> `fond/mapping_condition_message`.
Ma classification etait fausse sur pieces : `.docs/instructions.append.md:57-64`
publie les DEUX chaines exactes AVEC leur condition, dans un bloc java commente,
et l'agent les avait recopiees toutes les deux (`Tree.java:50` et `:71`). Il a
laisse celle de `fromPov` se propager a travers `pathTo` au lieu de la
convertir. La famille `libelle_seul` compte donc **9**, pas 10.

Ajoutes : `java/twelve-days` (separateur terminal -- 15 tests officiels sur 15
tombent, 7 tests maison sur 7 passent, cause unique un `\n` final ; l'enonce
publie les paroles COMPLETES et dit « should _exactly_ match », mais un bloc
markdown ne peut pas montrer une terminaison) et `java/state-of-tic-tac-toe`.
**38 echecs juges, 38 classes.**

**Etat du run a cette lecture : 110 verdicts. Lecture d'etape. La regle d'arret
tient -- le depouillement fait foi une seule fois, sur les 225.**

---

## R28x — 27/08 : CORRECTION DE R28w. Le retour du juge au tour 2 n'est pas un defaut, c'est un ordre operateur

**Ce que R28w disait de faux.** J'y ai ecrit que `pilote.py:1071` -- qui rend a
l'agent la sortie d'erreur de la suite officielle au tour 2 -- etait une
« contamination » et un « defaut de conception ». **C'est faux.** Le lanceur
porte l'ordre, date, `lancer_polyglot_complet.ps1:50-68` :

> ORDRE OPERATEUR, 27/08 07:10. Au tour 2, `pilote.py` renvoie a l'agent la
> SORTIE D'ERREUR de la suite officielle (jamais son code source) avec la
> relance mot pour mot d'aider. […] C'est la definition de `pass_rate_2`. Les
> chiffres publies auxquels on se compare -- 52,0 %, Qwen3 32B 40,0, Qwen3
> 235B-A22B 59,6 -- sont TOUS des `pass_rate_2`. A `--tours 1` on produisait un
> `pass_rate_1`, qui ne se pose a cote d'aucune de ces lignes.

Un bras D a 2 tours est le symetrique HONNETE de `pass_rate_2`. Rien a corriger
la-dedans, et je n'y touche pas.

**Ce qui reste vrai de R28w**, et que le lanceur dit avec moi : le run en cours
est a UN tour, donc il produit un `pass_rate_1`. Le comparer a 52,0 % etait
faux. Le chiffre a information egale (46,3 % contre 15,9 % sur 82, p ~ 1e-5)
tient sans changement.

**LE DEFAUT REEL, plus etroit : LE BRAS N'EST PAS HOMOGENE.** 107 exercices a
1 tour, 5 exercices cpp a 2 tours -- residu de l'etape « complement » de
`mesurer_valeur_du_semis.ps1:136-141`, qui rejoue en `--tours 2` DANS LE MEME
repertoire de run. 4 des 5 basculent FAIL -> PASS. Un meme bras melange donc
`pass_rate_1` et `pass_rate_2`.

**Pourquoi personne ne l'a vu.** `len(tests_outcomes)` etait le seul indice
disponible, et il ne distingue pas « 2 tours demandes, converge au premier » de
« 1 tour demande ». Le pilote ecrivait deja `variante`, `sans_tests`,
`sans_corriges`, `tests_maison` -- avec, en commentaire, exactement le bon
principe : « sans ca, deux runs du meme pilote produisent des
`.dsh.results.json` indiscernables et on finit par comparer B a C sans le
savoir ». Le budget de tours manquait a cette liste. C'est tout le defaut.

### Correctifs poses le 27/08

 * `pilote.py` : nouveau champ **`tours_demandes`**, ecrit dans chaque
   `.dsh.results.json` au meme titre que `variante`. Additif, ne change aucun
   comportement. Le pilote en vol a ete lance une seule fois
   (`lancer_polyglot_complet.ps1:231`, tout `--langages` d'un coup) : editer le
   fichier n'atteint pas le processus, verifie avant d'ecrire.
 * `etat_run.py` : nouvelle **`alerte_bras_heterogene()`**, appelee a chaque
   depouillement. Elle groupe par budget de tours, nomme le taux correspondant
   (`pass_rate_1` / `pass_rate_2`), liste le groupe minoritaire quand il fait
   8 exercices ou moins, et refuse de laisser moyenner. Elle tire sur le cas
   reel : 107 a 1 tour / 5 a 2 tours.
 * `comparer_protocoles.py` : en-tete reecrit -- le tour 2 n'y est plus decrit
   comme un defaut mais comme la definition de `pass_rate_2` ; le defaut nomme
   est l'heterogeneite du bras.

### Reste a faire, BLOQUE SUR LA CARTE

Rejouer les 5 cpp a 1 tour pour rendre le bras homogene. **Non lance** : le run
principal est en vol (PID 51944, depuis 14:52:32) et la carte est a 94 % avec
23 998 / 24 564 MiB. Un second pilote contre le meme llama-server serialiserait
les appels ; avec `--veille-silence 600` sur le run principal, une attente de
plus de 600 s declencherait des coupures fantomes et abimerait la mesure en
cours. Garde-fou ressource partagee : occupe => attendre, jamais tuer.

Commande, a lancer quand la carte est libre :

```
python pilote.py pi_D_t1_dflash2 --agent pi --accueil-pi $env:USERPROFILE\.pi-bench-polyglot \
  --dotenv <racine>\.env --tests-maison --conteneur pi-polyglot-tests \
  --exercices cpp/all-your-base,cpp/bank-account,cpp/parallel-letter-frequency,cpp/phone-number,cpp/zebra-puzzle \
  --tours 1 --delai-tour 1800 --veille-silence 600 --effort medium \
  --fournisseur local-mesure --modele specdec-q38-dflash2
```

Les 5 `.dsh.results.json` doivent etre retires d'abord, sinon `pilote.py:1044`
saute l'exercice. **Retrait de fichiers = autorisation humaine**, non fait.

---

## R28y — 27/08 : la signature d'ambiguite NE SEPARE PAS. Lecture d'etape, contre moi

**Lecture d'ETAPE, pas un depouillement.** La regle gelee dans
`verifier_prediction.py` et dans `PREDICTION_PISTES_RESTANTES.md` dit que
l'analyse fait foi **une seule fois, sur les 225 verdicts du run termine**. Ce
qui suit sert a piloter le travail, jamais a conclure. Je l'inscris quand meme,
maintenant, parce que ca va dans le sens qui me derange et qu'attendre serait
choisir le moment.

### Ce que la mesure dit, a 46 echecs juges sur 114 depouilles

`python verifier_prediction.py pi_D_t1_dflash2`. Fisher exact unilateral,
Bonferroni sur 4 signatures.

| lecture | S1 | S2 | S3 | S4 |
|---|---|---|---|---|
| tout, fondateurs compris | -7,2 pt | **+19,9 pt** p×4 = 0,195 | **+32,5 pt** p×4 = 0,197 | +13,0 pt |
| hors 3 fondateurs | -39,4 pt | +17,3 pt p×4 = 0,338 | +30,4 pt p×4 = 0,308 | +3,0 pt |
| hors fondateurs **et** hors fond | -33,3 pt | +10,5 pt p×4 = **0,990** | +26,3 pt p×4 = 0,621 | +9,3 pt |

**Rien ne survit a Bonferroni, a aucune ligne.** S1 est negative aux trois
lectures. S4 est plate des qu'on retire les cas qui l'ont ecrite.

### Le fait le plus genant, et il est structurel

La lecture **la plus fine** — celle que ma propre methode impose, hors
fondateurs et hors echecs de fond — est la **plus faible**. S2 tombe de
+17,3 a +10,5 pt, son p×4 de 0,338 a 0,990.

Pourquoi : **5 des 10 echecs que j'ai classes `fond` etaient signales par S2**
— `java/pov`, `java/variable-length-quantity`, `javascript/alphametics`,
`javascript/beer-song`, `javascript/bottle-song`. Les retirer retire donc
precisement les cas qui faisaient paraitre la signature predictive.

Deux lectures possibles, et je ne peux pas trancher seul :

* le critere gele a ete applique sans regarder si l'exercice etait signale — et
  c'est ce que le code fait, litteralement : `verifier_prediction.py` lit la
  classe depuis `classification_echecs.json` sans consulter la prediction ;
* ou j'ai, sans le vouloir, durci en `fond` des cas signales.

C'est la premiere question posee au red team `classification-echecs-27-08.md`.

### Le detecteur rate plus de la moitie

**24 des 46 echecs n'etaient signales par AUCUNE signature**, dont les trois
premiers javascript juges. Chacun est soit une famille d'ambiguite que le
detecteur ne sait pas voir, soit un echec de fond sans rapport avec l'enonce.
Le detecteur couvre donc, au mieux, la moitie du phenomene qu'il pretend nommer.

### Ce que ca ne remet PAS en cause

L'ecart **+30,5 points** de R28w/R28x est un appariement de verdicts PASS/FAIL
entre deux protocoles. Il ne depend ni de la classification, ni des signatures :
aucune ligne ci-dessus ne le touche. Ce qui est atteint, c'est la these
SECONDAIRE — « les echecs restants viennent surtout de l'enonce ». A 46 echecs,
les pieces ne la soutiennent pas au seuil corrige.

### Ce qu'il faut faire, et ne pas faire

* **Ne pas** reecrire les signatures pour ameliorer le p. Le pre-enregistrement
  a fige la liste ; la retoucher apres avoir vu les verdicts detruirait la seule
  chose qui rendait la prediction falsifiable.
* **Ne pas** conclure a l'inverse non plus : 46 echecs, ce n'est pas 225, et
  javascript vient a peine de commencer. Un ecart non significatif a mi-parcours
  n'est pas une refutation.
* **Attendre** les 225 verdicts, puis depouiller une fois.
* En attendant, ne plus ecrire nulle part que « les echecs viennent surtout de
  l'enonce » sans citer ce tableau a cote.

---

## R28z — 27/08 : RETRACTATION DU +30,5. Le masquage avait un trou, et l'agent l'a utilise

**Ce qui est retire.** La phrase publiee en R28w/R28x —

> un agent local qui **ecrit ses propres tests** et **ne voit jamais la suite
> officielle** reussit 46,3 % contre 15,9 % pour le meme modele sous le
> protocole du board a information egale, ecart **+30,5 points**, p = 1,1e-5

— est **fausse sur sa premisse** et **fausse sur sa magnitude**. Elle ne doit
plus etre citee. Trouvee par le red team GLM-5.3 du 27/08 (constat F1),
verifiee sur pieces ici avant d'etre reprise.

### Le trou

`pilote.py::chemins_a_masquer` ne retirait que `files.test` de
`.meta/config.json`. Or les exercices go rangent leur **table de cas
officielle** sous une autre cle de la meme config :

```
"test":   ["word_search_test.go"]     <- masque
"editor": ["cases_test.go"]           <- JAMAIS masque
```

et `cases_test.go` porte les entrees **et les sorties attendues**,
`expectError` compris. `go/robot-simulator` est pire : ses
`robot_simulator_step2_test.go` et `_step3_test.go` sont des **suites
completes**, declarees dans aucune cle.

**19 exercices de l'intersection** etaient concernes : 18 go et `java/satellite`.

### Ce n'est pas une deduction — l'agent le dit

Sortie de `go/book-store`, mot pour mot :

> « I then extended them to cover all 18 cases from the provided
> `cases_test.go` data to confirm the solution matches **the full hidden
> suite** — all pass. »

`go/alphametics` : « a runner over the provided `testCases` in `cases_test.go`
comparing against the exact expected maps ». `go/bottle-song`, `go/word-search`,
`go/forth`, `go/say`, `go/sublist`, `go/two-bucket`, `go/bowling` : idem.
**9 exercices go citent le fichier nommement. Les 9 passent.**

### Le cout, mesure

**Instant de lecture : 126 exercices juges cote D, intersection aveugle 121.**
Le run est en vol, ces chiffres bougeront ; la ligne « publiee » ci-dessous est
la lecture du matin sur un run plus jeune, elle n'est pas re-mesurable. Toutes
cellules hors confondus documentes (cpp — stubs semes le 27/08 contre un run
aider du 25/08 — et les deux `ledger`), bras aveugle, contre `pass_rate_1` :

| cellule | n | D | board | ecart | b / c | McNemar exact |
|---|---|---|---|---|---|---|
| **publiee ce matin** (run plus jeune) | 82 | 46,3 % | 15,9 % | **+30,5** | 29 / 4 | 1,1e-5 |
| A. meme base, a 126 juges, fuite comprise | 98 | 41,8 % | 18,4 % | +23,5 | 32 / 9 | 4,3e-4 |
| **B. fuite retiree (F1)** | **79** | **34,2 %** | **17,7 %** | **+16,5** | **21 / 8** | **0,024** |

**Deux causes distinctes, et il faut les separer :**

* de **+30,5 a +23,5** : l'**avancement du run**. javascript est entre depuis, et
  D y perd. Rien a voir avec la fuite. La lecture du matin portait sur le
  sous-ensemble favorable.
* de **+23,5 a +16,5** : la **fuite de masquage**, soit **−7,0 points**. Les 19
  exercices fuites font 14 PASS cote D contre 4 cote board.

Par piste, cellule B :

| piste | n | D | board | ecart | b / c | p |
|---|---|---|---|---|---|---|
| go | 20 | 55,0 % | 20,0 % | +35,0 | 7 / 0 | 0,016 |
| java | 44 | 31,8 % | 11,4 % | +20,5 | 12 / 3 | 0,035 |
| javascript | 15 | 13,3 % | 33,3 % | **−20,0** | 2 / 5 | 0,45 |

**La direction s'inverse en javascript.** Non significatif a n = 15, mais c'est
la seule piste ou le board devance l'agent, et elle n'etait pas commencee quand
le +30,5 a ete ecrit.

### Ce qui survit, et ce qui ne survit pas

* **Survit** : la direction sur go et java, chacune significative isolement.
  L'ecart global +16,5 reste positif, p = 0,024.
* **Ne survit pas** : la magnitude « +30,5 », la premisse « ne voit jamais la
  suite officielle », et toute lecture qui generalise a « le polyglot ». Un p de
  0,024 ne survivrait a aucune correction de multiplicite.

### Corrige

* `pilote.py` : `tests_hors_config()` masque desormais tout fichier qui porte un
  nom de test **et** des cas (`[Tt]estCases`, `func Test`, `@Test`, `#[test]`,
  `TEST_CASE`, `def test_`, `describe(`, `it(`), quelle que soit la cle de
  config. Essai a blanc sur le corpus vierge : attrape `cases_test.go` et les
  deux suites `_stepN_` de robot-simulator, **n'attrape pas**
  `cpp/*/test/tests-main.cpp` (qui ne porte que `#define CATCH_CONFIG_MAIN` --
  le masquer casserait la construction sans rien cacher).
* `comparer_protocoles.py` : deux blocs de plus, `APPARIEMENT PROPRE` et
  `CELLULE PUBLIABLE`, avec les confondus nommes dans `--exclure` plutot que
  retranches a la main.

**CE CORRECTIF NE SAUVE PAS LE RUN EN VOL.** Le pilote PID 51944 a importe
`pilote.py` a 14:52 ; Python ne relit pas un module charge. `pi_D_t1_dflash2`
garde sa fuite jusqu'au bout ; elle se retranche a la lecture, pas a la source.
Un bras propre demande un run neuf.

### Ecart avec le rapport du red team, declare

Le red team compte **21** exercices fuites (20 go + satellite) et publie
36,1 % / 11,5 % sur 61. Je compte **19** (18 go + satellite) et publie
34,2 % / 17,7 % sur 79. Les deux lectures ne portent pas sur le meme instant du
run ni sur les memes exclusions de confondus. Je publie la mienne parce que sa
regle est ecrite dans l'instrument et rejouable ; l'ecart de comptage n'est pas
elucide et il est declare comme tel.

---

## R29 — 27/08 : la sonde d'adaptateur. Un jugement remplace par une mesure, et l'instrument se retourne contre moi sur commande

### Le probleme qu'elle resout

Le critere gele classe un echec en `ambiguite` si DEUX conditions tiennent :
(1) la logique passe les cas voisins, nommement ; (2) l'element divergent est
absent de tout ce que l'agent peut voir.

La condition (2) se verifie par lecture : on ouvre `TASK.md` et le stub, on
cherche, on trouve ou on ne trouve pas. **La condition (1) se verifiait au
jugement**, et c'est la que je pouvais me tromper dans mon sens. Trois echecs
javascript l'ont montre nettement : les seuls tests officiels qui passaient le
faisaient parce que l'agent rendait une valeur vide pour toute entree. Compter
cela comme � la logique passe les cas voisins � est une complaisance.

### La regle de la sonde

Sur une **copie hors du repertoire du run**
(`tmp.benchmarks/_sonde_adaptateur/`), appliquer **UNE substitution**, portant
**uniquement sur la lecture de l'entree ou la convention en cause**, puis
relancer la suite officielle par le meme juge docker.

Ce qui est interdit : toucher une comparaison, une borne, un tri, une formule.
La substitution doit tenir dans un `diff` de quelques lignes et se lire d'un
coup d'oeil. Les sorties sont conservees dans
`scripts/polyglot_dsh/sonde_adaptateur_*.txt` pour etre rejouables.

  la suite officielle passe  -> l'algorithme etait juste, l'echec tient a la
                                seule convention non publiee
  elle echoue encore         -> il y a aussi du fond, et le classement doit
                                le dire

### Ce qu'elle a donne

| exercice | substitution unique | avant | apres |
|---|---|---|---|
| `javascript/killer-sudoku-helper` | lire `{sum, size, exclude}` au lieu de `[somme, taille]` | 13 echecs / 23 | **PASS** |
| `javascript/palindrome-products` | `{ min, max }` -> `{ minFactor: min, maxFactor: max }` | 9 echecs | **PASS** |
| `javascript/meetup` | `dayIndex[weekday]` -> `dayIndex[...toLowerCase()]` | 95 echecs / 163 | **163 passed, 163 total** |
| `java/forth` | decouper la LIGNE en jetons sur les espaces | 54 echecs / 90 | **31 echecs / 90** |

Les trois premiers cas : la suite officielle passe **en entier**, et le seul
fichier qui tombe ensuite est `maison.test.js` — les tests que l'AGENT avait
ecrits, qui appellent l'ancienne signature. `meetup` est le cas extreme : les
95 cas officiels (sept descripteurs, sept jours, bornes de mois, bissextiles)
etaient **tous** justes, et la totalite de l'echec tenait a la CASSE d'une
chaine, dans un exercice dont le stub vierge est `export const meetup = () =>`
— sans aucun parametre declare.

### Le quatrieme cas est le plus important

`java/forth` est classe **`fond`** par moi. Je l'ai sonde exprès, parce qu'un
instrument qu'on n'applique que la ou il donne le bon resultat n'est pas un
instrument.

Il ne passe pas. Le decoupage en jetons — la correction du contrat d'entree —
fait tomber les echecs de 54 a 31 sur 90, et s'arrete la. Ce qui reste est du
fond, et se nomme : `testOverCopiesTheSecondElementIfThereAreMoreThanTwo`
attend `[1, 2, 3, 2]` et obtient `[2, 3, 2, 1]` — **la pile de l'agent est
dans l'ordre inverse**. Aucune convention ne repare cela.

**La sonde ne produit donc pas mecaniquement un PASS.** Elle separe. Le
classement `fond` de `java/forth` est desormais confirme par une mesure et non
par mon argument, et le chiffre est publiable tel quel : le contrat d'entree
expliquait 23 des 54 echecs, les 31 autres sont des defauts.

### Ce que ces mesures n'autorisent PAS a dire

Trois PASS sur une seule piste, sur des cas que je soupconnais deja. A porter
avec le resultat, sans quoi il est trompeur :

1. **Biais de selection assume.** J'ai sonde la ou j'avais vu la signature
   (suite officielle qui tombe en bloc, reussites vides). Sept entrees
   `contrat_*` ou `signature_du_stub_contredite` restent non sondees, dont
   `java/rational-numbers`, `java/custom-set`, `java/rest-api`,
   `javascript/grep`, `javascript/grade-school`. Tant qu'elles ne le sont pas,
   la mesure porte sur quatre cas, pas sur une population.

2. **La piste des trois PASS est celle ou l'agent PERD.** javascript est a
   **-20,0 points** contre le board (n = 15, p = 0,45, R28z). C'est le fait
   genant et il faut le dire dans le meme souffle : montrer que trois echecs
   javascript sont des conventions et non de l'incompetence **n'implique pas**
   que l'agent y soit meilleur. Les deux choses coexistent — les enonces
   javascript laissent beaucoup de conventions ouvertes, ET l'agent y perd.
   Toute lecture qui transforme la premiere en la seconde est fausse.

3. **La sonde etablit (1), pas (2).** Un exercice peut avoir un algorithme
   parfait ET un element divergent parfaitement visible : la sonde passerait,
   et le classement resterait `fond` par la condition (2). C'est le cas de
   figure a surveiller ; il n'est pas encore survenu, mais rien ne l'empeche.

4. **Elle ne dit rien du board.** Elle mesure ce que l'agent aurait obtenu si
   la convention lui avait ete donnee. Elle ne dit pas ce que le meme modele
   aurait fait sous le protocole aider, ou la suite officielle est visible et
   la question ne se pose pas.

### Reserve de protocole

`_sonde_adaptateur` est un run bidon cree a cote du run reel ; **rien n'est
ecrit dans `pi_D_t1_dflash2`**. Deux precautions apprises a la dure ce soir :
la copie doit inclure les fichiers en point (`rejuger.py` refuse un exercice
sans `.dsh.results.json`, et une copie par `*` les saute silencieusement — j'ai
lu pendant plusieurs minutes une sortie perimee en croyant sonder) ; et la
sortie reelle du juge doit etre sauvegardee avant la sonde, puisque
`rejuger.py` ecrit au meme chemin.

---

## R30 — 27/08 au soir : le red team casse ma regle de sonde, la cellule est remesuree, et javascript revient a parite

### 1. La trouvaille HIGH est juste, et elle porte sur mon instrument

Le red team GLM-5.3 (`redteam/sonde-adaptateur-27-08.md`, 66 appels, 2 049 s)
a attaque la sonde d'adaptateur. Une trouvaille HIGH, et je l'accepte sans
discussion parce qu'elle me coute :

> **rational-numbers** : la substitution remplace le corps de retour de `exp`
> par un appel a une autre formule. Intention defendable, mais la regle L6573
> l'interdit mot pour mot.

C'est exact. R29 ecrit : « Ce qui est interdit : toucher une comparaison, une
borne, un tri, **une formule**. » Et la sonde de `java/rational-numbers`
remplace bien `Math.pow(num, e) / Math.pow(den, e)` par `expOf(exponent)`.
Que la cible soit une methode que l'AGENT a ecrite et que je n'ai pas touchee
ne change rien a la lettre de la regle.

### 2. La regle, recrite en deux classes au lieu d'une

Plutot que d'elargir la regle en silence pour y faire entrer le cas qui
m'arrange — exactement la derive reprochee sur `java/poker` —, je la coupe en
deux, et la seconde classe est declaree plus faible que la premiere.

**Classe A — sonde d'adaptateur.** UNE substitution portant sur la lecture de
l'entree ou sur la FORME de la sortie : nom de cle, casse, separateur,
notation, structure de retour. Aucune expression calculee n'est touchee.
C'est la sonde forte. Sept cas : killer-sudoku-helper, palindrome-products,
meetup, grep, grade-school, rest-api, variable-length-quantity, forth.

Le red team releve en MEDIUM que quatre de ces sondes portent sur la SORTIE et
non sur « la lecture de l'entree ». La clause « ou la convention en cause » les
couvrait, mais la frontiere n'etait pas ecrite. Elle l'est maintenant : entree
ET forme de sortie sont dans la classe A ; le calcul n'y est jamais.

**Classe B — sonde d'aiguillage.** L'agent a implemente PLUSIEURS operations,
chacune exacte, et n'avait qu'a deviner laquelle un nom unique du stub designe.
La substitution ne cree aucune logique : elle rebranche le nom sur l'une des
implementations de l'agent, non modifiee. C'est une sonde plus faible, parce
qu'elle suppose etabli que les deux implementations sont justes — ce qui se
verifie separement, ou pas du tout.

Un seul cas : `java/rational-numbers`, ou l'agent avait ecrit `exp` (r^x) ET
`expOf` (x^r), et ou le stub n'offre qu'une methode. **Ce resultat se cite
comme classe B, jamais melange aux sept autres.**

### 3. Deux corrections de compte, a moi

- **R29 disait « sept entrees non sondees ».** Faux : cinq reelles, et j'y
  comptais `custom-set` qui n'est pas de la meme famille tout en omettant
  `variable-length-quantity`. Le red team a raison sur l'arithmetique. La
  limite est de toute facon eteinte par les faits : les dix sont sondees.
- **Le libelle du confondu `ledger` est faux dans mes textes.** J'ecrivais
  « leur suite est dans le fichier de solution ». C'est la SOLUTION DE
  REFERENCE qui est semee dans le stub, pas la suite de tests. L'exclusion
  reste justifiee ; sa raison etait mal dite.

### 4. La copie de sonde : LOW confirme sur pieces

`killer-sudoku-helper` : la copie a perdu six fichiers — `.eslintrc`, `.npmrc`,
`.docs/instructions.md`, `.meta/config.json`, `.meta/tests.toml`,
`.meta/proof.ci.js`. Tous inertes pour le juge. Et le dernier merite d'etre
nomme : `.meta/proof.ci.js` est **la solution de reference**. Son absence de la
copie ne peut que durcir la sonde. Les neuf autres copies sont rigoureusement
identiques au run.

La regle se lit desormais « copie INTEGRALE, fichiers caches compris ».

### 5. La jurisprudence `meetup`, ecrite au lieu d'etre sous-entendue

Le red team demande que la faiblesse litterale de `meetup` soit inscrite comme
regle et non laissee implicite. Elle l'est :

> **La majuscule d'un nom propre dans une phrase anglaise n'est pas une
> specification de format de chaine.** Un enonce qui ecrit « the first Friday
> of next month » l'ecrirait identiquement si l'argument attendu etait
> `'friday'`, `'FRIDAY'` ou l'entier 5. Cette lecture vaut pour tous les
> exercices ou une valeur apparait UNIQUEMENT dans la prose narrative. Elle NE
> vaut PAS quand la valeur apparait dans un bloc de code, un tableau ou un
> schema de sortie — voir `javascript/queen-attack`, ou le plateau attendu est
> DESSINE en majuscules dans un bloc `text` et ou l'exercice part donc en
> `fond`.

### 6. La cellule, remesuree ce soir

Le red team a mesure pendant que le run avancait, et donne
+14,9 (n = 94, p = 0,024). J'ai remesure apres : les deux chiffres sont vrais
a des instants differents. L'instant de lecture est **147 exercices juges sur
225**, `comparer_protocoles.py pi_D_t1_dflash2 2026-08-25-11-54-27--dsh-q8q4-160k-dflash2`.

| cellule | n | D | board | ecart | b/c | p |
|---|---|---|---|---|---|---|
| zero exclusion | 141 | 50,4 % | 17,7 % | +32,6 | 57/11 | ~0 |
| hors fuite F1 | 122 | 46,7 % | 17,2 % | +29,5 | 46/10 | ~0 |
| **publiable** | **99** | **34,3 %** | **18,2 %** | **+16,2** | **26/10** | **0,011** |

Par piste, cellule publiable :

| piste | n | D | board | ecart |
|---|---|---|---|---|
| go | 20 | 55,0 % | 20,0 % | +35,0 |
| java | 44 | 31,8 % | 11,4 % | +20,5 |
| javascript | 35 | 25,7 % | 25,7 % | **+0,0** |

**Ce qui a bouge depuis R28z** (+16,5 a n = 79) :

- l'ecart global tient a **+16,2** avec vingt exercices de plus, et le p passe
  de 0,024 a **0,011** ;
- **javascript est remonte de -20,0 (n = 15) a exactement 0,0 (n = 35)**, neuf
  reussites de chaque cote. Le red team, a n = 30, mesurait -6,7 : meme
  direction, run moins avance. Le deficit javascript de R28z etait un effet de
  petit n. **La phrase de R29 point 2 — « la piste des trois PASS est celle ou
  l'agent PERD » — est donc perimee et doit etre retiree de toute
  publication.** Elle etait vraie a n = 15 ; elle ne l'est plus.

### 7. Trois chiffres qui ne sont pas des echecs de contenu

Sur les echecs juges, la separation a ete faite et elle change ce qui se
classe :

- **5 coupes** — l'agent n'a jamais rendu : `cpp/parallel-letter-frequency`
  (1 150 s), `go/octal` (636 s), `java/connect` (838 s),
  `java/tree-building` (699 s), `javascript/connect` (767 s).
- **1 panne d'infra** — `go/palindrome-products` : `toolchain not available`,
  le conteneur du juge n'a pas pu telecharger go1.24.
- Verifie : **aucune** des 57 entrees classees avant cette separation n'etait
  une coupe ou une panne. Le fichier de classement etait propre.

**`go/octal` merite sa ligne.** Le fichier de l'agent est identique octet pour
octet au stub vierge. Or ce stub declare

    func ParseOctal(input string, expectedNum int64, expectErr bool)

sans valeur de retour, tandis que `octal_test.go:21` appelle
`ParseOctal(test.input)` et en attend deux. **L'exercice est inpassable en
aveugle** : respecter le seul contrat visible garantit l'echec de compilation.
Confondu structurel, a declarer comme tel — au meme titre que
`javascript/resistor-color-trio`, dont le stub declare `label()` methode quand
la suite lit `.label` propriete.

---

## R31 — 27/08 au soir : le serveur meurt en cours de run, et ce que la mesure devient

### 1. La panne, et pourquoi son ampleur est contre-intuitive

Le `llama-server` du port 8005 est mort a **20 h 12 min 33 s**, en plein run
`pi_D_t1_dflash2`. Le pilote, lui, a continue : `pi` ouvre une connexion neuve
a chaque exercice, echoue en `ECONNREFUSED 127.0.0.1:8005`, et rend un FAIL.

**71 exercices ont ete brules ainsi**, jusqu'a 20 h 36 min 53 s.

Le chiffre parait impossible et c'est le point interessant : l'intuition est
calibree sur la duree d'un exercice qui travaille — **mediane 137,6 s** — et 71
exercices auraient donc demande 2 h 43. Mais un refus de connexion ne coute
rien : **mediane 20,6 s**. La panne brule **7 fois plus vite que le travail**.
24 minutes ont suffi.

Recoupement, trois signaux independants, tous concordants :

| signal | les 71 | les 153 sains |
|---|---|---|
| duree mediane | **20,6 s** | 137,6 s |
| duree maximale | 62,8 s | 1 150 s |
| PASS | **0** | 78 |
| rang chronologique | 153 → 224, **ininterrompu** | 1 → 152 |

Aucun exercice sain n'est intercale parmi les 71. La coupure est nette.

Manifeste ecrit sur disque :
`scripts/polyglot_dsh/a_rejouer_panne_serveur_2708.json`.
**Regle : a rejouer, jamais a classer.** Ces verdicts ne mesurent rien.

Repartition : javascript 7, **python 34, rust 30**. Les deux dernieres pistes
sont **entierement perdues** — zero exercice sain sur 64.

### 2. Deux erreurs de comptage a moi, corrigees ici

- **« 7 exercices perdus »** annonce a l'operateur pendant la panne. C'etait la
  mesure a l'instant t ; le run a continue pendant l'echange. Le chiffre reel
  est **71**. L'operateur a doute du chiffre, et le doute etait fonde au sens
  ou il demandait un recoupement — c'est ce recoupement, section 1, qui
  l'etablit.
- **« 0 coupure parmi les sains »**. Faux : je lisais un champ `coupe` a la
  racine, qui n'existe pas. La coupure est portee par `tours_coupes` (racine)
  et `turns[-1].coupe`. Il y en a **8** :

| exercice | verdict | duree |
|---|---|---|
| cpp/parallel-letter-frequency | FAIL | 1 150,0 s |
| cpp/zebra-puzzle | **PASS** | 843,5 s |
| go/crypto-square | **PASS** | 710,6 s |
| go/ledger | **PASS** | 855,7 s |
| go/octal | FAIL | 635,6 s |
| java/connect | FAIL | 838,2 s |
| java/tree-building | FAIL | 699,0 s |
| javascript/connect | FAIL | 766,6 s |

La liste de 5 donnee en R30 section 7 n'etait pas fausse, elle etait partielle :
elle ne retenait que les coupures **qui echouent**. Trois coupures ont passe
quand meme.

### 3. Le trou de masquage F1 est chiffre, et il coute 31 points sur go

`pilote.py` masque les fichiers listes sous `files.test` de `.meta/config.json`.
Mesure sur les six pistes : **go est la seule touchee**, et l'ampleur exacte est
**18 exercices sur 39** (et non 19) qui declarent `cases_test.go` ailleurs que
sous `files.test` — l'agent voyait donc la suite officielle.

| sous-ensemble go | PASS | taux |
|---|---|---|
| suite officielle **visible** (trou F1) | 15/18 | **83,3 %** |
| correctement masques | 11/21 | **52,4 %** |
| ecart | | **+31,0 points** |

cpp, java, javascript, python et rust : **0 exercice** concerne. Le trou est
propre a go.

### 4. L'etat de la mesure, sans extrapolation

| piste | sains | PASS | taux | board apparie |
|---|---|---|---|---|
| cpp | 26 | 25 | **96,2 %** | 53,8 % |
| go | 39 | 26 | 66,7 % | 43,6 % |
| java | 46 | 15 | 32,6 % | 50,0 % |
| javascript | 42 | 12 | 28,6 % | 63,4 % |
| python | **0** | — | — | 52,9 % |
| rust | **0** | — | — | 46,7 % |
| **total** | **153** | **78** | **51,0 %** | 52,6 % |

Hors les 8 coupures : **75/145 = 51,7 %**, et **cpp passe a 24/24 = 100 %**.

Plancher si rien n'est rejoue : **78/224 = 34,8 %**.

### 5. L'estimation demandee, et pourquoi sa bande est large

python et rust n'ayant **aucune** mesure, le seul ancrage est le taux du board
sur les memes exercices. L'ecart pi−board, une fois F1 retire de go, vaut
**cpp +42,4 · go +8,8 · java −17,4 · javascript −34,8** : moyenne **−0,2**,
**ecart-type 29,1 points**. C'est cette dispersion qui fixe la bande, et elle
est enorme.

| | python | rust | global brut | **F1 corrige** |
|---|---|---|---|---|
| central | 17,9/34 | 13,9/30 | 49,9 % | **47,4 %** |
| bas (−1σ) | 8,0 | 5,2 | 41,6 % | 39,1 % |
| haut (+1σ) | 27,8 | 22,7 | 58,2 % | 55,8 % |

**≈ 47 %, bande 39–56 %.** C'est une extrapolation, pas une mesure, et elle ne
vaut que jusqu'au rejeu.

**Une hypothese testee et refutee.** J'attendais que l'ecart suive la presence
de la chaine d'outils cote agent, puisque la variante D lui demande d'executer
ses propres tests. Verification du PATH de l'hote : `python`, `node`, `cargo`
et `rustc` **presents** ; `go`, `java`, `javac`, `g++`, `gcc` **absents**. Or
javascript a `node` et **perd 34,8 points**, tandis que cpp n'a **aucun
compilateur** et **gagne 42,4 points**. La correlation est inverse de celle
attendue. Aucun facteur mesure ne predit l'ecart par piste — donc rien
n'autorise a resserrer la bande.

### 6. Ce qui reste ouvert, et qui pese plus que le chiffre

**cpp a 96,2 % — 100 % hors coupures — sans compilateur, contre 53,8 % pour le
banc aider sur les memes 26 exercices.** Un ecart de +42 points en faveur d'un
agent qui ne peut pas compiler demande une explication, et trois hypotheses
restent a departager sur pieces : memorisation (les exercices Exercism sont
publics), fuite de masquage d'une autre forme que F1, ou exercices simplement
plus faciles. Tant que ce n'est pas tranche, le +42 de cpp porte toute
l'estimation vers le haut sans justification etablie.

### 7. Etat du serveur

Relance detache le 27/08 au soir sous **autorisation humaine explicite**, avec
le regime **reproduit a l'identique** de celui du run, pour que le rejeu des 71
mesure la meme chose que les 153 sains : binaire `build-faq`, `-Config
q38-dflash2`, `-CtxSize 163840`, `-Ctk q8_0 -Ctv q4_0`, `-SpecDraftNMax 7`,
`--parallel 1`. Verifie : `/health` → `ok`, alias `specdec-q38-dflash2`,
`n_ctx` 163840, 27 320 697 856 parametres, 23 778 MiB de VRAM.

Le lanceur exige `-Config` : un premier essai sans ce parametre a echoue
proprement (`MissingMandatoryParameter`), ce qui est le bon comportement — il
n'y a pas de repli silencieux vers une autre configuration.

**A faire** : rejouer les 71 (~2 h de carte) plus les 3 jamais juges
(2 cpp, 1 java). Le rejeu remplace la ligne « central » de la section 5 par une
mesure.

### 8. Correction des sections 4 et 5 : je comparais au mauvais board

**L'erreur.** Les colonnes « board apparie » des sections 4 et 5 lisent
`tests_outcomes[-1]`, c'est-a-dire le board **apres 2 tentatives**. Or D tourne
a `--tours 1`. Le comparateur juste est `tests_outcomes[0]`, la **premiere
tentative**. `comparer_protocoles.py` porte d'ailleurs les deux
(`verdict_aider_1` et `verdict_aider_2`) ; j'ai pris le mauvais. RT#4 utilisait
le bon champ.

Consequence : j'ai a la fois **sous-estime l'avantage de D** et **surestime le
niveau absolu** de python et rust, qui sert d'ancrage a l'estimation.

| piste | D (sains, hors fuites go) | board a1 | board a2 | delta vs **a1** |
|---|---|---|---|---|
| cpp | 25/26 = 96,2 % | 11,5 % | 53,8 % | **+84,6** |
| go | 10/20 = 50,0 % | 10,0 % | 45,0 % | **+40,0** |
| java | 15/46 = 32,6 % | 10,9 % | 50,0 % | **+21,7** |
| javascript | 12/42 = 28,6 % | 24,5 % | 63,3 % | **+2,4** |
| python | — perdu — | 11,8 % | 52,9 % | — |
| rust | — perdu — | 20,0 % | 46,7 % | — |

Moyenne des ecarts **+37,2**, ecart-type **30,4**.

**Estimation refaite** (ancrage board a1 + cet ecart) :

| | python | rust | global /224 |
|---|---|---|---|
| bas (−1σ) | 18,5 % | 26,7 % | 42,1 % |
| **central** | **48,9 %** | **57,2 %** | **50,8 %** |
| haut (+1σ) | 79,4 % | 87,6 % | 59,5 % |

**≈ 51 %**, bande 42–59 %, au lieu des 47 % de la section 5. Les deux erreurs
se compensent en partie : ancrer sur a1 abaisse le niveau de depart et releve
l'ecart.

### 9. RT#4 « la significativite est morte en vol » — refute dans son mecanisme

RT#4 (`harness/redteam/reponse-les-pass-sont-ils-reels-27-08.md`) pose en HIGH
que la cellule publiable est passee de **+16,2 (p = 0,011, n = 99)** a
**+3,4 (p = 0,4709, n = 175)**, et en donne la cause : « l'ordre de jugement —
go/java (D-favorables) complets tot, python/rust (D-negatifs) tard », donc un
biais d'arret optionnel.

**La cause est ailleurs.** RT#4 a lu le run a **20:36:33**. Le serveur etait
mort depuis **20:12:33**. Sa cellule contient les cadavres.

| cellule facon V4 | n | D | board a1 | ecart | b/c | p exact |
|---|---|---|---|---|---|---|
| telle que RT#4 l'a lue | 179 | 20,7 % | 16,2 % | +4,5 | 29/21 | 0,3222 |
| **apres retrait des morts** | **108** | **34,3 %** | 16,7 % | **+17,6** | **29/10** | **0,0034** |

**71 des 179 exercices de sa cellule — 40 % — sont des `ECONNREFUSED`, avec
D-PASS = 0 et board-PASS = 11.** Le rapport ecrit lui-meme « python −11,8
(n=34), rust −20,7 (n=29) », soit **0/63 cumules** : ce n'est pas une faiblesse
du modele sur ces deux langages, c'est la signature de la panne. Un taux de
reussite exactement nul sur 63 exercices aurait du alerter.

Par piste, avant et apres retrait :

| piste | morts inclus (lecture RT#4) | morts retires |
|---|---|---|
| go | n=20, +40,0 | n=20, +40,0 |
| java | n=46, +21,7 | n=46, +21,7 |
| javascript | n=49, +0,0 | n=42, +2,4 |
| python | n=34, D **0,0 %**, board 11,8 %, −11,8 | aucun survivant |
| rust | n=30, D **0,0 %**, board 20,0 %, −20,0 | aucun survivant |

**Le chiffre publie n'est donc pas mort : il est reproduit et renforce.**
+16,2 / p = 0,011 a n=99 devient **+17,6 / p = 0,0034 a n=108**. La trajectoire
decroissante que RT#4 decrit (+16,5 → +16,2 → +8,1 → +5,7 → +3,4) est
exactement la dilution progressive par les 71 morts, dans l'ordre ou ils
tombaient.

**Ce qui tient dans RT#4, et qu'il faut garder** : aucun faux PASS demontre sur
les quatre chemins testes (§1) ; l'equite du board etablie (corpus gele, 0
coupe cotee en echec cote board, `@Disabled` symetrique) ; le detecteur F1
incomplet de 2 (`go/dnd-character`, `go/wordy`, tables `var tests =
[]<Type>Test` que `FLAIRS_TEST` ne voit pas) — effet delta nul, paires
concordantes ; `auditer_pass.py:166` fragile sur `tests_outcomes` vide. Sa
reserve M4 (≈ 14 echecs board a marqueurs infra) reste ouverte et va, elle,
contre D.

**Et sa limite propre etait declaree** : « Run en vol : tous les chiffres sont
horodates 2026-08-27 20:36:33. Remesure obligatoire a completion. » La remesure
etait bien obligatoire ; ce que le rapport n'a pas vu, c'est que le run
n'avancait plus depuis 24 minutes — il brulait.

### 10. Rejeu lance

Autorisation humaine obtenue. Les 71 `.dsh.results.json` faux ont ete
**deplaces** (jamais supprimes) vers
`tmp.benchmarks/_panne_2708/pi_D_t1_dflash2/`, arborescence conservee, retour
arriere par deplacement inverse. `pilote.py:1044` saute un exercice dont le
resultat existe : c'est pourquoi le retrait est necessaire.

Commande, protocole identique a l'origine (`--tests-maison` implique
`sans_tests` et `sans_corriges`, `pilote.py:1625-1627`) :

```
python pilote.py pi_D_t1_dflash2 --agent pi --accueil-pi %USERPROFILE%\.pi-bench-polyglot
  --dotenv <racine>\.env --tests-maison --conteneur pi-polyglot-tests
  --exercices <les 71, gelees dans _exercices_rejeu_2708.txt>
  --tours 1 --delai-tour 1800 --veille-silence 600 --effort medium
  --fournisseur local-mesure --modele specdec-q38-dflash2
```

Le lanceur porte desormais une garde qui **refuse de partir si `/health` ne
repond pas** sur 8005 — celle qui manquait a 20 h 12 et dont l'absence a coute
71 exercices.

**Le pilote a emis le garde-fou de chaine d'outils** reclame par le plan :

> `CHAINE D'OUTILS ABSENTE COTE AGENT : javascript — NODE_PATH ne resout pas
> @exercism/babel-preset-javascript (jest global sans node_modules local
> execute 0 test) -> 7 exercices sur 71.`

Ces 7 javascript rejouent donc sans pouvoir executer leurs propres tests, ce
qui est un protocole degrade au regard de la variante D. **A declarer au
depouillement**, pas a decouvrir apres.

---

## R32 — 27/08, audit des 75 echecs sains : le taux n'est pas sous-estime, il est SUR-estime

Audit demande sur l'hypothese de l'operateur (« les scores devraient etre
meilleurs »). Il la refute, et il refute au passage une affirmation que j'avais
faite le meme soir.

### 1. Zero bascule

**Aucun des 75 echecs sains ne bascule en PASS.** Les artefacts de banc
existent, mais aucun ne cache un code correct :

| exercice | artefact reel du banc | pourquoi il ne bascule pas |
|---|---|---|
| `javascript/food-chain` | le pilote a **plante avant le jugement** sur un fichier nomme `nul` (nom reserve Windows) cree pendant le tour ; `tests_outcomes: []` donc FAIL par defaut, alors que l'agent avait livre | rejuge en copie isolee : **10/10 tombent** (un `\n` final manquant) |
| `go/palindrome-products` | l'agent a reecrit `go.mod` (`go 1.24`, module renomme) et le banc **ne restaure pas `go.mod`** — il ne remet que `CMakeLists.txt` et `Cargo.toml` (`pilote.py:256`). Le juge est mort sur `toolchain not available` | `go.mod` vierge remis : **2 tests officiels tombent encore** |
| `cpp/parallel-letter-frequency` | sortie de juge **vide** aux deux tours (`erreurs: ""`) : le verdict ne portait aucune explication | rejuge : `12 | 6 passed | 6 failed` — vrai echec de fond |

Le seul gain defendable est le retrait de deux exercices **structurellement
impassables en aveugle** : `go/octal` (deja connu) et **`go/trinary`, nouveau**
— stub `ParseTrinary(arg string, want int64, ok bool)`, c'est-a-dire les champs
de la table de cas, quand la suite exige un retour `error`. Retires du
denominateur : go 26/37 = 70,3 %, global **78/151 = 51,7 %**, soit **+0,7 pt**.

Origine des 75 : **68 viennent d'une suite qui a reellement tourne**
(assertions), 4 d'echecs de compilation go, 1 d'environnement, 2 de sortie
vide. **Zero OOM, zero `exit 137`** — les quatre « 137 » reperes etaient des
numeros de ligne `spec.js:137`.

### 2. L'effet inverse, et il est plus grand : le run melange deux protocoles

Mesure faite independamment de l'audit, sur `tours_max` et la longueur de
`tests_outcomes` :

| piste | `tours_max` | exercices |
|---|---|---|
| **cpp** | **2** | 26 sur 26 |
| go | 1 | 39 |
| java | 1 | 46 |
| javascript | 1 | 42 |

Un run nomme `t1` porte donc un bloc cpp joue a **deux tours**, le second
nourri par la sortie d'erreur de la suite officielle. **Quatre PASS cpp
n'existent qu'au tour 2** : `all-your-base`, `bank-account`, `phone-number`,
`zebra-puzzle` (`tests_outcomes = [false, true]`).

| | tel que mesure | **t1 homogene** |
|---|---|---|
| cpp | 25/26 = 96,2 % | **21/26 = 80,8 %** |
| global sain | 78/153 = 51,0 % | **74/153 = 48,4 %** |

### 3. Correction : mon affirmation sur la chaine d'outils etait fausse

J'ai ecrit en R31 section 5 que l'hypothese « chaine d'outils » etait refutee,
au motif que cpp n'a « ni `g++` ni `gcc` » et gagne malgre tout. **J'avais
interroge MON PATH, pas celui que le lanceur donne a l'agent.**

Les pieces disent le contraire :

- cmake + MSVC presents pendant le bloc cpp (transcript `zebra-puzzle` :
  « MSVC/VS 2022 via CMake ») ;
- le lanceur a **ajoute `go\bin` et `jdk21\bin` au PATH de l'agent** avant les
  segments t1 (lignes « chaine ajoutee au PATH », journaux 12:29 et 14:52) ;
- **31/39** files go, **27/46** java, **23/42** javascript disent avoir execute
  leurs tests.

La conclusion de R28k (« 86 exercices mesures hors variante D faute de chaine »)
vaut donc pour les segments ANTERIEURS a ces ajouts, pas pour tout le run. A
reprendre : la ligne exacte de partage.

### 4. L'ecart cpp est explique, sans invoquer la memorisation

Trois avantages de protocole cumules, tous documentes :

1. **Le semis.** Les 26 stubs cpp servis pendant le run etaient les
   **declarations d'API completes** tirees de `.meta/example.h`, corps retires
   (`semer_signatures.py` ; `binary_search_tree.h` fait 105 lignes d'API contre
   5 a l'origine). C'est une fuite partielle du contrat, deliberee et declaree,
   mais derivee du corrige.
2. **Deux tours au lieu d'un** (section 2).
3. **Une chaine operante** (section 3).

Une fuite de la **suite** est en revanche exclue au niveau des fichiers : zero
test officiel hors `files.test` sur cpp, contre 18 `cases_test.go` sur go.
La memorisation n'est pas exclue, mais elle n'est **pas necessaire** pour
expliquer l'ecart.

**Le bras temoin n'existe pas.** Le commit `cd4f461` pose
`mesurer_valeur_du_semis.ps1` et le run `pi_cpp_sans_semis` comme la
justification en attente ; ce run **est absent de `tmp.benchmarks`**. Tant
qu'il n'est pas joue, la valeur du semis reste non mesuree.

### 5. Correction a `classification_echecs.json`

La preuve de `go/robot-simulator` attribue a l'agent des signatures qui sont en
fait celles du **stub vierge**, octet pour octet. A reecrire : c'est une
livraison incomplete, pas une signature choisie par l'agent.

### 6. Ce que l'audit n'a pas pu verifier, nomme

- Les transcripts complets : `wire_pi_D_t1_dflash2.jsonl` ne porte que des
  metadonnees (comptes de caracteres, empreintes) et `sortie_queue` se limite
  aux 600 derniers caracteres. Les exercices coupes n'ont aucun transcript.
- Quatre exercices restent **indetermines faute de piece**, et ils ne
  basculent pas pour autant : `java/connect` et `javascript/connect` (coupes
  par la veille-silence a 835 s et 765 s, solution = stub intact — le FAIL
  mesure la laisse, pas le code) ; `java/sgf-parsing` et `go/robot-simulator`
  (tour complet, tests maison ecrits, solution = stub intact — livraison
  incomplete de l'agent, sans transcript pour l'affirmer).
- `auditer_pass.py:166` leve un `IndexError` sur `tests_outcomes` vide — meme
  defaut que celui signale par RT#4.

### 7. Rejeu : la panne avait DEUX maillons, pas un

Le premier lancement du rejeu a echoue alors que `/health` sur 8005 rendait
`ok`. Cause : le fournisseur `local-mesure` de pi ne pointe **pas** sur 8005
mais sur **l'enregistreur 8013**
(`~/.pi-bench-polyglot/models.json`), qui relaie vers 8005 et ecrit le fil.
Cet enregistreur etait mort lui aussi. Remonte par `proxy.mjs`
(`UP_PORT=8005`, `PROXY_PORT=8013`, meme fil que le run), le pre-vol est passe
**OK en 2,2 s**.

**Deux gardes ont mordu avant que quoi que ce soit ne parte a vide**, et les
deux sont des acquis :

1. `pilote.py:1552` — refus quand une chaine d'outils manque cote agent
   (« le taux melangerait deux protocoles dans une meme colonne »). Il a fallu
   `--sans-chaine-outils` pour assumer l'ecart des 7 javascript, ecart declare
   ici.
2. Le **pre-vol** « l'agent repond-il ? » — « le banc ne part pas : un agent
   muet rendrait 225 FAIL indiscernables d'un mauvais modele ». C'est
   exactement le garde-fou dont l'absence a coute 71 exercices a 20 h 12.
