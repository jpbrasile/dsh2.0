# REPLIQUES : trois tirages par configuration, parce qu'un seul ne dit rien.
#
# CE QUI A DECLENCHE CE SCRIPT. Le bras local @10 outils a ete rejoue pour
# recuperer la mesure de pensee. Meme exercice, meme serveur, meme configuration,
# a une demi-heure d'intervalle :
#
#     tirage 1   26 appels   21 942 jetons de sortie   535 s
#     tirage 2   28 appels   11 101 jetons de sortie   269 s
#
# FACTEUR 2,0 entre deux tirages IDENTIQUES. A temperature 1,0, sur une tache
# agentique ou chaque tour depend du precedent, la dispersion d'un seul tirage
# depasse tous les effets qu'on essayait de mesurer :
#
#   « retirer 15 outils fait monter la pensee de 611 a 851 jetons/appel » (+39 %)
#   « le local genere 2,54x moins de jetons qu'AkashML »
#
# Les deux sont DANS ce bruit. Ni l'un ni l'autre n'est etabli. Ce script existe
# pour les etablir ou les abandonner, pas pour les confirmer.
#
# POURQUOI TROIS ET PAS DIX. Chaque tirage prend 5 a 9 minutes de carte, et la
# carte porte le bras GPQA. Trois tirages par bras donnent un ecart-type -- pas
# une precision, mais de quoi dire si un facteur 1,4 est lisible ou non. Dix
# seraient mieux et couteraient une heure de bras. Le choix est declare ici et
# n'est pas revise apres avoir vu les chiffres.
#
# CE QUE CE SCRIPT NE FERA PAS. Choisir apres coup le nombre de tirages, ou
# rejouer un bras « parce qu'il est bizarre ». Les six tirages sont joues, tous
# publies, y compris ceux qui derangent.
#
# NOMS NEUFS A CHAQUE FOIS. Le bras @25 de 20:30 est mort en `FileNotFoundError`
# a 0,0 s : son espace de travail avait ete laisse a moitie copie par une
# tentative interrompue, et `pilote.py` ne recopie pas un repertoire existant.
# Chaque tirage a donc son propre nom.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$gpqa = Join-Path $racine 'scripts\gpqa'
$prof = Join-Path $env:USERPROFILE '.dsh-bench-dflash2\profiles\headless'
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
    $p = Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -PassThru -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_repliques.err')
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

# 3 tirages @25 ; 1 tirage @10 de plus (deux existent deja) => 3 par bras.
$plan = @(
    @{ n = 'r25a'; outils = 25 }, @{ n = 'r25b'; outils = 25 }, @{ n = 'r25c'; outils = 25 },
    @{ n = 'r10c'; outils = 10 }
)

foreach ($t in $plan) {
    Write-Output ''
    Write-Output "=== tirage $($t.n) -- $($t.outils) outils ==="
    if ($t.outils -eq 10) {
        Copy-Item (Join-Path $PSScriptRoot 'bras_outils_reduits.yml') (Join-Path $prof 'cordis.patch.yml') -Force
    } else {
        Copy-Item (Join-Path $prof 'cordis.patch.yml.avant-bras-outils') (Join-Path $prof 'cordis.patch.yml') -Force
    }
    Arreter-Proxy8013
    Demarrer-Proxy8013 (Join-Path $banc "wire_$($t.n).jsonl")
    python pilote.py "dsh_$($t.n)" --tests-maison --conteneur dsh-polyglot-tests `
        --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
        --fournisseur local-mesure --modele specdec-q38-plain
}

Write-Output ''
Write-Output '=== remise en etat ==='
Copy-Item (Join-Path $prof 'cordis.patch.yml.avant-bras-outils') (Join-Path $prof 'cordis.patch.yml') -Force
Arreter-Proxy8013
Set-Location $gpqa
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie local_q4_t1_libre_tournant.jsonl
