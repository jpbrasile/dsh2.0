All six files read. Now I have all the evidence I need to produce the plan.

---

## PLAN

### Goal
Write a single new triage note at `docs/vv/TRIAGE_V09_2026-08-24.md` that honestly records the state, history, last conclusion, next probe, and guardrails for V09, citing only the six evidence files by path and line or section — no exploration, no code changes, no other files touched.

### Files to Touch
**Create (1 file):** `docs/vv/TRIAGE_V09_2026-08-24.md` — the triage note.

**Nothing else may be created or modified. No glob, no grep beyond verifying the note exists after writing. No Julia execution. No directory listing.**

### What Each Section Must Contain (with Citations to the Six Files)

#### 1. STATE
- The PIRT row (line 57) says **4/7 FAIL** as of its generation date.
- The STOPPED marker summary (`validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/summary.txt`, line 4) says **5/7 FAIL** on 2026-08-16 (C2 PASS, C3 FAIL, C4 FAIL — the other four pass).
- The discrepancy must be flagged explicitly: PIRT says 4/7; the last artifact that REGRADED criteria (2026-08-16) says 5/7. The two do not agree. The note must report both dates and both scores without guessing which is correct.
- Cite the exact criteria: C2 (2026-08-16: PASS at `199.71 ± 2.71` against bar `[5, 200]`, `comparison.txt` line 51), C3 (FAIL, `comparison.txt` line 52), C4 (FAIL, `comparison.txt` line 53). The other four (C1, C5, C6, C7) pass in both sources.

#### 2. HISTORY
From README (lines 8–11): 5/7 on 2026-07-03 → 4/7 after RNG-repair re-run 2026-08-06 (KI-20) → re-sealed 2026-08-09 on the C2-redress script.
From STOPPED marker (`summary.txt` line 3–4, `comparison.txt` line 3): 2026-08-16 grid-extension probe produced 5/7 (C2 regraded to PASS by seeded-sweep prereg, C3/C4 still FAIL), and the operator stopped rather than sealing — the marker exists to record that decision.
From FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md (lines 1–7): 2026-08-19 arithmetic probe on sealed sweep data — no re-run, no GPU — measured the maximum effect of the N₂ channel lever; proved it cannot turn C3 or C4 green. This is the most recent dated document.

#### 3. LAST CONCLUSION
The 2026-08-19 FINDING is the most recent dated document. Its conclusion (lines 96–118, especially lines 113–118): at the best-fit point (60 Td), the O-atom source is ALREADY inside its anchored band (`[1.50, 8.00]` atoms/100 eV, actual `1.99`). The efficiency *demanded* by the Shimizu comparison (`0.66` atoms/100 eV) is 2.27× below the bottom of that band. Therefore the missing factor cannot reside in the source lever — not even removing the N₂ channel entirely (f=0) makes C3 or C4 pass. The direction designated is sinks of O₃ (or the sampling point), not a source coefficient to lower. This agrees independently with the conclusion of `FINDING_O_SOURCE_N2_CHANNEL` (line 117).

#### 4. SMALLEST NEXT PROBE
The 2026-08-19 FINDING (line 128) names the next step: identify the missing sink. It explicitly says this touches V151, V82, V87, V106 (KI-28) and requires its own prereg — "un chantier séparé, avec son propre préreg" (line 129).
The plan must instruct the coder to state: (a) the single cheapest next measurement is an O₃-sink budget audit (not a re-run, not a GPU job), (b) it MUST be preceded by a new PREREG file — the discipline recorded in the FINDING and in the STOPPED marker (which itself followed `PREREG_V09_C3_GRID_EXTENSION`), (c) a result that identifies a sink channel with an anchored rate constant and folds it into the 0-D chemistry would change the PIRT row if C3 and/or C4 then pass in a re-sealed run.

