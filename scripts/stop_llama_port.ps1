# stop_llama_port.ps1 -- stop ONLY a llama-server listening on one specific port.
#
# Port-scoped and name-checked: we find the process bound to -Port, and stop it
# ONLY if its ProcessName is "llama-server". We NEVER touch :8004 (production)
# and NEVER kill an unrelated process.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_llama_port.ps1 -Port 8005
#
# Exit codes:
#   0   a llama-server on that port was stopped, OR no listener was found.
#   1   refused: the port is held by a non-llama-server process (PID printed).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$Port
)

$ErrorActionPreference = "Continue"

# F13: fail CLOSED on a GENUINE enumeration failure, but treat an EMPTY listener
# set as "no listener found" (exit 0) -- exactly what the documented contract
# promises. Do NOT use -ErrorAction Stop here: on a port with no listener it
# THROWS a benign "no matching objects found" error, which must not be read as
# "cannot enumerate". SilentlyContinue (the repo convention, cf. cold_start.ps1)
# yields $null for an empty port; a genuine terminating error still hits the
# catch below and fails closed with exit 1.
$holders = @()
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $holders = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
} catch {
    Write-Host "REFUS (exit=1): could not enumerate listeners on :$Port ($_)."
    exit 1
}

$stopped = $false
foreach ($procId in $holders) {
    try {
        $p = Get-Process -Id $procId -ErrorAction Stop
    } catch {
        continue
    }
    if ($p.ProcessName -ieq "llama-server") {
        Write-Host "Stopping llama-server PID=$($p.Id) on :$Port"
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction Stop
            $stopped = $true
        } catch {
            Write-Host "WARN: could not stop PID=$($p.Id): $_"
        }
    } else {
        Write-Host "REFUS (exit=1): port :$Port is held by a non-llama-server process"
        Write-Host "  PID=$($p.Id) name=$($p.ProcessName). Not touching it."
        exit 1
    }
}

if (-not $stopped -and $holders.Count -eq 0) {
    Write-Host "No listener found on :$Port. Nothing to do."
} elseif (-not $stopped) {
    Write-Host "No llama-server listener on :$Port (other holders refused)."
}
exit 0