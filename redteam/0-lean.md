# Red team -- 0-lean

| | |
|---|---|
| date | 2026-08-23 14:46 |
| modele red team | `deepseek/deepseek-v4-pro` via `openrouter-banc` (servi : `deepseek/deepseek-v4-pro`) |
| prompt | `harness/redteam/0-lean.md` |
| cwd | `C:\Users\test\Documents\dsh2.0` |
| appels / tokens | 31 appels, 1219656 entree, 24480 sortie, 905 s |
| dsh | rc de fumee_route = 0 ; VERDICT : OK -- chaque appel servi par deepseek/deepseek-v4-pro |
| fichiers suivis modifies par le red team | **AUCUN** |

## Rapport brut du red team (non edite)

The report is written to `_rt_scratch/rapport.md`. Here's a summary of the findings:

---

## Summary

**Verdict: FALSIFIED** — Step 2 is NOT done.

### HIGH (1 finding)
- **`lean_check.py` cannot run** — `dsh --dump-config` crashes with `EPERM` because `prepareProfile()` unconditionally calls `writeFileSync` on `~/.dsh/profiles/headless/cordis.yml`, which is outside the `workspace-write` sandbox. Since `lean_check.py` IS the control for step 2, and its measurement cannot be reproduced, the claim of "done" is unsubstantiated.

### MEDIUM (2 findings)
- **`# tools-absent:` annotation is incomplete** — `tool-web` registers TWO tools (`web_search` + `web_fetch`), but only `web_search` appears in the annotation.
- **`lean_check.py` only compares JSON-serialized configs** — behavioral drift (changed internal logic, same config) is invisible to the check. The PHASE0.md journal overstates what the tool proves.

### LOW (1 finding)
- **`command-feedback` and `command-compact` survive the "workflow extras" purge** — not declared in "kept, unchanged" and not disabled. Minimal practical impact.

### ⚑ RT 1 (second paths): **PASSES** — subagents inherit the same cordis context (same profile, same patches), MCP is stripped, no alternative routes to web/skills/workflows/vision exist.

### ⚑ RT 2 (undeclared drift): **CANNOT FULLY VERIFY** — the EPERM blocks `--dump-config`, which is the only way to prove no undeclared rows exist. The only undeclared survivors found through source analysis are the two chat commands (LOW).

## Rapport detaille du red team (`_rt_scratch/rapport.md`, non edite)

# Red Team Review — Phase 0 Step 2: Lean Preset

**Target:** `harness/lean.patch.yml` (125 lines, 17 disabled ids, 4 inserted ids)
**Control claim:** `python harness/lean_check.py` exits 0 → step is done
**Red team model:** DeepSeek v4 (different family from Qwen worker)

---

## Findings

### [HIGH] `lean_check.py` is non-reproducible — `dsh --dump-config` crashes with EPERM

**Claim attacked:** « `python harness/lean_check.py` proves two things after every dsh bump: the composed tree differs from the default tree by exactly these rows »

**Reproduction:**
```powershell
dsh --profile headless --dump-config
# Error: EPERM: operation not permitted, open 'C:\Users\test\.dsh\profiles\headless\cordis.yml'
```

Same failure with `--dump-default-config` (same code path). Same failure with `$env:DSH_PERMISSION_MODE = "danger-full-access"`.

**Evidence:**
1. Source at `node_modules/@deepseek-ai/dsh/lib/profile-boot-DG5t9aNs.js` lines 140-143:
   ```js
   function prepareProfile(name, userLayer = true) {
     // ...
     writeFileSync(join(profile.dir, PROFILE_ROOT_FILENAME), PROFILE_ROOT_CONFIG);
   ```
   Every invocation of `--dump-config` calls `prepareProfile()`, which unconditionally calls `writeFileSync` on `~/.dsh/profiles/headless/cordis.yml`.

