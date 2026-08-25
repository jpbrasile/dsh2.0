# Red team 5 — harnais distiller/ops/routes (25/08/2026)

- **Worker :** `deepseek/deepseek-v4-flash` via OpenRouter (mono-appel, ordre
  utilisateur : « passe les rt sur openrouter le dernier deepseek V4 flash »).
  3 charges (rôle red team + groupe de claims + fichiers complets), 3/3 servies
  (in 8367/3809/6894 tokens, out 2021/1835/2507).
- **Cible :** 13 done-claims (A1–F2) sur les commits 5566ec5 + 2056259 —
  `harness/distiller.py`, `harness/providers.yaml`, `scripts/dsh.ps1`,
  `scripts/freellm_key.py`, `scripts/ops/{distiller_nightly,julia_gate_arret,
  installer_taches_nocturnes}.ps1`. Tier OPEN uniquement (aucun fichier du
  framework privé dans les charges).
- **Règle de triage :** aucun finding accepté sans vérification de sa citation
  contre le code réel. C'était nécessaire : voir « Qualité du red team » en bas.
- Trajet initialement commandé sur freellmapi (ox-alpha) : impossible ce jour —
  limiteur local ~1 req/min + délestage amont des requêtes multi-k tokens
  (502 après ~20 s, ~17 tentatives espacées sur 5 modèles épinglés), opencode
  503. Publié comme échec, 0 USD ; bascule OpenRouter sur ordre utilisateur.

## Verdicts (12 findings + 4 claims tenus)

| # | Verdict RT | Triage | Pourquoi |
|---|---|---|---|
| A1 extraire_json fragile aux variantes du délimiteur | BROKEN | **RÉFUTÉ** | Le RT cite `rsplit(" response", 1)` — le code réel (distiller.py:354) découpe sur `</think>`. Son scénario « `</think>.` + JSON » passe par le repli `re.search(r"\{.*\}", t)` (l.359) qui opère sur le texte **post-découpe**, pas sur le raisonnement : le JSON est extrait. |
| A2 troncature si délimiteur mot naturel | PARTIAL | **RÉFUTÉ** (résidu noté) | Le scénario repose sur « response » comme mot courant — artefact. Le vrai délimiteur `</think>` littéral dans une réponse sans think est le mode de défaillance n°2 mesuré le 25/08 : `rsplit` dernier-délimiteur le gère (le JSON réel vient après). Résidu théorique : JSON réel AVANT un `</think>` littéral — jamais observé, filet A3 (retry au rerun). |
| A3 échec JSON non marqué dans distillations | HOLDS | **CONFIRMÉ TENU** | `continue` avant l'INSERT (l.549) ; rerun nu retente. |
| A4 scores_vus non transactionnel, double comptage | BROKEN | **RÉFUTÉ** | `sqlite3.connect` défaut = transaction implicite ; INSERT scores_vus + UPDATE modeles partagent la même transaction, `c.commit()` unique (l.460). Crash avant commit ⇒ rollback des DEUX. « Sauté si table modeles absente » = comportement voulu (agrégation optionnelle), pas une rupture d'idempotence. Nightly mono-instance ; SQLite sérialise les écrivains. |
| B1 serveur trouvé sain non re-vérifié en sortie | BROKEN (HIGH) | **PARTIEL retenu (LOW) — corrigé** | La lettre du claim tient (« ne sera PAS arrêté » : le script n'y touche pas ; le distilleur ne fait que du HTTP). Vrai manque : une mort de cause externe pendant la passe sortait en exit 0 muet. Correctif : re-mesure `/health` en sortie + journal (« toujours sain » / « ATTENTION … ne répond plus »), sans arrêt ni relance. |
| B2 timeout ⇒ kill d'un processus tiers sur :8004 | PARTIAL (MEDIUM) | **RÉFUTÉ** | Le RT n'a pas ouvert `stop_llama_port.ps1` : port-scoped **et name-checked** — n'arrête que `ProcessName -ieq "llama-server"`, REFUS exit 1 sinon. Un tiers non-llama qui prend :8004 pendant l'attente n'est pas tué. (Un llama-server tiers muet au /health pendant la fenêtre de 240 s reste un résidu ultra-étroit, accepté.) |
| B3 arrêt VÉRIFIÉ port en main, exit 4 | HOLDS | **CONFIRMÉ** | Get-NetTCPConnection + exit 4 (l.108-111). |
| B4 issues non journalisées avant le 1er Ecrire | PARTIAL | **RÉFUTÉ** | `Ecrire "=== passe ==="` (l.49) écrit TOUJOURS avant tout poll. Les catch{} du poll sont l'attente normale (serveur pas encore levé) ; chaque issue (SAUTE/ECHEC/pret) a son Ecrire. |
| B5 ExitCode après HasExited | HOLDS | **CONFIRMÉ** | Accès sûr en .NET tant que l'objet Process est référencé. |
| C1 exit-0 silencieux contredit sa propre doc | BROKEN (MEDIUM) | **RÉFUTÉ** | Le silence est DOCUMENTÉ : en-tête l.11 (« sortie 0 silencieuse ») et commentaire en ligne l.23 (« rien à journaliser »). Le claim C1 annonçait exactement cela. |
| D1 déclencheurs décalés UTC/DST | PARTIAL (HIGH) | **RÉFUTÉ** | `New-ScheduledTaskTrigger -At 00:50` produit un StartBoundary SANS fuseau ⇒ heure LOCALE pour le Task Scheduler (doc Microsoft) ; aucun décalage UTC/DST. Fait mesuré au triage : les 2 tâches ne sont de toute façon **pas encore installées** (Get-ScheduledTask : introuvables, 25/08) — l'installeur attend son exécution manuelle. |
| E1 clé lue env-d'abord, jamais affichée | HOLDS | **CONFIRMÉ** | Longueur seule, aucun écho de valeur. |
| F1 contextWindow ox-alpha = sommet catalogue | BROKEN (HIGH) | **CONFIRMÉ (MEDIUM) — corrigé** | Contradiction interne réelle : doctrine « PLANCHER prudent » (providers.yaml l.177-181, qui nomme 1048576 comme annonce catalogue) vs `contextWindow: 1048576` sur `stealth/ox-alpha` et `x-preview-f-free`. Ramenés au plancher 131072 avec commentaire. MEDIUM et non HIGH : la route est morte ce jour (mesuré), le risque (400/troncature amont) ne mord qu'à sa reprise. |
| F2 auto:smartest non documenté interdit de mesure | BROKEN (MEDIUM) | **RÉFUTÉ** (politesse ajoutée) | Le commentaire de bloc (l.183-184 : « Modèle VIRTUEL … INTERDIT pour une mesure », puis « `auto:<profil>` choisit la STRATÉGIE… ») couvre auto:smartest. Le RT n'a lu que les champs `name:`. Par symétrie, le `name` d'auto:smartest porte désormais aussi « (bascule, ne pas mesurer avec) ». |

**Bilan : 2 retenus (F1 corrigé, B1 partiel corrigé), 4 claims tenus confirmés,
8 réfutés.** Découverte du triage lui-même : l'en-tête de `stop_llama_port.ps1`
(« we NEVER touch :8004 (production) ») datait du monde banc-:8005 et
contredisait l'appel du nightly sur :8004 — commentaire corrigé (le garde-fou
réel est le name-check, pas le numéro de port).

