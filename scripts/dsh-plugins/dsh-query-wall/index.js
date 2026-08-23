/**
 * dsh-query-wall -- Phase 2 of the README (`searcher`), 2026-08-23.
 *
 * The orchestrator runs on a PRIVATE route and reads the framework; the
 * `searcher` child runs on an OPEN chain (free / stealth models that may train
 * on inputs). The ONLY channel from the parent to the child is the `prompt`
 * argument of the delegation tool. README, Agents: "Queries carry library
 * names and generic questions only -- no framework code."
 *
 * This plugin sits on `tools/pre-execute` and, for the configured tool names
 * (the delegation tool AND the Context7 MCP tools, which are global and thus
 * visible to the orchestrator), REFUSES a call whose string arguments carry:
 *   - a code fence or lines that read as code (Julia/Python/JS signatures,
 *     assignments with calls, `using`/`import` lines, lone `end`) -- 2 such
 *     lines are enough, 1 `using`/`import` of a non-library name is enough;
 *   - a filesystem path (drive, UNC, `~/`, `./`, `../`, `src/...`);
 *   - a marking segment of the walled roots (`DSH_READ_WALL`, same source as
 *     dsh-read-wall) or the framework's module name (config `identifiers`);
 *   - a secret-looking token (sk-..., AIza..., ghp_..., hf_..., AKIA...);
 *   - more than `maxChars` characters (default 1200): a library question fits,
 *     a pasted function does not.
 * Everything else passes. The wall is a policy fence inside one process, like
 * dsh-read-wall: it is measured by `node harness/query_unit.mjs` (free) and on
 * the wire by `fumee_route.py` (stderr "query-wall: REFUS n -- ...").
 *
 * `verifier(prompt, opts)` is exported pure so the unit control and the plugin
 * share one implementation.
 */

export const name = 'query-wall';
export const inject = ['tools'];

const SECRETS = /\b(sk-or-v1-[a-z0-9]{8,}|sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|ghp_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}|xox[abp]-[A-Za-z0-9-]{10,})\b/;
const PATHS = /(^|[\s"'`(])(?:[a-zA-Z]:[\\/]|\\\\[^\s]+\\|~[\\/]|\.{1,2}[\\/]|(?:src|test|scripts|harness|lib|docs)[\\/][\w.-]+)/;
const FENCE = /```|~~~/;
// One line that reads as code. Kept deliberately narrow: a prose sentence with
// parentheses must pass, a Julia/Python signature must not.
const CODE_LINES = [
  /^\s*(?:function|macro|struct|mutable struct|abstract type|primitive type|module|baremodule)\s+[\w!.]+/,  // Julia
  /^\s*(?:def|class|async def)\s+\w+\s*\(/,                                                              // Python
  /^\s*(?:export\s+)?(?:async\s+)?function\s*\w*\s*\(|^\s*(?:const|let|var)\s+\w+\s*=/,                 // JS
  /^\s*end\s*$/,                                                                                         // Julia/Ruby block end
  /^\s*@\w+\s+\w+/,                                                                                      // Julia macro call at line start
  /^\s*[\w!.\[\]]+\s*(?:[-+*/]|\.)?=\s*[\w"'(\[].*[(\[]/,                                              // assignment with a call/index
  /^\s*(?:if|elseif|while|for)\s+.+\s*$/,                                                                // control flow (Julia has no parens)
  /^\s*return\s+\S/,
  /^\s*#\s*[\w!]+\(.*\)/,                                                                                // commented-out call
  /[;{}]\s*$/,                                                                                           // statement terminators
];
const USING = /^\s*(?:using|import)\b\s+["\w.]|^\s*include\s*\(/;

function segmentsDe(roots) {
  const out = new Set();
  for (const r of roots) {
    for (const seg of String(r).replace(/\\/g, '/').toLowerCase().split('/')) {
      if (seg.length >= 8 && !/^[a-z]:$/.test(seg) && seg !== 'users' && seg !== 'documents') out.add(seg);
    }
  }
  return [...out];
}

/**
 * @param {string} prompt
 * @param {{maxChars?: number, segments?: string[], identifiers?: string[]}} opts
 * @returns {null | {motif: string, extrait: string}}  null = passes
 */
export function verifier(prompt, opts = {}) {
  const s = String(prompt ?? '');
  const maxChars = opts.maxChars ?? 1200;
  if (s.length > maxChars) return { motif: `longueur ${s.length} > ${maxChars}`, extrait: s.slice(0, 80) };
  const m0 = SECRETS.exec(s);
  if (m0) return { motif: 'secret', extrait: m0[1].slice(0, 12) + '...' };
  if (FENCE.test(s)) return { motif: 'bloc de code (```)', extrait: s.slice(s.search(FENCE), s.search(FENCE) + 60) };
  const m1 = PATHS.exec(s);
  if (m1) return { motif: 'chemin de fichier', extrait: m1[0].trim().slice(0, 60) };
  const low = s.toLowerCase();
  for (const id of opts.identifiers || []) {
    const i = low.indexOf(String(id).toLowerCase());
    if (i >= 0) return { motif: `identifiant du framework "${id}"`, extrait: s.slice(Math.max(0, i - 20), i + 40) };
  }
  for (const seg of opts.segments || []) {
    const i = low.indexOf(seg);
    if (i >= 0) return { motif: `segment de racine murée "${seg}"`, extrait: s.slice(Math.max(0, i - 20), i + 40) };
  }
  let code = 0, premier = null;
  for (const line of s.split(/\r?\n/)) {
    if (!line.trim()) continue;
    if (USING.test(line)) return { motif: 'ligne using/import/include', extrait: line.trim().slice(0, 60) };
    if (CODE_LINES.some((re) => re.test(line))) { code++; premier ??= line.trim().slice(0, 60); if (code >= 2) return { motif: `${code} lignes de code`, extrait: premier }; }
  }
  return null;
}

export function apply(ctx, config = {}) {
  const TOOLS = new Set(config.tools || ['searcher']);
  const roots = (process.env.DSH_READ_WALL || '').split(';').map((x) => x.trim()).filter(Boolean).concat(config.roots || []);
  const opts = {
    maxChars: config.maxChars ?? 1200,
    segments: segmentsDe(roots),
    identifiers: config.identifiers || [],
  };
  let refus = 0;
  ctx.on('tools/pre-execute', async (exec, next) => {
    if (!TOOLS.has(exec.name)) return next();
    const a = exec.arguments || {};
    // every string argument, joined: prompt/description (searcher), query/libraryName/libraryId (Context7)
    const texte = Object.values(a).filter((v) => typeof v === 'string').join('\n');
    const k = verifier(texte, opts);
    if (!k) return next();
    refus++;
    console.error(`query-wall: REFUS ${refus} -- ${exec.name} : ${k.motif} ("${k.extrait.replace(/\s+/g, ' ')}")`);
    return {
      kind: 'deny',
      reason: `query wall: the ${exec.name} delegate runs on an OPEN model; its prompt may carry library names and generic questions only. Refused: ${k.motif}. `
        + 'Rephrase as a question about the library or API (name, version, function, keyword), without code, paths, framework names or secrets.',
    };
  });
  console.error(`query-wall: arme -- outil(s) ${[...TOOLS].join(',')}, ${opts.segments.length} segment(s) de racine, ${opts.identifiers.length} identifiant(s), max ${opts.maxChars} car.`);
}