2. The DSH file sandbox (`workspace-write`) restricts writes to `C:\Users\test\Documents\dsh2.0\`. `~/.dsh/` is outside the workspace. Even PowerShell `Out-File` to that directory fails — this is not a Node.js issue; the sandbox policy blocks all writes to that path.

3. `lean_check.py` (lines 83-103) calls `dump()` twice — once with the Lean patch and once for the default — both hit the same EPERM, and the script exits rc=1 without producing any comparison.

4. `docs/PHASE0.md` claims the measurement returned `OK` — we cannot reproduce that result under the same sandbox constraints that govern actual harness use.

**Why it matters:** The verification tool IS the control for step 2. Without it, there is no automated way to prove that the composed tree differs from the default tree by exactly the declared rows. Every dsh version bump, every profile change, every new plugin in the bundle could silently drift the Lean preset, and the claimed guard (`lean_check.py`) would not catch it because it cannot even start. This is a **falsification of the claim that step 2 is done**: the measurement is not reproducible.

**Severity rationale:** HIGH because `lean_check.py` is the ONLY automated verification for this step. The PHASE0.md journal treats its output as the acceptance criterion. If it cannot run, the step is unverified.

---

### [MEDIUM] `# tools-absent:` annotation is incomplete — `web_fetch` is missing

**Claim attacked:** The `# tools-absent:` line at the bottom of `lean.patch.yml` claims to enumerate every tool removed from the Standard catalog.

**Reproduction:**
```powershell
# dsh-tool-web registers TWO tools, not one:
grep -r "defineTool" node_modules/@deepseek-ai/dsh-tool-web/lib/index.js
```

**Evidence:**
- `dsh-tool-web/lib/index.js` registers **two** tools: `web_search` (line 256) and `web_fetch` (line 711).
- `lean.patch.yml` line 125 declares: `# tools-absent: skill web_search workflow ralph create_goal get_goal update_goal subagent_vision`
- `web_fetch` is **not listed**, even though disabling `tool-web` (line 42) removes both tools.

The other mappings check out:
| Plugin disabled | Tool(s) removed | In `# tools-absent:`? |
|---|---|---|
| `tool-skill` | `skill` | ✓ |
| `tool-web` | `web_search`, `web_fetch` | ✗ (`web_fetch` missing) |
| `tool-workflow` | `workflow` | ✓ |
| `tool-ralph` | `ralph` | ✓ |
| `tool-goal` | `get_goal`, `create_goal`, `update_goal` | ✓ |
| `tool-subagent-vision` | `subagent_vision` | ✓ |
| `tool-pwsh` | `pwsh` (replaced, not just removed) | N/A |

**Why it matters:** This is a documentation/maintenance hazard. If someone reads `# tools-absent:` as authoritative and checks for `web_fetch` in the Lean tool catalog, they won't find it — because it was never there. But the annotation claims completeness and is not complete. A future `lean_check.py` enhancement that cross-checks `# tools-absent:` against the default dump would correctly flag this as a mismatch, creating noise.

**Severity rationale:** MEDIUM — does not affect runtime behavior (the tool IS stripped), but the annotation is the human-readable contract for what the preset removes, and it's wrong.

---

### [MEDIUM] `lean_check.py` compares JSON-serialized configs — behavioral drift is invisible

**Claim attacked:** « the composed tree differs from the default tree by exactly these rows »

**Reproduction:** Read `harness/lean_check.py` lines 51-67 (`compare_trees` function):
```python
def compare_trees(composed, default):
    keys1 = set(composed.keys())
    keys2 = set(default.keys())
    only_composed = keys1 - keys2
    only_default = keys2 - keys1
    common = keys1 & keys2
    diffs = []
    for k in sorted(common):
        v1 = json.dumps(composed[k], sort_keys=True, default=str)
        v2 = json.dumps(default[k], sort_keys=True, default=str)
        if v1 != v2:
            diffs.append((k, composed[k], default[k]))
    return only_composed, only_default, diffs
```

**Evidence:**
1. **`json.dumps` with `default=str`** serializes non-JSON types (functions, `!!js` expressions, symbols) as their string representation. Two different `!!js` expressions could produce the same string (`"<js expression>"`) and compare equal, even though they evaluate to different runtime values. Conversely, the same expression captured at different times could produce different strings and be flagged as drift when there is none.

2. **Config fields that are not serializable** (functions, class instances, Promises) would be coerced by `default=str` — `"<function ...>"` vs `"<function ...>"` always compare equal even if the functions differ.

3. **Behavioral changes without config changes** are invisible. If `dsh-tool-subagent` v0.1.2 changes how `toolFilter` works internally without changing its default config, `lean_check.py` sees identical JSON and reports no drift. But the preset's behavior has changed.

4. **New rows inserted by a dsh bump** would be flagged as `only_composed` or `only_default`, which is correct — but only if the script can run (see HIGH finding).

