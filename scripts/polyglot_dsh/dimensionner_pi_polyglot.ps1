# DIMENSIONNER le polyglot agentique complet -- pi en local, VARIANTE D.
#
# CE QUI EST DEMANDE, ET TRANCHE PAR L'OPERATEUR LE 26/08 A 21:15.
# « L'agent doit creer le src ET ses tests, et tourner jusqu'a ce que ca
# passe. » Deux lectures existaient ; c'est la premiere qui est retenue :
#
#   RETENU   `--tests-maison --tours 1`, delai long. L'agent ecrit sa source et
#            ses tests, et ITERE DANS SON TOUR jusqu'a ce que SES tests passent.
#            La suite d'acceptation juge une fois, a la fin, et il ne la voit
#            jamais. La boucle est celle de l'AGENT.
#
#   ECARTE   `--tours 4` et plus. Le pilote renvoie alors a l'agent la SORTIE de
#            la suite officielle comme consigne du tour suivant
#            (`texte = erreurs + TEST_FAILURES`, pilote.py). En variante D la
#            suite cachee fuirait donc par ses messages d'erreur des le tour 2,
#            et « l'agent ne voit jamais le script de test » deviendrait faux.
#            Ce n'est pas une preference de style : c'est la coherence de la
#            variante.
#
# Le pilote sort deja de la boucle des que la suite officielle passe
# (`if erreurs is None: break`) : monter `--tours` n'ajoute rien a un exercice
# reussi, seulement une relance informee aux echecs.
#
# POURQUOI DIMENSIONNER AVANT LES 225. Les deux seules durees connues de pi en
# variante D encadrent trop large pour decider :
#
#   `go/beer-song`, LOCAL, ce soir, 3 tirages     95 a 144 s   (mais 3 FAIL)
#   12 exercices, OpenRouter, cet apres-midi      14,2 min/exercice
#
#   x225 -> entre 8 h et 53 h. Aucune decision ne se prend sur cet intervalle.
#
# 5 exercices etales sur les six langages (`--pas 45`), au decalage 10 pour ne
# pas rejouer l'echantillon D de cet apres-midi. `--limite` prendrait les
# premiers de chaque langue -- alphabetiquement les plus simples -- et donnerait
# une duree flattee.
#
# `--delai-tour 1800` : c'est la LAISSE, pas une borne cosmetique. « Tourner
# jusqu'a ce que ca passe » demande du temps dans le tour ; 30 minutes est la
# valeur des tirages de ce soir. Un tour coupe est compte comme coupe.
#
# CE QUE CET ECHANTILLON NE DIT PAS. Rien sur le taux : 5 exercices ne rendent
# pas un pass_rate, et il sera publie comme ce qu'il est. Il mesure une DUREE.
#
# LA CARTE. A jouer APRES la fin du bras GPQA -- ordre tranche par l'operateur.
# Ce script met quand meme le bras en pause s'il en trouve un, et le relance a
# la fin : il doit rester rejouable seul.

# 27/08 05:20 -- LE CONTRAT D'API EST DESORMAIS SEME DANS LES STUBS cpp.
# Le premier tirage (pi_dimD) a montre que cpp/gigasecond echouait pour une
# raison qui n'est pas la programmation : le test officiel appelle
# `gigasecond::advance`, le stub livrait un namespace VIDE, et TASK.md ne nomme
# aucune fonction. En variante D le test est masque : le nom n'etait ecrit
# NULLE PART que l'agent puisse lire. Il a ecrit `anniversary` -- le seul mot de
# l'enonce -- avec une logique par ailleurs juste.
#   Mesure : 26 exercices sur 225 (12 %) etaient dans ce cas, TOUS en cpp.
#   go, java, javascript, python et rust livrent deja leurs signatures.
#   Correction : semer_signatures.py ecrit dans chaque stub cpp les
#   DECLARATIONS de .meta/example.h, corps de fonction retires (controle : 0
#   corps survivant sur les 26), sauvegarde en <ex>.h.stub-origine.
# Passer -Nom pour ne pas melanger deux protocoles dans un meme repertoire.

param([string]$Nom = 'pi_dimD')

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

Write-Output '=== pause du bras GPQA ==='
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
Write-Output '=== pi local, VARIANTE D, 1 tour, laisse 1800 s ==='
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --pas 45 --decalage 10 --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-plain

Write-Output ''
Write-Output '=== remise en etat ==='
Arreter-Proxy8013
Set-Location $gpqa
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie local_q4_t1_libre_tournant.jsonl
