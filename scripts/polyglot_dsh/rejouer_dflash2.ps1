# REJOUER LES 5 EXERCICES DU DIMENSIONNEMENT, AVEC dflash2.
#
# Ordre operateur du 27/08 06:40 : « refais simplement les runs deja fait ici
# avec dflash2 », apres la question juste « mais avec dflash les perf ne sont
# pas degradees ? ».
#
# CE QU'ON SAIT ET CE QU'ON NE SAIT PAS. Mesure B1 : en glouton, graine fixe,
# meme binaire, plain contre dflash2 rend 12/12 sorties DIVERGENTES. Donc le
# decodeur n'est pas sans perte. Mais divergent n'est PAS degrade : l'effet sur
# la JUSTESSE n'a jamais ete mesure. Ce script le mesure, sur le seul materiau
# qui compte pour le livrable 1.
#
# LE PLAN D'EXPERIENCE. Memes 5 exercices (`--pas 45 --decalage 10`), meme
# variante D, meme laisse, meme corpus (stubs cpp semes des deux cotes). Le
# serveur porte un argv IDENTIQUE a celui du bras plain -- meme binaire
# build-faq, meme modele, --ctx-size 163840, KV q8_0/q4_0, --parallel 1 --
# auquel s'ajoutent seulement `--spec-type draft-dflash`, `-md <brouillon>` et
# `--spec-draft-n-max 7`. UN facteur.
#
#   CONFONDANT DECLARE, et il ne touche qu'UN exercice sur 5 : depuis le 27/08
#   05:55, CMakeLists.txt est editable en cpp. Le bras plain `pi_dimD2` a tourne
#   AVANT ce changement. Donc pour `cpp/gigasecond` deux facteurs bougent, et sa
#   comparaison ne conclut rien seule. Les 4 autres (go, java, javascript,
#   python) ne sont pas concernes : CONSTRUCTION ne contient que ".cpp".
#
# CE QUE LE RESULTAT DECIDERA. Verdicts identiques sur les 4 exercices propres
# et duree nettement plus basse => dflash2 est neutre en justesse sur ce
# materiau, et B6 le reprend (2,2x sur ~20 h). Un seul verdict qui bascule =>
# on garde plain, et on aura enfin chiffre ce que coute le decodeur.
#
# CE SCRIPT NE TOUCHE PAS AU BRAS GPQA. B6 doit reprendre juste apres ; le
# rallumage de GPQA reste au lanceur de B6.

param([string]$Nom = 'pi_dimD2_dflash2')

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

function Arreter-Proxy8013 {
    foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
}

# Garde-fou d'etiquetage : le 26/08 un bras est sorti estampille du mauvais
# modele parce que le lanceur ne verifiait pas le serveur VIVANT. On lit donc
# l'alias servi, et on refuse si ce n'est pas dflash2.
$vu = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").CommandLine
if (-not $vu) { Write-Output 'REFUS : aucun llama-server en vie.'; exit 6 }
if ($vu -notmatch 'draft-dflash') {
    Write-Output 'REFUS : le serveur vivant ne sert PAS dflash2 (pas de --spec-type draft-dflash).'
    exit 6
}
if ($vu -notmatch '--ctx-size 163840' -or $vu -notmatch 'cache-type-k q8_0' -or $vu -notmatch 'cache-type-v q4_0') {
    Write-Output 'REFUS : le serveur vivant ne porte pas le meme contexte/KV que le bras plain.'
    Write-Output "  argv vu : $vu"
    exit 6
}
Write-Output '=== serveur verifie : dflash2, ctx 163840, KV q8_0/q4_0 ==='

Arreter-Proxy8013
$env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
$env:PROXY_PORT = '8013'; $env:PROXY_LOG = (Join-Path $banc "wire_$Nom.jsonl")
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
    -WorkingDirectory $banc -WindowStyle Hidden `
    -RedirectStandardError (Join-Path $banc "proxy_$Nom.err") | Out-Null
Start-Sleep -Seconds 3

Write-Output ''
Write-Output "=== rejeu dflash2, memes 5 exercices, VARIANTE D $(Get-Date -Format 'HH:mm:ss') ==="
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --pas 45 --decalage 10 --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-dflash2

Write-Output ''
python auditer_pass.py $Nom --tous

Write-Output ''
Write-Output "=== fin du rejeu $(Get-Date -Format 'HH:mm:ss') ==="
Arreter-Proxy8013
