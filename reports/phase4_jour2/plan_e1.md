Now I have all the evidence I need. Let me compile the plan.

---

## PLAN

**Goal:** Write `docs/vv/TRIAGE_V09_2026-08-24.md` — a single triage note built from the repository record, with all five required sections, each claim cited by file path and line or section.

### Files the coder must read (exact paths, in this order):

1. `docs/vv/PIRT.md` — row PD-9 (lines 57 and 353)
2. `validation/09_ozone_saturation/results/summary.txt` — current sealed verdict (all 20 lines)
3. `validation/VERDICT_V09_C3_GRID_EXTENSION_2026-08-16.md` — newest verdict (all 102 lines)
4. `validation/VERDICT_V09_V10_V21_RNG_RERUN_2026-08-06.md` — earlier verdict (all 386 lines)
5. `validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/summary.txt` — stopped run's results (all 19 lines)
6. `validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/run_2026-08-16.log` — stopped run's log
7. `validation/PREREG_V09_V10_V21_RNG_RERUN_2026-08-06.md` — RNG rerun prereg
8. `validation/PREREG_V09_C2_REDRESS_2026-08-08.md` — C2 redress prereg (especially §§8-9 for the conclusion)
9. `validation/PREREG_V09_C3_GRID_EXTENSION_2026-08-08.md` — C3 grid extension prereg
10. `validation/PREREG_V09_C4_DECOMP_PROBE_2026-08-08.md` — C4 decomposition probe prereg
11. `validation/PREREG_V09_V21_NOX_CHANNEL_2026-08-08.md` — NOx channel prereg
12. `validation/PREREG_V09_C2_POINT_SEED_2026-08-16.md` — point-seed derivation prereg
13. `validation/09_ozone_saturation/FINDING_O_SOURCE_N2_CHANNEL_2026-08-15.md` — O-source finding
14. `validation/09_ozone_saturation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md` — source ceiling finding
15. `validation/09_ozone_saturation/PROBE_C4_DECOMP_RUN2_2026-08-08.txt` — C4 probe run
16. `validation/09_ozone_saturation/PROBE_C3_SOURCE_CEILING_RUN_2026-08-19.txt` — C3 source ceiling run

### The note — what goes in each section:

**1. STATE** — From `results/summary.txt` lines 3-4: Status: FAIL, Score: 4/7. Per-criterion vector from line 13: C1 PASS · C2 FAIL · C3 FAIL · C4 FAIL · C5 PASS · C6 PASS · C7 PASS. Date of evidence: the seal date attested in the file; the verdict doc dates to 2026-08-09 (re-seal on C2 redress). Cite the summary lines. Also cite PIRT row PD-9 (line 57) which shows V09 as 4/7 FAIL.

**2. HISTORY** — Five preregistered attempts in chronological order, each with one line citing the prereg and its verdict:

- **C2 redress** — `validation/PREREG_V09_C2_REDRESS_2026-08-08.md`, designed before execution under anti-rescue invariant (§3). Verdict: `validation/VERDICT_V09_V10_V21_RNG_RERUN_2026-08-06.md` (which preceded this prereg but whose data the redress consumed), then re-sealed FAIL 4/7 on 2026-08-09 per the prereg's §9 conclusion.
- **C3 grid extension** — `validation/PREREG_V09_C3_GRID_EXTENSION_2026-08-08.md`. Verdict: `validation/VERDICT_V09_C3_GRID_EXTENSION_2026-08-16.md` §1 — STOPPED at FAIL 5/7 (C2 flipped on a draw-indexing artifact), not re-sealed.
- **C4 decomposition probe** — `validation/PREREG_V09_C4_DECOMP_PROBE_2026-08-08.md`. Run1 VOID (guard failure), Run2 executed — `validation/09_ozone_saturation/PROBE_C4_DECOMP_RUN2_2026-08-08.txt`, arm H found level-closing at plausible η_c but probe did not grade anything (§7 of prereg: "this probe grades nothing and writes no sealed results").
- **NOx channel** — `validation/PREREG_V09_V21_NOX_CHANNEL_2026-08-08.md`. The prereg discovered that `nox_chemistry_3d.jl` already existed (§1bis of that prereg) and identified two wiring defects (one-way coupling, no vibrational NO source). No run was executed under this prereg — it was a design document.
- **RNG rerun** — `validation/PREREG_V09_V10_V21_RNG_RERUN_2026-08-06.md`. Verdict: `validation/VERDICT_V09_V10_V21_RNG_RERUN_2026-08-06.md` — the RNG change was undetectable (Welch t = −0.64 on C2), but the exercise revealed that C2 is a "coin-flip gate" whose bar falls inside its own noise band. V09 moved from 6/7 to 4/7 because the old seal rode on a lucky draw.

