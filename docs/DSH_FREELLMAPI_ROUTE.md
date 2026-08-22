# Câbler dsh sur FreeLLMAPI (routeur local, 380 modèles gratuits)

**Pour qui :** un agent qui doit ajouter à `dsh` une route LLM passant par FreeLLMAPI,
le routeur OpenAI-compatible installé localement le 2026-08-22.

**Ce que ça ouvre :** `deepseek-ai/DeepSeek-V4-Pro` et `DeepSeek-V4-Flash` — le modèle
natif de dsh — deviennent accessibles **gratuitement**, sans clef DeepSeek, avec
bascule automatique vers 379 autres modèles quand un fournisseur rend 429 ou vide.

**État mesuré à l'écriture (2026-08-22, ne pas recopier sans re-mesurer) :**

| | |
|---|---|
| Endpoint | `http://127.0.0.1:31415/v1` |
| Licence | `lifetime` / `active`, catalogue palier `live` v2026.08.20.9eb863ca |
| Catalogue | 517 modèles ; **380 réellement servis** (les 137 autres n'ont pas de clef active) |
| Clefs fournisseurs | 16, toutes `healthy` |
| Appel témoin | `model:"auto"` → HTTP 200 en **2,4 s**, servi par `zai-org/GLM-5.1` |

---

## 0. Avant d'écrire : l'endpoint répond-il ENCORE ?

L'app est un service de bureau ; elle peut être éteinte. **Sonder d'abord, écrire ensuite.**

```powershell
Get-Process -Name FreeLLMAPI -ErrorAction SilentlyContinue | Select-Object Id
```

Si rien ne sort, l'app est fermée. La relancer :

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\freellmapi-desktop\FreeLLMAPI.exe"
```

Elle vit dans la zone de notification et n'ouvre aucune fenêtre au démarrage.
Relancer l'exécutable une seconde fois déclenche le gestionnaire `second-instance`
et ouvre le tableau de bord — c'est le seul moyen de le faire apparaître.

**Le port est 31415, PAS 3001.** La documentation amont annonce partout 3001 ; c'est le
port du déploiement serveur. L'app Desktop lit `%APPDATA%\FreeLLMAPI\config.json`, qui
porte `{"port": 31415}` (`desktop/src/main.ts:12`, `DEFAULT_PORT`). Vérifier ce fichier
plutôt que supposer : `listenWithScan` balaie 50 ports si 31415 est pris.

---

## 1. La clef unifiée — la lire, jamais la recopier dans un fichier versionné

FreeLLMAPI a **deux** clefs, ne pas les confondre :

| clef | forme | rôle |
|---|---|---|
| licence premium | `fla_…` (36 car.) | achète le catalogue vivant ; vit dans `.env` du dépôt sous `FREE_LLM_API_KEY` ; **jamais utilisée comme clef d'API** |
| clef unifiée | `freellmapi-…` (59 car.) | **c'est celle-ci** que dsh doit présenter en `Authorization: Bearer` |

Trois façons de récupérer la clef unifiée, par ordre de préférence :

1. menu de l'icône dans la zone de notification → **Copy API key** ;
2. tableau de bord → page **Keys**, en en-tête ;
3. en base, sans affichage :

```python
import sqlite3
db = r"C:\Users\test\AppData\Roaming\FreeLLMAPI\freeapi.db"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)   # mode=ro : l'app tient le WAL
KEY = con.execute("SELECT value FROM settings WHERE key='unified_api_key'").fetchone()[0]
```

⚠️ **Ne jamais écrire la valeur dans `~/.dsh/settings.yaml`.** dsh n'attend pas un secret
mais le **nom** d'une variable d'environnement (`apiKeyEnv`). C'est la convention de
toutes les routes déjà présentes dans ce fichier.

---

## 2. Le piège qui tue la route : `apiKeyEnv` DÉCLARÉ n'est pas `apiKeyEnv` DÉFINI

Ce piège est déjà documenté dans `~/.dsh/settings.yaml` lui-même, et il a déjà fait une
victime : la route `local` référence `DSH_LOCAL_API_KEY`, **qui n'est définie nulle part**
(ni process, ni utilisateur, ni machine) — cette route est cassée pour cette raison exacte,
et l'erreur rendue est trompeuse :

```
PI_AI_ERROR: No API key for provider
```

Elle ne dit pas « variable vide », elle dit « pas de clef », ce qui envoie chercher au
mauvais endroit. `llm-pi-ai` exige une clef **même sur une route locale non authentifiée**.

**Donc, deux gestes, pas un.** Le second se fait dans `scripts/dsh.ps1`, à côté de la ligne
qui pose déjà `$env:DSH_LOCAL_API_KEY = 'local-dummy'` (~ligne 601) :

```powershell
# FreeLLMAPI : routeur local. La clef unifiee est LUE au lancement, jamais ecrite ici.
$env:DSH_FREELLM_API_KEY = (& python "$PSScriptRoot\freellm_key.py")
if (-not $env:DSH_FREELLM_API_KEY) { Write-Warning 'DSH_FREELLM_API_KEY vide -> la route freellm rendra "No API key for provider"' }
```

`scripts/freellm_key.py` est versionné dans ce dépôt. **Ne pas le remplacer par un
`python -c` en ligne** : la version en une ligne exige des guillemets imbriqués
(PowerShell → python → SQL) et le canal les mange. Mesuré le 2026-08-22 — le one-liner
rendait `SyntaxError: unterminated string literal` et laissait la variable **vide**, ce qui
ne se manifeste qu'au premier appel, sous la forme trompeuse `No API key for provider`.

Contrôle des deux bras, à relancer après toute modification :

```powershell
python scripts\freellm_key.py                 # attendu : 59 caracteres, prefixe freellmapi-
python scripts\freellm_key.py C:\pas\une\base.db   # attendu : code 1 + "base introuvable"
```

Le second bras n'est pas une formalité : **un contrôle qui n'a jamais échoué exprès n'a pas
été montré comme mesurant quoi que ce soit.** Et l'avertissement du script n'est pas
décoratif — **une route dont la clef est vide échoue en permissif** : elle est montée,
visible dans `/model`, et ne casse qu'au premier appel.

---

## 3. La route, dans `~/.dsh/settings.yaml`

Ajouter sous `llm-pi-ai.providers:`, à côté de `local`, `local-vision`, `local-think`,
`openrouter`, `openrouter-cheap` :

```yaml
    # Routeur FreeLLMAPI local (app Desktop, port 31415). Agrege 16 fournisseurs
    # gratuits derriere UN endpoint OpenAI-compatible, avec bascule automatique
    # sur 429/5xx/complétion vide. Mesure 22/08 : 380 modeles servis sur 517 au
    # catalogue -- l'ecart, ce sont les modeles sans clef fournisseur active.
    freellm:
      name: FreeLLMAPI (routeur local)
      apiKeyEnv: DSH_FREELLM_API_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:31415/v1
      # Plancher prudent : voir le piege des fenetres de contexte en §5.
      defaultContextWindow: 131072
      models:
        # Modele VIRTUEL : le routeur choisit. C'est lui qui apporte la bascule.
        - id: auto
          name: FreeLLMAPI - routeur automatique
          contextWindow: 131072
        - id: auto:smart
          name: FreeLLMAPI - privilegie l'intelligence
          contextWindow: 131072
        - id: auto:fast
          name: FreeLLMAPI - privilegie la vitesse
          contextWindow: 131072
        # Modeles EPINGLES : pas de bascule, mais un comportement reproductible.
        - id: deepseek-ai/DeepSeek-V4-Pro
          name: DeepSeek V4 Pro (gratuit, via HuggingFace)
          contextWindow: 131072
        - id: deepseek-ai/DeepSeek-V4-Flash
          name: DeepSeek V4 Flash (gratuit, via HuggingFace)
          contextWindow: 131072
        - id: Qwen/Qwen3-Coder-480B-A35B-Instruct
          name: Qwen3 Coder 480B (gratuit)
          contextWindow: 262144
        - id: moonshotai/Kimi-K3
          name: Kimi K3 (gratuit)
          contextWindow: 262144
        - id: gemini-3.7-flash
          name: Gemini 3.7 Flash (gratuit, 1M de contexte)
          contextWindow: 1048576
