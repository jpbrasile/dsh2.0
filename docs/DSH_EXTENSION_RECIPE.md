# Ajouter une fonctionnalité à dsh — recette et pièges

**Pour qui :** un agent qui doit ajouter un comportement à DeepSeek Harness (`dsh`) sans
modifier `node_modules`. Suivre de haut en bas.

**Ce que ça produit :** un greffon cordis local, versionné dans ce dépôt, monté dans les
profils dsh, et dont on peut PROUVER qu'il tourne.

**Exemple travaillé, à lire comme référence :**
[`scripts/dsh-plugins/dsh-subagent-timeout/index.js`](../scripts/dsh-plugins/dsh-subagent-timeout/index.js)
(borne de durée des sous-agents) et son installateur dans
[`scripts/dsh.ps1`](../scripts/dsh.ps1) (`-InstallPlugins`).

---

## 0. Avant d'écrire quoi que ce soit : le comportement existe-t-il déjà ?

dsh est un arbre de ~190 greffons. La moitié des « fonctionnalités manquantes » existent
et sont juste non câblées, ou câblées mais inertes.

```bash
DSH="$HOME/.dsh/runtime/dsh-<version>/node_modules/.bin/dsh.cmd"
"$DSH" --profile web --dump-config          # l'arbre RÉELLEMENT composé, profil par profil
ls "$HOME/.dsh/runtime/dsh-<version>/node_modules/@deepseek-ai"   # les 188 greffons
```

Puis lire la source du greffon candidat. **Un greffon présent n'est pas un greffon actif.**
Exemple mesuré : `dsh-tool-call-timeout-policy` est monté dans `web` ET `headless`, mais il
ne fait rien sur un outil qui ne déclare pas `timeoutMs` — et les outils de délégation n'en
déclarent aucun. Le greffon était là, la borne n'existait pas.

Vérifier aussi l'**amont**, qui est public :

```bash
gh api repos/deepseek-ai/deepseek-harness/git/trees/master?recursive=1 --jq '.tree[].path' | grep <sujet>
gh api repos/deepseek-ai/deepseek-harness/contents/<chemin> --jq '.content' | base64 -d
```

⚠️ Les **issues sont désactivées** sur ce dépôt (`has_issues=false`) : une recherche d'issues
rend toujours `total=0`, ce qui ne veut rien dire. Lire la source et les `README.md` des
paquets, qui sont détaillés.

---

## 1. Écrire le greffon

Un greffon cordis est un module ESM avec trois exports. **Zéro dépendance** : ne pas importer
`@deepseek-ai/*`, la résolution depuis un profil est un piège inutile.

```js
export const name = 'mon-greffon';            // nom cordis, visible dans les diagnostics
export const inject = ['tools', 'subagents']; // services requis ; le greffon attend qu'ils existent
export function apply(ctx, config) { /* ... */ }
```

Deux points d'accroche utiles :

| accroche | ce qu'elle voit | forme |
|---|---|---|
| `ctx.on('tools/execute', async (exec, next) => …)` | chaque appel d'outil, avant exécution | intercepteur : appeler `next()` ou rendre un résultat de substitution |
| `ctx.on('<domaine>/<evenement>', (payload) => …)` | le cycle de vie (`subagent/start`, `agent/created`, …) | écouteur simple |

La liste des événements se lit ainsi :

```bash
grep -rho '"[a-z-]*/[a-z/-]*"' node_modules/@deepseek-ai/dsh-scope/lib/invariant.js | sort -u
```

`package.json` minimal : `{"name": "...", "private": true, "type": "module", "main": "index.js"}`.

---

## 2. Le monter dans les profils

Les profils vivent dans `~/.dsh/profiles/<web|headless>/`. Deux gestes, tous deux faits par
`.\scripts\dsh.ps1 -InstallPlugins` :

