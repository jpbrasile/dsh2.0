Read the whole package: the plan, the earlier red team, the pre-registration (3 revisions), the logbook, the harness, the scorer, both launchers, the chainer, and the pilot. Findings below, most severe first. Two of the direct questions get short answers up front because the ranked list leans on them.

**The old certification vs the plan's §2 — the old one is wrong, and the plan is also wrong in its phrasing.** First principles: a 27B Q4_K_M is ~16 GB of weights (the package's own numbers: 18192 MiB total at ctx 16384, `start_llama_qwen38_27b_specdec.ps1:77`). A 4090 moves ~1 TB/s, so a batch-1 decode step spends ~16 ms reading weights — the package *measures* this: 47.65 t/s plain batch-1 decode (`start_llama_qwen38_27b_specdec.ps1:16`), i.e. ~75% of the bandwidth ceiling and ~4% of the FLOPs. Eight concurrent sequences reuse each weight read 8×; at ~432 GFLOP per batched step the card is still under its compute roofline, so aggregate throughput should scale ~4–6×. The earlier red team's "concurrency would falsify per-call times **for nothing**" certified a latency-measurement argument as a throughput optimum — that is the error. But the plan over-corrects: what is nearly free is the *marginal weight read*, not the per-call time — each call decodes slower behind the other seven. Both documents miss the consequence that matters here: under `--parallel 8` the sweep's *time* endpoint ("le temps et le coût par appel", `PRE_ENREGISTREMENT_BUDGET.md:76`) stops being comparable to any per-call time ever measured in this campaign.

**The §1 inference (6018 / 70,8 = 85 s ≈ 80 s ⇒ "pure generation, client weighs nothing") is circular.** The debit was computed as tokens/secondes per call client-side (`gpqa_diamond.py:163-166, 372`), so tokens ÷ (tokens/seconds) ≈ seconds is an accounting identity that would hold identically if half of every call were client overhead. It cannot distinguish generation-bound from overhead-bound; it is not evidence. What it additionally hides: (i) median(tokens)/median(debit) divides medians of two different quantities from a bimodal distribution (mean output 5090 < median 6018 proves the bimodality — the "median call by tokens" and "median call by seconds" are different calls); (ii) the server has been up since 14:12 and the 70.8 t/s was measured at ~2 h age, while the package's own paired measurement says a 17 h-old server loses ~27% throughput (66.1 → 84.2 t/s, `DSH_QWEN_LOCAL_LOGBOOK.md:2065-2069`) — so the 4.41 h projection and any fresh-server A/B cell are optimistic relative to a 4.4 h arm. The conclusion is probably right; the arithmetic presented as its proof is void, and §7 ground 2 leans on it.

---

## Ranked findings

### 1. HIGH — A 45.5 % budget-cut rate voids the calibration of 8192 itself, and with rule 5 still unamended the sweep's decision is structurally biased toward 2048 regardless of the data.

**Severity meaning:** HIGH here = the primary endpoint (which budget the pre-registered sweep selects, `PLAN_SUITE_20260826.md:115-121`) is corrupted in a known direction — toward the lower budget — before any arm-B call exists.

**Where:** `PLAN_SUITE_20260826.md:29` (45.5 %, reported, no consequence drawn); `DSH_QWEN_LOCAL_LOGBOOK.md:2232-2236` (the 8192 calibration); `PRE_ENREGISTREMENT_BUDGET.md:73-80` (rule 5); `PRE_ENREGISTREMENT_BUDGET.md:245` (finding 3 of the earlier red team: "Non amendé").

**Defect:** 8192 was set at "1.9× the worst healthy call" from an illimité sample of **30 calls over 8 questions** (median 1111, p90 2695, max sain 4371, "gap total, rien entre les deux") — and the plan's own §1 now shows 25/55 calls still running at 8192, i.e. a 45.5 % overrun rate versus the 17 % ceiling rate that calibration predicted; the bimodality story is refuted by the plan's own re-measure, and the plan draws no consequence.

