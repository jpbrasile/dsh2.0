# TRIAGE — V09 Ozone Saturation (2026-08-24)

Triage note for validation case V09 (`validation/09_ozone_saturation/`). It records the
current state, the dated history, the last dated conclusion, the smallest honest next
probe, and the guardrails that bind the next operator. Every claim cites one of the six
evidence files by path and line or section. Nothing in this note resolves, re-grades, or
re-runs anything.

## 1. STATE

Two dated sources disagree on the score, and this note reports both without guessing
which is correct:

- The PIRT row says **V09 (4/7 FAIL)** (docs/vv/PIRT.md, line 57 — row PD-9, "Ozone
  chemistry (3-channel)", status as of that table's generation date).
- The last artifact that **regraded the criteria** — the stopped 2026-08-16
  grid-extension run — says **5/7 FAIL**
  (validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/summary.txt, line 4,
  "Score: 5/7"; verdict line:
  validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/comparison.txt, line 58,
  "VERDICT: FAIL (5/7)").
- **The discrepancy (4/7 vs 5/7) is reported, not resolved.** PIRT says 4/7; the
  2026-08-16 regrade says 5/7 three days after the 2026-08-09 re-seal. Determining which
  stands would require a re-run or a re-grade, which is out of scope for this note.

Per-criterion, the two sources agree that C1, C5, C6 and C7 pass and that C3 and C4
fail; they differ only on C2:

- **C2 — G_max window [5, 200] g/kWh.** On 2026-08-16: PASS at
  `199.71 ± 2.71` g/kWh mean over 5 seeded sweeps, margin +0.29 against the bar 200,
  se = 1.21 — i.e. within 2·se of the bar, and the artifact itself says this "carries
  no evidential weight — it is a frozen draw, not a measurement"
  (validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/comparison.txt, line 51;
  details: summary.txt, lines 5–9). Under the 2026-08-09 seal that PIRT's 4/7 reflects,
  C2 FAILS (docs/vv/PIRT.md, line 57;
  validation/09_ozone_saturation/README.md, lines 5–11 — current seal "C1✓ C2✗ C3✗ C4✗
  C5✓ C6✓ C7✓", C2 graded on the pre-registered mean of 5 seeded sweeps 202.51 ± 6.12 vs
  bar 200, margin −2.51).
- **C3 — E/N_eff window [100, 400] Td: FAIL in both sources**
  (comparison.txt, line 52 — `E/N_eff = 60 Td`, "BOUND — argmin at the domain floor,
  CENSURE DÉPLACÉE"; README.md, lines 19 and 32).
- **C4 — O₃ plateau ±50% of Shimizu (≥2/3): FAIL in both sources**
  (comparison.txt, line 53 — 0/3 within ±50%, errors 96% / 161% / 311%; README.md,
  lines 19 and 30, where the stale 2026-07-03-era table still shows C4 as the 2026-07-03
  reading; the 2026-08-16 regrade is FAIL 0/3, and the README header, lines 3–11, records
  the current seal as 4/7 with C4 ✗).
- **C1, C5, C6, C7 — PASS in both sources** (comparison.txt, lines 50, 54, 55, 56;
  README.md, lines 5–11 seal and lines 29, 31–33 for C7, C2, C3).

## 2. HISTORY

- **2026-07-03: 5/7.** The first corrected cross-section era: "History: 5/7 (2026-07-03)
  → 4/7 after the RNG-repair re-run (2026-08-06, KI-20) → re-sealed on the C2-redress
  script (2026-08-09)" (validation/09_ozone_saturation/README.md, lines 8–11; status
  header lines 3–11). The prior "7/7" rode on the old inflated-rotational / lumped N₂
  cross-section set and was retired in this same era (README.md, lines 13–25).
- **2026-08-06: 4/7 after the RNG-repair re-run (KI-20)** — the seeded-sweep discipline
  that makes C2 a pre-registered 5-seed statistic entered with this re-run (README.md,
  lines 8–10).
- **2026-08-09: re-sealed** on the C2-redress script, at 4/7, "documented physics, gates
  NOT widened" (README.md, lines 3, 9–10).
- **2026-08-16: grid-extension probe produced 5/7 — and the operator STOPPED rather than
  sealing.** The probe (deliverable (d) of the C3-grid chantier) extended the E/N grid
  and applied the convergence guard "≥ 400 events in BOTH channels for ALL 5 seeds",
  excluding 20/30/40/50 Td; C2 was regraded to PASS by the seeded-sweep prereg, C3 and
  C4 stayed FAIL (validation/09_ozone_saturation/STOPPED_C3GRID_FAIL5of7_2026-08-16/
  summary.txt, lines 3–5, 12, 14; comparison.txt, line 3 "Date: 2026-08-16T11:31:43.029",
  lines 34–37). The marker directory itself is the record of the decision to stop rather
  than seal that 5/7 (summary.txt, lines 3–4; the 2026-08-19 FINDING reaffirms the
  decision, see §3 below).
- **2026-08-19: arithmetic probe on the sealed sweep data — the most recent dated
  document.** `FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md`: "Aucun GPU, aucun run, aucun
  sceau touché: relecture arithmétique du balayage MCC scellé `results/v09_en_sweep.csv`"
  (validation/09_ozone_saturation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md, lines 1–8).
  It measured the maximum possible effect of the N₂-channel source lever on C3 and C4
  and proved it cannot turn either green (lines 9–30, 50–77).

## 3. LAST CONCLUSION

The 2026-08-19 FINDING is the most recent dated document, and its conclusion is
(validation/09_ozone_saturation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md, lines 96–118,
especially 109–118):

- At the case's calibration point (best-fit E/N = 60 Td, f = 1), the O-atom source
  **already sits inside its anchored band**: `[1.50, 8.00]` atoms/100 eV (Naidis via
  `probe_o_source_budget.jl`), actual **1.99** (lines 99–105).
- The O-atom efficiency **demanded by the Shimizu comparison** (G* = 11.81 g/kWh) is
  **0.66 atoms/100 eV — 2.27× below the bottom of that band** (lines 105, 112–115).
- Therefore **the missing factor cannot reside in the source lever**: even removing the
  N₂ channel entirely (f = 0) leaves C3 FAIL (E/N_eff pinned at the 60 Td floor, G =
  24.05) and C4 FAIL (1/3 of the three points inside ±50%, bar is ≥ 2)
  (lines 59–77).
- The designated direction is the **sinks of O₃ (or the sampling point)** — "jamais un
  coefficient de source à baisser" (lines 21–25, 115–118). This agrees independently
  with the conclusion of `FINDING_O_SOURCE_N2_CHANNEL` §3 (established there on V151 and
  "retrouvé ici indépendamment, sur les critères propres de V09", lines 116–118).
- The same document confirms the 2026-08-16 decision to stop rather than seal the 5/7:
  C2 sat at +0.29 margin for se = 1.21, and "la décision d'ARRÊTER plutôt que de
  sceller ce 5/7 reste la bonne, et ce document ne la rouvre pas" (lines 131–134).

## 4. SMALLEST NEXT PROBE

The 2026-08-19 FINDING (lines 127–130) names the next step: **identify the missing
O₃ sink**. It states explicitly that this "est un chantier séparé, avec son propre
préreg", that it touches **V151 / V82 / V87 / V106 (KI-28)**, and that it "ne se fait
pas en passant". Accordingly, the next probe is:

1. **(a) An O₃-sink budget audit — an arithmetic/measurement audit on sealed data, not
   a re-run and not a GPU job.** The probe methodology is already demonstrated: the
   2026-08-19 ceiling was measured by re-reading the sealed sweep
   (`results/v09_en_sweep.csv`) without any GPU time
   (FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md, lines 4–8).
2. **(b) It MUST be preceded by a new PREREG file.** The discipline is recorded in the
   FINDING itself (lines 128–129, "son propre préreg") and was exercised three days
   earlier: the 2026-08-16 grid-extension probe ran under
   `PREREG_V09_C3_GRID_EXTENSION` (summary.txt, lines 5–6 cite the C2-redress prereg
   §8 for the seeds; comparison.txt, line 34 names
   `PREREG_V09_C3_GRID_EXTENSION` for the convergence guard), and the operator's
   stop-rather-than-seal decision was recorded by the STOPPED marker (summary.txt,
   lines 3–4).
3. **(c) The promotion path is through a re-sealed run, not through the note.** A result
   that identifies a sink channel with an anchored rate constant and folds it into the
   0-D chemistry would be graded in the next re-sealed V09 run; only if C3 and/or C4
   then pass on their own bars would the PIRT row
   (docs/vv/PIRT.md, line 57) change. The mechanics of such a wiring are already mapped:
   any wired loss channel enters through the chemistry chain and moves C7 and C5
   together, under the pre-registered replacement bars C7′ and C5′
   (validation/09_ozone_saturation/CRITERIA_CODE_MAP_2026-08-08.md, lines 33–41 and
   lines 43–95; expected score after installation on the current physics: unchanged
   FAIL 4/7, lines 93–95).

## 5. WHAT NOT TO DO

- **No parameter tuned to force a PASS.** The source lever is priced as a ceiling, not a
  knob: "ni `F_N2A_BRANCH` ni sa fraction qualifiante ne se dimensionnent sur un écart
  gradé" (validation/09_ozone_saturation/FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md,
  line 123; the same trap was armed on 2026-08-15 in `FINDING_O_SOURCE_N2_CHANNEL` §5,
  lines 122–124).
