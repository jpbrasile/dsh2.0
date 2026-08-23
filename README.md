# Harness Spec

Self-improving LLM dev harness on DeepSeek Harness (dsh). Serves daily work on a
private 600k+ LOC Julia framework. Solo owner. This repo is MIT. Daytime: framework
work on `stable` profile. Harness changes land in `staging`.

Two execution principles run through everything below:

- **Single thread.** One agent executes the work sequentially, one step at a time.
  No concurrent sessions, no parallel worktrees. The human intervenes only at
  red-team gates and phase done-criteria.
- **Red team after every critical step.** A `red-team` agent on a *different LLM*
  than the one that did the work tries to break the step before it counts as done.
  Critical steps are marked **⚑ RT** in the Phases section.

## Backbone
- Custom **Lean preset**, authored in Creator mode: duplicate Standard, strip skills
  injection, web-search tool, workflow extras. Keep: persistent bash,
  str_replace_editor, subagent scheduler, compaction.
- Preset = thin patch layers over the Standard bundle. No forked plugin code.
- Version bumps: apply in `staging` → run replay suite → red-team the diff →
  diff `--dump-config` against last known-good → promote.
- Stock Minimal preset: model benchmarking / probation scoring only.
- Agent prompts are harness-agnostic markdown (portable to opencode).

## Model routes — two tiers
**OPEN** = this harness repo. **PRIVATE** = framework repo + all session logs from
framework work (logs contain framework code; they inherit PRIVATE wherever stored).
The harness repo never contains logs or credentials.

**Sprint providers** (Phases 0–2): OpenRouter is the sole gateway — frontier,
cheap, and stealth tiers behind one endpoint, one key. z.ai + DeepSeek added as
direct dsh providers (5-min YAML each) to exercise multi-provider routing.
**Post-sprint providers** (Phase 5, parallel with resumed framework work): local
Qwen inference + freellmapi.

| Route | Use | Tier | When |
|---|---|---|---|
| OpenRouter paid | frontier planning; sprint default for all workers | PRIVATE+OPEN | sprint |
| OpenRouter stealth/free | harness dev, probation tasks, red team on OPEN steps | OPEN only | sprint |
| z.ai GLM (€18) | interactive coding; red team when worker was DeepSeek | PRIVATE+OPEN | sprint |
| DeepSeek API | agent-loop coder, off-peak batch, improver proposals; red team when worker was GLM | PRIVATE+OPEN | sprint |
| Local Qwen (RTX 4090) | embeddings, repo index, digests, log distillation | PRIVATE+OPEN | Phase 5 |
| freellmapi free chains | harness dev, search digests, drafts | OPEN only | Phase 5 |

Until Phase 5, PRIVATE distillation jobs run on DeepSeek off-peak instead of local
Qwen. Enforcement: OPEN-route workers have tool permissions scoped to the harness
repo; no read access to framework repo or log store. Secret-redactor masks keys in
tool results.

## Agents
- `planner` — top-ranked PRIVATE route. Read-only. Outputs a plan.
- `searcher` — search tools + Context7 MCP (mcp.context7.com), OPEN chains, no
  write/edit. Library/API questions route to Context7 first (resolve-library-id →
  query-docs, version-pinned); web search on miss. Returns digest + links. Queries
  carry library names and generic questions only — no framework code.
- `coder` — DeepSeek/GLM. bash + editor. Loop: edit → targeted tests → green diff
  or structured failure. Full suite pre-merge only.
- `claude-code` — `claude -p "<task>" --output-format json` from bash, API-key auth,
  wrapped with --allowedTools and --max-turns. Selected by ranking like any worker.
