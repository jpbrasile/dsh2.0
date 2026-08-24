I have all evidence needed. Note that I'm the planner — I do NOT write files. My final message is the plan. Here it is.

---

# PLAN — Write `docs/vv/TRIAGE_V44_2026-08-24.md`

## 1. Goal
Create one documentation file, `docs/vv/TRIAGE_V44_2026-08-24.md`, a citation-complete triage note for the open PIRT FAIL at row PD-12 (V44 H2S removal, 14/25), citing only the five named evidence files, with all five required sections, leaving every other file untouched.

## 2. Files to touch
- **CREATE `docs/vv/TRIAGE_V44_2026-08-24.md`** — the only new file. Markdown, five sections (STATE / HISTORY / LAST CONCLUSION / SMALLEST NEXT PROBE / WHAT NOT TO DO). No other file created or modified. `DONE.md` (which the orchestrator will write) is the only other expected filesystem change.

## 3. Content plan, section by section (all claims cited as `path, line/section`)

**STATE** — from `validation/44_h2s_removal/SEALED_N2VV_FAIL14of25_2026-08-09/summary.txt`:
- Status FAIL, Score 14/25 (summary.txt, lines 3–4). 11 criteria fail; case's own rule tolerates ≤2 (`overall_pass = g_n_pass >= g_n_checks - 2`), summary.txt line 5.
- Which check passes/fails (name the sub-checks): C1a/C5/C6/C9a/C10 PASS; C2/C3 (30–200 J/L)/C7/C8(0.02–0.05) FAIL — map each to summary.txt lines 6–30.
- Evidence date: seal dated **2026-08-09** (README_SEAL.md line 3); verdict stable over 3 draws (README_SEAL.md lines 10–11; VALIDATION_SUMMARY.md lines 68–74, 101).

