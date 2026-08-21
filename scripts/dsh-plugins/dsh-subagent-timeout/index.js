/**
 * dsh-subagent-timeout -- une borne de duree PAR DEFAUT sur les sous-agents.
 *
 * POURQUOI CE GREFFON EXISTE (mesure du 21/08 sur l'arbre 0.1.1-rc.2)
 *   dsh livre `@deepseek-ai/dsh-tool-call-timeout-policy`, et ce greffon est
 *   bien monte dans les profils `web` et `headless`. Mais il est COOPERATIF :
 *       const timeoutMs = ctx.tools.get(exec.name, exec.agent)?.timeoutMs;
 *       if (timeoutMs === void 0) return next();
 *   Il n'arme donc une echeance que sur les outils qui en DECLARENT une.
 *   Compte mesure : 19 paquets du scope declarent `timeoutMs` (tool-bash,
 *   tool-pwsh, tool-web, tool-fs-search, ...) et `dsh-tool-subagent` en
 *   declare ZERO. Les outils de delegation sont donc les seuls outils longs
 *   qui ne sont bornes par rien du tout, et un enfant qui ne finit pas ne
 *   finit jamais : il faut aller le tuer a la main.
 *   Ce n'est pas un retard d'installation : `packages/subagent/tool-subagent/
 *   src/index.ts` sur le `master` amont, pousse le 21/08 a la version exacte
 *   que nous faisons tourner (0.1.1-rc.2), contient ZERO `timeoutMs`.
 *
 * DEUX ARMES, PARCE QU'UN SEUL POINT NE COUVRE PAS LES DEUX ROUTES
 *   Le preset livre `standard` configure les deux lignes en
 *   `backgroundMode: continuable`, et dans ce mode
 *       runInBackground = request.run_in_background ?? continuable
 *   vaut TRUE par defaut : l'appel d'outil rend la main tout de suite avec un
 *   identifiant, et l'enfant continue tout seul. Une echeance posee sur
 *   l'appel d'outil ne verrait donc jamais rien.
 *
 *   ARME 1 -- l'APPEL D'OUTIL (`tools/execute`), pour les appels au premier
 *   plan : c'est le contrat de la politique livree, restreint aux outils qui
 *   ont oublie de declarer leur borne. A l'expiration on annule `exec.signal`,
 *   que `dsh-tool-subagent` honore (`settleStart` rend `status: "killed"`), et
 *   on rend au modele un resultat d'erreur explicite.
 *
 *   ARME 2 -- le RUN (`subagent/start` / `subagent/end`), pour les enfants
 *   continuables lances en arriere-plan : l'appel d'outil est deja rendu, donc
 *   la borne doit vivre sur le run. A l'expiration on appelle
 *   `ctx.subagents.interrupt(...)` -- le MEME appel que l'outil
 *   `interrupt_agent` que le modele peut declencher. L'autorite est
 *   reconstruite depuis le registre vivant, PAS lue sur l'evenement : voir
 *   `interruptChild`, ou la premiere version echouait faute de parent.
 *
 * CE QUE CE GREFFON NE FAIT PAS, ET IL FAUT LE SAVOIR
 *   `interrupt` n'arrete QUE le tour courant de la cible : les agents qu'elle
 *   a elle-meme lances continuent (c'est ecrit dans la description de
 *   `interrupt_agent`). Sur un arbre profond, la borne s'applique a chaque
 *   noeud separement, au fur et a mesure que chacun atteint la sienne.
 *
 * @module dsh-subagent-timeout
 */

/** Nom cordis, visible dans les diagnostics du chargeur. */
export const name = 'subagent-timeout';

/** Services requis : le registre d'outils (arme 1) et le service (arme 2). */
export const inject = ['tools', 'subagents', 'agents'];

/** Dix minutes : assez pour une vraie delegation, fini pour une qui part. */
const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;

/** Les deux outils livres par `dsh-tool-subagent` dans les presets standard. */
const DEFAULT_TOOL_NAMES = ['subagent', 'subagent_fork'];

/** Code porte par le resultat d'erreur, pour qu'un rejeu puisse router dessus. */
const SUBAGENT_TIMEOUT = 'SUBAGENT_TIMEOUT';

/**
 * Le resultat substitue quand notre echeance gagne. Le texte est model-facing :
 * il dit ce qui s'est passe ET quoi faire, sinon le modele relance a l'identique.
 * @param {number} timeoutMs - le budget ecoule, rendu dans le message.
 * @returns {object} le resultat d'outil en erreur.
 */