```

Pour en faire le défaut, `agent-default-model` — mais **l'UI réécrit ce bloc dès qu'on
utilise `/model`**, donc ne pas s'y fier pour savoir quelle route tourne :

```yaml
agent-default-model:
  provider: freellm
  model: auto
```

### Les modèles virtuels `auto:*`

`auto` suit la chaîne de repli active du tableau de bord. Les suffixes réordonnent
**tous** les modèles activés pour une seule requête, sans rien changer au tableau de bord :
`auto:smart` (intelligence), `auto:fast` (débit + temps au premier octet), `auto:reliable`
(taux de succès récent), `auto:balanced` (le défaut), `auto:cheap`. `auto:<profil>` route
par une chaîne nommée. Un profil inconnu rend un `400` explicite, pas un repli silencieux.

---

## 4. Prouver que ça tourne — étape non contournable

**Une route montée n'est pas une route qui répond.** Le témoin doit nommer le modèle
réellement servi, pas se contenter d'un HTTP 200.

```python
import sqlite3, json, urllib.request, time
db = r"C:\Users\test\AppData\Roaming\FreeLLMAPI\freeapi.db"
KEY = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
    "SELECT value FROM settings WHERE key='unified_api_key'").fetchone()[0]
req = urllib.request.Request(
    "http://127.0.0.1:31415/v1/chat/completions",
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    data=json.dumps({"model": "auto",
                     "messages": [{"role": "user", "content": "Reponds exactement: PONG"}],
                     "max_tokens": 16, "temperature": 0}).encode())
