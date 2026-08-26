Set-Location "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
python pilote.py dsh-dev-or --tours 2 --pas 6 --decalage 3 --par-langue 2 --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
