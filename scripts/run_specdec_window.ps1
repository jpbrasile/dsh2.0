# run_specdec_window.ps1 -- FUTURE outage orchestrator for the 4090
# spec-decoding bench. NEVER run for real outside an APPROVED outage window:
# it deliberately stops production llama-server on :8004, benches the three
# configs on :8005, then ALWAYS restores production in a finally block.
#
# ---------------------------------------------------------------------------
# CO-DEGRADATION NOTES (read before approving an outage):
#   * memory_guard hook: while :8004 is down, any memory_guard invocation that
#     health-checks the local LLM will observe the outage and may take its
#     configured action (alert / halt dependent work).
#   * codegen_* skills/agents default to :8004 as their LLM base URL: requests
#     issued during the window fail with connection refused (fail-fast, no
#     silent degradation) and retry on the next attempt.
#   * local_bridge defaults to :8004: every call routed through it fails
#     during the window.
#   * The 03:00 nightly probe (agentic-flow-nightly-llm-probe) may alert if a
#     window overlaps it -- scheduled work is NOT paused by this script.
# ---------------------------------------------------------------------------
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_specdec_window.ps1 -CheckOnly
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_specdec_window.ps1 -ApproveOutage
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_specdec_window.ps1 -ApproveOutage -Dflash2BinaryPath C:\tools\llama-cuda-pr27342-5ecbe1a\llama-server.exe
#
# -Dflash2BinaryPath <path>: optional; when set, the q38-dflash2 config's
# launcher invocation gets -BinaryPath <path> (the locally built PR #27342
# DFlash2-capable binary). Other configs are unaffected.
#
# -Ctk <type> / -Ctv <type>: optional; when set, passed to the LAUNCHER only
# (never the bench driver) so the f16/f16 KV-cache experiment runs through the
# standard window machinery (2026-08-19: quantized-KV long-context decode
# suspicion). Values are allowlisted by the launcher (exit 4 on anything else).
#
# Flow (real run):
#   1. record :8004 listener state
#   2. port-scoped stop of the 8004 llama-server ONLY via stop_llama_port.ps1
#      (refuses with exit 1 if the port is held by a non-llama-server process)
#   3. per config q38-plain / q38-mtp / q38-dflash2:
#        a. capture the launcher's effective argv via -CheckOnly ->
#           <out-dir>/<config>.argv.txt  (dflash2 whose binary check fails is
#           SKIPPED with a recorded warning -- other configs still run)
#        b. launch the server in the background (launcher, -LogPath <out-dir>/<config>-server.log)
#        c. health-poll http://127.0.0.1:8005/health (<= 10 min)
#        d. run bench/bench_specdec_4090.py with --config-label/--argv-file/--server-log
#        e. port-scoped stop of the 8005 server
#   4. finally (ALWAYS):
#        restart_production.ps1, poll http://localhost:8004/health (<= 10 min),
#        write production_restored {true|false, timestamp} to <out-dir>.
#
# Exit codes:
#   0   window completed; production restored.
#   1   production NOT restored (restart_production.ps1 ran, 8004 unhealthy).
#   2   restore OK but no config produced a bench result.
#   4   refused: -ApproveOutage required for a real run (see VPS note below).
#
# -CheckOnly: validates artifacts via the launcher -CheckOnly (dflash2 binary
# failure = warning, not a fail), REPORTS GPU state without failing on it,
# prints the planned sequence, exits 0. Nothing is stopped or launched.
#
# NEVER launch this without -ApproveOutage: the VPS-visible production LLM
# (prof.atthesametime.eu over Tailscale -> local :8004) goes dark for the whole
# window. -ApproveOutage is the human's explicit acknowledgment of that.
[CmdletBinding()]
param(
    [switch]$ApproveOutage,
    [switch]$CheckOnly,
    [string]$OutDir,
    [string]$Dflash2BinaryPath,
    [string[]]$Configs = @("q38-plain", "q38-mtp", "q38-dflash2"),
    [int]$CtxSize = 0,
    [string]$Ctk = "",
    [string]$Ctv = "",
    [string]$PromptsFile,
    [string]$ReportTag
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $RepoRoot "scripts\start_llama_qwen38_27b_specdec.ps1"
$Stopper  = Join-Path $RepoRoot "scripts\stop_llama_port.ps1"
$Restart  = Join-Path $RepoRoot "scripts\restart_production.ps1"
$Bench    = Join-Path $RepoRoot "bench\bench_specdec_4090.py"
$ValidConfigs = @("q38-plain", "q38-mtp", "q38-dflash2")
$PortBench = 8005
$PortProd  = 8004

# Normalize -Configs: via `-File`, a comma-joined list arrives as ONE string
# element ("q38-mtp,q38-dflash2"); split each element on commas so both
# `-Configs q38-mtp,q38-dflash2` and `-Configs q38-mtp -Configs q38-dflash2`
# work identically.
$NormalizedConfigs = @()
foreach ($c in $Configs) {
    foreach ($part in ($c -split ',')) {
        $t = $part.Trim()
        if ($t) { $NormalizedConfigs += $t }
    }
}
$Configs = $NormalizedConfigs

# Validate -Configs against the launcher's fixed set before anything else.
foreach ($cfg in $Configs) {
    if ($ValidConfigs -notcontains $cfg) {
        Write-Host "REFUS (exit 4): unknown -Configs entry '$cfg' (valid: $($ValidConfigs -join ', '))."
        exit 4
    }
}

$OutDirExplicit = -not [string]::IsNullOrEmpty($OutDir)
if ($ReportTag) {
    $OutDir = Join-Path $RepoRoot ("reports\specdec_{0}_window_{1}" -f (Get-Date -Format "yyyyMMdd"), $ReportTag)
} elseif (-not $OutDirExplicit) {
    $OutDir = Join-Path $RepoRoot ("reports\specdec_{0}_window" -f (Get-Date -Format "yyyyMMdd"))
}
$OutDir = [System.IO.Path]::GetFullPath($OutDir)

# Evidence preservation: a NON-default workload set (-PromptsFile) MUST NOT
# write run_<config>.json into the default report dir, or it would OVERWRITE
# the measured records from the approved 2026-08-19 run. Require a distinct
# report directory (-ReportTag or an explicit -OutDir).
if ($PromptsFile -and (-not $ReportTag) -and (-not $OutDirExplicit)) {
    Write-Host "REFUS (exit 4): -PromptsFile given requires -ReportTag (or an explicit -OutDir)."
    Write-Host "  Writing run_<config>.json into the default reports\specdec_<date>_window dir would"
    Write-Host "  OVERWRITE the 2026-08-19 measured records. Point this workload set at a distinct"
    Write-Host "  report directory, e.g. -ReportTag longctx64k."
    exit 4
}

function Log([string]$msg) { Write-Host ("[window] {0}" -f $msg) }

function Test-Health([string]$url, [int]$timeoutSec = 5) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
    } catch { return $false }
}

