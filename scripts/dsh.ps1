<#
.SYNOPSIS
  Lanceur DSH (DeepSeek Harness rc.7) : prepare les 3 ingredients puis boote un profil.

.DESCRIPTION
  DSH n'a ni --cwd, ni --model, ni --base-url. Tout passe par :
    1. le REPERTOIRE DU PROCESS   -> espace de travail + cle des sessions
    2. l'ENV du process           -> resout les references apiKeyEnv de settings.yaml
    3. ~/.dsh/settings.yaml       -> les routes (local / openrouter / openrouter-cheap)
  Ce script fait 1 et 2, puis lance. Il ne touche jamais a settings.yaml.

  La cle OpenRouter est lue depuis le .env du depot et posee UNIQUEMENT dans l'env
  de ce process. Elle n'est jamais affichee, jamais ecrite ailleurs.

.EXAMPLE
  .\scripts\dsh.ps1
  Ouvre l'UI de chat sur http://127.0.0.1:8010 dans le BAC A SABLE par defaut
  (%LOCALAPPDATA%\Temp\dsh-workspace), pas dans le repertoire courant.

.EXAMPLE
  .\scripts\dsh.ps1 -Workspace C:\projets\essai -Cheap
  Demarre le proxy "upstream le moins cher" s'il ne tourne pas, puis l'UI sur ce dossier.

.EXAMPLE
  .\scripts\dsh.ps1 -Ask "ecris un script python qui renomme les .txt en .md"
  Une seule tache, pas d'UI, rend la main quand c'est fini.

.EXAMPLE
  .\scripts\dsh.ps1 -Stop
  Arrete l'UI (et le proxy s'il tourne).
#>
[CmdletBinding()]
param(
    [string] $Ask,                                   # tache one-shot (profil headless)
    [string] $Workspace,                             # dossier nomme (cree s'il manque)
    [switch] $Here,                                  # utiliser le repertoire COURANT
    [switch] $Fresh,                                 # dossier jetable horodate
    [int]    $Port = 8010,                           # port de l'UI web
    [int]    $ProxyPort = 8011,                      # port du proxy "moins cher"
    [switch] $Cheap,                                 # demarre le proxy s'il est absent
    [switch] $NoOpen,                                # ne pas ouvrir le navigateur
    [switch] $Stop,                                  # arreter UI + proxy
    [string] $QuarantineSession,                     # deplacer UN journal de session fautif
    [switch] $SkipSessionCheck,                      # sauter le preflight du magasin de sessions
    [switch] $SkipTreeCheck,                         # sauter le preflight de coherence de l'arbre
    [string] $DshVersion = '0.1.1-rc.2',             # version de @deepseek-ai/dsh a lancer
    [switch] $InstallRuntime,                        # (re)construire l'arbre EPINGLE de cette version
    [switch] $InstallPlugins,                        # monter scripts/dsh-plugins/ dans les profils
    [int]    $SubagentTimeoutMs = 600000,            # borne par defaut d'un sous-agent (10 min)
    [switch] $Help                                   # afficher l'aide et sortir
)

$ErrorActionPreference = 'Stop'
$RepoRoot   = Split-Path -Parent $PSScriptRoot

