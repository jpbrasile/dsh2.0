// Controle unitaire des deux greffons de murs -- GRATUIT (pas d'agent, pas de
// modele) : on charge scripts/dsh-plugins/* avec un faux `ctx`, on appelle la
// cascade avec de faux appels d'outils, on regarde la decision.
//
//     node harness/murs_unit.mjs            -> code 0 si tout est conforme
//
// Chaque cas vient d'une trouvaille du red team 0-walls (23/08) ou d'une limite
// que l'on GARDE et que l'on veut voir rester la ou elle est (`attendu: 'passe'`
// = fuite connue ; si un jour elle est fermee, le cas echoue et on met a jour la
// doc). Un verdict ne se deduit jamais d'un message : on lit `kind`.
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';

const DEPOT = new URL('..', import.meta.url).pathname.replace(/^\/([a-z]:)/i, '$1');
const ROOT = 'C:\\Program Files\\nodejs';                  // existe sur cette machine, a un nom 8.3
const COURT = execFileSync('powershell', ['-NoProfile', '-Command',
  "(New-Object -ComObject Scripting.FileSystemObject).GetFolder('" + ROOT + "').ShortPath"]).toString().trim(); // C:\PROGRA~1\nodejs
if (!/~/.test(COURT)) { console.error('pas de nom court 8.3 pour ' + ROOT + ' : ' + COURT); process.exit(2); }
let total = 0, faux = 0;
function cas(nom, ok, detail) {
  total++; if (!ok) faux++;
  console.log(`  ${ok ? 'OK   ' : 'ECHEC'} ${nom}${detail ? '  -- ' + detail : ''}`);
}

// ------------------------------------------------------------------ mur
async function mur(roots, exec) {
  const m = await import(new URL('../scripts/dsh-plugins/dsh-read-wall/index.js', import.meta.url).href + '?v=' + Math.random());
  let fn; const ctx = { on: (ev, f) => { if (ev === 'tools/pre-execute') fn = f; } };
  const errs = []; const ce = console.error; console.error = (s) => errs.push(String(s));
  try { m.apply(ctx, { roots }); return { d: await fn(exec, async () => ({ kind: 'next' })), errs }; }
  finally { console.error = ce; }
}
console.log('== read-wall  (racine de test : ' + ROOT + ', forme 8.3 : ' + COURT + ')');
{
  const R = [ROOT];
  const deny = async (nom, args, tool = 'read') => cas(nom, (await mur(R, { name: tool, arguments: args })).d.kind === 'deny');
  const pass = async (nom, args, tool = 'read') => cas(nom, (await mur(R, { name: tool, arguments: args })).d.kind === 'next', 'limite gardee, documentee');
  await deny('chemin direct', { file_path: ROOT + '\\node.exe' });
  await deny('barres obliques + barre finale', { file_path: ROOT.replace(/\\/g, '/') + '/' });
  await deny('nom court 8.3 (red team)', { file_path: COURT + '\\node.exe' });
  await deny('UNC \\\\localhost\\C$ (red team)', { file_path: '\\\\localhost\\C$' + ROOT.slice(2) + '\\node.exe' });
  await deny('UNC \\\\127.0.0.1\\C$ (red team)', { file_path: '\\\\127.0.0.1\\C$' + ROOT.slice(2) + '\\node.exe' });
  await deny('prefixe \\\\?\\ (red team)', { file_path: '\\\\?\\' + ROOT + '\\node.exe' });
  await deny('prefixe \\\\?\\ + 8.3', { file_path: '\\\\?\\' + COURT + '\\node.exe' });
  await deny('read_image sur le framework (red team 3.4)', { file_path: ROOT + '\\x.png' }, 'read_image');
  await deny('outil inconnu, argument imbrique', { opts: { paths: [ROOT + '\\y'] } }, 'outil_futur');
  await deny('shell qui epelle la racine', { command: "Get-Content '" + ROOT + "\\node.exe'" }, 'pwsh');
  await deny('shell avec nom court 8.3', { command: "Get-Content '" + COURT + "\\node.exe'" }, 'pwsh');
  await pass('shell : indirection $env:X (red team, GARDEE)', { command: 'Get-Content $env:X' }, 'pwsh');
  await pass('shell : joker (GARDEE)', { command: "Get-Content 'C:\\Progra*\\node*\\node.exe'" }, 'pwsh');
  cas('chemin hors racine : passe', (await mur(R, { name: 'read', arguments: { file_path: 'C:\\Windows\\win.ini' } })).d.kind === 'next');
  const nc = await mur([], { name: 'read', arguments: { file_path: 'C:\\Windows\\win.ini' } });
  cas('DSH_READ_WALL vide -> TOUT refuse (red team)', nc.d.kind === 'deny' && nc.errs.some((e) => e.includes('NON CONFIGURE')), nc.errs[0]);
}

