# Rejoue go/alphametics PROPREMENT, une fois la carte libre.
#
# POURQUOI CE REJEU. Le verdict du 27/08 11:35 (FAIL 75,5 s) etait un artefact
# du banc : le `maison_test.go` remis en place par `reparer_amputes.py` avant la
# relance n'a pas ete ecarte avant le juge, et ses deux `func TestSolve` ont
# casse la compilation du paquet. Le rejeu du juge seul rend `ok alphametics
# 5.103s`. Le correctif est en place (`tests_de_l_agent`, commit 41c9934), mais
# un resultat ne se corrige pas a la main : on rejoue.
#
# POURQUOI ATTENDRE. Le 4090 est occupe par le run principal (pilote 64844).
# Deux agents sur un serveur `--parallel 1` se mettent en file d'attente et se
# volent le cache de prefixe : on abimerait A LA FOIS la duree d'alphametics et
# celle de l'exercice que le run principal traite au meme moment. Regle du
# projet : materiel partage occupe => attendre, jamais tuer.
#
# ON ATTEND LE LANCEUR, PAS LE PILOTE. Le lanceur enchaine `auditer_pass.py`
# puis ARRETE LE PROXY 8013 ; demarrer entre les deux ferait tomber le proxy
# sous nos pieds.

$ErrorActionPreference = 'Stop'
$banc = 'C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh'
$sonde = 'C:\Users\test\Documents\dsh2.0\scripts\bench_julia_effort'
$nom = 'pi_D_t1_dflash2'
$journal = Join-Path $banc 'rejeu_alphametics.log'

function Journal($m) {
    $t = Get-Date -Format 'HH:mm:ss'
    Add-Content -Path $journal -Value "[$t] $m" -Encoding utf8
}

Set-Content -Path $journal -Value '' -Encoding utf8
Journal 'attente de la fin du run principal (lanceur 62028 / pilote 64844)'

# Sondage espace : 60 s suffisent, le run dure des heures.
$mortsDeSuite = 0
while ($mortsDeSuite -lt 3) {
    $vivants = @()
    foreach ($procId in @(62028, 64844)) {
        if (Get-Process -Id $procId -ErrorAction SilentlyContinue) { $vivants += $procId }
    }
    if ($vivants.Count -eq 0) { $mortsDeSuite++ } else { $mortsDeSuite = 0 }
    if ($mortsDeSuite -lt 3) { Start-Sleep -Seconds 60 }
}
Journal 'run principal termine.'

# Personne d'autre sur la carte ? Un pilote tiers interdit de demarrer.
$autres = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*pilote.py*' }
if ($autres) {
    foreach ($a in $autres) { Journal "REFUS : pilote tiers PID $($a.ProcessId)" }
    Journal 'rien lance. Relancer ce script quand la carte est libre.'
    exit 3
}

# Le proxy 8013 est mort avec le lanceur : on le remonte, meme journal de fil.
$env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
$env:PROXY_PORT = '8013'
$env:PROXY_LOG = (Join-Path $sonde "wire_$nom.jsonl")
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
$p = Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
    -WorkingDirectory $sonde -WindowStyle Hidden `
    -RedirectStandardError (Join-Path $sonde "proxy_rejeu_alphametics.err") -PassThru
Start-Sleep -Seconds 3
Journal "proxy 8013 remonte (PID $($p.Id))"

Set-Location $banc
Journal 'pilote : --exercices go/alphametics, 1 tour'
& python pilote.py $nom --agent pi `
    --accueil-pi 'C:\Users\test\.pi-bench-polyglot' `
    --dotenv 'C:\Users\test\Documents\dsh2.0\.env' `
    --tests-maison --conteneur pi-polyglot-tests `
    --exercices go/alphametics `
    --tours 1 --delai-tour 1800 --veille-silence 600 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-dflash2 2>&1 |
    Tee-Object -FilePath $journal -Append

# UN SUCCES SE VERIFIE AUSSI DUREMENT QU'UN ECHEC : l'audit doit repasser sur
# l'exercice rejoue, celui du lanceur ayant tourne sans lui.
Journal 'audit du PASS/FAIL rejoue'
& python auditer_pass.py $nom --tous 2>&1 | Tee-Object -FilePath $journal -Append

Stop-Process -Id $p.Id -Force -Confirm:$false -ErrorAction SilentlyContinue
Journal 'proxy 8013 arrete. Rejeu termine.'
