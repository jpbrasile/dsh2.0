Good. I have all four files read. Now let me construct the triage note.

Here is my plan:

---

## PLAN

**Goal:** Write `docs/vv/TRIAGE_V51_2026-08-24.md` — a five-section triage note for V51 (BD-10, 17/18 FAIL) that synthesizes the four evidence files into a single dated record with cited claims, an honest next-step, and explicit refusal of the known trapdoors.

### Files to touch (1)

1. **`docs/vv/TRIAGE_V51_2026-08-24.md`** — CREATE, a new triage note synthesizing the four evidence files into five required sections. No other file created or modified.

### Why

V51 is an open FAIL at 17/18. The four evidence files collectively document: (a) the flux-limited attribution of A4, (b) the 2026-08-12 input audit that demoted the case from DOCUMENTED to FAIL (same score), (c) the cross-case ordering consequence that blocks the obvious next wiring (γ* = 23.47 on V49's unanchored n_e scaling would make A4 circular). The triage note consolidates this into one document that an engineer can read without chasing four files.

### Ordered steps for the coder

1. **Read none of the evidence files** — the planner has already read all four and the plan contains all necessary citations. The coder reads NOTHING beyond PLAN.md (if it uses it) and writes the file from the plan's content.

2. **Create `docs/vv/TRIAGE_V51_2026-08-24.md`** via the `write` tool with the exact content specified below in the five sections. Every claim cites (file, line or section) from the four evidence files.

   The five sections:

   **§1 STATE** — Report: PIRT row BD-10 says V51 (17/18 FAIL), ref Kossyi 1992, "8-species ODE" (*PIRT.md*, line 309). The case was sealed DOCUMENTED 17/18 under seal `5d975a83…` and moved to FAIL 17/18 after the 2026-08-12 input audit under seal `e834bfcd…` — same score, worse status (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, lines 159-176). A4 reads X(270 s) = 0.065847 (sealed) / 0.3589 (corrected) against the bracket [0.88, 0.99] (*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §1, lines 20-27; *PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, line 166).

   **§2 HISTORY** — One line per dated event from the four files:
   - 2026-08-11: `FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md` — A4 measured as FLUX-limited at the graded point (ceiling worth 0.9%, §2); seal's named route `R_ox` reaches 0.9372 with one free number (§5); §9 corrections withdraw "cannot" after RT finds `kri` ×1e3 at anchored flux lands 0.9097 (§10.1); §10.7 registers input audit as correct next step.
   - 2026-08-12: `PREREG_V51_A4_INPUTS_2026-08-12.md` — task #74 input audit: `film` and `MW` wrong against Niemczyk 2021, thickness worth 5.5× (§0, §1); one-sided excuse test found and fixed (§1, §5); case demoted DOCUMENTED → FAIL 17/18, seal `e834bfcd` (§5); 9149/9149 suite replay clean (P7).
   - 2026-08-12: `FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md` — task #100: γ* = 23.47 on V49's typed n_e scaling (§3); this BLOCKS task #101 (wiring R_ox into V51's neat path) because V49's calibration anchor and V51's A4 target are transcribed from one sentence of one Niemczyk paper (§4); three admissible routes in preference order (§4).

   **§3 LAST CONCLUSION** — What the 2026-08-12 documents actually concluded:
   - **Measured attribution:** A4 is "flux-limited at the graded point" (*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §2, §10.2). The corrected X(270 s) = 0.3589 stays far below [0.88, 0.99] (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, line 166).
   - **Input-audit outcome:** `film = 20 µm` and `MW = 250` were wrong against the paper; corrected to 0.4359 µm and 200.23 (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §0 table, lines 40-55). Worth 5.5× on X — did not rescue A4. `freq` is CORRECT; `gap` is UNPUBLISHED and left labelled unanchored. The excuse test (`excuse_valid = A4_CEILING < A4_LO`) was a constant that could not fail; the two-sided replacement made the case FAIL (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §1 lines 78-91, §5 lines 195-209).
   - **Ordering:** The anchored route to the bar exists — V49's `R_ox(γ=1) = 2.8844e-4 1/s`, γ* = 23.47 — but wiring it is BLOCKED (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4, lines 71-107). V49's calibration anchor (`allyl_conversion_90s`) and V51's A4 target (`allyl_conversion_270s`) are the same sentence of the same Niemczyk paper, so wiring γ*-scaled R_ox would make A4 circular — a SHAPE test between two points of one paper wearing the label of an independent magnitude grade. Three routes in preference order: (1) anchor n_e independently first (#100), then derive R_ox and revisit A4; (2) wire γ*-scaled R_ox and relabel A4 as shape/consistency (costs the only independent magnitude grade); (3) leave A4 failing (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 lines 97-107). V51 honestly sits at route 3, seal `e834bfcd`.

   **§4 SMALLEST NEXT PROBE** — Route 1 from the record: anchor n_e independently first (task #100, *FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 lines 97-98, §6 lines 120-127), then derive R_ox from the anchored flux, and only then revisit A4 under a new prereg. The prereg discipline: search for an external same-class anchor for a DBD at the Niemczyk operating point (atmospheric Ar, ~10 kHz, 0.53–1.60 W·cm⁻²), register the n_e with stated uncertainty, replace the typed prefactor, re-derive γ*. What result would change the PIRT row: if γ moves toward 1 (the flux was low and the corrected A4 rises toward the bar), or stays ~23 (oxidation physics genuinely missing) — both outcomes publishable and neither tuned (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §6). A4 is then run once afterwards, whatever it then reads (*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §7, line 241-244; *PREREG_V51_A4_INPUTS_2026-08-12.md*, §4 fallback #1, lines 141-144).

   **§5 WHAT NOT TO DO** — Explicitly from the record:
   - "Choosing the wiring, the flux, or any R_ox scale because it lands A4 inside [0.88, 0.99]" is refused in advance (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §3 line 232-234).
   - Wiring γ*-scaled R_ox into A4's path would create the same-sentence circularity (V49's calibration anchor and A4's target are transcribed from one sentence of one Niemczyk paper) and is forbidden while γ* is unexplained (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 lines 79-92).
   - No test or validation script weakened (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §4 fallback #6, lines 153-155).
   - No rerun without a new prereg.
   - A FAIL that survives honest triage stays a FAIL in the note (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 route 3, lines 106-107).

3. **Invoke `julia_gate` on the workspace** after writing the file. By construction this is a documentation-only change — no `.jl` file is modified — so the gate reports ORANGE "rien a rejouer." Report its verdict VERBATIM in the final message.

4. **Self-check:** verify no file other than `DONE.md` and `docs/vv/TRIAGE_V51_2026-08-24.md` was created or modified. Use `glob` with pattern `*` to list all files, or rely on the gate's report. The coder may write `DONE.md` reporting completion; that is the only other new file permitted.

### Targeted tests

- **`julia_gate`** invoked on the workspace after writing the note. Expect ORANGE "rien a rejouer" since no `.jl` file changed. Any ROUGE or failed test is a failure.
- Acceptance criterion: the file exists at `docs/vv/TRIAGE_V51_2026-08-24.md` with all five sections, all claims cited to the four evidence files, and the gate verdict reported verbatim.

### Risks and what NOT to touch

- **Do NOT read any file beyond the four listed.** The coder should not read any evidence file — the plan contains all citations.
- **Do NOT read or cite** the out-of-bounds items: `validation/51_multi_monomer_chemistry/results/` (seal artefacts) or the 2026-08-13 probe script in the case directory. The note may mention "later probe activity out of scope of this note's evidence" if relevant but must not cite them.
- **No `.jl` file, no source file, no test file, no validation script may be touched.** This is a documentation-only triage note.
- The gate will return ORANGE — that is expected and CORRECT. Do not retry or attempt to fix it. Report it verbatim.
- The coder must not attempt to run Julia directly — only `julia_gate`.

---

That is the plan. The coder writes one file, invokes `julia_gate`, reports the verdict, and self-checks.