// ------------------------------------------------------------------ redacteur
async function redacteur(valeur, env = {}) {
  const home = mkdtempSync(join(tmpdir(), 'murs-'));
  const sauve = { ...process.env };
  Object.assign(process.env, env, { DSH_HOME: home });
  try {
    const m = await import(new URL('../scripts/dsh-plugins/dsh-secret-redactor/index.js', import.meta.url).href + '?v=' + Math.random());
    let fn; const ctx = { on: (ev, f) => { if (ev === 'tools/post-execute') fn = f; } };
    const ce = console.error; console.error = () => {};
    try {
      m.apply(ctx, {});
      // relecture : un .env qui apparait APRES le demarrage doit etre masque (red team : valeurs figees)
      writeFileSync(join(home, '.env'), 'APRES_DEMARRAGE_TOKEN=tardif-secret-valeur-9876\n');
      const d = await fn({ name: 'read', arguments: {} }, { isError: false, value: valeur }, async () => ({ kind: 'accept' }));
      return d.value === undefined ? valeur : d.value;
    } finally { console.error = ce; }
  } finally {
    for (const k of Object.keys(process.env)) if (!(k in sauve)) delete process.env[k];
    Object.assign(process.env, sauve);
    rmSync(home, { recursive: true, force: true });
  }
}
console.log('== secret-redactor');
{
  const masque = async (nom, texte, secret, env) => {
    const out = await redacteur(texte, env);
    cas(nom, !out.includes(secret) && out.includes('***REDACTED***'), out.length > 90 ? out.slice(0, 90) + '...' : out);
  };
  await masque('Bearer espace', 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123', 'abcdefghijklmnopqrstuvwxyz0123');
  await masque('Bearer:deux-points (red team)', 'Authorization: Bearer:abcdefghijklmnopqrstuvwxyz0123', 'abcdefghijklmnopqrstuvwxyz0123');
  await masque('env ACCESS_KEY vive (red team)', 'x=' + 'acc3ss-k3y-vive-1', 'acc3ss-k3y-vive-1', { MY_ACCESS_KEY: 'acc3ss-k3y-vive-1' });
  await masque('env SECRET_KEY vive (red team)', 'x=s3cr3t-k3y-vive', 's3cr3t-k3y-vive', { APP_SECRET_KEY: 's3cr3t-k3y-vive' });
  await masque('env DB_PASS vive (red team)', 'x=db-pass-vive-1', 'db-pass-vive-1', { DB_PASS: 'db-pass-vive-1' });
  await masque('valeur vive de 11 caracteres (red team)', 'cle: onzecaracte', 'onzecaracte', { COURTE_API_KEY: 'onzecaracte' });
  // Fausses cles assemblees a l'execution : un litteral de la bonne forme, meme bidon,
  // est refuse par la protection anti-secrets de GitHub (push bloque le 23/08 sur la
  // cle Stripe). L'AWS est l'exemple officiel de la doc AWS, tolere par le scanner.
  const ALPHA = 'abcdefghijklmnopqrstuvwxyz';
  const FAUX_HF = 'hf_' + ALPHA + '0123456789';
  const FAUX_STRIPE = 'sk_live' + '_' + ALPHA;
  await masque('AWS AKIA (red team)', 'aws_access_key_id = AKIAIOSFODNN7EXAMPLE', 'AKIAIOSFODNN7EXAMPLE');
  await masque('HuggingFace hf_ (red team)', 'token ' + FAUX_HF, FAUX_HF);
  await masque('Stripe sk_live_ (red team)', FAUX_STRIPE, FAUX_STRIPE);
  await masque('relecture des fichiers apres demarrage (red team)', 'v=tardif-secret-valeur-9876', 'tardif-secret-valeur-9876');
  await masque('OpenRouter sk-or-v1', 'k=sk-or-v1-' + 'deadbeef'.repeat(8), 'sk-or-v1-' + 'deadbeef'.repeat(8));
  const clair = await redacteur('rien de secret ici, juste du texte et un chemin C:\\x\\y.txt');
  cas('texte sans secret : intact', clair === 'rien de secret ici, juste du texte et un chemin C:\\x\\y.txt');
}

console.log(`\nBILAN : ${total - faux}/${total}`);
process.exit(faux ? 1 : 0);
