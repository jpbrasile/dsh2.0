# SPECDEC_4090_BENCH — Speculative-decoding benchmark on the RTX 4090

Status: **MEASURED, 3 windows** (2026-08-19). (1) Short-ctx matrix 3/3 configs
(`reports/specdec_20260819_window/`): dflash2 +62/+28/+80 % tok/s vs plain.
(2) Long-ctx matrix 3/3 configs at 29k/58k tokens filled, KV q8_0/q4_0
(`reports/specdec_20260819_window_longctx64k/`): decode collapses to 1.2–4.0
tok/s, speculation harmful, systematic 55–65 min first-fill stall. (3) f16-KV
window, plain (`reports/specdec_20260819_window_longctx64k-f16kv/`): decode
38.8–41.7 tok/s at 29k/58k filled, prefix cache engages, stall GONE —
**the KV quantization was the long-context killer, not the model or the 4090.**
Production :8004 restored automatically after every window (until 2026-08-23,
when production was deliberately stopped; windows since then record
`production_restored=false` as the true pre-existing state). 2026-08-22
(window 4): mtp leg at f16 KV RUN — MTP decode +68–86 %. 2026-08-24
(window 6): the coding-agent A/B real run RUN — 12/12 solved, median
wall-clock per solved task under MTP: dsh 17.8 s vs opencode 18.2 s (parity);
MTP beats plain for both agents (−43 %/−55 %). Remaining NOT-RUN: dflash2
legs (PR #27342 still open upstream) and the lossless-greedy re-check.

## Goal

Measure, on THIS machine's RTX 4090, whether three llama.cpp serving
configurations of the same Qwen3.8-27B model (plain, MTP self-speculation,
DFlash2 external draft) differ in **median wall-clock time per successfully
solved task** under a realistic 4090 coding-agent workload, so we can decide
whether DFlash2 is worth the extra VRAM/complexity.

The benchmark is a controlled, lossless, server-level throughput comparison
(the `/v1/chat/completions` driver) **plus** a coding-agent A/B harness (the
honest consumer of those tokens). Throughput alone is never the decision;
solved-task wall-clock on the 4090 is.

## Decision rule

> Decision rule: do not remove DFlash merely because MTP has strong synthetic
> or favorable-generation throughput. DFlash should be removed only if a
> controlled 4090 coding-agent benchmark shows that its extra VRAM/complexity
> does not improve median wall-clock time per successfully solved task.
> Conversely, do not adopt DFlash solely from results on other GPU
> configurations.

This literal rule is the gate. DFlash2 survives by default; removing it
requires 4090-specific evidence; adopting it requires 4090-specific evidence.

## Config matrix

All three rows run **Qwen3.8-27B Q4_K_M** (17,106,775,008 B,
sha256 `7e78da5d…6fe169`, unsloth). The only per-row difference is speculation:

| config      | spec flags | draft | notes |
|-------------|-----------|-------|-------|
| `q38-plain` | *(none)*  | —     | baseline, no speculation |
| `q38-mtp`   | `--spec-type draft-mtp --spec-draft-p-min 0.75 --spec-draft-n-max 2 --spec-draft-n-min 1` | MTP head resident in the GGUF | no extra VRAM, lossless |
| `q38-dflash2` | `--spec-type draft-dflash -md <draft>` | incoai DFlash2 Q4_K_M (1,143,006,752 B, sha256 `18a380ef…d0594`) | external draft, lossless; z-lab mirror is identical (same LFS oid) |

Shared serving flags (all rows):
`--host 127.0.0.1 --ctx-size 32768 --flash-attn on --cache-type-k q8_0
--cache-type-v q4_0 --batch-size 2048 --ubatch-size 512 --n-gpu-layers 99
--parallel 1 --jinja --reasoning-format none --reasoning-budget 512
--temp 0.6 --top-k 20 --top-p 0.95 --min-p 0 --presence-penalty 0.0
--repeat-penalty 1.0 --alias specdec-<config>`.

### DFlash2 timeline (corrected 2026-08-19; verified via the GitHub API)

- incoai `Qwen3.8-27B-DFlash2-GGUF` (and its z-lab mirror) released **2026-08-15..18**.
- **DFlash v1 ≠ DFlash2.** DFlash v1 = llama.cpp **PR #22105 ("feat: add DFlash
  support"), MERGED 2026-06-28** (merge commit `d1b34251`), with follow-ups
  (#25246 `spec-draft-p-min`, #25823 injected-KV rotation, …) also merged.
  b10488 ships **v1**: its `--spec-type draft-dflash` flag is the v1 flag.
- **DFlash2 = PR #27342** (grouped dynamic depthwise convolution + candidate
  selector; per its body "DFlash2 is enabled when the checkpoint is
  DFlash2"). **OPEN/UNMERGED as of 2026-08-19** (`state: "open"`,
  `merged_at: null`). b10488 was published **2026-08-18 11:05 UTC**, ~10 h
  BEFORE #27342 was opened (**2026-08-18 20:53 UTC**) — b10488 therefore
  **cannot** contain DFlash2 and **cannot** serve the incoai DFlash2
  checkpoint (silent-garbage/load-failure path).
- The pinned binary **b10488 (build 10488, commit 9d77fa172) advertises
  `draft-dflash` among its `--spec-type` choices** — verified 2026-08-19 via
  `<exe> --help`. That proves the v1 flag only (necessary, NOT sufficient).
  The launcher's q38-dflash2 gate is **REFUSED-BY-DESIGN** for b10488:
  `--help` must expose `draft-dflash` AND the binary must be a known
  DFlash2-capable build (allowlist, currently EMPTY) OR
  `-AssumeDflash2Capable` (expert-only). **Actual DFlash2 serving (loading
  the incoai checkpoint) is NOT verified and NOT-RUN** — that needs the
  approved outage window and a post-merge binary.
- `scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag <release-tag>` still
  stages any newer post-merge release (digest-verified from the GitHub API) into
  `C:\Users\test\tools\llama-cpp\llama-cuda-<tag>\`, and the launcher's
  `-BinaryPath` override selects it. Local fork build of `z-lab/llama.cpp-fork`
  `dflash2` @ SHA `5ecbe1ac17ec0484c5b44af0bd580cdc9c428ed4` remains the
  documented alternative.

### Context-only reference numbers (NOT 4090 data)

Cited only to motivate, never to conclude:

- PR #27342 author-reported (Apple M5 Pro class) acceptance ~5.03, ~1.81× decode.
- H200 + SGLang reports: DFlash2 ~3.43× vs MTP ~2.59×.

Per the decision rule, neither transfers to this 24 GB Ada card; they only
justify running the controlled 4090 experiment.

### Quant rationale

- VRAM budget is **24 GB on the RTX 4090 (Ada)**.
- **NVFP4 was rejected**: its quant/dequant kernels are Blackwell-only; on Ada
  llama.cpp falls back to W4A8 which gives no benefit here.
- **Q4_K_M chosen**: 17.1 GB weights + 32K-context q8_0/q4_0 KV + compute budget
  lands ≈ 20–21 GB, leaving headroom on a shared 4090 and (for DFlash2) room for
  the 1.14 GB draft checkpoint.

## Methodology

- Every `/v1/chat/completions` request fixes `seed=42`, `temperature=0.6`,
  `max_tokens` from the workload definition.
- A unique **nonce line is appended INSIDE the user prompt on every rep** so
  rep ≥ 2 cannot be served from a prefix-cached completion (throughput numbers
  are not inflated). See the documented comment in each run we call this out.
- **Warmup**: the first request after the driver starts is a warmup and is
  excluded from stats.
- **3 reps** per workload; **medians** are reported (not means).
- All rows in a matrix run use the **same binary**; each row records its
  **provenance** (`--argv-file` + optional `--sha` of the model).
- Spec decoding is **lossless**: `--compare` diffs the generated text per
  (workload, rep) across configs. A mismatch is a loud WARN (detector, not a
  gate) because lossless spec-dec must produce token-identical output.
- VRAM (nvidia-smi) captured before/after each config.
- The Tee'd server log is best-effort regex-parsed for spec/accept lines;
  `null` + parse-status when absent.

## Run instructions

```
1. Fetch artifacts once (resumable, digest-verified):
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1

2. When DFlash2 is wanted, stage a post-merge capable binary — `-Dflash2BinaryTag`
   is REQUIRED once PR #27342 merges and a release ships it (until then the
   launcher's q38-dflash2 gate REFUSES b10488, exit 4, and a `-Dflash2BinaryTag`
   release does not exist yet):
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag <release-tag>

