# Harness Spec

Self-improving LLM dev harness on DeepSeek Harness (dsh). Serves daily work on a
private 600k+ LOC Julia framework. Solo owner. This repo is MIT. Daytime: framework
work on `stable` profile. Harness changes land in `staging`.

## Backbone
- Custom **Lean preset**, authored in Creator mode: duplicate Standard, strip skills
  injection, web-search tool, workflow extras. Keep: persistent bash,
  str_replace_editor, subagent scheduler, compaction.
- Preset = thin patch layers over the Standard bundle. No forked plugin code.
- Version bumps: apply in `staging` → run replay suite → diff `--dump-config`
  against last known-good → promote.
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
| OpenRouter stealth/free | harness dev, probation tasks | OPEN only | sprint |
| z.ai GLM (€18) | interactive coding | PRIVATE+OPEN | sprint |
| DeepSeek API | agent-loop coder, off-peak batch, improver proposals | PRIVATE+OPEN | sprint |
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
3. **Nightly improver** (separate repo + profile + budget): refresh → distill →
   propose config diffs (off-peak DeepSeek) → verify on replay suite → branch +
   3-line summary.
   - Judge model pinned + versioned; never a model whose ranking is being edited.
   - Auto-revert: merged change regressing tokens/diff or first-pass rate beyond
     threshold over 3 days reverts automatically (the only self-applied action).
   - Human review weekly. "No change" is a valid outcome. Freeze merges during
     delicate framework refactor weeks.

## Rules
- Everything in git: preset layers, YAML, prompts, scripts, SQLite schema.
- Pin dsh version and plugins to exact commits (`github:owner/repo#sha`).
  dsh-poison-guard scan before install; startup-guard active; no auto-updates.
- Per-task metrics: tokens/merged diff, first-pass test rate, escalation rate,
  cache-hit rate, wall-clock. Every harness change moves one or reverts.
- Cache discipline: stable system-prompt prefix, no per-turn content ahead of the
  cached region, check duplicate CLAUDE.md/AGENTS.md injection. Batch work off-peak
  (peak 01:00–04:00, 06:00–10:00 UTC).
- Budget €60–100/month. OpenRouter drain >€40/month ⇒ fix routing. Cache-hit <50%
  ⇒ find the cache-buster in dsh-context.
- Escalate to frontier after two failed cheap-tier attempts.
- Plugin-list review monthly.

## Phases

Sprint = Phases 0–2 at 100% allocation, OpenRouter-first. Framework work resumes at
the Phase 2 done-criterion; Phases 3–5 run in parallel afterward, fed by live logs.

**Parallel tracks within the sprint** (independent, can run as concurrent Claude
Code sessions on separate worktrees):
- Track A: Phase 0 (harness foundation) — dsh + preset + providers.
- Track B: Phase 0.5 (Julia test gate) — pure Julia tooling, zero harness
  dependency; also the long-lead risk item, so start it day one.
- Track C: Phase 1 refresh script — plain Python/SQLite against the OpenRouter
  API; only its final "emit config + session hook" step needs Track A done.
Phase 2 is sequential (needs A+B+C) and adds workers one at a time.

### 0 — Foundation
- [ ] Repo init; this spec as README; dsh from source, version pinned.
- [ ] Author Lean preset (Creator mode); commit patch layers; verify --dump-config.
- [ ] OpenRouter as provider: paid + free/stealth model IDs; keys in credentials
      file only.
- [ ] z.ai + DeepSeek as direct providers.
- [ ] Secret-redactor installed; OPEN-worker permission walls set.
- **Done:** Lean agent completes a small real framework task end-to-end; an OPEN
  worker provably cannot read the framework repo.

### 0.5 — Fast Julia test gate (blocks Phase 2)
- [ ] Targeted runner: changed files → affected test items (ReTestItems or equiv).
- [ ] Persistent Julia session (Revise daemon) or sysimage; no TTFX in the loop.
- [ ] Full suite pre-merge only.
- **Done:** one-file edit → verdict <30s. If unreachable: STOP, redesign Phase 2.

### 1 — Model loop
- [ ] Refresh script → SQLite: models(id, provider, ctx, tool_calls, free, stealth,
      probation, tier, first_seen, last_seen, task_scores). Rank → emit config.
- [ ] Stealth injection with probation + tier. Hook into session start.
- [ ] cost-meter + dsh-context installed, real prices, cache-hit visible.
- **Done:** new OpenRouter stealth model reaches the OPEN chain in one session
  start; one day's cost + cache-hit rate visible.

### 2 — Agent split (one worker at a time)
- [ ] `searcher`: verify orchestrator context stays flat during research turns.
- [ ] Context7: probe resolve-library-id for the framework's top Julia dependencies;
      submit missing ones via context7.com/add-library (GitHub repo or Documenter
      docs URL); wire searcher routing docs-first, web-search fallback.
- [ ] `coder` wired to Phase 0.5 gate.
- [ ] `planner` read-only on top PRIVATE route.
- [ ] `claude-code` wrapper script; verify JSON parses and cost hits the meter.
- **Done:** mid-sized real task passes planner → coder → green targeted tests →
  green full suite, flat orchestrator context, cost measured.

### 3 — Memory
- [ ] Session-end distiller (DeepSeek off-peak; local Qwen after Phase 5):
      scores → SQLite; lessons → planner notes.
- [ ] Memory plugin (dsh-mnemon, or the SQLite ctx.memory provider) only if the
      notes file proves insufficient.
- **Done:** planner avoids a previously logged mistake.

### 4 — Nightly improver (after 2 stable weeks)
- [ ] Separate repo/profile/budget; read-only log copies in, branch out.
- [ ] Pipeline + auto-revert wiring; replay suite = 5–10 logged real tasks with
      metric baselines and pinned judge.
- **Done:** three consecutive honest runs (incl. "no change"); one deliberately
  bad config caught by verify + auto-revert.

### 5 — Cost layer (post-sprint, parallel with framework work; OPEN-tier tasks
executed by the harness itself)
- [ ] Local Qwen serving (quantized for 24GB): wire as provider; move embeddings,
      digests, distillation onto it; probation as coder.
- [ ] freellmapi in Docker: real ENCRYPTION_KEY, provider keys, ToS-violating
      providers disabled, `coding` fallback chain; refresh script extended to its
      catalog; OPEN workers migrated from OpenRouter free to freellmapi chains.
- **Done:** OPEN-tier work runs at ~€0 marginal cost; PRIVATE distillation local;
  OpenRouter drain drops to planning-only.

## Verify early
1. Lean preset survives a dsh bump with patch-layer edits only (Phase 0, each bump).
2. Targeted Julia tests <30s (Phase 0.5 — hard gate).
3. DeepSeek cache-hit >50% under Lean preset (Phase 1).
4. GLM/DeepSeek Julia quality acceptable with the test gate (Phase 2, week 1 —
   core bet).
5. claude -p output parses; cost metered (Phase 2).
6. OPEN workers walled off from framework repo (Phase 0; re-test after any
   permission/plugin change).

## Risks
- dsh preview, breaking changes → patch layers, pins, staging, opencode exit.
- Free-tier churn, stealth models train on inputs → failover, probation, tiers.
- Julia weak on cheap models → fast gate load-bearing, early escalation.
- Solo maintainer → each phase ships value alone; improver caps review at weekly.
