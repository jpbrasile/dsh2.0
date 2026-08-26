# start_llama_qwen38_27b_specdec.ps1 -- parameterized launcher for the 4090
# spec-decoding bench (port 8005). Production llama-server on :8004 is NEVER
# touched by this script.
#
# Three configs (selected by -Config, names FIXED):
#   q38-plain   : Qwen3.8-27B Q4_K_M, no speculation (baseline).
#   q38-mtp     : same model, self-speculative decoding via the MTP
#                 (multi-token prediction) head resident in the GGUF. Lossless
#                 (every draft token is verified by the target model).
#                 "No extra VRAM" was WRONG and is corrected here: the in-file
#                 head is free, the RUNTIME draft context is not. Measured:
#                   +838 MiB @ ctx 32768, +968 MiB @ ctx 65536
#                   => ~708 MiB fixed + ~4 KiB per token of draft KV.
#                 Measured 22/08/2026 at KV f16, ctx 65536, no mmproj -- this
#                 is the fastest config on this card by a wide margin:
#                   n_past    507 : decode 47.65 -> 80.28 t/s  (+68 %)
#                   n_past 16 105 : decode 45.18 -> 84.16 t/s  (+86 %)
#                   n_past 60 915 : decode 39.35 -> 71.78 t/s  (+82 %)
#                 Prefill costs a flat ~6 %. Draft acceptance 0.90-1.00.
#                 The older "speculation OFF beyond ~20-29k" guidance was an
#                 artifact of QUANTIZED KV (acceptance 0.80 there, 0.96 here);
#                 see docs/SPECDEC_4090_BENCH.md window 4.
#   q38-dflash2 : same model + an external DFlash2 draft GGUF (-md). Draft
#                 tokens are always verified by the main model -> lossless.
#                 Hard gated: requires a binary that actually exposes
#                 --spec-type draft-dflash (see the DFlash2 limitation below).
#
# ---------------------------------------------------------------------------
# DFlash2 v1 vs v2 timeline (verified 2026-08-19 via the GitHub API; do not
# re-litigate -- the -Config q38-dflash2 gate is REFUSED-BY-DESIGN today):
#   * DFlash v1 == llama.cpp PR #22105 (MERGED 2026-06-28). b10488 ships v1;
#     its `--spec-type draft-dflash` flag is the v1 flag. The --help gate
#     passing only proves the v1 flag is present -- necessary but NOT
#     sufficient for DFlash2.
#   * DFlash2 == llama.cpp PR #27342 (grouped dynamic depthwise convolution +
#     candidate selector; "DFlash2 is enabled when the checkpoint is
#     DFlash2"). OPEN/UNMERGED as of 2026-08-19; b10488 (published
#     2026-08-18 11:05 UTC) predates the PR (opened 2026-08-18 20:53 UTC) by
#     ~10 h, so b10488 CANNOT serve a DFlash2 checkpoint. The staged incoai
#     DFlash2 GGUF is a DFlash2 checkpoint; feeding it to a v1-DFlash build is
#     a silent-garbage/load-failure path.
#   Gate (ALL of):
#     * `--help` must expose `draft-dflash` (NECESSARY; missing -> exit 4).
#     * AND the binary is a KNOWN DFlash2-capable build (allowlist
#       $KnownDflash2Builds below -- one locally built PR #27342 entry as of
#       2026-08-19) OR the expert override -AssumeDflash2Capable is given (the
#       --help necessary check STILL applies; -CheckOnly prints a prominent
#       ASSUMED warning, not a verification).
#   b10488 is explicitly REFUSED (exit 4): match on path containing b10488 OR
#   on --version output matching 9d77fa172 / b10488 / r788. The refusal
#   message points at PR #27342 and at
#   scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag <release-tag>
#   (or building z-lab/llama.cpp-fork branch dflash2 @
#   5ecbe1ac17ec0484c5b44af0bd580cdc9c428ed4).
#   NEVER a silent fallback to another config or binary.
#   NOTE: even when the gate passes, actual DFlash2 serving (loading the
#   incoai checkpoint) is NOT verified yet -- it needs the approved outage
#   window.
# ---------------------------------------------------------------------------
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen38_27b_specdec.ps1 -Config q38-plain
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen38_27b_specdec.ps1 -Config q38-mtp -CheckOnly
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen38_27b_specdec.ps1 -Config q38-dflash2 -CheckOnly
#
# Parameters (all override the per-config defaults):
#   -Config       q38-plain | q38-mtp | q38-dflash2 (mandatory).
#   -ModelPath    path to the main GGUF   (default: the unsloth Q4_K_M below).
#   -DraftPath    path to the DFlash2 draft GGUF  (q38-dflash2 only; default
#                 the incoai DFlash2 Q4_K_M below).
#   -BinaryPath   path to llama-server.exe (default: the b10488 CUDA binary).
#   -Port         listener port          (default 8005).
#   -CtxSize      context size           (default 32768).
#                 Measured 22/08/2026 on this card, KV f16, mmproj loaded,
#                 -ImageMaxTokens 1024, native model ctx 262144. VRAM is
#                 linear at 65 KiB/token of context:
#                   ctx 16384  -> 18192 MiB      ctx 32768  -> 19232 MiB
#                   ctx 98304  -> 23392 MiB of 24564 (1172 MiB margin)
#                 Throughput at ctx 98304 (scripts/bench_llama_ctx.py):
#                   n_past    507 : prefill 2174 t/s   decode 47.41 t/s
#                   n_past  13915 : prefill 2814 t/s   decode 45.44 t/s
#                   n_past  33415 : prefill 2615 t/s   decode 42.92 t/s
#                   n_past  71715 : prefill 2272 t/s   decode 38.57 t/s
#                   n_past  94173 : prefill 2106 t/s   decode 36.10 t/s
#                 So 98304 costs 4160 MiB over 32768 and 24% of decode over
#                 the full sweep -- no cliff, and it still fits on one 4090.
#                 Above ~98304 the card is out of room: 131072 would need
#                 ~25.5 GiB. Raising ctx does NOT slow a SHORT request.
#   -RopeScaling  rope scaling type (e.g. "yarn"), default OFF: empty => the
#                 flag pair is NOT added and the argv is identical to today.
#   -RopeScale    rope scale factor (e.g. 2.0), used with -RopeScaling.
#                 Capability ONLY -- nothing is auto-applied from GGUF
#                 metadata; pass these explicit.
#   -Ctk          KV-cache key quant override, e.g. "f16"; empty (default) =>
#                 the hardcoded q8_0. Allowlisted: f16, f32, q8_0, q4_0, q4_1,
#                 iq4_nl, bf16. Anything else = exit 4 (fail closed).
#   -Ctv          KV-cache value quant override, e.g. "f16"; empty (default) =>
#                 the hardcoded q4_0. Same allowlist and fail-closed rule.
#   2026-08-19: f16/f16 KV is the candidate fix for the measured quantized-KV
#   long-context decode collapse (4.0 tok/s @29k filled, 1.9 @58k) -- it fits
#   in 24 GB for this model (~+3.6 GB at 58k).
#   -UbatchSize   ubatch-size override; 0 (default) = the hardcoded 512.
#   -Mmproj       path to the multimodal projector GGUF. EMPTY (default) =>
#                 no vision flags are added and the argv is byte-identical to
#                 today. A Qwen3.8-27B weights GGUF carries the LANGUAGE model
#                 only: llama.cpp keeps the vision tower in a separate file, so
#                 without this the server is TEXT-ONLY and an image request is
#                 not slow, it is impossible. Fetch it with
#                 scripts\fetch_specdec_artifacts.ps1 -SkipTarget -SkipDraft -SkipBinary.
#                 When set, the alias gains a -vision suffix so a client cannot
#                 mistake a vision server for the text-only one.
#   -ImageMaxTokens N   per-image token cap (guardrail against hi-DPI blow-up);
#                 0 (default) => flag not passed. Only meaningful with -Mmproj.
#   -LogPath      override the Tee'd server log (default
#                 $env:USERPROFILE\llama-server-specdec-<config>.log).
#   -CheckOnly    run every guard/artifact/config check, print the FULL
#                 effective argv, and exit 0 WITHOUT launching anything.
#   -AssumeDflash2Capable   EXPERT-ONLY override (q38-dflash2): skip the
#                 DFlash2 allowlist refusal for a post-merge/nightly build
#                 whose --version marker we have not enumerated yet. The
#                 --help `draft-dflash` necessary check STILL applies. With
#                 -CheckOnly it prints a prominent ASSUMED (not verified)
#                 warning. DO NOT pass for b10488 or any v1-only binary.
#
# Exit codes (the contract):
#   0   guards + artifact checks passed (and, if -CheckOnly, argv printed).
#   2   refused: the shared GPU is busy (a CUDA process is running).
#   3   refused: GPU state undeterminable (nvidia-smi missing or failing).
#   4   refused: a required artifact is missing / the binary does not expose
#       the requested spec mode / the binary is not a known DFlash2-capable
#       build. In particular b10488 is REFUSED-BY-DESIGN (DFlash v1 only;
#       DFlash2 is PR #27342, OPEN as of 2026-08-19).
#
# Fail closed: a missing artifact, an unknown GPU state, or an unsupported
# binary is a refusal -- NEVER a silent fallback to another model or config.
# This script never touches :8004.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("q38-plain", "q38-mtp", "q38-dflash2")]
    [string]$Config,
    [string]$ModelPath,
    [string]$DraftPath,
    [string]$BinaryPath,
    [int]$Port = 8005,
    [int]$CtxSize = 32768,
    [string]$RopeScaling,
    [double]$RopeScale,
    [string]$Ctk = "",
    [string]$Ctv = "",
    [int]$UbatchSize = 0,
    [string]$Mmproj = "",
    [int]$ImageMaxTokens = 0,
    [string]$LogPath,
    [int]$SpecDraftNMax = 0,
    [double]$SpecDraftPMin = 0,
    # Nombre de slots servis en concurrence. Etait CODE EN DUR a 1 jusqu'au
    # 26/08/2026, et ce 1 n'a jamais ete mesure : il vient du meme copier-coller
    # que le budget 512 ci-dessous.
    #
    # CE QUE CA COUTE EN VRAM, cote KV PRINCIPAL : rien. llama.cpp PARTAGE
    # --ctx-size entre les slots, il ne le multiplie pas -- verifie sur le
    # journal de ce binaire, 26/08 14:12 :
    #   srv load_model: initializing, n_slots = 1, n_ctx_slot = 163840
    # A -Parallel 8, ce n_ctx_slot vaut 20480 et le KV total est le meme.
    #
    # MAIS CE N'EST PAS TOUTE LA VRAM, et la carte n'a AUCUNE marge. Mesure du
    # 26/08 16:30, serveur au repos, `nvidia-smi` :
    #   24 032 MiB utilises sur 24 564 -- 107 MiB libres.
    # Le decodage speculatif alloue un contexte de brouillon PAR SLOT. A
    # -Parallel 8 il en faut 8, et ils n'entrent pas dans 107 MiB. Un
    # -Parallel > 1 avec -Config q38-dflash2 ou q38-mtp doit donc etre precede
    # d'une mesure de VRAM, pas d'une esperance : la voie sure est
    # -Config q38-plain, qui libere en plus les 1,06 GiB du GGUF de brouillon.
    #
    # CE QUE CA PEUT RAPPORTER : le decodage a lot 1 d'un 27B Q4 est limite par
    # la bande passante memoire, pas par le calcul -- 8 sequences concurrentes
    # devraient donc coûter presque le meme temps qu'une seule. NON MESURE sur
    # cette carte au 26/08 : c'est exactement ce que l'A/B de l'etape 1 du plan
    # (docs/PLAN_SUITE_20260826.md) doit trancher, avec le decodage speculatif
    # comme confondant a isoler (-Config q38-plain contre -Config q38-dflash2).
    #
    # CE QUE CA CASSE : la duree PAR APPEL cesse d'etre une latence, les appels
    # se disputant la carte. Toute analyse qui lit `secondes` par appel doit
    # etre refaite ou abandonnee des que -Parallel > 1.
    #
    # Defaut 1 : le comportement de tous les appelants existants est inchange.
    [ValidateRange(1, 64)]
    [int]$Parallel = 1,
    # Hard cap on thinking tokens. -1 = unrestricted (llama.cpp's own default);
    # 0 = no thinking at all; N>0 = guillotine at N tokens.
    #
    # WAS HARD-CODED TO 512 UNTIL 2026-08-26, and that was a measured defect on
    # any reasoning workload. The value was never chosen for this bench: it was
    # copy-pasted from the start_llama_qwopus_27b_coder_* family, where the
    # intent is stated in the original comment -- keep agentic thinking short
    # and cheap. Carried into GPQA Diamond it does the opposite of what is
    # wanted. Measured on the live run (275 calls, server /tokenize, 60-block
    # sample): median think block 512 tokens, p90 512, max 514, 53/60 landing
    # exactly on the budget -- a razor-sharp wall, not a distribution -- and
    # 83 % of blocks ending mid-sentence, sometimes mid-word.
    #
    # llama.cpp cuts NAKED unless --reasoning-budget-message is also given.
    # Published measurement: a naked cut on Qwen3 9B / HumanEval fell to 78 %
    # against 94 % unrestricted and 88 % with no thinking at all -- i.e. WORSE
    # than not thinking; a transition message at budget 1000 recovered 89 %.
    # So: -1 here, and if a budget is ever wanted again, pair it with a message.
    [int]$ReasoningBudget = -1,
    # Texte injecte JUSTE AVANT la balise de fin de pensee quand le budget est
    # epuise (--reasoning-budget-message, defaut du binaire : none).
    #
    # NE JAMAIS POSER UN BUDGET SANS CE MESSAGE. C'est la difference entre une
    # coupure nue et une conclusion : la mesure publiee sur Qwen3 9B / HumanEval
    # donne 94 % sans bride, 88 % sans raisonnement, 78 % coupe NU, et 89 % avec
    # un message de transition a budget 1000. Une coupure nue est donc PIRE que
    # pas de raisonnement du tout.
    #
    # Vide => le drapeau est absent de l'argv, comportement inchange.
    [string]$ReasoningBudgetMessage = "",
    [switch]$CheckOnly,
    [switch]$AssumeDflash2Capable
)

