# Phase 4 — deux semaines stables (et d'abord : la campagne de rodage)

2026-08-24. Une pierre deux coups (demande utilisateur du 24/08) : chaque tâche réelle
passée dans dsh **valide le harnais** ET **améliore le framework** (`agentic-flow`,
sous-arbre `plasma-digital-twin`). Un échec de tâche n'est donc jamais seulement un
échec : il est trié, et sa cause nourrit l'un des deux côtés.

## Campagne de rodage (avant l'horloge stable)

Constat du jour 1 : les premiers runs révèlent des défauts de harnais (mur de tests,
timeout) qui n'ont rien à voir avec le modèle. Compter ces jours dans les « 2 semaines
stables » fausserait la mesure. Donc :

- **Rodage** : les tâches réelles s'enchaînent **dès que le triage le permet** (2–3/jour
  possibles), au lieu d'une par jour.
- **Triage de chaque run** : défaut *harnais* → correctif immédiat + contrôle mesuré +
  retry ; défaut *modèle* → distillation (leçon) + un retry avec leçon fraîche ; VERT →
  livrable promu (voir Promotion).
- **Sortie du rodage** : **2 runs consécutifs sans défaut harnais**. Critère mesurable,
  pas un sentiment.

**Décision 2026-08-24 (utilisateur) : campagne enchaînée, pas d'horloge calendaire.**
Le 1 tâche/jour × 2 semaines mesurait la dérive temporelle de la route ; ce signal sera
échantillonné plus tard par un smoke nightly maigre **activé côté projet (agentic-flow),
pas par dsh2.0**. À la sortie du rodage, les tâches du backlog s'enchaînent au rythme du
triage (2–4/jour selon la revue), chacune avec triage + red team (mutation pour les
tests, citations croisées pour les notes) + promotion si VERT. Biais assumé et noté :
le cache chaud (68 % vs 29 % à froid) flatte coûts et latences — les chiffres du premier
run de chaque session sont marqués à part. Backlog initial, mesuré dans le dépôt le
24/08 : `anchors` 1 source/0 test ; `gpu3d_integration` 28 sources/6 tests ; `liquid`
43/20 ; triages PIRT V44 (14/25), V49 (2/6), V51, V72 ; et la propre liste du dépôt
`test/GAP_ANALYSIS.md`.

## Politique de timeout : mesurée, pas devinée