- `red-team` — adversarial reviewer. Runs on a **different model family/provider**
  than the agent whose work it reviews (never the same model; never a model on
  probation or whose ranking is being edited). Read-only + test execution, same
  tier as the data it sees (PRIVATE diff → PRIVATE route). Input: the step's
  done-criterion, the diff/config, the logs. Job: falsify the "done" claim —
  unverified assumptions, tests that pass trivially, permission or secret leaks,
  cost leaks, drift from this spec. Output: findings with severity, reproduction,
  evidence, committed to `redteam/<phase>-<step>.md`. A step closes only when every
  HIGH finding is fixed or explicitly accepted by the human in that file.
- Orchestrator: Lean preset, mid-tier model, minimal tools.
- Compaction: composed in Lean preset. Metering: dsh-cost-meter + dsh-context, real
  prices on all paid routes, cache-hit rate tracked.

## Loops
1. **Session start:** poll OpenRouter /api/v1/models (+ freellmapi catalog from
   Phase 5) → SQLite
   upsert → task-fit rank → emit provider YAML / fallback chains. New stealth models:
   custom endpoint, `probation` flag, OPEN tier, low-stakes tasks until N green
   diffs scored under stock Minimal.
2. **Session end:** distiller sweeps session log → outcome scores into SQLite
   (model × task-type) → lessons file injected into planner context. Runs on
   DeepSeek off-peak until Phase 5, local Qwen after.
3. **Red-team gate** (after each ⚑ RT step): worker reports done → `red-team` on a
   different LLM attacks the done-criterion → findings file → fix or accept →
   step closes. A first-attempt pass with zero findings is suspicious: re-run once
   with a second, different model before accepting it.
4. **Nightly improver** (separate repo + profile + budget): refresh → distill →
   propose config diffs (off-peak DeepSeek) → red-team the diff → verify on replay
   suite → branch + 3-line summary.
   - Judge model pinned + versioned; never a model whose ranking is being edited.
     Red-team model ≠ judge ≠ proposer.
   - Auto-revert: merged change regressing tokens/diff or first-pass rate beyond
     threshold over 3 days reverts automatically (the only self-applied action).
   - Human review weekly. "No change" is a valid outcome. Freeze merges during
     delicate framework refactor weeks.

## Rules
- Everything in git: preset layers, YAML, prompts, scripts, SQLite schema, red-team
  findings.
- Pin dsh version and plugins to exact commits (`github:owner/repo#sha`).
  dsh-poison-guard scan before install; startup-guard active; no auto-updates.
- Per-task metrics: tokens/merged diff, first-pass test rate, escalation rate,
  cache-hit rate, wall-clock, red-team findings per step. Every harness change
  moves one or reverts.
- Red-team diversity: the red-team route is picked by the refresh ranking from a
  provider family different from the worker's, pinned per phase, recorded in the
  findings file. Red-team spend counts in the per-task metrics.
- Cache discipline: stable system-prompt prefix, no per-turn content ahead of the
  cached region, check duplicate CLAUDE.md/AGENTS.md injection. Batch work off-peak
  (peak 01:00–04:00, 06:00–10:00 UTC).
- Budget €60–100/month. OpenRouter drain >€40/month ⇒ fix routing. Cache-hit <50%
  ⇒ find the cache-buster in dsh-context.
- Escalate to frontier after two failed cheap-tier attempts.
- Plugin-list review monthly.

## Phases

Sprint = Phases 0–2 at 100% allocation, OpenRouter-first. Framework work resumes at
the Phase 2 done-criterion; Phases 3–5 follow afterward, fed by live logs.

**Single thread.** One agent (one Claude Code session, one worktree) executes the
sprint as an ordered sequence. The work formerly split into three parallel tracks
is performed by that agent in this order:

1. Phase 0.5 (Julia test gate) — first, because it has zero harness dependency and
   is the hard gate: if it is unreachable the Phase 2 design changes, and that must
   be known before anything is built on it.
2. Phase 0 (harness foundation) — dsh + preset + providers + permission walls.
3. Phase 1 (model loop) — refresh script against the OpenRouter API, then its
   "emit config + session hook" step on top of Phase 0.
4. Phase 2 (agent split) — workers added one at a time.

