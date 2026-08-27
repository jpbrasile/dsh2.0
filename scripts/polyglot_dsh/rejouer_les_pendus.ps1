# REJEU PRIORITAIRE DES EXERCICES ABIMES PAR LE HARNAIS.
#
# ORDRE OPERATEUR, 27/08 09:50 : « retraite les cas a problemes en priorite ».
#
# CE QUI LES ABIME. Trois tours ont ete coupes a 1 800 s sans que le modele
# soit sollicite : l'agent cesse d'appeler au bout de 20 a 164 s, puis plus
# rien. Cause mesuree : l'outil `bash` de pi declare son delai `Optional` et
# son propre schema dit « no default timeout » ; une commande non bornee fige
# le tour. Pris sur le fait le 27/08 a 09:34:45, `find / -name plf_build.ps1`
# balayant tout le disque -- DEUX de ces `find` tournaient encore a l'arret.
# Le tour n'a pas manque de temps : il a manque d'un garde-fou.
#
# CE QUI EST DEJA CORRIGE. `pilote.py` porte desormais `--veille-silence` :
# le tour est coupe apres N secondes sans un seul appel au modele. Seuil lu
# dans la distribution -- 460 ecarts entre appels, plus long ecart LEGITIME
# 120,4 s, puis un gouffre jusqu'a 1 677 s. Defaut 600 s, 5x de marge.
#
# PERIMETRE, RESTREINT PAR L'OPERATEUR 27/08 09:55 : « tu peux te limiter aux
# timeout sur round 1 ». On ne rejoue donc QUE les tours 1 pendus.
#
#   kindergarten-garden        REJOUE -- tour 1 pendu 1 760 s.
#   linked-list                REJOUE -- tour 1 pendu 1 677 s.
#
#   all-your-base              HORS PERIMETRE. Son tour 1 a fini SEUL en
#       119,0 s et a echoue de plein droit ; seul son tour 2 a pendu (20 s
#       d'appels, puis 1 780 s de silence). Il garde donc son FAIL. Ce FAIL
#       a peut-etre ete decide par la panne et non par le modele -- on le
#       garde quand meme, et il faut le dire : il joue CONTRE nous. Le
#       laisser ne gonfle aucun chiffre, l'enlever en gonflerait un.
#
#   parallel-letter-frequency  ampute par l'arret du 27/08 09:47 (suite
#       officielle restee au stash) -- pas de resultat, il repart seul.
#   complex-numbers            ampute par l'arret du 27/08 08:07 -- idem.
#
# Ces quatre-la sont en tete du corpus cpp : le run principal, qui reprend
# sans perte en sautant ce qui porte deja un resultat, les refait donc EN
# PREMIER de lui-meme. Aucun run separe n'est necessaire.
#
# ============================ LA REGLE, ECRITE AVANT ========================
# Le verdict du REJEU est l'officiel pour les cinq, QUEL QU'IL SOIT. Les
# anciens verdicts sont conserves (renommes, jamais supprimes) et publies a
# cote. Si un PASS devient FAIL, c'est le FAIL qui compte.
#
# Sans cette regle ecrite d'avance, rejouer deux PASS serait une option
# gratuite : on garderait le meilleur des deux tirages et le taux monterait
# tout seul. C'est exactement le cliquet a sens unique refuse le matin meme
# pour l'arbitre claude -p.
# ===========================================================================

param(
    [string]$Nom = 'pi_D_t1_dflash2',
    [string]$Modele = 'specdec-q38-dflash2',
    [int]$Tours = 2,
    [int]$DelaiTour = 1800,
    [int]$DelaiTour2 = 600,
    [int]$VeilleSilence = 600,
    [switch]$PuisRelancerPrincipal
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$bench = Join-Path $env:USERPROFILE 'tools\aider-bench\aider\tmp.benchmarks'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

# Tours 1 pendus, et eux seuls (perimetre fixe par l'operateur).
$pendus = @('kindergarten-garden', 'linked-list')

# --- 0. refus si un pilote vit ------------------------------------------
$vivants = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'pilote\.py' }
if ($vivants) {
    Write-Output 'REFUS : un pilote tourne encore.'
    $vivants | ForEach-Object { Write-Output ("  PID {0}" -f $_.ProcessId) }
    exit 3
}

