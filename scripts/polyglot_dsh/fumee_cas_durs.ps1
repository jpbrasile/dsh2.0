# FUMEE SUR LES CAS DURS -- les seuls qui peuvent DEMENTIR le nouveau protocole.
#
# Une fumee sur des exercices faciles passe deja : elle ne prouve rien. On
# rejoue donc exactement ce qui a casse dans dsh-dev-or / pi-dev-or (extrait par
# `cas_durs.py`, pas choisi a la main) :
#
#   java/book-store          pi FAIL 1847,9 s, 2 tours coupes, artefact
#                            dsh coupe a 910,4 s          <- le pire des deux
#   go/beer-song             dsh coupe a 901,1 s
#   go/crypto-square         dsh coupe a 903,1 s
#   cpp/binary-search-tree   dsh 869,8 s au ras du plafond, artefact efface
#   cpp/dnd-character        dsh artefact efface
#   java/custom-set          pi artefact efface
#
# TROIS CHANGEMENTS A LA FOIS, ET C'EST VOULU POUR UNE FUMEE : on cherche une
# panne, pas un effet. Si ca passe, chaque facteur sera isole ensuite.
#
#   1. VARIANTE D (--tests-maison). L'agent ecrit ses propres tests. cpp et java
#      sont declares structurellement plus durs en D (cabler un test maison
#      demande de toucher CMakeLists.txt / Gradle, interdits) : 4 des 6 cas
#      durs sont justement en cpp ou java. La fumee teste donc D la ou elle
#      fait le plus mal.
#   2. --tours 1. Le tour 2 reinjecte la sortie d'echec de la suite OFFICIELLE
#      (pilote.py, `texte = erreurs + TEST_FAILURES`) : en variante D cette
#      suite est la recette d'acceptation CACHEE. Un deuxieme tour la fuite.
#      Un seul tour est une condition de validite, pas une economie.
#   3. --delai-tour 1800. Trois des six ont ete coupes entre 901 et 910 s
#      contre un plafond de 900. Passer a un seul tour retire la moitie du
#      temps d'horloge au moment ou l'iteration rentre A L'INTERIEUR du tour :
#      a 900 s on mesurerait le chronometre, et surtout chez dsh, le plus lent.
#
# ECHANTILLONNAGE INJECTE. Route `openrouter-inject` -> proxy 8009, qui pose
# temperature 1.0 / top_p 0.95 / top_k 20 / min_p 0 dans chaque requete. Ce sont
# les valeurs QUE LE RUN AIDER DE REFERENCE FORCE deja (--read-model-settings) :
# l'injection n'aligne pas seulement dsh et pi entre eux, elle les aligne sur le
# bras aider. Mesure du 26/08 : sans elle, aucun des deux n'envoyait ces champs.
#
# LE PROXY DOIT TOURNER. Sans lui la route rend une erreur de connexion et les
# six exercices sortiraient en quelques secondes avec un rc non nul -- un
# « 0 sur 6 » qui ressemble a un echec d'agent. On refuse de partir a vide.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
$durs = "java/book-store,go/beer-song,go/crypto-square,cpp/binary-search-tree,cpp/dnd-character,java/custom-set"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'pilote\.py' }
if ($py) { Write-Output "REFUS : un pilote tourne deja (PID $($py.ProcessId))."; exit 2 }

try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:8009/api/v1/models" -TimeoutSec 15 -UseBasicParsing
    Write-Output "proxy d'injection 8009 : vivant."
} catch {
    Write-Output "REFUS : proxy 8009 injoignable. Le lancer d'abord :"
    Write-Output "  cd ..\bench_julia_effort"
    Write-Output "  `$env:PROXY_PORT=8009; `$env:UP_TLS=1; `$env:UP_HOST='openrouter.ai'; `$env:UP_PORT=443"
    Write-Output "  `$env:PROXY_LOG='./wire_fumee_durs.jsonl'"
    Write-Output "  `$env:PROXY_INJECT='{\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"min_p\":0}'"
    Write-Output "  node proxy.mjs"
    exit 2
}

Set-Location $banc
python pilote.py fumee-durs-dsh --tests-maison --conteneur dsh-polyglot-tests `
    --exercices $durs --tours 1 --delai-tour 1800 `
    --effort medium --fournisseur openrouter-inject --modele "qwen/qwen3.8-27b" `
    --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
