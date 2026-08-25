# Red team 7 — colonne `importance` du registre PIRT (25/08/2026)

- **Contexte :** l'utilisateur a amendé le principe 1 du chantier PIRT :
  « fait la remplir par fable 5 et red team par deepseek V4 pro latest ».
  Proposeur : Fable 5 (classement ancré dans les en-têtes physiques des 6
  sources, grep des constantes, et les mesures de campagne J11-J14/C4).
  Auditeur : `deepseek/deepseek-v4-pro` via OpenRouter (repli deepseek.ai
  autorisé, non nécessaire). Données PRIVATE → route payante (tier établi).
- **Saga du tir (5 tirs, leçon reconduite) :** v4-pro sur cette charge brûle
  tout le plafond en RAISONNEMENT et ne rend rien (finish=length ×3, dont
  une borne `effort: low` ignorée par l'amont et un plafond 12000 replafonné
  à 6000 par l'amont). Le remède était DÉJÀ dans le repo :
  `"reasoning": {"enabled": false}` (distiller.py:314, mesuré le 23/08 contre
  le même symptôme) ⇒ tir 5 : `finish=stop`, rapport complet (10 218 car.,
  in 3922 / out 2669). Bug de mon tireur v1 corrigé au passage
  (`content=None` non géré) ; un fichier réponse VIDE créé par le crash v1 a
  ensuite fait sauter un retry (« deja servi ») — purgé.
- **Incident clé (séparé du RT) :** en vérifiant la présence du credential
  DeepSeek, mon caviardage a raté et la valeur de DEEPSEEK_API_KEY a été
  affichée dans une sortie d'outil (transcript local uniquement ; rien de
  committé ni poussé). Signalé à l'utilisateur, rotation recommandée.

## Verdicts (le RT n'a vu que 30 lignes d'en-tête par fichier ; le triage
## tranche avec les mesures de campagne qu'il n'avait pas)

| phenomene | moi | RT | retenu | triage |
|---|---|---|---|---|
| ozone.branche_n2a | 3 | 1 | **2** | Le RT a démonté à raison mon « biaise la QoI 1:1 » — c'est MESURÉ faux chez nous (ancres J13 : f +8,3 % ⇒ G +0,87 %, élasticité ~0,1). Mais son 1 sur-corrige : G est la métrique de tête et f la déplace réellement (canal air/DBD). Justification réécrite avec les chiffres. |
| amr.seuil_chimie_jet | 1 | AGREE 1 | **1** | Convergence. (Le tir n°4 tronqué du MÊME modèle disait 2 « TOO LOW » — contradiction inter-tirs consignée : un verdict de RT est un tirage, pas une constante.) |
| pic_core.taux_penning_o2 | 2 | 1 | **2 (désaccord assumé)** | Son argument suppose les configs jet He hors périmètre. Le module He est réel et exercé (110 tests). 2 tant que le He est au périmètre ; **arbitrage humain invité** (ligne annotée dans le YAML). |
| coupling.masse_electron | 2 | 1 | **2 (requalifié)** | Le RT a raison sur la CATÉGORIE : une constante fondamentale n'est pas un phénomène. La ligne désigne désormais le MÉCANISME (chauffage élastique e-neutres, dominant DBD/jet froid, rétroaction T_gaz→taux trois-corps), M_ELECTRON n'étant que son verrou de code (mutation C4). |
| ions_ar.alpha_dr_kcluster | 2 | 3 | **3 (accepté)** | L'en-tête du module le dit : sans la boucle Ar⁺→Ar₂⁺→Ar*, pas de puits électronique ni de retour Ar* — en rafale 1 MHz la chaîne VUV→O₃ s'effondre. Mon « à un cran de la QoI » sous-estimait. |
| jet_ar.excimere_vuv | 3 | AGREE 3 | **3** | Convergence — le pont spatial unique cœur Ar → O₂. |

**Bilan : 2 valeurs corrigées par le RT (ozone 3→2, ions_ar 2→3), 1
requalification de catégorie (coupling), 1 désaccord assumé et documenté
(pic_core), 2 convergences.** Nouveau top-3 mesuré du registre :
`ions_ar.alpha_dr_kcluster`, `jet_ar.excimere_vuv`,
`coupling.masse_electron` (verrou littéral seul).

## Limites honnêtes

- Le RT n'a audité que 30 lignes d'en-tête par fichier (charge volontairement
  compacte) : son « f n'existe pas dans ozone_3d.jl » est un artefact de ce
  périmètre — le kwarg existe (mesuré J13), c'est le 1:1 qui était faux.
- 4 tirs sur 5 inutilisables (raisonnement) : coût publié en échecs,
  quelques centimes ; leçon opérationnelle : TOUJOURS partir de la recette
  distiller (`reasoning enabled:false`) pour un RT deepseek non-interactif.
- La colonne reste RÉVOCABLE par l'humain (principe 1 amendé, pas aboli).

## Preuves

- `redteam/preuves-7-importance/reponse_or_importance.md` — rapport complet (tir 5).
- `redteam/preuves-7-importance/reponse_or_importance_tronque3.md` — tir 4
  (contenu partiel, 3 lignes sur 6 : source de la contradiction amr).
- Pensées brutes tronquées des tirs 2-3 (23-24k car.) : non archivées,
  disponibles dans le scratchpad de session.
