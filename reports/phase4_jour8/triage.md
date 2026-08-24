# Triage — V72 chain UQ leave-one-out cross-validation, open PIRT FAIL (rows AD-4 / AD-7, 6/7)

Date: 2026-08-24. This note triages the open PIRT FAIL at rows AD-4 and AD-7
("PEF pretreatment coupling", "UQ chain (LHS + discrepancy)", both listing V72
6/7 **FAIL**; `docs/vv/PIRT.md`, lines 186 and 189 — evidence, not output; the
file is not touched). Every citation below resolves by line or section to one of
exactly six evidence files:

- `SZ` = `validation/SEAL_ZHAO_ARMS_V72_FAIL_2026-08-10.md`
- `SR` = `validation/SEAL_V72_RT_FOLD_2026-08-10.md`
- `SN` = `validation/SEAL_V72_NMC_CONVERGENCE_2026-08-10.md`
- `VL` = `validation/VERDICT_V72_LOOCV_2026-08-08.md`
- `FF` = `validation/72_chain_uq_crossval/FINDING_V72_C2_FOUR_CHANNELS_MEASURED_2026-08-18.md`
- `PIRT` = `docs/vv/PIRT.md` (cited for the discordance below; read-only)

---

## §1 STATE

- **V72 is FAIL 6/7 today**, per the 2026-08-18 FINDING, the last dated V72
  document: title + line 3 — "V72 reste `FAIL 6/7`, scellé" (`FF`, title, line 3).
- **PIRT discordance — flagged, NOT resolved.** The row vectors say FAIL 6/7;
  the Notes cell and every Context of Use section say 7/7 PASS:
  - **Row AD-4** (`PIRT`, line 186): "V72 (6/7 **FAIL**)" in the Validation
    Cases column.
  - **Row AD-7** (`PIRT`, line 189): Validation Cases column says "V72 (6/7
    **FAIL**)" but the Notes cell says "V71 12/12, **V72 7/7**".
  - **Line 202** (§5.1 AD-4 Context of Use): "**V72** (7/7 PASS, indirect support)".
  - **Line 228** (§5.2 AD-5 Context of Use): "**V72** (7/7 PASS, indirect support)".
  - **Line 251** (§5.3 AD-7 Context of Use): "**V72** (7/7 PASS): Chain UQ
    Leave-One-Out Cross-Validation".
  - **Line 255** (§5.3 Assessment notes): "V71 12/12, **V72 7/7**. ISS-2+ISS-3 resolved."
  - The discordance: two row vectors (lines 186, 189) say 6/7 FAIL; the Notes cell
    (line 189) and all Context of Use sections (lines 202, 228, 251, 255) say
    7/7 PASS. It is flagged, not resolved, because this note is read-only with
    respect to the PIRT and determining which side is correct is the PIRT
    maintainer's job.

## §2 HISTORY

One line per dated event, ordered by chantier/task number (three of the six
events carry the same date and are ordered by chantier number where the dates
tie):

| Order | Event | Source |
|-------|-------|--------|
| #57 | PASS 7/7 sealed at `e4a0f5de` | `SZ`, line 4 |
| #60 | Zhao 2024 dose-response arms folded in (fold set 5 → 9): PASS 7/7 → **FAIL 5/7**; two criteria fell — C2 coverage 7/9 = 77.8 % and C7 ablation | `SZ`, lines 1, 5, 48–62 |
| #62 | RT GLM-5.2 red team folded into the instrument: 5/7 → **6/7** (C7 reformulated in FORM — `t > −2` over five seeds — not in direction or bar; **Check 2 untouched and still failing**, so nothing in this fold could have rescued the case) | `SR`, lines 1, 5–6 |
| #64 | NMC convergence ladder: 6/7 → **5/7** — the repair made the score worse; seed-dependence gone, coverage confirmed 7/9 below the bar, and **C7 flips to FAIL at the converged budget** (`t = −2.35`); no bar, band, prior bound, physical parameter or pinned seed moved | `SN`, lines 1, 4–7, 78–89, 110–113 |
| #75 | LOOCV verdict: **NOT repaired, unchanged FAIL 6/7**; refutation of the repair the case's own FINDING prescribed (the `f_I` lever is dead on the batch path) + seal drift measured (`src` moved under a sealed case) | `VL`, lines 1, 4–6, 10–21 |
| 2026-08-18 | Four-channels FINDING: FAIL 6/7 sealed; the two OUT points are not the same species (R1 3.3 pp, Anyang2 28.7 pp); **three channels dead by measurement, one alive (dose, 103 pp) with no anchored law** | `FF`, lines 1, 127–132 |

