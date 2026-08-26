# Lance un bras de reglage a POSITION TOURNANTE : 198 questions, 1 appel
# chacune, la position de la bonne reponse tournant entre les questions.
#
# Voir PRE_ENREGISTREMENT_BUDGET.md, revision 1, pour le plan et les regles de
# lecture arretees AVANT les donnees.
#
# NE PAS confondre avec --rotations 1, qui prendrait la rotation 0 de CHAQUE
# question, c'est-a-dire la bonne reponse en A pour les 198 : ce ne serait pas
# retirer le controle de position mais le remplacer par un confondant.

param(
    [Parameter(Mandatory = $true)][int]$Budget,
    [Parameter(Mandatory = $true)][string]$Sortie
)

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc ("run_" + [IO.Path]::GetFileNameWithoutExtension($Sortie) + ".log")

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4' }
if ($py) { Write-Output "REFUS : un run local tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 10 | Out-Null
} catch {
    Write-Output "REFUS : llama-server injoignable sur 8005 -- ne pas lancer a vide."; exit 2
}

# Le seul temoin qui compte est le processus vivant. Un lanceur peut echouer en
# silence et laisser l'ancien serveur en place -- arrive le 26/08 a 13:37, et
# indistinguable d'une reussite depuis /props.
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch ("--reasoning-budget\s+" + [regex]::Escape("$Budget"))) {
    Write-Output "REFUS : le serveur vivant ne porte PAS --reasoning-budget $Budget."
    Write-Output "  argv : $argv"
    exit 3
}
if ($argv -notmatch '--reasoning-budget-message') {
    Write-Output "REFUS : budget $Budget sans message de transition."
    Write-Output "  Une coupure nue mesure pire que pas de raisonnement du tout."
    exit 4
}
Write-Output "verifie sur le processus vivant : budget $Budget + message."

$fils = Join-Path $banc ("_run_" + [IO.Path]::GetFileNameWithoutExtension($Sortie) + "_fils.ps1")
$corps = @"
Set-Location "$banc"
python gpqa_diamond.py $Sortie ``
    --rotation-tournante --max-tokens 16384 --parallele 1 ``
    --temperature 1.0 --top-p 0.95 ``
    --extra-fichier extra_local.json
Write-Output "=== exit : `$LASTEXITCODE ==="
"@
Set-Content -LiteralPath $fils -Value $corps -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "bras tournant budget $Budget lance DETACHE (PID $($p.Id))"
Write-Output "  journal : $log"
Write-Output "  sortie  : $Sortie"
