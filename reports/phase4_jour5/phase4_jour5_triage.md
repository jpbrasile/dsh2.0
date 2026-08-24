# TRIAGE — V49 / PIRT BD-1 (plasma-polymerization FRP kinetics)

**Triage date: 2026-08-24.** Evidence-cited note for the open PIRT FAIL **BD-1 / V49**.
Every claim below cites exactly one of the five sources listed in §0, as
`(path, line/section)`. No other file is cited as evidence.

**Sources (the only lines/locations this note may cite):**

| # | File |
|---|---|
| S1 | `docs/vv/PIRT.md` (line 301 — BD-1 row) |
| S2 | `validation/FINDING_V49_CORRECTED_INPUTS_2026-08-11.md` |
| S3 | `validation/FINDING_V49_DEPTH_AND_PHI_2026-08-11.md` |
| S4 | `validation/PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md` |
| S5 | `validation/FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md` |

---

## 1. STATE

**Both scores are reported, in parallel. This note does not pick one.**

- **V49 = 2/6 FAIL** — as stated in the PIRT row (`docs/vv/PIRT.md`, line 301:
  "V49 (2/6 **FAIL**) … **GUARD: Knowledge H not supported by evidence —
  V49=FAIL(2/6)**").
- **V49 = 3/6 (sealed) → 3/7 (sealed)** —
  - 3/6 with seal `18302730` recorded as the corrected-inputs demotion
    ("PASS 6/6 → FAIL 3/6", `FINDING_V49_CORRECTED_INPUTS_2026-08-11.md`, line 6);
  - 3/6 confirmed untouched by the depth-and-phi run ("V49 stays **FAIL 3/6**
    (seal `18302730`)", `FINDING_V49_DEPTH_AND_PHI_2026-08-11.md`, line 5);
  - 3/7 sealed on 2026-08-12 after the oxidation-channel repair ("Sealed
    **FAIL 3/7**, signature `4096f485…`", `PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md`,
    line 176ff; the prereg's own header opens on the predecessor state "Sealed
    **FAIL 3/6**, signature `18302730…`, signed 2026-08-11", line 5).

**The 2/6 vs 3/6 discrepancy is UNRESOLVED within the five files, and this note
flags it rather than reconciles it.**

- The PIRT row's "2/6" is not dated anywhere in the PIRT window read — the only
  occurrence is the whole-file row at line 301.
- The "3/6" is attested at two seals: `18302730` (2026-08-11) and, with the
  oxidation criterion added, `4096f485…` = 3/7 (2026-08-12).
- Any reconciliation — "the 2/6 is stale", "the 3/6 is an intermediate seal", or
  either other direction — would be inference beyond the five files. This note
  therefore reports **both**, marks the discrepancy **open**, and points the reader
  at the authoritative source that lies outside the citation bound:
  `validation/49_plasma_polymerization/results/summary.txt` (the case's own seal).
  That file is named here as the out-of-scope authority and is **not** cited.

---

## 2. HISTORY (chronological, one line per dated event)

- **(pre-row, 2026-08-07) — PASS 6/6, seal `d2a13600`.** Retro-cited origin,
  quoted by the corrected-inputs finding ("PASS 6/6 (seal `d2a13600`,
  2026-08-07) → FAIL 3/6 (seal `18302730`)", `FINDING_V49_CORRECTED_INPUTS_2026-08-11.md`,
  line 6).
- **2026-08-11 — corrected inputs.** MW 250→200.23 (HRMS), argon VUV yield
  (`ETA_VUV` 0.10 air → `ETA_VUV_ARGON` 0.30), EBP-derived film thickness band
  [0.138, 1.378] µm (`FINDING_V49_CORRECTED_INPUTS_2026-08-11.md`, lines 12–16).
  Result: **FAIL 3/6, seal `18302730`**; the thickness correction alone demoted the
  case, and it exposed a physics defect the inputs had been hiding
  (`...CORRECTED_INPUTS...md`, lines 1–6, 103–121).
- **2026-08-11 — depth-and-phi arm.** Depth lever **REFUTED** (radicals diffuse;
  "no photons at depth" ≠ "no conversion at depth", `FINDING_V49_DEPTH_AND_PHI_2026-08-11.md`,
  §1 lines 19–59); φ lever **real but a dial — NOT applicable** (bracket 50× wide,
  three criteria flip inside it, §3 lines 117–166); a **288.7× `SIGMA_UV` identity
  defect** found in `film_reaction_diffusion.jl` (measured 1.0e-18 vs derived
  3.4634e-21 m², §2 lines 61–103) — queued for V53, not corrected in V49.
- **2026-08-11 — real-inputs seal signed.** The corrected seal was signed
  2026-08-11 (`PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md`, line 6: "Sealed FAIL
  3/6, signature `18302730…`, signed 2026-08-11"), under predecessor prereg
  `PREREG_V49_REAL_INPUTS_2026-08-11.md` (named at line 6).
- **2026-08-12 — oxidation-channel prereg + run.** The case was re-wired onto the
  module written for the experiment (`cure_allyl_oligomer`), with the neutral
  oxidant flux (O + OH + O₃) routed to `R_ox` (`PREREG_...2026-08-12.md`, §2 lines
  103–116). Sealed **FAIL 3/7** (§6 lines 173–190): one criterion added that
  passes, one demoted — the pass COUNT did not move, and the document records it
  as such, not as an improvement. It names the next lever: **γ\* = 23.47 / `n_e`**
  (lines 241–251).
- **2026-08-12 — ne-scaling finding (this note's "last conclusion", §3).**
  `γ* = 23.47` is a verdict **on** the unanchored typed scaling
  `n_e = 1.0e16 * P` (`FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md`, lines 1–8,
  §3 lines 53–69), and the finding carries an ordering consequence: it **blocks
  task #101** (§4 lines 71–107).

---

## 3. LAST CONCLUSION (from `FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md`)

**γ\* = 23.47 is a verdict ON the single line `n_e = 1.0e16 * P`.** The codepoint is
`run_validation.jl:137-147` (the arm V49 grades; `...NE_SCALING...md` §1,
codepoint block lines 8–28): a typed scaling with no registry anchor. It is six
typed numbers, not one — the prefactor `1.0e16`, the linearity in P, and the four
ratios `n_O/n_e = 100`, `n_OH/n_e = 1`, `n_O3/n_e = 1000`, `n_ion/n_e = 0.1` — none
of which has a checkable citation (lines 26–28: `n_OH = n_e * 1.0` is a redundant
prefactor, "an unenforced degree of freedom wearing the syntax of a conversion").
Because the nominal flux is exactly that line, γ\* cannot currently distinguish
"the oxidation physics is missing a factor ~23" from "the typed flux is low by
~23" (e.g. `n_O/n_e` should be ~2300, or the prefactor 2.3e17, or the P-dependence
is not linear) (lines 60–69). It is "the C7 blind spot one layer down": the flux
scale error γ absorbs is invisible to C7, and γ\* is where that error went.

**The searched absence it records** (§2, lines 30–51): the `data/anchors/`
registry holds 7 anchors, but `grep -rln "kogelschatz\|cartry" --include=*.yaml`
returns **no anchor.yaml** — the two sources named in the codepoint comments are
registered nowhere. `data/experimental/bonding_debonding.json` carries the
Niemczyk conditions but no electron density (only `power_density_W_cm2`). The
`electron-density` keyword resolves to an *arc* electrical model
(`src__electrical_model__plasma_resistance`), not a DBD n_e(P) relation — not a
drop-in. The APPJ two-point anchor (~1e19 m⁻³ peak, order-of-magnitude ×3 gate) is
a streamer-head free-plume regime: its *method* (external same-class anchor,
order-of-magnitude band) is reusable, but its *number* is not. "A comment naming a
paper is a memory, not a citation the framework can check — the anchor registry is
what makes it checkable."

**The ordering consequence** (§4, lines 71–107): this finding **BLOCKS task #101**
(wiring V49's anchored `R_ox` into `evaluate_bonding`'s neat path to lift V51's
A4, 0.3589 against a 0.88 floor). With γ\* = 23.47, that wiring would turn A4 from
a held-out magnitude grade into a **calibrated/same-sentence circularity**: V49's
γ anchor (`allyl_conversion_90s`) and V51's A4 target (`allyl_conversion_270s`) are
transcribed from **one sentence of one Niemczyk paper** — the registry's own
`anchor.yaml:73` says "Same sentence as allyl_conversion_90s". A4 would become
"V49's C7: a SHAPE test between two points of one paper, wearing the label of an
independent magnitude grade". Three admissible routes, in preference order:
(1) anchor `n_e` independently first (task #100), then derive `R_ox` from the
anchored flux — the only route that can produce a genuinely held-out A4;
(2) wire γ\*-scaled `R_ox` but **relabel A4** as a shape/consistency grade, naming
the calibration path in the artefact (honest, but removes V51's only independent
magnitude grade of neat A6CC); (3) **leave A4 FAIL 17/18, seal `e834bfcd`** —
"where the case honestly sits until one of the other two lands".

---

## 4. SMALLEST NEXT PROBE

**Independently anchor `n_e`** (and the `n_O/n_e` ratio). Per
`FINDING_V49_NE_SCALING_UNANCHORED_2026-08-12.md` §6 (lines 120–127), the closing
measurement is an **external, same-class anchor for a DBD at the Niemczyk
operating point** — atmospheric Ar, ~10 kHz, 0.53–1.60 W·cm⁻² — giving n_e with a
stated uncertainty, plus either a measured or a mechanism-derived n_O/n_e.

**Prereq discipline:** a new PREREG file is committed **BEFORE any run or edit** —
"Written and committed BEFORE any edit" (`PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md`,
lines 1–3), and the record's own rule is explicit: "That is a **separate prereg
with its anchor fixed before the run**" (`PREREG_...2026-08-12.md`, lines 249–251).
(This note names the discipline, not an executed file; no prereg path is
registered as done.)

**What would change the PIRT row:** register the anchor, replace the typed
prefactor with the registry pull, re-derive γ\* — and record which way γ moves
(`...NE_SCALING...md` §6 lines 120–127): if γ moves toward 1, the flux was low
(physics only — the chemistry was right and the input wrong); if γ stays ~23, the
oxidation physics is genuinely missing. "Both outcomes are publishable and neither
is tuned."

**One rule of the probe:** the *absence* anchor must be **read to the page** —
never registered "as if" Kogelschatz published `1.0e16` without having read the
paper to the page; a filename is a memory, not a citation
(`...NE_SCALING...md` §5, lines 111–118).

---

## 5. WHAT NOT TO DO (the five mandated traps)

1. **Do not tune γ\*, the `n_e` scaling, or any input toward the green band.**
   γ near 1 is trivially available by dividing; choosing `n_e`, any ratio, or the
   P-exponent to make γ land near 1 would fabricate both the parameter and the
   verdict — "γ near 1 would be the *appearance* of a calibrated flux; … it would
   mean nothing. The anchor has to come from outside this case's data"
   (`...NE_SCALING...md` §5, lines 109–114). The prereg restates it in advance:
   "Choosing `n_e` so that `gamma` lands at 1 is exactly the fake-green this file
   exists to prevent, and is refused in advance" (`PREREG_...2026-08-12.md`, lines
   249–251).

2. **Do not weaken any test or validation script; do not launder the absence
   into a citation.** The unanchored prefactor must not be registered "as if"
   Kogelschatz published it without reading the paper to the page, and an
   order-of-magnitude statement ("atmospheric DBDs run ~1e16–1e17 m⁻³") anchors a
   magnitude but **no functional form** — it is no licence for the linearity in P
   or for the four ratios (`...NE_SCALING...md` §5, lines 111–118). Relabelling
   A4 instead of anchoring also costs a real grade — "Route 2 … *removes* V51's
   only independent magnitude grade of neat A6CC" (`...NE_SCALING...md` §4, lines
   94–107) — and the guard on the PIRT row must be respected as written
   (`docs/vv/PIRT.md`, line 301).

3. **Do not rerun without a new prereg.** The record's rule is that the prereg is
   "Written and committed **BEFORE any edit** to the case or to `src/`"
   (`PREREG_V49_OXIDATION_CHANNEL_2026-08-12.md`, lines 1–3), with the anchor fixed
   before the run (lines 249–251).

4. **Do not bypass the ordering consequence.** Task #101 is **NOT** to be executed
   with γ\*-scaled `R_ox`: wiring V49's anchored channel into `evaluate_bonding`'s
   neat path would convert A4 into a calibrated same-sentence circularity and the
   artefact "would not say so" — so "#101 as written cannot be executed honestly"
   until route 1 (anchor `n_e`, task #100) or route 2 (relabel A4) lands
   (`...NE_SCALING...md` §4, lines 71–107).

5. **Do not launder the verdict.** A FAIL that survives honest triage stays a FAIL
   in this note: V49 remains **FAIL**, with the 2/6-vs-3/6 discrepancy left
   unresolved (§1). The PIRT row's own GUARD is the standing form of this rule
   ("**GUARD: Knowledge H not supported by evidence — V49=FAIL(2/6)**",
   `docs/vv/PIRT.md`, line 301), and the next-probe outcomes are both publishable
   failures-of-the-hypothesis, not rescues: "Both outcomes are publishable and
   neither is tuned" (`...NE_SCALING...md` §6).

---

## Boundaries (what this note does and does not do)

- **Cites only the five files above**, as `(path, line/section)`. No sixth file, no
  CLAUDE.md status block, no `validation/validation_status.json` (a stale snapshot
  that must not be used as evidence for V49's score) is cited.
- **Names but does not cite** `validation/49_plasma_polymerization/results/summary.txt`
  as the authoritative, out-of-bounds source for the 2/6-vs-3/6 discrepancy.
- **Touches no other file**: `docs/vv/PIRT.md`, the five `validation/*.md` sources,
  any `run_validation.jl`, `src/bonding_debonding/*`, and every anchor YAML are
  unmodified by this triage.
- **Names no executed prereg**: the "new PREREG before the run" statement in §4 is a
  discipline statement only.