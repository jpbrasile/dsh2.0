# TEMOIN DU BRAS MINIMAL -- sans toucher au 4090.
#
# CE QU'IL VERIFIE. `bras_minimal.yml` pretend reduire dsh a deux outils et a
# une phrase de systeme. Le dump de configuration montre les rangees
# desactivees, mais une rangee desactivee n'est pas un outil retire du corps de
# requete : c'est la meme distinction que le 24/08 sur les greffons -- ce qui
# est ecrit n'est pas ce qui part.
#
# COMMENT, SANS CARTE. Le serveur temoin `temoin_echantillonnage.py` ecoute sur
# 8007 et repond LUI-MEME, sans charger de modele. On pointe l'enregistreur
# 8013 sur lui au lieu du 8005 : dsh compose sa requete complete, l'enregistreur
# la journalise (n_tools, sys_chars, noms des outils), le temoin repond une
# phrase, dsh s'arrete. Le bras GPQA garde la carte pendant ce temps.
#
# CE QUE LE TEMOIN NE DIT PAS. Rien sur la performance : la reponse est
# fabriquee. Il etablit UNIQUEMENT la composition envoyee.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$accueil = Join-Path $env:USERPROFILE '.dsh-bench-dflash2'
$journal = Join-Path $banc 'wire_temoin_minimal.jsonl'

if (Test-Path $journal) { Remove-Item $journal -Confirm:$false }

foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
}

$env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8007'
$env:PROXY_PORT = '8013'; $env:PROXY_LOG = $journal
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
    -WorkingDirectory $banc -WindowStyle Hidden `
    -RedirectStandardError (Join-Path $banc 'proxy_temoin_minimal.err') | Out-Null
Start-Sleep -Seconds 3

$env:DSH_HOME = $accueil
$env:DSH_TELEMETRY_DISABLED = '1'
$env:DSH_LOCAL_API_KEY = 'local-loopback-noauth'
$bin = Join-Path $env:USERPROFILE '.dsh\runtime\dsh-0.1.1-rc.2\node_modules\@deepseek-ai\dsh\lib\bin.js'

Write-Output '=== appel temoin ==='
node $bin --profile headless "List the files in the current directory, then stop."
Write-Output "rc=$LASTEXITCODE"

foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
}
Write-Output "journal : $journal"
