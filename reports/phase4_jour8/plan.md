Good — the file doesn't exist yet. Now let me produce the plan.

---

# PLAN: Write `docs/vv/TRIAGE_V72_2026-08-24.md`

## 1. Goal

Write a single triage note for V72 (chain UQ leave-one-out cross-validation, FAIL 6/7) that synthesises the six-evidence-file record into five required sections, flags the PIRT discordance without resolving it, and cites every claim by file path and line/section.

## 2. File to create

**`docs/vv/TRIAGE_V72_2026-08-24.md`** — one new file. Nothing else.

## 3. Content plan, section by section

### §1 STATE
- V72 is **FAIL 6/7** today, per the 2026-08-18 FINDING (`validation/72_chain_uq_crossval/FINDING_V72_C2_FOUR_CHANNELS_MEASURED_2026-08-18.md`, title + line 3-4: "V72 reste FAIL 6/7, scellé").
- Flag the PIRT discordance, with line numbers, NOT resolved:
  - **Row AD-4** (PIRT line 186): "V72 (6/7 **FAIL**)"
  - **Row AD-7** (PIRT line 189): "V72 (6/7 **FAIL**)" in the row vector, but Notes cell says "V72 7/7"
  - **Lines 202, 228, 251, 255**: all say "V72 (7/7 PASS)" or "7/7"
  - The discordance: row vectors say 6/7 FAIL; the Notes cell and every Context of Use section say 7/7 PASS. Flagged, not resolved, because the triage note is read-only and the PIRT is not to be edited.

### §2 HISTORY
One line per dated event, ordered as specified (by chantier/task number where dates tie):

| Order | Event | Source |
|-------|-------|--------|
| #57 | PASS 7/7 sealed at `e4a0f5de` | SEAL_ZHAO_ARMS_V72_FAIL, line 4 |
| #60 | Zhao 2024 arms folded in: FAIL 5/7 on 9 points | SEAL_ZHAO_ARMS_V72_FAIL, lines 1, 5, 48-62 |
| #62 | RT GLM-5.2 red team folded into instrument: 5/7 → 6/7 (C2 untouched, still failing) | SEAL_V72_RT_FOLD, lines 1, 5-6 |
| #64 | NMC convergence ladder: 6/7 → **5/7** (repair made score worse; C7 flips to FAIL at converged budget; seed-dependence gone) | SEAL_V72_NMC_CONVERGENCE, lines 1, 4-7, 78-89, 110-113 |
| #75 | LOOCV verdict: NOT repaired, unchanged FAIL 6/7; repair refutation + seal drift measured | VERDICT_V72_LOOCV, lines 1, 4-6, 10-21 |
| 2026-08-18 | Four-channels FINDING: FAIL 6/7 sealed; three channels dead, one alive (dose, 103 pp) with no anchored law | FINDING_V72_C2_FOUR_CHANNELS_MEASURED, lines 1, 127-132 |