function Wait-Health([string]$url, [int]$timeoutSec = 600) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health $url 5) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Wait-HealthOrExit([string]$url, [int]$timeoutSec, $proc) {
    # F5: health-poll while also watching the launched launcher process. If the
    # launcher itself exits (refused / crashed) we surface that immediately
    # instead of burning the full wait. Returns
    #   @{ Healthy = bool; Exited = bool; ExitCode = <int or $null> }
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Health $url 5) { return @{ Healthy = $true; Exited = $false; ExitCode = $null } }
        if ($proc -and $proc.HasExited) {
            return @{ Healthy = $false; Exited = $true; ExitCode = $proc.ExitCode }
        }
        Start-Sleep -Seconds 5
    }
    $exited = ($proc -and $proc.HasExited)
    return @{ Healthy = $false; Exited = $exited; ExitCode = $(if ($exited) { $proc.ExitCode } else { $null }) }
}

function Split-ArgvLine([string]$line) {
    # Split a quoted-argv line into tokens, honoring double quotes.
    $tokens = @(); $current = ""; $inQuote = $false
    foreach ($ch in $line.ToCharArray()) {
        if ($ch -eq '"') { $inQuote = -not $inQuote; continue }
        if ($ch -eq ' ' -and -not $inQuote) {
            if ($current) { $tokens += $current; $current = "" }
            continue
        }
        $current += [string]$ch
    }
    if ($current) { $tokens += $current }
    return $tokens
}

