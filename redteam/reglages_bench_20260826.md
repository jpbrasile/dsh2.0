All evidence re-verified from source after the context break (files, line numbers, and every journal figure cited below were re-read, not carried over from summary). Report follows.

---

# RED TEAM — ranked findings

**Scale convention used below:** HIGH = the defect corrupts a number the campaign has already published or will publish, or the decision rule itself, in a known direction. MEDIUM = corrupts a secondary number or leaves a named accuracy variable untested. LOW = latent trap, no number wrong today.

---

## 1. HIGH — Pre-registered rule 3 ("truncated = non-measure, excluded and counted") is implemented nowhere. The scorer cannot even see one of the two truncation regimes.

**Severity meaning:** every accuracy figure published to date (68.7 %, 81.2 %, and both in-flight tournant arms) is a mixture of model error and measurement failure in unknown proportion — the exact mixture the pre-registration was written to prevent.

**Where:** `scripts/gpqa/depouiller_gpqa.py:59-63` and `:102-104`; `PRE_ENREGISTREMENT_BUDGET.md:69`; contrast `rendement_coupure.py:35,49`.

**Defect:** `par_question()` ingests every record without exception; `finish_reason == "length"` records are counted as wrong inside the grouped mean, and budget-cut calls (which the logbook itself proves never raise `length` — `DSH_QWEN_LOCAL_LOGBOOK.md:2289-2292`) are not identifiable by `depouiller_gpqa.py` at all, because only `rendement_coupure.py` looks for the MARQUE.

**Concrete failure:** illimité arm: 25 correct + 5 at the 16384 ceiling = 83.3 % raw per-call; the journal publishes **81.2 % ± 12.3 grouped** — arithmetically consistent *only* with the 5 ceiling calls being inside the grouped mean as wrong. That violates the pre-reg's own "exlu **et compté**" rule at `PRE_ENREGISTREMENT_BUDGET.md:2314-2316`, which also admits the promised 32768 catch-up ("rattrapage symétrique") is still owed and unrun. Worse case: the frozen 512 arm — 68.7 % ± 4.2 contains 7 `finish=length` calls *and* ~83 % of think blocks guillotined mid-sentence (`DSH_QWEN_LOCAL_LOGBOOK.md:1895,1898`) scored as ordinary wrongs; the pre-reg calls exactly those calls non-measures.

**Set instead:** implement rule 3 in the scorer — `moyenne_groupee` over records with `finish_reason != "length"` (and a MARQUE column parsed once at ingest), with truncated counts reported alongside, never inside, the score. Then recompute the two frozen arms before arm B finishes.

**Cheap test:** recompute 81.2 % with the 5 ceiling calls excluded per question: the number moves to ~83 %+ and the ± 12.3 shrinks; that delta *is* the size of the current violation.

---

## 2. HIGH — `--rotation-tournante` × rule 3: a truncated call now deletes the *whole question* from the paired comparison — non-randomly, concentrated on exactly the questions the lower budget destroys.

**Severity meaning:** the sweep's primary endpoint (A vs B paired on common questions) is selected on the treatment; the comparison will be run on the subset of questions 2048 can survive, biasing toward "non départagés".

**Where:** `gpqa_diamond.py:305` (one rotation per question), `:203` (carve-out re-runs length-truncated calls); `PRE_ENREGISTREMENT_BUDGET.md:69` (rule 3), `:154-162` (rules 7–8).

**Defect:** under 4 rotations a truncated call left three rotations of that question in the paired mean; under tournante it leaves zero — rule 3 exclusion drops the question from `comparer()`'s common set entirely, and truncation probability is a function of the question (hard questions burn more think tokens: illimité median 1111, p90 2695, max 4371 healthy vs 16384 failures, `DSH_QWEN_LOCAL_LOGBOOK.md:2232-2236`).

