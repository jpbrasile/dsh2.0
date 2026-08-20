<#
.SYNOPSIS
  Lanceur DSH (DeepSeek Harness rc.7) : prepare les 3 ingredients puis boote un profil.

.DESCRIPTION
  DSH n'a ni --cwd, ni --model, ni --base-url. Tout passe par :
    1. le REPERTOIRE COURANT      -> espace de travail + cle des sessions
    2. l'ENV du process           -> resout les references apiKeyEnv de settings.yaml
    3. ~/.dsh/settings.yaml       -> les routes (local / openrouter / openrouter-cheap)
  Ce script fait 1 et 2, puis lance. Il ne touche jamais a settings.yaml.

  La cle OpenRouter est lue depuis le .env du depot et posee UNIQUEMENT dans l'env
  de ce process. Elle n'est jamais affichee, jamais ecrite ailleurs.

.EXAMPLE
  .\scripts\dsh.ps1
  Ouvre l'UI de chat sur http://127.0.0.1:8010, espace de travail = dossier courant.

.EXAMPLE
  .\scripts\dsh.ps1 -Workspace C:\projets\essai -Cheap
  Demarre le proxy "upstream le moins cher" s'il ne tourne pas, puis l'UI sur ce dossier.

.EXAMPLE
  .\scripts\dsh.ps1 -Ask "ecris un script python qui renomme les .txt en .md"
  Une seule tache, pas d'UI, rend la main quand c'est fini.

.EXAMPLE
  .\scripts\dsh.ps1 -Stop
  Arrete l'UI (et le proxy s'il tourne).
#>
[CmdletBinding()]
param(
    [string] $Ask,                                   # tache one-shot (profil headless)
    [string] $Workspace,                             # defaut : repertoire courant
    [int]    $Port = 8010,                           # port de l'UI web
    [int]    $ProxyPort = 8011,                      # port du proxy "moins cher"
    [switch] $Cheap,                                 # demarre le proxy s'il est absent
    [switch] $NoOpen,                                # ne pas ouvrir le navigateur
    [switch] $Stop,                                  # arreter UI + proxy
    [switch] $Help                                   # afficher l'aide et sortir
)

$ErrorActionPreference = 'Stop'
$DshVersion = '0.1.0-rc.7'
$RepoRoot   = Split-Path -Parent $PSScriptRoot

