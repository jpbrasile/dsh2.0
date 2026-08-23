You are the SECOND red team for Phase 1 ("Model loop") of the dsh2.0 harness. The first red team (`redteam/1-done.md`, read its "Reponse de l'ouvrier" section first) FALSIFIED the Done claim: the `open` chain was empty. The worker then changed the code. Your job: FALSIFY the corrected claim, or say precisely why it holds now.

Corrected claim: "a new OpenRouter stealth model reaches `openrouter-auto` + the `probation` chain at the first session start, and reaches the `open` chain (`harness/chaines.yaml`) at the session start following 3 green `minimal` runs; one day's cost + cache-hit rate visible." Current state: `chaines.yaml` has `open: [stealth/ox-alpha]` after 3 green smoke runs recorded by `scripts/bench_julia_effort/fumee_route.py` into `harness/modeles.sqlite` (table `verdicts`).

What changed since the first red team (read-only, current directory = dsh2.0 repo):
- `fumee_route.py` (end of file): after each run it calls `python harness/modeles.py --verdict <model> --tache ... --preset <minimal | patch:NAME> --vert|--rouge`, but only if ALL recorded calls were served by the requested model (`servi`), and not when `FUMEE_SANS_VERDICT=1`.
- `harness/modeles.py`: `_prix()` refuses NaN/Infinity/booleans; `verifier_emis()` accepts exactly one block, `openrouter-auto`; `harness/providers_install.py` refuses (rc 3, nothing written) an emitted block whose name exists in `providers.yaml`.
- `harness/cout.py`: `ingerer()` reports ignored duplicates, marked DIVERGENT when the cost differs; CLI rc 1 on a divergent.
- `docs/PHASE1.md` section 5 states the limits: the 3 greens are the PONG smoke (low stakes); `--verdict` on the CLI is unguarded by design (the operator's tool).
You may run, free of charge: `python harness/modeles_unit.py`, `python harness/modeles.py --classer`, `python harness/modeles.py --verdict ... --base <a COPY of modeles.sqlite in _rt_scratch/>`, `python harness/modeles.py --emettre --base <copy>` (this rewrites harness/providers.emis.yaml and chaines.yaml in the repo: after any --emettre on a copy, finish with `python harness/modeles.py --emettre` on the real base so the tracked files are restored), `python harness/cout.py --livre _rt_scratch/l.jsonl --ingerer <your JSONL>`. Never run `--session`, `fumee_route.py` or `redteam_run.py` (paid agents / writes settings.yaml). Never modify a tracked file.

Attack surface -- TWO angles only, in this order:
1. The path to the `open` chain. Read the verdict hook at the end of `fumee_route.py` and `probation_de()` / `verts_minimal()` in `modeles.py`. Can a model reach `open` without 3 green stock runs served by itself? Look for: a failed run noted green; a run served by another model (`servi` differs) noted on the requested model; a run with 0 calls; a patched run counted as `minimal` (the preset comes from the patch file name); verdicts on a model id with different case/unicode; a verdict noted on a PRIVATE+OPEN model changing its tier; `probation_de()` recomputed at `--rafraichir` — does a refresh re-enter probation or skip it wrongly; a disappeared model (`disparu=1`) kept in `open`. Reproduce on a COPY of the base with `--verdict` and a crafted catalog via `--catalogue`.
2. Cost honesty after the fix. Craft a wire JSONL with duplicates (same cost, different cost, missing usage, `cost` absent on a paid model, `status` 500 with usage) and check what `cout.py` reports and what it silently keeps. Is `--jour` correct across a midnight boundary (t0 in ms vs s)? Is a 54-call red-team run's cost the sum of `usage.cost` or something else?

Output format (this is the whole report; no preamble):
## Findings
For each: `### [HIGH|MEDIUM|LOW] <title>`, `Claim attacked:`, `Reproduction:` (exact commands/files), `Evidence:` (quoted output), `Why it matters:`.
## What I checked and did not break
One line per check with the command and the result.
## Verdict
`DONE-CLAIM HOLDS` / `DONE-CLAIM HOLDS WITH LOW/MEDIUM FINDINGS` / `DONE-CLAIM FALSIFIED` -- one sentence why.

Rules: modify nothing tracked; everything you create goes under `_rt_scratch/`. Do not ask questions -- finish and stop.

TIME AND REPORT DISCIPLINE (mandatory, the first red team ignored it and made 54 calls): you have about 12 minutes of wall-clock; the run is killed at 15. HARD CAP: 20 tool calls in total, count them. Create `_rt_scratch/rapport.md` BEFORE your first check and APPEND each finding or "checked, not broken" line to it as soon as you have it. After the 18th tool call or 10 minutes, whichever comes first, stop exploring, write the `## Verdict` section into the file with what you have, then print the whole file content as your final answer and stop. Do not read large files whole: grep them for what you need.