Note on dating: SEAL_ZHAO_ARMS, SEAL_V72_RT_FOLD, and SEAL_V72_NMC_CONVERGENCE all carry date 2026-08-10; they are ordered by chantier number (#60, #62, #64) as the task specifies. VERDICT_V72_LOOCV is dated 2026-08-08 (task #75 — note that task #75 is dated earlier than chantiers #60/#62/#64 but the FINDING on 2026-08-08 already had the repair attempt and its refutation; flag that #75's date (2026-08-08) precedes #60/#62/#64 (2026-08-10) in calendar time even though the history ordering above follows the logical chain. The task says "order by chantier/task number where dates tie" — here dates do NOT all tie, so flag the chronological anomaly explicitly: VERDICT_V72_LOOCV (#75) is dated 2026-08-08, two days before the chantiers that moved the score. The history as presented follows the logical score trajectory. This is flagged, not resolved.

### §3 LAST CONCLUSION
Synthesise from FINDING_V72_C2_FOUR_CHANNELS_MEASURED, the last dated V72 document (2026-08-18):

- The two OUT points are not the same species: R1 at **3.3 pp** outside p5 vs Anyang2 at **28.7 pp** outside (FINDING lines 15-25).
- Three channels are dead by measurement: f_I (Anyang2 needs f_I ≈ 0.92, bracket ceiling is 0.870 — lines 100-116), OLR/loading (5.03 pp effect vs 95.9 pp measured gap, wrong direction — lines 74-98), dispersion (forbidden by case, dominated by flat prior anyway — lines 118-123).
- One channel is alive: **dose** at 103 pp span (lines 38-72). The data is present (`specific_energy_kJ_kgTS` in every Zhao arm), the leak rule licenses it (operating condition known before digestion — line 48-50), and the case still cannot use it because the only dose-response law in the repo is vacuous (synthetic schema-validation data, monotone-saturating form refuted by independent anchors Safavi 2017/2015, Szwarc 2021 — lines 54-66).
- The blocker is a **flat prior on `f_irrev` on a dose-response dataset** — 9 points all receiving `f_irrev ∈ [0.10, 0.80]` regardless of their measured specific energy (FINDING lines 127-132).
- "Aucune promotion de V72 n'est atteignable aujourd'hui sans desserrer" (FINDING line 128-129).

### §4 SMALLEST NEXT PROBE
What the record itself names as the missing piece (FINDING lines 68-72):

- An **independently anchored dose-response law for WAS**, with specific energy in kJ/kgTS, from a source independent of Choi and Zhao.
- This must be written as a new preregistration before any rerun.
- What would change the PIRT row: a law that maps `E_kJ_kgTS → f_irrev` anchored outside the case's own 9 points, admitted under the leak rule that already licensed VS/TS → f_I. If such a law exists and the dose channel (measured at 103 pp) separates the Zhao arms, Check 2 could reach 8/9.
- What would NOT change it: R1 at 3.3 pp has no anchored lever — the f_I bracket is constant for all three Choi arms (FINDING lines 31-36); Anyang2 at 28.7 pp is reachable only by a continuation that exits the anchored Ekama bracket and is refuted by its sibling arm Anyang1 (f_I > 1, impossible — FINDING lines 109-114).

### §5 WHAT NOT TO DO
From the record, explicit prohibitions:

- No bar, band, prior bound, physical parameter, or pinned seed moves (every seal: SEAL_ZHAO_ARMS §8 line 204; SEAL_V72_RT_FOLD §8 lines 191-198; SEAL_V72_NMC_CONVERGENCE §8 lines 144-153).
- No re-opening of Anyang2 — user decision of 2026-08-08, it stays OUT and still counts against coverage (SEAL_ZHAO_ARMS §8 lines 202-203).
- No choosing a dose law or prior BECAUSE it lands coverage above the bar — the seals' conflict-of-interest discipline (SEAL_ZHAO_ARMS §0 lines 11-14; SEAL_V72_RT_FOLD §0 pre-registration commitment).
- A converged-budget result that worsens the score is still the result (SEAL_V72_NMC_CONVERGENCE, title + lines 4-7, 110-113).
- No rerun without a new prereg (every seal; VERDICT_V72_LOOCV lines 258-259).
- A FAIL that survives honest triage stays a FAIL in the note (explicit in task instructions).

## 4. Ordered steps for the coder

1. **Write the file** `docs/vv/TRIAGE_V72_2026-08-24.md` with all five sections populated as above, each claim cited as `(file_path, line/section)`. The PIRT discordance is flagged with line numbers, not resolved. The history chronological anomaly (#75 dated 2026-08-08 before #60/#62/#64 dated 2026-08-10) is flagged, not resolved.

2. **Invoke `julia_gate` on the workspace** (no specific `.jl` file — a documentation-only change). The gate will report **ORANGE "rien a rejouer"** by construction. Report its verdict VERBATIM in the final message. A ROUGE or any failed test is a FAILURE — but the expectation is ORANGE, and ORANGE is acceptable because the change is documentation-only.

3. **Self-check**: confirm via glob that no file other than `docs/vv/TRIAGE_V72_2026-08-24.md` and DONE.md was created or modified.

## 5. Acceptance criteria

- File exists at exact path `docs/vv/TRIAGE_V72_2026-08-24.md` with all five sections (§1 STATE, §2 HISTORY, §3 LAST CONCLUSION, §4 SMALLEST NEXT PROBE, §5 WHAT NOT TO DO).
- Every claim is cited to one of the six evidence files by path and line/section.
- The PIRT discordance is flagged with line numbers, not resolved.
- The history date anomaly (VERDICT_V72_LOOCV 2026-08-08 vs chantiers 2026-08-10) is flagged, not resolved.
- `julia_gate` verdict reported verbatim.
- Self-check: only the note and DONE.md were created/modified.

## 6. Risks and what NOT to touch

- **Do NOT edit `docs/vv/PIRT.md`** — the discordance is flagged in the triage note, not resolved in the PIRT.
- **Do NOT read files outside the evidence set** — the five named out-of-bounds items (`PREREG_V72_*`, `PREREG_V73_V72_LYSIS_ROUTING`, `PREREG_ZHAO_FOLD_ARMS`, `PREREG_ORTIZ_FOLD_RECORD`, `FINDING_choi2006_provenance`) and everything in `validation/72_chain_uq_crossval/` beyond file 6 are named but never read.
- **Do NOT create or modify any file other than `docs/vv/TRIAGE_V72_2026-08-24.md`**.
- The note is a documentation-only artefact; `julia_gate` will find no `.jl` file to replay and will report ORANGE. That is the expected verdict — do not attempt to "fix" it.
- The PIRT says 7/7 PASS in five places against 6/7 FAIL in two row vectors. The discordance is real and documented. Do not attempt to determine which side is correct — that is the PIRT maintainer's job.