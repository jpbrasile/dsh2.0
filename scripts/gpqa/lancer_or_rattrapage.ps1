# RATTRAPAGE des appels TRONQUES du rodage bf16, plafond 16384 -> 32768.
#
# POURQUOI. Le premier passage a 16384 tokens a rendu 71,2 % +/- 6,6 -- mais
# 42 appels sur 160 se sont arretes AU PLAFOND, dont 36 sans avoir ecrit la
# ligne "Answer: X". Ces 36 sont comptes FAUX. Le chiffre publie par Alibaba
# sur les memes poids est 89,2. Tant que le quart des appels meurt au plafond,
# l'ecart mesure n'est pas une propriete du modele, c'est une propriete de ma
# limite de tokens -- et il ne dit rien sur le Q4 local non plus.
#
# CE QUI EST REJOUE, ET RIEN D'AUTRE. La clause de reprise de gpqa_diamond.py
# ne rejoue qu'un appel a la fois TRONQUE et SANS REPONSE :
#     if d.get("finish_reason") == "length" and not d.get("donne"): continue
# Donc 36 appels. Les 4 non-parses NON tronques restent comptes faux : le
# modele avait la place d'ecrire le format et ne l'a pas fait, c'est un echec
# reel. Les rejouer serait desserrer la barre jusqu'a obtenir le bon chiffre.
#
# TRAITEMENT SYMETRIQUE, sinon la comparaison est nulle. Le run Q4 local subira
# EXACTEMENT le meme protocole quand il aura fini : premier passage a 16384,
# puis rattrapage des seuls tronques a 32768. Il n'a que 6 tronques sur 181, le
# rattrapage y sera marginal -- mais il aura lieu, et il sera dit.
#
# LECTURE ATTENDUE, fixee AVANT de voir le resultat :
#   bf16 rattrape ~= 89,2 (a +/- 7) -> mon harnais reproduit la reference ;
#                                      le chiffre du Q4 local devient lisible.
#   bf16 rattrape << 89,2            -> mon harnais sous-mesure pour une autre
#                                      raison ; ne PAS comparer le local a 89,2.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_or_rattrapage.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py' -and $_.CommandLine -match 'or_bf16' }
if ($py) { Write-Output "REFUS : un run bf16 tourne deja (PID $($py.ProcessId))."; exit 2 }

$fils = Join-Path $banc "_run_or_rattrapage_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py or_bf16.jsonl `
    --url "https://openrouter.ai/api/v1" `
    --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env" `
    --cle-env OPENROUTER_API_KEY `
    --questions 40 --rotations 4 --parallele 6 `
    --max-tokens 32768 --delai 900 `
    --extra-fichier extra_or_bf16.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "rattrapage bf16 a 32768 lance DETACHE (PID $($p.Id)) -- journal : $log"