- **No test or validation script weakened; the gates are not widened.** "The gate
  windows are NOT widened here (a gate change is a human decision) and the channel-3
  O-branch is NOT re-tuned to pass" (validation/09_ozone_saturation/README.md, lines
  22–23; status header line 3, "gates NOT widened").
- **No re-run without a prereg.** The FINDING moved nothing: "Il ne déplace aucun sceau,
  aucune barre, aucun `Status:`" (FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md, lines
  125–126). The 2026-08-16 5/7 was deliberately left UNSEALED — the STOPPED marker
  exists precisely to record that the operator chose to stop rather than seal
  (summary.txt, lines 3–4). Re-running before a new prereg reopens a decision two
  documents have already closed.
- **A FAIL that survives honest triage stays a FAIL in this note.** In particular this
  note does not resolve the 4/7 vs 5/7 discrepancy stated in §1: it reports both dates
  and both scores, and any reconciliation is the next operator's (or a future re-seal's)
  job, done under its own prereg.

---
*Scope of this note: documentation only. No code changed, no re-run, no re-seal, no
re-grade. Evidence set: the six files cited above (PIRT.md; the case README.md; the
STOPPED marker's summary.txt and comparison.txt; FINDING_C3_C4_SOURCE_CEILING_2026-08-19.md;
CRITERIA_CODE_MAP_2026-08-08.md).*