# --- 1. le patch est-il bien en place ? ----------------------------------
$aide = & python pilote.py --help 2>&1 | Out-String
if ($aide -notmatch 'veille-silence') {
    Write-Output 'REFUS : pilote.py ne porte pas --veille-silence.'
    Write-Output '  Rejouer sans le correctif reproduirait exactement la panne.'
    exit 4
}
Write-Output 'pilote.py porte --veille-silence : correctif en place.'

# --- 2. reparer les amputes ----------------------------------------------
Write-Output ''
Write-Output '=== reparation des exercices amputes ==='
python reparer_amputes.py $Nom --appliquer
if ($LASTEXITCODE -ne 0) { Write-Output "REFUS : reparation en echec ($LASTEXITCODE)."; exit 5 }

# --- 3. ecarter les verdicts rendus sous harnais pendu -------------------
# RENOMMER, jamais supprimer : les deux verdicts seront publies cote a cote.
$horo = Get-Date -Format 'yyyyMMdd-HHmmss'
Write-Output ''
Write-Output '=== mise de cote des verdicts rendus sous harnais pendu ==='
foreach ($e in $pendus) {
    $f = Join-Path $bench "$Nom\cpp\exercises\practice\$e\.dsh.results.json"
    if (Test-Path $f) {
        $dest = "$f.pendu-$horo"
        Move-Item -LiteralPath $f -Destination $dest
        Write-Output "  $e -> $(Split-Path $dest -Leaf)"
    } else {
        Write-Output "  $e : aucun resultat actif (deja ecarte)"
    }
}

# --- 4. reprise du run principal, qui EST le rejeu ------------------------
# Les quatre exercices sans resultat (les deux ecartes ci-dessus + les deux
# amputes) sont en tete du corpus cpp. Le run principal saute ce qui porte
# deja un resultat, donc il les refait EN PREMIER, puis continue la ou il
# s'etait arrete. Un run separe n'apporterait rien et multiplierait les
# proxys et les journaux.
#
# Le lanceur remonte son propre proxy avec PROXY_LOG = wire_<Nom>.jsonl,
# qui est exactement le fichier que le chien de garde surveille. C'est
# indispensable : le chien ne s'arme QUE s'il voit un appel de ce tour
# tomber dans ce fichier-la.
Write-Output ''
Write-Output '=== ce que le run principal va refaire en premier ==='
foreach ($e in ($pendus + @('complex-numbers', 'parallel-letter-frequency'))) {
    $f = Join-Path $bench "$Nom\cpp\exercises\practice\$e\.dsh.results.json"
    if (Test-Path $f) {
        Write-Output "  ATTENTION $e porte encore un resultat : il sera SAUTE."
    } else {
        Write-Output "  $e : sans resultat, sera rejoue."
    }
}

if (-not $PuisRelancerPrincipal) {
    Write-Output ''
    Write-Output 'run principal NON relance (ajouter -PuisRelancerPrincipal).'
    Write-Output "depouillement quand il aura tourne :"
    Write-Output "  python comparer_pendus.py $Nom --horodatage $horo"
    exit 0
}
Write-Output ''
Write-Output "=== reprise du run principal $(Get-Date -Format 'HH:mm:ss') ==="
Start-Process -FilePath 'powershell' `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"lancer_polyglot_complet.ps1`" -Nom $Nom -Modele $Modele -Tours $Tours -DelaiTour $DelaiTour -DelaiTour2 $DelaiTour2 -VeilleSilence $VeilleSilence" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $PSScriptRoot 'polyglot_t1_dflash2_c.log') `
    -RedirectStandardError (Join-Path $PSScriptRoot 'polyglot_t1_dflash2_c.err') | Out-Null
Write-Output 'relance detachee.'
Write-Output ''
Write-Output "quand les deux rejoues auront un verdict :"
Write-Output "  python comparer_pendus.py $Nom --horodatage $horo"
