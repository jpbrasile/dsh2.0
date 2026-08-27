# TEMOIN MUET : les MEMES 5 exercices, une SECONDE fois en plain.
#
# POURQUOI CE SCRIPT EXISTE. Le rejeu dflash2 (R25) a ete concu comme une
# comparaison appariee « un seul facteur ». Verification faite APRES coup, cette
# prémisse est FAUSSE :
#
#   argv du serveur : --temp 0.6 --top-k 20 --top-p 0.95 --min-p 0
#                     --repeat-penalty 1.0   (et AUCUN --seed)
#   cote client     : ni cabler_local_mesure.py ni pilote.py n'envoient de
#                     temperature ni de graine -> les defauts serveur s'appliquent.
#
# Le banc ECHANTILLONNE, avec une graine tiree a chaque appel. Deux runs PLAIN du
# meme exercice ne donnent donc pas forcement le meme verdict. La regle
# pre-enregistree « un basculement => dflash2 refuse » supposait implicitement le
# determinisme ; elle ne s'applique pas telle quelle.
#
# La mesure B1 (12/12 divergences plain contre dflash2) restait valide, elle :
# elle etait en GLOUTON, graine fixe. Cette precaution n'avait pas ete transposee
# au banc agentique. C'est la faute, et ce script la repare.
#
# CE QU'IL MESURE. La variance PROPRE du banc, decodeur constant. Memes 5
# exercices (--pas 45 --decalage 10), meme variante D, meme laisse, meme corpus,
# serveur plain -- exactement la configuration de `pi_dimD2`, rejouee.
#
# COMMENT LE LIRE, ecrit avant le resultat :
#   - >= 1 verdict bascule entre pi_dimD2 et ce temoin => le banc est bruyant a
#     ce n, et la comparaison dflash2 sur 5 exercices est NON CONCLUANTE. On ne
#     departagera pas les decodeurs sans un banc apparie bien plus large.
#   - 0 basculement sur les 5 => le banc est stable a ce n MALGRE
#     l'echantillonnage, et le basculement observe sous dflash2
#     (java/sgf-parsing, FAIL -> PASS) redevient imputable au decodeur.
#     Attention : 0 sur 5 ne prouve pas la reproductibilite, il la rend
#     seulement plausible.
#
# CE SCRIPT NE TOUCHE PAS AU BRAS GPQA.

param([string]$Nom = 'pi_dimD2_temoin')

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

# Garde-fou d'etiquetage, symetrique de celui du rejeu dflash2 : on refuse si le
# serveur vivant n'est PAS le plain, ou s'il ne porte pas le meme contexte/KV.
$vu = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").CommandLine
if (-not $vu) { Write-Output 'REFUS : aucun llama-server en vie.'; exit 6 }
if ($vu -match 'draft-dflash') {
    Write-Output 'REFUS : le serveur vivant sert dflash2, or le temoin doit etre PLAIN.'
    exit 6
}
if ($vu -notmatch '--ctx-size 163840' -or $vu -notmatch 'cache-type-k q8_0' -or $vu -notmatch 'cache-type-v q4_0') {
    Write-Output 'REFUS : le serveur vivant ne porte pas ctx 163840 + KV q8_0/q4_0.'
    Write-Output "  argv vu : $vu"
    exit 6
}
Write-Output '=== serveur verifie : plain, ctx 163840, KV q8_0/q4_0 ==='

Arreter-Proxy8013
$env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
$env:PROXY_PORT = '8013'; $env:PROXY_LOG = (Join-Path $banc "wire_$Nom.jsonl")
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
    -WorkingDirectory $banc -WindowStyle Hidden `
    -RedirectStandardError (Join-Path $banc "proxy_$Nom.err") | Out-Null
Start-Sleep -Seconds 3

Write-Output ''
Write-Output "=== temoin muet plain, memes 5 exercices, VARIANTE D $(Get-Date -Format 'HH:mm:ss') ==="
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --pas 45 --decalage 10 --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-plain

Write-Output ''
python auditer_pass.py $Nom --tous

Write-Output ''
Write-Output "=== fin du temoin $(Get-Date -Format 'HH:mm:ss') ==="
Arreter-Proxy8013
