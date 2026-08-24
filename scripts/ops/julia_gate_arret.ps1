# julia_gate_arret.ps1 -- arret propre de la porte Julia AVANT les balayages
# living-docs (test-all 01:00, test-gpu 05:00) dont la garde julia_procs.ps1
# differe des qu'un julia.exe est vivant, sans connaitre la regle du port 8077.
#
# Cause mesuree (mail [PDT] FAIL: test-all du 25/08 01:00) : le serveur porte
# (PID 6096, resident depuis le 24/08) a fait DEFERRER le balayage nocturne.
# La porte se relance a la demande (les runners ont leur boucle de prechauffe),
# l'arreter la nuit ne coute qu'un warmup (~10 s) au premier appel du matin.
#
# Tache planifiee `dsh-julia-gate-arret`, declencheurs 00:50 et 04:50.
# Ne touche RIEN d'autre : si :8077 n'ecoute pas, sortie 0 silencieuse.
# Sorties : 0 arrete-ou-deja-absent ; 4 port encore tenu apres l'arret demande.
[CmdletBinding()]
param()

$DEPOT = "C:\Users\test\Documents\dsh2.0"
$JOURNAL = "$env:USERPROFILE\dsh-julia-gate-arret.log"
function Ecrire([string]$m) {
    Add-Content -LiteralPath $JOURNAL -Encoding UTF8 -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m)
}

$conn = Get-NetTCPConnection -LocalPort 8077 -State Listen -ErrorAction SilentlyContinue
if (-not $conn) { exit 0 }   # porte deja absente : rien a faire, rien a journaliser

$proprietaire = ($conn | Select-Object -ExpandProperty OwningProcess -Unique) -join ","
& python "$DEPOT\scripts\julia_gate\porte.py" --arret 2>&1 | Out-Null
Start-Sleep -Seconds 3
$encore = Get-NetTCPConnection -LocalPort 8077 -State Listen -ErrorAction SilentlyContinue
if ($encore) {
    Ecrire ("ECHEC : --arret envoye mais :8077 encore tenu par PID " + (($encore | Select-Object -ExpandProperty OwningProcess -Unique) -join ","))
    exit 4
}
Ecrire ("porte arretee (PID etait " + $proprietaire + "), :8077 verifie libre")
exit 0