Note: the C2 point-seed prereg (`validation/PREREG_V09_C2_POINT_SEED_2026-08-16.md`) is owner-authorized but not yet executed — it is the next step, not part of the history.

**3. LAST CONCLUSION** — From `validation/VERDICT_V09_C3_GRID_EXTENSION_2026-08-16.md` §1: the stop rule fired because C2 flipped FAIL→PASS on a draw-indexing artifact (grid extension prepended 5 points, which advanced the global RNG stream and gave every legacy point fresh draws — a coupling the prereg didn't name). The flip mechanism (§2) is "NOT one of the two pre-declared pathways." The STOPPED marker at `validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/` is a dated, unsealed snapshot; the sealed `results/` was restored to FAIL 4/7. The document ends with three owner options (§5), the second of which (decouple the statistic from grid composition) has since been pre-registered as `PREREG_V09_C2_POINT_SEED_2026-08-16.md` but NOT yet executed.

**4. SMALLEST NEXT PROBE** — The record points to option 2 from `validation/VERDICT_V09_C3_GRID_EXTENSION_2026-08-16.md` §5, now pre-registered as `validation/PREREG_V09_C2_POINT_SEED_2026-08-16.md`. This is the single cheapest next measurement because:
- It costs ONE GPU run (the prereg is written, the owner decision is given per the prereg's header).
- It decouples C2's statistic from grid composition by deriving each point's seed from `(sweep_seed, E/N)` via SHA-256, making the draws invariant to grid edits.
- The prereg discipline is already followed: the prereg is written BEFORE the run (§5: "No stop rule this time — the human decision is already given").
- What result would change the PIRT row: if C2 stabilizes on either side of the bar and the run is re-sealed, the row changes from FAIL 4/7 to either FAIL 4/7 (if C2 draws FAIL again — unchanged) or FAIL 5/7 (if C2 draws PASS — formally closer but the summary itself warns the PASS carries no evidential weight). If the controls (R3-POS proving grid-composition invariance) pass, the measurement becomes credible regardless of which side C2 lands on.

However, `validation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md` has already priced the only unanchored degree of freedom in the source (the N₂ channel qualifying fraction) and shown it cannot move C3 or C4 (§§2-3: the entire channel removed still leaves C3 at 60 Td and C4 at 1/3). The honest next probe beyond the point-seed run is a PUITS-side measurement (destruction channels or sampling-point geometry), not another source-side perturbation.

**5. WHAT NOT TO DO** — Explicitly:
- No parameter tuned to force a PASS (cite `validation/PREREG_V09_C2_REDRESS_2026-08-08.md` §3: "Any moved bar, applied to the draws already on disk, must leave C2 FAIL" — the anti-rescue invariant).
- No test or validation script weakened (cite `validation/FINDING_O_SOURCE_N2_CHANNEL_2026-08-15.md` §5: "`F_N2A_BRANCH` ne doit jamais être réglé sur l'écart O₃" — the false-green trap, armed).
- No rerun without a prereg (cite `validation/VERDICT_V09_C3_GRID_EXTENSION_2026-08-16.md` §1: "no re-seal without an explicit human decision" — the stop rule).
- A FAIL that survives honest triage stays FAIL in the note — this is exactly what happened: C3 and C4 are physical FAILs that no lever within the model's honest domain can close (`validation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md` §0: "le levier 'source' de V09 est PRICÉ : il ne peut verdir ni C3 ni C4").
- No widening of the C3 bar [100, 400] Td — the prereg itself states "the C3 bar does NOT move" (`validation/PREREG_V09_C3_GRID_EXTENSION_2026-08-08.md` §0).

### Acceptance

- `julia_gate` verdict VERT on the workspace — the note is pure documentation, the existing test suite replays green since no source file, test file, validation script or result file is modified.
- The note exists at `docs/vv/TRIAGE_V09_2026-08-24.md` with all five sections.
- Self-check: only `DONE.md` and the new note were created or modified.

### Ordered steps for the coder:

1. Read all 16 files listed above.
2. Write `docs/vv/TRIAGE_V09_2026-08-24.md` with the five sections as specified.
3. Run `julia_gate` on the workspace — verify VERT.
4. Self-check: verify no file other than `DONE.md` and `docs/vv/TRIAGE_V09_2026-08-24.md` was created or modified.

### Risks and what NOT to touch:

- **Do not** modify `run_validation.jl`, any source file in `src/`, any test file, or any validation script.
- **Do not** modify any `results/` file or seal.
- **Do not** modify any existing VERDICT, PREREG, or FINDING file.
- **Do not** run or re-run V09 — the note is documentation only.
- The coder must NOT guess at any claim; every sentence must cite a file path and line/section from the repository record.