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

# REPRISE. Ce lanceur est rejouable tel quel : `pilote.py:1044` saute tout
# exercice qui porte deja son `.dsh.results.json`. Relance avec le MEME $Nom et
# il repart ou il s'est arrete, sans rejuger ce qui est deja juge.
#
# DECODEUR. `-Modele` choisit l'alias servi. Le run du 27/08 est parti en
# `specdec-q38-plain` ; le rejeu apparie de 5 exercices (R25) decide si la suite
# passe en `specdec-q38-dflash2`. Le garde-fou ci-dessous refuse de partir si le
# serveur VIVANT ne correspond pas a l'alias demande -- un bras est sorti
# estampille du mauvais modele le 26/08 faute de ce controle.

# DEUX TOURS, ET C'EST CE QUI REND LE CHIFFRE COMPARABLE.
#
# ORDRE OPERATEUR, 27/08 07:10. Au tour 2, `pilote.py` renvoie a l'agent la
# SORTIE D'ERREUR de la suite officielle (jamais son code source) avec la
# relance mot pour mot d'aider :
#
#     See the testing errors above.
#     The tests are correct, don't try and change them.
#     Fix the code in {file_list} to resolve the errors.
#
# C'est la definition de `pass_rate_2`. Les chiffres publies auxquels on se
# compare -- 52,0 % (fenetre 7quater), Qwen3 32B 40,0, Qwen3 235B-A22B 59,6 --
# sont TOUS des pass_rate_2. A `--tours 1` on produisait un pass_rate_1, qui ne
# se pose a cote d'aucune de ces lignes.
#
# UN SEUL RUN REND LES DEUX TAUX : le journal enregistre `ok` par tour, donc
# pass_1 = fraction dont le tour 1 passe, pass_2 = verdict final.
#
# Le tour 2 dissout aussi l'ecart de perception de la variante D : js/say
# echouait sur un litteral present nulle part ailleurs que dans le test cache ;
# au tour 2 l'agent lit le litteral dans l'erreur et corrige. Ce qui echoue
# APRES avoir vu l'erreur n'a plus d'excuse de protocole.

# LAISSE COURTE AU TOUR 2, ordre operateur du 27/08 08:05. Mesure des 3
# premiers exercices du run : le tour 2 corrige en 31,8 s quand il converge
# (cpp/bank-account, tour 1 194,7 s echoue), et brule 1 800,3 s pour rien quand
# il ne converge pas (cpp/all-your-base, coupe, FAIL de toute facon) -- 77 % du
# temps consomme par un seul tour sans effet sur le taux. 600 s borne la casse.
#
# CE QUE CE BRIDAGE PEUT COUTER, et il faut le dire : une correction longue mais
# LEGITIME au tour 2 devient un FAIL. Sur les 3 exercices deja juges, aucun
# verdict ne change -- le seul tour 2 au-dela de 600 s echouait deja a 1 800 s.

param(
    [string]$Nom = 'pi_D_complet',
    [string]$Modele = 'specdec-q38-plain',
    [int]$Tours = 2,
    [int]$DelaiTour = 1800,
    [int]$DelaiTour2 = 600
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$vu = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").CommandLine
if (-not $vu) { Write-Output 'REFUS : aucun llama-server en vie.'; exit 6 }
$veutDflash = $Modele -match 'dflash'
$sertDflash = $vu -match 'draft-dflash'
if ($veutDflash -ne $sertDflash) {
    Write-Output "REFUS : alias demande '$Modele' mais le serveur vivant sert $(if ($sertDflash) { 'dflash2' } else { 'plain' })."
    exit 6
}
if ($vu -notmatch '--ctx-size 163840' -or $vu -notmatch 'cache-type-k q8_0' -or $vu -notmatch 'cache-type-v q4_0') {
    Write-Output 'REFUS : le serveur vivant ne porte pas ctx 163840 + KV q8_0/q4_0.'
    Write-Output "  argv vu : $vu"
    exit 6
}
Write-Output "=== serveur verifie : $Modele, ctx 163840, KV q8_0/q4_0 ==="

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
Write-Output "=== LIVRABLE 1 : 225 exercices, VARIANTE D, $Tours tour(s), laisse $DelaiTour s (tour 2+ : $DelaiTour2 s) ==="
python pilote.py $Nom --agent pi --accueil-pi $accueilPi --dotenv $dotenv `
    --tests-maison --conteneur pi-polyglot-tests `
    --tours $Tours --delai-tour $DelaiTour --delai-tour-2 $DelaiTour2 --effort medium `
    --fournisseur local-mesure --modele $Modele

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

# UN FICHIER PAR REGIME. Decision de l'operateur, 27/08 07:15 : « qa diamond :
# ca ne change pas grand chose ; la temperature est le facteur primordial, on
# passe en dflash et on fera plus tard le retrofit. » GPQA passe donc en dflash2,
# ce qui revient sur R25 -- et c'est assume.
#
# Ce qui NE se fait pas pour autant : ecrire les enregistrements dflash2 A LA
# SUITE des 115 plain dans le meme fichier. Verifie : les 115 portent tous
# modele=specdec-q38-plain, temperature 1.0, top_p 0.95, top_k 20, min_p 0,
# max_tokens 32768 -- un seul jeu. Les melanger donnerait un taux moyen sur deux
# decodeurs, qui ne caracterise ni l'un ni l'autre. Le fichier de sortie suit
# donc le regime servi, et les 115 plain restent un partiel date, intact.
#
# Consequence assumee : sur un fichier neuf, la rotation repart de zero et joue
# les 198 questions en dflash2. C'est le prix d'un chiffre a regime unique.
$vuFin = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'").CommandLine
if ($vuFin -match 'draft-dflash') {
    $sortieGpqa = 'local_q4_t1_libre_dflash2.jsonl'
    Write-Output '  serveur dflash2 : le bras GPQA ecrit dans un fichier NEUF.'
    Write-Output "    sortie : $sortieGpqa   (les 115 enregistrements plain restent intacts)"
} else {
    $sortieGpqa = 'local_q4_t1_libre_tournant.jsonl'
    Write-Output "  serveur plain : reprise du fichier existant ($sortieGpqa)."
}
Set-Location $gpqa
powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 `
    -Sortie $sortieGpqa