$ErrorActionPreference = "Continue"

# --- DFlash2 capability allowlist -------------------------------------------
# Known-DFlash2-capable version/build markers, map of
#   "<--version marker substring>" -> "<note>".
# Starts EMPTY: as of 2026-08-19 no binary is known DFlash2-capable
# (DFlash2 = llama.cpp PR #27342, OPEN/UNMERGED; b10488 is DFlash v1 only,
# PR #22105). When PR #27342 merges and a post-merge release is enumerated,
# add that release's --version marker here (human-edited; do not invent it).
$script:KnownDflash2Builds = @{}
# Locally built from the PR #27342 head (commit 5ecbe1a) on 2026-08-19 using
# the official recipe (clone + `git fetch origin pull/27342/head:pr-27342` +
# cmake -DGGML_CUDA=ON). Installed at
# C:\Users\test\tools\llama-cpp\llama-cuda-pr27342-5ecbe1a\llama-server.exe.
# --version output: "version: 0.1.2-dev (build 1, commit 5ecbe1a)";
# --help exposes --spec-type draft-dflash (verified on the built binary).
# pre-upstream-merge: this binary predates any post-merge release; re-verify
# with the real DFlash2 checkpoint in the approved outage window.
$script:KnownDflash2Builds["0.1.2-dev (build 1, commit 5ecbe1a)"] = "PR #27342 head 5ecbe1a built locally 2026-08-19 (pre-upstream-merge), --help draft-dflash verified"
$script:KnownDflash2Builds["0.1.2-dev (build 1, commit f7aadef)"] = "PR #27342 head f7aadef (24/08) built locally 2026-08-25 from user-cloned z-lab/llama.cpp-fork dflash2 (13 commits past 5ecbe1a: Optimize Dflash 2 cost, rejection-sampling revert, mrope fix, p_min), --help draft-dflash verified. ATTENTION deux binaires portent cette empreinte : llama-cuda-pr27342-f7aadef (standard, 4 kernels FA symetriques seuls) et src-dflash2/build-faq (GGML_CUDA_FA_ALL_QUANTS=ON, 25/08 soir, KV mixte q8K/q4V rapide) -- seul le CHEMIN -BinaryPath les distingue, le journal de l'arm doit le porter"

