// Controle gratuit du greffon dsh-julia-gate (outil modele `julia_gate`) -- Phase 2.
//
//     node harness/julia_gate_unit.mjs
//
// Une FAUSSE porte.py (ecrite dans un dossier temporaire) rend le code demande par le nom
// du fichier passe : vert.jl -> 0, rouge.jl -> 1, orange.jl -> 2, panne.jl -> 3,
// crash.jl -> 1 avec un Traceback Python sur stderr (le cas vu au run Done du 23/08 :
// porte.py plantait en cp1252 APRES le rejeu et le greffon lisait ROUGE). Attendu :
// VERT / ROUGE / ORANGE / PANNE / PANNE, et `dernier.json` relu quand il existe.
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { apply } from '../scripts/dsh-plugins/dsh-julia-gate/index.js';

let total = 0, faux = 0;
function cas(nom, ok, detail) {
  total++;
  if (!ok) faux++;
  console.log(`  ${ok ? 'OK  ' : 'KO  '} ${nom}${detail !== undefined ? '  -- ' + JSON.stringify(detail) : ''}`);
}

const d = mkdtempSync(join(tmpdir(), 'jgate-'));
mkdirSync(join(d, '_gate'));
const porte = join(d, 'porte.py');
writeFileSync(porte, [
  'import sys, json, os',
  'f = os.path.basename(sys.argv[-1])',
  'code = {"vert.jl": 0, "rouge.jl": 1, "orange.jl": 2, "panne.jl": 3, "crash.jl": 1}.get(f, 3)',
  'print("tests cibles : 1 ; budget 30s")',
  'json.dump({"verdict": ["VERT","ROUGE","ORANGE","PANNE"][min(code,3)], "resultats": [{"fichier": "t.jl"}] if code < 3 else [], "non_rejoues": [], "non_couverts": [], "wall_s": 1.5}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_gate", "dernier.json"), "w"))',
  'if f == "crash.jl":',
  '    sys.stderr.write("Traceback (most recent call last):\\n  File porte.py, line 1\\nUnicodeEncodeError: charmap\\n")',
  'sys.exit(code)',
  '',
].join('\n'));

let outil = null;
const ctx = { tools: { register(t) { outil = t; } }, on() {} };
apply(ctx, { porte, repo: d, budget: 5 });
cas('outil julia_gate enregistre', outil && outil.name === 'julia_gate');
cas('schema : files requis', outil && outil.parameters.required.includes('files'));

for (const [f, attendu, code] of [['vert.jl', 'VERT', 0], ['rouge.jl', 'ROUGE', 1], ['orange.jl', 'ORANGE', 2], ['panne.jl', 'PANNE', 3], ['crash.jl', 'PANNE', 3]]) {
  const r = await outil.execute({ files: [f] });
  cas(`${f} -> ${attendu} (code ${code})`, r.verdict === attendu && r.code === code, { verdict: r.verdict, code: r.code });
  if (f === 'vert.jl') cas('dernier.json relu (1 test rejoue, wall 1.5)', r.tests_rejoues === 1 && r.wall_s === 1.5, { t: r.tests_rejoues, w: r.wall_s });
  if (f === 'crash.jl') cas('crash : la sortie garde le Traceback pour le modele', /Traceback/.test(r.sortie));
}
const vide = await outil.execute({ files: [] });
cas('aucun fichier -> ORANGE sans lancer la porte', vide.verdict === 'ORANGE' && vide.code === 2);
const rendu = outil.output.render({}, vide);
cas('render : texte "VERDICT ORANGE"', Array.isArray(rendu) && /^VERDICT ORANGE/.test(rendu[0].text));

rmSync(d, { recursive: true, force: true });
console.log(`\nBILAN : ${total - faux}/${total}`);
process.exit(faux ? 1 : 0);
