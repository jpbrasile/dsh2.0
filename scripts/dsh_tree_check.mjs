/**
 * dsh_tree_check.mjs -- preflight de COHERENCE DE L'ARBRE npx de DSH.
 *
 * POURQUOI CE FICHIER EXISTE (mesure 2026-08-21)
 *   Le lanceur epingle UNE seule chose : `npx -y @deepseek-ai/dsh@<version>`.
 *   Les 65 dependances de ce paquet, elles, sont declarees en CARET
 *   (`^0.1.0-rc.7`), donc npm les resout au plus recent < 0.2.0 le jour de
 *   l'installation. L'arbre mesure le 2026-08-21 :
 *       @deepseek-ai/dsh          0.1.0-rc.7   (epingle par le lanceur)
 *       185 autres @deepseek-ai/* 0.1.0-rc.8   (flottants, installes le 20/08)
 *   L'application etait donc d'une version, tous ses greffons d'une autre.
 *
 * CE QUE CETTE VERSION-LA CASSAIT, AU CODEPOINT
 *   dsh-tool-subagent@0.1.0-rc.8 enregistre une section de prompt au nom FIXE
 *   `delegation:policy` des que `backgroundMode: continuable`. Ni rc.7 ni
 *   0.1.1-rc.2 ne l'enregistrent (verifie sur les trois tarballs). Or le preset
 *   `standard` livre par l'application contient DEUX lignes continuable
 *   (`tool-subagent` spawn et `tool-subagent-fork` fork) dans un meme groupe,
 *   donc une meme portee de prompt. La seconde levait :
 *       prompt section "delegation:policy" is already registered in this scope
 *   Le preset ne montait plus, donc AUCUNE session ne s'ouvrait ni ne
 *   reprenait -- l'UI repondait toujours 200, mais aucun modele ne chargeait.
 *
 * CE QUE CE CONTROLE MESURE
 *   1. la COHERENCE : version de l'app contre versions de ses greffons ;
 *   2. la PAIRE FATALE elle-meme, qui est le vrai defaut : un greffon qui
 *      enregistre `delegation:policy` a nom fixe ET un preset qui porte >= 2
 *      lignes continuable. On nomme le preset. Une simple difference de
 *      versions n'est PAS un refus : elle est frequente et souvent benigne.
 *
 * ARMES DU CONTROLE (les deux tirees le 2026-08-21, sur l'arbre reel)
 *   known-BAD  : arbre dsh 0.1.0-rc.7 + greffons 0.1.0-rc.8
 *                -> PAIRE FATALE nommee (standard, scrub), exit 1
 *   known-GOOD : arbre dsh 0.1.1-rc.2 + greffons 0.1.1-rc.2
 *                -> coherent, aucune paire fatale, exit 0
 *
 * Le controle est ADVISORY : il decrit, il ne refuse rien. Sortie 1 quand une
 * paire fatale existe, 0 sinon, 2 quand aucun arbre npx n'a ete trouve.
 *
 * Usage : node scripts/dsh_tree_check.mjs [version-attendue]
 */