#### 5. WHAT NOT TO DO
Explicitly:
- No parameter tuned to force a PASS (the FINDING §5, line 123: "ni `F_N2A_BRANCH` ni sa fraction qualifiante ne se dimensionnent sur un écart gradé").
- No test or validation script weakened (the README line 22–23: "The gate windows are NOT widened here").
- No rerun without a prereg (the FINDING §5, line 125–127: no seal, bar, or Status moved; the STOPPED marker exists precisely to record that the operator chose to stop rather than seal).
- A FAIL that survives honest triage stays a FAIL in the note — the note does not resolve the 4/7 vs 5/7 discrepancy, it reports it.

### Ordered Steps for the Coder

1. **Read `docs/vv/PIRT.md`** lines 37–76 (the window around line 57). Cite line 57 for the 4/7 FAIL claim and its date context.
2. **Read `validation/09_ozone_saturation/README.md`** top to bottom (230 lines). Extract: status header (lines 3–11), the criteria table (lines 27–33), the history of rescoring (lines 8–11), and the explicit "gates NOT widened" declaration.
3. **Read `validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/summary.txt`** top to bottom (19 lines). Extract: the 5/7 score (line 4), the C2 pass details (lines 5–9), the C3 censure déplacée (line 13), the individual criterion list (line 12).
4. **Read `validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/comparison.txt`** top to bottom (58 lines). Extract: the three-channel physics (lines 5–12), the E/N sweep data and convergence guard (lines 14–37), the Shimizu comparison overestimates (lines 42–45), the per-criterion verdicts (lines 50–58).
5. **Read `validation/09_ozone_saturation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md`** top to bottom (148 lines). Extract: the arithmetic-probe methodology (lines 5–8), the C3 ceiling table (lines 59–63), the C4 ceiling table (lines 74–77), the key finding that the source is inside its band but the demanded yield is 2.27× below (lines 96–118), and what this document does not do (lines 120–134).
6. **Read `validation/09_ozone_saturation/CRITERIA_CODE_MAP_2026-08-08.md`** top to bottom (95 lines). Extract: the C1–C7 code coupling map (lines 9–29), the hinge between MCC sweep and chemistry (lines 33–38), the pre-registered replacement bars C7′ and C5′ (lines 43–94) for context on what future wiring would involve.
7. **Write `docs/vv/TRIAGE_V09_2026-08-24.md`** containing all five required sections, each with inline citations of the form `(file path, line N)` or `(file path, §section heading)`. No other file is created, edited, or opened for writing.
8. **Self-check:** verify via `glob` for `DONE.md` and the new triage note that no unexpected files were created; verify the note exists at the exact path with all five section headings.

### Targeted Tests the Gate Must Replay
The gate (`julia_gate`) will be invoked on the workspace. The note is documentation, not code — the existing test suite must pass:
- **`test/runtests.jl`** (or the incremental runner) must produce green (VERT). The note is passive documentation; no Julia code changes, so the suite's state is unchanged from before.
- **Gate verdict:** VERT on the workspace. VERT is the only green.

### Acceptance Criterion
`julia_gate` returns VERT. The file `docs/vv/TRIAGE_V09_2026-08-24.md` exists with all five sections: STATE, HISTORY, LAST CONCLUSION, SMALLEST NEXT PROBE, WHAT NOT TO DO. A self-check confirms no file other than `DONE.md` (created by the orchestrator) and the note was created or modified.

### Risks and What NOT to Touch
- **Do NOT resolve the 4/7 vs 5/7 discrepancy.** The PIRT says one thing, the STOPPED marker says another three days later. The note reports both with their dates; the coder must not attempt to determine which is "correct" — that would require re-running or re-grading, which is outside scope.
- **Do NOT read any file beyond the six listed.** The HARD READING BOUND is part of the contract.
- **Do NOT run Julia, invoke the GPU, or touch any `.jl` file.**
- **Do NOT glob for anything other than `DONE.md`** — no directory listings, no exploration.
- **Do NOT cite the CLAUDE.md system prompt or the AI-generated status block** — those are not in the evidence set.