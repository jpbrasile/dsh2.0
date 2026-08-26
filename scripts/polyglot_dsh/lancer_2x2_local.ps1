# LE 2x2 : {AkashML, local} x {25 outils, 10 outils}, meme exercice.
#
# CE QU'IL MANQUE ET QUE CE SCRIPT COMBLE. Trois bras existent : AkashML @25
# (29 appels, 611 jetons de pensee/appel), AkashML @10 (45 appels, 851/appel) et
# local @10 (29 appels, pensee NON MESUREE faute d'instrument). Le resultat
# « moins d'outils => plus de pensee » ne repose donc que sur UN tirage, sur UN
# amont. Un amont independant le replique ou le refute.
#
# LES DEUX BRAS LOCAUX SONT REJOUES, PAS SEULEMENT LE @25. Le proxy ne comptait
# pas la pensee quand local @10 a tourne ; comparer un bras ou elle est mesuree
# a un bras ou elle ne l'est pas ne donnerait rien. On rejoue les deux dans la
# meme fenetre, avec le meme instrument et le meme serveur.
#
# CE QUE LA PAUSE COUTE, ET POURQUOI ELLE EST QUAND MEME PRISE. `--parallel 1` :
# un seul slot. Un agent lance a cote du bras GPQA contendrait et gonflerait les
# DEUX mesures. La pause est donc obligatoire. Son cout est declare en Revision
# 6 : au redemarrage, `deja_fait()` rejoue les questions tronquees. UNE fenetre
# pour les deux bras, pas deux.
#
# CE QUE CE SCRIPT NE FAIT PAS. Il ne touche pas au serveur. `--reasoning-format
# none` reste tel quel : la pensee est dans `message.content` entre <think> et
# </think>, le proxy la mesure, et basculer en `deepseek` casserait le parseur
# du banc GPQA qui reprend juste apres.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$gpqa = Join-Path $racine 'scripts\gpqa'
$prof = Join-Path $env:USERPROFILE '.dsh-bench-dflash2\profiles\headless'
$env:DSH_LOCAL_API_KEY = 'local'

function Arreter-Proxy8013 {
    $c = Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue
    foreach ($x in $c) {
        Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
        Write-Output "  enregistreur 8013 arrete (PID $($x.OwningProcess)) -- il portait l'ancien code."
    }
}

function Demarrer-Proxy8013 ($journal) {
    $env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
    $env:PROXY_PORT = '8013'; $env:PROXY_LOG = $journal
    Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -PassThru -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_2x2.err')
    Start-Sleep -Seconds 3
    Write-Output "  enregistreur 8013 -> $(Split-Path $journal -Leaf) (PID $($p.Id))"
}

# --- 1. mettre le bras GPQA en pause --------------------------------------
Write-Output '=== pause du bras GPQA ==='
$g = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -match 'gpqa_diamond' }
if ($g) {
    $avant = (Get-Content (Join-Path $gpqa 'local_q4_t1_libre_tournant.jsonl') | Measure-Object -Line).Lines
    Stop-Process -Id $g.ProcessId -Force -Confirm:$false
    Start-Sleep -Seconds 2
    Write-Output "  bras arrete (PID $($g.ProcessId)), $avant enregistrements conserves."
} else {
    Write-Output '  aucun bras GPQA en cours.'
}

# --- 2. les deux bras, dans l'ordre ---------------------------------------
# @25 d'abord : c'est la configuration standard de dsh, et celle de la
# reference AkashML la plus citee.
$bras = @(
    @{ nom = 'dsh_local_25outils'; patch = '[]'; journal = 'wire_local_25.jsonl'; etiq = '25 outils (standard)' },
    @{ nom = 'dsh_local_10outils'; patch = 'reduits'; journal = 'wire_local_10.jsonl'; etiq = '10 outils (allege)' }
)

foreach ($b in $bras) {
    Write-Output ''
    Write-Output "=== bras $($b.etiq) ==="
    if ($b.patch -eq 'reduits') {
        Copy-Item (Join-Path $PSScriptRoot 'bras_outils_reduits.yml') `
                  (Join-Path $prof 'cordis.patch.yml') -Force
        Write-Output '  cordis.patch.yml : machinerie desactivee'
    } else {
        Copy-Item (Join-Path $prof 'cordis.patch.yml.avant-bras-outils') `
                  (Join-Path $prof 'cordis.patch.yml') -Force
        Write-Output '  cordis.patch.yml : restaure (aucune desactivation)'
    }
    Arreter-Proxy8013
    Demarrer-Proxy8013 (Join-Path $banc $b.journal)

    python pilote.py $b.nom --tests-maison --conteneur dsh-polyglot-tests `
        --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
        --fournisseur local-mesure --modele specdec-q38-plain
}

# --- 3. remettre en etat et relancer le bras ------------------------------
Write-Output ''
Write-Output '=== remise en etat ==='
Copy-Item (Join-Path $prof 'cordis.patch.yml.avant-bras-outils') `
          (Join-Path $prof 'cordis.patch.yml') -Force
Write-Output '  cordis.patch.yml restaure (25 outils)'
Arreter-Proxy8013

Set-Location $gpqa
# PAS de Tee-Object vers le meme fichier que la redirection du lanceur : le
# verrou Windows fait echouer la redirection de l'enfant, `sys.stdout` vaut
# None et le processus meurt au demarrage. Constate le 26/08 a 19:12.
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie local_q4_t1_libre_tournant.jsonl