# --- -Help : on affiche et on sort, sans rien toucher -----------------------
if ($Help) {
    Write-Host ("dsh.ps1 -- lanceur DeepSeek Harness (paquet epingle @deepseek-ai/dsh@{0})" -f $DshVersion)
    $usage = @'

USAGE
  .\scripts\dsh.ps1 [-Here | -Fresh | -Workspace <dir>] [-Port <n>] [-Cheap] [-NoOpen]
  .\scripts\dsh.ps1 -Ask "<tache>" [-Here | -Fresh | -Workspace <dir>]
  .\scripts\dsh.ps1 -Stop [-Port <n>] [-ProxyPort <n>]
  .\scripts\dsh.ps1 -QuarantineSession <dir>
  .\scripts\dsh.ps1 -Help

PARAMETRES
  ESPACE DE TRAVAIL -- par DEFAUT un bac a sable temporaire, PAS le repertoire
                    courant. DSH n'a pas de --cwd : ce dossier est a la fois ce que
                    l'agent voit et la cle sous laquelle tes sessions sont rangees,
                    donc lancer depuis le depot lui donnerait le depot comme terrain.
    (rien)          %LOCALAPPDATA%\Temp\dsh-workspace -- stable : tes fichiers et
                    ton historique de chat y survivent d'un lancement a l'autre.
    -Fresh          sous-dossier horodate jetable. Session NEUVE a chaque fois, et
                    rien du run precedent : c'est le prix de l'isolement.
    -Here           le repertoire courant, explicitement. Le script previent si ce
                    dossier est dans le depot.
    -Workspace <d>  un dossier nomme, cree s'il manque.
  -Ask "<tache>"    Une seule tache (profil headless), pas d'UI, rend la main a la fin.
                    Sans -Ask, ouvre l'UI de chat.
  -Port <n>         Port de l'UI web. Defaut 8010.
  -Cheap            Demarre le proxy "upstream le moins cher" (scripts/openrouter_
                    cheapest_proxy.mjs) s'il ne tourne pas deja. Requis par la route
                    openrouter-cheap.
  -ProxyPort <n>    Port de ce proxy. Defaut 8011.
  -NoOpen           Ne pas ouvrir le navigateur automatiquement.
  -Stop             Arrete l'UI et le proxy, puis sort.
  -QuarantineSession <dir>
                    Deplace UN repertoire de session hors de ~/.dsh/sessions, vers
                    ~/.dsh/quarantine/<horodatage>/. Les octets sont CONSERVES ;
                    rien n'est supprime. Sert quand le preflight nomme un journal.
  -SkipSessionCheck Sauter le preflight du magasin de sessions (voir plus bas).
  -DshVersion <v>   Version de @deepseek-ai/dsh a lancer. Defaut 0.1.1-rc.2.
  -InstallRuntime   (Re)construit l'arbre EPINGLE de cette version sous
                    ~/.dsh/runtime/dsh-<v>, puis sort. A faire UNE fois par
                    version ; ensuite le boot le prefere a npx tout seul.
  -SkipTreeCheck    Sauter le preflight de coherence de l'arbre (voir plus bas).
  -InstallPlugins   Monte les greffons de scripts/dsh-plugins/ dans les profils
                    web et headless (jonction + rangee dans cordis.patch.yml),
                    puis sort. Idempotent. Voir plus bas.
  -SubagentTimeoutMs <n>
                    Borne posee par -InstallPlugins sur un sous-agent. Defaut
                    600000 (10 min).
  -Help             Ceci.

LE PREFLIGHT DU MAGASIN DE SESSIONS (scripts/dsh_session_check.mjs)
  Au boot, dsh parcourt TOUTES les sessions de TOUS les workspaces. UN journal
  illisible fait echouer le boot partout, et la trace ne NOMME AUCUN FICHIER :
    "plugin tree failed to load: ... corrupt Zstandard session log"
  Le preflight rejoue les trois refus possibles et sort le NOM du fautif avec la
  commande de quarantaine. Il DECRIT, il ne bloque pas : le lancement suit.

LE PREFLIGHT DE COHERENCE DE L'ARBRE (scripts/dsh_tree_check.mjs)
  Ce script n'epingle que @deepseek-ai/dsh ; ses 65 dependances sont declarees en
  caret, donc npm resout les greffons au plus recent < 0.2.0 le JOUR de
  l'installation. L'app et ses greffons peuvent donc diverger sans que rien ne le
  dise. Mesure du 21/08 : app 0.1.0-rc.7 + 185 greffons 0.1.0-rc.8, et rc.8
  enregistrait une section de prompt a nom fixe "delegation:policy" que les
  presets livres declarent DEUX fois. Plus aucun preset ne montait :
    "preset 'standard' failed to mount: prompt section 'delegation:policy'
     is already registered in this scope"
  L'UI repondait 200 et aucun modele ne chargeait. Le preflight NOMME les presets
  concernes. Il DECRIT, il ne bloque pas.
  -DshVersion <v> pour epingler autre chose ; -SkipTreeCheck pour le sauter.

L'ARBRE EPINGLE (~/.dsh/runtime/dsh-<version>)
  La reparation de fond, pas le detecteur : npx re-resout les greffons a chaque
  installation, donc on installe UNE fois avec des `overrides` exacts sur les 186
  paquets du scope, et le package-lock.json fige l'arbre pour de bon.
    .\scripts\dsh.ps1 -InstallRuntime                 (version par defaut)
    .\scripts\dsh.ps1 -InstallRuntime -DshVersion <v> (une autre)
  Ensuite le boot prend ce binaire tout seul. S'il manque, le script le DIT et
  retombe sur npx -- il ne t'arrete pas, mais l'arbre redevient flottant.

LA BORNE DES SOUS-AGENTS (scripts/dsh-plugins/dsh-subagent-timeout)
  dsh livre bien une politique de timeout, mais elle est COOPERATIVE : elle
  n'arme une echeance que sur les outils qui declarent un `timeoutMs`. Or
  `subagent` et `subagent_fork` n'en declarent AUCUN -- verifie sur le master
  amont, meme version. Un enfant qui ne finit pas ne finit donc jamais, et il
  faut aller le tuer a la main. Le greffon local pose la borne manquante :
    .\scripts\dsh.ps1 -InstallPlugins                        (10 min par defaut)
    .\scripts\dsh.ps1 -InstallPlugins -SubagentTimeoutMs 1800000
  Au boot il s'annonce sur stderr ("subagent-timeout: arme a N ms sur ...") :
  pas d'annonce = pas de borne, ne pas le deduire du fichier de config.
  ARRETER UN ENFANT DEJA PARTI, sans attendre la borne : les fournisseurs sont
  `in-process`, il n'y a donc AUCUN processus a tuer. Dans la conversation,
  `list_agents` puis `interrupt_agent <id>`. Sinon .\scripts\dsh.ps1 -Stop,
  qui emporte tout le serveur.

CE QUE LE SCRIPT PREPARE POUR TOI
  1. le repertoire de travail          bac a sable par defaut ; -Here / -Fresh /
                                        -Workspace pour en changer
  2. l'environnement                    DSH_TELEMETRY_DISABLED=1, DSH_LOCAL_API_KEY,
                                        et OPENROUTER_API_KEY lue depuis le .env du
                                        depot -- jamais affichee, jamais recopiee
  3. il ANNONCE la route active         lue dans ~/.dsh/settings.yaml, et ne sonde que
                                        le serveur dont cette route depend

LA LIGNE A LIRE AVANT DE LANCER
  "route active : <provider> / <modele>"
  L'UI REECRIT ce defaut des que tu choisis un modele avec /model -- y compris pour
  les -Ask suivants. Une route openrouter* est PAYANTE (~8 000 tokens d'entree par
  tour d'agent). Le script te previent, il ne t'arrete pas.

ROUTES DISPONIBLES (definies dans ~/.dsh/settings.yaml, pas ici)
  local             llama-server :8004, gratuit, RTX 4090
  openrouter        DeepSeek V4 Pro (flottant / GA 0813) et Qwen3.8-27B, +suffixe :floor
  openrouter-cheap  via le proxy :8011, qui classe les upstreams par cout reel

EN CAS DE PANNE, UN SEUL DES TROIS MANQUE
  mauvais dossier  -> l'agent ne voit pas tes fichiers / session introuvable
  cle absente      -> MISSING_CREDENTIAL. Ajouter une ROUTE a chaud marche,
                      ajouter une CLE non : il faut relancer le process.
  serveur absent   -> erreur de connexion au premier message

AIDE DETAILLEE
  Get-Help .\scripts\dsh.ps1 -Full
'@
    Write-Host $usage
    return
}

function Get-ListenerPid([int]$p) {
    $line = netstat -ano | Select-String -Pattern (":{0}\s" -f $p) |
            Select-String -Pattern 'LISTENING' | Select-Object -First 1
    if ($null -eq $line) { return $null }
    return ($line.Line -split '\s+')[-1]
}

# --- l'arbre EPINGLE : ~/.dsh/runtime/dsh-<version> -------------------------
# `npx -y @deepseek-ai/dsh@<v>` n'epingle QUE ce paquet. Ses 65 dependances sont
# declarees en caret, donc npm les RE-RESOUT a chaque installation et l'arbre
# derive tout seul -- mesure du 21/08 : app 0.1.0-rc.7, greffons 0.1.0-rc.8, et
# plus aucun preset ne montait. On installe donc une seule fois, avec des
# `overrides` EXACTS sur tout le scope, dans un repertoire a nous ; le
# package-lock.json qui en sort fige l'arbre. Le boot prefere ce binaire et ne
# retombe sur npx qu'a defaut, en le DISANT.
$RuntimeRoot = Join-Path (Join-Path $env:USERPROFILE '.dsh') 'runtime'
$RuntimeDir  = Join-Path $RuntimeRoot ('dsh-' + $DshVersion)
$RuntimeBin  = Join-Path (Join-Path (Join-Path $RuntimeDir 'node_modules') '.bin') 'dsh.cmd'
$Self        = Join-Path (Join-Path '.' 'scripts') 'dsh.ps1'

if ($InstallRuntime) {
    # Les NOMS du scope viennent d'un arbre deja installe (npx ou runtime) : c'est
    # la seule source qui connaisse les dependances TRANSITIVES. Sans aucun arbre
    # sous la main on installe sans overrides -- correct, mais npm peut thrasher
    # sur 186 plages de prerelease (mesure : 12 min a 100 % de CPU et 3,4 Go sans
    # ecrire un seul paquet). On le dit plutot que de le cacher.
    $names = New-Object System.Collections.Generic.HashSet[string]
    $scan  = @()
    $npxRoot = Join-Path (Join-Path $env:LOCALAPPDATA 'npm-cache') '_npx'
    if (Test-Path $npxRoot)     { $scan += (Get-ChildItem -Directory $npxRoot     | ForEach-Object { $_.FullName }) }
    if (Test-Path $RuntimeRoot) { $scan += (Get-ChildItem -Directory $RuntimeRoot | ForEach-Object { $_.FullName }) }
    foreach ($dir in $scan) {
        $scoped = Join-Path (Join-Path $dir 'node_modules') '@deepseek-ai'
        if (-not (Test-Path $scoped)) { continue }
        # SEULEMENT dsh et dsh-* : le scope @deepseek-ai/ heberge aussi cordis
        # 4.0.1, cosmokit 1.8.2, schemastery 3.18.1, node-addon-landlock-run
        # 0.1.1 et cinq cordis-plugin-*, qui ont leur PROPRE versionnement.
        # Les forcer a la version de dsh casse l'installation (ETARGET) --
        # mesure 21/08 : 11 paquets du scope sur 197 sont dans ce cas, et les
        # 188 restants sont tous a 0.1.1-rc.2, donc le motif dsh* est exact.
        foreach ($p in (Get-ChildItem -Directory $scoped)) {
            if ($p.Name -ne 'dsh' -and -not $p.Name.StartsWith('dsh-')) { continue }
            [void]$names.Add('@deepseek-ai/' + $p.Name)
        }
    }
    [void]$names.Add('@deepseek-ai/dsh')

    $overrides = [ordered]@{}
    foreach ($n in ($names | Sort-Object)) { $overrides[$n] = $DshVersion }
    $manifest = [ordered]@{
        name         = 'dsh-runtime'
        private      = $true
        version      = '1.0.0'
        dependencies = [ordered]@{ '@deepseek-ai/dsh' = $DshVersion }
        overrides    = $overrides
    }
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    # Serialiser A COTE puis deplacer : ouvrir le fichier cible le tronque AVANT
    # que l'ecriture puisse echouer. Sans BOM, npm lit du JSON, pas de l'UTF-8
    # decore.
    $target = Join-Path $RuntimeDir 'package.json'
    $tmp    = $target + '.tmp'
    [System.IO.File]::WriteAllText($tmp, ($manifest | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -Path $tmp -Destination $target -Force

    Write-Host ("arbre epingle : {0}" -f $RuntimeDir)
    Write-Host ("  {0} paquets du scope forces a {1}" -f $overrides.Count, $DshVersion)
    if ($overrides.Count -le 1) {
        Write-Warning "aucun arbre @deepseek-ai deja installe : npm va tout re-resoudre a partir des plages caret. Compter >10 min, ou un thrash."
    }
    Push-Location $RuntimeDir
    try { & npm install --no-audit --no-fund }
    finally { Pop-Location }
    if (Test-Path $RuntimeBin) { Write-Host ("pret : {0}" -f $RuntimeBin) }
    else { Write-Warning ("npm a rendu la main mais {0} n'existe pas." -f $RuntimeBin) }
    return
}

# --- -InstallPlugins : monter les greffons LOCAUX dans les profils dsh ------
# Un greffon qui vit dans le depot mais n'est cable que par une edition a la
# main sous ~/.dsh est invisible en lisant l'arbre, et il meurt au prochain
# `pnpm install` du profil. Cette etape est son APPELANT : elle cree la
# jonction (repertoire, donc pas besoin d'admin) et insere la rangee dans la
# couche patch du profil. Idempotente : relancer ne duplique rien.
if ($InstallPlugins) {
    $pluginRoot = Join-Path $PSScriptRoot 'dsh-plugins'
    if (-not (Test-Path $pluginRoot)) { throw "aucun greffon local sous $pluginRoot" }
    $profilesRoot = Join-Path (Join-Path $env:USERPROFILE '.dsh') 'profiles'

    foreach ($profileName in @('web', 'headless')) {
        $profileDir = Join-Path $profilesRoot $profileName
        if (-not (Test-Path $profileDir)) { Write-Warning ("profil absent, ignore : {0}" -f $profileDir); continue }
        Write-Host ("profil {0}" -f $profileName)

        $modules = Join-Path $profileDir 'node_modules'
        New-Item -ItemType Directory -Force -Path $modules | Out-Null
        foreach ($plugin in (Get-ChildItem -Directory $pluginRoot)) {
            $link = Join-Path $modules $plugin.Name
            if (Test-Path $link) { Write-Host ("  {0} : deja monte" -f $plugin.Name) }
            else {
                New-Item -ItemType Junction -Path $link -Target $plugin.FullName | Out-Null
                Write-Host ("  {0} : jonction creee" -f $plugin.Name)
            }
        }

        # La rangee. Le chargeur n'INSERE que via `- insert:` ; une entree
        # `- id:` nue ne fait que CIBLER une rangee existante et sort
        # "entry not found" (mesure du 21/08, premier essai).
        $patch = Join-Path $profileDir 'cordis.patch.yml'
        if (-not (Test-Path $patch)) { Write-Warning ("couche patch absente : {0}" -f $patch); continue }
        $text = Get-Content -Raw -Path $patch
        if ($text -match 'id:\s*subagent-timeout') {
            Write-Host "  rangee subagent-timeout : deja presente"
            continue
        }
        $row = @(
            '',
            '# Borne de duree par defaut sur les outils de delegation.',
            '# `subagent` / `subagent_fork` ne declarent AUCUN `timeoutMs`, donc la',
            '# politique livree `timeout-policy` ne peut rien armer sur eux : un enfant',
            '# qui ne finit pas ne finit jamais. Pose par dsh.ps1 -InstallPlugins.',
            '- insert:',
            '    - id: subagent-timeout',
            '      name: dsh-subagent-timeout',
            '      config:',
            ('        timeoutMs: {0}' -f $SubagentTimeoutMs),
            ''
        ) -join "`n"
        # `[]` est le marqueur de liste VIDE du fichier livre : le laisser en
        # place ferait deux documents. Sinon on ajoute a la suite, une liste
        # YAML de tete acceptant des elements supplementaires.
        if ($text -match '(?m)^\[\]\s*$') { $body = ($text -replace '(?m)^\[\]\s*$', '').TrimEnd() }
        else { $body = $text.TrimEnd() }
        $merged = $body + "`n" + $row
        $tmp = $patch + '.tmp'
        [System.IO.File]::WriteAllText($tmp, $merged, (New-Object System.Text.UTF8Encoding($false)))
        Move-Item -Path $tmp -Destination $patch -Force
        Write-Host ("  rangee subagent-timeout inseree ({0} ms)" -f $SubagentTimeoutMs)
    }
    Write-Host ""
    Write-Host "relance dsh pour que les profils prennent ces rangees ; au boot le greffon s'annonce sur stderr :"
    Write-Host ("  subagent-timeout: arme a {0} ms sur subagent, subagent_fork" -f $SubagentTimeoutMs)
    return
}

# --- -QuarantineSession : on deplace UN journal fautif, on ne supprime rien --
# Le magasin de sessions est un CACHE, mais il porte l'historique de chat : on
# DEPLACE, jamais on n'efface. Le repertoire de destination reproduit le chemin
# d'origine (projet/session) pour qu'un retour en arriere soit une seule commande.
if ($QuarantineSession) {
    if (-not (Test-Path $QuarantineSession)) { throw "repertoire de session introuvable : $QuarantineSession" }
    $src         = (Resolve-Path $QuarantineSession).Path
    $sessionRoot = Join-Path $env:USERPROFILE '.dsh\sessions'
    if (-not $src.StartsWith($sessionRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "refus : $src n'est pas sous $sessionRoot"
    }
    $sessionName = Split-Path -Leaf $src
    $projectName = Split-Path -Leaf (Split-Path -Parent $src)
    $stamp       = Get-Date -Format 'yyyyMMdd-HHmmss'
    $dest        = Join-Path $env:USERPROFILE ('.dsh\quarantine\{0}\{1}' -f $stamp, $projectName)
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Move-Item -Path $src -Destination $dest
    $moved = Join-Path $dest $sessionName
    Write-Host ("session mise en quarantaine (rien n'est supprime) :")
    Write-Host ("  depuis : {0}" -f $src)
    Write-Host ("  vers   : {0}" -f $moved)
    Write-Host ("pour la remettre : Move-Item '{0}' '{1}'" -f $moved, (Split-Path -Parent $src))
    return
}

# --- -Stop : on arrete et on sort ------------------------------------------
if ($Stop) {
    foreach ($pair in @(@{n='UI';p=$Port}, @{n='proxy';p=$ProxyPort})) {
        $listenerPid = Get-ListenerPid $pair.p
        if ($listenerPid) {
            taskkill /PID $listenerPid /T /F | Out-Null
            Write-Host ("{0} arrete (PID {1}, port {2})" -f $pair.n, $listenerPid, $pair.p)
        } else {
            Write-Host ("{0} : rien n'ecoute sur {1}" -f $pair.n, $pair.p)
        }
    }
    return
}

# --- ingredient 1 : le repertoire de travail --------------------------------
# DEFAUT = un workspace TEMPORAIRE, jamais le repertoire courant. L'agent ecrit
# dans son cwd : lancer depuis le depot lui donnerait le depot comme terrain de
# jeu, et un simple "cd" oublie suffirait. Il faut donc DEMANDER le depot.
#   (defaut)          bac a sable stable -> l'historique et les fichiers survivent
#   -Fresh            dossier horodate jetable -> nouvelle session a chaque fois
#   -Here             le repertoire courant, explicitement
#   -Workspace <dir>  un dossier nomme (cree s'il manque)
$ScratchRoot = Join-Path $env:LOCALAPPDATA 'Temp\dsh-workspace'

if ($Workspace) {
    if (-not (Test-Path $Workspace)) { New-Item -ItemType Directory -Force -Path $Workspace | Out-Null }
    $target = (Resolve-Path $Workspace).Path
    $origin = 'dossier nomme (-Workspace)'
} elseif ($Fresh) {
    $target = Join-Path $ScratchRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $origin = 'jetable (-Fresh) -- session neuve, rien du run precedent'
} elseif ($Here) {
    $target = (Get-Location).Path
    $origin = 'repertoire courant (-Here)'
} else {
    if (-not (Test-Path $ScratchRoot)) { New-Item -ItemType Directory -Force -Path $ScratchRoot | Out-Null }
    $target = $ScratchRoot
    $origin = 'bac a sable par defaut'
}

# On ne fait PAS Set-Location : ca deplacerait le shell de l'appelant et il se
# retrouverait dans le bac a sable apres coup. Le cwd est pousse UNIQUEMENT autour
# de l'appel npx, plus bas, et depile dans un finally.
$cwd = $target
Write-Host ("espace de travail : {0}   [{1}]" -f $cwd, $origin)

# Le slug de session DERIVE du cwd : changer d'espace de travail change de
# conversation. C'est aussi ce qui rend un espace partage dangereux.
if ($cwd.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warning "  cet espace est DANS le depot : l'agent peut y ecrire. git status avant/apres."
}

# --- ingredient 2 : l'environnement ----------------------------------------
$env:DSH_TELEMETRY_DISABLED = '1'          # en plus du defaut DISABLED du paquet
$env:DSH_LOCAL_API_KEY      = 'local-dummy' # llama.cpp ne verifie rien, mais la
                                            # reference doit resoudre vers QUELQUE chose

$envFile = Join-Path $RepoRoot '.env'
$orKey = $null
if (Test-Path $envFile) {
    $hit = Get-Content $envFile | Where-Object { $_ -like 'OPENROUTER_API_KEY=*' } | Select-Object -First 1
    if ($hit) { $orKey = ($hit -replace '^OPENROUTER_API_KEY=', '').Trim().Trim('"').Trim("'") }
}
if ($orKey) {
    $env:OPENROUTER_API_KEY = $orKey
    Write-Host ("cle OpenRouter chargee depuis .env (longueur {0}, jamais affichee)" -f $orKey.Length)
} else {
    Write-Warning "OPENROUTER_API_KEY absente du .env : les routes openrouter* refuseront (MISSING_CREDENTIAL). La route 'local' fonctionne quand meme."
}

# --- ingredient 3 : QUELLE route est active, et son serveur -----------------
# Le defaut ne vit PAS dans ce script : il est dans ~/.dsh/settings.yaml, et l'UI
# le REECRIT des qu'on choisit un modele avec /model. On le lit donc a chaque
# lancement et on l'annonce -- sinon on croit taper sur le 4090 gratuit alors
# qu'on facture des tokens OpenRouter (mesure 2026-08-20).
function Test-Port([string]$h, [int]$p) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $null = $c.ConnectAsync($h, $p).Wait(2000); return $c.Connected }
    catch { return $false } finally { $c.Dispose() }
}

$settings = Join-Path $env:USERPROFILE '.dsh\settings.yaml'
$route = $null; $model = $null
if (Test-Path $settings) {
    $txt = Get-Content $settings
    for ($i = 0; $i -lt $txt.Count; $i++) {
        if ($txt[$i] -match '^agent-default-model:') {
            foreach ($j in ($i + 1)..([Math]::Min($i + 4, $txt.Count - 1))) {
                if ($txt[$j] -match '^\s+provider:\s*(\S+)') { $route = $Matches[1] }
                if ($txt[$j] -match '^\s+model:\s*(\S+)')    { $model = $Matches[1] }
            }
            break
        }
    }
}
if ($route) { Write-Host ("route active : {0} / {1}" -f $route, $model) }
else { Write-Warning "agent-default-model illisible dans $settings" }

# On ne sonde QUE le serveur dont la route active depend.
if ($route -eq 'local') {
    if (Test-Port '127.0.0.1' 8004) { Write-Host "  llama-server :8004 en ligne (gratuit, RTX 4090)" }
    else { Write-Warning "  llama-server :8004 muet : cette route echouera. Relancer scripts\restart_production.ps1" }
} elseif ($route -eq 'openrouter-cheap') {
    if (Test-Port '127.0.0.1' $ProxyPort) { Write-Host ("  proxy :{0} en ligne" -f $ProxyPort) }
    else { Write-Warning ("  proxy :{0} absent : cette route echouera. Relancer avec -Cheap" -f $ProxyPort) }
} elseif ($route -like 'openrouter*') {
    Write-Host "  ATTENTION : route PAYANTE (OpenRouter). Un tour d'agent coute ~8 000 tokens d'entree."
}

if ($Cheap) {
    if (Get-ListenerPid $ProxyPort) {
        Write-Host ("proxy 'moins cher' deja en ecoute sur {0}" -f $ProxyPort)
    } else {
        $proxy = Join-Path $PSScriptRoot 'openrouter_cheapest_proxy.mjs'
        Start-Process -FilePath 'node' -ArgumentList @($proxy, '--port', $ProxyPort) `
                      -WorkingDirectory $RepoRoot -WindowStyle Minimized
        Start-Sleep -Seconds 2
        if (Get-ListenerPid $ProxyPort) { Write-Host ("proxy demarre sur {0}" -f $ProxyPort) }
        else { Write-Warning "le proxy n'ecoute pas encore ; la route 'openrouter-cheap' echouera" }
    }
}

# --- preflight : le magasin de sessions peut-il seulement etre LISTE ? -------
# dsh-workspace appelle listArtifacts() au boot, qui parcourt TOUTES les sessions
# de TOUS les workspaces sous ~/.dsh/sessions. Un seul journal illisible fait
# echouer le boot partout, et la trace ne nomme AUCUN fichier (mesure 21/08 :
# un journal ayant perdu sa frame d'en-tete tenait dsh mort dans tous les profils).
# Ce controle NOMME le fautif. Il decrit, il ne refuse pas : le lancement suit.
if (-not $SkipSessionCheck) {
    $checker = Join-Path $PSScriptRoot 'dsh_session_check.mjs'
    if (Test-Path $checker) {
        $report = & node $checker 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host ($report | Select-Object -First 1)
        } else {
            Write-Warning "le magasin de sessions bloque le boot -- le detail suit, dsh va probablement echouer :"
            $report | ForEach-Object { Write-Host ("  " + $_) }
        }
    } else {
        Write-Warning "preflight absent ($checker) : un journal de session fautif ne sera pas nomme."
    }
}

# --- preflight : l'app et ses greffons sont-ils de la MEME version ? ---------
# Le lanceur n'epingle que @deepseek-ai/dsh ; ses 65 dependances sont en caret,
# donc npm les resout au plus recent < 0.2.0 le jour de l'installation. Mesure
# du 21/08 : app 0.1.0-rc.7 + 185 greffons 0.1.0-rc.8, et rc.8 enregistrait une
# section de prompt a nom FIXE que les presets livres declarent deux fois. Plus
# aucun preset ne montait : l'UI repondait 200, aucun modele ne chargeait.
# Ce controle NOMME les presets qui ne peuvent pas monter. Il decrit, il ne
# refuse pas : le lancement suit.
if (-not $SkipTreeCheck) {
    $treeChecker = Join-Path $PSScriptRoot 'dsh_tree_check.mjs'
    if (Test-Path $treeChecker) {
        $treeReport = & node $treeChecker $DshVersion 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host ($treeReport | Select-Object -Last 1)
        } else {
            Write-Warning "l'arbre npx est incoherent -- le detail suit, aucune session ne s'ouvrira :"
            $treeReport | ForEach-Object { Write-Host ("  " + $_) }
        }
    } else {
        Write-Warning "preflight absent ($treeChecker) : un arbre npx incoherent ne sera pas nomme."
    }
}

# --- boot -------------------------------------------------------------------
$pkg = '@deepseek-ai/dsh@' + $DshVersion

# L'arbre epingle d'abord ; npx seulement a defaut, et jamais en silence.
if (Test-Path $RuntimeBin) {
    $exe = $RuntimeBin
    $pre = @()
    Write-Host ("arbre       : epingle -- {0}" -f $RuntimeDir)
} else {
    $exe = 'npx'
    $pre = @('-y', $pkg)
    Write-Warning ("aucun arbre epingle pour {0} : npx va re-resoudre les greffons, et l'arbre peut deriver sous toi. Le figer : {1} -InstallRuntime -DshVersion {0}" -f $DshVersion, $Self)
}

if ($Ask) {
    Write-Host "tache one-shot (profil headless)"
    Push-Location $cwd
    try { & $exe @pre --profile headless $Ask }
    finally { Pop-Location }
    exit $LASTEXITCODE
}

$busy = Get-ListenerPid $Port
if ($busy) {
    Write-Warning ("le port {0} est deja pris (PID {1}). Soit l'UI tourne deja -> http://127.0.0.1:{0}, soit relance avec -Stop puis retente, soit choisis -Port <autre>." -f $Port, $busy)
    return
}

Write-Host ("UI de chat  : http://127.0.0.1:{0}" -f $Port)
Write-Host "Ctrl+C pour arreter, ou depuis un autre terminal : .\scripts\dsh.ps1 -Stop"

$dshArgs = $pre + @('web', '--host', '127.0.0.1', '--port', $Port)
if ($NoOpen) { $dshArgs += '--no-open' }
Push-Location $cwd
try { & $exe @dshArgs }
finally { Pop-Location }