**Concrete failure:** arm B at 2048 will cut ~55–65 % of calls (45.5 % runaways + the healthy calls above p90 2695). Both arms are then majority-guillotined regimes; the sweep contains no arm in which the model finishes thinking on most questions, so it cannot answer "what budget retains" — it ranks two degrees of amputation. Rule 5 then decides: a 2048 arm whose cut calls recover at 40–55 % (between chance 25 % and the ~70 % healthy recovery) passes every rung — no floor above chance, no statistic, tie broken by "lowest budget wins" (`PRE_ENREGISTREMENT_BUDGET.md:75-76`) — and 2048 is selected while converting most of the bench into post-guillotine guesses. This was the earlier red team's finding 3, dismissed in Rev 2 as "désamorcé en grande partie" by 3a; at 45–65 % cut rates the dead zone is no longer an edge case, it is the main path.

**What to do instead:** write a dated amendment **now**, before any arm-B data exist (after the arms run, amending rule 5 is exactly the post-hoc gesture the pre-registration exists to prevent): (a) record that the 8192 calibration population was 8 questions and is void; (b) add the missing rung — "an arm whose cut-call recovery is more than 15 points below its own free-call accuracy, with n_cut ≥ 30, is écarté"; (c) restate the claim honestly: the sweep measures the cost of cutting at 45 % vs ~60 % cut rates, not the preservation of thinking. And schedule the missing cell the throughput work makes affordable: a `−1` (illimité) tournant arm at the retained fast config (~1–1.5 h if batching pays off) is the only mostly-free-thinking comparator in the whole design.

**How to test cheaply:** no GPU needed — tokenize the stored think blocks of the 55-call partial (`rendement_coupure.py` with a SEUIL sweep) to get the empirical P(think > t) curve, and read off the expected cut rates at 2048/8192/16384. That replaces an 8-question calibration with a 55-question one. (Correct for the ~5 % token undercount on cut calls caused by the 24000-char tail — finding 12.)

---

### 2. HIGH — §4's "same config on both sides is enough" breaks because the treatment itself moves each arm to a different context-depth operating point of a quantized KV cache.

**Severity meaning:** HIGH here = the A−B paired accuracy difference — the sweep's deciding number — absorbs a term that is not the budget, in the direction that penalizes the larger budget and feeds "lowest budget wins".

**Where:** `PLAN_SUITE_20260826.md:103-111` (§4); `start_llama_qwen38_27b_specdec.ps1:421-424` (q8_0/q4_0 in force); `start_llama_qwen38_27b_specdec.ps1:20-23` (acceptance 0.80 under quantized KV vs 0.96 under f16); `DSH_QWEN_LOCAL_LOGBOOK.md:1814-1818` (the undecomposed 89.2 → ~70 gap).

**Defect:** budget 8192 fills a slot to ~9 k tokens (8228 think + answer + 245 prompt); budget 2048 fills it to ~3 k — the arms differ in *depth*, and every attention sum at depth d in a q4_0-value cache accumulates d quantized values, so the arms are served at different amounts of KV noise; "same config both sides" cancels constants, not treatment-dependent variables.

**Concrete failure:** the package's own launcher documents that swapping KV quantization moved draft acceptance from 0.96 to 0.80 (`start_llama_qwen38_27b_specdec.ps1:20-23`) — i.e. the KV regime measurably shifts the model's next-token distribution; if that shift costs accuracy points at 9 k depth, every dollar of it lands on arm A, the paired difference reads "2048 ≈ 8192 or better", rule 5's tie-break fires, and the effect is attributed to the budget. The same depth term confounds the *time* endpoint: decode slows with depth (their own sweep: 47.4 t/s @507 → 36.1 @94 k, plain config), so arm A is also slower for a non-budget reason — and rule 5's stated rationale is that the lower budget buys time.

**What to do instead:** run the arms under `-Ctk f16 -Ctv f16` at a ctx that fits: f16 KV needs ~65 KiB/token (their slope, `start_llama_qwen38_27b_specdec.ps1:76-78`), so 163840 is impossible, but the sweep only needs 245 + 16384 + margin ≈ 17 k per call — `-CtxSize 32768` at `--parallel 1` fits (19232 MiB measured, `:77`), and at `--parallel 8` a ctx of 139264 gives 17408/slot. Quantized KV buys VRAM that a 245-token-prompt benchmark does not need; the plan keeps it for ctx it does not need either.