**Concrete failure:** at 2048, ~40–60 % of calls will eat the budget (p90 of healthy thinking is already 2695); arm A at 8192 cut 10/35 ≈ 29 %. The paired A−B difference is therefore computed on a 2048-survivor subset. Direction: suppresses the apparent cost of 2048 → feeds "non départagés" → rule "lowest budget wins" (`PRE_ENREGISTREMENT_BUDGET.md:75-76`). Note the revision bought nothing for this endpoint: Rev 0 (50 q × 4 rot = 200 calls) and Rev 1 (198 q × 1 call = 198 calls) have *identical* paired power — question-difficulty variance already cancels by pairing in both designs, and total draws are the same (~200); rule 8's own admission (per-question noise ×4) cancels the 4× question count exactly. The revision is power-neutral for A/B and strictly worse for dropout.

**Set instead:** either revert arm B to 4 rotations on the 50 Rev-0 questions, or keep tournante but change rule 3 for this sweep: a cut call is scored as wrong (kept in pairing) rather than excluded, and the exclusion rule applies only to `finish_reason == "length"` from the *output* ceiling, never to budget cuts. Publish both computations.

**Cheap test:** on the existing 35-call 8192 partial: count how many questions would lose their only draw if their cut call were excluded (10/35 ≈ 29 %). Then simulate at 2048's expected cut rate: ≥ 30 % of 198 questions drop out of `comparer()` — re-run the paired diff with cut-as-wrong vs cut-excluded and see if the sign flips.

---

## 3. HIGH — The pre-registered decision ladder can only ever select the lowest budget. That is the loophole.

**Severity meaning:** "choose the flattering threshold after the fact," re-institutionalized inside the pre-registration itself.

**Where:** `PRE_ENREGISTREMENT_BUDGET.md:73-80` (rule 5), `:75-76` (tie → lowest wins), `:154-157` (rule 7 strands all frozen comparators).

**Defect:** rule 5 discards an arm only if cut-call recovery falls to chance (25 %) — there is no floor *above* chance, no test statistic, and no minimum n; combined with the tie-break, a 2048 arm recovering at 40 % (vs 70 % free-thinking at 8192) passes every rung and wins.

