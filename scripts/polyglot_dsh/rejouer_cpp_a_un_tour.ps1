# REJEU DES 5 cpp A UN TOUR -- rendre le bras HOMOGENE.
#
# ORDRE OPERATEUR, 27/08 : « fais les modifs et les rejoue », puis choix
# explicite « a la fin du run » quand la carte a ete signalee occupee.
#
# LE DEFAUT REPARE. Le run `pi_D_t1_dflash2` porte 107 exercices a 1 tour et
# 5 exercices cpp a 2 tours -- residu de l'etape « complement » de
# mesurer_valeur_du_semis.ps1:136-141, qui rejoue en `--tours 2` DANS LE MEME
# repertoire de run. A 2 tours, pilote.py:1071 rend a l'agent la sortie d'erreur
# de la suite officielle : c'est la definition de pass_rate_2 (ordre operateur
# du 27/08 07:10, lancer_polyglot_complet.ps1:50-68), donc parfaitement
# legitime -- mais ca ne se moyenne pas avec 107 tours aveugles. 4 des 5
# basculent FAIL -> PASS a ce tour 2.
#
# CE QUE LE REJEU NE REPARE PAS, et il faut le dire : cpp reste EXCLU de la
# comparaison appariee au board, parce que ses 26 stubs ont ete semes le 27/08
# alors que le run aider date du 25/08. Le rejeu ne sert qu'au chiffre INTERNE
# des 225. Rejouer ne rend pas cpp comparable.
#
# PAS DE SUPPRESSION. Les 5 `.dsh.results.json` sont DEPLACES dans
# `_avant_rejeu_1tour/`, jamais effaces : l'ordre etait de rejouer, pas de
# detruire, et un deplacement se defait. pilote.py:1044 saute tout exercice qui
# porte deja son resultat -- c'est pourquoi il faut les ecarter.

param(
    [string]$Nom = 'pi_D_t1_dflash2',
    [string]$Modele = 'specdec-q38-dflash2',
    [switch]$Simuler          # -Simuler : montre ce qui serait fait, ne fait rien
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$bench = Join-Path $env:USERPROFILE 'tools\aider-bench\aider\tmp.benchmarks'
$accueilPi = Join-Path $env:USERPROFILE '.pi-bench-polyglot'
$dotenv = Join-Path $racine '.env'
$env:DSH_LOCAL_API_KEY = 'local'

$exercices = @('all-your-base', 'bank-account', 'parallel-letter-frequency',
               'phone-number', 'zebra-puzzle')

# --- 1. LA CARTE EST-ELLE LIBRE ? --------------------------------------------
# Garde-fou ressource partagee : regarder QUI l'utilise, occupe => attendre,
# JAMAIS tuer. Ce script refuse de partir, il n'arrete rien.
$pilotes = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'pilote\.py' })
if ($pilotes) {
    Write-Output 'REFUS : un pilote est en vol.'
    foreach ($p in $pilotes) { Write-Output ("  PID {0}" -f $p.ProcessId) }
    Write-Output '  La carte est prise. Attendre la fin du run ; ne rien tuer.'
    exit 3
}
Write-Output 'aucun pilote en vol.'

$vram = (nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader) -join ' '
Write-Output "GPU : $vram"

# --- 2. ETAT AVANT, pour pouvoir comparer apres ------------------------------
Write-Output ''
Write-Output '=== etat des 5 AVANT rejeu ==='
$avant = @{}
foreach ($e in $exercices) {
    $f = Join-Path $bench "$Nom\cpp\exercises\practice\$e\.dsh.results.json"
    if (-not (Test-Path $f)) { Write-Output ("  {0,-28} ABSENT" -f $e); continue }
    $d = Get-Content $f -Raw | ConvertFrom-Json
    $o = @($d.tests_outcomes)
    $avant[$e] = $o
    Write-Output ("  {0,-28} tours={1} outcomes={2}" -f $e, $o.Count, ($o -join ','))
}

if ($Simuler) {
    Write-Output ''
    Write-Output '-Simuler : rien n a ete fait.'
    exit 0
}

# --- 3. ECARTER les resultats a 2 tours (DEPLACEMENT, pas suppression) -------
$archive = Join-Path $bench "$Nom\_avant_rejeu_1tour"
New-Item -ItemType Directory -Force $archive | Out-Null
Write-Output ''
Write-Output "=== mise de cote dans $archive ==="
foreach ($e in $exercices) {
    $f = Join-Path $bench "$Nom\cpp\exercises\practice\$e\.dsh.results.json"
    if (Test-Path $f) {
        Move-Item $f (Join-Path $archive "$e.dsh.results.json") -Force
        Write-Output "  $e deplace"
    }
}

# --- 4. REJEU a UN tour ------------------------------------------------------
$liste = ($exercices | ForEach-Object { "cpp/$_" }) -join ','
Write-Output ''
Write-Output "=== rejeu a 1 tour, $(Get-Date -Format 'HH:mm:ss') ==="
Write-Output "  $liste"
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --exercices $liste `
    --tours 1 --delai-tour 1800 --effort medium `
    --veille-silence 600 `
    --fournisseur local-mesure --modele $Modele
$code = $LASTEXITCODE
Write-Output "pilote rc=$code"

# --- 5. REPARER un eventuel exercice ampute ----------------------------------
python reparer_amputes.py $Nom --appliquer

# --- 6. ETAT APRES, et le bras est-il homogene ? -----------------------------
Write-Output ''
Write-Output '=== etat des 5 APRES rejeu ==='
foreach ($e in $exercices) {
    $f = Join-Path $bench "$Nom\cpp\exercises\practice\$e\.dsh.results.json"
    if (-not (Test-Path $f)) { Write-Output ("  {0,-28} ABSENT" -f $e); continue }
    $d = Get-Content $f -Raw | ConvertFrom-Json
    $o = @($d.tests_outcomes)
    $av = if ($avant.ContainsKey($e)) { ($avant[$e] -join ',') } else { '-' }
    Write-Output ("  {0,-28} avant=[{1}]  apres=[{2}]  tours_demandes={3}" `
                  -f $e, $av, ($o -join ','), $d.tours_demandes)
}

Write-Output ''
Write-Output '=== l alerte d heterogeneite doit avoir DISPARU ==='
python etat_run.py $Nom
Write-Output ''
Write-Output '=== audit des PASS sur les 5 rejoues ==='
python auditer_pass.py $Nom --tous