# --- per-config defaults ----------------------------------------------------
# Pinned artifact paths (see docs/SPECDEC_4090_BENCH.md). The launcher NEVER
# falls back silently: a missing path aborts with exit 4 naming the item.
$model   = "C:\Users\test\models\qwen38-27b\Qwen3.8-27B-Q4_K_M.gguf"
$binary  = "C:\Users\test\tools\llama-cpp\llama-cuda-b10488\llama-server.exe"
$draft   = "C:\Users\test\models\dflash2-qwen38-27b\Qwen3.8-27B-DFlash2-Q4_K_M.gguf"

if ($ModelPath)  { $model  = $ModelPath }
if ($BinaryPath) { $binary = $BinaryPath }
if ($DraftPath)  { $draft  = $DraftPath }

$log   = if ($LogPath) { $LogPath } else { "$env:USERPROFILE\llama-server-specdec-$Config.log" }
$alias = "specdec-$Config"

# --- (kv) KV-cache type / ubatch overrides (fail closed, exit 4) ------------
# 2026-08-19: f16/f16 KV is the candidate fix for the measured quantized-KV
# long-context decode collapse (4.0 tok/s @29k filled, 1.9 @58k with q8_0/q4_0
# KV; f16/f16 fits 24 GB for this model, ~+3.6 GB at 58k). When -Ctk/-Ctv are
# set the server argv uses them INSTEAD of the hardcoded q8_0/q4_0; -UbatchSize
# > 0 replaces the hardcoded 512. Unset params leave the argv byte-identical to
# today. An unknown -Ctk/-Ctv value is a REFUSAL (exit 4) -- never a silent
# fallback to a default.
$ValidKvTypes = @("f16", "f32", "q8_0", "q4_0", "q4_1", "iq4_nl", "bf16")
$kvInvalid = @()
if ($Ctk -and ($ValidKvTypes -notcontains $Ctk)) { $kvInvalid += "-Ctk '$Ctk'" }
if ($Ctv -and ($ValidKvTypes -notcontains $Ctv)) { $kvInvalid += "-Ctv '$Ctv'" }
if ($kvInvalid.Count -gt 0) {
    Write-Host "REFUS (exit 4): invalid KV-cache type override(s): $($kvInvalid -join ', ')."
    Write-Host "  Allowed -Ctk/-Ctv values: $($ValidKvTypes -join ', ')."
    Write-Host "  No silent fallback; pass nothing to keep the defaults."
    exit 4
}