Every step marked **⚑ RT** ends with a red-team gate (Loop 3) before the next step
starts. Phase done-criteria are always ⚑ RT.

### 0 — Foundation
- [x] Repo init; this spec as README.
- [ ] dsh from source, version pinned.
- [ ] Author Lean preset (Creator mode); commit patch layers; verify --dump-config.
      **⚑ RT:** are stripped features still reachable through another path? does
      the preset drift from Standard beyond the patch layers?
- [ ] OpenRouter as provider: paid + free/stealth model IDs; keys in credentials
      file only.
- [ ] z.ai + DeepSeek as direct providers.
- [ ] Secret-redactor installed; OPEN-worker permission walls set.
      **⚑ RT:** from an OPEN-route worker, attempt to read the framework repo and
      the log store; plant a fake key in a tool result and check it is masked.
- **Done (⚑ RT):** Lean agent completes a small real framework task end-to-end; an
  OPEN worker provably cannot read the framework repo.

### 0.5 — Fast Julia test gate (blocks Phase 2; executed first)
- [ ] Targeted runner: changed files → affected test items (ReTestItems or equiv).
- [ ] Persistent Julia session (Revise daemon) or sysimage; no TTFX in the loop.
- [ ] Full suite pre-merge only.
- **Done (⚑ RT):** one-file edit → verdict <30s. Red team plants a breaking change
  in a file the runner's mapping is likely to miss and checks the verdict goes red.
  If unreachable: STOP, redesign Phase 2.

### 1 — Model loop
- [ ] Refresh script → SQLite: models(id, provider, ctx, tool_calls, free, stealth,
      probation, tier, first_seen, last_seen, task_scores). Rank → emit config.
- [ ] Stealth injection with probation + tier. Hook into session start.
      **⚑ RT:** feed a malformed catalog and a fake model entry; try to get a
      probation model onto a PRIVATE route or a high-stakes task.
- [ ] cost-meter + dsh-context installed, real prices, cache-hit visible.
- **Done (⚑ RT):** new OpenRouter stealth model reaches the OPEN chain in one
  session start; one day's cost + cache-hit rate visible.

### 2 — Agent split (one worker at a time, each followed by a red-team gate)
- [ ] `searcher`: verify orchestrator context stays flat during research turns.
      **⚑ RT:** try to make a query carry framework code; check context growth.
- [ ] Context7: probe resolve-library-id for the framework's top Julia dependencies;
      submit missing ones via context7.com/add-library (GitHub repo or Documenter
      docs URL); wire searcher routing docs-first, web-search fallback.
- [ ] `coder` wired to Phase 0.5 gate.
      **⚑ RT:** can the coder obtain a green diff by deleting or weakening tests?
- [ ] `planner` read-only on top PRIVATE route.
      **⚑ RT:** attempt a write through the planner's tool set.
- [ ] `claude-code` wrapper script; verify JSON parses and cost hits the meter.
      **⚑ RT:** escape --allowedTools / --max-turns; unmetered spend.
- **Done (⚑ RT):** mid-sized real task passes planner → coder → green targeted
  tests → green full suite, flat orchestrator context, cost measured.

### 3 — Memory
- [ ] Session-end distiller (DeepSeek off-peak; local Qwen after Phase 5):
      scores → SQLite; lessons → planner notes.
      **⚑ RT:** poison a session log with adversarial content; check it does not
      reach the planner notes as an instruction.
- [ ] Memory plugin (dsh-mnemon, or the SQLite ctx.memory provider) only if the
      notes file proves insufficient.
- **Done (⚑ RT):** planner avoids a previously logged mistake.

### 4 — Nightly improver (after 2 stable weeks)
- [ ] Separate repo/profile/budget; read-only log copies in, branch out.
- [ ] Pipeline + auto-revert wiring; replay suite = 5–10 logged real tasks with
      metric baselines and pinned judge. Red-team step in the pipeline (Loop 4).
      **⚑ RT:** red team authors the deliberately bad configs used to prove
      verify + auto-revert fail on purpose.
