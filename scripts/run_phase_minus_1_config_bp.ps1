# Phase -1 Config B-prime orchestration: stop production, run TurboQuant bench @ 128K, restart production.
# Matched-context comparison vs Config A (production also at 128K).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_phase_minus_1_config_bp.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$orchLog  = "$env:USERPROFILE\phase-minus-1-config-bp-orch.log"

function Log($msg) {
    $ts = (Get-Date).ToString("HH:mm:ss")
    "$ts $msg" | Tee-Object -FilePath $orchLog -Append
}

function Stop-AllLlamaServers {
    $procs = Get-Process llama-server -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            Log "Stopping llama-server PID=$($p.Id)"
            try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch { Log "  already gone" }
        }
        Start-Sleep -Seconds 5
    } else {
        Log "No llama-server process running."
    }
}

function Wait-ForHealth {
    param([string]$Url, [int]$TimeoutSec = 600)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) {
                $body = $r.Content
                if ($body -match '"status"\s*:\s*"ok"') { return $true }
            }
        } catch {}
        Start-Sleep -Seconds 3
    }
    return $false
}

Set-Content -Path $orchLog -Value "" -Encoding utf8

Log "===== Phase -1 Config B-prime orchestration ====="
Log "repoRoot=$repoRoot"

try {
    Log "Step 1: stop production llama-server"
    Stop-AllLlamaServers

    Log "Step 2: launch bench server (Config bp = TurboQuant @ 128K, port 8005)"
    $benchScript = Join-Path $repoRoot "scripts\start_llama_turboquant_bench.ps1"
    $benchArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $benchScript, "-Config", "bp")
    $benchProc = Start-Process powershell.exe -ArgumentList $benchArgs -PassThru -WindowStyle Hidden
    Log "  bench launcher PID=$($benchProc.Id)"

    Log "Step 3: wait for bench server /health (up to 10 min for model load)"
    if (-not (Wait-ForHealth -Url "http://127.0.0.1:8005" -TimeoutSec 600)) {
        throw "bench server never became ready on 8005"
    }
    Log "  bench server ready"

    Log "Step 4: run TPS bench (Config bp, 5 prompts x 3 seeds = 15 runs)"
    Push-Location $repoRoot
    try {
        & python bench\turboquant_tps.py --config bp --server-url http://127.0.0.1:8005 2>&1 | Tee-Object -FilePath $orchLog -Append
    } finally {
        Pop-Location
    }
    Log "  bench complete"

} catch {
    Log "ERROR during bench: $_"
} finally {
    Log "Step 5: stop bench server"
    Stop-AllLlamaServers

    Log "Step 6: restart production llama-server (port 8004)"
    $prodScript = Join-Path $repoRoot "scripts\start_llama_qwen36_35b_a3b.ps1"
    $prodArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $prodScript)
    $prodProc = Start-Process powershell.exe -ArgumentList $prodArgs -PassThru -WindowStyle Hidden
    Log "  production launcher PID=$($prodProc.Id)"

    Log "Step 7: wait for production /health"
    if (Wait-ForHealth -Url "http://127.0.0.1:8004" -TimeoutSec 600) {
        Log "SUCCESS: production back online on 8004"
    } else {
        Log "WARNING: production did not respond in 10 min - check $env:USERPROFILE\llama-server-qwen36-35b-a3b.log"
    }
    Log "===== Done. Orch log: $orchLog ====="
}
