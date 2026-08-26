# pi sur OpenRouter (qwen/qwen3.8-27b), LOT DE PRE-OPTIMISATION, detache.
#
# MEMES 12 exercices que le run dsh : --pas 6 --decalage 3 --par-langue 2,
# deux par langage, pris dans le lot de developpement (indices 3, 9, 15...)
# donc disjoint du lot de test. Un seul facteur change entre les deux runs :
# la commande de l'agent. Consigne, masquage, juge sur tests d'origine,
# boucle de tours -- tout le reste est partage.
#
# CONTENEUR SEPARE (pi-polyglot-tests). Le juge est un conteneur dormant ou
# l'on entre par `docker exec`, donc deux runs sur des repertoires differents
# ne se marchent pas dessus. Mais les caches gradle, cargo et npm vivent DANS
# le conteneur : deux `./gradlew test` simultanes partageraient les verrous de
# ~/.gradle. Un second conteneur supprime la question.
#
# RESERVE DE MESURE, a tenir au depouillement : deux runs concurrents se
# partagent le CPU, donc leurs DUREES ne sont pas comparables entre elles. Sur
# ce lot de 12 c'est acceptable -- la duree y est diagnostique, pas publiee.
# Le comparatif final sur 38 se fera en SEQUENTIEL, sinon la colonne cout est
# fausse.
#
# Le garde-fou ne regarde que les pilotes `--agent pi` : un run dsh en cours
# n'est pas un motif de refus, il ne partage ni la carte ni settings.yaml.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
$log  = Join-Path $banc "run_dev_pi.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'pilote\.py' -and $_.CommandLine -match '--agent\s+pi' }
if ($py) { Write-Output "REFUS : un pilote pi tourne deja (PID $($py.ProcessId))."; exit 2 }

$fils = Join-Path $banc "_run_dev_pi_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
python pilote.py pi-dev-or --agent pi --conteneur pi-polyglot-tests --tours 2 --pas 6 --decalage 3 --par-langue 2 --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "pi/OpenRouter pre-optimisation lance DETACHE (PID $($p.Id)) -- journal : $log"
