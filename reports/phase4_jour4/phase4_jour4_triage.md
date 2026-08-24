# Triage — V44 H2S Removal, open PIRT FAIL (row PD-12, 14/25)

Date: 2026-08-24. This note triages the open PIRT FAIL at row PD-12 ("H2S removal
by DBD", V44 14/25 FAIL; `docs/vv/PIRT.md`, line 60 — evidence, not output; the
file is not touched). Every citation below resolves by line or section to one of
exactly five evidence files:

- `S` = `validation/44_h2s_removal/SEALED_N2VV_FAIL14of25_2026-08-09/summary.txt`
- `RS` = `validation/44_h2s_removal/SEALED_N2VV_FAIL14of25_2026-08-09/README_SEAL.md`
- `VS` = `validation/44_h2s_removal/VALIDATION_SUMMARY.md` (living copy, preserved
  2026-08-06)
- `VSA` = `validation/44_h2s_removal/SEALED_N2VV_FAIL14of25_2026-08-09/VALIDATION_SUMMARY_at_seal.md` (byte-identical forensics copy in the seal)
- `RT` = `validation/RT_GLM_V44_DECISION_2026-08-09.md`

---

## STATE

Seal dated **2026-08-09** (`RS`, line 3); the seal freezes the N2-V-V variant of
V44 as-is: pure N2 matrix, 100 ppm H2S, N2(v)->H2S V-V amplification mechanism
(eta_vib_diss = 0.03), signed script sha256 720372… (`RS`, lines 9–15).

- **Status FAIL, Score 14/25** (`S`, lines 3–4).
- **11 criteria fail**; the case's own verdict rule tolerates up to 2:
  `overall_pass = g_n_pass >= g_n_checks - 2`, "reproduced here exactly, not
  re-tuned" (`S`, line 5).
- Per sub-check (`S`, lines 6–30):
  - **PASS**: C1a (k_diss direct 2.324e-14 m3/s, line 6), C1b (line 7), C3 @ 10 J/L
    (eta 5.8% in [0, 40]%, line 9), C4 monotonicity (line 14), C5 energy cost at all
    five SEI points (lines 15–19), C6 product selectivity 56.3% (line 20), C8 @ 0.10
    (line 27), C9a (line 28), C9b (line 29), C10 (line 30).
  - **FAIL**: C2 F_VV = 35x vs the 50–2000x band (line 8); C3 at 30 / 50 / 100 / 200 J/L
    — eta 16.3 / 25.6 / 44.5 / 69.1% against admissible 25–70 / 45–90 / 70–100 /
    80–100% (lines 10–13); C7 k_VV sensitivity at 5.0e-19 / 1.0e-18 / 2.0e-18 m3/s —
    eta 44.2 / 44.5 / 44.7%, all outside 70–100% (lines 21–23); C8 eta_vib_diss
    sensitivity at 0.02 / 0.03 / 0.05 — eta 32.9 / 44.5 / 62.1%, F_VV 24 / 35 / 59x
    (lines 24–26).
- Only **1 of 5** eta points sits inside the experimental band (`S`, line 31).
- eta_vib_diss is "self-contradicting against Fridman (2008) Table 7.4", recorded open
  as task #22, "blocked: no local copy of the table" (`S`, line 32).
- The verdict is stable over **3 independent draws** on RTX 4090: 14/25 every time,
  F_VV 37/35/37x, none of the stochastic quantities near a bar — "the FAIL 14/25 is
  robust, not a draw" (`VS`, lines 59–101, especially the draw table at 68–72 and the
  stability statement at 74, 101; same text in `VSA`, lines 59–109).

## HISTORY

- **2026-02-17** — `results/summary.txt` and `results/comparison.txt` were written by a
  single documentary pass, commit `139fa0d7`, that "wrote 50 summaries and 50
  comparisons and executed nothing"; the case consequently "audited as DOC_STALE
  with no witness at all" (`VS`, lines 6–11; `VSA`, lines 6–11).