**How to test cheaply:** 40 tournant questions, two cells — q8_0/q4_0 vs f16/f16 (parallel 1, specdec untouched, same seed, paired) — about 1 h of card. If the paired difference at equal budget is ≥ 3 points, the depth term is real at these depths and the sweep must not run on quantized KV. This is the earlier red team's finding 8, still unrun, and it gates 9 h of arm time.

---

### 3. HIGH — The §6 catch-up (32768) is arithmetically impossible under the very config §2 may retain, cannot be launched through the campaign's own tooling for the 512 arm, and by construction mixes server regimes inside the frozen arms.

**Severity meaning:** HIGH here = the pre-registered obligation that makes the illimité arm publishable ("reste DÛ", `DSH_QWEN_LOCAL_LOGBOOK.md:2314-2316`) either cannot be executed as specified or, when executed, contaminates the frozen anchors it is meant to repair.

**Where:** `PLAN_SUITE_20260826.md:124-128` (§6) vs `:81-82` (20480/slot "with margin"); `start_llama_qwen38_27b_specdec.ps1:451-456` (exit 8: budget > 0 without message refused); `chainer_bras_2048.ps1` regime discipline; `gpqa_diamond.py:222-231` (resume carve-out for length-truncated calls).

**Defect:** a 32768-ceiling call needs 245 + 32768 = 33 013 tokens of context, and the retained parallel-8 config allots 20 480 per slot — the plan checked the margin for the 16384 arms and never checked it against §6; and the 512-arm leg of the catch-up requires re-running calls under a nude 512 budget, which the launcher now refuses by design (exit 8), so preserving that arm's treatment is only possible by bypassing the campaign's own guard.

**Concrete failure:** after the config is retained, the catch-up forces a fourth server regime (restart at `--parallel 1`, ctx ≥ 33 013, budget −1), so the "symmetric" repair splices 5 calls served under a new regime into an arm whose other 25 calls were served under the old one — the exact mixture §3 refuses to tolerate when it discards 55 calls. The 512 arm's 7 calls are worse: re-run nude (refused by the launcher, and a nude re-run may simply run away to 32 768 and truncate again — those calls truncated *because* the model loops after a naked cut), or re-run with the message (a different treatment than the arm being repaired). Meanwhile the illimité arm's [81.2 ; 100.0] interval stays 18.8 points wide and §9's "rien ne sort avant l'étape 5" blocks every other publication behind it.

**What to do instead:** run the catch-up **now, before any config change**, under the frozen arms' own regime (parallel 1, specdec, q8_0/q4_0, ctx 163840): it is ~12 calls × ≤ 8 min ≈ 1.5 h. For the 512 arm, make the dated decision the guard forces: either re-run those 7 with the transition message and publish them as a third, labelled computation, or leave the 512 arm as the declared mixture it already is (`ETAT_CAMPAGNE_20260826.md:84-87`).

**How to test cheaply:** the arithmetic is free (33 013 > 20 480). The launcher refusal is a 10-second dry run: invoke the relance with `-ReasoningBudget 512` and no message, watch exit 8.

---

### 4. HIGH — The accuracy-relevant server variables are never varied and one of them sits on an unmerged-fork binary whose own changelog lists a "rejection-sampling revert"; the plan's only config experiment measures speed.

**Severity meaning:** HIGH here = the absolute number §0 promises to publish next to BF16 inherits an unmeasured error of unknown sign from the serving regime, and no scheduled step can detect it.

**Where:** `start_llama_qwen38_27b_specdec.ps1:210` (f7aadef build note: "13 commits past 5ecbe1a: Optimize Dflash 2 cost, **rejection-sampling revert**, mrose fix, p_min"); `:479-491` (spec flags, "always verified → lossless" is a comment, not a measurement); `DSH_QWEN_LOCAL_LOGBOOK.md:1814-1816` ("censé préserver la distribution… à vérifier, pas à supposer"); `PLAN_SUITE_20260826.md:61-91` (§2 tests throughput only).