# --- (a) GPU guard (fail closed; mirrors scripts/ops/julia_gpu_safe.ps1) -----
# `nvidia-smi --query-compute-apps=pid` lists only processes holding a CUDA
# context, which is exactly the question. A missing/failing nvidia-smi is NOT a
# green light on a shared-GPU box.
$smi = (Get-Command nvidia-smi -ErrorAction SilentlyContinue).Source
if (-not $smi) {
    $msg = "nvidia-smi not found; GPU state unknown on a shared-GPU box."
    if ($CheckOnly) { Write-Host "WARN (GPU): $msg (continuing in CheckOnly)" }
    else            { Write-Host "REFUS (exit 3): $msg"; exit 3 }
} else {
    try {
        $raw = & $smi --query-compute-apps=pid --format=csv,noheader
        if ($LASTEXITCODE -ne 0) {
            $msg = "nvidia-smi failed (exit $LASTEXITCODE); GPU state unknown."
            if ($CheckOnly) { Write-Host "WARN (GPU): $msg (continuing in CheckOnly)" }
            else            { Write-Host "REFUS (exit 3): $msg"; exit 3 }
        } else {
            $busy = @($raw | Where-Object { $_ -and ($_.ToString().Trim() -ne "") })
            # 25/08 : sous WDDM la liste compute-apps inclut desormais les
            # processus graphiques du bureau re-promus en VRAM (dwm, chrome,
            # explorer... mesure : 8 residents a ~0,4 Go total, 13 W, P8).
            # Le simple comptage donnait un faux REFUS. Trois signaux mesures
            # le remplacent (fail closed conserve : erreur de lecture => exit 3
            # via le catch) :
            #  - VRAM totale > 1500 MiB : un calcul/serveur resident (llama
            #    23 Go, julia) -- le bureau mesure 0,3-0,5 Go ;
            #  - nom de processus calcul connu dans la liste ;
            #  - puissance > 100 W : un kernel tourne (repos mesure ~13 W,
            #    bench 350-450 W).
            $memRaw = (& $smi --query-gpu=memory.used --format=csv,noheader,nounits)
            $pwRaw  = (& $smi --query-gpu=power.draw  --format=csv,noheader,nounits)
            $mem = [int]([double]"$memRaw".Trim())
            $pw  = [double]"$pwRaw".Trim()
            $names = & $smi --query-compute-apps=process_name --format=csv,noheader
            $calc = @($names | Where-Object { $_ -match '(?i)julia|python|llama|vllm|ollama|torch|kobold|lmstudio|\.ninfer' })
            $occupied = ($mem -gt 1500) -or ($calc.Count -gt 0) -or ($pw -gt 100)
            if ($occupied -and -not $CheckOnly) {
                Write-Host "REFUS (exit 2): GPU busy (mem=${mem} MiB, power=${pw} W, calc procs=$($calc.Count) : $($calc -join ', '))."
                exit 2
            } elseif ($occupied) {
                Write-Host "WARN (GPU): busy par signaux mesures (mem=${mem} MiB, pw=${pw} W, calc=$($calc.Count)) (CheckOnly: continuing)."
            } else {
                Write-Host "GPU guard: no compute occupant (mem=${mem} MiB, power=${pw} W, $($busy.Count) desktop-resident process(es)). OK."
            }
        }
    } catch {
        $msg = "failed to query GPU ($_); state unknown."
        if ($CheckOnly) { Write-Host "WARN (GPU): $msg (continuing in CheckOnly)" }
        else            { Write-Host "REFUS (exit 3): $msg"; exit 3 }
    }
}

