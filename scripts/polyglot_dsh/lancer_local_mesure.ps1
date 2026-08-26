# Essai dsh sur `go/beer-song` EN LOCAL, a travers l'enregistreur.
#
# LE TROISIEME BRAS. Meme exercice, meme variante D, meme effort `medium`, meme
# liste de 10 outils que les deux bras OpenRouter du soir. Seul l'amont change :
#   AkashML bf16   45 appels   851 jetons de pensee/appel   decode ~33 j/s
#   Venice  fp8     8 appels  2708 jetons de pensee/appel   decode  91,5 j/s
#   ici     Q4_K_M  ?
#
# CE QUE LE LOCAL DONNE EN PLUS, ET QUI JUSTIFIE CE BRAS A LUI SEUL.
# llama-server renvoie un bloc `timings` dans chaque reponse. Le proxy le
# journalise deja. On y lit, MESURE et non ajuste :
#   prompt_n / prompt_ms / prompt_per_second        -> le prefill, directement
#   predicted_n / predicted_ms / predicted_per_second -> le decode, directement
# Chez OpenRouter il fallait ajuster deux pentes par moindres carres et publier
# un residu pour savoir si on pouvait lire le resultat. Ici les deux termes sont
# declares par la machine qui les a payes. Ce bras VALIDE donc aussi
# l'instrument : si l'ajustement et les `timings` se rejoignent, la methode
# tient ; s'ils divergent, c'est l'ajustement qui tombe, pas le serveur.
#
# LA CARTE EST A NOUS. Le bras GPQA a ete mis en pause a 21/198 (reprise
# automatique par `deja_fait()`, rien n'est perdu). `--parallel 1` : un seul
# slot, donc tout autre client contendrait. Aucun ne tourne.
#
# RESERVE DECLAREE. Le modele local est en Q4_K_M ; AkashML sert du bf16 et
# Venice du fp8. Ce bras compare des DEBITS et des VOLUMES de generation, pas
# des qualites. Le verdict PASS/FAIL de l'exercice n'est pas comparable entre
# quantifications differentes, et ne sera pas presente comme tel.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$racine = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$banc = Join-Path $racine 'scripts\bench_julia_effort'
$journal = Join-Path $banc 'wire_local_mesure.jsonl'

# --- 1. enregistreur 8013 -> 8005, sans TLS, sans injection ----------------
$env:UP_TLS = '0'
$env:UP_HOST = '127.0.0.1'
$env:UP_PORT = '8005'
$env:PROXY_PORT = '8013'
$env:PROXY_LOG = $journal
Remove-Item Env:\PROXY_INJECT -ErrorAction SilentlyContinue

$deja = Get-NetTCPConnection -LocalPort 8013 -State Listen -ErrorAction SilentlyContinue
if ($deja) {
    Write-Output "enregistreur 8013 deja en ecoute (PID $($deja.OwningProcess)), reutilise."
} else {
    $p = Start-Process -FilePath 'node' -ArgumentList 'proxy.mjs' `
        -WorkingDirectory $banc -PassThru -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $banc 'proxy_local_mesure.err')
    Write-Output "enregistreur 8013 lance, PID $($p.Id)"
    Start-Sleep -Seconds 3
}

# --- 2. le chemin repond-il, et le serveur rend-il bien `timings` ? --------
# llama-server accepte n'importe quel jeton mais dsh en exige un.
$env:DSH_LOCAL_API_KEY = 'local'
$corps = @{
    model = 'specdec-q38-plain'
    messages = @(@{ role = 'user'; content = 'Reponds par le seul mot OK.' })
    max_tokens = 8
} | ConvertTo-Json -Depth 6 -Compress
$r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8013/v1/chat/completions' `
    -Headers @{ Authorization = 'Bearer local' } -ContentType 'application/json' -Body $corps
if ($null -eq $r.timings) {
    Write-Output 'REFUS : le serveur ne renvoie pas de bloc `timings`.'
    Write-Output '  Tout le benefice de ce bras en depend ; on ne lance pas a l aveugle.'
    exit 3
}
Write-Output ("temoin : prefill {0:N0} j/s, decode {1:N1} j/s" -f `
    $r.timings.prompt_per_second, $r.timings.predicted_per_second)

# --- 3. l'exercice ---------------------------------------------------------
Write-Output ''
Write-Output 'exercice go/beer-song, variante D, effort medium, LOCAL 8005'
python pilote.py dsh_local_beersong --tests-maison --conteneur dsh-polyglot-tests `
    --exercices go/beer-song --tours 1 --delai-tour 1800 --effort medium `
    --fournisseur local-mesure --modele specdec-q38-plain
