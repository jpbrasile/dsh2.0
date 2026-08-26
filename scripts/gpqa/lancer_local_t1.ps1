# GPQA Diamond, Q4 local, aux reglages PUBLIES par Qwen pour le mode thinking.
#
# CE QUI CHANGE, ET RIEN D'AUTRE : temperature 0,6 -> 1,0.
#
# La carte de modele Qwen3.8-27B recommande, en mode thinking : temperature 1.0,
# top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0.
# Le llama-server tourne deja avec --top-k 20 --top-p 0.95 --min-p 0
# --presence-penalty 0.0 --repeat-penalty 1.0 : cinq parametres sur six sont
# conformes. Le seul ecart etait --temp 0.6, qui est la recommandation de la
# generation Qwen3 PRECEDENTE, portee telle quelle. La temperature est donc a la
# fois le seul ecart au protocole publie ET le seul facteur qui change entre ce
# run et le precedent -- la comparaison reste attribuable.
#
# POURQUOI CA POURRAIT COMPTER. Qwen deconseille un decodage trop deterministe
# sur ses modeles thinking : il provoque des repetitions sans fin. Le rodage
# bf16 a 0,6 a vu 26 % des appels mourir AU PLAFOND de jetons, ce qui est la
# signature d'une boucle. Hypothese testable, pas certitude.
#
# FICHIER NEUF. On n'ecrit PAS dans local_q4.jsonl : melanger deux temperatures
# dans un journal dont le depouillement fait « le dernier gagne » produirait une
# moyenne de deux regimes, sans que rien ne le signale. Les 243 appels a t=0,6
# restent intacts et deviennent le bras de comparaison.
#
# MEME GRAINE (1234, defaut) : meme ordre de questions, memes rotations, memes
# distracteurs. La comparaison est APPARIEE couple (id, rotation) par couple.
#
# PLAFOND INCHANGE a 16384, comme le run precedent et comme le premier passage
# bf16. Le rattrapage des tronques a 32768 se fera apres, par la clause de
# reprise -- meme protocole des deux cotes.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc "run_local_t1.log"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4' }
if ($py) { Write-Output "REFUS : un run local tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    $m = Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 10
    Write-Output "serveur 8005 vivant, modele servi : $($m.models[0].name)"
} catch {
    Write-Output "REFUS : llama-server injoignable sur 8005 -- ne pas lancer a vide."; exit 2
}

$fils = Join-Path $banc "_run_local_t1_fils.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
python gpqa_diamond.py local_q4_t1.jsonl `
    --rotations 4 --max-tokens 16384 --parallele 1 `
    --temperature 1.0 --top-p 0.95 `
    --extra-fichier extra_local.json
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $fils -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "GPQA local t=1.0 lance DETACHE (PID $($p.Id)) -- journal : $log"
