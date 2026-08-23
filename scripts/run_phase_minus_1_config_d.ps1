# Phase -1 Config D orchestration: stop production, run TurboQuant hybrid bench
# (turbo4/turbo3 KV @ 128K + -ngl 30), restart production. Validates voice-stack
# VRAM headroom: LLM partial-CPU + STT(CPU, 0 GB) + Kokoro(GPU) on 24 GB.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_phase_minus_1_config_d.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$orchLog  = "$env:USERPROFILE\phase-minus-1-config-d-orch.log"

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
            if ($r.StatusCode -eq 200 -and $r.Content -match '"status"\s*:\s*"ok"') { return $true }
        } catch {}
        Start-Sleep -Seconds 3
    }
    return $false
}

function Get-VramUsedMiB {
    try {
        $r = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits
        return [int]($r.Trim().Split("`n")[0])
    } catch { return -1 }
}

Set-Content -Path $orchLog -Value "" -Encoding utf8

Log "===== Phase -1 Config D orchestration (hybrid -ngl 30) ====="

try {
    Log "Step 1: stop production"
    Stop-AllLlamaServers

    Log "Step 2: launch bench (Config d, turbo4/turbo3 @ 128K, -ngl 30)"
    $benchScript = Join-Path $repoRoot "scripts\start_llama_turboquant_bench.ps1"
    $benchArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $benchScript, "-Config", "d")
    $benchProc = Start-Process powershell.exe -ArgumentList $benchArgs -PassThru -WindowStyle Hidden
    Log "  bench launcher PID=$($benchProc.Id)"

    Log "Step 3: wait for /health (CPU-side layer load may take longer)"
    if (-not (Wait-ForHealth -Url "http://127.0.0.1:8005" -TimeoutSec 600)) {
        throw "bench server never became ready on 8005"
    }
    Log "  bench server ready"

    $idleVram = Get-VramUsedMiB
    Log "  VRAM at idle (post-load, pre-bench): $idleVram MiB"

    Log "Step 4: run TPS bench (15 runs)"
    Push-Location $repoRoot
    try {
        & python bench\turboquant_tps.py --config d --server-url http://127.0.0.1:8005 2>&1 | Tee-Object -FilePath $orchLog -Append
    } finally {
        Pop-Location
    }

    $warmVram = Get-VramUsedMiB
    Log "  VRAM after bench (warm): $warmVram MiB"
    Log "  bench complete"

} catch {
    Log "ERROR during bench: $_"
} finally {
    Log "Step 5: stop bench"
    Stop-AllLlamaServers

    Log "Step 6: restart production"
    $prodScript = Join-Path $repoRoot "scripts\start_llama_qwen36_35b_a3b.ps1"
    $prodArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $prodScript)
    $prodProc = Start-Process powershell.exe -ArgumentList $prodArgs -PassThru -WindowStyle Hidden
    Log "  production launcher PID=$($prodProc.Id)"

    Log "Step 7: wait for production /health"
    if (Wait-ForHealth -Url "http://127.0.0.1:8004" -TimeoutSec 600) {
        Log "SUCCESS: production back online on 8004"
    } else {
        Log "WARNING: production did not respond in 10 min"
    }
    Log "===== Done. Orch log: $orchLog ====="
}