# --- -Help : on affiche et on sort, sans rien toucher -----------------------
if ($Help) {
    Write-Host ("dsh.ps1 -- lanceur DeepSeek Harness (paquet epingle @deepseek-ai/dsh@{0})" -f $DshVersion)
    $usage = @'

USAGE
  .\scripts\dsh.ps1 [-Workspace <dir>] [-Port <n>] [-Cheap] [-NoOpen]
  .\scripts\dsh.ps1 -Ask "<tache>" [-Workspace <dir>]
  .\scripts\dsh.ps1 -Stop [-Port <n>] [-ProxyPort <n>]
  .\scripts\dsh.ps1 -Help

PARAMETRES
  -Workspace <dir>  Espace de travail. Defaut : le repertoire courant.
                    DSH n'a PAS de --cwd : ce dossier est a la fois ce que l'agent
                    voit et la cle sous laquelle tes sessions sont rangees.
  -Ask "<tache>"    Une seule tache (profil headless), pas d'UI, rend la main a la fin.
                    Sans -Ask, ouvre l'UI de chat.
  -Port <n>         Port de l'UI web. Defaut 8010.
  -Cheap            Demarre le proxy "upstream le moins cher" (scripts/openrouter_
                    cheapest_proxy.mjs) s'il ne tourne pas deja. Requis par la route
                    openrouter-cheap.
  -ProxyPort <n>    Port de ce proxy. Defaut 8011.
  -NoOpen           Ne pas ouvrir le navigateur automatiquement.
  -Stop             Arrete l'UI et le proxy, puis sort.
  -Help             Ceci.

CE QUE LE SCRIPT PREPARE POUR TOI
  1. le repertoire de travail          (-Workspace, sinon le courant)
  2. l'environnement                    DSH_TELEMETRY_DISABLED=1, DSH_LOCAL_API_KEY,
                                        et OPENROUTER_API_KEY lue depuis le .env du
                                        depot -- jamais affichee, jamais recopiee
  3. il ANNONCE la route active         lue dans ~/.dsh/settings.yaml, et ne sonde que
                                        le serveur dont cette route depend

LA LIGNE A LIRE AVANT DE LANCER
  "route active : <provider> / <modele>"
  L'UI REECRIT ce defaut des que tu choisis un modele avec /model -- y compris pour
  les -Ask suivants. Une route openrouter* est PAYANTE (~8 000 tokens d'entree par
  tour d'agent). Le script te previent, il ne t'arrete pas.

ROUTES DISPONIBLES (definies dans ~/.dsh/settings.yaml, pas ici)
  local             llama-server :8004, gratuit, RTX 4090
  openrouter        DeepSeek V4 Pro (flottant / GA 0813) et Qwen3.8-27B, +suffixe :floor
  openrouter-cheap  via le proxy :8011, qui classe les upstreams par cout reel

EN CAS DE PANNE, UN SEUL DES TROIS MANQUE
  mauvais dossier  -> l'agent ne voit pas tes fichiers / session introuvable
  cle absente      -> MISSING_CREDENTIAL. Ajouter une ROUTE a chaud marche,
                      ajouter une CLE non : il faut relancer le process.
  serveur absent   -> erreur de connexion au premier message

AIDE DETAILLEE
  Get-Help .\scripts\dsh.ps1 -Full
'@
    Write-Host $usage
    return
}

function Get-ListenerPid([int]$p) {
    $line = netstat -ano | Select-String -Pattern (":{0}\s" -f $p) |
            Select-String -Pattern 'LISTENING' | Select-Object -First 1
    if ($null -eq $line) { return $null }
    return ($line.Line -split '\s+')[-1]
}

# --- -Stop : on arrete et on sort ------------------------------------------
if ($Stop) {
    foreach ($pair in @(@{n='UI';p=$Port}, @{n='proxy';p=$ProxyPort})) {
        $target = Get-ListenerPid $pair.p
        if ($target) {
            taskkill /PID $target /T /F | Out-Null
            Write-Host ("{0} arrete (PID {1}, port {2})" -f $pair.n, $target, $pair.p)
        } else {
            Write-Host ("{0} : rien n'ecoute sur {1}" -f $pair.n, $pair.p)
        }
    }
    return
}

# --- ingredient 1 : le repertoire de travail --------------------------------
if ($Workspace) {
    if (-not (Test-Path $Workspace)) { throw "Workspace introuvable : $Workspace" }
    Set-Location $Workspace
}
$cwd = (Get-Location).Path

# --- ingredient 2 : l'environnement ----------------------------------------
$env:DSH_TELEMETRY_DISABLED = '1'          # en plus du defaut DISABLED du paquet
$env:DSH_LOCAL_API_KEY      = 'local-dummy' # llama.cpp ne verifie rien, mais la
                                            # reference doit resoudre vers QUELQUE chose

$envFile = Join-Path $RepoRoot '.env'
$orKey = $null
if (Test-Path $envFile) {
    $hit = Get-Content $envFile | Where-Object { $_ -like 'OPENROUTER_API_KEY=*' } | Select-Object -First 1
    if ($hit) { $orKey = ($hit -replace '^OPENROUTER_API_KEY=', '').Trim().Trim('"').Trim("'") }
}
if ($orKey) {
    $env:OPENROUTER_API_KEY = $orKey
    Write-Host ("cle OpenRouter chargee depuis .env (longueur {0}, jamais affichee)" -f $orKey.Length)
} else {
    Write-Warning "OPENROUTER_API_KEY absente du .env : les routes openrouter* refuseront (MISSING_CREDENTIAL). La route 'local' fonctionne quand meme."
}

# --- ingredient 3 : QUELLE route est active, et son serveur -----------------
# Le defaut ne vit PAS dans ce script : il est dans ~/.dsh/settings.yaml, et l'UI
# le REECRIT des qu'on choisit un modele avec /model. On le lit donc a chaque
# lancement et on l'annonce -- sinon on croit taper sur le 4090 gratuit alors
# qu'on facture des tokens OpenRouter (mesure 2026-08-20).
function Test-Port([string]$h, [int]$p) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $null = $c.ConnectAsync($h, $p).Wait(2000); return $c.Connected }
    catch { return $false } finally { $c.Dispose() }
}