- Rodage : `--delai 1800` (l'essai 1 à 900 s a été tué en plein travail du coder).
- Après ≥ 5 runs achevés (VERT ou échec propre, hors timeout) : `delai =
  max(1800, 1.5 × p95 des durées observées)`, recalculé depuis les `duree=` des logs
  de run archivés dans `reports/phase4_*/`.

## Registre des défauts harnais (rodage)

| # | Défaut | Vu le | État |
|---|--------|-------|------|
| D1 | test-wall refuse la tâche « écrire des tests » (REFUS write + str_replace_editor) | 24/08 essai 1 | **Corrigé** : `DSH_TEST_WALL_ALLOW` (fichiers exacts, posés par le script de run, hors de portée du coder) ; contrôle 41/41 ; commit 9acab0e |
| D2 | délai 900 s trop court (tué pendant le coder ; ~400 s perdues en amont) | 24/08 essai 1 | **Corrigé** : 1800 s + politique p95 ci-dessus |
| D3 | 3 appels qwen quasi vides (in=20281 identiques, out 36-135, 120–140 s chacun) entre planner et coder | 24/08 essai 1 | **Diagnostiqué + corrigé** (preuve wire au prochain run). Journal de session (`session-9e7bf9ad`) : `llm/retry` 1..3, « Upstream idle timeout exceeded », sur l'étape « recopie le plan verbatim dans l'appel coder » (~6 k tokens d'arguments) ; 522 s + ~60 k tokens d'entrée re-facturés, réussite à la 4e tentative. Correctif : greffon `dsh-plan-spool` — le plan passe par référence (écrit dans PLAN.md par le greffon, accusé court au parent, le coder lit le fichier) ; contrôle `plan_spool_unit.mjs` 17/17 ; déclaré dans agents.patch.yml, jonction headless posée. Le retry dsh (politique 5×, backoff) reste le filet. **2e mesure (essai 2, sans le greffon — booté avant le correctif)** : même étape, forme pire. Le parent a passé **1046 s à régénérer le plan (23 740 tokens de sortie)**, a écrit lui-même un `.plan_tmp.txt` (11 209 car.)… puis a recopié le plan verbatim dans l'appel coder (11 254 car.) quand même. Son contexte, gonflé par sa propre sortie, a déclenché 2 compactions en plein run (voir D4) ; tué à 1801 s à ~2 commandes de DONE.md. Preuves : `reports/phase4_jour1/session_2c2285c6_digest.txt`, `plan_tmp_essai2.txt`. **Preuve fil livrée (essai 3, spool armé)** : `plan-spool: planner -> PLAN.md (13214 car.), accuse court rendu au parent` ; l'étape est passée de **1046 s / 23 740 tokens à 160 s / 7 522 tokens** (−85 % / −68 %), run VERT en 614 s. **Clos.** |
| D4 | Compaction en plein run qui échoue : « summarization truncated at the token cap (incomplete checkpoint) », 248 s perdues, une 2e compaction démarrait au kill | 24/08 essai 2 | **Observé, pas traité directement** : le déclencheur (contexte parent gonflé par les 23 k tokens de D3) disparaît avec le greffon plan-spool. À réévaluer seulement si une compaction en plein run réapparaît sur un run où `plan-spool: arme` figure au log. **Contre-preuve essai 3** : spool armé, zéro événement compaction dans le journal parent (`session-e338d7c8`, 1584 événements). |

## Red team des livrables : la porte prouve « vert », la mutation prouve « ça mord »

Constat (question utilisateur du 24/08) : jusqu'à J1, aucun red team des avancées — la
porte VERT prouve que la suite *tourne au vert*, pas qu'elle *détecte* quoi que ce soit ;
des tests cérémoniels passent aussi. Règle désormais : **un livrable test n'est promu
qu'après (a) porte VERT et (b) au moins une mutation attrapée** — casser une constante du
module dans le worktree (jamais dans le workspace d'un run en cours), porte attendue
ROUGE, restauration `git checkout` + md5, porte de nouveau VERT. Trois verdicts, tous
archivés. Première application (J1, post-promotion — la règle arrive après le commit
`54196582`, validé rétroactivement) : mutation `_SYM_GROWTH_RATE_G_L_DAY 0.8→0.9` →
**ROUGE, 4 assertions tombent** (922 ok, 4 faux) ; restauré, VERT. Les corrections
harnais gardent leur red team unitaire (cas adversariaux dans `test_wall_unit.mjs`,
`plan_spool_unit.mjs`) ; les briefs `*_rt.txt` restent disponibles pour une passe
red-team LLM quand un livrable n'est pas mutable mécaniquement (ex. note de triage J2 :
vérification humaine ou croisée des citations).

Asymétrie mesurée le 24/08 (J4) : sur un changement **doc-only**, la porte répond
« aucun fichier .jl modifié : rien à rejouer (verdict ORANGE, pas vert) » — **par
construction**, VERT est inatteignable sans `.jl` rejoué (le VERT de J2 venait de
suites `.jl` en attente dans l'état de la porte à ce moment-là, pas de la note).
Acceptation d'un livrable doc-only, donc : (a) ORANGE structurel avec **0 échec**,
verdict de la porte cité verbatim ; (b) rejeu direct vert de la dernière suite `.jl`
touchée ; (c) red team citations ligne à ligne. Les briefs doc-only ne promettent
plus « VERT is the only green » (le brief J5 applique la leçon).

## Règle des briefs (leçon J2 essai 1, 24/08)

Un brief qui dit « lire au minimum … » sur un dossier non borné est un défaut de **brief**
(ni harnais, ni modèle) : à ~25 s le tour LLM cloud, 55 lectures consciencieuses = budget
mort sans une ligne écrite (J2e1 : 1801 s tués, 0,8451 USD, 2,96 M tokens d'entrée, le
coder lisait encore au kill — et il contre-vérifiait même les chiffres au grep, comportement
exemplaire). Règles : (1) **nommer les fichiers exacts** dans le brief, vérifiés existants
au moment de l'écrire — J2e1 exigeait des `VERDICT_V09_*`/`PREREG_V09_*` qui n'existent pas
sous ces noms dans la copie (résidu de résumé post-compaction, non mesuré) ; (2) borner :
« ces N fichiers, une lecture chacun, rien d'autre » ; (3) dimensionner : lignes totales à
lire × ~2-3 s/25 lignes + rédaction ≤ 60 % du délai.

## Promotion des livrables VERT

Worktree dédié `C:\Users\test\Documents\agentic-flow-phase4` (branche `phase4-tests`,
créée le 24/08 depuis 002737c0). Un jour VERT = un commit sur cette branche (fichiers du
jour uniquement, message pointant les preuves `reports/phase4_*` de dsh2.0). Push
uniquement sur « pousse » explicite. L'arbre de travail `agentic-flow-fresh` n'est
jamais touché.

## Journal

- **J5 (24/08) — triage V49** : run propre **n° 5 consécutif**. rc=0 en **667 s**,
  0,2235 USD, cache 43 % ; spool actif (9071 car., DONE.md concorde) ; porte
  préchauffée essai 2. Note `TRIAGE_V49_2026-08-24.md` (219 lignes, 5 sections +
  Boundaries) : les DEUX scores rapportés en parallèle — 2/6 (PIRT l.301, non daté)
  vs 3/6 scellé `18302730` (11/08) puis 3/7 scellé `4096f485` (12/08) — discordance
  **NON RÉSOLUE signalée** (comme demandé par le brief), autorité hors-borne nommée
  mais pas citée. Dernier mot : γ*=23,47 = verdict sur `n_e = 1.0e16*P` (6 nombres
  typés non ancrés), **BLOQUE #101** (circularité même-phrase Niemczyk 90 s/270 s),
  3 routes ; sonde = ancrer n_e indépendamment (Ar atm. ~10 kHz, 0,53–1,60 W/cm²)
  sous PREREG neuf ; pièges repris verbatim (« refused in advance »). **Porte :
  ORANGE structurel doc-only** ; l'état « 2 non rejouées » élucidé :
  `literature_constants.jl` (bonding_debonding) porté modifié antérieurement à la
  campagne, suite ciblée 31 s > budget 30 s ⇒ rejeu direct
  `test/bonding_debonding/runtests.jl` : **9225/9225 en 3 min 58** (GPU libre
  vérifié avant : 0 processus). **Red team citations PASSÉ** : ~45 citations
  ligne à ligne sur les 5 fichiers, 6+ verbatim exacts, zéro falsification ;
  3 mineurs (2 fenêtres décalées ; self-check `git status` du coder remonté au
  dépôt parent — le WS n'est pas un dépôt git, ride harnais à surveiller).
  **Promu** : `bcfb69ff` sur `phase4-tests` (5e livrable). Preuves
  `reports/phase4_jour5/` (scan secrets 0).

- **J4 (24/08) — triage V44** : run propre **n° 4 consécutif**. rc=0 en **539 s**,
  0,2217 USD, cache 37 % ; spool actif (7251 car., DONE.md concorde — la ride J3 ne
  s'est pas reproduite) ; porte préchauffée essai 1. Note `TRIAGE_V44_2026-08-24.md`
  (157 lignes, 5 sections) : sceau du 09/08 FERMÉ (citation du mécanisme VIDE —
  Fridman §7.4 = halides ; Zhao 2007 contredit la voie vibrationnelle ; barres C3 mal
  attribuées) ; sonde la moins chère EXTERNE (lire la vraie Table 7.4, deux branches
  pré-déclarées, sous PREREG neuf) ; piège KI-23 (η_vib_diss→0.10 = double fake-green,
  fausse ligne « stable » à `run_validation.jl:593` armée) explicitement interdit ;
  le FAIL reste FAIL. **Porte : ORANGE structurel** (doc-only, « rien à rejouer, pas
  vert » par construction — voir Red team des livrables) ; 0 échec ; rejeu direct
  `test/anchors` 15/15 en 3,0 s. **Red team citations PASSÉ** : ~50 citations
  vérifiées ligne à ligne sur S/RS/VS/RT/PIRT l.60 ; copie sous scellé
  `VALIDATION_SUMMARY_at_seal.md` vérifiée **byte-identique** (cmp) ; 6 citations
  verbatim exactes ; zéro falsification. **Déviation justifiée** : le coder a lu et
  cité cette 6e copie hors des 5 fichiers du brief — byte-identique ⇒ aucune preuve
  nouvelle. Deux mineurs : fenêtre VSA « 59–109 » vs VS « 59–101 » pour un contenu
  identique ; composition du jeu de preuve vs brief. Coder honnête sur l'ORANGE
  (n'a pas cherché un faux vert). **Promu** : `ce781e4c` sur `phase4-tests`
  (4e livrable). Preuves `reports/phase4_jour4/` (scan secrets 0).

- **J2 (24/08) — triage V09** : essai 1 **ÉCHEC — défaut de brief** (1801 s tués,
  0,8451 USD, cache 54 %). Harnais irréprochable : plan-spool actif (8674 car. → PLAN.md),
  murs armés, zéro REFUS. Le coder : todo « lire les 16 fichiers du plan », ~55 lectures
  méthodiques, contre-vérification des chiffres au grep — tué en pleine lecture, rien
  écrit. Cause : brief non borné + noms de fichiers non vérifiés (voir Règle des briefs).
  Trouvaille au passage : la ligne PIRT dit V09 **4/7** FAIL, le summary du STOPPED dit
  **5/7** — divergence à signaler dans la note. Essai 2 lancé : brief v2 borné à 6
  fichiers nommés et vérifiés (742 lignes au total). Compteur de sortie du rodage :
  reste **1/2** (seuls les runs achevés proprement comptent). Preuves
  `reports/phase4_jour2/`.
  Essai 2 **VERT** : rc=0 en **794 s**, 0,2373 USD, cache 47 % ; spool actif (7808 car.),
  porte ORANGE→VERT, DONE.md conforme. Le brief borné a fait tomber le coût de 0,845 →
  0,237 USD. **Red team citations TENU** : ~40 citations vérifiées ligne à ligne contre
  les 5 fichiers cités — zéro falsification, zéro chiffre déformé ; la note rapporte la
  divergence 4/7 (PIRT) vs 5/7 (STOPPED 16/08) sans la résoudre, donne le dernier mot au
  FINDING du 19/08 (levier source PRICÉ → direction : puits d'O₃), exige un préreg avant
  toute sonde. **Promu** : commit `dec9af2e` sur `phase4-tests`. **RODAGE CLOS : 2/2**
  (J1e3 + J2e2, deux runs consécutifs sans défaut harnais). La campagne enchaînée
  démarre (J3 : tests `anchors`).
- **J3 (24/08) — tests `src/anchors/` (registre anti-fabrication)** : **VERT** en 655 s,
  0,1978 USD, cache 56 % ; spool actif (7907 car.), porte ROUGE→VERT ; 15 assertions,
  4 fonctions exportées couvertes, 2 fichiers exactement, module intact. **Déviation
  justifiée** : le brief exigeait `>= 40` ancres (comptage de répertoires, faux), le
  coder a mesuré et asserté `>= 9` — réalité : 10 `anchor.yaml` en récursif sur 41
  répertoires. Leçon briefs (bis) : compter la chose elle-même, pas son contenant.
  **Red team mutation PASSÉ** : référence 15/15 (2,9 s) ; mutation `anchor_value`
  split "." → ":" : 3 passés / 1 erreur, suite en échec ; restauration : 15/15.
  Ride comptable : DONE.md dit `planner: 7965 chars`, le spool 7907 (58 car. d'écart,
  sans impact). Porte worktree ORANGE (suites lourdes en attente hors budget) → red
  team fait par exécution directe de la suite. **Promu** : `a4d7bf32` sur
  `phase4-tests`. Preuves `reports/phase4_jour3/`. Run propre n° 3 consécutif.

- **J1 (24/08) — tests `biorefinery_symbiosis.jl`** : essai 1 **ÉCHEC** (timeout 900 s,
  D1+D2 ; 0,1252 USD, 17 appels, cache 29 % ; preuves `reports/phase4_jour1/`).
  Essai 2 **ÉCHEC protocolaire** (0,3052 USD, cache 41 %) : le livrable a bien été produit —
  48 assertions `@test`, les 2 fonctions couvertes, include ajouté (1 seule ligne de diff),
  module sous test identique octet pour octet, porte **VERT** sur le fil (`julia-gate:
  appel 2 -> VERT en 5.3s`), coder : 168 s seulement — mais DONE.md absent : le parent a
  brûlé 1046 s sur D3 puis 2 compactions (D4) et a été tué à 1801 s. D1 corrigé prouvé sur
  le fil (« 2 fichier(s) permis par le harnais », zéro REFUS). Workspace remis à l'état de
  départ (test supprimé, runtests.jl restauré depuis la base 002737c0) ; essai 3 lancé avec
  `dsh-plan-spool` armé — contrôle avant/après sur la même tâche.
  Essai 3 **VERT** : rc=0 en **614 s**, 0,1430 USD, cache 68 % ; porte VERT du premier coup
  (5,3 s) ; 15 assertions `@test` (contrat ≥ 12), `symbiosis_economics` ×7,
  `estimate_biorefinery_capex` ×3, 1 ligne de diff dans runtests.jl, module intact (md5).
  D3 : preuve fil livrée (étape 1046 s → 160 s) ; D4 : zéro compaction. **Promu** :
  commit `54196582` sur `phase4-tests` (2 fichiers, 60 insertions, garde md5 passée, pas
  de push). Préchauffage porte : 5 essais nécessaires (vs 2 à l'essai 2) — à surveiller,
  hors budget du run. **Run sans défaut harnais n° 1** (critère de sortie du rodage : 2
  consécutifs).