**HISTORY** — one line per dated event (cite the record's own dates):
- 2026-02-17: `results/summary.txt` + `comparison.txt` written by a documentary pass, commit `139fa0d7`, executed nothing → case later audited DOC_STALE (VALIDATION_SUMMARY.md lines 6–11).
- 2026-07-04 (in the record as the seal date of the misleading header): "Score 25/25/PASS" header dated to this seal; run has never printed those numbers (VALIDATION_SUMMARY.md lines 32–39).
- 2026-08-05: header corrected 25/25→14/25, "all 5 SEI"→"1 of 5", "F_VV~300x" corrected; F_VV=37x below the 50–2000x band; 3-draw stability measured on RTX 4090; check9a identity (VALIDATION_SUMMARY.md lines 20–109).
- 2026-08-06: this file preserved "as it stood before 2026-08-06" (VALIDATION_SUMMARY.md lines 1–4).
- 2026-08-07: `run_validation.jl` signature timestamp 13:50:54, sha256 720372… (README_SEAL.md lines 13–15).
- 2026-08-09: acquisition established citation VOID, Zhao 2007 contradiction, C3 bars mis-attributed → **sealed FAIL 14/25 as-is** (README_SEAL.md lines 17–36); red-team GLM-5.2 brief decision "A" reviewed, no BLOQUANT, 12 findings (RT_GLM_V44_DECISION_2026-08-09.md lines 26–54).

**LAST CONCLUSION** — the 2026-08-09 seal + red-team conclusion, quoted/tightly paraphrased:
- The seal froze V44 as FAIL 14/25 *as-is* because the mechanism's citation is **VOID** (Fridman 2008 §7.4/Table 7.4 is "Direct Decomposition of Halides"; neither 0.03 nor 0.05–0.15 has any anchor), the mechanism is contradicted by the in-house primary source (Zhao 2007), and the C3 bars are mis-attributed (README_SEAL.md lines 21–29). A case whose mechanism has no anchor and whose bars have no provenance is not "repaired" — it is sealed; any successor is a declared "V44 rev2" whose score is on *different* checks and is **not comparable to 14/25** (README_SEAL.md lines 31–36).
- Red team: decision A holds, no BLOQUANT, honest (no fake-green); residual findings are documentary-honesty issues (Abolentsev 1995 unsilently dropped, OA/paywall asymmetry, §6.1 closed by proxy, archival-grade overstate, V80 provenance underbounded) (RT_GLM docs, lines 14, 26–54, 58).

**SMALLEST NEXT PROBE**
- The record itself names the cheap external probe twice: **open Fridman (2008) Table 7.4 / §7.4 and read the value it supports for H₂S** (VALIDATION_SUMMARY.md lines 138–145, "THE CRITERION THAT DECIDES FAIL VS DOCUMENTED IS THEREFORE EXTERNAL, AND CHEAP"; summary.txt line 32 records it open as task #22 "blocked: no local copy of the table"). If §7.4 supports 0.05–0.15 the constant misreads its citation (a sourcing correction, not tuning); if it supports 0.03 the model's F_VV really is short (a physics deficiency — would flip PIRT Knowledge M→ lower / reclassify the gap as a *known limitation*, opening the DOCUMENTED tier).
- **Prereg discipline:** write a NEW PREREG file (e.g. `docs/vv/PREREG_V44_...md`) BEFORE opening the page, stating the two branches and what each outcome changes in the PIRT row PD-12 (Validation Cases / Knowledge / Notes columns at PIRT.md line 60). No rerun, no re-sign, no parameter move before the prereg is written and the page is read. This mirrors the record's own warning that the branch "stays FAIL rather than DOCUMENTED" until someone reads the source (VALIDATION_SUMMARY.md lines 143–145).

**WHAT NOT TO DO**
- **Never raise `η_vib_diss` (or any vibrational-amplification parameter) toward the green band.** It is the documented double-fake-green: the parameter has no anchoring citation (the "[0.02, 0.15]" bracket "exists nowhere"; three different answers cited to the same source — VALIDATION_SUMMARY.md lines 120–136; README_SEAL.md line 23), and 0.10 is the single value that flips F_VV/eta into the green band (VALIDATION_SUMMARY.md lines 111–118, 147–156; summary.txt line 27). Tuning it to pass fabricates both the parameter and the verdict.
- No weakening/label-shuffling of any test or validation check; summary.txt's verdict rule is "reproduced here exactly, not re-tuned" (summary.txt line 5).
- No rerun without a prereg; no re-hash of the seal to match a changed script.
- A FAIL that survives honest triage stays FAIL in this note — not silently promoted to DOCUMENTED (VALIDATION_SUMMARY.md lines 158–163).
- Do not touch the seal directory (append-only, README_SEAL.md line 45); do not edit PIRT.md or any evidence file.

## 4. Acceptance / targeted tests
- **julia_gate** must return **VERT** on the workspace: the note is pure documentation, so this reduces to "the existing test suite still replays green" plus the file-existence checks. The coder runs tests ONLY via `julia_gate`, never a shell `julia` command. No Julia test file is added by this task, so there is no new test to name — the gate's replay of the existing suite is the gate criterion. VERT is the only green; ORANGE/ROUGE means investigate, not retry blindly.
- **Note exists** at exactly `docs/vv/TRIAGE_V44_2026-08-24.md` with all five sections (STATE, HISTORY, LAST CONCLUSION, SMALLEST NEXT PROBE, WHAT NOT TO DO).
- **Self-check**: no file other than `DONE.md` and the note was created/modified.

## 5. Risks / do NOT touch
- Every citation must resolve to one of the five files, by line or section — no external reference, no `src/`, no additional reads (hard reading bound).
- Do not edit `docs/vv/PIRT.md` (row PD-12 line 60 is evidence, not output), the seal directory, `VALIDATION_SUMMARY.md`, `summary.txt`, `README_SEAL.md`, or `RT_GLM_V44_DECISION_2026-08-09.md`.
- The seal directory is append-only; the note must phrase any successor-work statement as "declared successor, not comparable to 14/25," never as "the 14/25 repaired."
- Ambiguity flag: the task's only ambiguity is whether an existing `DONE.md` may be read — it does not exist (glob returned none), so nothing to read; this does not change the plan.