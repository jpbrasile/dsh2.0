// Controle gratuit du mur de requete (scripts/dsh-plugins/dsh-query-wall) -- Phase 2, `searcher`.
//
//     node harness/query_unit.mjs
//
// Rejoue l'angle red team du README ("try to make a query carry framework code") sur la
// fonction pure `verifier()` : chaque cas dit ce qui doit PASSER (une question de bibliotheque)
// et ce qui doit etre REFUSE (code, chemin, nom du framework, secret, trop long). Le verdict se
// lit dans le motif rendu, jamais dans un message. Puis le plugin est monte sur un faux `ctx`
// pour prouver que seul l'outil configure est filtre et que le refus est un `deny`.
import { verifier, apply } from '../scripts/dsh-plugins/dsh-query-wall/index.js';

let total = 0, faux = 0;
function cas(nom, ok, detail) {
  total++;
  if (!ok) faux++;
  console.log(`  ${ok ? 'OK  ' : 'KO  '} ${nom}${detail !== undefined ? '  -- ' + JSON.stringify(detail) : ''}`);
}

const OPTS = { maxChars: 1200, segments: ['agentic-flow-fresh', 'plasma-digital-twin'], identifiers: ['PlasmaDigitalTwin'] };
const ALPHA = 'abcdefghijklmnopqrstuvwxyz';

console.log('== doit PASSER (questions de bibliotheque, generiques)');
for (const [nom, q] of [
  ['question simple', 'What are the keyword arguments of solve for an ODEProblem with Tsit5 in DifferentialEquations.jl (saveat, abstol, reltol)?'],
  ['nom + version', 'CUDA.jl 5.x: how do I allocate a CuArray of Float32 and launch a kernel with @cuda? Generic usage only.'],
  ['parentheses en prose', 'In DataFrames.jl (version 1.6), how does groupby(df, :col) combine with combine(...)? Give the documented signature.'],
  ['plusieurs lignes de prose', 'Two questions about HDF5.jl:\n1. how to open a file read-only\n2. how to read a dataset slice into an existing array'],
  ['mention d un identifiant courant', 'What does Interpolations.jl recommend for a cubic spline on a regular grid? Is extrapolation bounded by default?'],
  ['mot "end" dans une phrase', 'In the end, does Optim.jl BFGS accept a gradient function, and what is the option name for the tolerance?'],
  ['1 200 caracteres pile', 'A'.repeat(1200)],
]) cas(nom, verifier(q, OPTS) === null, verifier(q, OPTS));

console.log('== doit etre REFUSE (code, chemin, framework, secret, longueur)');
for (const [nom, q, motif] of [
  ['bloc de code', 'Explain this:\n```julia\nf(x) = x^2\n```', /bloc de code/],
  ['fonction Julia + end', 'What does this do?\nfunction ionize!(s::State, dt)\n    s.n .+= dt\nend', /lignes de code|using/],
  ['signature Python', 'def compute(a, b):\n    return a + b\nWhat is the complexity?', /lignes de code/],
  ['using PlasmaDigitalTwin', 'using PlasmaDigitalTwin.Physics\nwhich solver is used?', /using|identifiant/],
  ['identifiant du framework en prose', 'In PlasmaDigitalTwin, the collision module calls a rate table; what is the SciML way to do that?', /identifiant/],
  ['segment de racine muree', 'Look at plasma-digital-twin/src/Physics.jl and tell me what solve options fit.', /segment|chemin/],
  ['chemin Windows', 'The file is at C:\\Users\\test\\Documents\\x\\src\\a.jl -- which package documents it?', /chemin/],
  ['chemin relatif src/', 'See src/Physics.jl: what does the solve call there need?', /chemin/],
  ['chemin ~/', 'Open ~/work/notes.md and summarise it', /chemin/],
  ['secret OpenRouter', 'use key sk-or-v1-' + ALPHA + '0123456789 to call the API', /secret/],
  ['secret Google', 'token AIza' + ALPHA.slice(0, 20) + 'ABCDE for maps', /secret/],
  ['trop long', 'Q '.repeat(700), /longueur/],
  ['assignation avec appel + return', 'x = solve(prob, Tsit5())\nreturn x.u', /lignes de code/],
  ['2 lignes JS', 'const a = 1;\nlet b = f(a);', /lignes de code/],
  ['include', 'include("physics.jl")\nwhat does it export?', /using|include/],
]) { const r = verifier(q, OPTS); cas(nom, r !== null && motif.test(r.motif), r && r.motif); }

console.log('== plugin monte sur un faux ctx : seul l outil configure est filtre, refus = deny');
const hooks = {};
const ctx = { on(ev, fn) { hooks[ev] = fn; } };
process.env.DSH_READ_WALL = 'C:\\Users\\x\\Documents\\agentic-flow-fresh;C:\\Users\\x\\Documents\\agentic-flow-fresh\\plasma-digital-twin';
apply(ctx, { tools: ['searcher'], identifiers: ['PlasmaDigitalTwin'] });
cas('hook tools/pre-execute pose', typeof hooks['tools/pre-execute'] === 'function');
const suite = async (name, args) => hooks['tools/pre-execute']({ name, arguments: args }, async () => ({ kind: 'next' }));
cas('searcher + question legitime -> next', (await suite('searcher', { description: 'solve kwargs', prompt: 'kwargs of solve in DifferentialEquations.jl?' })).kind === 'next');
const d1 = await suite('searcher', { description: 'explain', prompt: 'function f(x)\n  x\nend' });
cas('searcher + code -> deny avec motif', d1.kind === 'deny' && /Refused: .*lignes de code/.test(d1.reason), d1.reason && d1.reason.slice(0, 100));
const d2 = await suite('searcher', { description: 'look in plasma-digital-twin', prompt: 'which solver?' });
cas('segment de DSH_READ_WALL dans la description -> deny', d2.kind === 'deny' && /segment/.test(d2.reason));
const d3 = await suite('searcher', { description: 'q', prompt: 'PlasmaDigitalTwin uses which ODE solver?' });
cas('identifiant configure -> deny', d3.kind === 'deny' && /identifiant/.test(d3.reason));
cas('autre outil (read) avec du code -> next (pas filtre)', (await suite('read', { path: 'function f() end' })).kind === 'next');
const hooks2 = {};
apply({ on(ev, fn) { hooks2[ev] = fn; } }, { tools: ['searcher', 'mcp__context7__query-docs'], identifiers: ['PlasmaDigitalTwin'] });
const suite2 = async (name, args) => hooks2['tools/pre-execute']({ name, arguments: args }, async () => ({ kind: 'next' }));
cas('Context7 query-docs + question legitime -> next', (await suite2('mcp__context7__query-docs', { libraryId: '/sciml/differentialequations.jl', query: 'solve keyword arguments saveat abstol' })).kind === 'next');
const d4 = await suite2('mcp__context7__query-docs', { libraryId: '/sciml/differentialequations.jl', query: 'explain:\nfunction rate!(s, dt)\n  s\nend' });
cas('Context7 query-docs + code dans `query` -> deny', d4.kind === 'deny' && /lignes de code/.test(d4.reason));
const d5 = await suite2('mcp__context7__query-docs', { libraryId: '/x/y', query: 'how does PlasmaDigitalTwin call the rate table?' });
cas('Context7 query-docs + identifiant du framework -> deny', d5.kind === 'deny' && /identifiant/.test(d5.reason));
cas('subagent generique non configure -> next', (await suite('subagent', { prompt: 'function f(x)\n x\nend' })).kind === 'next');

console.log(`\nBILAN : ${total - faux}/${total}`);
process.exit(faux ? 1 : 0);