1. **une jonction** `~/.dsh/profiles/<profil>/node_modules/<nom> → scripts/dsh-plugins/<nom>`
   (répertoire, donc pas besoin d'admin sous Windows) ;
2. **une rangée** dans `~/.dsh/profiles/<profil>/cordis.patch.yml`.

```yaml
- insert:
    - id: mon-greffon
      name: mon-greffon
      config:
        maCle: 123
```

Ajouter le greffon à `scripts/dsh-plugins/` suffit : l'installateur monte tout ce qu'il y
trouve. Écrire soi-même la rangée seulement si sa `config` diffère.

---

## 3. Prouver qu'il tourne — étape non contournable

**Faire annoncer le greffon sur `stderr` au démarrage**, dans `apply()` :

```js
console.error(`mon-greffon: arme a ${valeur}`);
```

Puis relancer et LIRE la sortie :

```powershell
.\scripts\dsh.ps1 -Stop
.\scripts\dsh.ps1 -NoOpen        # l'annonce sort sur stderr
```

> **Pas d'annonce = pas de garde.** Ne jamais déduire qu'un greffon tourne du fait que sa
> rangée est dans `cordis.patch.yml`, ni de l'absence d'erreur. `--dump-config` prouve que la
> rangée est *composée*, pas que `apply()` a été *appelé*.

Ne pas utiliser `ctx.logger` pour cette annonce : il est muet dans `headless`.

---

## 4. Les deux bras, sur une exécution réelle

`headless` exécute une tâche en ligne de commande : c'est le banc d'essai, pas besoin de
navigateur.

```bash
"$DSH" --profile headless "<tâche qui déclenche le comportement>"
```

- **known-GOOD** — configuration normale : le comportement d'origine est inchangé.
- **known-BAD** — une entrée dont on SAIT qu'elle doit déclencher le refus.

> Un bras known-BAD dont l'entrée n'est pas *vraiment* mauvaise ne mesure rien. Mesuré ici :
> une borne à 1500 ms n'a pas tiré parce que l'enfant finissait plus vite — j'ai lu « garde
> mort » alors que le garde allait bien. À 200 ms, il tire. Choisir une entrée qu'aucune
> exécution normale ne peut satisfaire.

---

## Table des pièges (chacun mesuré le 21/08/2026)

| piège | symptôme exact | règle |
|---|---|---|
| `- id:` nu dans un patch | `patch: entry "<id>" not found` | une entrée `- id:` **cible** une rangée existante ; pour en **ajouter** une, il faut `- insert:` |
| `ctx.logger` en headless | aucune trace, greffon pourtant chargé | annoncer sur `stderr`, jamais via le logger |
| clé de portée d'un événement | un argument attendu arrive `undefined` | le 2ᵉ argument d'un `emit` scopé est la **clé de portée**, pas un argument d'écouteur — reconstruire l'info depuis un registre (`ctx.agents.get(id)`) |
| known-BAD trop doux | le garde « ne tire pas » | vérifier que l'entrée est réellement hors bornes avant de conclure |
| `npx` fait flotter l'arbre | panne « ça marchait hier », trace sans rapport | l'app est épinglée, ses ~190 dépendances non : `.\scripts\dsh.ps1 -InstallRuntime` fige l'arbre, le préflight `dsh_tree_check.mjs` le vérifie |
| `pnpm install` dans un profil | le greffon disparaît | la jonction n'est pas une dépendance déclarée ; relancer `-InstallPlugins` après tout `pnpm install` |
| profils inégaux | un greffon marche dans `headless`, pas dans `web` | les presets d'agent ne sont montés QUE par `web` ; `--dump-config` par profil avant toute conclusion |

---

## Cas travaillé n°2 — faire regarder une IMAGE à un sous-agent

Chaîne complète : un serveur MCP émet l'image, le pont la relaie, le modèle la
regarde. Elle est câblée par
[`.\scripts\dsh.ps1 -InstallVision`](../scripts/dsh.ps1) et son serveur est
[`scripts/dsh-mcp/effitech-image/`](../scripts/dsh-mcp/effitech-image/server.mjs).

Les **quatre** conditions, toutes nécessaires, chacune avec un refus différent :

| condition | où | ce qu'on voit si elle manque |
|---|---|---|
| le serveur charge un `mmproj` | argv de llama-server | rien de visible : le serveur répond, **texte seulement** |
| la route déclare `input: [text, image]` | `~/.dsh/settings.yaml` | `model "X" does not declare image input` |
| la route a un `apiKeyEnv` **défini** | idem + environnement | `PI_AI_ERROR: No API key for provider: X` |
| un serveur MCP émet un bloc `image` | `cordis.patch.yml` | l'outil n'existe pas, sans erreur |

Le poids GGUF d'un modèle de vision **ne contient que le modèle de langue** :
llama.cpp garde la tour de vision dans un second fichier. Sans `--mmproj`, lire
une image n'est pas lent, c'est impossible — et rien ne le dit.

`llm-pi-ai` met par défaut `DEFAULT_INPUT = ["text"]` (`lib/index.js:862`) et
`dsh-mcp-client` refuse en conséquence (`lib/index.js:330`). Le README de
`llm-pi-ai` affirme que les modalités « have no harness consumer » : **c'était
vrai avant ce pont, ce ne l'est plus.** Lire le schéma zod, pas la prose.

Pour que l'ENFANT tourne sur un autre modèle que son parent, ne pas chercher un
preset : `agentOptions` d'une instance de `dsh-tool-subagent` porte `provider`,
`model`, `maxTokens` et surcharge l'héritage. Et déclarer la nouvelle instance
dans le `tools:` de la borne, sinon elle est la seule non bornée.

---

## Table des pièges n°2 (mesurés le 21/08/2026, en écrivant l'installateur)

| piège | symptôme exact | règle |
|---|---|---|
| backtick dans une chaîne PowerShell à guillemets **doubles** | `bad indentation of a mapping entry` au boot, du code PowerShell visible dans le YAML | le backtick EST l'échappement de PowerShell : chaîne à guillemets simples, ou pas de backtick |
| détecter « déjà fait » par sous-chaîne | l'installateur annonce « déjà présent » et n'écrit rien, sur un fichier où la config a disparu | ancrer le motif sur la **ligne YAML** ; le marqueur s'était trouvé dans son propre commentaire |
| écrire sans relire par le consommateur | le patch cassé ne se voit qu'au boot suivant, qui peut être dans trois semaines | après écriture : `dsh --profile <p> --dump-config`, exit ≠ 0 ⇒ **restaurer** |
| `-CheckOnly` / `--dump-config` comme preuve | la rangée est composée, `apply()` n'a jamais tourné | composer ≠ exécuter : exiger l'annonce sur stderr |
| budget de sortie trop court | la dernière ligne demandée (verdict, `TYPE:`) n'arrive jamais | une réponse tronquée à `max_tokens` n'est pas un mauvais verdict, c'est **pas de verdict** |

---

## Ce qui ne se règle PAS par un greffon

Certains comportements sont de la **configuration de preset**, pas du code. Les presets
d'agent livrés sont dans `<runtime>/node_modules/@deepseek-ai/dsh/config/agent-presets/`, et
la surcouche utilisateur dans `~/.dsh/.agent-presets/`.

⚠️ Une surcouche ne peut pas **masquer** un preset livré : à identifiant égal, le preset livré
gagne. Pour modifier `standard`, il faut créer un preset d'un AUTRE nom et le choisir.

Exemple : « le sous-agent ne rend pas de résultat » est le comportement documenté du mode
`backgroundMode: continuable` (« *this tool returns no result of its own* ») — l'appel rend
`started subagent <id>` et le résultat arrive plus tard comme notice de règlement. Le
corriger, c'est passer la rangée en `one-shot`, pas écrire un greffon.

---

## Arrêter un agent déjà parti

Les fournisseurs sont `spawn-in-process` / `fork-in-process` : les sous-agents vivent **dans
le processus node du serveur**. Il n'y a aucun processus à tuer, et `taskkill` sur un
sous-agent n'existe pas.

| besoin | geste |
|---|---|
| couper un enfant précis | dans la conversation : `list_agents` (ids durables) puis `interrupt_agent <id>` |
| couper tout | `.\scripts\dsh.ps1 -Stop` — emporte le serveur entier ; les sessions restent reprenables |

⚠️ `interrupt_agent` n'arrête que le **tour courant** de sa cible : les agents qu'elle a
elle-même lancés continuent. Sur un arbre, `list_agents scope=descendants` puis un
`interrupt_agent` par nœud. Et `list_agents` ne liste que les enfants **continuables** —
un enfant one-shot n'y apparaît pas, il meurt avec son appel d'outil.
