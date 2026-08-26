# Relance le llama-server avec un budget de pensee donne, APPARIE au message.
#
# Le message vient de message_transition.txt, un fichier unique lu par tous les
# bras. C'est volontaire : si chaque bras portait sa propre copie du texte,
# rien ne garantirait qu'ils soient identiques, et la comparaison entre budgets
# ne vaudrait plus rien. Un octet de difference et on compare deux dispositifs.
#
# Le texte ne passe JAMAIS par un -ArgumentList. Premier essai le 26/08 :
# Start-Process a re-decoupe le message sur les espaces et le mot « is » s'est
# retrouve lie a -Port ("Impossible de convertir la valeur is en Int32") ;
# serveur a terre, aucun bras en vol. Ici il reste une variable PowerShell
# jusqu'a l'appel du lanceur, qui lie une seule valeur.

param(
    [Parameter(Mandatory = $true)][int]$Budget
)

$ErrorActionPreference = "Continue"
$banc  = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$fichierMsg = Join-Path $banc "message_transition.txt"

if ($Budget -le 0) {
    Write-Output "REFUS : ce script ne sert qu'aux budgets > 0 (recu $Budget)."
    exit 9
}
if (-not (Test-Path $fichierMsg)) {
    Write-Output "REFUS : message_transition.txt introuvable. Un budget nu"
    Write-Output "  mesure PIRE que pas de raisonnement du tout (78 % / 88 %)."
    exit 8
}
# .Trim() : le fichier finit par un saut de ligne, et un saut de ligne dans un
# argument survit a PowerShell mais pas forcement a la ligne de commande native
# que CreateProcess reconstruit.
$msg = (Get-Content -LiteralPath $fichierMsg -Raw -Encoding UTF8).Trim()
if (-not $msg) { Write-Output "REFUS : message vide."; exit 8 }

# --- arreter le serveur en place -------------------------------------------
# Le lanceur refuse de partir si le GPU est occupe (son garde-fou tourne AVANT
# sa section d'arret par port) : il faut donc liberer la carte d'abord.
$srv = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue
if ($srv) {
    foreach ($s in $srv) {
        Write-Output "arret du llama-server PID $($s.ProcessId)"
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $t = 0
    while ((Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue) -and $t -lt 120) {
        Start-Sleep -Seconds 2; $t += 2
    }
    Write-Output "carte liberee apres $t s"
}

# --- enveloppe fille --------------------------------------------------------
$fils = Join-Path $banc "_relance_budget_courant_fils.ps1"
$corps = @"
`$msg = (Get-Content -LiteralPath "$fichierMsg" -Raw -Encoding UTF8).Trim()
& "C:\Users\test\Documents\dsh2.0\scripts\start_llama_qwen38_27b_specdec.ps1" ``
    -Config q38-dflash2 ``
    -BinaryPath "C:\Users\test\tools\llama-cpp\src-dflash2\build-faq\bin\Release\llama-server.exe" ``
    -CtxSize 163840 ``
    -Ctk q8_0 -Ctv q4_0 ``
    -SpecDraftNMax 7 ``
    -AssumeDflash2Capable ``
    -ReasoningBudget $Budget ``
    -ReasoningBudgetMessage `$msg
"@
Set-Content -LiteralPath $fils -Value $corps -Encoding utf8

$log = Join-Path $banc ("relance_budget{0}.log" -f $Budget)
$p = Start-Process -FilePath "powershell.exe" `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru
Write-Output "enveloppe detachee PID $($p.Id), journal $log"

# --- attendre que le modele soit charge ------------------------------------
$t = 0
while ($t -lt 600) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 5 | Out-Null
        break
    } catch { Start-Sleep -Seconds 5; $t += 5 }
}
if ($t -ge 600) { Write-Output "ECHEC : serveur toujours injoignable apres 600 s."; exit 4 }
Write-Output "serveur vivant apres $t s"

# --- verifier sur l'ARGV DU PROCESSUS VIVANT, pas sur le script ------------
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch ("--reasoning-budget\s+" + [regex]::Escape("$Budget"))) {
    Write-Output "ECHEC : le serveur vivant ne porte PAS --reasoning-budget $Budget."
    Write-Output "  argv : $argv"
    exit 3
}
if ($argv -notmatch '--reasoning-budget-message') {
    Write-Output "ECHEC : budget $Budget present mais SANS message de transition."
    exit 5
}
Write-Output "VERIFIE sur le processus vivant : budget $Budget + message."
