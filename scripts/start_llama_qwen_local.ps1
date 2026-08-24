# start_llama_qwen_local.ps1 -- Phase 5 (README case "Local Qwen serving"), 2026-08-24.
# Serveur llama.cpp de PRODUCTION locale sur :8004 -- la route dsh `qwen-local`.
# Le banc specdec (:8005) et la porte Julia (:8077) ne sont JAMAIS touches.
#
# Herite du patron de start_llama_qwen38_27b_specdec.ps1 (garde GPU fail-closed,
# -CheckOnly, log UTF-8 via cmd.exe) avec UNE difference de garde, motivee :
#   Le serveur julia_gate (un julia.exe qui possede le port 8077) garde un
#   contexte CUDA en permanence (556 MiB mesures le 24/08) -- la garde "aucun
#   processus CUDA" du banc refuserait DONC TOUJOURS ici. Politique de cette
#   garde-ci : le SEUL resident admis est le PID qui possede le port 8077 en
#   LISTEN ; tout autre processus CUDA => REFUS exit 2 (on attend, on ne tue
#   jamais). nvidia-smi absent/en echec => REFUS exit 3 (fail closed).
#
# Budget VRAM mesure (banc specdec, meme binaire, meme modele, f16/f16) :
#   ctx 32768 -> 19232 MiB + ~556 MiB (gate) = ~19.8 Go sur 24 Go.
#   Marge pour les rejeux CUDA de la porte : ~4.7 Go. Si un rejeu de porte
#   echoue en OOM pendant que ce serveur tourne, ARRETER CE SERVEUR d'abord
#   (scripts\stop_llama_port.ps1 -Port 8004), jamais la porte.
#
# KV f16/f16 NON NEGOCIABLE par defaut : quantifier le KV a coute un
# effondrement 60x du prefill au-dela de ~10k de contexte (mesure 21/08,
# details dans start_llama_qwen38_27b_specdec.ps1).
#
# -Embeddings est OPT-IN et ajoute `--embeddings --pooling last` a l'argv.
# MESURE avant de s'y fier : selon le build, --embeddings sur un modele causal
# peut degrader ou casser la generation ; la validation Phase 5 mesure les DEUX
# endpoints sur le meme processus et ecrit le resultat dans docs/PHASE5.md.
#
# Usage :
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen_local.ps1 -CheckOnly
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen_local.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_qwen_local.ps1 -Embeddings
#   scripts\stop_llama_port.ps1 -Port 8004        # arret (nomme, port-scope)
#
# Codes de sortie (contrat identique au banc) :
#   0  gardes + artefacts OK (et argv imprime si -CheckOnly)
#   2  refus : un processus CUDA AUTRE que le serveur julia_gate tient le GPU
#   3  refus : etat GPU indeterminable (nvidia-smi absent ou en echec)
#   4  refus : artefact manquant, ou port tenu par un non-llama-server
[CmdletBinding()]
param(
    [string]$ModelPath = "C:\Users\test\models\qwen38-27b\Qwen3.8-27B-Q4_K_M.gguf",
    [string]$BinaryPath = "C:\Users\test\tools\llama-cpp\llama-cuda-b10488\llama-server.exe",
    [int]$Port = 8004,
    [int]$CtxSize = 32768,
    [switch]$Embeddings,
    [string]$LogPath,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Continue"
$alias = "qwen-local"
$log = if ($LogPath) { $LogPath } else { "$env:USERPROFILE\llama-server-qwen-local.log" }

# --- (a) garde GPU : seul le serveur julia_gate (port 8077) est admis --------
$smi = (Get-Command nvidia-smi -ErrorAction SilentlyContinue).Source
if (-not $smi) {
    if ($CheckOnly) { Write-Host "WARN (GPU) : nvidia-smi introuvable (CheckOnly : on continue)" }
    else { Write-Host "REFUS (exit 3) : nvidia-smi introuvable ; etat GPU inconnu."; exit 3 }
} else {
    $raw = & $smi --query-compute-apps=pid --format=csv,noheader
    if ($LASTEXITCODE -ne 0) {
        if ($CheckOnly) { Write-Host "WARN (GPU) : nvidia-smi en echec (CheckOnly : on continue)" }
        else { Write-Host "REFUS (exit 3) : nvidia-smi en echec (exit $LASTEXITCODE)."; exit 3 }
    } else {
        $cudaPids = @($raw | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -ne "" })
        $gatePids = @(Get-NetTCPConnection -LocalPort 8077 -State Listen -ErrorAction SilentlyContinue |
                      Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { "$_" })
        $etrangers = @($cudaPids | Where-Object { $gatePids -notcontains $_ })
        if ($etrangers.Count -gt 0) {
            $liste = ($etrangers | ForEach-Object {
                $p = Get-Process -Id ([int]$_) -ErrorAction SilentlyContinue
                if ($p) { "PID $_ ($($p.ProcessName))" } else { "PID $_" }
            }) -join ", "
            if ($CheckOnly) { Write-Host "WARN (GPU) : processus CUDA etranger(s) : $liste (CheckOnly : on continue)" }
            else {
                Write-Host "REFUS (exit 2) : GPU occupe par un processus CUDA etranger : $liste."
                Write-Host "  Seul le serveur julia_gate (proprietaire du port 8077) est admis en co-residence."
                Write-Host "  On attend ; on ne tue jamais un processus tiers."
                exit 2
            }
        } elseif ($cudaPids.Count -gt 0) {
            Write-Host "Garde GPU : resident(s) CUDA = le serveur julia_gate ($($cudaPids -join ',')). OK."
        } else {
            Write-Host "Garde GPU : aucun processus CUDA. OK."
        }
    }
}

