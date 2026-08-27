# LIVRABLE 1 -- le polyglot aider COMPLET, agentique, VARIANTE D.
#
# ORDRE DE L'OPERATEUR, 27/08 05:55 : « laisse a 1 mais mets aider polyglot
# devant ». Le bras GPQA passe donc APRES : ce script le met en pause au
# demarrage (ses enregistrements sont conserves) et le relance a la fin.
#
# CE QUI EST JOUE. Les 225 exercices, sans `--pas`, sans `--limite`, sans
# `--langages` : la population complete, celle du tableau public. Le
# dimensionnement (`dimensionner_pi_polyglot.ps1`) reste a cote, rejouable seul.
#
# DUREE ATTENDUE, mesuree et pas supposee. Tirage `pi_dimD2` du 27/08 :
# 5 exercices, 1 574,1 s, moyenne 314,8 s -> 225 x 314,8 = 19,7 h. Un PASS coute
# 2,3x un FAIL (477,7 s contre 206,2), donc un meilleur taux ALLONGE le run :
# a 52 % de reussite, 21,7 h. Fourchette de travail 20-22 h.
#
#   RISQUE DECLARE, a la hausse : depuis le 27/08 l'agent peut editer
#   CMakeLists.txt en cpp (26 exercices), donc il peut enfin COMPILER ses tests
#   maison. Il va probablement iterer davantage. Les 26 cpp pourraient donc
#   couter plus que les 314,8 s de moyenne -- au pire la laisse, 1 800 s. Ce
#   n'est pas dans l'estimation ci-dessus, qui repose sur un seul cpp.
#
# CE QUE CE RUN MESURE, ET CE QU'IL NE MESURE PAS. Il rend un pass_rate sur 225
# exercices en variante D. Ce taux n'est PAS comparable au `pass_rate_2 = 52,0 %`
# de la fenetre 7quater ni au tableau public, pour trois raisons ecrites au plan
# (R20, R22, R24b) :
#   1. le test d'acceptation est masque -- c'est le protocole voulu ;
#   2. le contrat d'API l'etait aussi en cpp -- CORRIGE le 27/08 (semis des 26
#      stubs), donc plus une raison a partir de ce run ;
#   3. la SEMANTIQUE l'est encore : au moins 70 exercices sur 225 (31 %) ont un
#      enonce qui ne cite meme pas les identifiants du stub. Non corrigeable
#      sans semer le test.
#
# SPLIT. 5 exercices (indices 10, 55, 100, 145, 190) ont servi au dimensionnement
# et ont motive le semis des stubs cpp. Ils font partie des 225 joues ici, et le
# depouillement publiera DEUX taux : sur les 225, et sur les 220 jamais vus.
# 5 sur 225 = 2,2 %.

param([string]$Nom = 'pi_D_complet')

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$gpqa = Join-Path $racine 'scripts\gpqa'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

function Arreter-Proxy8013 {
    foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
}

Write-Output "=== depart $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

Write-Output '=== pause du bras GPQA (il repassera a la fin) ==='
$g = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -match 'gpqa_diamond' }
if ($g) {
    $n = (Get-Content (Join-Path $gpqa 'local_q4_t1_libre_tournant.jsonl') | Measure-Object -Line).Lines
    Stop-Process -Id $g.ProcessId -Force -Confirm:$false
    Start-Sleep -Seconds 2
    Write-Output "  bras arrete (PID $($g.ProcessId)), $n enregistrements conserves."
} else { Write-Output '  aucun bras GPQA en cours.' }

Arreter-Proxy8013
$env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
$env:PROXY_PORT = '8013'; $env:PROXY_LOG = (Join-Path $banc "wire_$Nom.jsonl")
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
    -WorkingDirectory $banc -WindowStyle Hidden `
    -RedirectStandardError (Join-Path $banc "proxy_$Nom.err") | Out-Null
Start-Sleep -Seconds 3

Write-Output ''
Write-Output '=== LIVRABLE 1 : 225 exercices, VARIANTE D, 1 tour, laisse 1800 s ==='
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-plain

Write-Output ''
Write-Output "=== fin du polyglot $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# UN SUCCES SE VERIFIE AUSSI DUREMENT QU'UN ECHEC. `auditer_pass.py` controle,
# pour chaque PASS : test officiel identique a l'original, construction remise a
# l'original, solution differente du stub ET differente du corrige `.meta`, et
# tout test ecrit par l'agent bien sorti pendant le verdict. Un PASS qui rate un
# de ces controles est signale et doit etre rejoue a la main avant publication.
Write-Output ''
python auditer_pass.py $Nom --tous

Write-Output ''
Write-Output '=== remise en etat : le bras GPQA reprend la carte ==='
Arreter-Proxy8013
Set-Location $gpqa
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie local_q4_t1_libre_tournant.jsonl
