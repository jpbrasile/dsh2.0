# UNE SEULE FENETRE DE PAUSE, DEUX BRAS : dsh « minimal », puis pi en local.
#
# POURQUOI LES DEUX ENSEMBLE. Chaque pause du bras GPQA lui fait rejouer la
# question en vol (`deja_fait()` ne saute que les paires terminees). Deux
# fenetres coutent deux rejeux ; une seule en coute un. Les deux bras sont prets
# et ne se genent pas : ils tournent l'un apres l'autre sur le meme serveur.
#
# BRAS 1 -- dsh « minimal ». dsh livre un preset d'agent `minimal` : persona
# d'une phrase, `complete: true`, deux outils. Ce profil headless ne monte pas
# le roster de presets, donc on reproduit la COMPOSITION par le patch cordis, et
# le temoin est le fil. TEMOIN DEJA PRIS, sans carte, contre le serveur temoin
# du port 8007 (`temoin_minimal.ps1`, 26/08 20:20) :
#
#     standard   25 outils   systeme 4 327 car.
#     reduit     10 outils   systeme 1 765 car.
#     minimal     2 outils   systeme   357 car.   <- pwsh, str_replace_editor
#
#   pour reference : pi offre 4 outils et 2 686 caracteres.
#
# Ce temoin a deja servi a autre chose qu'a confirmer : il a attrape un montage
# qui ne demarrait pas. Desactiver `compaction-basic` sans desactiver
# `command-compact` laisse ce dernier en attente du service `compaction` et dsh
# sort en rc=1 sans un seul appel. Sur la carte, ca aurait coute trois tirages
# morts et une demi-heure de bras GPQA.
#
# BRAS 2 -- pi en local. La question « connait-on un reglage dsh aussi
# performant que pi ? » n'a pas de reponse tant que pi n'a pas tourne sur le
# MEME serveur : ses 282,5 s ont ete mesurees chez AkashML, a 33 jetons/s de
# decode contre 43,5 en local. Meme plafond 16 384, meme enregistreur 8013,
# meme exercice.
#
# TROIS TIRAGES PAR BRAS, FIXE AVANT DE VOIR. Mesure du soir : deux tirages
# identiques de dsh donnent 21 942 et 11 101 jetons de sortie, et la paroi va de
# 269 a 677 s sur trois tirages de la meme configuration. Un tirage unique ne
# distingue rien. Le nombre ne sera pas revise apres coup et les six seront
# publies, y compris ceux qui derangent.
#
# NOMS NEUFS. `pilote.py` ne recopie pas un espace de travail existant : un nom
# reutilise apres une interruption meurt en `FileNotFoundError` a 0,0 s.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$gpqa = Join-Path $racine 'scripts\gpqa'
$prof = Join-Path $env:USERPROFILE '.dsh-bench-dflash2\profiles\headless'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

function Arreter-Proxy8013 {
    foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
}
function Demarrer-Proxy8013 ($journal) {
    $env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
    $env:PROXY_PORT = '8013'; $env:PROXY_LOG = $journal
    Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
    Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_minimal_pi.err') | Out-Null
    Start-Sleep -Seconds 3
}

Write-Output '=== pause du bras GPQA ==='
$g = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -match 'gpqa_diamond' }
if ($g) {
    $n = (Get-Content (Join-Path $gpqa 'local_q4_t1_libre_tournant.jsonl') | Measure-Object -Line).Lines
    Stop-Process -Id $g.ProcessId -Force -Confirm:$false
    Start-Sleep -Seconds 2
    Write-Output "  bras arrete (PID $($g.ProcessId)), $n enregistrements conserves."
} else { Write-Output '  aucun bras GPQA en cours.' }

Write-Output ''
Write-Output '=== BRAS 1 : dsh minimal (2 outils, systeme 357 car.) ==='
Copy-Item (Join-Path $PSScriptRoot 'bras_minimal.yml') (Join-Path $prof 'cordis.patch.yml') -Force
foreach ($t in @('m1', 'm2', 'm3')) {
    Write-Output ''
    Write-Output "--- tirage $t ---"
    Arreter-Proxy8013
    Demarrer-Proxy8013 (Join-Path $banc "wire_$t.jsonl")
    python pilote.py "dsh_min_$t" --tests-maison --conteneur dsh-polyglot-tests `
        --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
        --fournisseur local-mesure --modele specdec-q38-plain
}

Write-Output ''
Write-Output '=== depose du patch minimal ==='
Copy-Item (Join-Path $prof 'cordis.patch.yml.avant-minimal') (Join-Path $prof 'cordis.patch.yml') -Force
Get-Content (Join-Path $prof 'cordis.patch.yml') | Select-Object -Last 1

Write-Output ''
Write-Output '=== BRAS 2 : pi en local ==='
foreach ($t in @('pa', 'pb', 'pc')) {
    Write-Output ''
    Write-Output "--- tirage $t ---"
    Arreter-Proxy8013
    Demarrer-Proxy8013 (Join-Path $banc "wire_pi_$t.jsonl")
    python pilote.py "pi_local_$t" --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
        --tests-maison --conteneur pi-polyglot-tests `
        --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
        --fournisseur local-mesure --modele specdec-q38-plain
}

Write-Output ''
Write-Output '=== remise en etat ==='
Arreter-Proxy8013
Set-Location $gpqa
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie local_q4_t1_libre_tournant.jsonl