# --- (b) artefacts (fail closed, exit 4) ------------------------------------
$missing = @()
if (-not (Test-Path $BinaryPath)) { $missing += "binaire ($BinaryPath)" }
if (-not (Test-Path $ModelPath))  { $missing += "modele ($ModelPath)" }
if ($missing.Count -gt 0) {
    Write-Host "REFUS (exit 4) : artefact(s) manquant(s) :"
    foreach ($m in $missing) { Write-Host "  - $m" }
    exit 4
}

# --- (c) argv effectif ------------------------------------------------------
# Echantillonnage : les recommandations Qwen3.8 non-thinking (identiques au banc).
$cmdArgs = @(
    "--model", $ModelPath,
    "--host",  "127.0.0.1",
    "--port",  $Port,
    "--ctx-size", $CtxSize,
    "--flash-attn",   "on",
    "--cache-type-k", "f16",
    "--cache-type-v", "f16",
    "--batch-size",   "2048",
    "--ubatch-size",  "512",
    "--n-gpu-layers", "99",
    "--parallel",     "1",
    "--jinja",
    "--reasoning-format", "none",
    "--reasoning-budget", "512",
    "--temp",             "0.6",
    "--top-k",            "20",
    "--top-p",            "0.95",
    "--min-p",            "0",
    "--presence-penalty", "0.0",
    "--repeat-penalty",   "1.0",
    "--alias", $alias
)
if ($Embeddings) { $cmdArgs += @("--embeddings", "--pooling", "last") }

if ($CheckOnly) {
    Write-Host "===== qwen-local -CheckOnly : gardes + artefacts PASSES ====="
    Write-Host "binaire : $BinaryPath"
    Write-Host "modele  : $ModelPath"
    Write-Host "port    : $Port  ctx : $CtxSize  embeddings : $(if ($Embeddings) { 'ON (--pooling last)' } else { 'off' })"
    Write-Host "log     : $log"
    Write-Host ""
    Write-Host "argv effectif (une ligne par argument) :"
    foreach ($a in @($BinaryPath) + $cmdArgs) { Write-Host ('  "{0}"' -f $a) }
    Write-Host ""
    Write-Host "(CheckOnly -- rien n'est lance. :8005 et :8077 intouches.)"
    exit 0
}

# --- (d) arret port-scope, nomme, sur LE port cible seulement ---------------
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        try {
            $p = Get-Process -Id $_ -ErrorAction Stop
            if ($p.ProcessName -ieq "llama-server") {
                Write-Host "Arret du llama-server precedent PID=$($p.Id) sur :$Port"
                Stop-Process -Id $p.Id -Force
            } else {
                Write-Host "REFUS (exit 4) : port $Port tenu par un non-llama-server PID=$($p.Id) ($($p.ProcessName))."
                exit 4
            }
        } catch {}
    }
Start-Sleep -Seconds 2

# --- (e) lancement, log UTF-8 (patron mesure du banc : cmd.exe merge + tee main)
Write-Host "===== lancement qwen-local sur :$Port ====="
Write-Host "Verifier le serveur QUI TOURNE (pas le log) une fois pret :"
Write-Host "  curl -s http://127.0.0.1:$Port/props"
Write-Host "  nvidia-smi --query-gpu=memory.used --format=csv"
$quoted  = $cmdArgs | ForEach-Object { if ("$_" -match "[ \t]") { '"' + $_ + '"' } else { "$_" } }
$cmdLine = '"' + $BinaryPath + '" ' + ($quoted -join ' ') + ' 2>&1'
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
& cmd.exe /c $cmdLine | ForEach-Object {
    Write-Host $_
    Add-Content -LiteralPath $log -Value $_ -Encoding UTF8
}
exit $LASTEXITCODE
