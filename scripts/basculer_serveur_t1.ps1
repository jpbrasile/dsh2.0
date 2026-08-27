# BASCULE DU SERVEUR : dflash2 + temperature 1.0 (valeur de carte, thinking).
#
# ORDRE OPERATEUR, 27/08 07:10 : « il faut le setting optimal pour qwen3.8 avec
# temperature = 1, passe en dflash et relance tous les tests ».
#
# CE QUI CHANGE, ET RIEN D'AUTRE. L'argv sortant est identique a celui du
# serveur vivant sauf `--temp` : 0.6 -> 1.0. Verifie par -CheckOnly avant
# d'arreter quoi que ce soit.
#
# POURQUOI. Ni `pilote.py` ni `cabler_local_mesure.py` n'envoient de
# temperature : le defaut serveur s'appliquait, donc le bras variante D tournait
# a 0,6 -- alors que le run aider de REFERENCE force 1.0 (pilote.py:37). Cet
# ecart n'etait declare nulle part. La carte Qwen3.8-27B en thinking publie
# 1.0 / 0.95 / 20 / 0.0 / 0.0 / 1.0 ; le reste de l'argv les portait deja.
#
# CE QUE CETTE BASCULE INVALIDE, et il faut le dire : tout ce qui a ete mesure
# a 0,6 sur le bras pi -- `pi_dimD2` (plain), `pi_dimD2_dflash2`, et les 4
# exercices de B6. Aucun de ces chiffres ne se compare au run qui suit.
#
# RESSOURCE PARTAGEE : le script REFUSE de tuer le serveur si un banc tourne
# encore (pilote polyglot ou bras GPQA). Il n'attend pas, il refuse -- a
# l'operateur de decider.

$ErrorActionPreference = 'Stop'

$lanceur = 'C:\Users\test\Documents\dsh2.0\scripts\start_llama_qwen38_27b_specdec.ps1'
$binaire = 'C:\Users\test\tools\llama-cpp\src-dflash2\build-faq\bin\Release\llama-server.exe'
# Table de hachage, PAS un tableau : le splat par tableau passe les elements en
# POSITIONNEL, et '-Config' se retrouve pris pour la valeur de $Config.
$argsLanceur = @{
    Config        = 'q38-dflash2'
    BinaryPath    = $binaire
    CtxSize       = 163840
    Ctk           = 'q8_0'
    Ctv           = 'q4_0'
    SpecDraftNMax = 7
    Parallel      = 1
}

# --- 1. personne d'autre sur la carte ---------------------------------------
$occupants = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'pilote\.py|gpqa_diamond' }
if ($occupants) {
    Write-Output 'REFUS : un banc utilise encore la carte.'
    foreach ($o in $occupants) { Write-Output ("  PID {0} : {1}" -f $o.ProcessId, $o.CommandLine.Substring(0, [Math]::Min(160, $o.CommandLine.Length))) }
    exit 5
}
Write-Output 'aucun banc en cours : la carte est libre.'

# --- 2. l'argv sortant, AVANT de casser quoi que ce soit ---------------------
Write-Output ''
Write-Output '=== controle a blanc de l argv sortant ==='
# `*>&1` et pas `2>&1` : le lanceur ecrit par Write-Host, donc sur le flux
# d'information (6), pas sur la sortie succes. Avec `2>&1` la capture etait vide
# et le controle a blanc echouait alors que l'argv etait bon.
$sortie = & $lanceur @argsLanceur -CheckOnly *>&1
$ligne = $sortie | Where-Object { $_ -match '^\s*"?C:\\Users\\test\\tools\\llama-cpp.*--model' } | Select-Object -First 1
if (-not $ligne) { Write-Output 'REFUS : -CheckOnly n a pas rendu d argv.'; $sortie | Select-Object -Last 12; exit 4 }
if ($ligne -notmatch '--temp 1\.0') { Write-Output 'REFUS : l argv sortant ne porte pas --temp 1.0.'; exit 4 }
if ($ligne -notmatch 'draft-dflash') { Write-Output 'REFUS : l argv sortant ne porte pas dflash.'; exit 4 }
Write-Output '  --temp 1.0 et draft-dflash confirmes.'

# --- 3. arret de l ancien serveur -------------------------------------------
$anciens = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'"
foreach ($a in $anciens) {
    Write-Output ("arret du serveur PID {0}" -f $a.ProcessId)
    Stop-Process -Id $a.ProcessId -Force -Confirm:$false
}
Start-Sleep -Seconds 5

# --- 4. relance DETACHEE ------------------------------------------------------
# Un lanceur en avant-plan meurt avec le terminal, et le serveur avec lui.
$argLigne = (($argsLanceur.GetEnumerator() | ForEach-Object { "-$($_.Key) `"$($_.Value)`"" }) -join ' ')
$p = Start-Process -FilePath 'powershell' `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$lanceur`" $argLigne" `
    -WindowStyle Hidden -PassThru
Write-Output ("lanceur detache, PID {0}" -f $p.Id)

# --- 5. attente de disponibilite ---------------------------------------------
$pret = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8005/v1/models' -UseBasicParsing -TimeoutSec 4
        if ($r.StatusCode -eq 200) { $pret = $true; break }
    } catch { }
}
if (-not $pret) { Write-Output 'ECHEC : le serveur n a pas repondu en 10 min.'; exit 7 }
Write-Output ("serveur pret a {0}" -f (Get-Date -Format 'HH:mm:ss'))

Write-Output ''
Write-Output '=== argv du serveur VIVANT ==='
(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").CommandLine

Write-Output ''
& 'C:\Windows\System32\nvidia-smi.exe' --query-gpu=memory.used,memory.free --format=csv,noheader
