# dsh ET pi, memes 12 exercices, CORRIGE MASQUE. Lance les deux, detaches.
#
# POURQUOI CE RUN EXISTE
# ----------------------
# Les runs precedents (dsh-dev-or, pi-dev-or) tournaient en VARIANTE C, c'est-a-
# dire sans aucun masquage. L'agent avait donc sur son disque, en plus du fichier
# de test officiel :
#     .meta/example.*          le CORRIGE DE REFERENCE
#     .approaches/*/snippet.txt   des solutions communautaires
# Un agent qui peut lire le corrige n'est pas teste. La docstring de
# chemins_a_masquer() le disait deja : « aider ne voit JAMAIS .meta/example.* ni
# .approaches/*/snippet.txt ; --sans-corriges est un correctif SANS
# CONTREPARTIE ». Il n'avait simplement pas ete arme.
#
# Cela vaut aussi pour la revendication de 92,1 % : elle a ete obtenue dans ces
# conditions-la. C'est a dire explicitement quand on la citera.
#
# CE QUI CHANGE, ET RIEN D'AUTRE : --sans-corriges.
# Le fichier de test RESTE visible. Le voir est defendable -- c'est une
# specification, et c'est le protocole revendique. Voir la solution ne l'est pas.
# Un seul facteur bouge, donc l'ecart avec les runs precedents MESURE ce que la
# fuite valait. Les anciens runs ne sont pas perdus : ils deviennent le bras
# « corrige visible » d'une comparaison a deux bras.
#
# Le juge repose de toute facon les tests VIERGES avant le verdict
# (poser_tests), donc un agent qui editerait les tests ne gagnerait rien. Ce
# garde-fou-la fonctionnait deja ; c'est le corrige qui manquait.
#
# RESERVE DE MESURE : les deux runs sont CONCURRENTS et se partagent le CPU.
# Leurs taux de reussite sont comparables, leurs DUREES ne le sont pas entre
# elles. Le comparatif de cout se fera en sequentiel sur les 38.

$ErrorActionPreference = "Continue"
$banc = "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match 'pilote\.py' }
if ($py) { Write-Output "REFUS : un pilote tourne deja (PID $($py.ProcessId))."; exit 2 }

# --- dsh ---------------------------------------------------------------
$filsD = Join-Path $banc "_run_dev_sc_dsh.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
python pilote.py dsh-dev-sc --sans-corriges --conteneur dsh-polyglot-tests --tours 2 --pas 6 --decalage 3 --par-langue 2 --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $filsD -Encoding utf8

$pd = Start-Process powershell.exe `
      -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $filsD) `
      -RedirectStandardOutput (Join-Path $banc "run_dev_sc_dsh.log") `
      -RedirectStandardError  (Join-Path $banc "run_dev_sc_dsh.log.err") `
      -WindowStyle Hidden -PassThru
Write-Output "dsh (corrige masque) lance DETACHE, PID $($pd.Id)"

# --- pi ----------------------------------------------------------------
$filsP = Join-Path $banc "_run_dev_sc_pi.ps1"
@'
Set-Location "C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh"
python pilote.py pi-dev-sc --agent pi --sans-corriges --conteneur pi-polyglot-tests --tours 2 --pas 6 --decalage 3 --par-langue 2 --effort medium --fournisseur openrouter --modele "qwen/qwen3.8-27b" --dotenv "C:\Users\test\Documents\dsh2.0\.env"
Write-Output "=== exit : $LASTEXITCODE ==="
'@ | Set-Content -LiteralPath $filsP -Encoding utf8

$pp = Start-Process powershell.exe `
      -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $filsP) `
      -RedirectStandardOutput (Join-Path $banc "run_dev_sc_pi.log") `
      -RedirectStandardError  (Join-Path $banc "run_dev_sc_pi.log.err") `
      -WindowStyle Hidden -PassThru
Write-Output "pi  (corrige masque) lance DETACHE, PID $($pp.Id)"
