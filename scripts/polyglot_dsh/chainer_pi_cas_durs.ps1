# CHAINAGE : pi sur les six memes cas durs, DERRIERE dsh.
#
# POURQUOI NE PAS LANCER EN PARALLELE. Cette fumee mesure precisement des
# DUREES : java/book-store est passe en 1434,0 s la ou dsh avait ete coupe a
# 910,4 s et pi avait echoue en 1847,9 s. Deux pilotes qui se partagent le CPU
# et le disque rendent ces durees incomparables. `pilote.py` refuse d'ailleurs
# de demarrer si un pilote tourne deja -- ce script attend proprement au lieu
# de se faire refuser.
#
# STRICTE PARITE avec le run dsh, sinon la comparaison ne vaut rien :
#   memes six exercices, meme ordre (--exercices preserve l'ordre donne)
#   --tests-maison (variante D)   --tours 1   --delai-tour 1800
#   --effort medium               --fournisseur openrouter-inject
#   --modele qwen/qwen3.8-27b     meme proxy d'injection sur 8009
# Seul change ce qui DOIT changer : --agent pi, son conteneur, son accueil.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
$log  = Join-Path $banc "run_fumee_durs_pi.log"
$durs = "java/book-store,go/beer-song,go/crypto-square,cpp/binary-search-tree,cpp/dnd-character,java/custom-set"

$fils = Join-Path $banc "_chainer_pi_fils.ps1"
@'
$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
$durs = "java/book-store,go/beer-song,go/crypto-square,cpp/binary-search-tree,cpp/dnd-character,java/custom-set"

# --- attendre que le pilote dsh sorte -------------------------------------
$attendu = 0
while ($true) {
    $py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'pilote\.py' }
    if (-not $py) { break }
    if ($attendu % 300 -eq 0) {
        Write-Output ("[{0}] pilote dsh encore vivant (PID {1}), attente... ({2} s)" -f (Get-Date -Format HH:mm:ss), $py.ProcessId, $attendu)
    }
    Start-Sleep -Seconds 30
    $attendu += 30
    if ($attendu -gt 21600) { Write-Output "ABANDON : 6 h d'attente, le pilote dsh ne sort pas."; exit 3 }
}
Write-Output ("[{0}] pilote dsh sorti apres {1} s d'attente. Lancement de pi." -f (Get-Date -Format HH:mm:ss), $attendu)

# --- le proxy d'injection doit etre vivant ---------------------------------
# Sans lui, la route openrouter-inject rend une erreur de connexion et les six
# exercices sortiraient en quelques secondes : un « 0 sur 6 » qui ressemble a
# un echec d'agent. On refuse de partir a vide.
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:8009/api/v1/models" -TimeoutSec 15 -UseBasicParsing
    Write-Output "proxy d'injection 8009 : vivant."
} catch {
    Write-Output "REFUS : proxy 8009 injoignable au moment de lancer pi."
    exit 2
}

Set-Location $banc
python pilote.py fumee-durs-pi --agent pi --tests-maison `
    --conteneur pi-polyglot-tests `
    --accueil-pi "C:\Users\test\.pi-bench-polyglot" `
    --exercices $durs --tours 1 --delai-tour 1800 `
    --effort medium --fournisseur openrouter-inject --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit pi : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "chainage pi ARME, detache (PID $($p.Id))"
Write-Output "  il attend la sortie du pilote dsh, puis lance pi sur les 6 memes cas."
Write-Output "  journal : $log"
