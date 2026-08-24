I have all evidence. No DONE.md exists yet (the orchestrator will create it). I have everything needed to write the plan.

---

# PLAN — Triage note `docs/vv/TRIAGE_V49_2026-08-24.md`

## 1. Goal (one sentence)

Write a single, evidence-cited triage note for the open PIRT FAIL **BD-1 / V49** (plasma-polymerization FRP kinetics) that states the current score, the dated history, the latest finding's conclusion, the smallest next probe, and the explicit "what-not-to-do" traps — touching no other file.

## 2. The file to create

**`docs/vv/TRIAGE_V49_2026-08-24.md`** (new; only file created). Five headed sections, every claim cited as `(file path, line/section)` against exactly these five sources — the only lines/locations the note may cite:

| File | Citable locations |
|---|---|
| `docs/vv/PIRT.md` | line 301 (BD-1 row) |
| `validation/FINDING_V49_CORRECTED_INPUTS_2026-08-11.md` | lines 1–184; notably line 6 (verdict + seal), §5 line 78ff (band), §6 line 103ff (defects), §7 line 172ff (duty-cycle anti-rescue) |
| `validation/FINDING_V49_DEPTH_AND_PHI_2026-08-11.md` | lines 1–201; notably line 5 (FAIL 3/6 seal `18302730`), §1 line 40ff (depth refuted), §2 line 61ff (288.7× σ defect), §3 line 117ff (φ = dial) |
| `validation/PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md` | lines 1–251; notably lines 4–5 (seal FAIL 3/6, signature, signed 2026-08-11), §0 line 14ff (two inert levers), §6 line 173ff (MEASURED 3/7), line 241ff (next lever γ*=23.47) |
| `validation/FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md` | lines 1–127; notably lines 8–28 (codepoint `n_e = 1.0e16*P`), §3 line 53ff (γ* verdict), §4 line 71ff (blocks #101; three routes), §5 line 109ff (refused), §6 line 120ff (what closes it) |

### Section-by-section content to write

**§1 STATE** — Report BOTH scores explicitly and in parallel, do not pick one:
- PIRT row says **V49 (2/6 FAIL)** (`docs/vv/PIRT.md`, line 301).
- The 2026-08-12 prereg opens "Sealed FAIL 3/6", signed 2026-08-11 (`PREREG_...2026-08-12.md`, line 5); the 2026-08-11 corrected-inputs finding likewise records "PASS 6/6 → FAIL 3/6" (`FINDING_V49_CORRECTED_INPUTS_2026-08-11.md`, line 6), and depth-and-phi confirms "V49 stays FAIL 3/6, seal `18302730`" (`FINDING_V49_DEPTH_AND_PHI_2026-08-11.md`, line 5).
- Attempt the resolution honestly: **flag as UNRESOLVED within the five files.** The row's "2/6" is not dated in the PIRT window read (only the whole-file row at line 301); the "3/6" is attested at two seals (`18302730` on 08-11, `4096f485…` = 3/7 on 08-12). State that asserting either reconciliation (e.g. "2/6 is stale" or "3/6 is an intermediate seal") would be inference beyond the five files, so the note reports both and marks the discrepancy open, pointing the reader at `validation/49_plasma_polymerization/results/summary.txt` as the authoritative source the note may NOT cite (out of bounds).

**§2 HISTORY** — one line per dated event, chronological:
- (pre-row) PASS 6/6 seal `d2a13600` 2026-08-07 (`FINDING_V49_CORRECTED_INPUTS_2026-08-11.md`, line 6) — retro-cited origin.
- 2026-08-11 — corrected inputs (MW 250→200.23, argon VUV yield, EBP thickness) → **FAIL 3/6** seal `18302730`; thickness masks a physics defect (`...CORRECTED_INPUTS...md`, lines 1–6, 103–121).
- 2026-08-11 — depth-and-phi: depth lever REFUTED, φ lever real but a dial (NOT applicable), 288.7× `SIGMA_UV` defect found (`FINDING_V49_DEPTH_AND_PHI_2026-08-11.md`, lines 1–5, 19–59, 117–166).
- 2026-08-11 — real-inputs seal signed (`PREREG_...2026-08-12.md`, line 6, predecessor `PREREG_V49_REAL_INPUTS_2026-08-11.md`).
- 2026-08-12 — oxidation-channel prereg: wires `R_ox` + `cure_allyl_oligomer`, seals **FAIL 3/7** (`...md`, lines 1–6, 173–190); names γ*=23.47 / `n_e` as the next lever (`...md`, lines 241–251).
- 2026-08-12 — ne-scaling finding: `γ* = 23.47` is a verdict on the unanchored typed scaling `n_e = 1.0e16 * P` (`FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md`, lines 1–8, 53–69, 71–107).

**§3 LAST CONCLUSION** — from `FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md`:
- **γ* = 23.47 is a verdict ON** the single line `n_e = 1.0e16 * P` (`:141` / codepoint lines 8–28, §3 lines 53–69): a typed scaling with no registry anchor; six typed numbers (prefactor, linearity in P, four ratios) none of which has a checkable citation.
- **Searched absence it records** (`§2`, lines 30–51): the `data/anchors/` registry holds 7 anchors but no `kogelschatz`/`cartry` anchor.yaml; `bonding_debonding.json` carries no electron density; the `electron-density` keyword resolves to an *arc* electrical model, not a DBD n_e(P); the APPJ anchor's *method* is reusable but its *number* is not.
- **ORDERING consequence** (`§4`, lines 71–107): it **BLOCKS task #101** (wiring V49's anchored `R_ox` into `evaluate_bonding` to lift V51's A4), because γ*-scaled wiring would turn A4 from a held-out magnitude grade into a calibrated/same-sentence circularity (both anchors transcribed from one sentence of one Niemczyk paper). Three routes, preference order — (1) anchor n_e first (task #100), (2) relabel A4 as shape grade, (3) leave A4 FAIL 17/18 seal `e834bfcd`.

**§4 SMALLEST NEXT PROBE** — the single cheapest measurement the record itself points to: **independently anchor `n_e`** (and the `n_O/n_e` ratio) — an external, same-class DBD anchor at the Niemczyk operating point (atmospheric Ar, ~10 kHz, 0.53–1.60 W·cm⁻²), per `FINDING_...NE_SCALING...md` §6 (lines 120–127). Prereq discipline: **a new PREREG file is committed BEFORE any run or edit** — named explicitly per the record's own rule ("That is a separate prereg with its anchor fixed before the run", `PREREG_...2026-08-12.md` lines 249–251). What would change the PIRT row: replacing the typed prefactor with a registry pull and re-deriving γ\* — if γ moves toward 1, the flux was low (physics only); if γ stays ~23, the oxidation physics is genuinely missing. The note must state that the *absence-anchor must be read to the page*, never registered "as if" published (`NE_SCALING...md` §5, lines 111–118).

**§5 WHAT NOT TO DO** — cover all five mandated traps explicitly with citations:
- Tuning γ\*, the `n_e` scaling, or any input toward the green band would fabricate both the parameter and the verdict (γ near 1 is trivially available by dividing; anchor must come from outside the case's data) — `NE_SCALING...md` §5 lines 109–114; `PREREG...md` lines 249–251.
- No test/validation script weakened; the unanchored prefactor must not be registered "as if" Kogelschatz published it, and an order-of-magnitude statement anchors a magnitude but no functional form — `NE_SCALING...md` §5 lines 111–118; §4 lines 94–107.
- No rerun without a new prereg — `PREREG...md` lines 1–3 ("Written and committed BEFORE any edit").
- The ordering consequence is respected: #101 is NOT bypassed; `evaluate_bonding`'s neat path is NOT wired with γ*-scaled `R_ox` — `NE_SCALING...md` §4 lines 71–107.
- A FAIL that survives honest triage stays a FAIL in the note (V49 remains FAIL, 2/6-vs-3/6 unresolved) — `PIRT.md` line 301 GUARD; `NE_SCALING...md` §6 "both outcomes are publishable and neither is tuned".

## 3. Ordered steps for the coder

1. Create `docs/vv/TRIAGE_V49_2026-08-24.md` with the five sections above; cite ONLY the five files, `(path, line/section)`.
2. In §1 report **both** 2/6 and 3/6 with their citations and mark the discrepancy **unresolved** (do not silently reconcile).
3. Self-check with `git status`: only the note and DONE.md may be added/modified.
4. Invoke `julia_gate` on the workspace; paste its verdict **verbatim** in the final message (expect ORANGE "rien a rejouer").

## 4. Targeted tests / acceptance

- **Test files replayed by the gate:** none (documentation-only change; no `.jl` path is replayed). This is by construction.
- **Acceptance criterion:** the gate reports **ORANGE** ("rien a rejouer") verbatim — a documentation-only change replays no Julia file. **Any ROUGE or any failed test = failure** (report it verbatim).
- **Self-check:** `git status` shows only `docs/vv/TRIAGE_V49_2026-08-24.md` and (orchestrator-owned) `DONE.md`; nothing else created or modified.

## 5. Risks & what NOT to touch

- **Do not** edit `docs/vv/PIRT.md`, any of the five `validation/*.md` files, any `run_validation.jl`, `src/bonding_debonding/*`, or any anchor YAML — the mandate is strictly one new note.
- **Do not** resolve the 2/6 vs 3/6 discrepancy by choosing one; flag it. Reading `validation/49_plasma_polymerization/results/summary.txt` (the authoritative case seal) is OUTSIDE the five-file bound and must not be cited; the note should name it as the out-of-scope authority but not quote it.
- **Do not** name a next prereg file path and then treat that as executed — it is a discipline statement only.
- **Do not** cite any sixth file, the CLAUDE.md status block, or `validation/validation_status.json` (the record explicitly warns it is a stale snapshot) as evidence for V49's score.

I am a read-only planner: I have not created any file. The coder must create the note and run `julia_gate`, reporting its verdict verbatim.