function Get-LauncherCheck([string]$cfg, [switch]$Silent) {
    # Run the launcher -CheckOnly and return @{ Exit = <code>; Out = <lines>; Argv = <tokens or $null> }
    $launcherArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", $Launcher, "-Config", $cfg, "-CheckOnly")
    # -CtxSize passthrough to the LAUNCHER only (never the bench): >0 overrides
    # the launcher's default 32768; 0 leaves the launcher default untouched.
    if ($CtxSize -gt 0) {
        $launcherArgs += @("-CtxSize", "$CtxSize")
    }
    # -Ctk/-Ctv passthrough to the LAUNCHER only (never the bench): empty leaves
    # the launcher's hardcoded q8_0/q4_0 defaults byte-identical to today.
    if ($Ctk) { $launcherArgs += @("-Ctk", $Ctk) }
    if ($Ctv) { $launcherArgs += @("-Ctv", $Ctv) }
    # -Dflash2BinaryPath passthrough: only the q38-dflash2 config is affected.
    if ($cfg -eq "q38-dflash2" -and $Dflash2BinaryPath) {
        $launcherArgs += @("-BinaryPath", $Dflash2BinaryPath)
    }
    $out = & powershell @launcherArgs 2>&1
    $code = $LASTEXITCODE
    $argv = $null
    $lines = @($out | ForEach-Object { "$_" })
    # F10: prefer the new per-line argv block (lossless round-trip with spaces);
    # fall back to splitting the joined line for old launcher output.
    $perLineIdx = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "one per line") { $perLineIdx = $i; break }
    }
    if ($perLineIdx -ge 0) {
        $argv = @()
        for ($j = $perLineIdx + 1; $j -lt $lines.Count; $j++) {
            $t = $lines[$j].Trim()
            if (-not $t) { break }
            if ($t.Length -ge 2 -and $t[0] -eq '"' -and $t[$t.Length - 1] -eq '"') {
                $t = $t.Substring(1, $t.Length - 2)
            }
            $argv += $t
        }
    } else {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "FULL effective argv") {
                if ($i + 1 -lt $lines.Count) { $argv = @(Split-ArgvLine $lines[$i + 1]) }
                break
            }
        }
    }
    if (-not $Silent) {
        Log "  launcher -CheckOnly ($cfg) exit=$code"
        foreach ($l in $lines) { Write-Host "    $l" }
    }
    return @{ Exit = $code; Out = $lines; Argv = $argv }
}

# ----------------------------------------------------------------------------
# gate: a real run requires explicit human approval
# ----------------------------------------------------------------------------
if (-not $ApproveOutage -and -not $CheckOnly) {
    Write-Host "REFUS (exit 4): -ApproveOutage is required for a real outage window."
    Write-Host "  Stopping :8004 makes the VPS-visible production LLM (prof.atthesametime.eu,"
    Write-Host "  Tailscale -> local :8004) go dark for the whole window (co-degradation:"
    Write-Host "  memory_guard hook, codegen_*, local_bridge on :8004 all fail during it)."
    Write-Host "  Pass -ApproveOutage ONLY after scheduling + announcing the outage."
    Write-Host "  Use -CheckOnly to validate the plan without touching anything."
    exit 4
}

