# Mise au point du harnais GPQA sur OpenRouter -- qwen/qwen3.8-27b en bf16.
#
# Ce run ne touche PAS la carte : il peut tourner pendant le run local.
#
# Il ne sert pas a produire un score de reference (le chiffre publie fait
# reference). Il sert a deux choses, et a deux seulement :
#   * mesurer les taux de DEFAUT du harnais -- non-parse, troncature --
#     sur un modele fort, la ou un defaut de gabarit se voit ;
#   * verifier que le harnais ne derive pas grossierement du chiffre publie.
# Le SCORE n'est pas un critere d'arret. Choisir une variante de harnais
# parce qu'elle rend un meilleur chiffre, c'est desserrer la barre.
#
# La quantification est EPINGLEE a bf16 dans extra_or_bf16.json et le
# fournisseur ayant reellement servi est enregistre a chaque ligne : sans ca,
# OpenRouter route vers du fp8 (8 des 10 fournisseurs) en silence.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_or.log"

$fils = Join-Path $banc "_run_or_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py or_bf16.jsonl `
    --url "https://openrouter.ai/api/v1" `
    --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env" `
    --cle-env OPENROUTER_API_KEY `
    --questions 40 --rotations 4 --parallele 12 `
    --max-tokens 16384 --delai 600 `
    --extra-fichier extra_or_bf16.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "GPQA OpenRouter bf16 lance DETACHE (PID $($p.Id)) -- journal : $log"