# --- (b) artifact / binary capability checks (fail closed, exit 4) ----------
$missing = @()
if (-not (Test-Path $binary)) { $missing += "binary ($binary)" }
if (-not (Test-Path $model))  { $missing += "model ($model)" }
if ($Config -eq "q38-dflash2" -and -not (Test-Path $draft)) { $missing += "dflash2 draft ($draft)" }
# Vision is opt-in, but an opt-in that silently degrades to text-only is the
# worst outcome: the server would answer ABOUT an image it never saw.
if ($Mmproj -and -not (Test-Path $Mmproj)) { $missing += "mmproj ($Mmproj)" }

if ($missing.Count -gt 0) {
    Write-Host "REFUS (exit 4): required artifact(s) missing:"
    foreach ($m in $missing) { Write-Host "  - $m" }
    Write-Host "Run scripts\fetch_specdec_artifacts.ps1 to download them. No silent fallback."
    exit 4
}

# DFlash2 gate = --help necessary check AND (allowlist OR -AssumeDflash2Capable).
# The --help check proves only that the (v1) flag exists; the allowlist /
# override decides whether the binary is actually DFlash2-capable.
if ($Config -eq "q38-dflash2") {
    # -- (1) NECESSARY check: `--help` must expose draft-dflash.
    $helpOut = try {
        $proc = & $binary --help 2>&1
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            Write-Host "REFUS (exit 4): binary $binary refused --help (exit $code)."
            exit 4
        }
        $proc
    } catch {
        Write-Host "REFUS (exit 4): could not run --help on $binary : $_"
        exit 4
    }
    $helpText = [string]::Join("`n", @($helpOut))
    if ($helpText -notmatch "draft-dflash") {
        Write-Host "REFUS (exit 4): binary $binary does not support --spec-type draft-dflash."
        Write-Host "  This binary predates llama.cpp PR #27342 (DFlash2, OPEN as of 2026-08-19)."
        Write-Host "  Stage a post-merge release via:"
        Write-Host "    scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag <release-tag>"
        Write-Host "  NEVER a silent fallback to another config or binary."
        exit 4
    }
    Write-Host "(binary offers draft-dflash: confirmed)"

    # -- (2) capability: `--version` output (best effort; empty is fine) plus
    #      the allowlist / expert override decision.
    $verOut = try {
        $proc = & $binary --version 2>&1
        $proc
    } catch {
        Write-Host "WARN (DFlash2): could not run --version on $binary : $_"
        $null
    }
    $verText = [string]::Join("`n", @($verOut))

    $allowMatched = $null
    foreach ($marker in $script:KnownDflash2Builds.Keys) {
        if ($verText -match [regex]::Escape($marker)) { $allowMatched = $marker; break }
    }
    $isB10488 = ($binary -match "b10488") -or ($verText -match "9d77fa172|b10488|r788")

    # F9: the b10488 hard-refusal sits ABOVE both the allowlist and the expert
    # hatch, so neither can override a KNOWN DFlash v1-only build. b10488 says
    # its --spec-type draft-dflash is the DFlash v1 flag (PR #22105); feeding it
    # a DFlash2 checkpoint (PR #27342, open/unmerged) is a silent-garbage path.
    if ($isB10488) {
        Write-Host "REFUS (exit 4): binary $binary is b10488 -- DFlash v1 only (llama.cpp PR #22105,"
        Write-Host "  MERGED 2026-06-28). Its --spec-type draft-dflash is the DFlash v1 flag."
        Write-Host "  DFlash2 support is PR #27342 -- OPEN/UNMERGED as of 2026-08-19; b10488"
        Write-Host "  (published 2026-08-18 11:05 UTC) predates the PR (opened 2026-08-18 20:53 UTC)"
        Write-Host "  by ~10 h, so it cannot serve a DFlash2 checkpoint."
        Write-Host "  Stage a post-merge release via:"
        Write-Host "    scripts\fetch_specdec_artifacts.ps1 -Dflash2BinaryTag <release-tag>"
        Write-Host "  or build z-lab/llama.cpp-fork branch dflash2 @"
        Write-Host "    5ecbe1ac17ec0484c5b44af0bd580cdc9c428ed4."
        Write-Host "  NEVER a silent fallback to another config or binary."
        exit 4
    } elseif ($AssumeDflash2Capable) {
        Write-Host "WARNING (DFlash2): DFlash2 capability is ASSUMED (expert override"
        Write-Host "  -AssumeDflash2Capable), NOT verified against the allowlist or --version."
        Write-Host "  Use only for a post-merge/nightly build; the --help check still applied."
    } elseif ($allowMatched) {
        Write-Host "(binary matches known DFlash2-capable marker: $allowMatched)"
    } else {
        Write-Host "REFUS (exit 4): binary $binary is not a known DFlash2-capable build."
        Write-Host "  This --version matches no entry in \$KnownDflash2Builds."
        Write-Host "  Add its marker to \$KnownDflash2Builds after PR #27342 is enumerated, or use"
        Write-Host "  -AssumeDflash2Capable (EXPERT-ONLY) for an unenumerated post-merge/nightly build."
        Write-Host "  NEVER a silent fallback to another config or binary."
        exit 4
    }
}

