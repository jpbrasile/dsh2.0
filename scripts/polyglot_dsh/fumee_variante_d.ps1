# FUMEE de la variante D avant de depenser deux runs complets.
#
# La variante D est cablee depuis le 26/08 mais n'a JAMAIS tourne. Son point
# fragile est identifie : `tests_de_l_agent()` doit reperer les fichiers que
# l'agent a crees pendant le tour et les SORTIR pendant le verdict. S'il les
# rate, le juge les ramasse (pytest collecte test_*.py, `go test ./...` balaie
# tout) et un test maison qui echoue fait compter FAIL un exercice dont la VRAIE
# suite passe. On mesurerait alors la qualite du detecteur, pas celle de l'agent.
#
# Deux exercices, deux langages aux mecaniques de collecte differentes :
# python (collecte par prefixe de nom) et go (collecte par package). 2 tours.
#
# CE QU'ON VERIFIE dans le .dsh.results.json produit :
#   variante == "D", sans_tests et sans_corriges == true  -> les implications
#     du drapeau ont bien ete appliquees ;
#   tests_maison == true ;
#   le verdict n'est pas un FAIL en quelques secondes -> signature d'un juge
#     qui ramasse les tests maison ou d'un espace de travail ampute.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'pilote\.py' }
if ($py) { Write-Output "REFUS : un pilote tourne deja (PID $($py.ProcessId))."; exit 2 }

Set-Location $banc
python pilote.py fumee-d --agent pi --tests-maison --conteneur pi-polyglot-tests `
    --tours 2 --pas 6 --decalage 3 --par-langue 1 --langages python,go `
    --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
