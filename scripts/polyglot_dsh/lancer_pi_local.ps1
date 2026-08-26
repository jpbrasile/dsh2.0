# pi EN LOCAL, trois tirages -- le bras qui manque pour comparer dsh et pi.
#
# LA QUESTION A LAQUELLE CE BRAS REPOND. « Connait-on un reglage dsh aussi
# performant que pi ? » Les quatre tirages locaux de dsh (269 a 547 s) encadrent
# les 282,5 s de pi, mais ces 282,5 s viennent d'AkashML, a 33 jetons/s de
# decode contre 43,5 en local. Comparer les deux serait comparer un dsh local a
# un pi distant. Tant que pi n'a pas tourne sur le MEME serveur, la question n'a
# pas de reponse -- et « on ne sait pas » est la seule reponse honnete.
#
# TROIS TIRAGES, PAS UN. Mesure du soir : deux tirages identiques de dsh
# donnent 21 942 et 11 101 jetons de sortie, facteur 2,0, et la pensee par appel
# va de 71 a 1 711 caracteres entre deux tirages de la MEME configuration. Un
# tirage de pi ne vaudrait pas mieux qu'un tirage de dsh. Le nombre est fixe ici
# et ne sera pas revise apres avoir vu les resultats ; les trois seront publies.
#
# MEME PLAFOND, MEME ENREGISTREUR, MEME EXERCICE. 16 384 jetons de sortie comme
# tous les bras de la soiree -- un tirage de dsh sur trois meurt dessus, et
# donner a pi un plafond plus haut lui epargnerait un mode d'echec que dsh
# subit. Meme proxy 8013, donc les memes grandeurs : pensee, cache, raison
# d'arret, `timings` du serveur.
#
# CE QUE CE BRAS NE POURRA PAS DIRE. Si pi va plus vite, on ne saura toujours
# pas si c'est sa consigne, sa structure de messages ou ses 4 outils -- ces
# trois-la varient ensemble entre les deux agents. Le bras mesure l'ECART sur le
# meme amont, il ne le decompose pas.
#
# DEUX DRAPEAUX QUE dsh N'EXIGE PAS : `--accueil-pi` et `--dotenv`. Oublies, le
# pre-vol echoue sur « Unknown provider » puis « No API key found ». Constate le
# 26/08.

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
function Demarrer-Proxy8013 ($journal) {
    $env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
    $env:PROXY_PORT = '8013'; $env:PROXY_LOG = $journal
    Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
    Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_pi_local.err') | Out-Null
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

foreach ($t in @('pa', 'pb', 'pc')) {
    Write-Output ''
    Write-Output "=== pi local, tirage $t ==="
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
