# Lance GPQA Diamond sur le Q4 local (:8005), DETACHE.
#
# Detache parce que cette nuit trois taches de fond ont ete tuees avec leur
# terminal. Ce qui a survecu, c'est ce qui n'en dependait pas.
#
# Le script ne prend pas la carte de force : il REFUSE de partir si un banc
# tourne deja ou si rien n'ecoute sur :8005.
#
# Les reglages de generation passent par extra_local.json et NON par un
# argument en ligne de commande : mesure du 26/08, PowerShell a coupe
# '{"top_k": 20}' en deux arguments et le run est sorti en code 2.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_local.log"

$held = Get-NetTCPConnection -LocalPort 8005 -State Listen -ErrorAction SilentlyContinue
if (-not $held) { Write-Output "REFUS : rien n'ecoute sur :8005."; exit 3 }

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'bench\.py|pilote\.py|gpqa_diamond\.py' }
if ($py) { Write-Output "REFUS : un banc tourne deja (PID $($py.ProcessId))."; exit 2 }

$fils = Join-Path $banc "_run_local_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4.jsonl --rotations 4 --max-tokens 16384 --parallele 1 --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "GPQA local lance DETACHE (PID $($p.Id)) -- journal : $log"
