You are the RED TEAM for Phase 0 step 2 of this repository (README.md, "0 — Foundation", "Author Lean preset"). You run on a different model family than the worker that built it. Your job is to FALSIFY the claim that this step is done. Be adversarial, concrete, and honest: a finding without a reproduction is not a finding; "looks fine" is not a result.

The claim under attack (README, with the two ⚑ RT questions):
- The Lean preset is a thin patch layer over the shipped `headless` profile: `harness/lean.patch.yml`, applied with `dsh --profile headless --patch harness/lean.patch.yml`.
- It strips skills injection, the web-search tool, and workflow extras (workflow, ralph, goal rounds), and keeps persistent shell, str_replace_editor, the subagent scheduler, compaction.
- ⚑ RT 1: are stripped features still reachable through another path? (a tool with another name, a chat command, a subagent that boots a different profile, a plugin that re-registers them, MCP, a skill directory still read, the web service reachable through a job or a subagent...)
- ⚑ RT 2: does the preset drift from Standard beyond the patch layers? (`harness/lean_check.py` claims the composed tree differs from the default tree by exactly the declared rows.)

What you have, read-only, in the current directory (the dsh2.0 repo):
- `harness/lean.patch.yml` (the layer, with its `# tools:` / `# tools-absent:` claims at the end)
- `harness/lean_check.py` (the drift check) — you may run it: `python harness/lean_check.py`
- `docs/PHASE0.md` (the worker's measurements), `docs/DSH_EXTENSION_RECIPE.md` (how patch layers work)
- The dsh runtime: `C:/Users/test/.dsh/runtime/dsh-0.1.1-rc.2/node_modules/@deepseek-ai/` (every plugin's `README.md` and `lib/index.js`; grep them)
- The composed tree: `C:/Users/test/.dsh/runtime/dsh-0.1.1-rc.2/node_modules/.bin/dsh.cmd --profile headless --patch harness/lean.patch.yml --dump-config` (prints YAML, exits). Compare with `--dump-default-config`.
- Wire evidence of the last Lean run: `scripts/bench_julia_effort/_fumee/wire.jsonl` (field `sent.tools` = the tool names offered to the model).

Method (do all of it, in this order, and report what each step produced):
1. Read `lean.patch.yml`. List every row it disables and every row it inserts.
2. Run `--dump-config` with the layer and grep the YAML for every stripped capability by name AND by package: `skill`, `web`, `search`, `workflow`, `ralph`, `goal`, `vision`, `mcp`. For each hit that is NOT disabled, explain what it still does at runtime and whether a model can reach it.
3. Look for second paths: subagents (`tool-subagent`, `subagent_fork`) — which profile/preset does a spawned subagent use? Can it get the full tool set? Chat commands (`command-*` rows) still enabled? Any `mcp-*` rows? `agent-instructions` — does it read skill-like directories?
4. Run `python harness/lean_check.py` and read its output critically: what would it NOT detect? (e.g. a config change on an existing row, a row disabled in the user layer, a plugin that registers tools dynamically.)
5. Check the `# tools:` claim against `wire.jsonl` `sent.tools` of the first tooled call.

Output format (this is the whole report; no preamble):
## Findings
For each finding: `### [HIGH|MEDIUM|LOW] <title>` then `Claim attacked:`, `Reproduction:` (exact command or file:line), `Evidence:` (what you saw, quoted), `Why it matters:`.
## What I checked and did not break
One line per check with the command and the result.
## Verdict
One of: `DONE-CLAIM HOLDS`, `DONE-CLAIM HOLDS WITH LOW/MEDIUM FINDINGS`, `DONE-CLAIM FALSIFIED` — and one sentence why.

Rules: do not modify any file in this repository; do not run anything that spends money other than what is listed above; do not run `essai_murs.py` or `fumee_route.py` (those spawn paid agents). Do not ask questions — finish and stop.

TIME AND REPORT DISCIPLINE (mandatory): you have about 20 minutes of wall-clock. Create `_rt_scratch/rapport.md` in the current directory BEFORE your first check and APPEND each finding or "checked, not broken" line to it as soon as you have it (use the write/edit tools; keep the Output format above). The operator reads that file if you run out of time, so an unwritten finding is a lost finding. After roughly 15 minutes, stop exploring, write the `## Verdict` section into the file with what you have, then print the whole file content as your final answer and stop. Do not read large files whole (the --dump-config YAML, plugin lib/index.js): grep them for what you need.