**Defect:** the losslessness of dflash2 speculative decoding is asserted by a header comment while the binary actually in service is a locally built PR fork whose changelog says the rejection-sampling path was *reverted* — the one mechanism that makes spec decoding distribution-preserving — and the plan's cells C1/C2/C3 vary specdec only as a speed variable, never checking whether it changes *what the model answers*.

**Concrete failure:** if the reverted rejection sampling makes sampling lossy on this build, every number in the campaign — 68.7, 81.2, 83.6, both arms, the budget decision's absolute level — carries an unquantified perturbation that lands precisely inside the 89.2 → ~70 gap the logbook leaves "sans partage mesuré". The same holds for q4_0 value-cache. None of this cancels in A-vs-B if the perturbation interacts with depth (finding 2).

**What to do instead:** one 20-call greedy check before anything else: fixed seed, `temperature: 0` from the client, specdec on vs specdec off, byte-compare the two outputs. Identical ⇒ lossless at least deterministically; any diff ⇒ specdec leaves the config for every accuracy-facing arm. KV f16 is finding 2's cell.

**How to test cheaply:** the greedy diff is ~10 minutes of card. If it fails, the fix costs nothing: C2 (no specdec) becomes the accuracy-facing config and the throughput question is answered by the same A/B the plan already scheduled.

---

### 5. MEDIUM — §0's headline comparison against the published BF16 number violates the harness's own comparability rule, and the step that would make it valid was explicitly abandoned.

**Severity meaning:** MEDIUM here = no measured number is wrong, but the claim the campaign fronts ("mis en regard du chiffre publié pour ce modèle en BF16", `PLAN_SUITE_20260826.md:15-17`) is one the package's own code declares invalid — the published-vs-local gap will be overstated by an unknown protocol term.

**Where:** `PLAN_SUITE_20260826.md:15-17`; `gpqa_diamond.py:5-9` ("un score GPQA publié n'est pas opposable à un score maison, parce que le gabarit de prompt, l'extraction de la réponse et le réglage CoT déplacent le résultat de plusieurs points"); `DSH_QWEN_LOCAL_LOGBOOK.md:1813-1818` (BF16 same-harness arm "abandonné le 26/08 par décision explicite"; protocol of the published number unknown).

**Defect:** the plan builds a same-harness comparison principle into the client, abandons the only arm that satisfies it, and then schedules a headline that needs it.

**Concrete failure:** the published juxtaposition reads "Q4 costs ~X points" when the honest decomposition is "Q4 + template (`--jinja` with a baked `reasoning_effort|default('xhigh')` instruction, `DSH_QWEN_LOCAL_LOGBOOK.md:1801-1806`) + extraction + budget + KV + specdec + unknown published protocol". A reader cannot tell how much of X is quantization — which is the entire question the campaign poses.

**What to do instead:** either complete the same-harness BF16 comparator (the `or_bf16` file exists at n = 128; extend it to the tournant 198 at ~0 $ of card — it is an OpenRouter arm), or reword §0 to publish the local number against its own bar with the published figure quoted as context-only, protocol declared unknown.

**How to test cheaply:** run the existing `or_bf16` partial through the amended scorer (`depouiller_gpqa.py`, rules 3a/3b) and see whether the local/BF16 gap under the *same harness* differs from 89.2 − local. That difference is the size of the protocol term being smuggled into the headline.

---

### 6. MEDIUM — §1's identity arithmetic is used to license two downstream claims it cannot support, and the projection built on it (4.41 h) ignores the package's own measured server-age decay.

**Severity meaning:** MEDIUM here = the wall-clock projections and the §7 "client cannot matter" argument rest on a non-test, and the projection is biased low.

**Where:** `PLAN_SUITE_20260826.md:51-54` (inference), `:35` (projection 4.41 h); `DSH_QWEN_LOCAL_LOGBOOK.md:2065-2069` (66.1 t/s at 17 h vs 84.2 fresh, "une table de vitesse doit porter l'âge du serveur"); `gpqa_diamond.py:163-166` (client-side timing).