# --- compile the effective argv --------------------------------------------
$cmdArgs = @(
    "--model", $model,
    "--host",  "127.0.0.1",
    "--port",  $Port,
    "--ctx-size", $CtxSize
)
# Rope scaling is capability ONLY and OFF by default: empty -RopeScaling means
# the flag pair is never added and the argv is byte-identical to today. Nothing
# is auto-applied from GGUF metadata; AC2 (scripts/gguf_meta.py) reports the
# model's native context_length so a caller decides explicitly whether to scale.
if ($RopeScaling) {
    if ($RopeScale -gt 0) {
        $cmdArgs += @("--rope-scaling", $RopeScaling, "--rope-scale", ("{0}" -f $RopeScale))
    } else {
        Write-Host "WARN (rope): -RopeScaling $RopeScaling given but -RopeScale is 0/not set; rope flags NOT passed."
    }
}
# KV cache dtype. Default f16, NOT quantized -- measured on this card 21/08/2026,
# same model, same binary (b10488), same probe, only -Ctk/-Ctv differing:
#
#            KV q8_0/q4_0      KV f16/f16
#   prefill @   715 tok      538 t/s        1117 t/s
#   prefill @ 13915 tok       47 t/s        2801 t/s      <-- 296 s vs 5 s
#   decode  @   715 tok     39.7 t/s        47.7 t/s
#   decode  @ 13915 tok     12.7 t/s        45.7 t/s
#   VRAM @ ctx 32768         18558 MiB      19232 MiB
#
# So quantizing the KV bought 674 MiB and cost a 60x prefill collapse past ~10k
# context; f16 decode is nearly flat to 32k (47.7 -> 42.9 t/s). -Ctk/-Ctv still
# override, for a caller who genuinely needs those 674 MiB.
if (($Ctk -and $Ctk -ne "f16") -or ($Ctv -and $Ctv -ne "f16")) {
    Write-Host "WARN (kv): quantized KV requested (k=$Ctk v=$Ctv). Measured 21/08/2026 on"
    Write-Host "  this card: q8_0/q4_0 prefill collapses to 47 t/s at ~14k context (f16: 2801 t/s)"
    Write-Host "  and decode to 12.7 t/s (f16: 45.7 t/s), to save 674 MiB. Advisory only."
}
# --- contexte PAR SLOT ------------------------------------------------------
# --ctx-size est PARTAGE entre les slots, pas alloue a chacun. Un -Parallel 8
# sur --ctx-size 163840 laisse 20480 jetons par slot. Si ce quotient tombe sous
# ce que le client demande (invite + --max-tokens), llama.cpp tronque ou refuse
# l'appel SANS que le harnais s'en apercoive : on lirait une chute d'exactitude
# la ou il n'y a qu'une fenetre trop petite. On l'affiche donc toujours.
$ctxParSlot = [int][math]::Floor($CtxSize / $Parallel)
Write-Host ("INFO (slots): -Parallel $Parallel sur --ctx-size $CtxSize " +
            "=> $ctxParSlot jetons par slot (VRAM inchangee, le contexte est partage).")
