# Relance le llama-server SANS budget de pensee (-1), dans la config demandee.
#
# A QUOI IL SERT. Deux choses, et c'est pour ca qu'il existe a cote de
# relance_serveur_budget.ps1 (qui, lui, refuse tout budget <= 0) :
#   1. la sonde de losslessness du specdec, qui a besoin des deux configs
#      -- q38-plain puis q38-dflash2 -- avec TOUT LE RESTE IDENTIQUE ;
#   2. le bras de production GPQA, arrete a budget -1 par la revision 4 du
#      pre-enregistrement (un bras qui ampute 45 a 64 % de ses appels ne
#      fournit pas « un chiffre GPQA du modele »).
#
# LE MEME BINAIRE DES DEUX COTES. -BinaryPath pointe sur le build src-dflash2
# meme en q38-plain. Comparer le build dflash2 avec speculation au build
# standard sans speculation ferait varier deux choses a la fois et la sonde ne
# dirait plus rien. Ici une seule ligne d'argv change : la speculation.
#
# PAS DE MESSAGE DE TRANSITION, ET C'EST CORRECT. Un message n'a de sens
# qu'apparie a un budget qui coupe. A budget -1 rien ne coupe : le lanceur
# n'exige le message que pour un budget > 0 (son exit 8).
#
# LE PIEGE DU 26/08, EVITE ICI COMME DANS LE JUMEAU. Le lanceur fait tourner
# son garde-fou « GPU occupe » AVANT sa section d'arret par port : lance sur une
# carte occupee il refuse, l'ancien serveur survit, /props repond normalement et
# la relance ressemble a une reussite. D'ou : on arrete d'abord, on attend la
# carte, et on VERIFIE sur l'argv du processus vivant -- jamais sur le script.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File relance_serveur_illimite.ps1 -Config q38-dflash2

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("q38-plain", "q38-dflash2")]
    [string]$Config
)

$ErrorActionPreference = "Continue"
$banc    = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$lanceur = "C:\Users\test\Documents\dsh2.0\scripts\start_llama_qwen38_27b_specdec.ps1"
$binaire = "C:\Users\test\tools\llama-cpp\src-dflash2\build-faq\bin\Release\llama-server.exe"

if (-not (Test-Path $lanceur)) { Write-Output "REFUS : lanceur introuvable."; exit 2 }
if (-not (Test-Path $binaire)) { Write-Output "REFUS : binaire introuvable."; exit 2 }

# --- ressource partagee : qui d'autre tient la carte ? ---------------------
# On n'arrete QUE des llama-server. Tout autre calcul CUDA vivant fait echouer
# la relance : un banc de plusieurs heures n'ecrit son point de reprise qu'a la
# sortie propre, et il n'est jamais a nous de le decider.
$autres = & nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>$null
foreach ($ligne in $autres) {
    if (-not $ligne) { continue }
    if ($ligne -match 'llama-server|explorer\.exe|WidgetBoard|Notepad|WhatsApp|Insufficient Permissions') { continue }
    Write-Output "REFUS : un autre calcul occupe la carte -> $ligne"
    exit 7
}

# --- arreter le serveur en place -------------------------------------------
$srv = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue
if ($srv) {
    foreach ($s in $srv) {
        Write-Output "arret du llama-server PID $($s.ProcessId) (lance par cette campagne)"
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $t = 0
    while ((Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue) -and $t -lt 120) {
        Start-Sleep -Seconds 2; $t += 2
    }
    Write-Output "carte liberee apres $t s"
}

# --- enveloppe fille, detachee ---------------------------------------------
# Le lanceur tee en foreground et meurt avec son terminal (constate 25/08 puis
# 26/08) : la relance est obligatoirement detachee, sortie redirigee.
# Deux branches ENTIERES plutot qu'un fragment interpole : un fragment vide
# laisserait une ligne blanche apres une continuation par backtick, ce qui
# coupe la commande en deux en silence.
$fils = Join-Path $banc ("_relance_illimite_{0}_fils.ps1" -f $Config)
if ($Config -eq "q38-dflash2") {
    $corps = @"
& "$lanceur" ``
    -Config q38-dflash2 ``
    -BinaryPath "$binaire" ``
    -CtxSize 163840 ``
    -Ctk q8_0 -Ctv q4_0 ``
    -SpecDraftNMax 7 ``
    -AssumeDflash2Capable ``
    -ReasoningBudget -1
"@
} else {
    $corps = @"
& "$lanceur" ``
    -Config q38-plain ``
    -BinaryPath "$binaire" ``
    -CtxSize 163840 ``
    -Ctk q8_0 -Ctv q4_0 ``
    -ReasoningBudget -1
"@
}
Set-Content -LiteralPath $fils -Value $corps -Encoding utf8

$log = Join-Path $banc ("relance_illimite_{0}.log" -f $Config)
$p = Start-Process -FilePath "powershell.exe" `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru
Write-Output "enveloppe detachee PID $($p.Id), journal $log"

# --- attendre le chargement ------------------------------------------------
$t = 0
while ($t -lt 600) {
    try { Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 5 | Out-Null; break }
    catch { Start-Sleep -Seconds 5; $t += 5 }
}
if ($t -ge 600) {
    Write-Output "ECHEC : serveur injoignable apres 600 s. Voir $log et $log.err"
    exit 4
}
Write-Output "serveur vivant apres $t s"

# --- verifier sur l'ARGV DU PROCESSUS VIVANT -------------------------------
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch '--reasoning-budget\s+-1') {
    Write-Output "ECHEC : le serveur vivant ne porte PAS --reasoning-budget -1."
    Write-Output "  argv : $argv"
    exit 3
}
if ($argv -match '--reasoning-budget-message') {
    Write-Output "ECHEC : un message de transition est present sans budget qui coupe."
    exit 5
}
$aSpec = ($argv -match '--spec-type')
if ($Config -eq "q38-dflash2" -and -not $aSpec) {
    Write-Output "ECHEC : q38-dflash2 demande mais aucun --spec-type dans l'argv."
    exit 6
}
if ($Config -eq "q38-plain" -and $aSpec) {
    Write-Output "ECHEC : q38-plain demande mais --spec-type present dans l'argv."
    exit 6
}
Write-Output "VERIFIE sur le processus vivant : budget -1, config $Config, speculation $aSpec."
Write-Output "argv : $argv"
