# dsh sur OpenRouter (qwen/qwen3.8-27b), LOT DE PRE-OPTIMISATION, detache.
#
# Lot = --pas 6 --decalage 3 --par-langue 2, soit 12 exercices, DEUX PAR
# LANGAGE, pris dans le lot de developpement (indices 3, 9, 15...) donc
# DISJOINT du lot de test (decalage 0).
#
# Pourquoi 2 par langage et non `--limite 12` : le corpus est trie par
# langage, donc --limite 12 ne jouerait que cpp et go. Or les defauts de
# harnais viennent surtout des chaines d'outils -- gradle, cmake, cargo,
# npm. Un lot de mise au point qui n'en exerce que deux ne sert a rien.
#
# CE QUE 12 EXERCICES MESURENT, ET CE QU'ILS NE MESURENT PAS :
#   * ils mesurent bien les signaux PAR EXERCICE -- tours consommes, tokens,
#     l'agent a-t-il lance les tests, categorie d'echec ;
#   * ils ne classent PAS deux designs par taux de reussite : +/- 14 points
#     de bruit binomial a 50 %. Le classement fin, c'est le lot de 38.
#
# Fournisseur `openrouter` et NON `openrouter-banc` : ce dernier passe par un
# enregistreur local sur 127.0.0.1:8050 qui ne tourne pas -- mesure du 26/08,
# pre-vol sorti en `dsh: TRANSPORT: Connection error` apres 18,2 s.
#
# Ce run ne prend PAS la carte : le modele est distant. Seul le juge tourne en
# local, dans le conteneur Docker, sur CPU.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
$log  = Join-Path $banc "run_dev_or.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'bench\.py|pilote\.py' }
if ($py) { Write-Output "REFUS : un pilote tourne deja (PID $($py.ProcessId))."; exit 2 }

$fils = Join-Path $banc "_run_dev_or_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
python pilote.py dsh-dev-or --tours 2 --pas 6 --decalage 3 --par-langue 2 --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "dsh/OpenRouter pre-optimisation lance DETACHE (PID $($p.Id)) -- journal : $log"