if ($ctxParSlot -lt 20480) {
    Write-Host "WARN (slots): $ctxParSlot jetons par slot. Un client a --max-tokens 16384"
    Write-Host "  plus son invite peut ne PAS tenir. Verifier avant de mesurer une exactitude."
}
if ($ctxParSlot -lt 2048) {
    Write-Host "REFUS (exit 9): $ctxParSlot jetons par slot -- fenetre inutilisable."
    exit 9
}

$cmdArgs += @(
    "--flash-attn",   "on",
    "--cache-type-k", $(if ($Ctk) { $Ctk } else { "f16" }),
    "--cache-type-v", $(if ($Ctv) { $Ctv } else { "f16" }),
    "--batch-size",   "2048",
    "--ubatch-size",  $(if ($UbatchSize -gt 0) { "$UbatchSize" } else { "512" }),
    "--n-gpu-layers", "99",
    "--parallel",     "$Parallel",
    "--jinja",
    "--reasoning-format", "none",
    "--reasoning-budget", "$ReasoningBudget",
    "--temp",             "0.6",
    "--top-k",            "20",
    "--top-p",            "0.95",
    "--min-p",            "0",
    "--presence-penalty", "0.0",
    "--repeat-penalty",   "1.0"
)

# --- budget de pensee : jamais nu -------------------------------------------
# Un budget SANS message de transition coupe la pensee en pleine phrase. La
# mesure publiee (Qwen3 9B / HumanEval) : 94 % sans bride, 88 % sans
# raisonnement, 78 % coupe NU, 89 % avec message a budget 1000. Une coupure nue
# est donc PIRE que pas de raisonnement du tout -- on refuse de la produire par
# accident, comme ce lanceur l'a fait du 25/08 au 26/08 avec un 512 code en dur.
if ($ReasoningBudget -gt 0 -and -not $ReasoningBudgetMessage) {
    Write-Host "REFUS (exit 8): -ReasoningBudget $ReasoningBudget sans -ReasoningBudgetMessage."
    Write-Host "  Une coupure NUE mesure PIRE que pas de raisonnement du tout (78 % contre 88 %)."
    Write-Host "  Donner un message de transition, ou -ReasoningBudget -1 (illimite)."
    exit 8
}
if ($ReasoningBudgetMessage) {
    $cmdArgs += @("--reasoning-budget-message", $ReasoningBudgetMessage)
}

# --- vision (opt-in; unset => argv byte-identical to today) -----------------
if ($Mmproj) {
    $alias = "$alias-vision"
    $cmdArgs += @("--mmproj", $Mmproj)
    if ($ImageMaxTokens -gt 0) { $cmdArgs += @("--image-max-tokens", "$ImageMaxTokens") }
}
$cmdArgs += @("--alias", $alias)

if ($Config -eq "q38-mtp") {
    # draft-mtp flag set, known good from b9637. p-min/n-max carried over from
    # Qwen3.6-27B acceptance-collapse tuning; revisit if Qwen3.8 acceptance
    # looks collapsed.
    $cmdArgs += @(
        "--spec-type",        "draft-mtp",
        "--spec-draft-p-min", "0.75",
        "--spec-draft-n-max", "2",
        "--spec-draft-n-min", "1"
    )
} elseif ($Config -eq "q38-dflash2") {
    # Per PR #27342 semantics (VERIFY at runtime via --help; DFlash2
    # auto-enables from the checkpoint; block size default). --spec-draft-n-max
    # follows the official incoai README block-8 flag set (7 draft tokens).
    # -SpecDraftNMax (0 = default 7) added 25/08 for the ctx-sweep parametric
    # study: the PR #27342 bench reports n-max 4 beating 7 by ~29 % at 32k
    # (folded review, docs/SPECDEC_4090_BENCH.md 25/08) -- measured HERE, not
    # assumed. Unset => argv byte-identical to before this parameter existed.
    $cmdArgs += @(
        "--spec-type",        "draft-dflash",
        "-md", $draft,
        "--spec-draft-n-max", $(if ($SpecDraftNMax -gt 0) { "$SpecDraftNMax" } else { "7" })
    )
    # -SpecDraftPMin (0 = flag absent, argv byte-identical) : le p_min dflash2
    # n'existe que depuis le commit du 21/08 (post-5ecbe1a) ; sonde de la reco
    # communautaire 0.60-0.75, a n'utiliser que sur un build >= f7aadef.
    if ($SpecDraftPMin -gt 0) {
        $cmdArgs += @("--spec-draft-p-min", ("{0}" -f $SpecDraftPMin))
    }
}

