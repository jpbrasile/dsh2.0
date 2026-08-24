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
- **Sortie du rodage** : l'horloge stable (1 tâche/jour, 2 semaines) ne démarre qu'après
  **2 runs consécutifs sans défaut harnais**. Critère mesurable, pas un sentiment.

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
| D3 | 3 appels qwen quasi vides (in=20281 identiques, out 36/41, 120–140 s chacun) entre planner et coder | 24/08 essai 1 | **Ouvert** : à trier sur le wire (marqueur de stagnation par appel dans fumee_route ?) |

## Promotion des livrables VERT

Worktree dédié `C:\Users\test\Documents\agentic-flow-phase4` (branche `phase4-tests`,
créée le 24/08 depuis 002737c0). Un jour VERT = un commit sur cette branche (fichiers du
jour uniquement, message pointant les preuves `reports/phase4_*` de dsh2.0). Push
uniquement sur « pousse » explicite. L'arbre de travail `agentic-flow-fresh` n'est
jamais touché.

## Journal

- **J1 (24/08) — tests `biorefinery_symbiosis.jl`** : essai 1 **ÉCHEC** (timeout 900 s,
  D1+D2 ; 0,1252 USD, 17 appels, cache 29 % ; preuves `reports/phase4_jour1/`).
  Essai 2 en cours (allowlist + 1800 s). Context7 : 10/10 bibliothèques acceptées.