**Concrete failure:** at n = 10 cut calls (arm A's measured 70 %), the fire threshold is decided by one or two answers: 7/10 vs 25 % gives z ≈ 3.3 (fires only below ~5/10); at full n ≈ 57 cut calls, recovery must fall under ~36 % to fire. Between 36 % and the healthy ~70 % lies an entire regime — "budget converts hard questions into degraded guesses that enter the score without signalling," their own words for what chance-level means (`rendement_coupure.py:71-73`) — that no rung of the ladder touches. Rule 7 then guarantees no external number (68.7 %, 81.2 %) can contradict the choice, and the final 198 × 4 publication run (rule 6) inherits it.

**Set instead:** add the missing rung, pre-stated: "an arm whose cut-call recovery is more than 15 points below its own free-call accuracy, with n_cut ≥ 30, is écarté." Fix the tie-break to "the budget whose *recovery-adjusted* score is highest," not "lowest."

**Cheap test:** none needed — this is arithmetic on rules already written; walk the ladder with hypothetical (recovery 45 %, paired loss 4 pts, n_cut = 80) and confirm every rung passes 2048.

---

## 4. MEDIUM — The χ² justification tests letter *preference*, which attenuates a position effect ~3×; "aucun biais détectable, ni de position" is unsupported by the test that was run.

**Severity meaning:** the protocol change of record rests on a statistic that could not have detected the position effect the data itself shows.

**Where:** `biais_position.py:44` (χ² on GIVEN letters only), `:58-66` (position effect only eyeballed), `:71-72` (MDE); `PRE_ENREGISTREMENT_BUDGET.md:107-114`.

**Defect:** given the measured per-position accuracies (r0 76.3 / r1 71.2 / r2 75.0 / r3 67.2, `DSH_QWEN_LOCAL_LOGBOOK.md:1793`), a *real* 9.1-point A−D position gap moves the given-letter distribution by only Δacc/3 ≈ 3 points per cell, because wrong guesses spread over three letters; the resulting χ² at n = 235 is ≈ 4n·Σδ² ≈ 0.5 — below their measured 2.02 and far below 7.81.

**Concrete failure:** the headline χ² values (4.16 / 2.02 / 0.31 at n = 285 / 235 / 128 — thresholds 7.81/11.34 for 3 df, correct) are consistent with "the full 9-point position effect we observed exists" and with "no effect" simultaneously. The pre-reg's own reserve (MDE ≈ 15 pts at n = 285; formula checks out: 1.96·√(2·0.7·0.3/71)·100 ≈ 15.1) concedes a 6-point effect is invisible — 6 points is the entire size of the budget effect being chased. And the journal over-claims anyway: "Du bruit. La rotation ne pénalise pas le modèle" (`DSH_QWEN_LOCAL_LOGBOOK.md:1794`) for a 9.1-pt spread at n ≈ 59/cell (± 5.7), i.e. ~1.1σ — "not separable" is the honest sentence; "does not penalize" is a positive claim their own MDE forbids. The 22.1 % A-given (`PRE_ENREGISTREMENT_BUDGET.md:127-128`) vs the 26.3 % the accuracy table predicts further shows a letter preference the χ² lumps in.

**Set instead:** test what you claim to test: paired-by-question position regression or Cochran's Q on the 4-rot data (cells are paired, so the naive two-cell MDE overstates the requirement); keep χ² for preference only, labelled as such.

**Cheap test:** recompute expected given-letters from the r0–r3 accuracies (formula above gives 26.3/24.6/25.9/23.3 %) and run their own `khi2()` on it: ≈ 0.5 at n = 235. One line of arithmetic demonstrating the test is blind to the observed effect.

---

## 5. MEDIUM — The transition message carries a literal `$LETTER`; an echo of it is a NON-PARSE counted as wrong — and echoes can only occur in the cut population, which is the population rule 5 reads.

**Severity meaning:** the recovery-rate criterion is contaminated by a formatting artifact with a known direction (downward).

**Where:** `message_transition.txt:1`; `_relance_budget8192_fils.ps1:14-16` (deliberately literal); `gpqa_diamond.py:59-63` (MOTIFS cannot match `$LETTER`), `:342` (non-parse ⇒ `juste: False`).

**Defect:** a model that obeys the injected instruction verbatim and ends with `Answer: $LETTER` matches none of the three MOTIFS — and the instruction *tells it to* finish with that line.

**Concrete failure:** one echo among 10 cut calls moves measured recovery 70 % → 60 %; at 2048 with n_cut ≈ 80, a 5 % echo rate silently costs 3.5 points of recovery. The sonde verified message presence and a structured answer (n = 1, no GPQA gabarit — `DSH_QWEN_LOCAL_LOGBOOK.md:2294-2295`), never the echo rate. Secondary `extraire()` traps on the same lines: unclosed `<think>` is not stripped (`gpqa_diamond.py:65` strips only closed blocks), so illimité ceiling calls can parse a bare letter line from *inside* surviving thinking via MOTIF[2]; "The correct answer is (C)" parses as None; observed non-parse rate on the 512 arm: 6/227 ≈ 2.6 % (`155/221 justes` at 227 calls, `DSH_QWEN_LOCAL_LOGBOOK.md:1781-1782`) — small overall, but the $LETTER term is concentrated where the decision is made.

**Set instead:** rewrite the tail of the message to a concrete imperative without a placeholder — "…and finish with the required last line stating your chosen letter" — or pre-substitute nothing and add a MOTIF[0] fallback that maps a literal `Answer: $LETTER` line to NON-PARSE-with-flag, reported separately from wrong answers.

**Cheap test:** replay `extraire()` over the 35-call 8192 partial, counting `donne == None` among MARQUE-bearing records (grep the MARQUE directly, `rendement_coupure.py:35`); then 20 sonde calls with the real GPQA gabarit at 2048. Cost: minutes, no GPU hours beyond the sonde.

---

## 6. MEDIUM — Temperature 1.0 against a vendor thinking-mode recommendation of 0.6: not a defect for any internal comparison, a defect for every absolute one.

**Severity meaning:** no published comparison is invalidated; the "89.2 published → ~70 ours" attribution and any future external contrast carry an untested −0 to −8 point setting delta.

**Where:** `lancer_bras_tournant.ps1:52` (`--temperature 1.0`); `gpqa_diamond.py:234` (harness *default* is 0.6 — a manual run silently differs); `start_llama_qwen38_27b_specdec.ps1:437` (server default 0.6); vendor 0.6/0.95/20/0 per your brief — **RECALL-ONLY, UNVERIFIED** (web off; not in repo).

**Defect:** all arms share t = 1.0, so A-vs-B, recovery, and dropout conclusions survive; but the one paired measurement in the repo — t = 1.0 74.6 % vs t = 0.6 79.2 %, −3.9 ± 3.7, z = −1.04, 105/128 identical responses (`DSH_QWEN_LOCAL_LOGBOOK.md:1786-1788`) — is non-separable, not null, and its point estimate is a third of the entire Q4-gap being investigated.

**Concrete failure:** the harness default (0.6) and the launcher value (1.0) disagree; anyone reproducing "the local GPQA number" with a bare `python gpqa_diamond.py` gets a different regime than every frozen file, with nothing in the JSONL recording temperature (enreg carries `modele` only, `gpqa_diamond.py:321-324`).

**Set instead:** either adopt 0.6 for all *future* absolute-facing arms (accepting the break with frozen t = 1.0 files, declaring it), or keep 1.0 everywhere and write the temperature into every JSONL record so the trap is at least visible.

**Cheap test:** none new — the 128-call paired comparison already exists; what is missing is only the decision, and the record field is a two-line patch.

---

## 7. MEDIUM — `reponse[-24000:]` is still too short for the arm it was raised for: a budget-cut call at 8192 has ≈ 8228 think tokens ≈ 24.7 k chars *plus* the answer, so the stored think block is headless.

**Severity meaning:** the analysis layer of the campaign's most interesting population (what the model was doing when the guillotine fell) runs on truncated data, and one classification path silently miscounts.

**Where:** `gpqa_diamond.py:355` (tail store, comment "24000 caractères couvrent ~8000 jetons"), `:348-354` (the 4000→24000 fix and its rationale); `rendement_coupure.py:44-49` (thinks parsed from the stored tail); sonde: think cut at 8228 tokens (`DSH_QWEN_LOCAL_LOGBOOK.md:2283`).

**Defect:** 24000 chars ≈ 8000 tokens (their own 3 chars/token calibration, `DSH_QWEN_LOCAL_LOGBOOK.md:1920-1922`) < 8228 think + answer body — so the opening `<think>` is cut off, the regex at `rendement_coupure.py:44` falls to the `split("</think>")` branch, and the *token count* of the pensee is computed on a fragment.

**Concrete failure:** a cut call with a 3000-char answer keeps ~21 k chars ≈ 7000 tokens of think → measured 7000 < SEUIL 7800; it is classified cut only because the MARQUE survives at the end of the think block. Drop the MARQUE (message flag lost in a relaunch) and the same call classifies as free. Likewise `distribution_pensee.py` medians on the 8192 arm are biased low for exactly the cut subpopulation. And a call whose `texte` was empty stores `reponse = ""` (`gpqa_diamond.py:355` stores `(rep["texte"] or "")` even though `extraire` at `:339` falls back to `raisonnement`) — the MARQUE is then gone entirely.

**Set instead:** store the pensee separately and whole: keep `reponse` as tail if you must, but add `"pensee_taille": n_tokens` and `"marque": bool` computed server-side at write time (the `/tokenize` round-trip already exists in `rendement_coupure.py:25-32`), or raise the tail to 40000.

**Cheap test:** over the 35-call partial, count records where `"</think>" in reponse` but `"<think>" not in reponse` — each one is a headless think the current analysis layer cannot see whole.

---

## 8. MEDIUM — Server config: two accuracy-relevant variables (KV q4_0 value cache, speculative-decoding distribution preservation) are unverified, and ctx 163840 *forces* the quantized KV on a 2 k-prompt benchmark.

**Severity meaning:** the unexplained 89.2 → ~70 gap is explicitly left "Q4 + protocole" undecomposed (`DSH_QWEN_LOCAL_LOGBOOK.md:1813-1818`), while a setting that plausibly lives inside that gap sits unvaried in every arm.

**Where:** `_relance_budget8192_fils.ps1:21-22` (`-CtxSize 163840 -Ctk q8_0 -Ctv q4_0`), `:20` (build-faq binary); `start_llama_qwen38_27b_specdec.ps1:94-98` vs `:428-429` — **docstring says empty `-Ctk` defaults to hardcoded q8_0; the code defaults to f16**; `:421-425` (their own 60× prefill / 12.7 t/s collapse warning, advisory only); `:435-440` (sampler and `--reasoning-format none`); `DSH_QWEN_LOCAL_LOGBOOK.md:1814-1816` ("censé préserver la distribution… à vérifier, pas à supposer").

**Defect:** for GPQA's ~250-token prompts (`DSH_QWEN_LOCAL_LOGBOOK.md:2050-2051`), a 163840 ctx buys nothing and costs the f16 KV (their own numbers: f16 fits at 32 k for +674 MiB; quantization was chosen to buy VRAM, and per their sweep note raising ctx does not slow a short request — so the only thing the big ctx does on this bench is *require* the quantized cache); spec-dec distribution preservation — the property that makes the benchmark's sampling meaningful — is assumed, and losslessness of the dflash2 draft on this nightly build is taken via `-AssumeDflash2Capable` (`start_llama_qwen38_27b_specdec.ps1:118-123`), an explicitly named expert override.

**Concrete failure:** any of these three alone could be worth the missing points; none was ever varied; all are constant across arms, so they cancel in A-vs-B and concentrate entirely in the absolute number the campaign ultimately publishes. The docstring/code KV mismatch additionally means the next person who reads the header and omits `-Ctk` gets f16, silently changing the regime from every frozen file.

**Set instead:** for the GPQA server only: `-CtxSize 32768 -Ctk f16 -Ctv f16` (fits: 19.2 GiB measured), spec-dec off or verified once against greedy (same seed, n = 20, diff outputs); fix the docstring at `:94-98` to match the code.

**Cheap test:** 30 questions × 2 configs (f16 KV vs q8_0/q4_0), same seed, paired — ~1 h of 4090; and one greedy-off vs greedy-on specdec diff at fixed seed. If either moves the score ≥ 3 pts, it decomposes the 89.2 → ~70 gap more than the entire budget sweep can.

---

## 9. MEDIUM — Coding bench: the 1800 s wall is recorded as FAIL by the instrument; "NON-MESURE" exists only in prose. And the wall sits 20 % above the slowest passing exercise.

**Severity meaning:** the pilot's own headline statistic ("N joues, M passes") counts censorship as model failure — the same class of mixture as finding 1, on the other benchmark.

**Where:** `pilote.py:599-600` (coupe counted), `:612-626` (tests judged on the partial tree after the kill), `:1001` + `:1010-1011` (summary uses `tests_outcomes[-1]`; `tours_coupes` never enters the tally); `DSH_QWEN_LOCAL_LOGBOOK.md:2216-2222` (beer-song 1800.3 s, `coupe: True`, `sortie_queue` vide — called non-mesure in the journal only), `:2222` ("la marge avant le mur était de 20 %"), `:2224` (book-store PASS at 1434.0 s); convention implemented only in `lire_resultat_agent.py`.

**Defect:** `un_exercice` judges whatever partial state the killed agent left and appends it to `tests_outcomes`; with `--tours 1` there is no later turn to overwrite it, so a censored turn is indistinguishable from a wrong solution in every downstream count.

**Concrete failure:** one beer-song kill at 1800.3 s lands as FAIL in "N joues, M passes" while the journal calls it a non-measure — the two documents disagree about the same run. And the wall is itself a confound, not just a censor: book-store spent 72 % of its time in the LLM with one 511.3 s call burning 10 095 reasoning tokens (`DSH_QWEN_LOCAL_LOGBOOK.md:2009-2014`); a wall at 1800 measures the model's verbosity budget as much as its coding, and it does so *differently per variant* — variant D's declared handicap (write your own tests first, cpp/java 73/225 exercises) inflates exactly the time the wall then cuts. On the narrower question — does variant D measure what it claims — the machinery holds (stash/restore verified, `@Disabled` removal and JUnit-XML count check are the correct gestures, `juge_claude.py:70-124`), and `--tours 1` is a genuine validity fix for the tour-2 leak at `pilote.py:637`; the un-mitigated cost of `--tours 1` is that a flaky Gradle/docker hiccup (their own 26/08 six-exercise incident, `pilote.py:629-633`) is now a permanent FAIL with no second chance.

**Set instead:** make the outcome a triple — PASS / FAIL / NON-MESURE with `tours_coupes > 0` ⇒ NON-MESURE — written by `pilote.py` itself; raise the wall to 3600 (2× slowest PASS) for any run whose numbers will be published; keep `--tours 1`.

**Cheap test:** rerun beer-song once at 3600 s; then recompute the pilot summary with the triple outcome over the existing cas durs and see how many FAILs become NON-MESUREs — that count is the current bias in the headline rate.

---

## 10. MEDIUM — Effort probe: n = 1 per cell, temperature 1.0, and the serving provider is not recorded — a direct violation of the repo's own per-line provider rule.

**Severity meaning:** "reasoning_effort is honoured" (4787 → 870, factor 5.5, `DSH_QWEN_LOCAL_LOGBOOK.md:2196`) may be a routing observation rather than a flag observation.

**Where:** `test_effort_openrouter.py:61` (t = 1.0, single basket question), `:88-93` (four cells, one call each), no `provider` printed anywhere in `appel()`; the rule it violates: `gpqa_diamond.py:155-159` ("épingler un fournisseur dans la requête ne prouve rien, seule la réponse le prouve").

**Defect:** OpenRouter can route `qwen/qwen3.8-27b` to different providers per request; reasoning-token accounting differs per provider (the probe's own row 4 proves the field itself is provider-shaped: native form reports `reasoning_tokens: 0` on 2766 output tokens, `DSH_QWEN_LOCAL_LOGBOOK.md:2201-2204`).

**Concrete failure:** the low (1307) > medium (870) inversion at n = 1 is acknowledged as noise (`DSH_QWEN_LOCAL_LOGBOOK.md:2198-2200`) — which concedes the per-cell noise scale is ≥ the medium effect; the headline 4787-vs-870 gap is 5.5×, probably real, but a single provider switch between two calls would produce the same table. The operational conclusion drawn from it ("medium est appliqué et reste insuffisant", `:2207`) drives the bench's effort setting for a projected ~64 $ / ~90 h run with 13.95 $ of credit (`:2040-2041`).

**Set instead:** 5 calls per cell, temperature 0.6 (determinism of the *observable* matters more than matching the bench's t), print and pin `provider` from each response, and treat cells with mixed providers as unmeasured.

**Cheap test:** 5×4 calls ≈ 8 $-cents-scale cost at their measured prices (0.004–0.015 $ per call) — under 0.30 $ total.

---

## 11. LOW — The live-server budget check is a prefix match: `--reasoning-budget 2048` validates a server running 20480.

**Where:** `lancer_bras_tournant.ps1:35` — `$argv -notmatch ("--reasoning-budget\s+" + [regex]::Escape("$Budget"))`, unanchored on the right.

**Defect:** 2048 matches the first four digits of 20480 (same for 8192 ⊂ 81920), so the arm-B gate can pass against a wrong-budget server — the exact failure mode the gate exists for (the silent-survivor incident of 26/08 13:37, `lancer_bras_tournant.ps1:30-32`).

**Set instead:** `"--reasoning-budget\s+{0}(\s|$)" -f $Budget`. **Test:** run with a server at 20480 once; the gate must refuse.

---

## 12. LOW — Three small traps, no number wrong today.

- `biais_position.py:41` conditions the *position* table on `donne` — accuracy-by-expected-letter is computed only over parsed calls; if parse failure is itself position-dependent (finding 5's `$LETTER` echo), the position audit is selected on a post-treatment. Set: report position table over all calls with non-parses as their own row.
- `depouiller_gpqa.py:125` — header "4 rotations => ~25 % attendus par lettre" is stale for tournant files (where it happens to still hold, 50/50/49/49, but for a different reason); the stability section silently disappears for 1-rotation arms with no marker. Set: print the protocol actually found.
- `gpqa_diamond.py:234` default `--temperature 0.6` vs every launcher at 1.0 (see finding 6): the bare-command reproduction trap.

---

## Numbers checked (from the brief)

| Claim | Verdict |
|---|---|
| Illimité 25 closed-thinking 100 % / 5 at 16384 (0 %) | ✓ consistent; 25/30 = 83.3 % raw vs 81.2 % grouped ⇒ truncated-as-wrong inside the mean (finding 1) |
| 8192 arm 35 calls, 0 non-convergent, free 25/25, cut 7/10 | ✓ internally consistent (32/35 = 91.4 % raw); n_cut = 10 is too small for rule 5 (finding 3); 7/10 vs 25 %: z ≈ 3.3, but 5/10 would already fail to fire |
| χ² thresholds 7.81 / 11.34, 3 df | ✓ correct |
| 4.16 / 2.02 / 0.31 at n = 285 / 235 / 128 | ✓ plausible magnitudes (rms letter deviation ≈ 3 / 2.6 / 2.2 pts) — but the test aims at preference, not position (finding 4) |
| Spreads 6.1 / 9.0 / 6.2 pts vs MDE ~15 | ✓ MDE arithmetic checks (15.1 at n = 285); the honest sentence is "a 9-pt position effect is invisible to this design," which is what was observed |
| 68.7 % ± 4.2, 294 calls / 74 questions | ✓ as published — but it is a rule-3-violating mixture (finding 1) |
| 50 + 50 + 49 + 49 = 198 | ✓ |
| 8192 = 1.9 × worst healthy call | ✓ (8192 / 4371 = 1.87) — the *value* is defensible; the message *wording* is not (finding 5) |

---

## What I would measure next, and why it beats what they are measuring now

1. **KV f16 vs q8_0/q4_0, paired, 50 questions, same seed.** It is the only accuracy-relevant server variable never varied, it is free on the idle 4090, and it attacks the one number the campaign actually cares about — the undecomposed 89.2 → ~70 gap the logbook closes with "Q4 + protocole, sans partage mesuré." The budget sweep optimizes within a regime whose baseline error is unmeasured; this measures the regime.
2. **NON-PARSE/echo rate among MARQUE-bearing calls** (replay of the 35-call partial + a 30-call sonde at 2048). It quantifies the contamination of rule 5's decision criterion — the quantity that decides the budget — at a cost of minutes. Another recovery measurement without this error bar is a number whose uncertainty is dominated by a formatting artifact.
3. **Instrument-recorded PASS / FAIL / NON-MESURE with the wall at 2× slowest PASS, rerun of the 5 cas durs.** Each censored exercise currently costs a phantom FAIL in the pilot's own headline; no quantity of new exercises fixes a broken tally, and the 511 s single call shows the wall is measuring verbosity as much as coding.

---

## At its optimum (each line: setting — reason)

- **Budget always paired with a transition message, never nude (exit-8 guard)** — their own cited 78 % nude vs 89 % messaged; the guard makes regression impossible.
- **8192 as a budget value** — 1.9× the worst healthy call, clean separation from a total bimodal gap; 0/35 non-convergent.
- **`--reasoning-format none`** — one text field keeps `extraire`, the MARQUE, and the think-parser on the same data.
- **`--parallele 1` on the single 4090** — their own timing rationale; concurrency would falsify per-call times for nothing.
- **Sampling extras via file (`extra_local.json`), `top_k 20 / min_p 0`** — matches vendor values; only temperature deviates (finding 6).
- **Resume by (Record ID, rotation) + a fresh JSONL per server regime** — the 26/08 mixed-regime near-miss is exactly what this prevents.
- **`--tours 1` for variant D** — kills the tour-2 acceptance-suite leak at `pilote.py:637`; a condition of validity, not a preference.
- **`@Disabled` removal + JUnit-XML count verification** (`juge_claude.py:70-124`) — their own first-attempt false PASS proves neither gesture is cosmetic.
- **The chainer's refusal gates** (≥ 190 calls, live-argv check, never kills what it didn't launch) — correct shared-resource discipline.
- **Client `--max-tokens 16384` given budget 8192** — 8228-token think + answer fits with margin; it is the censor only where it is meant to be (the illimité arm).