5. **Row order** is not compared (the code compares `set(keys)`), but the Lean patch comments say "Row order carries no load semantics" — so this is correct behavior, not a bug.

**Why it matters:** The worker records "dérive = exactement les lignes déclarées" as the acceptance criterion. Even if the script could run, this comparison only proves config-level drift, not behavioral drift. A silent behavioral change in a kept plugin (e.g., the `web_search`-shaped tool in `dsh-tool-web` being replaced by a local-only version) would pass the check but break the preset's contract.

**Severity rationale:** MEDIUM — `lean_check.py` is designed to be a config-level check and it IS honest about its scope (it compares dumps). But the PHASE0.md journal treats it as if it proves the preset is correct, which overstates what the tool actually verifies.

---

### [LOW] Chat command infrastructure partially active — `/feedback` and `/compact` survive

**Claim attacked:** « stripped: workflow extras » — the goal driver and its chat command are removed, but the commands router and two other chat commands remain active.

**Reproduction:**
- `lean.patch.yml` disables `command-goal` (line 63) but does NOT disable `commands` (the router), `command-feedback`, or `command-compact`.
- These three ids (`commands`, `command-feedback`, `command-compact`) are present in `dsh-base/cordis.patch.yml` and are NOT in the Lean disable list.

**Evidence:**
- `dsh-base/cordis.patch.yml` line 250: `- id: commands` — the chat command router
- Line 253: `- id: command-feedback` — the `/feedback` command
- Line 289: `- id: command-compact` — the `/compact` command
- None of these three ids appear in `lean.patch.yml`.

**Why it matters:** In an automated harness run, `/feedback` has no human to type it, so the risk is minimal. `/compact` gives the model a SECOND path to trigger compaction (alongside the automatic `compaction-basic`), which slightly changes the model's context-management surface compared to a truly minimal preset. Neither is a second path to a stripped feature (web search, skills, workflows), so they do not satisfy ⚑ RT 1. They are, however, rows that survive the "workflow extras" purge without being declared in the "kept, unchanged" section.

**Severity rationale:** LOW — no second path to stripped features, no measurable impact on automated runs.

---

## What I checked and did not break

### ⚑ RT 1: Are stripped features still reachable through another path?

| Path investigated | Result |
|---|---|
| **Subagent spawn (`subagent`)** | `dsh-subagent-spawn-in-process` creates child on same cordis context (`parent.ctx.agents.create`). Same profile, same patch layers, same tool catalog. Child CANNOT escape Lean. |
| **Subagent fork (`subagent_fork`)** | `dsh-subagent-fork-in-process` seeds child with parent's session log prefix, otherwise same as spawn. Same cordis context. Child CANNOT escape Lean. |
| **MCP rows** | `mcp-effitech` is disabled. `dsh-headless` bundle contains no MCP rows. No MCP client can inject tools. |
| **Skills injection** | `skill`, `skill-filesystem`, `tool-skill` all disabled. `agent-instructions` is separate (loads AGENTS.md/CLAUDE.md) and correctly kept — the harness's own prompts depend on it. |
| **Web search** | `web`, `web-search-deepseek`, `tool-web` all disabled. No other plugin in the headless profile registers `web_search` or `web_fetch`. |
| **Workflow extras** | All 7 rows disabled (`workflow-worker-thread`, `tool-workflow`, `tool-ralph`, `tool-goal`, `goal`, `goal-round-driver`, `command-goal`). No alternative path to workflow tools or goal tools. |
| **Vision subagent** | `tool-subagent-vision` disabled. No other plugin registers `subagent_vision`. |
| **One-shot pwsh** | `tool-pwsh` disabled. Replaced by `lean-pty` + `lean-terminal-pwsh` + `lean-persistent-pwsh`. Tool name `pwsh` is the same — model sees no difference. |

**Conclusion for ⚑ RT 1:** No stripped feature is reachable through another path. The disable rows are comprehensive and correctly target all ids that provide the stripped capabilities.

### ⚑ RT 2: Does the preset drift from Standard beyond the declared patch layers?

