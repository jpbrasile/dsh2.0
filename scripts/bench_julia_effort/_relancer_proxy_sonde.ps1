# Relance UN proxy 8009 propre, avec la sonde de prefixe active.
#
# DETACHE. Un proxy lance en avant-plan meurt avec le terminal qui l'a lance --
# incident du 25/08 sur llama-server, meme cause. Start-Process sans -Wait et
# sans -NoNewWindow le detache du shell appelant.
#
# JOURNAL NEUF. Les mesures d'avant la sonde n'ont ni `prefix_h` ni
# `fournisseur` ; les melanger dans un meme fichier ferait croire a des champs
# manquants alors que c'est un changement d'instrument. Nouveau fichier, date.
#
# L'INJECTION EST REPRISE A L'IDENTIQUE de cabler_proxy_injection.py : changer
# l'echantillonnage en meme temps que l'instrument rendrait tout ecart
# inattribuable.

$ErrorActionPreference = "Stop"
$ici = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ici

$existant = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
              Where-Object { $_.CommandLine -match 'proxy\.mjs' })
if ($existant.Count -gt 0) {
    Write-Output "REFUS : $($existant.Count) proxy(s) deja vivant(s). Les arreter d'abord."
    exit 2
}

if (-not (Select-String -Path (Join-Path $ici "proxy.mjs") -Pattern "prefix_h" -Quiet)) {
    Write-Output "REFUS : proxy.mjs ne porte pas la sonde (prefix_h absent)."
    exit 3
}

$env:PROXY_PORT = "8009"
$env:UP_TLS     = "1"
$env:UP_HOST    = "openrouter.ai"
$env:UP_PORT    = "443"
$env:PROXY_LOG  = "./wire_sonde_20260826.jsonl"
$env:PROXY_INJECT = '{"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0}'

Start-Process -FilePath "node" -ArgumentList "proxy.mjs" `
    -WorkingDirectory $ici -WindowStyle Hidden

Start-Sleep -Seconds 3
$v = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
       Where-Object { $_.CommandLine -match 'proxy\.mjs' })
if ($v.Count -ne 1) {
    Write-Output "ECHEC : $($v.Count) proxy(s) apres lancement, attendu 1."
    exit 4
}
Write-Output "proxy 8009 relance, PID $($v[0].ProcessId), journal $($env:PROXY_LOG)"

# Le seul temoin qui compte est le port qui repond, pas le processus qui existe.
try {
    $t = New-Object System.Net.Sockets.TcpClient
    $t.Connect("127.0.0.1", 8009)
    $t.Close()
    Write-Output "port 8009 : REPOND"
} catch {
    Write-Output "ATTENTION : le processus vit mais le port 8009 ne repond pas."
    exit 5
}