t0 = time.time()
with urllib.request.urlopen(req, timeout=180) as r:
    body = json.loads(r.read())
    print("modele servi :", body["model"], f"en {time.time()-t0:.1f}s")
    print("bascules     :", r.headers.get("x-fallback-trail") or "aucune")
```

Sortie du 2026-08-22 (à re-mesurer, pas à recopier) :

```
modele servi : zai-org/GLM-5.1 en 2.4s
bascules     : google/gemini-3-flash-preview key1=empty_completion
```

**Lire la deuxième ligne.** `x-fallback-trail` nomme chaque saut qui a échoué et pourquoi.
Ici Gemini a rendu une complétion vide et le routeur est passé à GLM-5.1 : la bascule
n'est pas une promesse de la documentation, elle a tiré pendant le test. Un `x-fallback-trail`
qui s'allonge sur toutes les requêtes est le signal qu'une clef fournisseur est morte —
le regarder avant d'accuser dsh.

Puis, côté dsh, le contrôle qui compte :

```powershell
.\scripts\dsh.ps1 -Provider freellm -Model auto
```

Le script **annonce la route active** qu'il lit dans `~/.dsh/settings.yaml`. Si l'annonce
et le bloc écrit divergent, croire l'annonce.

---

## 5. Les six pièges mesurés

**1 — La fenêtre de contexte de `auto` est un PLAFOND, pas une garantie.**
`/v1/models` annonce `context_window: 1048576` pour `auto`. C'est le contexte du plus
large modèle du pool (`server/src/routes/proxy.ts:303`), pas ce que la requête obtiendra :
si le routeur atterrit sur `DeepSeek-V4-Pro`, le plafond réel est 131 072. Déclarer
1 048 576 côté dsh ferait partir des requêtes que le serveur refuserait en 400 — exactement
le piège déjà consigné pour `local-think` le 22/08. **Déclarer le plancher du pool, pas le
sommet**, ou épingler un modèle dont on connaît la fenêtre.

**2 — Trois budgets de temps se superposent, et le plus court gagne.**
Côté FreeLLMAPI : timeout de chat par fournisseur (60 s pour la plupart, 180 s NVIDIA),
watchdog de stagnation de flux à 90 s, budget de bascule à 45 s. Mesures du 22/08 : 2,4 s
en `auto`, mais **37,5 s et 39,8 s** sur les gros modèles HuggingFace (550 B). Pour un
harnais d'agent qui enchaîne les appels d'outils, prévoir la marge ou épingler un modèle
rapide. Réglable par `PROVIDER_TIMEOUT_<PLATEFORME>` dans le `.env` de FreeLLMAPI.

**3 — Plafond de débit : 120 requêtes/minute par IP cliente** (`PROXY_RATE_LIMIT_RPM`).
Suffisant pour un agent, pas pour un banc en éventail. Le mettre à 0 le désactive.

**4 — Le raisonnement peut fuir dans le contenu.**
Mesuré : GLM-5.1 a rendu `"1. **Analyze the Request:** ..."` dans `message.content`.
Une route agrégée sert des modèles aux formats de pensée hétérogènes ; **aucun
`thinkingFormat` de dsh ne convient à tous**. Laisser `compat.thinkingFormat` NON déclaré
sur la route `freellm`. Si le raisonnement structuré compte, épingler un modèle et lui
faire son propre bloc `compat`, comme `local-think` le fait déjà.

**5 — La vision exige `input: [text, image]`, en double.**
`llm-pi-ai` met par défaut `DEFAULT_INPUT = ["text"]` et `dsh-mcp-client` REFUSE de
transmettre une image à un modèle qui ne déclare pas la modalité. FreeLLMAPI, lui,
restreint automatiquement le routage aux modèles capables de vision dès qu'une image est
présente — mais **ça ne sert à rien si dsh n'envoie jamais l'image**. Ajouter les deux
lignes sur les modèles concernés.

**6 — 380 servis sur 517 au catalogue.** Trois clefs `healthy` ne routent rien du tout :
`github`, `pollinations`, `siliconflow` ont **0 ligne** dans `models`, `media_models` et
`embedding_models`. Et les 517 lignes sont toutes en `source=catalog` : rien n'est découvert
dynamiquement depuis la clef. Une clef saine n'est donc pas une preuve qu'un modèle existe —
c'est `/v1/models` qui fait foi.

---

## 6. Ce qu'il ne faut PAS faire

- **Ne pas écrire la clef unifiée dans `settings.yaml`** ni dans un fichier versionné.
- **Ne pas toucher `~/.dsh/settings.yaml` sans sauvegarde** : le fichier porte déjà cinq
  `.bak-*`, signe qu'il a été perdu. Copier avant d'éditer.
- **Ne pas remplacer les routes existantes.** `local`, `local-vision`, `local-think`
  portent la campagne de banc du 22/08 et leurs commentaires sont des mesures, pas de la
  prose. Ajouter à côté.
- **Ne pas router un banc « zéro-Anthropic » par `auto`** sans épingler : un modèle qui
  change entre deux mesures rend les deux mesures incomparables. Épingler l'id, et
  journaliser `x-fallback-trail` pour prouver qu'aucune bascule n'a eu lieu.
- **Ne pas ajouter la route `cohere`** côté FreeLLMAPI : la revue ToS du dépôt
  (`docs/architecture.md:101`) la classe ❌ *Avoid* — ses conditions §14 interdisent
  l'usage « personal, family or household purposes ».

---

## 7. Où lire la suite

| besoin | fichier |
|---|---|
| ajouter un greffon à dsh | `docs/DSH_EXTENSION_RECIPE.md` |
| l'historique de la route locale Qwen | `docs/DSH_QWEN_LOCAL_LOGBOOK.md` |
| surfaces d'API de FreeLLMAPI (OpenAI, Anthropic, Gemini, Ollama, MCP) | `C:\Users\test\Documents\freellmapi\docs\api.md` |
| revue ToS par fournisseur | `C:\Users\test\Documents\freellmapi\docs\architecture.md` §« Terms of Service review » |
| variables d'environnement de FreeLLMAPI | `C:\Users\test\Documents\freellmapi\.env.example` |

Le dépôt source est cloné en `C:\Users\test\Documents\freellmapi` — **hors** de
`agentic-flow-fresh`, pour ne pas polluer l'index git partagé.
