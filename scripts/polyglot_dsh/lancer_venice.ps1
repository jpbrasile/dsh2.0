# Essai dsh sur `go/beer-song`, EPINGLE sur Venice, meme variante et meme
# effort que la reference AkashML.
#
# CE QUI EST COMPARE, ET CE QUI NE L'EST PAS.
#   comparable    : le debit de decode vu au fil, les jetons de pensee par
#                   appel, le nombre d'appels. Ces trois-la ne dependent pas
#                   de ce qui tourne sur cette machine.
#   NON comparable: la paroi totale, si un autre run occupe le CPU en meme
#                   temps. La reference (1383,0 s) a tourne SEULE ; l'echantillon
#                   pi tourne peut-etre encore. La paroi sera publiee avec cette
#                   reserve, jamais sans.
#
# LE PROXY EST DETACHE. Un `node proxy.mjs` en avant-plan meurt avec le
# terminal qui l'a lance -- constate le 26/08 sur llama-server, meme cause.
# Start-Process le detache ; son PID est ecrit pour pouvoir l'arreter apres.
#
# L'EPINGLAGE EST VERIFIE AVANT LE RUN, pas suppose. Un appel minuscule part
# par le proxy et la reponse doit dire `Venice`. Si elle dit autre chose, on
# s'arrete : un exercice complet chez le mauvais fournisseur coute ~0,50 $ et
# ne mesure rien.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$journal = Join-Path $banc 'wire_or-venice.jsonl'

# --- 1. proxy detache, avec injection -------------------------------------
$env:UP_TLS = '1'
$env:UP_HOST = 'openrouter.ai'
$env:PROXY_PORT = '8012'
$env:PROXY_LOG = $journal
$env:PROXY_INJECT = '{"provider": {"order": ["Venice"], "allow_fallbacks": false}}'

$deja = Get-NetTCPConnection -LocalPort 8012 -State Listen -ErrorAction SilentlyContinue
if ($deja) {
    Write-Output "proxy 8012 deja en ecoute (PID $($deja.OwningProcess)), reutilise."
} else {
    $p = Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -PassThru -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_venice.err')
    Write-Output "proxy 8012 lance, PID $($p.Id)"
    Start-Sleep -Seconds 3
}

# --- 2. l'epinglage tient-il ? --------------------------------------------
# On charge la cle depuis l'environnement du .env sans jamais l'afficher.
$dotenv = Join-Path $racine '.env'
if (Test-Path $dotenv) {
    Get-Content $dotenv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$') {
            $n = $Matches[1]; $v = $Matches[2].Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($n)) {
                [Environment]::SetEnvironmentVariable($n, $v)
            }
        }
    }
}
$cle = $env:OPENROUTER_API_KEY
if (-not $cle) { Write-Output 'REFUS : OPENROUTER_API_KEY absent.'; exit 2 }

$corps = @{
    model = 'qwen/qwen3.8-27b'
    messages = @(@{ role = 'user'; content = 'Reponds par le seul mot OK.' })
    max_tokens = 8
} | ConvertTo-Json -Depth 6 -Compress

$r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8012/api/v1/chat/completions' `
    -Headers @{ Authorization = "Bearer $cle" } -ContentType 'application/json' -Body $corps
Write-Output "temoin d'epinglage : servi par $($r.provider)"
if ($r.provider -ne 'Venice') {
    Write-Output "REFUS : epingle sur Venice, servi par $($r.provider). On n'engage pas."
    exit 3
}

# --- 3. l'exercice ---------------------------------------------------------
Write-Output ''
Write-Output 'exercice go/beer-song, variante D, effort medium, epingle Venice'
python pilote.py dsh_venice_beersong --tests-maison --conteneur dsh-polyglot-tests `
    --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur or-venice --modele qwen/qwen3.8-27b --dotenv $dotenv