import { readFile, readdir, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';

/** Le nom exact du greffon ; -control / -report sont d'autres paquets. */
const SUBAGENT_PKG = '@deepseek-ai/dsh-tool-subagent';
/** Le nom FIXE dont la seconde occurrence dans une portee est fatale. */
const FIXED_SECTION = 'delegation:policy';

async function exists(path) {
  try { await stat(path); return true; } catch { return false; }
}

async function readJson(path) {
  try { return JSON.parse(await readFile(path, 'utf8')); } catch { return undefined; }
}

async function listDirs(path) {
  try {
    const entries = await readdir(path, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory()).map((e) => e.name);
  } catch { return []; }
}

/**
 * Les lignes `- id: X` d'une composition cordis, avec les champs qui decident
 * si la ligne enregistre une section de delegation. Lecture par TEXTE : on ne
 * reserialise rien, donc rien ne peut etre reecrit par ce controle.
 * @returns {Array<{id: string, name: string, disabled: boolean, backgroundMode: string, background: string}>}
 */
function scanRows(text) {
  const rows = [];
  let current;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/\s+$/, '');
    const head = /^(\s*)-\s+id:\s*(\S+)\s*$/.exec(line);
    if (head !== null) {
      current = { id: head[2], name: '', disabled: false, backgroundMode: '', background: '' };
      rows.push(current);
      continue;
    }
    if (current === undefined) continue;
    const field = /^\s*([A-Za-z]+):\s*(.*)$/.exec(line);
    if (field === null) continue;
    const value = field[2].trim().replace(/^['"]|['"]$/g, '');
    if (field[1] === 'name') current.name = value;
    else if (field[1] === 'disabled') current.disabled = value === 'true';
    else if (field[1] === 'backgroundMode') current.backgroundMode = value;
    else if (field[1] === 'enableRunInBackground') current.background = value;
  }
  return rows;
}

/** Combien de lignes d'un preset enregistreraient `delegation:policy`. */
function continuableSubagentRows(text) {
  return scanRows(text).filter((r) =>
    r.name === SUBAGENT_PKG
    && !r.disabled
    && r.backgroundMode === 'continuable'
    && r.background !== 'false');
}

/** Le greffon installe enregistre-t-il la section a NOM FIXE ? */
async function pluginRegistersFixedSection(pkgDir) {
  const source = await readFile(join(pkgDir, 'lib', 'index.js'), 'utf8').catch(() => '');
  return source.includes('"' + FIXED_SECTION + '"') || source.includes("'" + FIXED_SECTION + "'");
}

/** Tous les presets visibles : ceux livres par l'app, puis la surcouche user. */
async function presetFiles(appDir) {
  const found = [];
  const packaged = join(appDir, 'config', 'agent-presets');
  for (const name of await listDirs(packaged)) {
    found.push({ preset: name, origin: 'livre', path: join(packaged, name, 'agent.cordis.yml') });
  }
  const overlay = join(homedir(), '.dsh', '.agent-presets');
  for (const name of await listDirs(overlay)) {
    found.push({ preset: name, origin: 'surcouche ~/.dsh', path: join(overlay, name, 'agent.cordis.yml') });
  }
  const kept = [];
  for (const entry of found) if (await exists(entry.path)) kept.push(entry);
  return kept;
}

const wanted = process.argv[2];
const npxRoot = join(process.env.LOCALAPPDATA ?? join(homedir(), 'AppData', 'Local'), 'npm-cache', '_npx');
const runtimeRoot = join(homedir(), '.dsh', 'runtime');

// Deux emplacements possibles : le cache npx (arbre FLOTTANT, re-resolu au gre des
// publications) et ~/.dsh/runtime/<nom> (arbre EPINGLE par un package-lock.json).
const roots = [];
for (const hash of await listDirs(npxRoot)) roots.push({ label: 'npx ' + hash, dir: join(npxRoot, hash) });
for (const name of await listDirs(runtimeRoot)) roots.push({ label: 'runtime ' + name, dir: join(runtimeRoot, name) });

const trees = [];
for (const root of roots) {
  const scoped = join(root.dir, 'node_modules', '@deepseek-ai');
  const appDir = join(scoped, 'dsh');
  const appPkg = await readJson(join(appDir, 'package.json'));
  if (appPkg === undefined) continue;
  const hash = root.label;
  const versions = new Map();
  for (const name of await listDirs(scoped)) {
    if (name === 'dsh') continue;
    const pkg = await readJson(join(scoped, name, 'package.json'));
    if (pkg?.version === undefined) continue;
    const bucket = versions.get(pkg.version) ?? [];
    bucket.push('@deepseek-ai/' + name);
    versions.set(pkg.version, bucket);
  }
  trees.push({ hash, appDir, scoped, app: appPkg.version, versions });
}

if (trees.length === 0) {
  console.log('aucun arbre dsh trouve sous ' + npxRoot + ' ni ' + runtimeRoot + ' (rien a verifier)');
  process.exit(2);
}

const fatal = [];
const lines = [];

let targetSeen = false;

for (const tree of trees) {
  // On ne juge que l'arbre qui va REELLEMENT tourner. Les autres restent dans le
  // cache npx sans etre lances : les declarer fatals ferait crier le lanceur sur
  // une version qu'il n'utilise plus (observe au premier lancement apres un
  // changement de -DshVersion, 21/08).
  const target = wanted === undefined || tree.app === wanted;
  if (target) targetSeen = true;
  const plugins = [...tree.versions.entries()].sort((a, b) => b[1].length - a[1].length);
  const split = plugins.filter(([v]) => v !== tree.app && v.startsWith('0.1.'));
  const shape = plugins.map(([v, names]) => v + ' x' + names.length).join(', ');
  lines.push((target ? '* ' : '  ') + 'arbre ' + tree.hash + ' : app ' + tree.app
    + '  |  greffons ' + shape + (target ? '' : '   (pas la version demandee)'));

  if (!target) continue;
  if (split.length === 0) continue;

  const subagentDir = join(tree.scoped, 'dsh-tool-subagent');
  if (!await exists(subagentDir)) continue;
  if (!await pluginRegistersFixedSection(subagentDir)) continue;

  const subagentPkg = await readJson(join(subagentDir, 'package.json'));
  for (const entry of await presetFiles(tree.appDir)) {
    const text = await readFile(entry.path, 'utf8').catch(() => '');
    const rows = continuableSubagentRows(text);
    if (rows.length < 2) continue;
    fatal.push({
      tree: tree.hash,
      app: tree.app,
      plugin: subagentPkg?.version ?? '?',
      preset: entry.preset,
      origin: entry.origin,
      path: entry.path,
      rows: rows.map((r) => r.id)
    });
  }
}

console.log('arbres npx de dsh (' + trees.length + ') :');
for (const line of lines) console.log('  ' + line);

if (!targetSeen) {
  console.log('coherence : aucun arbre installe pour ' + wanted
    + ' -- npx va l installer au boot, le controle ne dira rien avant le lancement suivant');
  process.exit(0);
}

if (fatal.length === 0) {
  console.log('coherence : aucune paire fatale (greffon a section fixe + preset a 2 lignes continuable)');
  process.exit(0);
}

console.log('');
console.log('PAIRE FATALE : ' + fatal.length + ' preset(s) ne peuvent PAS monter -- aucune session ne s ouvrira');
for (const f of fatal) {
  console.log('');
  console.log('  preset "' + f.preset + '" (' + f.origin + ')');
  console.log('      ' + f.path);
  console.log('      app @deepseek-ai/dsh ' + f.app + ' + greffon dsh-tool-subagent ' + f.plugin);
  console.log('      ' + f.plugin + ' enregistre la section a nom fixe "' + FIXED_SECTION + '",');
  console.log('      et ce preset porte ' + f.rows.length + ' lignes continuable dans une meme portee : ' + f.rows.join(', '));
  console.log('      -> la seconde leve : prompt section "' + FIXED_SECTION + '" is already registered in this scope');
}
console.log('');
console.log('REPARER : aligner l app et ses greffons sur une meme version.');
console.log('  .\\scripts\\dsh.ps1 -Stop');
console.log('  .\\scripts\\dsh.ps1 -DshVersion <version>');
console.log('  (version publiee "latest" : npm view @deepseek-ai/dsh dist-tags)');
process.exit(1);