- **2026-07-04** — the date of the seal of the misleading hand-written header
  ("Score: 25/25 / Status: PASS", "all 5 SEI points", "F_VV ~ 300x"), which the
  script "HAS NEVER PRINTED"; the disagreement between file and run "dates to the
  seal of 2026-07-04" (`VS`, lines 32–39; `VSA`, lines 32–39).
- **2026-08-05** — header corrected 25/25 -> 14/25, "all 5 SEI" -> "1 of 5",
  "F_VV ~ 300x" -> F_VV = 37x BELOW the 50–2000x band; 3-draw stability measured on
  RTX 4090 (14/25 x3, F_VV 37/35/37); check9a identified as an identity (same closed
  form compared to itself), check9b/9c/9d shown to be arithmetic on hardcoded
  constants, never calling the solver; the eta_vib_diss sweep measured (only 0.10 in
  band) (`VS`, lines 20–101; `VSA`, lines 20–109).
- **2026-08-06** — `results/summary.txt` preserved "as it stood before 2026-08-06",
  the day `run_validation.jl` began writing that file itself (`VS`, lines 1–4;
  `VSA`, lines 1–4).
- **2026-08-07** — `run_validation.jl` signature timestamp 13:50:54, sha256
  720372b916827d6b0b9dc55058cc0986ec4387511fe5cd9257ffa1c93a2cadc5 (`RS`, lines 13–15).
- **2026-08-09** — acquisition established the citation VOID (Fridman 2008
  §7.4/Table 7.4 = "Direct Decomposition of Halides"; neither 0.03 nor 0.05–0.15
  has an anchor), the Zhao 2007 contradiction, and the C3 bar mis-attribution;
  **V44 sealed FAIL 14/25 as-is** (`RS`, lines 17–36). Red-team GLM-5.2 brief read
  at frozen commit 7658c85e: decision "A" (branch) reviewed — "Motivable et
  honnête", **Aucun BLOQUANT**, 12 numbered findings (5 majeurs, 7 mineurs)
  (`RT`, lines 4–6, 14–20, 26–54, 58).

## LAST CONCLUSION

The 2026-08-09 seal froze V44 **as-is, FAIL 14/25, closed and not "à réparer"**
(`RS`, lines 17–18), because three things were established:

1. **The mechanism's citation is VOID**: "Fridman (2008) §7.4/Table 7.4" is
   "Direct Decomposition of Halides" (CUP official TOC); neither 0.03 nor
   0.05–0.15 has any anchor (`RS`, lines 21–23).
2. **The mechanism is contradicted by the in-house primary source** (Zhao 2007,
   CES 62:2216: four candidate pathways, none vibrational; ionic pathways refuted
   by its own data) (`RS`, lines 24–27).
3. **The C3 bars are mis-attributed** (PMC11039977 = H2S in humidified AIR, not
   "100 ppm in N2"; Trenchev :87 attribution unverified) (`RS`, lines 28–29).

"Un cas dont le mécanisme n'a pas d'ancre et dont les barres n'ont pas de
provenance ne se « répare » pas en vert : il se scelle" (`RS`, lines 31–32). Any
successor is a **declared** "V44 rev2", whose score runs on a *different* set of
checks and is **not comparable to 14/25**; presenting a rev2 PASS as "le 14/25
réparé" is explicitly forbidden (`RS`, lines 33–36). The seal directory is
APPEND-ONLY (`RS`, line 45).

