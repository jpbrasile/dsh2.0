# Enregistre les deux taches planifiees du chantier distilleur autonome.
# Idempotent : -Force remplace une definition existante du meme nom.
$DEPOT = "C:\Users\test\Documents\dsh2.0"
$ps = "powershell.exe"

# 1. dsh-julia-gate-arret -- 00:50 et 04:50, avant test-all (01:00) et test-gpu (05:00)
$a1 = New-ScheduledTaskAction -Execute $ps -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$DEPOT\scripts\ops\julia_gate_arret.ps1`""
$t1a = New-ScheduledTaskTrigger -Daily -At 00:50
$t1b = New-ScheduledTaskTrigger -Daily -At 04:50
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "dsh-julia-gate-arret" -Action $a1 -Trigger @($t1a, $t1b) -Settings $s -Description "Arret propre de la porte Julia (:8077) avant les balayages living-docs 01:00/05:00 ; cause du DEFERRED du 25/08." -Force | Out-Null
"dsh-julia-gate-arret : enregistree"

# 2. dsh-distiller-nightly -- 07:00, apres test-gpu ; la passe SAUTE d'elle-meme si GPU tiers
$a2 = New-ScheduledTaskAction -Execute $ps -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$DEPOT\scripts\ops\distiller_nightly.ps1`""
$t2 = New-ScheduledTaskTrigger -Daily -At 07:00
$s2 = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "dsh-distiller-nightly" -Action $a2 -Trigger $t2 -Settings $s2 -Description "Distillation nocturne des deux viviers sur qwen-local :8004 (0 USD) ; saute si le lanceur refuse le GPU." -Force | Out-Null
"dsh-distiller-nightly : enregistree"

Get-ScheduledTask -TaskName "dsh-julia-gate-arret", "dsh-distiller-nightly" |
    ForEach-Object { "{0} : {1}" -f $_.TaskName, $_.State }
(Get-ScheduledTask -TaskName "dsh-julia-gate-arret").Triggers | ForEach-Object { "declencheur gate-arret : " + $_.StartBoundary }
(Get-ScheduledTask -TaskName "dsh-distiller-nightly").Triggers | ForEach-Object { "declencheur distiller : " + $_.StartBoundary }
