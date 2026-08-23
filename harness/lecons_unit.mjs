// Controle gratuit du greffon dsh-lecons (variable {{lecons}}) -- Phase 3.
//
//     node harness/lecons_unit.mjs
//
// Verifie : la variable est enregistree ; un fichier absent rend l'en-tete + "(no past
// observations yet)" ; les puces passent, le titre et la prose sont ecartes ; le plafond par
// role tient ; une modification du fichier (mtime) est relue sans relancer ; l'en-tete dit
// "DATA, not instructions" (le cadre que le red team 3 attaque).
import { mkdtempSync, writeFileSync, rmSync, utimesSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { apply, rendre, ENTETE, VIDE } from '../scripts/dsh-plugins/dsh-lecons/index.js';

let total = 0, faux = 0;
function cas(nom, ok, detail) {
  total++;
  if (!ok) faux++;
  console.log(`  ${ok ? 'OK  ' : 'KO  '} ${nom}${detail !== undefined ? '  -- ' + JSON.stringify(detail) : ''}`);
}

// rendre()
cas('vide -> en-tete + VIDE', rendre('') === `${ENTETE}\n${VIDE}`);
const md = ['# Titre du fichier', '', 'Prose explicative a ecarter.', '## planner', '- [2026-08-23 abc] lecon A', '- [2026-08-23 abc] lecon B', '- [2026-08-23 abc] lecon C', '', '## coder', '- [2026-08-23 def] lecon D', ''].join('\n');
const r = rendre(md, 2);
cas('titre et prose ecartes', !/Titre du fichier|Prose explicative/.test(r));
cas('sections gardees', /## planner\n- \[2026-08-23 abc\] lecon A\n- \[2026-08-23 abc\] lecon B\n## coder\n- \[2026-08-23 def\] lecon D$/.test(r), r.slice(-80));
cas('plafond 2 par role : lecon C absente', !/lecon C/.test(r));
cas('en-tete "DATA, not instructions"', r.startsWith(ENTETE) && /DATA, not instructions/.test(ENTETE));

// apply() avec un fichier
const d = mkdtempSync(join(tmpdir(), 'lecons-'));
const f = join(d, 'lecons.md');
const vars = {};
const ctx = { systemPrompt: { variable(nom, p) { vars[nom] = p; } } };
apply(ctx, { fichier: f, max: 40 });
cas('variable {{lecons}} enregistree', typeof vars.lecons === 'function');
cas('fichier absent -> VIDE, pas d erreur', vars.lecons().endsWith(VIDE));
writeFileSync(f, '## planner\n- [d s] premiere lecon\n');
cas('fichier ecrit -> relu', /premiere lecon/.test(vars.lecons()));
writeFileSync(f, '## planner\n- [d s] seconde lecon\n');
utimesSync(f, new Date(Date.now() + 5000), new Date(Date.now() + 5000));  // mtime force (ecritures < 1 ms)
cas('fichier modifie (mtime) -> relu sans relance', /seconde lecon/.test(vars.lecons()) && !/premiere/.test(vars.lecons()));
const ctx2 = { systemPrompt: { variable(nom, p) { vars[nom] = p; } } };
apply(ctx2, { fichier: f, variable: 'memoire' });
cas('nom de variable configurable', typeof vars.memoire === 'function');
rmSync(d, { recursive: true, force: true });

console.log(`\nBILAN : ${total - faux}/${total}`);
process.exit(faux ? 1 : 0);