# ----------------------------------------------------------------------------
# -CheckOnly: validate everything, touch nothing, exit 0
# ----------------------------------------------------------------------------
if ($CheckOnly) {
    Write-Host "===== run_specdec_window -CheckOnly (nothing stopped, nothing launched) ====="
    Log "validating each config through the launcher -CheckOnly ..."
    foreach ($cfg in $Configs) {
        $r = Get-LauncherCheck $cfg
        if ($r.Exit -eq 0) {
            Log "  $cfg : launcher checks PASSED ($($r.Argv.Count) argv tokens)"
        } elseif ($cfg -eq "q38-dflash2") {
            Log "  $cfg : WARN (will SKIP in a real run) -- launcher -CheckOnly exit $($r.Exit):"
            foreach ($l in $r.Out) { Write-Host "    $l" }
        } else {
            Log "  $cfg : launcher -CheckOnly exit $($r.Exit) (real run would record this as a failure):"
            foreach ($l in $r.Out) { Write-Host "    $l" }
        }
    }
    $smi = (Get-Command nvidia-smi -ErrorAction SilentlyContinue).Source
    if ($smi) {
        $raw = & $smi --query-compute-apps=pid --format=csv,noheader 2>$null
        $busy = @($raw | Where-Object { $_ -and ($_.ToString().Trim() -ne "") })
        if ($busy.Count -gt 0) {
            Log "GPU state: BUSY ($($busy.Count) CUDA process(es)) -- real run would refuse (exit 2)."
        } else {
            Log "GPU state: free."
        }
    } else {
        Log "GPU state: nvidia-smi not found (real run would refuse with exit 3)."
    }
    Log "planned sequence (real run):"
    Log "  1. record :8004 listener state -> $OutDir"
    Log "  2. stop_llama_port.ps1 -Port 8004 (port-scoped, name-checked)"
    Log "  3. per config ($($Configs -join ', '))): argv capture -> launch on 8005 -> health-poll -> bench -> stop 8005"
    if ($CtxSize -gt 0) {
        Log "     launcher -CtxSize $CtxSize (ctx override; NOT passed to the bench)"
    }
    if ($Ctk) { Log "     launcher -Ctk $Ctk (KV-k override; NOT passed to the bench)" }
    if ($Ctv) { Log "     launcher -Ctv $Ctv (KV-v override; NOT passed to the bench)" }
    if ($PromptsFile) {
        Log "     bench --prompts-file $PromptsFile (long-context workload set)"
    }
    if ($Dflash2BinaryPath) {
        Log "     (q38-dflash2 launches with -BinaryPath $Dflash2BinaryPath via -Dflash2BinaryPath)"
    }
    Log "  4. finally: restart_production.ps1 -> poll :8004 -> production_restored record"
    Write-Host "(CheckOnly complete -- nothing was stopped, launched, or modified.)"
    exit 0
}

# ----------------------------------------------------------------------------
# REAL RUN
# ----------------------------------------------------------------------------
Write-Host "===== run_specdec_window -ApproveOutage (REAL) ====="
Log "out-dir: $OutDir"
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$restoreOk = $false
$configOkCount = 0
$results = @()