- **Done (⚑ RT):** three consecutive honest runs (incl. "no change"); one
  deliberately bad config caught by verify + auto-revert.

### 5 — Cost layer (post-sprint; OPEN-tier tasks executed by the harness itself)
- [ ] Local Qwen serving (quantized for 24GB): wire as provider; move embeddings,
      digests, distillation onto it; probation as coder.
- [ ] freellmapi in Docker: real ENCRYPTION_KEY, provider keys, ToS-violating
      providers disabled, `coding` fallback chain; refresh script extended to its
      catalog; OPEN workers migrated from OpenRouter free to freellmapi chains.
      **⚑ RT:** default ENCRYPTION_KEY still in place? ToS-violating provider
      reachable through a chain? PRIVATE data on a freellmapi route?
- **Done (⚑ RT):** OPEN-tier work runs at ~€0 marginal cost; PRIVATE distillation
  local; OpenRouter drain drops to planning-only.

## Verify early
1. Targeted Julia tests <30s (Phase 0.5 — hard gate, runs first).
2. Lean preset survives a dsh bump with patch-layer edits only (Phase 0, each bump).
3. The red-team gate fails on purpose: a deliberately leaky permission rule must
   be caught before the gate is trusted (Phase 0). A gate that has never failed
   has not been shown to measure anything.
4. DeepSeek cache-hit >50% under Lean preset (Phase 1).
5. GLM/DeepSeek Julia quality acceptable with the test gate (Phase 2, week 1 —
   core bet).
6. claude -p output parses; cost metered (Phase 2).
7. OPEN workers walled off from framework repo (Phase 0; re-test after any
   permission/plugin change).

## Risks
- dsh preview, breaking changes → patch layers, pins, staging, opencode exit.
- Free-tier churn, stealth models train on inputs → failover, probation, tiers.
- Julia weak on cheap models → fast gate load-bearing, early escalation.
- Red team rubber-stamps → different provider family enforced, planted-defect
  check per phase, zero-finding passes re-run on a second model.
- Single thread lengthens the sprint → each phase ships value alone; red-team
  gates keep rework from accumulating across phases.
- Solo maintainer → improver caps review at weekly.

## Layout

Preliminary work imported from the plasma repo (`agentic-flow`) on 2026-08-23 with its
history; paths kept as they were so relative references still hold.

- `scripts/dsh.ps1` — dsh launcher (pinned package, profiles, `-InstallPlugins`, `-Cheap`
  via `scripts/openrouter_cheapest_proxy.mjs`). Reads `OPENROUTER_API_KEY` from this repo's
  `.env` (gitignored, never committed).
- `scripts/dsh-plugins/`, `scripts/dsh-mcp/` — cordis plugins and MCP servers mounted by the
  launcher; recipe in `docs/DSH_EXTENSION_RECIPE.md`.
- `scripts/dsh_session_check.mjs`, `scripts/dsh_tree_check.mjs` — guards on the session log
  and the pinned npx tree.
- `scripts/bench_julia_effort/` — the "reasoning effort" bench (Julia tasks, arms, judge,
  `analyse.py`); run outputs (`runs/`, `_par/`, `resultats_*.jsonl`, `wire.jsonl`) stay
  untracked by its own `.gitignore`. `python bench.py --selftest` is the mandatory control.
- `scripts/freellm_key.py`, `scripts/freellm_demarrage.ps1` — FreeLLMAPI key reader and
  start-up; route described in `docs/DSH_FREELLMAPI_ROUTE.md`.
- `docs/DSH_QWEN_LOCAL_LOGBOOK.md` — dated logbook of what was measured on the local route.
- `docs/LOCAL_LLM.md` — the local Qwen / llama.cpp serving setup on the RTX 4090. The
  launchers and the 4090 benchmark **stay in `agentic-flow`** (they also serve that project);
  this page is the pointer the harness needs.
