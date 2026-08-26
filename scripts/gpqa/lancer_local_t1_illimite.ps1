# GPQA Diamond, Q4 local, RAISONNEMENT NON BRIDE.
#
# CE QUI CHANGE, ET RIEN D'AUTRE : --reasoning-budget 512 -> -1 sur le serveur.
# Meme binaire, meme modele, meme draft, meme ctx, meme KV, memes six parametres
# d'echantillonnage, meme graine, meme plafond de jetons. Diff de l'argv complet
# verifie ligne a ligne le 26/08 : UNE seule ligne differe.
#
# POURQUOI. Le serveur tournait depuis le 25/08 20:57 avec un budget dur de 512
# jetons de pensee, sans --reasoning-budget-message. Ce n'etait pas un choix de
# ce banc : la valeur vient par copier-coller de la famille
# start_llama_qwopus_27b_coder_*, ou l'intention d'origine est ecrite en clair
# -- garder la pensee agentique courte et bon marche. Portee dans un banc de
# RAISONNEMENT, elle fait l'inverse de ce qu'on veut.
#
# LA MESURE, pas la lecture de code. Sur les 294 appels du bras t=1,0 :
#   - 256 blocs <think> analysables, 212 finissent EN PLEINE PHRASE (83 %),
#     parfois en plein mot (« ...Fe3+ is weak acid, hydroly |</think> ») ;
#   - tokenises par le /tokenize DU SERVEUR (60 blocs echantillonnes) :
#     mediane 512, p75 512, p90 512, max 514, 53 sur 60 tombant exactement sur
#     le budget. Un mur, pas une distribution.
#   - finish_reason=length seulement 7 fois sur 294 : ce n'est donc PAS le
#     plafond a 16384 qui coupait, c'est bien le budget en amont.
# (Mon estimation precedente « pas de mur visible » etait fausse : je comptais
# 4 caracteres par jeton, ce texte telegraphique en fait ~3. Le mur etait
# masque par l'approximation, pas absent.)
#
# CE QU'EN DIT LA LITTERATURE. Une coupure NUE est pire que pas de raisonnement
# du tout : sur Qwen3 9B / HumanEval, 94 % sans bride, 88 % sans raisonnement,
# 78 % avec coupure forcee ; un message de transition a budget 1000 remonte a
# 89 %. Si un budget redevient souhaitable, il devra etre PAIRE avec
# --reasoning-budget-message.
#
# FICHIER NEUF, OBLIGATOIRE. gpqa_diamond.py reprend automatiquement en sautant
# les couples (Record ID, rotation) deja presents : ecrire dans
# local_q4_t1.jsonl sauterait les 294 appels faits sous guillotine et
# produirait un journal melangeant deux regimes de serveur sans que rien ne le
# signale. Le bras 512 est gele dans local_q4_t1_budget512.jsonl (294 appels,
# 74 questions dont 72 completes 4/4, 68,7 % +/- 4,2).
#
# PLAFOND INCHANGE a 16384. Le modele va penser plus longtemps : les tronques
# vont probablement augmenter. C'est attendu, c'est mesure, et la regle de
# lecture pre-enregistree s'applique -- un appel tronque est une NON-MESURE,
# exclu et COMPTE, avec rattrapage symetrique a 32768 sur les deux bras.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_local_t1_illimite.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4' }
if ($py) { Write-Output "REFUS : un run local tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    $m = Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 10
    Write-Output "serveur 8005 vivant, modele servi : $($m.models[0].name)"
} catch {
    Write-Output "REFUS : llama-server injoignable sur 8005 -- ne pas lancer a vide."; exit 2
}

# GARDE-FOU PROPRE A CE RUN : on refuse de partir si le serveur qui repond
# porte encore le budget 512. Sans ce controle, un lanceur qui a echoue en
# silence produirait un « bras illimite » qui n'en est pas un -- c'est
# exactement ce qui s'est passe a 13:37 le 26/08 (le lanceur a refuse sur son
# garde-fou GPU et l'ancien serveur a survecu, indistinguable d'une reussite).
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch '--reasoning-budget\s+-1') {
    Write-Output "REFUS : le llama-server vivant ne porte PAS --reasoning-budget -1."
    Write-Output "  argv : $argv"
    exit 3
}
Write-Output "verifie sur le processus vivant : --reasoning-budget -1."

$fils = Join-Path $banc "_run_local_t1_illimite_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4_t1_illimite.jsonl `
    --rotations 4 --max-tokens 16384 --parallele 1 `
    --temperature 1.0 --top-p 0.95 `
    --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "GPQA local t=1.0 BUDGET ILLIMITE lance DETACHE (PID $($p.Id))"
Write-Output "  journal : $log"
Write-Output "  sortie  : local_q4_t1_illimite.jsonl"
