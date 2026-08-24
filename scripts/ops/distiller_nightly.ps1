# distiller_nightly.ps1 -- cablage AUTONOME du distilleur sur le Qwen local.
# Ordre utilisateur du 25/08/2026 (« cablage du distillateur en mode autonome »),
# apres la validation Phase 5 du 24/08 (docs/PHASE5.md).
#
# Ce que fait une passe (concue pour tourner la nuit, tache planifiee
# `dsh-distiller-nightly`, mais lancable a la main a tout moment) :
#   1. Serveur qwen-local :8004 -- REGLE « rendre le monde comme trouve » :
#      * un llama-server SAIN repond deja sur :8004 -> on l'utilise, on ne
#        l'arrete PAS a la fin ;
#      * sinon on le lance via start_llama_qwen_local.ps1 (sa garde GPU
#        s'applique : seul le serveur julia_gate est admis en co-residence ;
#        tout autre processus CUDA -> le lanceur refuse exit 2 et CETTE PASSE
#        EST SAUTEE -- on n'attend pas des heures la nuit, on retente la nuit
#        suivante ; on ne tue jamais rien) ; alors on l'arrete a la fin, et on
#        VERIFIE que le port est rendu (on ne l'affirme pas, on le mesure).
#   2. Distille les DEUX viviers de sessions, idempotent (les arbres deja
#      distilles sont sautes par le distilleur lui-meme) :
#      * ~/.dsh              (sessions interactives et outillees reelles)
#      * scripts/bench_julia_effort/_fumee/home  (runs de campagne)
#      Route : DISTILLER_URL locale, modele qwen-local, campagne
#      phase5/distiller-nightly, cout 0 USD au grand livre.
#   3. Journal append UTF-8 : %USERPROFILE%\dsh-distiller-nightly.log --
#      chaque passe dit FAIT / SAUTE / ECHEC avec les codes de sortie reels.
#
# Ce que cette passe ne fait JAMAIS : toucher :8005 (banc) ou :8077 (porte
# Julia) ; basculer sur une route payante en silence (serveur indisponible =
# SAUTE, pas DeepSeek) ; tuer un processus qu'elle n'a pas lance.
#
# Lecon du 25/08 (premiere passe de preuve, ECHEC silencieux) : en PowerShell
# `$home` et `$args` sont des variables AUTOMATIQUES (la boucle `foreach ($home
# ...)` ne tourne jamais) et les noms sont INSENSIBLES A LA CASSE (`$r` d'un
# Invoke-WebRequest a ecrase `$R`, le chemin du depot, et l'arret du serveur a
# echoue pendant que le journal disait « arrete »). D'ou : noms longs uniques
# ($DEPOT, $rep, $vivier, $argsDistiller) et arret VERIFIE port en main.
[CmdletBinding()]
param(
    [string]$Depuis = "",     # AAAA-MM-JJ optionnel : borner une passe manuelle
    [int]$SanteDelai = 240    # secondes max d'attente du /health apres lancement
)

$DEPOT = "C:\Users\test\Documents\dsh2.0"
$JOURNAL = "$env:USERPROFILE\dsh-distiller-nightly.log"
function Ecrire([string]$m) {
    $ligne = ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m)
    Write-Host $ligne
    Add-Content -LiteralPath $JOURNAL -Value $ligne -Encoding UTF8
}

Ecrire "=== passe distiller-nightly ==="

# --- 1. serveur : trouve ou lance -------------------------------------------
$dejaLa = $false
try {
    $rep = Invoke-WebRequest -Uri "http://127.0.0.1:8004/health" -UseBasicParsing -TimeoutSec 3
    if ($rep.StatusCode -eq 200) { $dejaLa = $true }
} catch {}