try {
    # 1. record :8004 listener state
    $listeners = @()
    try {
        $conns = Get-NetTCPConnection -LocalPort $PortProd -State Listen -ErrorAction Stop
        $listeners = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {}
    $stateFile = Join-Path $OutDir "state_8004_before.json"
    @{ timestamp = (Get-Date).ToUniversalTime().ToString("o"); listeners_8004 = $listeners } |
        ConvertTo-Json | Out-File -FilePath $stateFile -Encoding ascii
    Log "8004 listener state recorded -> $stateFile ($($listeners.Count) PID(s))"

    # 2. port-scoped stop of 8004 ONLY (refuse on non-llama-server holder)
    Log "stopping production llama-server on :$PortProd (port-scoped, name-checked)..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $PortProd
    $stopCode = $LASTEXITCODE
    if ($stopCode -ne 0) {
        Log "REFUS: :$PortProd not safely stoppable (stop_llama_port exit $stopCode). Aborting bench sequence."
        $results += @{ config = "all"; aborted = "8004-stop-refused"; stop_exit = $stopCode }
    } else {
        # 3. per config
        foreach ($cfg in $Configs) {
            Log "===== config $cfg ====="
            $r = Get-LauncherCheck $cfg -Silent:$true
            if ($r.Exit -ne 0) {
                if ($cfg -eq "q38-dflash2") {
                    Log "  SKIP $cfg (recorded warning): launcher -CheckOnly exit $($r.Exit) -- see output below."
                    foreach ($l in $r.Out) { Write-Host "    $l" }
                } else {
                    Log "  FAIL ${cfg}: launcher -CheckOnly exit $($r.Exit); continuing with next config."
                    foreach ($l in $r.Out) { Write-Host "    $l" }
                }
                $results += @{ config = $cfg; status = "skipped"; check_exit = $r.Exit }
                continue
            }

            # argv file (one arg per line) for the bench driver's provenance.
            $argvFile = Join-Path $OutDir "$cfg.argv.txt"
            $r.Argv | Out-File -FilePath $argvFile -Encoding ascii
            Log "  argv captured -> $argvFile ($($r.Argv.Count) tokens)"

            # b. launch the server in the background
            $serverLog = Join-Path $OutDir "$cfg-server.log"
            $launcherArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", $Launcher, "-Config", $cfg, "-LogPath", $serverLog)
            # -CtxSize passthrough to the LAUNCHER only (never the bench).
            if ($CtxSize -gt 0) {
                $launcherArgs += @("-CtxSize", "$CtxSize")
            }
            # -Ctk/-Ctv passthrough to the LAUNCHER only (never the bench).
            if ($Ctk) { $launcherArgs += @("-Ctk", $Ctk) }
            if ($Ctv) { $launcherArgs += @("-Ctv", $Ctv) }
            # -Dflash2BinaryPath passthrough: only the q38-dflash2 config is affected.
            if ($cfg -eq "q38-dflash2" -and $Dflash2BinaryPath) {
                $launcherArgs += @("-BinaryPath", $Dflash2BinaryPath)
            }
            $launchProc = Start-Process powershell.exe `
                -ArgumentList $launcherArgs `
                -PassThru -WindowStyle Hidden
            Log "  launcher started PID=$($launchProc.Id), log -> $serverLog"

            # c. health poll (<= 10 min), aborting early if the launcher exits.
            $healthUrl = "http://127.0.0.1:$PortBench/health"
            $hRes = Wait-HealthOrExit $healthUrl 600 $launchProc
            if ($hRes.Exited) {
                Log "  FAIL: launcher exited early (exit $($hRes.ExitCode)) while waiting for health at $healthUrl; aborting this config's wait."
                $results += @{ config = $cfg; status = "launcher-exited"; launcher_exit = $hRes.ExitCode; launcher_pid = $launchProc.Id }
                & powershell -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $PortBench | Out-Null
                continue
            }
            if (-not $hRes.Healthy) {
                Log "  FAIL: server did not become healthy at $healthUrl within 10 min."
                $results += @{ config = $cfg; status = "health-timeout"; launcher_pid = $launchProc.Id }
                & powershell -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $PortBench | Out-Null
                continue
            }
            Log "  server healthy."

            # d. bench driver
            # F12: derive the model path from the captured argv (the value after
            # --model) so --sha computes the real hash instead of staying null.
            $modelPath = $null
            for ($k = 0; $k -lt $r.Argv.Count - 1; $k++) {
                if ($r.Argv[$k] -eq "--model") { $modelPath = $r.Argv[$k + 1]; break }
            }
            $benchCmd = @($Bench,
                          "--port", "$PortBench",
                          "--config-label", $cfg,
                          "--argv-file", $argvFile,
                          "--reps", "3",
                          "--server-log", $serverLog,
                          "--out-dir", $OutDir,
                          "--sha")
            if ($PromptsFile) { $benchCmd += @("--prompts-file", $PromptsFile) }
            if ($modelPath) { $benchCmd += @("--model-path", $modelPath) }
            Log "  running: python $($benchCmd -join ' ')"
            & python @benchCmd
            $benchExit = $LASTEXITCODE
            Log "  bench exit=$benchExit"

            # e. stop the bench server
            & powershell -NoProfile -ExecutionPolicy Bypass -File $Stopper -Port $PortBench | Out-Null
            Log "  8005 stopped."
            # F4: a config is OK only if the bench run record carries a non-empty
            # `medians` (i.e. at least one valid rep), and only on bench exit 0.
            $recordFile = Join-Path $OutDir "run_$cfg.json"
            $hasMedians = $false
            if (Test-Path $recordFile) {
                try {
                    $rec = Get-Content $recordFile -Raw | ConvertFrom-Json
                    $hasMedians = ($null -ne $rec.medians -and
                                   $rec.medians.PSObject.Properties.Count -gt 0)
                } catch { $hasMedians = $false }
            }
            if ($benchExit -eq 0 -and $hasMedians) { $configOkCount += 1 }
            $results += @{ config = $cfg; status = "done"; bench_exit = $benchExit;
                           has_medians = $hasMedians; argv_file = $argvFile }
        }
    }
} finally {
    # 4. ALWAYS restore production
    Log "===== FINALLY: restoring production on :8004 ====="
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Restart
    $restartExit = $LASTEXITCODE
    Log "restart_production exit=$restartExit"
    $prodUrl = "http://localhost:$PortProd/health"
    $restoreOk = Wait-Health $prodUrl 600
    Log ("production restore: {0}" -f $(if ($restoreOk) { "HEALTHY" } else { "UNHEALTHY" }))

    $prodRecord = @{
        production_restored = $restoreOk
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        restart_production_exit = $restartExit
        health_url = $prodUrl
    }
    $prodRecord | ConvertTo-Json | Out-File -FilePath (Join-Path $OutDir "production_restored.json") -Encoding ascii
}

# summary
$windowReport = @{
    out_dir = $OutDir
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    results = $results
    production_restored = $restoreOk
    configs_with_results = $configOkCount
}
$windowReport | ConvertTo-Json -Depth 6 | Out-File -FilePath (Join-Path $OutDir "window_report.json") -Encoding ascii
Write-Host "===== WINDOW SUMMARY ====="
Write-Host ("production_restored : {0}" -f $restoreOk)
Write-Host ("configs with results : {0}/3" -f $configOkCount)
Write-Host ("report               : {0}" -f (Join-Path $OutDir "window_report.json"))

if (-not $restoreOk) {
    Write-Host "FATAL: production NOT restored. Investigate :8004 immediately (restart_production.ps1 by hand)."
    exit 1
}
# F4: an *attempted* config (launcher check passed -> ran on :8005) that still
# produced no bench result (bad exit or empty medians) is a real failure -- NOT
# the same as a config SKIPPED for a missing/incompatible binary. Exit nonzero
# so the outage window cannot be marked clean when a config silently produced
# nothing.
$attemptedNoResult = @($results | Where-Object { $_.status -eq "done" -and
    ($_.bench_exit -ne 0 -or -not $_.has_medians) }).Count -gt 0
if ($attemptedNoResult) {
    Write-Host "Some attempted config(s) produced no bench result -- see window_report.json (exit 2)."
    exit 2
}
if ($configOkCount -eq 0) {
    Write-Host "Restore OK, but no config produced a bench result -- see window_report.json."
    exit 2
}
exit 0
