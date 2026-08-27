# NOMME L'OUTIL SUR LEQUEL L'AGENT BLOQUE.
#
# LE MANQUE. Le 27/08, go/bottle-song a ete coupe sur silence apres 601 s sans
# appel au modele. L'appel qui precede le trou est `status 200` /
# `fin_raison: tool_calls` : le serveur a repondu, l'agent s'est bloque DANS un
# appel d'outil. Impossible de dire lequel -- le journal de fil ne porte que des
# compteurs (`ms`, `sent`, `servi`), pi ne laisse pas de transcription, et rien
# sur le disque ne nomme la commande.
#
# CE QUE FAIT CE SCRIPT. Il echantillonne l'arbre de processus SOUS le pilote et
# ecrit toute commande qui vit depuis plus de $SeuilSecondes. Un outil qui bloque
# 10 minutes y apparaitra 30 fois avec sa ligne de commande complete ; un outil
# normal (quelques secondes) n'y apparait jamais.
#
# POURQUOI DEHORS ET PAS DANS LE PILOTE. Le pilote 64844 a deja charge son
# module : l'y ajouter demanderait de le tuer, donc de perdre le run. Ce
# veilleur est EXTERNE, en lecture seule, et ne touche a rien.
#
# IL NE TUE RIEN. Il regarde. Le chien de garde du pilote garde la main.

param(
    [int]$SeuilSecondes = 45,
    [int]$PasSecondes = 20
)

$ErrorActionPreference = 'Stop'
$sortie = 'C:\Users\test\Documents\dsh2.0\scripts\polyglot_dsh\outils_lents.jsonl'

function Descendants($racine) {
    $tous = Get-CimInstance Win32_Process |
        Select-Object ProcessId, ParentProcessId, Name, CommandLine, CreationDate
    $index = @{}
    foreach ($p in $tous) { $index[[int]$p.ProcessId] = $p }
    $vus = @{}
    $pile = New-Object System.Collections.Stack
    $pile.Push([int]$racine)
    while ($pile.Count -gt 0) {
        $id = $pile.Pop()
        foreach ($p in $tous) {
            $pp = [int]$p.ParentProcessId
            $ip = [int]$p.ProcessId
            if ($pp -eq $id -and -not $vus.ContainsKey($ip)) {
                $vus[$ip] = $p
                $pile.Push($ip)
            }
        }
    }
    return $vus.Values
}

while ($true) {
    $pilote = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*pilote.py*' } |
        Select-Object -First 1
    if (-not $pilote) { Start-Sleep -Seconds $PasSecondes; continue }

    $maintenant = Get-Date
    foreach ($p in (Descendants $pilote.ProcessId)) {
        if (-not $p.CreationDate) { continue }
        $age = ($maintenant - $p.CreationDate).TotalSeconds
        if ($age -lt $SeuilSecondes) { continue }
        # Le processus `node` de pi vit tout le tour : ce n'est pas lui qui
        # bloque, c'est ce qu'il a lance. On le garde quand meme comme repere.
        $enr = [ordered]@{
            t     = $maintenant.ToString('yyyy-MM-dd HH:mm:ss')
            pid   = [int]$p.ProcessId
            ppid  = [int]$p.ParentProcessId
            nom   = $p.Name
            age_s = [math]::Round($age, 1)
            cmd   = if ($p.CommandLine) { $p.CommandLine.Substring(0,
                        [Math]::Min(600, $p.CommandLine.Length)) } else { '' }
        }
        Add-Content -Path $sortie -Encoding utf8 `
            -Value ($enr | ConvertTo-Json -Compress)
    }
    Start-Sleep -Seconds $PasSecondes
}