$settings = Join-Path $env:USERPROFILE '.dsh\settings.yaml'
$route = $null; $model = $null
if (Test-Path $settings) {
    $txt = Get-Content $settings
    for ($i = 0; $i -lt $txt.Count; $i++) {
        if ($txt[$i] -match '^agent-default-model:') {
            foreach ($j in ($i + 1)..([Math]::Min($i + 4, $txt.Count - 1))) {
                if ($txt[$j] -match '^\s+provider:\s*(\S+)') { $route = $Matches[1] }
                if ($txt[$j] -match '^\s+model:\s*(\S+)')    { $model = $Matches[1] }
            }
            break
        }
    }
}
if ($route) { Write-Host ("route active : {0} / {1}" -f $route, $model) }
else { Write-Warning "agent-default-model illisible dans $settings" }

# On ne sonde QUE le serveur dont la route active depend.
if ($route -eq 'local') {
    if (Test-Port '127.0.0.1' 8004) { Write-Host "  llama-server :8004 en ligne (gratuit, RTX 4090)" }
    else { Write-Warning "  llama-server :8004 muet : cette route echouera. Relancer scripts\restart_production.ps1" }
} elseif ($route -eq 'openrouter-cheap') {
    if (Test-Port '127.0.0.1' $ProxyPort) { Write-Host ("  proxy :{0} en ligne" -f $ProxyPort) }
    else { Write-Warning ("  proxy :{0} absent : cette route echouera. Relancer avec -Cheap" -f $ProxyPort) }
} elseif ($route -like 'openrouter*') {
    Write-Host "  ATTENTION : route PAYANTE (OpenRouter). Un tour d'agent coute ~8 000 tokens d'entree."
}

if ($Cheap) {
    if (Get-ListenerPid $ProxyPort) {
        Write-Host ("proxy 'moins cher' deja en ecoute sur {0}" -f $ProxyPort)
    } else {
        $proxy = Join-Path $PSScriptRoot 'openrouter_cheapest_proxy.mjs'
        Start-Process -FilePath 'node' -ArgumentList @($proxy, '--port', $ProxyPort) `
                      -WorkingDirectory $RepoRoot -WindowStyle Minimized
        Start-Sleep -Seconds 2
        if (Get-ListenerPid $ProxyPort) { Write-Host ("proxy demarre sur {0}" -f $ProxyPort) }
        else { Write-Warning "le proxy n'ecoute pas encore ; la route 'openrouter-cheap' echouera" }
    }
}

# --- boot -------------------------------------------------------------------
$pkg = '@deepseek-ai/dsh@' + $DshVersion

if ($Ask) {
    Write-Host ("tache one-shot | espace de travail : {0}" -f $cwd)
    & npx -y $pkg --profile headless $Ask
    exit $LASTEXITCODE
}

$busy = Get-ListenerPid $Port
if ($busy) {
    Write-Warning ("le port {0} est deja pris (PID {1}). Soit l'UI tourne deja -> http://127.0.0.1:{0}, soit relance avec -Stop puis retente, soit choisis -Port <autre>." -f $Port, $busy)
    return
}

Write-Host ("UI de chat  : http://127.0.0.1:{0}" -f $Port)
Write-Host ("espace de travail : {0}" -f $cwd)
Write-Host "Ctrl+C pour arreter, ou depuis un autre terminal : .\scripts\dsh.ps1 -Stop"

$dshArgs = @('-y', $pkg, 'web', '--host', '127.0.0.1', '--port', $Port)
if ($NoOpen) { $dshArgs += '--no-open' }
& npx @dshArgs