**Defect:** dividing the median token count by the median per-call rate reproduces the median duration by construction (see preamble), so it is presented as evidence for three conclusions it does not test: "the time is pure generation", "the client weighs nothing", "the only lever is server-side".

**Concrete failure:** two numbers come out wrong. (i) The 4.41 h projection extrapolates a ~2 h-old server's median over a 4.4 h run while the package's own paired measurement shows a decay worth −27 % at 17 h — arm A will run slower than projected and by an amount nobody will have logged, because the JSONL records no server age (the logbook's own rule, `DSH_QWEN_LOCAL_LOGBOOK.md:2069-2071`, is not implemented anywhere). (ii) §7 ground 2 ("changing the client doesn't change throughput, therefore the lever is `--parallel`") is true for a 245-token prompt but was generalized from an identity, not a measurement — an agent harness multiplies *total generated tokens* (multi-turn), which is the one thing that does scale wall-clock client-side.

**What to do instead:** stamp every JSONL record with server uptime at call time (one field, server start is known — 14:12:06 in §1); compute the projection from the age-binned rates; and replace the §1 sentence with the honest version: "prompt is 245 tokens, prefill is < 0.3 s at measured prefill rates, so per-call time is generation-dominated" — which is provable from numbers already in the package.

**How to test cheaply:** no GPU — regress per-call t/s (tokens_sortie/secondes, already recorded) against call index over the 55 existing calls. A negative slope at 2 h of age confirms the decay is already inside the arm data.

---

### 7. MEDIUM — The ordering measures speed before validity, and leaves the pre-registered rule-5 amendment past its deadline; what it risks making unpublishable is everything.

**Severity meaning:** MEDIUM here = the sequence can burn 9 h of arms under a regime that a cheaper earlier measurement would have rejected, and it delays the one obligation (catch-up) that gates all publication.

**Where:** `PLAN_SUITE_20260826.md:61` (étape 1 = throughput) through `:124` (catch-up at étape 5); `PRE_ENREGISTREMENT_BUDGET.md` header (amendments must precede their data).

**Defect:** étape 1 decides a *speed* variable while the *validity* variables (KV quant, specdec losslessness — findings 2 and 4) are testable in ~1 h and gate whether the arms should run under this regime at all; rule 5 must be amended before arm-B data exist, and no step schedules it; and the catch-up is sequenced after the config change that makes it regime-mixing (finding 3).

**Concrete failure:** arms A and B run (étapes 2–3, ~7–9 h); the greedy specdec check or the KV cell is run later, or never, and either fails — both arms are unpublishable against §0's claim and must be re-run; meanwhile the illimité anchor stays [81.2 ; 100] because its repair was scheduled last.

**What to do instead:** reorder to: (0) rule-5 amendment, written and dated today; (1) the two validity cells (greedy specdec diff, KV f16 paired — findings 2/4); (2) the 32768 catch-up under the frozen regime; (3) the throughput A/B; (4) arms. The whole pre-flight is ~2.5 h against 9 h it protects.

**How to test cheaply:** no measurement — walk the failure tree: for each of {specdec lossy, KV q4_0 costly at 9 k depth, catch-up impossible at 20480/slot}, ask which scheduled step detects it and how many GPU-hours have already been spent at that point. Today the answers are {nothing, nothing, étape 5}.

---

### 8. MEDIUM — The A/B's three cells omit the one cell that attributes the effect, its primary metric is confounded by per-cell token counts, and its guardrails are thresholds without numbers.

**Severity meaning:** MEDIUM here = the retained config can be chosen on a 1.3–1.5× artifact or leave "is specdec worth it at batch 1" unmeasured — the question that decides whether per-call times stay comparable to anything frozen.

**Where:** `PLAN_SUITE_20260826.md:77-89` (C1/C2/C3, "mesure primaire : temps de paroi", "du même ordre", "une seule mesure par config suffit"); `ETAT_CAMPAGNE_20260826.md:40-43` ("spéculatif et lot se marrient mal — à trancher par un A/B").

**Defect:** C2−C1 changes three things at once (server parallel, specdec, client parallel); the decomposition the plan needs (C3−C1 for parallel, C2−C3 for specdec at batch 8) is available, but the effect of specdec *at batch 1* — the regime of every frozen arm and of the C1 comparability claim — has no cell; and wall-clock over 20 questions is proportional to tokens generated, which differ across cells because each cell is a fresh sampling draw at temp 1.0.

**Concrete failure:** a cell whose draws happen to produce 10 % fewer tokens shows a 10 % wall-clock gain that is not speed; the stated guardrail ("cut rate and output-token median must stay du même ordre") tolerates exactly this; and with 20 questions ≈ 2.5 waves at parallel 8, makespan is dominated by stragglers (max 137.6 s in §1), so a true 3× at n = 198 can read as 1.8× at n = 20 — under the ≥ 2× expectation, the plan would then conclude against a config that actually wins. Also unguarded: VRAM at C3 (draft context per slot — the MTP measurement priced draft KV at ~708 MiB fixed + ~4 KiB/token, `start_llama_qwen38_27b_specdec.ps1:11-14`, but nothing verifies the dflash2 draft scales the same under 8 slots), and `--reasoning-budget` accounting per slot under concurrency — the treatment-delivery mechanism itself, untested at parallel 8.

**What to do instead:** add cell C0 = `--parallel 1`, specdec **off** (this is also finding 4's accuracy cell done on the same restart); make the primary metric aggregate decode throughput = total generated tokens / wall-clock, with per-cell token totals required within ±10 %; state numeric guardrails (cut rate within ±10 points of C1, median output tokens within ±10 %, `nvidia-smi` recorded after load and after the run); stamp server age per cell.

**How to test cheaply:** the C0 cell is 20 questions ≈ 25 min on the existing server regime; the metric change is arithmetic on fields already recorded (`tokens_sortie`, `secondes`).

---

### 9. MEDIUM — Discarding the 55 calls is a conditional necessity treated as an absolute, and in the branch where it is not enough, the plan does not name what else is contaminated.

**Severity meaning:** MEDIUM here = 1.13 h of card is spent for uniformity in the branch where the regime does not change, while in the branch where it does change, real contamination (the catch-up splices, the stability-control partial, the frozen anchors' times) goes unflagged.

**Where:** `PLAN_SUITE_20260826.md:95-99` (§3, unconditional fresh file); `gpqa_diamond.py:222-231` (resume is the designed behavior); `PRE_ENREGISTREMENT_BUDGET.md:164-167` (the 4-rot partial is kept *for* the stability control).

**Defect:** if C1 is retained, the 55 calls were served under the byte-identical argv of the retained config and are arm A's first 55 measurements — the fresh-file rule ("un fichier JSONL neuf par configuration… jamais de mélange de régimes serveur", and the logbook's 26/08 mixed-regime near-miss) governs *regimes*, not server age, and no regime changed.

**Concrete failure:** in the C1 branch the plan pays 1.13 h to re-measure 55 answers it already has, and loses the only within-arm replication check it will ever have (old 55 vs new 55 on the same ids — a free noise-floor reading, the same trick as the `high`≡`xhigh` control the logbook prizes). In the C2/C3 branch, discarding the 55 is *necessary but insufficient*: the 32768 catch-up re-runs frozen-arm calls under the new regime (finding 3), and the 4-rot 8192 partial that the stability control depends on remains old-regime while everything around it moves.

**What to do instead:** make §3 conditional: C1 retained ⇒ resume the existing file to 198 (the harness already skips done pairs); C2/C3 retained ⇒ fresh file, and add the named list of what stays old-regime (4-rot partial, frozen arms, catch-up splices) to the publication's comparability notes.

**How to test cheaply:** free — after the A/B, diff the retained argv against the 14:12:06 server's argv (the §1 block already captured it). Byte-identical is the C1 branch.

---

### 10. LOW-MEDIUM — The π refusal is right, but its fallback ("GPQA agentique, étiquetée") is a consolation prize that should be dropped, and ground 1 of the refusal argues the wrong case.

**Severity meaning:** LOW-MEDIUM here = no published number is at risk; the risk is 1–3 h of card spent on a measurement with no comparator.

**Where:** `PLAN_SUITE_20260826.md:132-162` (§7); `pilote.py:741` (`--agent dsh|pi` is the coding bench — verified), `pilote.py:880-884` (pi launch line — verified); `DSH_QWEN_LOCAL_LOGBOOK.md:1801-1811` (xhigh template default, telegraphic think at budget-free GPQA).

**Defect:** the refusal's grounds 3 and 4 (budget inoperative per tour; tools change the benchmark) are verified and sufficient, but ground 1 ("nothing to cache at 245 tokens") answers a *cache* question nobody asked locally — the honest ground is that an agent harness multiplies total generated tokens and turns, which §1's own logic says is the only thing that scales wall-clock; and the proposed fallback has no comparator: no published agentic-GPQA number for this model exists, the budget sweep cannot read it, and at a measured 45.5 % runaway-thinking rate under a template that defaults to `xhigh` (`DSH_QWEN_LOCAL_LOGBOOK.md:1801-1806`), an agent loop with a 16 384 client cap will spend most of its turns hitting output ceilings — it would measure walls, not reasoning.

**Concrete failure:** 10 questions × 2–5 turns × 4–5 min/call ≈ 1–2.5 h of card for a number that is comparable to nothing in the package and that §9's own logic would refuse to publish next to any other figure.

**What to do instead:** refuse both halves; keep the one sentence in §7 that has value ("il faudrait le construire" — i.e. it is a new instrument, not a config), and spend the saved hour on finding 1's illimité arm.

**How to test cheaply:** cost it before running it: one question through a 3-turn loop, measure tokens and ceilings. If it hits the output ceiling on turn 1 (the 45.5 % rate says it will), the fallback is dead on arrival for 45 minutes of card.

---

### 11. LOW — The effective sampling temperature of the arms appears nowhere: the plan's own §1 "config" block is silent about it, the JSONL does not record it, and the earlier red team's premise about the vendor value is contradicted inside the package.

**Where:** `PLAN_SUITE_20260826.md:41-48` (argv with `--temp 0.6`, no mention that requests override it); `lancer_bras_tournant.ps1:57` (`--temperature 1.0` is what the arm actually sends); `gpqa_diamond.py:260` (harness default 0.6 — the bare-command trap); `DSH_QWEN_LOCAL_LOGBOOK.md:1757-1760` (the measured model card: thinking mode = temp 1.0) vs `redteam/reglages_bench_20260826.md:95` (vendor reco 0.6, RECALL-ONLY).

**Defect:** the arms run at client temp 1.0 overriding the server's 0.6, and nothing in the record pins this — a future reader (or a future arm relaunched after someone "fixes" the server temp) silently changes regime; and the record contradicts the earlier red team's finding 6, which nobody has reconciled.

**Concrete failure:** arm A re-run at a different effective temperature than the 55 discarded calls and than arm B is not detectable afterwards — `enreg` carries `modele` only (`gpqa_diamond.py:320-324`).

**What to do instead:** two-line patch — write `temperature`, `top_p`, and the `extra` dict into each record; state the effective temp in §1's config block. **Cheap test:** none needed.

---

### 12. LOW — The unfixed 24000-char tail now touches 45.5 % of arm A's records: every cut call's stored think block is headless, which corrupts the analysis layer exactly on the population rule 5 reads.

**Where:** `gpqa_diamond.py:381` (`reponse[-24000:]`, "24000 caractères couvrent ~8000 jetons" — the cut calls' think alone is ~8228 tokens ≈ 24.7 k chars); `rendement_coupure.py:22` (SEUIL 7800); `redteam/reglages_bench_20260826.md:107-119` (finding 7, listed non-traité in `ETAT_CAMPAGNE_20260826.md:129`).

**Defect:** at a 45.5 % cut rate, the stored tail of every cut call has lost its `<think>` opener and its first ~300–800 tokens, so `pensee_de()` measures a fragment, `rendement_coupure.py`'s token counts run ~5–10 % low on exactly the cut population, and a cut call with a longer answer can fall below SEUIL 7800 and classify as free if the MARQUE is ever lost.

**Concrete failure:** rule 5's recovery statistic and any think-length distribution published from the arms (finding 1's P(think > t) curve included) are computed on truncated data for the subpopulation the decision is about.

**What to do instead:** store `"pensee_taille"` and `"marque": bool` at write time (the `/tokenize` round-trip already exists, `rendement_coupure.py:25-32`), or raise the tail to 40000.

**How to test cheaply:** free — count records in the 55-call partial where `"</think>" in reponse` but `"<think>" not in reponse`. Each is a headless think; expect ~25 of 55.

---

## The three GPU-hours best spent

1. **The validity pair (~1 h 10): 20-call greedy specdec on/off byte-diff, then 40 tournant questions paired q8_0/q4_0 vs f16/f16 KV, same seed.** These two cells decide whether the 9 h of arms run under a regime that can be published against §0's claim at all; they attack the undecomposed 89.2 → ~70 gap more than the entire budget sweep can; and each can veto the retained config. The plan's étape 1 spends the same card on a question (speed) whose answer cannot invalidate anything.
2. **The 32768 catch-up, run now under the frozen arms' regime (~1.5 h).** It is pre-registered, owed, gates all publication per §9, becomes arithmetically impossible or regime-mixing the moment a parallel-8 config is retained, and converts the illimité anchor from an 18.8-point interval into a number. Every hour it is deferred increases the chance it is the item squeezed out at the end of the day.
3. **The throughput A/B with the missing cell and the right metric (~1 h): C0 (parallel 1, no specdec) + C1 + C3, primary metric tokens/second aggregate, per-cell token totals within ±10 %, VRAM and server age stamped.** Cheaper than the plan's three cells (C3 and C0 answer specdec-at-batch-1 and specdec-at-batch-8 in one design) and it produces the number the plan actually needs: whether the illimité arm of finding 1 fits in the remaining card time.

## What in this plan is already right

- **Fresh JSONL per server regime, never concatenating across regimes** (`PLAN_SUITE_20260826.md:76-77`, §3) — the resume-skip trap is real and documented at `gpqa_diamond.py:222-231`; the discipline is correct in the branch where the regime actually changes.
- **The anchored budget guard** (`lancer_bras_tournant.ps1:39`) — verified fixed and tested against a 20480 server (`ETAT_CAMPAGNE_20260826.md:122-124`); it closes the silent-wrong-server failure the 13:37 incident proved possible.
- **Budget never nude: launcher exit 8 + live-argv message check** (`start_llama_qwen38_27b_specdec.ps1:451-456`, `lancer_bras_tournant.ps1:45-49`) — the 78 %-nude-vs-89 %-messaged measurement makes the guard load-bearing, not cosmetic.
- **Rules 3a/3b/3c are actually implemented in the scorer** (`depouiller_gpqa.py:98-118, 152-155, 367-391`), both computations published side by side with an explicit "non concluant" verdict on contradiction — the amendment is not prose.
- **§2's own admission that the 20-question A/B says nothing about accuracy** (`PLAN_SUITE_20260826.md:88-89`) — consistent with the package's measured MDE (~15 pt at n = 285, `PRE_ENREGISTREMENT_BUDGET.md:114-120`); the plan does not overclaim this cell.
- **The π refusal's factual basis** (`PLAN_SUITE_20260826.md:134-143`) — verified: `pilote.py:741` and `:880-884` confirm no GPQA-to-π path exists, and grounds 3–4 (per-turn budget, tools change the benchmark) are sound even though ground 1 is the wrong argument.
- **Human authorization before server restarts** (`PLAN_SUITE_20260826.md:90-91`) — matches the shared-resource rule the chainer already implements by never killing what it did not launch (`chainer_bras_2048.ps1:27-39`).