| What I verified | Result |
|---|---|
| **`# tools:` claim (18 tools) vs wire.jsonl** | Exact match. First tooled call in `scripts/bench_julia_effort/_fumee/wire.jsonl` has `sent.tools` = `["edit","exit_plan_mode","glob","grep","interrupt_agent","job_kill","job_list","job_output","list_agents","pwsh","read","read_image","send_message","str_replace_editor","subagent","subagent_fork","todo_write","write"]` — 18 tools, identical to the claim. |
| **`--dump-config` comparison** | Cannot verify — EPERM (see HIGH finding). |
| **Insert rows** | 4 inserts (`lean-pty`, `lean-terminal-pwsh`, `lean-persistent-pwsh`, `secret-redactor`), all use shipped `@deepseek-ai/*` packages except `secret-redactor` which uses the local `dsh-secret-redactor` plugin. No forked or copied code. |
| **User layer interaction** | The user's `~/.dsh/profiles/headless/cordis.patch.yml` inserts `subagent-timeout`, `mcp-effitech`, and `tool-subagent-vision`. Lean disables the latter two. `subagent-timeout` survives (it bounds subagent duration — this is desirable and declared as "kept" in the patch comments). |

**Conclusion for ⚑ RT 2:** Beyond the EPERM issue (which prevents full verification), the only undeclared survivors are `command-feedback` and `command-compact` (see LOW finding). No evidence of undeclared tool additions or capability changes.

---

## Verdict

**The claim that step 2 is DONE is FALSIFIED.**

The single strongest finding is the **HIGH-severity EPERM failure**: `dsh --dump-config` cannot run under the `workspace-write` sandbox that governs all actual harness use. The verification tool (`lean_check.py`) that the step's acceptance depends on is non-functional. The `docs/PHASE0.md` measurement of `OK` cannot be reproduced. Without a working `--dump-config`, there is no automated guard against profile drift after dsh version bumps.

The stripped features themselves appear correctly disabled (RT 1 passes), and the wire.jsonl tool catalog matches the claim. But **you cannot prove** that the composed tree differs from the default tree by exactly the declared rows, because the tool that proves it is broken by the same sandbox that the harness runs under.

**Recommended fix:** Either (a) make `prepareProfile()` skip the `writeFileSync` when the file already contains the canonical root config, or (b) give the dsh binary a `workspace-write` exception for its own `~/.dsh/profiles/` directory, or (c) make `--dump-config` not call `prepareProfile()` at all (it only needs the composed tree, not the persisted root).

## Reponse de l'ouvrier (2026-08-23, avant decision humaine)

- **HIGH « lean_check.py non reproductible (EPERM) »** : vrai *depuis l'interieur du
  sandbox dsh* du red team (`--dump-config` ecrit `~/.dsh/profiles/headless/cordis.yml`,
  hors de l'espace `workspace-write`). Depuis un shell normal, relance le 23/08 apres le
  rapport : `arbre de base : 84 rangees ; arbre Lean : 88 rangees ; couche : 17 desactivees,
  4 inserees / rangees actives : base 82 -> Lean 69 / VERDICT : OK`. Correctif d'outillage :
  `redteam_run.py --prep "<cmd>"` lance les controles hors sandbox et depose leur sortie
  dans `_rt_scratch/prep_<n>.txt` avant le red team (utilise pour 0-walls et 0-done).
  Proposition : reclasser en limite d'environnement ; la mesure de l'etape tient.
- **MEDIUM « web_fetch manque a tools-absent »** : exact (`dsh-tool-web/lib/index.js`
  enregistre `web_search` et `web_fetch`). Sur le fil du run Lean : 0 occurrence de
  `web_fetch` (l'outil est bien absent). Corrige : annotation `# tools-absent:` et
  commentaire de la section web dans `harness/lean.patch.yml`, catalogue dans
  `docs/PHASE0.md`.
- **MEDIUM « lean_check compare des configs, pas des comportements »** : exact et
  assume ; `docs/PHASE0.md` §2 le dit maintenant en toutes lettres (l'arbre compose pour
  la derive, le catalogue sur le fil pour les outils).
- **LOW « command-feedback / command-compact survivent »** : ce sont des commandes de
  chat de la surface interactive, jamais offertes au modele en headless ; gardees, et
  dites dans le commentaire « kept » de la couche.
- **RT 1 (second chemin) : PASSES** selon le red team (les sous-agents heritent du meme
  contexte cordis, MCP retire, pas de chemin vers web/skills/workflows/vision).

## Decision humaine

_(a remplir : pour chaque trouvaille HIGH, « corrige dans <commit> » ou « acceptee : <raison> »)_
