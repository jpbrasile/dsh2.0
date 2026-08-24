// Controle gratuit du greffon plan-spool (scripts/dsh-plugins/dsh-plan-spool) -- rodage D3.
//
//     node harness/plan_spool_unit.mjs
//
// Rejoue le defaut du jour 1 essai 1 : un plan de ~5 k tokens recopie verbatim dans un
// argument d'outil (3 x "Upstream idle timeout exceeded"). Avec le greffon : le texte long
// d'un outil vise part dans PLAN.md, le parent recoit un accuse court ; un texte court, un
// autre outil, une erreur d'outil -- intacts.
import { mkdtempSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spooler, apply } from '../scripts/dsh-plugins/dsh-plan-spool/index.js';

let total = 0, faux = 0;
function cas(nom, ok, detail) {
  total++;
  if (!ok) faux++;
  console.log(`  ${ok ? 'OK  ' : 'KO  '} ${nom}${detail !== undefined ? '  -- ' + JSON.stringify(String(detail).slice(0, 90)) : ''}`);
}

console.log('== spooler() pur');
const LONG = 'PLAN: etape 1 puis etape 2. '.repeat(200);   // ~5600 car.
const COURT = 'petit plan';
{
  const r = spooler(LONG, { seuil: 2000, fichier: 'C:/ws/PLAN.md' });
  cas('texte long -> accuse', r !== null);
  cas('accuse porte la taille exacte', r !== null && r.accuse.includes(`(${LONG.length} chars)`));
  cas('accuse nomme PLAN.md', r !== null && /READ PLAN\.md/.test(r.accuse));
  cas('accuse contient un apercu, pas le plan entier', r !== null && r.accuse.length < 800, r && r.accuse.length);
  cas('texte court -> intact (null)', spooler(COURT, { seuil: 2000, fichier: 'C:/ws/PLAN.md' }) === null);
  cas('non-string -> intact (null)', spooler(undefined, { seuil: 2000, fichier: 'C:/ws/PLAN.md' }) === null);
}

console.log('== greffon monte sur un faux ctx (cwd = espace de travail temporaire)');
const ws = mkdtempSync(join(tmpdir(), 'pspool-'));
const hooks = {};
const cwd0 = process.cwd();
process.chdir(ws);
apply({ on(ev, fn) { hooks[ev] = fn; } }, { tools: ['planner'], seuil: 2000 });
process.chdir(cwd0);
cas('hook tools/post-execute pose', typeof hooks['tools/post-execute'] === 'function');

const passe = (name, result, decision) =>
  hooks['tools/post-execute']({ name, arguments: {} }, result, async () => decision);

// 1. planner long, forme `content` (tableau de blocs texte)
{
  const d = await passe('planner', { isError: false, content: [{ type: 'text', text: LONG }] }, { kind: 'accept' });
  const plan = join(ws, 'PLAN.md');
  cas('planner long (content) -> PLAN.md ecrit', existsSync(plan));
  cas('PLAN.md contient le plan entier', existsSync(plan) && readFileSync(plan, 'utf8') === LONG);
  cas('le parent recoit l accuse court', Array.isArray(d.content) && d.content[0].text.includes('written to PLAN.md'), d.content && d.content[0].text);
}
// 2. deuxieme spool -> PLAN_2.md (pas d ecrasement)
{
  const d = await passe('planner', { isError: false, content: [{ type: 'text', text: LONG + ' bis' }] }, { kind: 'accept' });
  cas('2e plan -> PLAN_2.md (pas d ecrasement)', existsSync(join(ws, 'PLAN_2.md')) && readFileSync(join(ws, 'PLAN.md'), 'utf8') === LONG);
  cas('accuse 2 nomme PLAN_2.md', Array.isArray(d.content) && d.content[0].text.includes('PLAN_2.md'));
}
// 3. planner court -> intact
{
  const avant = { kind: 'accept' };
  const d = await passe('planner', { isError: false, content: [{ type: 'text', text: COURT }] }, avant);
  cas('planner court -> decision intacte', d === avant);
}
// 4. autre outil (coder) long -> intact
{
  const avant = { kind: 'accept' };
  const d = await passe('coder', { isError: false, content: [{ type: 'text', text: LONG }] }, avant);
  cas('outil non vise -> intact', d === avant);
}
// 5. erreur d outil -> intact
{
  const avant = { kind: 'accept' };
  const d = await passe('planner', { isError: true, content: [{ type: 'text', text: LONG }] }, avant);
  cas('erreur d outil -> intact', d === avant);
}
// 6. forme `value` (chaine canonique) -> accuse en `value`
{
  const d = await passe('planner', { isError: false, value: LONG }, { kind: 'accept', value: LONG });
  cas('forme value -> accuse en value', typeof d.value === 'string' && d.value.includes('chars) has been written'), d.value);
}
// 7. decision non-accept (deny d un mur en aval) -> intacte
{
  const avant = { kind: 'deny', reason: 'x' };
  const d = await passe('planner', { isError: false, content: [{ type: 'text', text: LONG }] }, avant);
  cas('decision non-accept -> intacte', d === avant);
}

rmSync(ws, { recursive: true, force: true });
console.log(`\nBILAN : ${total - faux}/${total}`);
process.exit(faux ? 1 : 0);
