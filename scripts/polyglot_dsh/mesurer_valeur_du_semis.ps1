# MESURE APPARIEE : ce que vaut le SEMIS des signatures cpp.
#
# ORDRE OPERATEUR, 27/08 08:45 : « ok fais la 1 » -- rejouer les 26 cpp SANS
# semis apres le bloc cpp, tout le reste identique.
#
# LA QUESTION. Les 26 stubs cpp ont ete semes le 27/08 : leur en-tete d'origine
# est un namespace VIDE, alors que le test cache appelle des classes et des
# methodes dont le nom n'apparait ni dans l'enonce ni dans le stub. En variante
# D l'agent ne voit jamais le test : il devait DEVINER le contrat d'API. Les
# cinq autres langages livrent leurs signatures gratuitement.
#
# MAIS le run est passe a --tours 2, et l'erreur de compilation du tour 1 NOMME
# les symboles manquants. C'est par la que les modeles du classement passent le
# cpp, sans semis. Le semis est donc probablement redondant, et cumuler les deux
# donne au cpp plus d'aide qu'aux autres langages ET plus que le banc publie.
#
# CE QU'ON N'A PAS. Une mesure. Le seul appui du semis est cpp/gigasecond,
# FAIL 1 508 s -> PASS 460 s : n=1 sous echantillonnage stochastique, ce qui ne
# vaut rien -- c'est le raisonnement rejete le matin meme pour dflash2.
#
# CE QUE FAIT CE SCRIPT, dans l'ordre, chaque etape refusant de partir si la
# precedente n'a pas abouti :
#   1. verifie que le bloc cpp du run principal est COMPLET ;
#   2. arrete le lanceur PUIS le pilote (jamais l'inverse : le lanceur
#      rallumerait le bras GPQA) ;
#   3. repare l'exercice ampute par cet arret (reparer_amputes.py) ;
#   4. rejoue AVEC semis les cpp qui manquent au run principal, pour que le bras
#      « avec semis » soit complet a 26 ;
#   5. RETIRE le semis du corpus vierge ;
#   6. joue les 26 cpp sous `pi_cpp_sans_semis`, meme decodeur, meme
#      temperature, memes 2 tours, memes laisses ;
#   7. REMET le semis ;
#   8. depouille l'appariement (comparer_semis.py) ;
#   9. relance le run principal, qui reprend a `go` sans perte.
#
# CE QUE LA MESURE POURRA DIRE. Le banc echantillonne : deux runs de la MEME
# configuration divergent deja. Un basculement isole ne prouve rien ; seul le
# BILAN des basculements dans les deux sens porte de l'information. Le
# depouillement sort un McNemar exact, a lire comme un ordre de grandeur.