# --- (c) -CheckOnly: print the FULL effective argv, then exit without launch --
if ($CheckOnly) {
    Write-Host "===== $Config -CheckOnly: guards + artifact checks PASSED ====="
    Write-Host "binary: $binary"
    Write-Host "model:  $model"
    if ($Config -eq "q38-dflash2") { Write-Host "draft:  $draft" }
    if ($Mmproj) { Write-Host "mmproj: $Mmproj  (VISION ON, alias $alias)" }
    else         { Write-Host "mmproj: (none) -- server is TEXT-ONLY" }
    Write-Host "port:   $Port  ctx: $CtxSize  log: $log"
    Write-Host ""
    Write-Host "FULL effective argv (joined):"
    $display = ('  {0} {1}' -f ('"{0}"' -f $binary), ($cmdArgs -join ' '))
    Write-Host $display
    Write-Host ""
    # F10: lossless one-arg-per-line block (each arg double-quoted) so the window
    # orchestrator can round-trip argv that contains spaces verbatim. The joined
    # line above is kept for humans / older parsers.
    Write-Host "FULL effective argv (one per line):"
    foreach ($a in @($binary) + $cmdArgs) {
        Write-Host ('  "{0}"' -f $a)
    }
    Write-Host ""
    Write-Host "(CheckOnly -- nothing launched. :8004 untouched.)"
    exit 0
}

# --- (e) port-scoped, name-checked stop on the TARGET port only -------------
# Stop ANY llama-server LISTENING on the target port. We never touch :8004. A
# non-llama-server holding the target port is a refusal (we never kill it).
# -State Listen is required: a stale TIME_WAIT socket (owner System/other)
# left by a force-stopped server is NOT a live holder and must not trip the
# refusal -- same semantics as stop_llama_port.ps1.
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        try {
            $p = Get-Process -Id $_ -ErrorAction Stop
            if ($p.ProcessName -ieq "llama-server") {
                Write-Host "Stopping prior bench llama-server PID=$($p.Id)"
                Stop-Process -Id $p.Id -Force
            } else {
                Write-Host "REFUS (exit 4): port $Port held by non-llama-server PID=$($p.Id) ($($p.ProcessName)). Abort."
                exit 4
            }
        } catch {}
    }
Start-Sleep -Seconds 2

# --- (f)+(g) launch, Tee log, print what is actually loaded -----------------
Write-Host "===== launching spec-dec config $Config on :$Port ====="
Write-Host "Binary:  $binary"
Write-Host "Model:   $model"
if ($Config -eq "q38-dflash2") { Write-Host "Draft:   $draft" }
Write-Host "Log:     $log"
# What the log actually carries was MEASURED on 21/08/2026 against b10488 at
# verbosity 3: it has `srv load_model: loading model ...` and `llama_server:
# model loaded`, and NO device/offload/buffer line at all -- this script used
# to promise `llama_model_loader ...`, which never appears. Do not go looking
# for offload in the log; ask the running server, which answers precisely:
Write-Host "Verify the RUNNING server (not the log) once it is up:"
Write-Host "  curl -s http://127.0.0.1:$Port/props   ->  .modalities.vision (mmproj really loaded),"
Write-Host "                                             .build_info, .default_generation_settings.n_ctx"
Write-Host "  nvidia-smi --query-gpu=memory.used --format=csv  ->  what the weights actually took"

# Two channel defects were measured in this very line on 21/08/2026, and both
# were SILENT -- the log looked fine and simply had less in it than advertised:
#
#   1. `2>&1` on a NATIVE exe in PowerShell 5.1 wraps stderr in ErrorRecords
#      (the log opened with a NativeCommandError block) and the model-load
#      lines this script promises above were absent from it. Merging inside
#      cmd.exe hands PowerShell ONE plain stdout stream instead.
#   2. Tee-Object in 5.1 writes UTF-16 with no -Encoding switch, so the log is
#      invisible to grep/rg -- `grep -c CUDA0 <log>` answered 0 on a log that
#      did contain the word. Tee by hand, in UTF-8.
$quoted  = $cmdArgs | ForEach-Object { if ("$_" -match "[ \t]") { '"' + $_ + '"' } else { "$_" } }
$cmdLine = '"' + $binary + '" ' + ($quoted -join ' ') + ' 2>&1'
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
& cmd.exe /c $cmdLine | ForEach-Object {
    Write-Host $_
    Add-Content -LiteralPath $log -Value $_ -Encoding UTF8
}
exit $LASTEXITCODE
