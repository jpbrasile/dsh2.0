# Enchaine le bras B (budget 2048 + message) derriere le bras A (8192).
#
# Une seule carte : les deux bras sont forcement sequentiels. Ce script attend
# la sortie PROPRE du bras A, relance le serveur en 2048, verifie sur l'argv du
# processus vivant, puis lance le bras B.
#
# IL N'ARRETE JAMAIS RIEN QU'IL N'AIT PAS LANCE. Si le bras A tourne encore au
# bout de 6 h, il abandonne et le dit -- il ne le tue pas.
#
# Voir PRE_ENREGISTREMENT_BUDGET.md revision 1 : 198 questions, un appel
# chacune, position tournante, memes questions et memes positions que le bras A
# (l'assignation est deterministe), donc bras APPARIES question par question.

$ErrorActionPreference = "Continue"
$banc   = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$sortieA = Join-Path $banc "local_q4_t1_b8192_tournant.jsonl"
$journal = Join-Path $banc "chainage_2048.log"

function Dire($m) {
    $l = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m
    Write-Output $l
    Add-Content -LiteralPath $journal -Value $l -Encoding utf8
}

Dire "attente de la fin du bras A (8192, position tournante)..."
$t = 0
while ($t -lt 21600) {
    $py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4_t1_b8192_tournant' }
    if (-not $py) { break }
    if ($t % 900 -eq 0) {
        $n = 0
        if (Test-Path $sortieA) { $n = (Get-Content $sortieA).Count }
        Dire "bras A vivant (PID $($py.ProcessId)), $n/198 appels, $t s ecoulees"
    }
    Start-Sleep -Seconds 60
    $t += 60
}
if ($t -ge 21600) { Dire "ABANDON : le bras A tourne encore apres 6 h. Rien n'est tue."; exit 7 }

$nA = 0
if (Test-Path $sortieA) { $nA = (Get-Content $sortieA).Count }
Dire "bras A termine : $nA appels."
if ($nA -lt 190) {
    Dire "REFUS d'enchainer : le bras A n'a que $nA appels sur 198 attendus."
    Dire "  Il s'est arrete avant terme -- diagnostiquer avant de comparer."
    exit 6
}

Dire "relance du serveur en budget 2048 + message..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $banc "relance_serveur_budget.ps1") -Budget 2048 |
    ForEach-Object { Dire $_ }
if ($LASTEXITCODE -ne 0) { Dire "ECHEC de la relance (code $LASTEXITCODE). Bras B non lance."; exit $LASTEXITCODE }

Dire "lancement du bras B..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $banc "lancer_bras_tournant.ps1") `
    -Budget 2048 -Sortie "local_q4_t1_b2048_tournant.jsonl" |
    ForEach-Object { Dire $_ }
Dire "=== enchainement termine, code $LASTEXITCODE ==="
