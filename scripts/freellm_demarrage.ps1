# Demarrage FreeLLMAPI + mise a jour du catalogue, en un geste.
#
# POURQUOI ICI. Le catalogue du routeur est tenu a jour en amont, mais avec du
# RETARD sur l'engouement des utilisateurs : les avant-premieres montent en
# usage en deux jours et n'y sont pas encore. Le seul moment ou combler ce
# retard sans y penser, c'est le lancement de l'application -- avant que la
# premiere campagne ne tire dans un catalogue en retard d'une semaine.
#
# ORDRE. Le port AVANT l'executable : relancer FreeLLMAPI.exe alors qu'une
# instance tourne declenche son gestionnaire `second-instance`, qui ramene la
# fenetre au premier plan au lieu de demarrer un serveur. On sonde donc le
# port, on ne suppose pas l'etat de l'application.
#
# Usage :
#   pwsh scripts/freellm_demarrage.ps1                 # verifie, met a jour, sonde
#   pwsh scripts/freellm_demarrage.ps1 -Afficher       # affichage seul, n ecrit rien
#   pwsh scripts/freellm_demarrage.ps1 -PuisDsh        # enchaine sur `dsh`
param(
  [switch]$Afficher,
  [switch]$PuisDsh,
  [int]$Port = 31415,
  [int]$AttenteMax = 45,
  [int]$Delai = 90
)

$ErrorActionPreference = 'Stop'
$racine = Split-Path -Parent $PSScriptRoot
$outil  = Join-Path $racine 'scripts/bench_julia_effort/freellm_catalogue.py'
$exe    = Join-Path $env:LOCALAPPDATA 'Programs/freellmapi-desktop/FreeLLMAPI.exe'

function Ecoute([int]$p) {
  try {
    $c = New-Object Net.Sockets.TcpClient
    $ok = $c.ConnectAsync('127.0.0.1', $p).Wait(700)
    $c.Close(); return $ok
  } catch { return $false }
}

if (Ecoute $Port) {
  Write-Host "FreeLLMAPI ecoute deja sur $Port."
} else {
  if (-not (Test-Path $exe)) { throw "FreeLLMAPI introuvable : $exe" }
  Write-Host "FreeLLMAPI absent du port $Port -- lancement."
  Start-Process $exe | Out-Null
  $t0 = Get-Date
  while (-not (Ecoute $Port)) {
    if (((Get-Date) - $t0).TotalSeconds -gt $AttenteMax) {
      throw "FreeLLMAPI n a pas ouvert $Port en $AttenteMax s. Rien n a ete ecrit au catalogue."
    }
    Start-Sleep -Milliseconds 800
  }
  Write-Host ("FreeLLMAPI ouvert sur {0} en {1:N1} s." -f $Port, ((Get-Date) - $t0).TotalSeconds)
}

# `--appliquer` par defaut, et c est deliberatoire : une routine de demarrage
# qui n ecrit rien tant qu on ne lui ajoute pas un drapeau ne tourne jamais.
# `-Afficher` reste la pour inspecter avant.
$argus = @($outil, 'demarrage')
$argus += @('--delai', "$Delai")
if (-not $Afficher) { $argus += '--appliquer' }
Write-Host ''
& python @argus
$rc = $LASTEXITCODE
if ($rc -ne 0) { throw "catalogue: la routine de demarrage a rendu $rc -- dsh n est PAS lance." }

if ($PuisDsh) {
  Write-Host ''
  Write-Host 'catalogue a jour -- lancement de dsh.'
  & dsh
}