**Date anomaly — flagged, NOT resolved.** `SZ`, `SR` and `SN` all carry the
date **2026-08-10** (each file's header: `SZ` line 3, `SR` line 3, `SN` line 3);
`VL` carries the date **2026-08-08** (file name; the repair-landed addendum
itself is dated 2026-08-08 at `VL` line 226). Task **#75** (`VL`) is therefore
dated **two days EARLIER** in calendar time than chantiers **#60 / #62 / #64**
(2026-08-10), even though the history ordering above follows the logical score
trajectory (7/7 → 5/7 → 6/7 → 5/7 → 6/7 → 6/7 sealed). The dates do not all tie,
so "order by chantier/task number where dates tie" does not by itself justify
the order presented; the anomaly is recorded here, not resolved.

## §3 LAST CONCLUSION

Synthesised from `FF` (2026-08-18), the last dated V72 document:

- **The two OUT points are not the same species:** Zhao R1 sits at **3.3 pp**
  outside p5 (measured +23.4, p5 = 26.7) while Choi Anyang2 sits at **28.7 pp**
  outside (measured +148.1, p95 = 119.4) (`FF`, lines 15–25). The author's own
  correction: the two points "ne sont pas de la même espèce et ne demandent pas
  la même réparation" (`FF`, lines 22–25).
- **Three channels are dead by measurement:**
  - **f_I** — Anyang2 would enter the interval at `f_I ≈ 0.92`, but the declared
    bracket ceiling is **0.870** (p95 = 138.8, short by 9.3 pp); 0.598 VS/TS is
    a true data edge of Ekama, not an implementation truncation (`FF`,
    lines 100–116).
  - **OLR / loading** — the model's effect across the three recorded Choi
    loadings is **5.03 pp** against a **95.9 pp** measured gap on the same arms,
    and in the **wrong direction** (model decreases with loading where the
    measurement peaks at the median arm); the mechanistic reason is that pH
    never leaves [6.98, 7.58], so the acid accumulation Choi invokes "ne
    s'enclenche jamais" (`FF`, lines 74–98).
  - **Dispersion** — forbidden by the case ("DOCUMENTED: Do NOT inflate
    discrepancy sigmas") and insufficient anyway: the discrepancy is one
    homoscedastic 9.25 pp Gaussian while the fold's predictive width is 84 pp —
    it is dominated by the flat prior on `f_irrev`, and even at s = 0 coverage
    stays 0.7778 (`FF`, lines 118–123).
- **One channel is alive: dose, at a 103 pp span.** ΔBMP moves from +15.4
  (`f_irrev` = 0.10) to +120.4 (0.80) = **103 pp**, against an 84 pp predictive
  width (`FF`, lines 38–72). The data is present — `specific_energy_kJ_kgTS` in
  every Zhao arm (`FF`, line 41–42) — the leak rule licenses it (operating
  condition recorded in the datapoint, known before digestion — the same
  argument that admitted the Ekama VS/TS prior — `FF`, lines 47–50), and the
  lever-check finds the field with **zero readers** in the repo (`FF`, lines
  45–46). Yet the case still cannot use it, because the only dose-response law
  in the repo is **vacuous** — its sole dataset is "Synthetic example for schema
  validation" — and its **monotone-saturating form is refuted** by the
  repo's own independent anchors: Safavi 2017 (interior optimum at 15 kWh/m³
  then methane declines), Safavi 2015 (methane below control at 32.4 / 48.7
  kWh/m³), Szwarc 2021 (Qe maximum at 4 min then −5.5 %) (`FF`, lines 54–66).
- **The blocker is a flat prior on `f_irrev` on a dose-response dataset:** all
  9 points receive `f_irrev ∈ [0.10, 0.80]` regardless of their measured
  specific energy ("un prior plat sur la dose sur un jeu de dose-réponse, avec
  la donnée présente, la règle de fuite qui la licencie, le canal mesuré à 103
  pp — et aucune loi ancrée pour la traduire") (`FF`, lines 127–132).
- **"Aucune promotion de V72 n'est atteignable aujourd'hui sans desserrer"**
  (`FF`, lines 128–129).

## §4 SMALLEST NEXT PROBE

What the record itself names as the missing piece (`FF`, lines 68–72):

- **An independently anchored dose-response law for WAS**, with specific energy
  in kJ/kgTS, from a source independent of Choi and Zhao: "C'est une cible
  d'acquisition nommée, pas un haussement d'épaules" (`FF`, lines 70–72).
- This must be written as a **new preregistration before any rerun** (the seal
  discipline cited in §5: no rerun without a prereg — `VL` lines 258–259).
- **What would change the PIRT row:** a law that maps `E_kJ_kgTS → f_irrev`,
  anchored outside the case's own 9 points, admitted under the leak rule that
  already licensed VS/TS → `f_I` (`FF`, lines 47–50). If such a law exists and
  the dose channel (measured at **103 pp**) separates the Zhao arms, Check 2
  could reach **8/9** — C2 demands 8 sur 9, and R1's remaining 3.3 pp is the
  only other miss (`FF`, lines 127, 15–18).
- **What would NOT change it:** R1 at 3.3 pp has **no anchored lever** — the
  `f_I` bracket is constant `triangular(0.786, 0.847, 0.870)` for all three
  Choi arms, so the covariate stops covarying exactly where they live (`FF`,
  lines 31–36). Anyang2 at 28.7 pp is reachable only by a **continuation**
  under the Ekama edge that exits the anchored bracket, and that continuation
  is **refuted by its sibling arm Anyang1** (`f_I > 1`, impossible),
  independently of what it does at Anyang2 (`FF`, lines 109–114).

## §5 WHAT NOT TO DO

From the record, explicit prohibitions:

- **No bar, band, prior bound, physical parameter or pinned seed moves.**
  Repeated in every seal: `SZ` §8, line 204 ("No bar, band, prior bound or
  physical parameter was changed in this chantier"); `SR` §8, lines 191–192
  ("No graded bar, band, prior bound or physical parameter was changed… the
  pinned seed is all exactly as they were"); `SN` §8, lines 144–146 (pinned
  seed still `UInt64(72)`; seed 75 forbidden in the pre-registration before any
  measurement). The NMC seal states it as a result, not an intention: "Same
  criteria, better-resolved evidence, **worse score**" (`SN`, lines 110–113).
- **No re-opening of Anyang2** — the user decision of 2026-08-08: it stays OUT
  and still counts against coverage (`SZ` §8, lines 202–203).
- **No choosing a dose law or prior BECAUSE it lands coverage above the
  bar** — the seals' conflict-of-interest discipline: the prereg's advance
  commitment "If V72 returns to FAIL, that is the result, and `e4a0f5de`'s
  PASS is superseded in the record, not quietly forgotten" (`SZ` §0,
  lines 11–16); the mirror-image commitment carried by `PREREG_ORTIZ_FOLD_RECORD`
  §4 as quoted there. The RT fold likewise pre-registered its C7 repair "in
  both directions before the sweep ran" because "a FAIL [on the board] is
  exactly the configuration in which I have an incentive to like the answer
  'it's noise'" (`SR` §77–79; `SZ` §5, lines 152–155).
- **A converged-budget result that worsens the score is still the result** —
  "FAIL 6/7 → FAIL 5/7" is the point of the seal, not its embarrassment (`SN`,
  title, lines 1, 4–7, 110–113).
- **No rerun without a new prereg** — `SR` line 4 ("Pre-registration… written
  before any run"); `SN` line 4 (same); `VL` lines 258–259 ("needs its OWN
  prereg before anyone touches it").
- **A FAIL that survives honest triage stays a FAIL in this note:** V72 remains
  **FAIL 6/7** (`FF`, line 3; `VL` lines 4, 259; `SR` line 198 "V72 remains
  FAIL"). The PIRT's five 7/7-PASS cells (lines 189 Notes, 202, 228, 251, 255)
  are the maintainer's to reconcile — this note cites them as the flagged
  discordance of §1 and asserts nothing from them.
