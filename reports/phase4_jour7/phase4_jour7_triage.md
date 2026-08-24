# Triage V51 (BD-10) — 2026-08-24

Evidence base for this note: `PIRT.md`, `FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md`,
`PREREG_V51_A4_INPUTS_2026-08-12.md`, `FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md`.
Every claim below cites one of these four files by section and, where the plan fixes it,
by line. Later probe activity (case-directory artefacts, 2026-08-13 probe script) is out of
scope of this note's evidence and is not cited.

## §1 STATE

- PIRT row **BD-10** says V51 is **17/18 FAIL**, ref Kossyi 1992, "8-species ODE"
  (*PIRT.md*, line 309).
- The case was sealed **DOCUMENTED 17/18** under seal `5d975a83…` and moved to **FAIL 17/18**
  after the 2026-08-12 input audit under seal `e834bfcd…` — **same score, worse status**
  (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, lines 159-176).
- A4 reads **X(270 s) = 0.065847 (sealed) / 0.3589 (corrected)** against the bracket
  **[0.88, 0.99]** (*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §1, lines 20-27;
  *PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, line 166).

## §2 HISTORY

One line per dated event from the four files:

- **2026-08-11** — `FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md`: A4 measured as
  **FLUX-limited at the graded point** (ceiling worth 0.9%, §2); the seal's named route
  `R_ox` reaches **0.9372** with one free number (§5); §9 corrections withdraw "cannot"
  after RT finds `kri` ×1e3 at anchored flux lands **0.9097** (§10.1); §10.7 registers the
  input audit as the correct next step.
- **2026-08-12** — `PREREG_V51_A4_INPUTS_2026-08-12.md` (task #74 input audit): `film` and
  `MW` **wrong against Niemczyk 2021**; thickness worth **5.5×** (§0, §1); one-sided excuse
  test found and fixed (§1, §5); case **demoted DOCUMENTED → FAIL 17/18**, seal `e834bfcd`
  (§5); **9149/9149** suite replay clean (P7).
- **2026-08-12** — `FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md` (task #100):
  **γ\* = 23.47** on V49's typed n_e scaling (§3); this **BLOCKS task #101** (wiring `R_ox`
  into V51's neat path) because V49's calibration anchor and V51's A4 target are transcribed
  from **one sentence of one Niemczyk paper** (§4); three admissible routes given in
  preference order (§4).

## §3 LAST CONCLUSION

What the 2026-08-12 documents actually concluded:

- **Measured attribution:** A4 is "**flux-limited at the graded point**"
  (*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §2, §10.2). The corrected
  **X(270 s) = 0.3589** stays far below **[0.88, 0.99]**
  (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §5, line 166).
- **Input-audit outcome:** `film = 20 µm` and `MW = 250` were **wrong against the paper**;
  corrected to **0.4359 µm and 200.23** (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §0 table,
  lines 40-55). Worth **5.5× on X** — **did not rescue A4**. `freq` is CORRECT; `gap` is
  UNPUBLISHED and left labelled unanchored. The excuse test
  (`excuse_valid = A4_CEILING < A4_LO`) was **a constant that could not fail**; the
  two-sided replacement made the case FAIL (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §1
  lines 78-91, §5 lines 195-209).
- **Ordering:** The anchored route to the bar exists — V49's `R_ox(γ=1) = 2.8844e-4 1/s`,
  **γ\* = 23.47** — but wiring it is **BLOCKED**
  (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4, lines 71-107). V49's calibration
  anchor (`allyl_conversion_90s`) and V51's A4 target (`allyl_conversion_270s`) are the
  **same sentence of the same Niemczyk paper**, so wiring γ\*-scaled `R_ox` would make A4
  **circular** — a SHAPE test between two points of one paper wearing the label of an
  independent magnitude grade. Three routes in preference order:
  1. **anchor n_e independently first (#100)**, then derive `R_ox` and revisit A4;
  2. **wire γ\*-scaled R_ox and relabel A4 as shape/consistency** (costs the only
     independent magnitude grade);
  3. **leave A4 failing** (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4
     lines 97-107).

  V51 honestly sits at **route 3**, seal `e834bfcd`.

## §4 SMALLEST NEXT PROBE

**Route 1** from the record: **anchor n_e independently first** (task #100,
*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 lines 97-98, §6 lines 120-127),
then **derive `R_ox` from the anchored flux**, and **only then revisit A4 under a new
prereg**.

Prereg discipline: search for an **external same-class anchor** for a DBD at the Niemczyk
operating point (atmospheric Ar, ~10 kHz, 0.53–1.60 W·cm⁻²), register the n_e with stated
uncertainty, replace the typed prefactor, re-derive γ\*.

What result would change the PIRT row: if **γ moves toward 1** (the flux was low and the
corrected A4 rises toward the bar), or **stays ~23** (oxidation physics genuinely
missing) — both outcomes publishable and **neither tuned**
(*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §6).

A4 is then **run once afterwards, whatever it then reads**
(*FINDING_V51_A4_FLUX_LIMITED_2026-08-11.md*, §7, lines 241-244;
*PREREG_V51_A4_INPUTS_2026-08-12.md*, §4 fallback #1, lines 141-144).

## §5 WHAT NOT TO DO

Explicitly from the record:

- **"Choosing the wiring, the flux, or any R_ox scale because it lands A4 inside
  [0.88, 0.99]"** is refused in advance (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §3
  lines 232-234).
- **Wiring γ\*-scaled R_ox into A4's path** would create the same-sentence circularity
  (V49's calibration anchor and A4's target are transcribed from one sentence of one
  Niemczyk paper) and is **forbidden while γ\* is unexplained**
  (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 lines 79-92).
- **No test or validation script weakened** (*PREREG_V51_A4_INPUTS_2026-08-12.md*, §4
  fallback #6, lines 153-155).
- **No rerun without a new prereg.**
- **A FAIL that survives honest triage stays a FAIL** in the note
  (*FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md*, §4 route 3, lines 106-107).