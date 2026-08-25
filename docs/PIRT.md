# Registre PIRT — proposition de chantier (25/08, « go PIRT »)

**But.** Étendre la boucle nocturne : aujourd'hui la distillation réduit la
dette technique du harnais (leçons de processus + notes par modèle). Ce
chantier lui fait produire, EN PLUS, une table PIRT vivante — *Phenomena
Identification and Ranking Table* — qui classe les phénomènes physiques du
framework par (importance × couverture-test × confiance V&V) et propose chaque
nuit « le prochain phénomène à verrouiller ». La campagne du 25/08 a prouvé que
la matière première existe déjà : l'audit-mutation est une mesure directe du
« niveau de connaissance verrouillé » par phénomène.

## Principes non négociables

1. **L'importance : proposeur + red team ; l'humain n'arbitre que les
   désaccords.** (Règle générale, ordre utilisateur du 25/08 — remplace la
   version initiale « la colonne n'est écrite que par l'humain ».) Fable 5
   propose chaque valeur avec justification ancrée dans les sources ; un red
   team indépendant (deepseek-v4-pro, route payante — données PRIVATE) audite ;
   convergence après triage ⇒ valeur retenue sans intervention humaine ;
   désaccord proposeur/red-team ⇒ tranché par l'humain, seul cas où il
   intervient (précédent : pic_core, 2 vs 1, arbitré 2 le 25/08). Toute valeur
   reste révocable par l'humain à tout moment ; la machine ne décide jamais
   SEULE (deux avis indépendants exigés). Échelle inchangée (1=support,
   2=significatif, 3=critique pour les grandeurs d'intérêt).
2. **Cloisonnement des niveaux.** Les DONNÉES du registre (noms de phénomènes,
   fichiers du framework, valeurs d'ancres) sont PRIVATE : la base et les
   événements vivent dans le dépôt framework (`plasma-digital-twin/pirt/`).
   L'OUTILLAGE (schéma, script de repli, requêtes) est OPEN et vit ici.
   Le balayage tourne sur Qwen local ou sans LLM — jamais sur une route OPEN.
3. **Rien de coché sans mesure.** Une ligne de registre ne change d'état que
   sur un événement daté et sourcé (rapport de campagne, commit, note V&V).
   « Aucun changement » est un résultat valide de la boucle nocturne.

## Schéma (mêmes conventions que distiller.py : SQLite, noms français, idempotent)

```sql
CREATE TABLE IF NOT EXISTS phenomenes (
  id TEXT PRIMARY KEY,            -- ex. 'ozone.branche_n2a'
  module TEXT, fichier_source TEXT,
  description TEXT,
  importance INTEGER,             -- 1..3, HUMAIN uniquement, NULL = pas classé
  cree_le TEXT);
CREATE TABLE IF NOT EXISTS pirt_evenements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phenomene_id TEXT, date TEXT,
  type TEXT,                      -- 'audit_mutation'|'suite_promue'|'ancre'|'note_vv'
  donnees TEXT,                   -- JSON : {bite, echecs, total, constante, commit, ...}
  source TEXT);                   -- chemin rapport / hash commit
CREATE TABLE IF NOT EXISTS pirt_etat (
  phenomene_id TEXT PRIMARY KEY,
  couverture REAL,                -- 0..1 : mutations attrapées / tentées (cumul)
  nb_tests INTEGER, dernier_bite TEXT,
  confiance_vv TEXT,              -- 'aucune'|'triage'|'validee' (source : notes V&V)
  maj_le TEXT);
-- Priorité (lecture seule) : importance DESC, couverture ASC, confiance_vv ASC.
```

## Sources des lignes (tous des artefacts qui existent déjà)

| Flux | Producteur | Quand | Exemple réel (25/08) |
|---|---|---|---|
| `audit_mutation` | le triage de campagne append 1 ligne JSONL (`pirt/evenements.jsonl`) | à chaque red team mutation | `{"phenomene":"ozone.branche_n2a","bite":false,"echecs":0,"total":76}` puis après J13 `{"bite":true,"echecs":9,"total":99}` |
| `suite_promue` | idem, au commit de promotion | à chaque livrable | J11 : 70 tests, mutation 65/5 |
| `ancre` | la sonde d'ancres (déjà obligatoire avant brief) | à chaque sonde | `k_cluster_eff=1.49611232e8` |
| `note_vv` | l'humain, dans les notes V&V du framework | au fil du V&V | note de triage V72 |

Discipline « une pierre deux coups » : le triage écrit l'événement au moment où
il mesure — aucun travail rétroactif, aucun parsing de prose.

## Boucle nocturne (s'ajoute à distiller_nightly.ps1, CPU seul par défaut)

1. Replier `pirt/evenements.jsonl` → `pirt_evenements` + recalcul `pirt_etat`
   (pur SQL/python, 0 LLM, 0 USD).
2. Régénérer le bloc généré de `pirt/PIRT.md` (table triée par priorité) —
   même convention que le bloc généré de CLAUDE.md : seul le bloc généré fait
   foi pour les comptes.
3. Émettre dans le journal nocturne les **3 phénomènes en tête** (importance
   haute × couverture basse) comme cibles proposées. L'humain choisit ; la
   campagne suivante les traite exactement comme C4→C5 du 25/08
   (no-bite → run de renforcement → contre-mutation → bite prouvé).
4. Option ultérieure (pas dans ce chantier) : Qwen local propose le découpage
   source → phénomènes pour les modules pas encore inventoriés ; l'humain
   valide chaque ligne avant insertion.

## Amorçage — lignes réelles, toutes mesurées le 25/08

| phenomene_id | couverture mesurée | preuve |
|---|---|---|
| ozone.branche_n2a | no-bite (0/76) → **bite 9/99** après J13 | jour13, commit 5780f658 |
| amr.seuil_chimie_jet | no-bite (0 échec muté) — renforcement R4 en cours | audit C4 |
| pic_core.taux_penning_o2 | bite littéral seul (1/110) — propagation nulle | audit C4 |
| coupling.masse_electron | bite littéral seul (1/92) | audit C4 |
| ions_ar.alpha_dr + k_cluster | bite 5/70, ancres visées | jour11, 847ed501 |
| jet_ar.excimere_vuv | bite 4/66, ancres visées | jour12, e5e94dae |

(`importance` : à remplir par l'humain — la machine ne la devine pas.)

## Critères Done du chantier

- D1 : schéma + repli JSONL→SQLite + bloc généré, testés sur les 6 lignes
  d'amorçage ci-dessus (comptes exacts reproduits depuis les rapports).
- D2 : le triage de campagne append l'événement en une ligne (gabarit fourni),
  prouvé sur une campagne réelle.
- D3 : une nuit complète : repli + PIRT.md régénéré + top-3 dans le journal,
  0 USD, monde laissé comme trouvé.
- D4 : red team du chantier (modèle différent) sur les done-claims D1-D3.

## Coûts et risques

- Coût de croisière : 0 USD (repli sans LLM) ; l'inventaire assisté (option 4)
  coûte du Qwen local uniquement.
- Risque principal : la tentation de laisser la machine remplir `importance` —
  interdit par principe 1 ; le second : des événements écrits en prose libre —
  paré par le gabarit JSONL obligatoire au triage.

## Implémentation (25/08, « pirt add on ») — écarts assumés vs la proposition

Outillage : `harness/pirt.py` (OPEN). Données : `plasma-digital-twin/pirt/`
(PRIVATE) — `phenomenes.yaml` (humain, porte `importance`),
`evenements.jsonl` (source de vérité, append-only), `PIRT.md` (bloc généré),
`pirt.sqlite` (cache dérivé, gitignoré, reconstruit à chaque repli).

Trois raffinements mesurés sur l'amorçage, documentés ici parce qu'ils
précisent le schéma proposé :

1. **`couverture` = dernier événement par (phénomène, constante)**, pas le
   cumul brut : un no-bite fermé par un renforcement prouvé (ozone C4→J13)
   compte 1.0, pas 0.5 — c'est l'état du verrou qui classe, pas l'historique.
2. **Colonne `portee` ajoutée** (`ancres` > `litteral` > `aucune`) : l'audit
   C4 a montré deux « bites » qui ne mordent que sur l'assertion du littéral
   (pic_core 1/110, coupling 1/92) — sans cette colonne ils seraient
   indistinguables d'un verrou réel, et le tri les fait remonter en tête.
3. **La base SQLite est un dérivé, jamais la source** : reconstruite de zéro
   à chaque repli depuis le JSONL (idempotence par construction, md5 du
   PIRT.md identique sur double run) ; fail-closed : une ligne invalide ⇒
   exit 2 et RIEN n'est écrit.

Câblage : étape 0.5 de `scripts/ops/distiller_nightly.ps1`, AVANT l'étape
serveur — le repli tourne même les nuits où le GPU refuse (0 LLM, 0 USD) ;
un échec du repli est journalisé mais ne bloque pas la distillation.

État des Done : **D1 fait** (comptes des 6 lignes d'amorçage reproduits :
9/99, 1/19, 1/110, 1/92, 5/70, 4/66 ; idempotence et fail-closed testés) ;
**D2 gabarit prouvé** sur les événements réels de la campagne du 25/08
(l'append au fil du triage se prouve à la prochaine campagne) ; **D3 câblé**
(la preuve « une nuit complète » se lit dans le journal nocturne après
l'installation des tâches — toujours en attente d'exécution manuelle de
`installer_taches_nocturnes.ps1`) ; **D4 fait** : red team par
`deepseek/deepseek-v4-pro` (charge vérifiée OPEN-pure), triage
`redteam/6-pirt-25-08.md` — 1 correctif retenu (P2 : champs vides rejetés),
1 résidu accepté documenté (P7), aucun HIGH ouvert. **Chantier clos.**

## Automatisation progressive (décidée 25/08, cran 1 non lancé)

Décision utilisateur : la boucle nocturne peut traiter *petit à petit* la
file de travail déjà validée du registre, si rien de plus urgent. Le mot
« traiter » s'arrête AVANT le merge — l'automatisation va jusqu'à la
proposition, jamais au-delà (cohérent avec le principe 1 amendé : l'humain
n'arbitre que les désaccords, et ici il valide chaque merge).

Rôles (fixés par ordre utilisateur du 25/08) :
- **Ouvrier** : modèle local (les données du registre sont PRIVATE — elles
  ne sortent jamais vers une route OPEN, principe 2 inchangé).
- **Red team** : z.ai GLM-5.3 en premier, repli OpenRouter si saturé.
  Fail-closed : les deux routes mortes ⇒ le chantier de la nuit s'arrête,
  il ne « fait sans » jamais. *(dégât évité : un correctif plausible-mais-
  faux validé par personne.)*

Trois conditions non négociables :
1. **Une nuit = une branche + un rapport, jamais un merge.** Le traitement
   nocturne atterrit sur une branche dédiée ; l'humain merge au matin.
   *(dégât évité : de la physique non relue sur main avec l'élan de la nuit.)*
2. **Le log de nuit est généré, pas rédigé** : gabarit fixe
   Quoi / Pourquoi / Preuve / Reste, sans jargon, dérivé des artefacts de
   la nuit — c'est la pièce qui rend la validation de merge humaine
   réellement exerçable. *(leçon existante : « derived at generation time,
   not typed ».)*
3. **1 sujet par nuit, budget plafonné** — le « petit à petit » est
   mécanique, pas une intention.

Déploiement en trois crans mesurables :
- **Cran 1 (à blanc)** : une nuit produit proposition + red team + log,
  ZÉRO changement de code ; on mesure coût et durée.
- **Cran 2** : ajoute le brouillon de traitement, toujours branche seule.
- **Cran 3** : régime de croisière (1 sujet/nuit, merge humain au matin).

Frontière des dépôts, rappelée parce qu'elle porte tout : CE dépôt
(dsh2.0) est OPEN — il porte l'outillage, ce document, et AUCUN nom de
phénomène ni identifiant de claim ; le registre, ses données et le poster
qui les affiche vivent dans le dépôt framework PRIVATE. Le texte PIRT du
poster reflète la même posture (automatique jusqu'à la proposition, merge
humain, outillage open / données privées) depuis le 25/08.
