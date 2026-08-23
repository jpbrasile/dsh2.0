# Launch llama-server with BASE Qwen3.6-35B-A3B APEX-I-Compact (NON-MTP) on the
# TurboQuant binary, port 8004 — the "high-tps at large context" config.
#
# WHY this combo (2026-07-14 swap off the Qwopus fine-tune, user request):
#   - Model = base Qwen3.6-35B-A3B in the APEX quant (mudler APEX-I-Compact, 16.1 GB).
#     APEX = imatrix-calibrated, adaptive per-tensor bits -> better than plain K-quant
#     at equal size (PPL 6.857 vs 6.883, HellaSwag 83.5% vs 82.8%, measured 2026-06-15).
#   - NON-MTP file, so it loads clean on the TurboQuant binary (the MTP head blk.40 was
#     the ONLY thing that blocked that binary; APEX quant + Qwen3.6 arch are compatible).
#   - TurboQuant turbo4/turbo3 KV -> tiny+fast KV cache -> 256K ctx in ~19 GB and fast
#     decode AT DEPTH (~139 t/s @6K vs a plain-KV collapse to ~56). This is the lever
#     that gives both context size AND speed-at-depth.
#   - NO speculation (MTP or ngram): both measured NET-NEGATIVE on this A3B *MoE* on a
#     single 24GB card (MoE expert-saturation: verifying a draft batch loads the union
#     of routed experts, cancelling the memory saving). thc1006 RTX3090 bench: MTP -12%,
#     ngram-cache -12%, ngram-mod -3%; your own box: MTP 52 vs 56 t/s @6K. Dropped on
#     purpose — costs nothing real on the agentic workload (8-18K ctx tool-call turns).
#
# Binary: atomicmilkshake/llama-cpp-turboquant (turbo3/turbo4 KV kernels). Same binary
# and arg set the Qwopus launcher used, proven-loadable.
#
# Revert to the Qwopus fine-tune = run scripts/start_llama_qwen36_35b_a3b_qwopus_turboquant.ps1
#
# Usage:
#   & scripts\start_llama_qwen36_35b_a3b_apex_turboquant.ps1
#
# Leave the window open. Ctrl-C to stop. Log Tee'd to:
#   $env:USERPROFILE\llama-server-qwen36-apex-turboquant.log

[CmdletBinding()]
param(
    # 0.0.0.0 so the VPS chat-router reaches this over Tailscale (100.80.215.119:8004).
    [string]$BindHost = "0.0.0.0"
)

$ErrorActionPreference = "Continue"

# Stop any existing llama-server (port 8004 is exclusive on this host).
Get-Process llama-server -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "Stopping existing llama-server PID=$($_.Id)"
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Seconds 3

$exe   = "C:\Users\test\tools\llama-cpp-turboquant-bin\llama-server.exe"
$model = "C:/Users/test/models/qwen36-35b-a3b-apex/Qwen3.6-35B-A3B-APEX-I-Compact.gguf"
$log   = "$env:USERPROFILE\llama-server-qwen36-apex-turboquant.log"

$cmdArgs = @(
    "--model", $model,
    "--host",  $BindHost,
    "--port",  "8004",
    # TurboQuant turbo4 K / turbo3 V -> KV stays tiny. Native 262144 (256K): KV ~1.2 GB,
    # total ~18-19 GB with vision. Context is NOT VRAM-bound; decode at depth is
    # compute-bound (150->57->27 t/s at 0->70K->195K).
    "--ctx-size",     "262144",
    "--parallel",     "1",
    "--cache-type-k", "turbo4",
    "--cache-type-v", "turbo3",
    "--flash-attn",   "on",
    "--n-gpu-layers", "999",
    # Vision / render-in-the-loop (verified on this binary). mmproj = shared Qwen3.6
    # projector; --image-max-tokens 1024 caps per-image token cost (guardrail).
    "--mmproj", "C:/Users/test/models/qwen36-35b-a3b-apex-mtp/mmproj.gguf",
    "--image-max-tokens", "1024",
    # Bound reasoning trace (verified supported). WITHOUT this an OpenCode agentic
    # request spends the whole budget in reasoning_content and returns EMPTY content.
    "--reasoning-budget", "512",
    # --reasoning-format none: fold reasoning INLINE. On a tool-call turn OpenCode does
    # NOT send enable_thinking:false; a separate reasoning_content channel collides with
    # tool_calls and OpenCode hangs. `none` gives a clean tool_calls response.
    "--reasoning-format", "none",
    # Sampling profile (same as the other Qwen3.6 launch scripts; presence 1.5 is the
    # tuned 35B-A3B MoE setting that curbs "Wait...Actually..." wandering).
    "--temp",             "0.6",
    "--top-k",            "20",
    "--top-p",            "0.95",
    "--min-p",            "0",
    "--presence-penalty", "1.5",
    # alias = base model id so opencode.json's qwen-local/qwen-moe + the chat-router
    # report writer (model "qwen36-35b-a3b") resolve UNCHANGED.
    "--alias",  "qwen36-35b-a3b",
    "--jinja"
)

Write-Host "Starting: $exe (BASE Qwen3.6-35B-A3B APEX-I-Compact NON-MTP + TurboQuant turbo4/turbo3 KV @256K)"
Write-Host "Model:    $model"
Write-Host "Log:      $log"
Write-Host ""

& $exe @cmdArgs 2>&1 | Tee-Object -FilePath $log