Red team (GLM-5.2): **no BLOQUANT** — the decision does not falsify identity and
fabricates no green; decision A holds ("la décision A tient — elle est
défendable et honnête", `RT`, line 58; line 26). Residual findings are
documentary-honesty issues, not verdict integrity: Abolentsev 1995 silently
dropped from gate (i) (finding 1), the undeclared OA/paywall asymmetry between
A and B sources (finding 2, also `RT` line 14), §6.1 closed by proxy with an
a-posteriori relevance reframe (finding 3), "grade archival" overstated versus the
actual archival state (finding 4), and the V80 provenance bounding underbounded —
grep-incidentel, four unanchored constants, not a KI-23 framing (finding 5).

## SMALLEST NEXT PROBE

The record itself names the cheap external probe twice. "THE CRITERION THAT
DECIDES FAIL VS DOCUMENTED IS THEREFORE EXTERNAL, AND CHEAP: open Fridman (2008)
Table 7.4 / section 7.4 and read which value the source supports for H2S"
(`VS`, lines 138–142); the sealed summary carries it as task #22, "blocked: no
local copy of the table" (`S`, line 32). Two branches, pre-declared:

- **§7.4 supports 0.05–0.15** → the shipped constant (0.03) misreads its own
  citation: the fix is a **sourcing correction, not a tuning** (`VS`, lines 141–142).
- **§7.4 supports 0.03** → the model's F_VV really is short: a **physics
  deficiency**, which is what keeps the PIRT Knowledge at (or below) M and
  reclassifies the gap as a *known limitation*, opening the DOCUMENTED tier for a
  successor note (`VS`, lines 140–141, 158–163; PIRT row PD-12 line 60:
  Validation Cases / Knowledge / Notes columns).

**Prereg discipline:** before opening the page, write a NEW prereg file (e.g.
`docs/vv/PREREG_V44_...md`) stating both branches and what each outcome changes in
PIRT row PD-12 (`docs/vv/PIRT.md`, line 60). No rerun, no re-sign, no parameter
move before the prereg exists and the page is read. This mirrors the record's own
warning: "Until someone reads it, neither branch is established — and that is
exactly why this stays FAIL rather than being promoted to DOCUMENTED: what is here
is an unreconciled citation, not a known limitation" (`VS`, lines 143–145).

## WHAT NOT TO DO

- **Never raise `eta_vib_diss` (or any vibrational-amplification parameter) toward
  the green band.** This is the documented double-fake-green: the parameter has no
  anchoring citation — the "[0.02, 0.15]" bracket "exists nowhere" and the case's
  own file cites the same source three times for three different answers (`VS`,
  lines 120–136; `RS`, line 23) — and 0.10 is the single value whose draw flips
  F_VV/eta into the green band: F_VV 118x, eta 85.3% (`S`, line 27); "The shipped
  default is 0.03. Choosing 0.10 because it is the value that makes the numbers
  agree is parameter tuning, whatever range it sits in" (`VS`, lines 111–118;
  `VSA`, lines 111–118). The unreachable false "stable" claim at `run_validation.jl:593`
  is armed for exactly that move (`VS`, lines 147–156). Tuning the parameter to
  pass fabricates both the parameter and the verdict.
- **No weakening, re-scoping, or label-shuffling of any test or validation
  check.** The verdict rule is "reproduced here exactly, not re-tuned" (`S`, line 5).
- **No rerun without a prereg; no re-hash of the seal to match a changed script.**
  The seal directory is append-only — "rien ne s'y modifie, rien ne s'y supprime"
  (`RS`, line 45).
- **Do not silently promote the verdict.** A FAIL that survives honest triage stays
  FAIL in this note: 14/25 = 56% is below the 75% PASS bar, and the gap is a
  deficiency, "not a documented limitation of the physics. Naming the mechanism is
  not the same as having established it. FAIL until someone does" (`VS`,
  lines 158–163).
- **Do not touch the seal directory** (append-only, `RS`, line 45), **`docs/vv/PIRT.md`**
  (row PD-12 at line 60 is evidence, not output), or any evidence file: `S`, `RS`,
  `VS`, `VSA`, `RT`.
- Any successor work is phrased as a **declared successor, not comparable to 14/25**
  (`RS`, lines 31–36) — never as "the 14/25 repaired".
