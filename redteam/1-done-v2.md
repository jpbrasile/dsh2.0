# Red team -- 1-done-v2

| | |
|---|---|
| date | 2026-08-23 17:53 |
| modele red team | `deepseek/deepseek-v4-pro` via `openrouter-banc` (servi : `deepseek/deepseek-v4-pro`) |
| prompt | `harness/redteam/1-done-v2.md` |
| cwd | `C:\Users\test\Documents\dsh2.0` |
| appels / tokens | 13 appels, 450239 entree, 22194 sortie, 696 s |
| dsh | rc de fumee_route = 0 ; VERDICT : OK -- chaque appel servi par deepseek/deepseek-v4-pro |
| fichiers suivis modifies par le red team | **ECHEC DU RUN** : `?? harness/agents.patch.yml`, `?? harness/context7_sonde.py`, `?? harness/query_unit.mjs`, `?? scripts/dsh-plugins/dsh-query-wall/` |

## Rapport brut du red team (non edite)

Here is my complete report as the second red team:

---

# Red Team Phase 1 — Second Pass — Rapport

## Findings

### LOW: Verdicts pré-enregistrables pour un modèle inexistant — bypass de probation

**Claim attacked:** "new OpenRouter stealth model reaches the OPEN chain in one session start" — mécanisme de probation corrigé.

**Reproduction:**

The `--verdict` command inserts the verdict **even when the model does not exist in the database** (line 347-350). The message « sera pris au prochain rafraîchissement » is printed, but the row is already committed. `verts_minimal()` (line 146) counts ALL green `minimal` verdicts for an `id` without checking model existence. `probation_de()` (lines 149-153) also doesn't check.

```bash
python -c "
import sqlite3, sys; sys.path.insert(0, 'harness'); import modeles
c = sqlite3.connect(modeles.BASE)
# Insert 3 green verdicts for a model that doesn't exist
c.execute('INSERT INTO verdicts VALUES (?,?,?,?,?,?)', ('stealth/phantom', 'fumee:PONG', 'minimal', '2026-08-23 18:00:00', 1, 'test'))
# ... 2 more ...
c.commit()
m = {'id': 'stealth/phantom', 'free': 0, 'stealth': 1, ...}
print('probation_de:', modeles.probation_de(c, m))  # → 0 (probation levée!)
print('tier:', modeles.tier_de(m))                    # → OPEN
"
```

**Evidence:** `probation_de()` returns 0 for a model that has never been in the catalog. When the model later appears via `rafraichir()`, it would arrive directly in the `open` chain — skipping probation entirely, on its **first** `--session`.

**Why it matters:** Probation is the sole gate keeping untested stealth/free models out of the `open` chain. A verdict is meant to be the trace of a real fumée test, but nothing cryptographically binds a verdict to a fumée run. An operator (or a buggy script) can pre-record 3 green verdicts and lift probation without ever testing the model. The bypass is documented in the code — it's a design choice, not a hidden bug — but it weakens the guarantee « hors probation = testé ».

---

## What I checked and did not break

- **`open` chain populated** : `chaines.yaml` line 20 = `open: [stealth/ox-alpha]` — fixed (was `[]`).
- **3 green `minimal` verdicts** : `SELECT COUNT(*) FROM verdicts` = 3, all `stealth/ox-alpha`, `preset='minimal'`, `vert=1`.
- **`probation=0`** for `stealth/ox-alpha` in the modeles table.
- **Unit tests 43/43** : `python harness/modeles_unit.py` — all passing, including 6 new cases (NaN, Infinity, boolean, block collision, DIVERGENT cost).
- **NaN/Inf/boolean rejected** : `_prix()` uses `math.isfinite()` (line 96) and rejects `bool` (lines 90-91) — all 3 pass in unit tests.
- **Block collision `openrouter`** : `verifier_emis()` rejects any block other than `openrouter-auto`; `providers_install.py` rejects name collisions — tested, holds.
- **DIVERGENT cost dedup** : `cout.ingerer()` marks `DIVERGENT cout X != Y au livre` and `cout.py --ingerer` returns rc=1 — code correct.
- **Cache % documentation** : `docs/PHASE1.md` now says « Par appel, le cache va de 0 % ... à 97-98 % » — fixed.
- **`classer("open")`** returns `['stealth/ox-alpha']`; **`classer("probation")`** contains the 21 other OPEN models (all `probation=1`).
- **Invariant `openrouter-auto`** : all models in the emitted block are `tier='OPEN'` — holds, tested.
- **No OPEN → PRIVATE leak** : `classer("ouvrier")` filters `tier != 'OPEN'` — `stealth/ox-alpha` absent from `ouvrier`/`redteam`.
- **Preset spoofing** : `probation_de()` hardcodes `preset='minimal'`, `fumee_route.py` uses `"patch:"` prefix — no collision possible.
- **Real cost** : `cout.py --jour 2026-08-23` = 67 calls, 80.9% cache, 0.2157 USD — consistent (54 paid deepseek-v4-pro + 13 free stealth calls).
- **Tier from catalog only** : `tier_de()` reads only `free`/`stealth` fields, never a verdict — holds.
- **Fumee wire** : current `_fumee/wire.jsonl` shows 9 calls by `deepseek/deepseek-v4-pro` (last red team run); the fumée dir is overwritten each run — stealth fumée evidence lives only in verdicts (permanent).

---

## Verdict

**DONE-CLAIM HOLDS WITH LOW FINDINGS**

The worker's correction works: `stealth/ox-alpha` is in the `open` chain of `chaines.yaml`, backed by 3 green `minimal` verdicts and `probation=0`. All 5 fixes (HIGH: empty `open` chain → verdict recording in `fumee_route.py`; MEDIUM: NaN pricing → `math.isfinite()`; LOW: block collision, DIVERGENT cost, cache doc) are implemented and pass 43/43 unit tests. The sole caveat (LOW): verdicts are pre-recordable for a non-existent model, allowing probation bypass without a real fumée test — a documented design choice, but one that weakens the « hors probation = testé » guarantee.

## Reponse de l'ouvrier (2026-08-23)

Verdict accepte : HOLDS WITH LOW FINDINGS, 13 appels (discipline des 20 respectee, contre 54 au
premier passage), 696 s. Le `rc=1` du lanceur vient du controle "fichiers suivis modifies pendant
le run" : les 4 fichiers listes (agents.patch.yml, context7_sonde.py, query_unit.mjs,
dsh-query-wall/) sont ceux de la Phase 2, crees par l'ouvrier en parallele -- le red team n'a
rien modifie.

- **LOW, verdicts pre-enregistrables sur un id absent.** Corrige : `modeles.py --verdict` refuse
  (rc 2, aucune ligne) un id inconnu de la base ou disparu ; un modele qui apparait ensuite nait
  en probation. Unitaire : 3 cas de plus (`stealth/phantom`), 46/46.
- Bouche en passant par l'ouvrier, avant ce red team : un patch nomme `minimal.patch.yml`
  aurait donne le preset `minimal` a un run patche ; `fumee_route.py` nomme maintenant tout run
  patche `patch:<nom>`, `minimal` = stock seulement.

## Decision humaine

Corrige avant commit ; aucune trouvaille acceptee sans correction. Phase 1 close.

_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_
