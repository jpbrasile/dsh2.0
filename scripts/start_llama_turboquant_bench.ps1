# Launch the TurboQuant llama.cpp fork on port 8005 for Phase −1 bench.
# Three configs selected by -Config a|b|c:
#   a = baseline (q8_0/q4_0 @ 64K) — same KV math as production, run via the bench binary
#   b = TurboQuant @ 64K (turbo4 K / turbo3 V) — apples-to-apples vs config a
#   c = TurboQuant @ 256K (turbo4 K / turbo3 V, ctx 262144) — long-ctx regime
#
# Production llama-server on port 8004 is left untouched (we use port 8005).
#
# Usage:
#   & scripts\start_llama_turboquant_bench.ps1 -Config a
#
# Leave the window open. Ctrl-C to stop. Server log Tee'd to:
#   $env:USERPROFILE\llama-server-tq-<config>.log

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("a", "b", "bp", "c", "d")]
    [string]$Config
)

$ErrorActionPreference = "Continue"

# Stop any prior llama-server on port 8005. We do NOT touch port 8004 (production).
Get-NetTCPConnection -LocalPort 8005 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        try {
            $p = Get-Process -Id $_ -ErrorAction Stop
            if ($p.ProcessName -eq "llama-server") {
                Write-Host "Stopping prior bench llama-server PID=$($p.Id)"
                Stop-Process -Id $p.Id -Force
            }
        } catch {}
    }
Start-Sleep -Seconds 2

$exe   = "C:\Users\test\tools\llama-cpp-turboquant-bin\llama-server.exe"
$model = "C:/Users/test/models/qwen36-35b-a3b/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf"
$log   = "$env:USERPROFILE\llama-server-tq-$Config.log"

switch ($Config) {
    "a" {
        $ctk = "q8_0"
        $ctv = "q4_0"
        $ctx = "65536"
        $alias = "tq-bench-a-baseline-64k"
    }
    "b" {
        $ctk = "turbo4"
        $ctv = "turbo3"
        $ctx = "65536"
        $alias = "tq-bench-b-turbo-64k"
    }
    "bp" {
        $ctk = "turbo4"
        $ctv = "turbo3"
        $ctx = "131072"
        $alias = "tq-bench-bp-turbo-128k"
    }
    "c" {
        $ctk = "turbo4"
        $ctv = "turbo3"
        $ctx = "262144"
        $alias = "tq-bench-c-turbo-256k"
    }
    "d" {
        # Hybrid -ngl 30: 30/64 layers on GPU, rest on CPU.
        # Per memory project_apex_hybrid_2026_04_30.md: frees ~4.8 GB VRAM at ~2x latency cost.
        # Goal: voice stack co-residence (LLM hybrid + STT(CPU) + Kokoro on GPU).
        $ctk = "turbo4"
        $ctv = "turbo3"
        $ctx = "131072"
        $alias = "tq-bench-d-hybrid-ngl30-128k"
    }
}

$ngl = if ($Config -eq "d") { "30" } else { "999" }

$cmdArgs = @(
    "--model", $model,
    "--host",  "127.0.0.1",
    "--port",  "8005",
    "--ctx-size",     $ctx,
    "--parallel",     "1",
    "--cache-type-k", $ctk,
    "--cache-type-v", $ctv,
    "--flash-attn",   "on",
    "--n-gpu-layers", $ngl,
    "--no-mmap",
    "--mlock",
    "--temp",             "0.6",
    "--top-k",            "20",
    "--top-p",            "0.95",
    "--min-p",            "0",
    "--presence-penalty", "1.5",
    "--alias",  $alias,
    "--jinja"
)

Write-Host "===== TurboQuant bench config $Config ====="
Write-Host "Exe:    $exe"
Write-Host "Model:  $model"
Write-Host "ctk:    $ctk"
Write-Host "ctv:    $ctv"
Write-Host "ctx:    $ctx"
Write-Host "Log:    $log"
Write-Host ""

& $exe @cmdArgs 2>&1 | Tee-Object -FilePath $log
