/**
 * dsh-julia-gate -- Phase 2 of the README (`coder` wired to the Phase 0.5 gate), 2026-08-23.
 *
 * Registers ONE model-facing tool, `julia_gate(files)`, that runs the fast Julia
 * test gate `scripts/julia_gate/porte.py` on the named source/test files and
 * returns its verdict as structured output:
 *   VERT   every selected test replayed and green, nothing uncovered
 *   ORANGE nothing red, but uncovered file / tests not replayed (budget) -- NOT green:
 *          "heavy suites pending" (README, Phase 0.5 consequence for the coder)
 *   ROUGE  at least one failing or erroring test, with the error blocks
 *   PANNE  the gate server could not be reached or started
 * The tool is the coder's ONLY way to run tests: dsh-test-wall refuses test
 * edits and shell test runs, so a green diff can only come from the gate.
 *
 * Config (all optional):
 *   porte   absolute path of porte.py     (default: env DSH_JULIA_GATE)
 *   repo    absolute path of the project  (default: env DSH_GATE_REPO, else process.cwd())
 *   budget  seconds for the gate           (default 30)
 *   python  interpreter                    (default "python")
 * No import from the dsh runtime: a local plugin copied into an isolated home
 * resolves nothing but node builtins. The definition is raw JSON Schema, the
 * shape `ctx.tools.register()` expects after defineTool().
 */
import { execFile } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { join, dirname, isAbsolute, resolve } from 'node:path';

export const name = 'julia-gate';
export const inject = ['tools'];

function lancer(python, args, cwd, timeoutMs) {
  return new Promise((res) => {
    execFile(python, args, { cwd, timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024, windowsHide: true, encoding: 'utf8' },
      (err, stdout, stderr) => {
        const code = err && typeof err.code === 'number' ? err.code : err ? -1 : 0;
        res({ code, stdout: stdout || '', stderr: stderr || '', tue: !!(err && err.killed) });
      });
  });
}

export function apply(ctx, config = {}) {
  const porte = config.porte || process.env.DSH_JULIA_GATE || '';
  const repo0 = config.repo || process.env.DSH_GATE_REPO || process.cwd();
  const budget = Number(config.budget) > 0 ? Number(config.budget) : 30;
  const python = config.python || 'python';
  if (!porte || !existsSync(porte)) {
    console.error(`julia-gate: NON CONFIGURE -- porte.py introuvable (${porte || 'DSH_JULIA_GATE vide'}) : outil julia_gate non enregistre`);
    return;
  }
  let appels = 0;
  ctx.tools.register({
    name: 'julia_gate',
    description:
      `Run the fast Julia test gate on the files you changed (paths relative to the project root ${repo0.replace(/\\/g, '/')} or absolute). `
      + 'It replays the tests that exercise those files in a persistent Julia session under a hard time budget and returns a verdict: '
      + 'VERT = every selected test replayed and green; ORANGE = nothing failed but some file is uncovered or tests were not replayed within the budget -- this is NOT green, heavier suites are still pending; '
      + 'ROUGE = a test failed or errored (the error blocks are included); PANNE = the gate could not run. '
      + 'This is the only way to run tests. Pass every .jl file you edited.',
    parameters: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' }, description: 'The .jl files you changed (src/ or test/ of the project). Required, at least one.' },
      },
      required: ['files'],
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          verdict: { type: 'string' },
          code: { type: 'integer' },
          tests_rejoues: { type: 'integer' },
          non_rejoues: { type: 'integer' },
          non_couverts: { type: 'array', items: { type: 'string' } },
          wall_s: { type: 'number' },
          sortie: { type: 'string' },
        },
        required: ['verdict', 'code', 'sortie'],
      },
      render: (_args, v) => [{ type: 'text', text: `VERDICT ${v.verdict} (code ${v.code}, ${v.tests_rejoues ?? 0} tests replayed in ${v.wall_s ?? 0}s, ${v.non_rejoues ?? 0} not replayed, ${(v.non_couverts || []).length} uncovered)\n${v.sortie}` }],
    },
    async execute(args) {
      appels++;
      const files = (args.files || []).map((f) => (isAbsolute(f) ? f : resolve(repo0, f)));
      if (!files.length) return { verdict: 'ORANGE', code: 2, sortie: 'no file given: nothing replayed (ORANGE, not green)', tests_rejoues: 0, non_rejoues: 0, non_couverts: [], wall_s: 0 };
      const t0 = Date.now();
      const r = await lancer(python, [porte, '--repo', repo0, '--budget', String(budget), ...files], repo0, (budget + 150) * 1000);
      // un crash Python de la porte (Traceback) n'est pas un test rouge : PANNE, quel que soit le code
      const plante = /Traceback \(most recent call last\)/.test(r.stderr || '');
      const verdict = r.tue || plante ? 'PANNE' : ({ 0: 'VERT', 1: 'ROUGE', 2: 'ORANGE', 3: 'PANNE' })[r.code] || 'PANNE';
      let d = {};
      try { d = JSON.parse(readFileSync(join(dirname(porte), '_gate', 'dernier.json'), 'utf8')); } catch { /* pas de dernier.json : verdict du code de retour seul */ }
      const lignes = (r.stdout + (r.stderr ? '\n[stderr] ' + r.stderr : '')).split(/\r?\n/).filter(Boolean);
      const sortie = lignes.slice(-60).join('\n');
      console.error(`julia-gate: appel ${appels} -> ${verdict} en ${((Date.now() - t0) / 1000).toFixed(1)}s (${files.length} fichier(s))`);
      return {
        verdict, code: plante ? 3 : r.code,
        tests_rejoues: Array.isArray(d.resultats) ? d.resultats.length : 0,
        non_rejoues: Array.isArray(d.non_rejoues) ? d.non_rejoues.length : 0,
        non_couverts: Array.isArray(d.non_couverts) ? d.non_couverts.map(String) : [],
        wall_s: typeof d.wall_s === 'number' ? d.wall_s : 0,
        sortie,
      };
    },
  });
  console.error(`julia-gate: arme -- porte ${porte.replace(/\\/g, '/')}, projet ${repo0.replace(/\\/g, '/')}, budget ${budget}s`);
}