$lanceur = $null
if ($dejaLa) {
    Ecrire "serveur :8004 deja sain -- utilise tel quel, ne sera PAS arrete"
} else {
    Ecrire "serveur :8004 absent -- lancement via start_llama_qwen_local.ps1"
    $lanceur = Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "$DEPOT\scripts\start_llama_qwen_local.ps1"
    ) -PassThru -WindowStyle Hidden
    $t0 = Get-Date
    $sain = $false
    while (((Get-Date) - $t0).TotalSeconds -lt $SanteDelai) {
        if ($lanceur.HasExited) { break }   # garde GPU a refuse (exit 2/3/4)
        try {
            $rep = Invoke-WebRequest -Uri "http://127.0.0.1:8004/health" -UseBasicParsing -TimeoutSec 2
            if ($rep.StatusCode -eq 200) { $sain = $true; break }
        } catch {}
        Start-Sleep -Seconds 3
    }
    if (-not $sain) {
        if ($lanceur.HasExited) {
            Ecrire ("SAUTE : lanceur refuse/mort, exit " + $lanceur.ExitCode + " (GPU occupe par un tiers ? artefact absent ?) -- retenter la nuit suivante")
        } else {
            Ecrire "ECHEC : serveur muet apres $SanteDelai s -- arret du lanceur et abandon de la passe"
            & powershell -NoProfile -ExecutionPolicy Bypass -File "$DEPOT\scripts\stop_llama_port.ps1" -Port 8004 | Out-Null
        }
        exit 2
    }
    Ecrire "serveur pret (lance par cette passe, sera arrete a la fin)"
}

# --- 2. distillation des deux viviers ---------------------------------------
$env:DISTILLER_URL      = "http://127.0.0.1:8004/v1/chat/completions"
$env:DISTILLER_CAMPAGNE = "phase5/distiller-nightly"
$codes = @()
foreach ($vivier in @("$env:USERPROFILE\.dsh", "$DEPOT\scripts\bench_julia_effort\_fumee\home")) {
    if (-not (Test-Path "$vivier\sessions")) { Ecrire "vivier absent, saute : $vivier"; continue }
    $argsDistiller = @("$DEPOT\harness\distiller.py", "--home", $vivier, "--modele", "qwen-local")
    if ($Depuis) { $argsDistiller += @("--depuis", $Depuis) }
    Ecrire ("distille : " + $vivier + $(if ($Depuis) { " (depuis $Depuis)" } else { "" }))
    & python @argsDistiller 2>&1 | ForEach-Object { Add-Content -LiteralPath $JOURNAL -Value ("    " + $_) -Encoding UTF8 }
    $codes += $LASTEXITCODE
    Ecrire ("  exit=" + $LASTEXITCODE + "  (0 fait, 1 aucun journal, 2 appel LLM en echec -- scores ecrits quand meme)")
}

# --- 3. rendre le monde comme trouve (et le VERIFIER) ------------------------
if (-not $dejaLa) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$DEPOT\scripts\stop_llama_port.ps1" -Port 8004 |
        ForEach-Object { Add-Content -LiteralPath $JOURNAL -Value ("    " + $_) -Encoding UTF8 }
    Start-Sleep -Seconds 2
    $tenu = Get-NetTCPConnection -LocalPort 8004 -State Listen -ErrorAction SilentlyContinue
    if ($tenu) {
        Ecrire ("ECHEC ARRET : :8004 encore tenu par PID " + (($tenu | Select-Object -ExpandProperty OwningProcess -Unique) -join ",") + " -- VRAM non rendue, intervention manuelle requise")
        exit 4
    }
    Ecrire "serveur arrete, :8004 verifie libre"
}

if ($codes.Count -eq 0) {
    Ecrire "=== ECHEC : AUCUN vivier traite (bug ou chemins absents) ==="
    exit 3
}
$pire = ($codes | Measure-Object -Maximum).Maximum
Ecrire ("=== passe finie, viviers=" + $codes.Count + " pire exit=" + $pire + " ===")
exit $(if ($pire -le 1) { 0 } else { $pire })