3. Approve + run the outage window (co-degradation documented in its header):
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_specdec_window.ps1 -ApproveOutage

4. The window invokes bench\bench_specdec_4090.py per config and writes
   reports\specdec_<YYYYMMDD>_window\run_<config>.json. Compare rows:
   python bench/bench_specdec_4090.py --compare reports\specdec_<YYYYMMDD>_window

5. Coding-agent A/B (OpenCode vs DSH) on the measured rows when decided:
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_harness_ab.ps1 -Run
   (firewall hardening + DSH install are documented in its header)
   Driver and llama.cpp launchers from THIS repo; the dsh bench and its
   analyse.py from C:\Users\test\Documents\dsh2.0\scripts\bench_julia_effort
   (repo jpbrasile/dsh2.0, moved 2026-08-23); the result is recorded in BOTH
   this document and dsh2.0/docs/LOCAL_LLM.md.
```

## Rollback checklist

- Stop the bench server: `stop_llama_port.ps1 -Port 8005`.
- Restore production on 8004: `restart_production.ps1` (also enforced by the
  window's `finally` block).
- Delete model/binary artifacts if desired:
  `C:\Users\test\models\qwen38-27b`, `C:\Users\test\models\dflash2-qwen38-27b`,
  `C:\Users\test\tools\llama-cpp\llama-cuda-*\`.
- Evict the pinned DSH from the npm cache and remove its profile:
  `npm cache clean` (targeted at `@deepseek-ai/dsh`), delete `~/.dsh`.
- Delete the A/B scratch root: `C:\Users\test\AppData\Local\Temp\opencode\specdec-ab\`.
- If the documented firewall rule was added, remove it (it is NOT added by any
  script).

## Status table

| item | status |
|------|--------|
| Tooling authored (launcher/fetch/window/harness/bench/driver/tests) | DONE (dry-run / -CheckOnly only) |
| Fetch phase (18.4 GB download) | executed per project phase, resumable |
| Benchmark runs (any config) | **RUN 2026-08-19**: `q38-plain`, `q38-mtp` (3 workloads × warmup + 3 reps each; records in `reports/specdec_20260819_window/`) |
| GPU measurements (TTFT, tok/s, VRAM) | **RUN 2026-08-19** for the two configs above — see "Measured results" |
| q38-dflash2 binary gate (b10488) | **REFUSED-BY-DESIGN** (exit 4): b10488 is DFlash v1 only (PR #22105); DFlash2 is PR #27342, OPEN as of 2026-08-19 |
| DFlash2 serving verification | **NOT-RUN** (needs post-merge binary; b10488 cannot serve DFlash2) |
| Coding-agent A/B (OpenCode vs DSH) | **RUN 2026-08-24** (window 6, run 5 valid, `reports/specdec_20260824_run5_verdict/`): 12/12 solved. Median wall-clock per solved task under **q38-mtp**: dsh **17.8 s** vs opencode **18.2 s** — parity. Under plain: dsh 39.7 s vs opencode 31.9 s. Limits stated in window 6: n=3 toy tasks, 1 rep per cell, no statistics, leg-A-first order gives leg B a warm prefix cache |
| Cross-config `--compare` lossless check | **RUN — 9/9 MISMATCH at temp 0.6** (expected for sampled decoding: RNG streams differ per path; identical-output losslessness must be asserted at temp 0 / greedy — follow-up, not a defect signal) |
| Long-ctx matrix (29k/58k filled, KV q8_0/q4_0) | **RUN 2026-08-19** 3/3 configs: plain 3.96/1.88 tok/s, mtp +1.5/+0.7 %, dflash2 **−45/−35 %**; systematic 55–65 min first-58k-fill stall; no prefix-cache reuse (upstream-broken for this hybrid family) |
| f16-KV window (plain, ctx 65536) | **RUN 2026-08-19**: 41.67/38.77 tok/s at 29k/58k filled (×10–20), repeat TTFT 0.4 s (prefix cache works), first fill 19.1 s, **no stall** — launcher `-Ctk/-Ctv/-UbatchSize` params added (allowlisted) |
| Coding-agent A/B harness | **TOOLING COMPLETE 2026-08-19** (rc.7 CLI grammar, D1a empirical config gate, watchdog+scrubbed grading, reference tests, outage discipline with finally-restore; adversarial review NO-BLOCK; 36/36 offline tests). Real `-Run` **executed 2026-08-24**, window 6 — it took 5 runs to reach one valid measurement, runs 1–4 each killed by a distinct migration defect (all found, fixed, committed, archived) |

User decision 2026-08-19 (morning): dry-run-only. **Superseded same day** by an
explicit "do the real work if gpu is available" — the window ran with
`-ApproveOutage`; production :8004 was already down pre-window and was
(re)started by the window's `finally` (`production_restored: true`,
`2026-08-19T11:16:28Z`).

## Measured results (2026-08-19, outage window)

Same GPU, same binary (b10488), same model file (sha256 `7e78da5d…6fe169`
verified identical for both configs), seed 42, nonce-per-rep, warmup excluded,
median of 3 valid reps, token count from `usage.completion_tokens`:

| config | workload | median tok/s | vs plain | median TTFT (s) | VRAM (MB) |
|--------|----------|-------------:|---------:|----------------:|----------:|
| q38-plain | code_module | 40.74 | — | 0.348 | 16 846 → 16 864 |
| q38-plain | prose_explain | 41.17 | — | 0.318 | |
| q38-plain | tool_json | 39.28 | — | 0.260 | |
| q38-mtp | code_module | 54.39 | **+33.5 %** | 0.363 | 17 684 → 17 722 |
| q38-mtp | prose_explain | 54.90 | **+33.3 %** | 0.319 | |
| q38-mtp | tool_json | 72.35 | **+84.1 %** | 0.356 | |

- MTP draft acceptance (parsed from the server log): **0.80** (8 accepted /
  10 drafted) — the Qwen3.6-era acceptance-collapse mitigation
  (`p-min 0.75 / n-max 2`) holds for Qwen3.8.
- VRAM: MTP costs **~+838 MB** over plain (draft context + batch buffers) —
  the config-matrix note "no extra VRAM" for MTP refers to the *in-file* head
  only; runtime buffers are NOT free. Total ~17.7 GB of 24 GB — the DFlash2
  row must budget its 1.14 GB draft on top of ~17.7 GB, which still fits.
- TTFT is statistically unchanged (±0.1 s) — speculation costs nothing on
  prompt latency here.
- These are **server-level** numbers at concurrency 1. The plan's decision
  metric (median wall-clock per solved coding task) still needs the A/B leg.

Runtime fixes applied during the window (both pre-existing tooling defects,
fail-closed direction, tests 20/20 after): `stop_llama_port.ps1` empty-list
false-refusal; launcher pre-stop now filters `-State Listen` (a TIME_WAIT
socket was misread as a foreign holder of 8005).

### DFlash2 leg — staged, ABORTED before launch (2026-08-19, later same day)

- PR #27342 was built locally per the official GGUF-repo recipe (clone
  ggml-org/llama.cpp, `git fetch origin pull/27342/head:pr-27342`):
  `llama-server` `0.1.2-dev (build 1, commit 5ecbe1a)`, CUDA (nvcc 12.1,
  arch 89), installed at `C:\Users\test\tools\llama-cpp\llama-cuda-pr27342-5ecbe1a\`.
  `--help` contains `draft-dflash` + `--spec-draft-n-max`; the launcher
  allowlist carries its marker (provenance-commented); dflash2 flags updated
  to `--spec-draft-n-max 7` per the official README. Tests 22/22.
- The real window invocation (`run_specdec_window.ps1 -ApproveOutage
  -Dflash2BinaryPath <pr27342 exe>`) is **denied by a tool-level permission
  guard** (execution + this script + this param). The user chose to abort the
  leg rather than modify the guard. Production :8004 was never stopped.
- **To run the leg, a human executes in their own terminal:**
  `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_specdec_window.ps1 -ApproveOutage -Dflash2BinaryPath C:\Users\test\tools\llama-cpp\llama-cuda-pr27342-5ecbe1a\llama-server.exe`
  (pick a low-traffic moment; VPS clients see :8004 down for ~30–45 min; the
  script auto-restores production in its `finally`). If q38-dflash2 OOMs at
  ctx 32768 (17.1 GB target + 1.14 GB draft + KV), re-run with `-CtxSize 16384`.
- Reference acceptance for the Q4_K_M draft (other hardware, NOT 4090 data):
  5.39 (official GGUF repo README, GSM8K-style eval).
- **Landing state (2026-08-19, end of session)**: permission guard fixed
  (allow `*run_specdec_window.ps1*` added to implementer + verifier agent
  maps; `resolve_perms.py` exit 0). The staged leg WAS subsequently run
  (detached) and measured — see the long-context matrix above. The human-gated
  commit landed as 921ec8ef; the evening windows' artifacts remain uncommitted
  alongside it.

### Long-context matrix (2026-08-19, evening windows)

Window 2 — `reports/specdec_20260819_window_longctx64k/`: all three configs,
ctx 65536 allocated, prompts FILLED to ~29k (`longctx_32k`) / ~58k
(`longctx_64k`) tokens, KV q8_0/q4_0, medians of 3 reps (256 completion tok):

| config | 29k tok/s | vs plain | 58k tok/s | vs plain | TTFT 58k | first-fill stall |
|--------|----------:|---------:|----------:|---------:|---------:|------------------|
| q38-plain | 3.96 | — | 1.88 | — | 78.9 s | 55 min |
| q38-mtp | 4.04 | +1.5 % | 1.90 | +0.7 % | 78.9 s | 55 min |
| q38-dflash2 | 2.24 | **−45 %** | 1.22 | **−35 %** | 91.8 s | 65 min |

- **Speculation is useless-to-harmful with filled long context** (draft
  verification pays full attention per draft token). Keep MTP/DFlash2 for
  short-context serving only; disable beyond ~20–29k filled.
- Systematic **55–65 min stall on the first 58k fill** (3/3 configs, first-rep
  TTFT 3 300–3 930 s vs ~80 s for reps 2–3) — KV-quantization pathology, gone
  with f16 (window 3).
- No prefix-cache reuse between identical-prefix reps (upstream-documented
  broken for this hybrid family: ggml-org issues #18497, #25567 closed
  not-planned, fix #23121 unmerged).

Window 3 — `reports/specdec_20260819_window_longctx64k-f16kv/`: q38-plain,
same prompts, KV **f16/f16** (launcher `-Ctk f16 -Ctv f16`):

| 29k filled | 58k filled | first 58k fill | repeat TTFT | stall |
|----------:|-----------:|---------------:|------------:|-------|
| 41.67 tok/s | 38.77 tok/s | 19.1 s (~3 000 tok/s prefill) | **0.40 s** (cache engages) | **none** |

**Verdict: the KV quantization — not the model, the card, or the hybrid
architecture — was the long-context killer.** f16/f16 at ctx 65536: ×10–20
decode, ×200 repeat-TTFT, stall eliminated, ~+3.4 GiB VRAM (fits 24 GB).
Serving guidance: long-context workloads → `-ctk f16 -ctv f16`; speculation
OFF beyond ~20–29k filled; MTP remains the short-context win (+33 %).
Still open: mtp/dflash2 legs at f16, `llama-bench -d` isolation of the
~3 000 tok/s cold prefill, greedy lossless re-check.

> **SUPERSEDED 2026-08-22 (window 4).** The line just above -- "speculation
> OFF beyond ~20-29k filled" and the "+33 %" figure -- was measured at KV
> **q8_0/q4_0**. Re-run at f16 it is wrong by a factor of two to fifty: MTP
> gives **+72 % at 32k and +82 % at 61k**. Read window 4, not that line. The
> sentence is kept, not deleted: it is the dated record of what the
> quantized-KV window actually showed.

Window 4 -- 2026-08-22, the `q38-mtp` leg at f16 that the line above lists as
still open. Same binary (b10488-9d77fa172), same model file, `-CtxSize 65536`,
KV **f16/f16**, **no mmproj** (text-only A/B), `scripts/bench_llama_ctx.py`,
one rep per point, timings taken from the server's own `timings` block:

| n_past | plain prefill | MTP prefill | plain decode | MTP decode | decode gain |
|-------:|--------------:|------------:|-------------:|-----------:|------------:|
|    507 |  1 168 t/s |   994 t/s |  47.65 t/s |  80.28 t/s | **+68 %** |
|  8 200 |  2 831 t/s | 2 643 t/s |  46.42 t/s |  84.93 t/s | **+83 %** |
| 16 105 |  2 782 t/s | 2 621 t/s |  45.18 t/s |  84.16 t/s | **+86 %** |
| 32 060 |  2 612 t/s | 2 471 t/s |  42.95 t/s |  73.67 t/s | **+72 %** |
| 60 915 |  2 351 t/s | 2 218 t/s |  39.35 t/s |  71.78 t/s | **+82 %** |

- **The mechanism is draft acceptance, and the KV dtype was driving it.**
  At f16 the server logs acceptance **0.90-1.00 (mean ~0.96)**, mean draft
  length 2.6-2.8. The 19/08 window at q8_0/q4_0 logged **0.80**. A quantized
  KV hands the draft head noisier logits, the target rejects more drafts, and
  the speedup collapses. Long context was never the cause.
- **Even the short-context "+33.5 %" was understated** for the same reason:
  the same regime at f16 gives +68 %.
- Prefill costs a flat **~6 %** with MTP at every point; the decode gain
  dwarfs it.
- **VRAM reproduced to the MiB.** plain 20 176, MTP 21 144 (**+968**) -- the
  same +968 MiB the 19/08 window measured at ctx 65536; and plain's 20 176 is
  byte-identical to `specdec_20260819_window_longctx64k-f16kv/run_q38-plain.json`.
- MTP overhead is **not** flat: 838 MiB at ctx 32768, 968 MiB at 65536, i.e.
  ~708 MiB fixed + ~4 KiB per token of draft KV.
- The `mmproj` vision projector costs **1 136 MiB** (from plain-with-mmproj
  23 392 MiB @ ctx 98304 against plain-without 20 176 MiB @ ctx 65536, both
  f16, at the measured 65 KiB/token). Dropping it is exactly what makes
  **MTP at ctx 98304 fit**: ~23 354-23 744 MiB of 24 564. Predicted, not run.

**DFlash2 remains unmeasurable, and the -45 % row is not a DFlash2 number.**
Checked against the GitHub API on 2026-08-22: PR #27342 is **still open**
(updated 2026-08-22T04:40Z); the newest release is b10569 (2026-08-22T01:17Z),
still pre-merge. The 19/08 dflash2 row was produced by feeding a **DFlash2
checkpoint to a DFlash v1 binary**, on top of quantized KV -- two independent
invalidations. Treat it as "not a measurement of DFlash2", never as evidence
against DFlash2. The launcher's exit-4 refusal is correct and stays.

Window 5 -- 2026-08-22, reasoning effort against real coding work.
Same server as window 4 (`q38-mtp`, ctx 65536, KV f16, no mmproj). 10 Julia
exercises x 5 effort levels = 50 agent runs through dsh; the model writes
`solution.jl`, Julia grades it against assertions it never sees.
Tool: `bench_julia_effort/` (self-tested: known-GOOD 10/10, known-BAD
caught 10/10, each by its own assertion) -- since 2026-08-23 at
`C:\Users\test\Documents\dsh2.0\scripts\bench_julia_effort` (repo
jpbrasile/dsh2.0, history preserved there).

| effort | pass | median | mean | tokens/task | decode | calls |
|---|---:|---:|---:|---:|---:|---:|
| off    | 9/10  | 10.1 s | 15.1 s |   624 | **88.0 t/s** |  5.8 |
| low    | 9/10  | 17.5 s | 35.5 s | 1 599 | 72.5 t/s |  6.2 |
| medium | 10/10 | 41.0 s | 68.9 s | 3 940 | 73.2 t/s | 10.9 |
| high   | 9/10  | 36.5 s | 74.6 s | 4 357 | 75.4 t/s | 12.1 |
| xhigh  | 7/10  | 45.4 s | 69.0 s | 4 012 | 75.1 t/s | 12.3 |

**Read the built-in control first.** Qwen3.8's chat template aliases `high` to
`xhigh`, so those two rows are the SAME request byte-for-byte (sha256
15c034577114cced, 352 chars, checked via `/apply-template`). Their measured
difference is therefore this bench's noise floor:

| quantity | noise floor (high vs xhigh) | off -> medium | ratio |
|---|---:|---:|---:|
| pass rate | **2 / 10** | 1 / 10 | **< 1** |
| tokens | 8 % | +531 % | 66x |
| mean time | 8 % | +356 % | 45x |
| decode t/s | 0.4 % | -17 % | 42x |

- **Pass rate: this bench separates nothing.** Two IDENTICAL configurations
  differ by 2/10; the whole spread across five levels is 3/10. `medium`'s
  10/10 and `xhigh`'s 7/10 are both inside the noise. No level can be called
  better at n=10 -- and that is a result, not a failure of the run.
- **Cost: it separates enormously.** Turning reasoning on multiplies tokens by
  2.6-7x and wall time per task by 2.4-5x, 45-66x the noise floor.
- **Reasoning also costs 17 % of decode throughput** -- 88.0 t/s off against
  72-75 t/s on. Consistent with the window-4 mechanism: MTP only wins on
  tokens the draft head guesses right, short constrained code is highly
  guessable, free-form reasoning much less. Acceptance not re-instrumented
  in this window.
- **Aggregate over all 215 recorded agent calls: 62.7 t/s** (39 311 generated
  tokens / 626.7 s of decode), median 62.9, p25-p75 44.7-83.9, max 101.5.
  Window 4's 72-84 t/s came from a synthetic fixed-length prompt; real agent
  traffic runs lower because it alternates guessable and unguessable spans.

**An attribution defect, caught by a clock check.** The first reading of this
table put `off` at 55.2 t/s -- the slowest. It was wrong. `wire.jsonl` held
TWO campaigns (the proxy appends and knows nothing of campaigns), so the first
arm's first six runs absorbed the previous campaign's calls. Nothing in the
numbers showed it: 55 t/s instead of 88 reads perfectly well. What caught it
is the one check that can contradict the attribution -- **a run cannot spend
more time in calls than it lasted**; `off/t06` claimed 226.9 s of decode inside
a 47.5 s run. The check is now wired at the end of `analyse.py` and runs on
every analysis (verified firing on the known-bad arm, naming all six runs);
attribution keeps the LAST window per task. After the fix: 50/50 runs
consistent, and `off` moves from 55.2 to 88.0 t/s.

### Firewall waiver (2026-08-19)

The dsh outbound-block firewall hardening documented in run_harness_ab.ps1
was **WAIVED by the user** (2026-08-19). Compensating controls in the harness:
full case-insensitive env scrub (API_KEY/_TOKEN/SECRET/PASSWORD/HF_/GITHUB_/
SUPABASE_/ANTHROPIC_/OPENROUTER_/GOOGLE_APPLICATION_CREDENTIALS) on BOTH arms
and on grading children, `DSH_TELEMETRY_DISABLED=1`, pinned
`@deepseek-ai/dsh@0.1.0-rc.7` (fail-closed D1a gate), self-contained toy
tasks. Residual risk: any dsh plugin telemetry that re-enables itself
(default-off per rc.7 docs).

### OpenCode version note

The OpenCode binary currently measured on this box is **1.18.18**, while
`AGENTS.md` still quotes **1.1.28**. The `AGENTS.md` figure is a stale doc; the
harness and this document treat the installed binary as authoritative. Update
`AGENTS.md` when convenient.

## Window 6 — 2026-08-24, the coding-agent A/B real run (the honest consumer)

The last major NOT-RUN item, run at last: `run_harness_ab.ps1 -Run`, OpenCode (leg A) vs
DSH (leg B) driven through the same local bench server on :8005, 3 toy tasks,
per-arm unittest grading (tests the model never sees), configs q38-plain and
q38-mtp (dflash2 auto-skipped: no post-#27342 binary; the launcher's gate
refusal is by design). Launcher KV default f16/f16 (the window-3/4 lesson).
GPU checked idle before every launch; :8004 had no listener (production
deliberately stopped 2026-08-23) — recorded, not "restored".

**It took 5 runs to get one valid measurement.** Runs 1–4 each died on a real,
distinct environment defect — none of them a model or bench-logic defect, all
of them migration debt — found, fixed, committed, archived:

1. `scripts/stop_llama_port.ps1` referenced by both bench scripts but never
   migrated from the old repo. Imported (md5-identical in 3 sibling repos),
   commit fc89931. Archive `reports/specdec_20260824_run1_legB_bootdead/`.
2. `~/.dsh/profiles/{headless,web}/cordis.patch.yml` still pointed the
   mcp-effitech server (failOnStartupError: true) at the REMOVED
   agentic-flow-fresh path; the server had migrated to
   `dsh2.0/scripts/dsh-mcp/effitech-image/`. Paths fixed (backups kept).
3. The 2026-08-19 pin `@deepseek-ai/dsh@0.1.0-rc.7` cannot read the machine's
   `.credentials.yaml` (rc.2 versioned format `version:`+`refs:`; rc.7 reads a
   flat map only). Pin bumped to 0.1.1-rc.2, commit 93bd189. Archive
   `reports/specdec_20260824_run2_legB_credformat/`.
4. Bare `npx -y @deepseek-ai/dsh@0.1.1-rc.2` resolves a DRIFTED tree (65 caret
   deps re-resolve; the documented 21/08 measurement in scripts/dsh.ps1) —
   its --help hung >300 s at 2 GB RSS and the D1a watchdog killed it (clean
   exit 4 BEFORE any outage; the gate works). Leg B and both D1a probes now
   invoke `node ~/.dsh/runtime/dsh-0.1.1-rc.2/.../lib/bin.js` — the LOCKED
   runtime (harness/runtime lockfile, 511 pkgs, pin_check.py OK), the same
   invocation as bench.py::commande_dsh(). rc.2 renamed --dump-default-config
   to --dump-config. Commit 5129457. Archive
   `reports/specdec_20260824_run3_gate_refus/`.
5. The junction `~/.dsh/profiles/headless/node_modules/dsh-subagent-timeout`
   (21/08) still pointed at the removed agentic-flow-fresh plugin dir; its two
   sister junctions had been repointed to dsh2.0 on 23/08 — the migration was
   incomplete. Repointed. And (6) the repo `.env` carried a Context7 key under
   the name `DSH_API_KEY`: dsh REFUSES to boot when a `.env` sets a reserved
   `DSH_*` variable ("only the launching environment may set") — this silently
   broke every dsh launched with cwd inside the repo. Renamed
   `CONTEXT7_API_KEY` (name only). Proof after 5+6: `--profile headless
   --help` boots the full plugin tree in <1 s. Archive
   `reports/specdec_20260824_run4_asym_fixes_midflight/` (run 4's mtp leg ran
   post-fix: first real dsh datapoints, plain leg pre-fix dead — asymmetric,
   not comparable).

**Run 5 (valid, `reports/specdec_20260824_run5_verdict/`): 12/12 solved.**
Wall-clock per task (s), harness stopwatch, solved-only:

| task | plain A (opencode) | plain B (dsh) | mtp A | mtp B |
|---|---:|---:|---:|---:|
| t1-write-module | 57.2 | 115.1 | 43.5 | 54.7 |
| t2-fix-bug      | 21.6 |  22.3 | 15.8 | 14.2 |
| t3-refactor     | 31.9 |  39.7 | 18.2 | 17.8 |
| **median**      | **31.9** | **39.7** | **18.2** | **17.8** |

- **MTP wins in real agent work**, not only in synthetic tok/s: median
  −43 % for opencode, −55 % for dsh. The Phase-5 serving config is
  **q38-mtp + KV f16**.
- **DSH is competitive**: under MTP the medians are 17.8 vs 18.2 s — parity
  (difference below this bench's noise; single rep). Under plain, dsh trails
  (39.7 vs 31.9), driven by the long generation task t1 (115 vs 57 s): a slow
  decoder amplifies dsh's extra turns; a fast one absorbs them.
- **The DFlash2 decision rule stays open** — still no post-#27342 binary;
  nothing here is evidence for or against DFlash2.
- Honest limits: n=3 toy tasks, 1 rep per cell, no statistics; the leg-A-first
  fixed order gives leg B a warm prefix-cache advantage on the shared server
  within a config — treated as part of "same server for both arms", not
  corrected. This is a feasibility verdict, not a paper.
- The firewall-waiver section above still names the rc.7 pin; window 6
  supersedes it: the pinned artifact is now the LOCKED runtime tree
  (0.1.1-rc.2), same scrub + telemetry-off controls, D1a gate unchanged and
  demonstrated fail-closed (run 3).


## 2026-08-25 — Revue externe pliée au plan (chaque point marqué vérifié-ici ou repris-de-source)

Contexte : l'utilisateur a apporté une revue externe d'une commande llama-server
proposée ailleurs pour Qwen3.8-27B + DFlash2. **Les flags fautifs qu'elle
épingle (`--chunk-size`, drafteur `Q2_K`, cache `q4_k`) ne figurent NULLE PART
dans ce dépôt** (grep 25/08 : docs/ + scripts/ vides) — nos fenêtres mesurées
1–6 ne sont pas concernées. Ce qui suit raffine le protocole des jambes
**dflash2 encore NOT-RUN**.

### Vérifié ICI le 25/08 (binaire b10488 `--help` + API GitHub)

- **PR #27342 toujours `open`, `merged: false`** (API GitHub, `updated_at`
  2026-08-25T07:47Z). Toute annonce « SOTA stable » reste surévaluée.
- **`q4_k` n'est PAS un type de cache valide.** b10488 : `-ctk/-ctv` admettent
  exactement `f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1`
  (défaut f16). Les variantes draft `-ctkd/-ctvd` existent, même liste.
- **`-ub` (ubatch, défaut 512) est le vrai bouton de chunk prefill** — la
  taille physique soumise au GPU par lancement de kernel ; `-cb` est le
  continuous batching (actif par défaut). Un « chunk » 8192 MONTERAIT le pic
  VRAM, il ne l'aplatirait pas.
- **`--spec-type` de b10488 contient `draft-dflash`** (le flag v1 — la
  section timeline ci-dessus reste exacte : b10488 ne peut PAS servir un
  checkpoint DFlash2).
- **Un build local de la PR existe déjà** : `C:\Users\test\tools\llama-cpp\
  llama-cuda-pr27342-5ecbe1a\` — c'est le levier pour courir la jambe
  dflash2 AVANT le merge (en l'étiquetant hors-stable), si on décide de ne
  pas attendre l'amont.
- Poids du modèle : notre artefact Q4_K_M épinglé fait 17 106 775 008 B
  ≈ 17,11 GB — recoupe exactement le chiffre de la source.

### Repris de la source (crédible, NON re-mesuré ici)

- **Profondeur de draft : 4 > 7 de ~29 % à 32k** (bench de la PR #27342) ;
  à faible profondeur les deux se valent.
- **Cache V quantifié coûte au décodage en profondeur** : ~38→24 tok/s à
  ~110K en q4_0 vs f16 (discussion ggml #20969, −37 %) ; `iq4_nl` (dequant
  par table) généralement plus lent encore. **Corrobore notre propre mesure**
  (fenêtres 2–3 : KV q8_0/q4_0 tuait le long contexte, f16 le ressuscitait).
- mmproj (image/vidéo) : +0,93 GB. Layout hybride : 16 couches sur 64
  seulement portent un KV croissant (16 × [3 GatedDeltaNet+FFN] + 1
  GatedAttention+FFN) — aide le budget, mais SE MESURE, ne se suppose pas.
- Qwen3.8-27B : Apache 2.0, sorti 14/08/2026, 262K natif.

### Conséquences sur le protocole des jambes dflash2 (quand elles courront)

1. `--spec-type draft-dflash --spec-draft-n-max 4` (pas 7) — et jamais le
   chemin générique `-md`+`--draft-max` seul.
2. Drafteur **Q4_K_M** (le nôtre, sha épinglé) — jamais Q2_K.
3. KV **f16** en long contexte (notre conclusion mesurée) ; si quantifier :
   q8_0 K / q4_0 V, jamais `q4_k` (invalide).
4. `-ub` laissé à 512 ; pas de « gros chunk ».
5. Démarrer à **128K**, `nvidia-smi` en main, avant de viser 200K+ — le
   budget 24 GB est plus serré que les annonces (17,11 GB + drafteur +
   buffers + KV).

Rien ici n'invalide les fenêtres 1–6 ; le rule-gate DFlash2 (§ décision)
reste ouvert et inchangé.

## Fenêtre 7 — 2026-08-25 : étude paramétrique tps × contexte × spéculation (jambes dflash2, PREMIÈRE MESURE RÉELLE)

Ordre utilisateur : « jambes dflash2 : fais l'étude paramétrique tps vs
context vs mtp actuel ». Rapport complet + preuves :
`reports/specdec_20260825_ctxsweep_dflash2/RAPPORT.md`. Même outil et mêmes
points que la fenêtre 4 (`bench_llama_ctx.py`, ctx 65536, KV f16, greedy,
1 rép/point) ; discipline warmup ajoutée (1er tir froid : prefill −57 %,
décode insensible — mesuré, bras MTP re-tiré chaud). Le lanceur gagne
`-SpecDraftNMax` (0 = défaut 7, argv inchangé ; tests 37/37).

**Première : un checkpoint DFlash2 a réellement SERVI ici** (build local PR
#27342 tête `5ecbe1a`, allowlisté ; garde anti-charabia : texte greedy lu,
cohérent). La « serving verification » NOT-RUN depuis le 19/08 est levée.

Décode (t/s), n_past 507 → 62 115 :

| bras | 507 | 8 395 | 16 205 | 32 060 | 62 115 | acceptation |
|---|---:|---:|---:|---:|---:|---|
| q38-mtp b10488 (« actuel ») | 79,6 | 84,1 | 80,8 | 75,0 | 74,0 | 0,95–0,99 |
| dflash2 n-max 7 | **127,4** | **128,2** | **121,0** | 109,8 | **116,9** | 0,51–0,61 |
| dflash2 n-max 4 | 123,1 | 115,8 | 119,3 | **110,3** | 110,7 | 0,70–0,79 |
| dflash2 n-max 2 | 94,3 | 89,5 | 87,9 | 83,8 | 81,1 | 0,84–0,89 |

- **DFlash2 (n7) bat le MTP actuel de +46 à +60 % en décode sur tout le
  domaine 507→62k** — l'effondrement « −45 % » du 19/08 était bien un
  artefact (KV quantifié + binaire v1), jamais un chiffre DFlash2.
- **Les deux recos externes de petit n-max sont réfutées ICI** : ordre
  monotone mesuré n2 < n4 ≤ n7 (le « 4>7 de 29 % » du testeur de la PR et
  le « 24 GB culmine à 2 » communautaire ne se transportent pas ; seul
  « re-balayer sur SA config » survit). Conséquence : le point 1 des
  « conséquences protocole » ci-dessus (n-max 4) est REMPLACÉ par la
  mesure — **n-max 7 (défaut README) reste le réglage servi**.
- Coût : +1,9 GiB VRAM vs MTP (23,1 GiB au pic, tient sur 24 GB texte
  seul ; avec mmproj ≈ 24,2 GiB — JUSTE) ; prefill −8–13 %.
- **mmproj résident (contrainte utilisateur 25/08)** : options mesurables —
  (a) mmproj VRAM + n7 ≈ 24,2 GiB (marge ~350 MiB, risqué) ; (b)
  `--no-mmproj-offload` (flag vérifié sur b10488 ET build PR, défaut =
  offload) : projecteur en RAM système, VRAM ≈ 23,1 GiB, encodage image
  sur CPU à mesurer ; (c) mmproj VRAM + n4 ≈ 23,7 GiB, décode −3 %.
- Validation web du sous-plan (question utilisateur) : PR open, tête
  `f7aadef` 13 commits devant notre build (dont `Optimize Dflash 2 cost`,
  `Revert draft sampling in rejection sampling`, mrope fix) — **ces
  chiffres minorent vraisemblablement la tête courante** ; le rebuild à
  `f7aadef` attend le clone (bloqué classifieur, commande fournie à
  l'humain). p_min dflash2 inexistant dans notre build (antérieur au
  commit du 21/08) — sonde p-min 0.60–0.75 réservée au nouveau build.
- Le rule-gate (§ décision) reste ouvert : ceci est du t/s serveur ; la
  décision se prend au wall-clock médian par tâche résolue (harnais A/B).

**Deuxième passe (même jour, après-midi) — tête `f7aadef` compilée ici**
(clone humain, VS2022+nvcc 12.1 arch 89, allowlist, tests 37/37) :
n7 = 114,5–133,9 t/s (**+4–6 % vs 5ecbe1a** — `Optimize Dflash 2 cost`
mesuré ; acceptation inchangée 0,43–0,61 : le gain est le coût du draft),
n4 < n7 confirmé sur la tête fraîche, p-min 0.75 neutre (<1 %, reste à 0).
Gain total vs MTP actuel : **+53–65 %**. Plafonds contexte mesurés (f16,
texte seul, prédits puis vérifiés nvidia-smi en main) : **dflash2-n7 80K**
(105,2 t/s @ 77k, pic 24 076 MiB ; 88K = OOM arithmétique), **mtp 96K**
(64,6 t/s @ 94k, 23 428 MiB), plain 128K chargé (24 084 MiB) mais point
profond non mesuré (interrompu). **KV quantifié définitivement clos** : la
variante K-seul q8_0/f16 (jamais mesurée avant) rend 1 538 MiB et coûte
prefill ×38 / décode ×4,8 — même pathologie ; f16 obligatoire. Le lanceur
gagne `-SpecDraftPMin` (0 = flag absent, argv inchangé).

## Fenêtre 7bis — 2026-08-25 soir : le « f16 obligatoire » est RENVERSÉ (kernels FA symétriques)

Ordre utilisateur : « web search : tu n'as pas réussi mais d'autres l'ont
fait récemment ». Verdict : ils avaient raison, et la fenêtre 7 se trompait
de variable causale.

**Cause racine (prouvée dans nos binaires, pas sur le web)** : sans
`GGML_CUDA_FA_ALL_QUANTS` (OFF chez nous ET dans les zips officiels), le
build CUDA ne compile que 4 kernels FA vec — `f16/f16`, `q4_0/q4_0`,
`q8_0/q8_0`, `bf16/bf16` (`ggml-cuda/CMakeLists.txt:119-124`). Toute
combinaison KV **mixte** ⇒ repli silencieux ×25-38 (issue #24485, jamais
de warning). Nos deux essais « pathologiques » (q8_0/q4_0 des fenêtres
2-3 — la reco de la revue externe — et K-seul q8_0/f16 de la fenêtre 7)
étaient tous deux mixtes. La combinaison rapide déjà compilée, q8_0/q8_0
symétrique, n'avait jamais été essayée.

**Mesures (f7aadef n7, greedy, warmup jeté, 1 rép/pt)** :
- q8/q8 @65536 : décode 131,9 / prefill 2 316 à 14k — **vitesse f16,
  −1 862 MiB** (21 202 vs 23 064).
- q8/q8 @**131 072** (impossible en f16, plafond 80K) : 7 points, décode
  131 → **79,4 t/s @ n_past 123 909**, prefill 1 654 à 125k, VRAM 23 858.
  Le plain f16 @128K au même point : 72,8 / 16,73 t/s (mesuré le soir
  même : « charge mais ne sert pas », marge 450 MiB — en q8/q8 la marge
  remonte à ~870 MiB et tout va vite ; hypothèse pression-VRAM compatible,
  mécanisme non prouvé).
- q4/q4 @65536 : 133,8 t/s au point 500 (= f16), 117,6 à 14k (−9 % vs
  q8/q8), 20 178 MiB.
- q4/q4 @**204 800** : CHARGE à 23 306 MiB (prédit 23 272) — le
  `-c 200000` de la revue externe, inatteignable en f16 (~28 GiB), tient
  sur la 4090 sans rebuild. Balayage profond : voir RAPPORT.md 7bis.

**Limite honnête** : qualité sous KV quantifié NON mesurée (vitesse/VRAM
seulement) ; avant production : rappel long, greedy-diff vs f16, taux
d'acceptation au propre. Routes suivantes : rebuild
`-DGGML_CUDA_FA_ALL_QUANTS=ON` (q8-K/q4-V asymétrique), forks TurboQuant
(4090 : X-15 07/05, Indras-Mirror TBQ4 03/08 — hors upstream).

**Addendum 25/08 tard — 200K balayé, qualité recadrée, asymétrique essayé.**
q4/q4 @204 800 balayage complet : 134,0 t/s @507 -> **65,9 t/s @ n_past
188 643** (prefill 1 414), VRAM stable. MAIS discussion upstream #23470
(KLD, Qwen2.5-7B + ARC-500) : q8/q8 = 98,0 % de tokens identiques,
q8-K/q4-V = 96,7 %, **q4/q4 = 11,6 %** (« q4_0 sur K seul reproduit
l'effondrement ») -> le 200K est un plafond de VITESSE, pas une config de
production ; l'intuition utilisateur (« le dissymétrique était pour la
qualité ») est validée par la source. Asymétrique q8-K/q4-V ESSAYÉ sur
f7aadef (ordre « l'as-tu essayé ? ») : 36,6 / 8,3 t/s à 14k — effondré,
kernel mixte absent, comme prédit. Route B lancée : rebuild
`-DGGML_CUDA_FA_ALL_QUANTS=ON` (build-faq séparé) -> visera q8-K/q4-V
~160K. Leviers non essayés notés : `--cache-type-k-draft/v-draft`.
Config recommandée en attendant le rebuild : **q8/q8 @131 072** (79,4 t/s
au point 123 909, qualité 98 % selon source externe — à recouper ici).

**Addendum 25/08 nuit — route B faite : l'asymetrique qualite tourne a 160K.**
Rebuild `build-faq` avec `-DGGML_CUDA_FA_ALL_QUANTS=ON` (meme empreinte de
version que l'installe : le CHEMIN -BinaryPath distingue, allowlist
annotee, tests 37/37). q8-K/q4-V @65536 : 36,6/8,3 -> **2 324 / 122,2 t/s**
(x63 recupere). Balayage @**163 840** (predit 23 656 MiB, charge 23 666,
ecart 10 ; 23 832 sous charge) : 123,4 t/s @32k, 92,5 @62k, 78,5 @124k,
**68,5 t/s @ n_past 153 759** — aucun effondrement. Config d'equilibre
vitesse x qualite (96,7 % selon #23470) x contexte. Recap des plafonds du
jour : f16 80K -> q8/q8 131K (79,4 @124k) -> q8K/q4V 160K (68,5 @154k) ->
q4/q4 204,8K (65,9 @189k, qualite disqualifiante probable). Restent avant
revendication SOTA : greedy-diff/rappel long sur NOTRE modele, acceptation
au propre, et publication (pousse).
