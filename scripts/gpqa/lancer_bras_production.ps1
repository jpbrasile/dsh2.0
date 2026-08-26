# LE BRAS QUI PRODUIT LE CHIFFRE -- pensee libre, plafond de sortie double.
#
# POURQUOI IL EXISTE A COTE DE lancer_bras_tournant.ps1. Ce jumeau-la EXIGE un
# budget > 0 apparie a un message de transition (son exit 4). C'est la bonne
# regle pour un bras de REGLAGE. Elle est exactement fausse pour le bras de
# PRODUCTION, que la revision 4 du pre-enregistrement arrete a budget -1 : un
# bras qui ampute 45 a 64 % de ses appels ne fournit pas « un chiffre GPQA du
# modele », il fournit le chiffre de sa propre guillotine.
#
# LES DEUX CHANGEMENTS, ET LEUR MESURE.
#   budget -1     : les appels coupes tombent a 64,0 % contre 100 % pour ceux
#                   qui finissent de penser seuls (bras 8192, 55 appels).
#   sortie 32768  : les appels qui butent sur le plafond de 16 384 sont faux
#                   12 fois sur 12 (7 au bras 512, 5 au bras illimite). Ce
#                   n'est pas une queue negligeable qu'on tronque, c'est une
#                   population entiere perdue.
#
# CE QUE CE BRAS NE PEUT PAS ETABLIR. Il mesure « Q4_K_M + KV q8_0/q4_0 +
# specdec dflash2 », pas le modele en precision pleine. Les trois limites sont
# declarees, aucune n'est levee ici. Tant que la sonde de losslessness du
# specdec n'a pas rendu son verdict, tout chiffre sort avec la mention
# « egalite au glouton non verifiee ».
#
# LE DELAI CLIENT SUIT LE PLAFOND. Le defaut de gpqa_diamond.py est 900 s ;
# 32 768 jetons a 60 t/s en demandent 546, et le debit baisse avec la
# profondeur de contexte. Un depassement de delai ne rate pas un appel lent :
# il transforme une mesure valide en erreur, et c'est la pire des deux issues.
# D'ou --delai 1800 pose ici, apparie au plafond.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File lancer_bras_production.ps1 -Sortie local_q4_t1_libre_tournant.jsonl

param(
    [Parameter(Mandatory = $true)][string]$Sortie,
    [int]$MaxTokens = 32768
)

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\gpqa"
$log  = Join-Path $banc ("run_" + [IO.Path]::GetFileNameWithoutExtension($Sortie) + ".log")

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'gpqa_diamond\.py\s+local_q4' }
if ($py) { Write-Output "REFUS : un run local tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8005/v1/models" -TimeoutSec 10 | Out-Null
} catch {
    Write-Output "REFUS : llama-server injoignable sur 8005 -- ne pas lancer a vide."; exit 2
}

# Le seul temoin qui compte est le processus vivant : un lanceur peut echouer
# en silence et laisser l'ancien serveur en place (26/08, 13:37), etat
# indistinguable d'une reussite depuis /props.
$argv = (Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
         Select-Object -First 1).CommandLine
if ($argv -notmatch '--reasoning-budget\s+-1(\s|$)') {
    Write-Output "REFUS : le serveur vivant ne porte PAS --reasoning-budget -1."
    Write-Output "  Un bras de production sous guillotine ne mesure pas le modele."
    Write-Output "  argv : $argv"
    exit 3
}
if ($argv -match '--reasoning-budget-message') {
    Write-Output "REFUS : message de transition present alors que rien ne coupe."
    exit 4
}
# Le contexte doit financer le plafond de sortie demande, sinon la troncature
# revient par une autre porte -- et silencieusement, cote serveur.
if ($argv -match '--ctx-size\s+(\d+)') {
    $ctx = [int]$Matches[1]
    if ($ctx -lt ($MaxTokens + 4096)) {
        Write-Output "REFUS : ctx $ctx trop court pour un plafond de $MaxTokens jetons."
        exit 5
    }
    Write-Output "ctx $ctx finance un plafond de $MaxTokens jetons."
}
# LE NOM DU MODELE EST UNE DONNEE, PAS UNE DECORATION. Il est recopie dans
# CHAQUE enregistrement et c'est la seule trace de la config qui a produit le
# chiffre. Sans --modele explicite, gpqa_diamond.py ecrit son defaut : un bras
# joue sur le serveur plain sort etiquete « dflash2 ». llama-server sert la
# requete quel que soit le champ `model`, donc l'erreur ne leve rien a
# l'execution -- elle n'apparait qu'au depouillement, quand le bras est fini.
# Constate le 26/08 a 17:43, apres une question jouee. On lit donc l'alias sur
# le PROCESSUS VIVANT, et on refuse s'il n'y en a pas : mieux vaut pas de bras
# qu'un bras mal etiquete.
if ($argv -notmatch '--alias\s+(\S+)') {
    Write-Output "REFUS : le serveur vivant ne porte pas d'--alias."
    Write-Output "  Le bras sortirait etiquete au defaut du script, pas a la config reelle."
    exit 6
}
$aliasServeur = $Matches[1]
Write-Output "verifie sur le processus vivant : budget -1, aucun message."
Write-Output "modele ecrit dans chaque enregistrement : $aliasServeur (lu sur le serveur)."

$fils = Join-Path $banc ("_run_" + [IO.Path]::GetFileNameWithoutExtension($Sortie) + "_fils.ps1")
$corps = @"
Set-Location "$banc"
python gpqa_diamond.py $Sortie ``
    --modele $aliasServeur ``
    --rotation-tournante --max-tokens $MaxTokens --parallele 1 ``
    --temperature 1.0 --top-p 0.95 --delai 1800 ``
    --extra-fichier extra_local.json
Write-Output "=== exit : `$LASTEXITCODE ==="
"@
Set-Content -LiteralPath $fils -Value $corps -Encoding utf8

$p = Start-Process powershell.exe `
     -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $fils) `
     -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") `
     -WindowStyle Hidden -PassThru

Write-Output "bras de PRODUCTION (pensee libre) lance DETACHE (PID $($p.Id))"
Write-Output "  plafond de sortie : $MaxTokens jetons"
Write-Output "  journal : $log"
Write-Output "  sortie  : $Sortie"