param(
    [string]$Principal = 'pi_D_t1_dflash2',
    [string]$Nu = 'pi_cpp_sans_semis',
    [string]$Modele = 'specdec-q38-dflash2',
    [switch]$SansRelancePrincipal
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$bench = Join-Path $env:USERPROFILE 'tools\aider-bench\aider\tmp.benchmarks'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

function Arreter-Proxy8013 {
    foreach ($x in (Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $x.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
}

function Demarrer-Proxy([string]$nom) {
    Arreter-Proxy8013
    $env:UP_TLS = '0'; $env:UP_HOST = '127.0.0.1'; $env:UP_PORT = '8005'
    $env:PROXY_PORT = '8013'; $env:PROXY_LOG = (Join-Path $banc "wire_$nom.jsonl")
    Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue
    Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc "proxy_$nom.err") | Out-Null
    Start-Sleep -Seconds 3
}

$pratique = Join-Path $bench 'polyglot-benchmark\cpp\exercises\practice'
$tousCpp = Get-ChildItem $pratique -Directory | Select-Object -ExpandProperty Name | Sort-Object
Write-Output "corpus cpp : $($tousCpp.Count) exercices"

# --- 1. le bloc cpp du run principal est-il fini ? ---------------------------
$log = Join-Path $PSScriptRoot 'polyglot_t1_dflash2_b.log'
$passeCpp = $false
if (Test-Path $log) {
    $passeCpp = (Select-String -Path $log -Pattern '^  (go|java|javascript|python|rust) ' -Quiet)
}
if (-not $passeCpp) {
    Write-Output 'REFUS : le run principal n a pas encore quitte le bloc cpp.'
    Write-Output '  (aucun verdict non-cpp dans le journal)'
    exit 4
}
Write-Output 'bloc cpp du run principal : depasse.'

# --- 2. arret : LANCEUR d abord, sinon il rallume le bras GPQA ---------------
foreach ($x in (Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
                Where-Object { $_.CommandLine -match 'lancer_polyglot_complet' })) {
    Write-Output ("arret du LANCEUR PID {0}" -f $x.ProcessId)
    Stop-Process -Id $x.ProcessId -Force -Confirm:$false
}
Start-Sleep -Seconds 2
foreach ($x in (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
                Where-Object { $_.CommandLine -match 'pilote\.py' })) {
    Write-Output ("arret du PILOTE PID {0}" -f $x.ProcessId)
    Stop-Process -Id $x.ProcessId -Force -Confirm:$false
}
Start-Sleep -Seconds 4
Arreter-Proxy8013

# --- 3. reparer ce que cet arret vient d amputer ------------------------------
Write-Output ''
Write-Output '=== reparation des exercices amputes ==='
python reparer_amputes.py $Principal --appliquer
if ($LASTEXITCODE -ne 0) { Write-Output "REFUS : reparation en echec ($LASTEXITCODE)."; exit 5 }

# --- 4. completer le bras AVEC semis a 26 ------------------------------------
$dejaCpp = @()
foreach ($e in $tousCpp) {
    if (Test-Path (Join-Path $bench "$Principal\cpp\exercises\practice\$e\.dsh.results.json")) {
        $dejaCpp += $e
    }
}
$manquants = $tousCpp | Where-Object { $dejaCpp -notcontains $_ }
Write-Output ''
Write-Output "bras AVEC semis : $($dejaCpp.Count)/$($tousCpp.Count) juges."
if ($manquants) {
    $liste = ($manquants | ForEach-Object { "cpp/$_" }) -join ','
    Write-Output "  a rejouer AVEC semis : $liste"
    Demarrer-Proxy "${Principal}_complement"
    python pilote.py $Principal --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
        --tests-maison --conteneur pi-polyglot-tests `
        --exercices $liste `
        --tours 2 --delai-tour 1800 --delai-tour-2 600 --effort medium `
        --fournisseur local-mesure --modele $Modele
    Arreter-Proxy8013
} else {
    Write-Output '  complet, rien a rejouer.'
}

# --- 5. retirer le semis -----------------------------------------------------
Write-Output ''
Write-Output '=== retrait du semis dans le corpus vierge ==='
python basculer_semis.py --retirer
if ($LASTEXITCODE -ne 0) { Write-Output "REFUS : retrait du semis en echec ($LASTEXITCODE)."; exit 6 }

# --- 6. le bras SANS semis ----------------------------------------------------
Write-Output ''
Write-Output "=== 26 cpp SANS semis, run $Nu, $(Get-Date -Format 'HH:mm:ss') ==="
Demarrer-Proxy $Nu
python pilote.py $Nu --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --langages cpp `
    --tours 2 --delai-tour 1800 --delai-tour-2 600 --effort medium `
    --fournisseur local-mesure --modele $Modele
$codeNu = $LASTEXITCODE
Arreter-Proxy8013

# --- 7. remettre le semis, QUOI QU IL ARRIVE ---------------------------------
Write-Output ''
Write-Output '=== remise du semis ==='
python reparer_amputes.py $Nu --appliquer
python basculer_semis.py --remettre

# --- 8. depouillement --------------------------------------------------------
Write-Output ''
python auditer_pass.py $Nu --tous
Write-Output ''
python comparer_semis.py $Principal $Nu --langage cpp

# --- 9. reprise du run principal ---------------------------------------------
if ($SansRelancePrincipal) {
    Write-Output ''
    Write-Output 'run principal NON relance (-SansRelancePrincipal).'
    exit 0
}
Write-Output ''
Write-Output "=== reprise du run principal, il repart a go $(Get-Date -Format 'HH:mm:ss') ==="
Start-Process -FilePath 'powershell' `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"lancer_polyglot_complet.ps1`" -Nom $Principal -Modele $Modele -Tours 2 -DelaiTour 1800 -DelaiTour2 600" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $PSScriptRoot 'polyglot_t1_dflash2_c.log') `
    -RedirectStandardError (Join-Path $PSScriptRoot 'polyglot_t1_dflash2_c.err') | Out-Null
Write-Output 'relance detachee.'
