/**
 * dsh-test-wall -- Phase 2 of the README (`coder`), 2026-08-23.
 *
 * README, Phase 2 red-team angle: "can the coder obtain a green diff by
 * deleting or weakening tests?" The structural answer: the coder cannot touch
 * tests at all, and cannot run them outside the gate. On `tools/pre-execute`:
 *   - file tools (edit, write, str_replace_editor, and any tool whose arguments
 *     name a path): REFUSED when a path resolves under a protected test root;
 *     read-only tools (read, glob, grep, read_image) and julia_gate itself PASS
 *     (default `<cwd>/test`, plus DSH_TEST_WALL roots, `;`-separated);
 *   - shell tools (pwsh, bash): REFUSED when the command names a test root
 *     (absolute, or the relative segment `test/` / `test\`), runs Julia or a
 *     test runner (`julia`, `Pkg.test`, `runtests`), or rewrites the tree by
 *     git (`checkout`, `restore`, `reset`, `stash`, `clean`, `rm`, `mv`).
 * Adding a NEW test file is refused too: tests are the planner's / human's
 * contract with the coder, not the coder's. A test the coder needs is a
 * structured failure to report, not a file to write. Measured by
 * `node harness/test_wall_unit.mjs` (free) and on the wire by fumee_route.py
 * (stderr "test-wall: REFUS n -- ...").
 *
 * `verifier(name, args, opts)` is exported pure for the unit control.
 */
import { realpathSync } from 'node:fs';
import { resolve, isAbsolute } from 'node:path';

export const name = 'test-wall';
export const inject = ['tools'];

const SHELL = new Set(['pwsh', 'bash', 'powershell', 'sh', 'cmd']);
const FILE_TOOLS = new Set(['edit', 'write', 'str_replace_editor', 'read']);
// Lecture seule, ou la porte elle-meme : un test se lit, se cherche et se rejoue ; il ne se modifie pas.
// (sur-refus constate sur le fil le 23/08 : grep test/ et julia_gate(test/...) refuses a tort)
const LECTURE = new Set(['read', 'glob', 'grep', 'read_image', 'julia_gate']);
const GIT_TREE = /\bgit\b[^|;&\n]*\b(checkout|restore|reset|stash|clean|rm|mv)\b/i;
const JULIA = /(^|[\s;&|(])(julia(\.exe)?|Pkg\.test|runtests)\b/i;
const REL_TEST = /(^|[\s"'`=(])(\.[\\/])?test[\\/]/i;

// Les prefixes de peripherique DOS (\\?\, \\.\, \\?\UNC\) designent le meme fichier que le chemin
// nu : on les retire avant de comparer aux racines (trouvaille red team 2-done du 23/08, LOW).
function canon(p) {
  return String(p).replace(/\\/g, '/').replace(/^\/\/[?.]\/(unc\/)?/i, (m, unc) => (unc ? '//' : '')).replace(/\/+$/, '').toLowerCase();
}
function reel(p) { try { return realpathSync.native(p); } catch { return p; } }

function sousRacine(chemin, roots) {
  const c = canon(chemin);
  const r = canon(reel(chemin));
  return roots.find((root) => c === root || c.startsWith(root + '/') || r === root || r.startsWith(root + '/')) || null;
}

function chemins(v, out = []) {
  if (typeof v === 'string') { out.push(v); return out; }
  if (Array.isArray(v)) { for (const x of v) chemins(x, out); return out; }
  if (v && typeof v === 'object') { for (const x of Object.values(v)) chemins(x, out); }
  return out;
}

/**
 * @returns {null | {motif: string, extrait: string}} null = passes
 */
export function verifier(toolName, args, opts) {
  const roots = opts.roots || [];
  const cwd = opts.cwd || process.cwd();
  if (SHELL.has(toolName)) {
    const cmd = chemins(args).join('\n');
    for (const root of roots) if (canon(cmd).includes(root)) return { motif: 'le shell nomme une racine de tests', extrait: cmd.slice(0, 80) };
    const m1 = REL_TEST.exec(cmd);
    if (m1) return { motif: 'le shell nomme test/', extrait: cmd.slice(Math.max(0, m1.index - 20), m1.index + 60) };
    const m2 = JULIA.exec(cmd);
    if (m2) return { motif: 'lancement de Julia / tests hors de la porte', extrait: cmd.slice(Math.max(0, m2.index - 10), m2.index + 60) };
    const m3 = GIT_TREE.exec(cmd);
    if (m3) return { motif: `git ${m3[1]} reecrit l'arbre`, extrait: m3[0].slice(0, 80) };
    return null;
  }
  if (LECTURE.has(toolName)) return null;  // lire / chercher / rejouer un test est permis (comprendre le contrat)
  for (const p of chemins(args)) {
    if (!/[\\/]/.test(p) && !FILE_TOOLS.has(toolName)) continue;  // un argument sans separateur n'est un chemin que pour un outil fichier
    const abs = isAbsolute(p) ? p : resolve(cwd, p);
    const root = sousRacine(abs, roots);
    if (root) return { motif: `${toolName} vise un fichier de tests`, extrait: p.slice(0, 80) };
  }
  return null;
}

export function apply(ctx, config = {}) {
  const cwd = process.cwd();
  const bruts = [join2(cwd, 'test')]
    .concat((process.env.DSH_TEST_WALL || '').split(';').map((x) => x.trim()).filter(Boolean))
    .concat(config.roots || []);
  const roots = [...new Set(bruts.flatMap((r) => [canon(r), canon(reel(r))]))];
  const opts = { roots, cwd };
  let refus = 0;
  ctx.on('tools/pre-execute', async (exec, next) => {
    const k = verifier(exec.name, exec.arguments || {}, opts);
    if (!k) return next();
    refus++;
    console.error(`test-wall: REFUS ${refus} -- ${exec.name} : ${k.motif} ("${k.extrait.replace(/\s+/g, ' ')}")`);
    return {
      kind: 'deny',
      reason: `test wall: ${k.motif}. The coder may not create, edit or delete tests, run Julia or tests outside the julia_gate tool, or rewrite the tree with git. `
        + 'If a test is wrong or missing, stop and report it as a structured failure (file, line, what you expected) -- do not work around it.',
    };
  });
  console.error(`test-wall: arme -- ${roots.length} racine(s) de tests (${bruts.map((b) => b.replace(/\\/g, '/')).join(', ')}), cwd ${cwd.replace(/\\/g, '/')}`);
}

function join2(a, b) { return a.replace(/[\\/]+$/, '') + '/' + b; }