## Porte README (HIGH fixés ou acceptés)

HIGHs annoncés par le RT : A3 (mal étiqueté — son propre verdict est HOLDS),
B1, D1, F1. Après triage : **F1 corrigé, B1 corrigé, D1 réfuté** — aucun HIGH
ouvert. Résidus acceptés (LOW, documentés ci-dessus) : A2 (JSON avant un
`</think>` littéral, jamais observé) ; B2 (llama-server tiers muet pendant la
fenêtre de 240 s).

## Qualité du red team (pour le PIRT et la méthode)

- **Littéral mutilé :** le rapport A1 a réécrit `</think>` en « response »
  partout, y compris dans ses « citations » de code — vraisemblablement son
  filtre de sortie a mangé la balise. Deux findings (A1, A2) reposaient
  entièrement sur ce texte fantôme.
- **Numéros de ligne fabriqués :** « line 86 » cité 5 fois pour des extraits
  différents de distiller_nightly.ps1 ; « line 38 » pour un fichier de 34
  lignes ; « lines 263-270 » pour un bloc réellement en 183-201.
- **Fichiers non ouverts :** B2 accuse `stop_llama_port.ps1` sans l'avoir lu
  (le name-check y réfute le scénario).
- Leçon reconduite : un finding de red team est une PISTE, jamais une mesure ;
  le triage contre le code réel est la partie qui coûte — et elle a inversé
  8 verdicts sur 12.

## Preuves

- `redteam/preuves-5-harnais/CLAIMS.md` — les 13 claims soumis.
- `redteam/preuves-5-harnais/reponse_or_a{1,2,3}*.md` — les 3 rapports bruts.
- Les charges rt_*.json (rôle + claims + fichiers) ne sont pas archivées :
  reconstructibles depuis CLAIMS.md + les fichiers du dépôt aux commits cités.
- Brief agent-mode non utilisé (bascule mono-appel) :
  `scripts/bench_julia_effort/briefs/rt1_redteam_harnais_ox_alpha.txt`.
