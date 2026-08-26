# GPQA Diamond, Q4 local, BUDGET DE PENSEE 8192 + MESSAGE DE TRANSITION.
#
# CE QUI CHANGE PAR RAPPORT AU BRAS ILLIMITE, ET RIEN D'AUTRE :
#   --reasoning-budget -1  ->  8192
#   --reasoning-budget-message  absent -> present
# Meme binaire (build-faq), meme modele, meme draft dflash2 n_max=7, meme ctx
# 163840, meme KV q8_0/q4_0, memes parametres d'echantillonnage, meme plafond
# 16384.
#
# POURQUOI 8192. Sur le bras illimite (30 appels, 8 questions) la distribution
# est BIMODALE et le creux est TOTAL : les appels qui aboutissent utilisent
# mediane 1111 jetons de pensee, p90 2695, MAX 4371 ; ceux qui echouent tapent
# 16384, tous, exactement. Rien entre 4371 et 16384. Ce n'est donc pas un
# manque de marge, c'est un regime d'emballement. 8192 = 1,9x le pire appel
# sain : aucun appel sain n'est touche, et les fuyards sont ramenes a conclure.
#
# POURQUOI UN MESSAGE, TOUJOURS. Une coupure NUE mesure PIRE que pas de
# raisonnement du tout (Qwen3 9B / HumanEval : 94 % sans bride, 88 % sans
# raisonnement, 78 % coupure nue, 89 % avec message a budget 1000). C'est
# exactement le defaut qu'on vient de retirer du lanceur -- on ne le
# reintroduit pas par la fenetre. Le lanceur REFUSE desormais (exit 8) un
# budget > 0 sans message.
#
# LE DISPOSITIF EST VERIFIE, PAS SUPPOSE. sonde_budget8192.py, 26/08 :
# bloc de pensee sorti a 8228 jetons, message de transition present a la fin de
# la pensee, reponse hors-pensee complete et structuree derriere,
# finish_reason=stop. Ce dernier point est le piege du dispositif : un budget
# de pensee ne leve JAMAIS finish_reason=length -- c'est ce qui a rendu la
# guillotine 512 invisible pendant vingt heures. Le journal ne le dira pas ;
# seul le texte le dit.
#
# FICHIER NEUF, OBLIGATOIRE. gpqa_diamond.py reprend en sautant les couples
# (Record ID, rotation) deja presents ; ecrire dans un fichier existant
# melangerait deux regimes de serveur sans que rien ne le signale. Bras geles :
#   local_q4_t1_budget512.jsonl        294 appels, 74 questions, 68,7 % +/- 4,2
#   local_q4_t1_budget_illimite.jsonl   30 appels,  8 questions, 81,2 % +/- 12,3
#                                       dont 17 % tronques
#
# PLAFOND INCHANGE a 16384, et la regle de lecture pre-enregistree tient : un
# appel tronque est une NON-MESURE, exclu ET COMPTE, avec rattrapage symetrique
# a 32768 sur tous les bras.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_local_t1_budget8192.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4' }
if ($py) { Write-Output "REFUS : un run local tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    $m = Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 10
    Write-Output "serveur 8005 vivant, modele servi : $($m.models[0].name)"
} catch {
    Write-Output "REFUS : llama-server injoignable sur 8005 -- ne pas lancer a vide."; exit 2
}

# GARDE-FOU PROPRE A CE RUN. Un lanceur peut echouer EN SILENCE et laisser
# l'ancien serveur en place : c'est arrive le 26/08 a 13:37 (refus sur le
# garde-fou GPU, ancien serveur survivant, /props repondant normalement,
# indistinguable d'une reussite). On interroge donc le PROCESSUS VIVANT, pas
# le script. Les DEUX drapeaux sont exiges : un budget sans message est
# precisement le defaut qu'on corrige.
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch '--reasoning-budget\s+8192') {
    Write-Output "REFUS : le llama-server vivant ne porte PAS --reasoning-budget 8192."
    Write-Output "  argv : $argv"
    exit 3
}
if ($argv -notmatch '--reasoning-budget-message') {
    Write-Output "REFUS : budget 8192 present mais SANS message de transition."
    Write-Output "  Une coupure nue mesure pire que pas de raisonnement du tout."
    Write-Output "  argv : $argv"
    exit 4
}
Write-Output "verifie sur le processus vivant : budget 8192 + message de transition."

$fils = Join-Path $banc "_run_local_t1_budget8192_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4_t1_budget8192.jsonl `
    --rotations 4 --max-tokens 16384 --parallele 1 `
    --temperature 1.0 --top-p 0.95 `
    --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "GPQA local t=1.0 BUDGET 8192 + MESSAGE lance DETACHE (PID $($p.Id))"
Write-Output "  journal : $log"
Write-Output "  sortie  : local_q4_t1_budget8192.jsonl"
