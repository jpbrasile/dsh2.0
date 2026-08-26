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
# exercices sortiraient en quelques secondes : un Â« 0 sur 6 Â» qui ressemble a
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
