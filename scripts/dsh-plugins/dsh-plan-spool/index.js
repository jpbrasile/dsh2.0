/**
 * dsh-plan-spool -- rodage phase 4, defaut D3 (2026-08-24).
 *
 * Constat (jour 1, essai 1, session-9e7bf9ad) : le brief demande au parent de
 * recopier VERBATIM le plan du planner (~5-6 k tokens) dans les arguments de
 * l'appel `coder`. Cette emission geante a echoue 3 fois de suite ("Upstream
 * idle timeout exceeded", llm/retry 1..3, 134+121+140 s, out 36-135 tokens),
 * reussie a la 4e (127 s) : 522 s et ~60 k tokens d'entree re-factures sur une
 * seule etape. Le plan doit passer PAR REFERENCE, jamais par recopie.
 *
 * Sur `tools/post-execute` (la cascade qui peut REMPLACER la valeur canonique,
 * comme dsh-secret-redactor) : quand un outil vise (defaut : `planner`) rend un
 * texte plus long que le seuil (defaut : 2000 car.), le greffon ecrit ce texte
 * dans PLAN.md (puis PLAN_2.md, ...) sous le cwd, et rend au parent un ACCUSE
 * court : taille, chemin, consigne de faire LIRE le fichier au coder, et les
 * premiers 400 caracteres pour le contexte. Le parent n'a plus jamais a
 * re-emettre le plan. Config : env DSH_PLAN_SPOOL_TOOLS (`;` ou `,`),
 * DSH_PLAN_SPOOL_SEUIL, DSH_PLAN_SPOOL_FICHIER, ou config {tools, seuil,
 * fichier}. Nota : le fichier est ecrit dans l'espace de travail (gitignore
 * en rodage) ; selon l'ordre de la cascade il peut precer la redaction des
 * secrets -- un plan est une sortie de lecture du depot, qui n'en contient pas.
 *
 * `spooler(texte, opts)` est exporte pur pour le controle
 * `node harness/plan_spool_unit.mjs` (gratuit).
 */
import { writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

export const name = 'plan-spool';
export const inject = ['tools'];

const APERCU = 400;

/**
 * @param {string} texte  le texte rendu par l'outil vise
 * @param {{seuil: number, fichier: string}} opts  fichier = chemin d'ecriture annonce
 * @returns {null | {accuse: string}} null = trop court, ne pas toucher
 */
export function spooler(texte, opts) {
  if (typeof texte !== 'string' || texte.length <= opts.seuil) return null;
  const nom = opts.fichier.replace(/\\/g, '/').split('/').pop();
  const accuse = `plan-spool: the full plan (${texte.length} chars) has been written to ${nom} `
    + `in the workspace. Do NOT copy the plan into your next tool call or message: `
    + `it would be slow and error-prone. Tell the coder to READ ${nom} and implement it exactly `
    + `(the file is the contract). Plan opening (first ${APERCU} chars):\n\n`
    + texte.slice(0, APERCU);
  return { accuse };
}

function texteDe(v) {
  if (typeof v === 'string') return v;
  if (Array.isArray(v)) return v.map(texteDe).filter(Boolean).join('\n');
  if (v && typeof v === 'object') {
    if (typeof v.text === 'string') return v.text;
    if (Object.hasOwn(v, 'value')) return texteDe(v.value);
    if (Object.hasOwn(v, 'content')) return texteDe(v.content);
  }
  return '';
}

export function apply(ctx, config = {}) {
  const cwd = process.cwd();
  const TOOLS = new Set(
    (process.env.DSH_PLAN_SPOOL_TOOLS || '').split(/[;,]/).map((x) => x.trim()).filter(Boolean)
      .concat(config.tools || []),
  );
  if (!TOOLS.size) TOOLS.add('planner');
  const seuil = Number(process.env.DSH_PLAN_SPOOL_SEUIL || config.seuil || 2000);
  const base = process.env.DSH_PLAN_SPOOL_FICHIER || config.fichier || 'PLAN.md';
  let n = 0;

  function prochain() {
    for (let i = n; ; i++) {
      const nom = i === 0 ? base : base.replace(/(\.[^.]*)?$/, (ext) => `_${i + 1}${ext || ''}`);
      const chemin = resolve(cwd, nom);
      if (!existsSync(chemin)) return chemin;
    }
  }

  ctx.on('tools/post-execute', async (exec, result, next) => {
    const decision = await next();
    if (!decision || decision.kind !== 'accept') return decision;
    if (!TOOLS.has(exec.name) || (result && result.isError)) return decision;
    const surContent = Object.hasOwn(decision, 'content')
      || (!Object.hasOwn(decision, 'value') && result && result.content !== undefined);
    const src = Object.hasOwn(decision, 'content') ? decision.content
      : Object.hasOwn(decision, 'value') ? decision.value
        : result ? (result.content !== undefined ? result.content : result.value) : undefined;
    const texte = texteDe(src);
    const chemin = prochain();
    const s = spooler(texte, { seuil, fichier: chemin });
    if (!s) return decision;
    writeFileSync(chemin, texte);
    n++;
    console.error(`plan-spool: ${exec.name} -> ${chemin.replace(/\\/g, '/')} (${texte.length} car.), accuse court rendu au parent`);
    return surContent
      ? { ...decision, content: [{ type: 'text', text: s.accuse }] }
      : { ...decision, value: s.accuse };
  });

  console.error(`plan-spool: arme -- outil(s) ${[...TOOLS].join(',')}, seuil ${seuil} car., fichier ${base}, cwd ${cwd.replace(/\\/g, '/')}`);
}