function timeoutResult(timeoutMs) {
  const message = `subagent call timed out after ${timeoutMs}ms and the child was cancelled`;
  return {
    content: [{
      type: 'text',
      text: `Error: ${message}. Do not retry the same delegation unchanged: either narrow the task, `
        + 'or raise this instance\'s timeoutMs in the profile patch layer.'
    }],
    isError: true,
    error: {
      message,
      info: { name: 'SubagentTimeoutError', code: SUBAGENT_TIMEOUT }
    }
  };
}

/**
 * @param {object} ctx - le contexte cordis (tools, subagents).
 * @param {object} [config] - `timeoutMs` (defaut 600000) et `tools` (defaut
 *   `subagent`, `subagent_fork`).
 */
export function apply(ctx, config) {
  const options = config ?? {};
  const timeoutMs = options.timeoutMs === undefined ? DEFAULT_TIMEOUT_MS : Number(options.timeoutMs);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error(`subagent-timeout: timeoutMs doit etre un nombre fini positif, recu ${JSON.stringify(options.timeoutMs)}`);
  }
  const toolNames = new Set(options.tools ?? DEFAULT_TOOL_NAMES);

  // Un garde qui ne s'annonce pas est indiscernable d'un garde qui n'a pas
  // charge : le premier bras known-BAD a echoue PERMISSIF, sans un mot.
  const announce = `subagent-timeout: arme a ${timeoutMs} ms sur ${[...toolNames].join(', ')}`;
  console.error(announce);

  // --- ARME 1 : l'appel d'outil au premier plan ------------------------------
  ctx.on('tools/execute', async (exec, next) => {
    if (!toolNames.has(exec.name)) return next();
    // Si l'outil declare DEJA sa borne, elle lui appartient : la politique
    // livree l'arme, et deux echeances concurrentes rendraient le diagnostic
    // illisible.
    if (ctx.tools.get(exec.name, exec.agent)?.timeoutMs !== undefined) return next();

    const upstream = exec.signal;
    const controller = new AbortController();
    let expired = false;
    const relay = () => controller.abort(upstream.reason);
    const timer = setTimeout(() => {
      expired = true;
      controller.abort(new Error(SUBAGENT_TIMEOUT));
    }, timeoutMs);

    if (upstream !== undefined) {
      if (upstream.aborted) controller.abort(upstream.reason);
      else upstream.addEventListener('abort', relay, { once: true });
    }
    exec.signal = controller.signal;
    try {
      const result = await next();
      // On ne substitue QUE si c'est notre minuterie qui a gagne : une
      // annulation venue d'en haut reste une annulation ordinaire.
      return expired ? timeoutResult(timeoutMs) : result;
    } finally {
      clearTimeout(timer);
      if (upstream !== undefined) upstream.removeEventListener('abort', relay);
      exec.signal = upstream;
    }
  });

  // --- ARME 2 : le run continuable lance en arriere-plan ----------------------
  const running = new Map();

  const clear = (runId) => {
    const timer = running.get(runId);
    if (timer === undefined) return;
    clearTimeout(timer);
    running.delete(runId);
  };

  /**
   * Couper un enfant continuable a l'expiration de sa borne.
   *
   * L'evenement `subagent/start` ne livre PAS le parent a ses ecouteurs : le
   * 2e argument de `emit("subagent/start", identity, parent)` est la cle de
   * PORTEE du dispatch, pas un argument d'ecouteur (mesure du 21/08 : la
   * sonde a rendu `parent=ABSENT`). On reconstruit donc l'autorite depuis le
   * registre vivant -- l'en-tete de session de l'enfant nomme son parent
   * durable, et c'est exactement ce que la forme `kind: "user"` de
   * `interrupt` verifie.
   * @param {string} childId - l'identifiant de session de l'enfant.
   */
  const interruptChild = (childId) => {
    try {
      const child = ctx.agents?.get?.(childId);
      const parentSessionId = child?.session?.header?.parentSession;
      // Un run one-shot n'a pas d'activation : rien a interrompre ici, c'est
      // l'ARME 1 qui borne ce cas-la.
      if (parentSessionId === undefined) return;
      ctx.subagents.interrupt(childId, { kind: 'user', parentSessionId });
    } catch (error) {
      console.error(`subagent-timeout: interruption de ${childId} refusee : ${String(error)}`);
    }
  };

  ctx.on('subagent/start', (identity) => {
    const timer = setTimeout(() => {
      running.delete(identity.runId);
      interruptChild(identity.id);
    }, timeoutMs);
    timer.unref?.();
    running.set(identity.runId, timer);
  });

  ctx.on('subagent/end', (identity) => { clear(identity.runId); });

  ctx.on('dispose', () => {
    for (const timer of running.values()) clearTimeout(timer);
    running.clear();
  });
}
