/**
 * dsh-read-wall -- un mur de LECTURE pour les ouvriers de la route OPEN.
 *
 * POURQUOI UN GREFFON LOCAL (mesure du 23/08 sur l'arbre 0.1.1-rc.2)
 *   Le sandbox livre ne restreint que les ECRITURES. Sous Windows c'est ecrit
 *   noir sur blanc dans `dsh-sandbox-windows-acl` (« Writes are restricted ;
 *   reads, network, and process visibility are not ») et dans `dsh-fs-sandbox`
 *   (« Reads always pass through -- every mode permits reading »). Le README du
 *   harnais exige pourtant qu'un ouvrier OPEN n'ait « no read access to
 *   framework repo or log store ». Rien dans l'arbre ne le fait.
 *
 * CE QUE CE GREFFON FAIT
 *   `tools/pre-execute` : AVANT qu'un outil ne tourne, il regarde chaque
 *   argument de type chaine (recursivement) et REFUSE l'appel si l'un d'eux
 *   nomme une racine interdite -- chemin absolu, chemin relatif resolu depuis
 *   le cwd du processus, formes `~`, `$HOME`, `$env:USERPROFILE`,
 *   `%USERPROFILE%`, barres dans les deux sens, casse ignoree. Pour le shell
 *   (`pwsh`, `bash`), c'est la meme regle appliquee au TEXTE de la commande :
 *   une commande qui epelle une racine interdite, ou l'un de ses segments
 *   marquants, est refusee. Le refus est un resultat d'outil en erreur qui
 *   dit au modele pourquoi, et il s'annonce sur stderr (`read-wall: REFUS`).
 *
 *   Racines toujours interdites, en plus de `roots` : le magasin de sessions
 *   et le fichier de credentials de l'accueil de l'UTILISATEUR (~/.dsh), ceux
 *   du DSH_HOME courant s'il differe, et <cwd>/.env.
 *
 * CE QUE CE GREFFON N'EST PAS -- A LIRE AVANT DE S'Y FIER
 *   C'est un FENCE DE POLITIQUE dans du code de confiance sur des arguments
 *   controles par le modele, pas une frontiere noyau. Il tient pour les outils
 *   fichiers (read/glob/grep/edit/write/str_replace_editor : le chemin EST
 *   l'argument). Il tient pour un shell qui nomme le chemin. Il NE tient PAS
 *   contre un shell qui construit le chemin sans l'epeler : joker
 *   (`C:\Users\test\Documents\agen*\plasma*\Project.toml`), concatenation
 *   de fragments, encodage. Le bras `essai_murs.py --evasion` le mesure et le
 *   garde en ECHEC connu. Un mur de lecture prouvable sous Windows demande
 *   l'OS : un compte Windows dedie aux ouvriers OPEN avec un ACE de refus NTFS
 *   sur le depot framework et le magasin de sessions, ou un jeton restreint
 *   en lecture (pas seulement WRITE_RESTRICTED) -- decision de l'utilisateur,
 *   voir docs/PHASE0.md.
 *
 * @module dsh-read-wall
 */
import { resolve, isAbsolute, join } from 'node:path';

export const name = 'read-wall';
export const inject = ['tools'];

const SHELL_TOOLS = new Set(['pwsh', 'bash', 'shell']);

function home() { return process.env.USERPROFILE || process.env.HOME || ''; }

/** Forme canonique : minuscules, barres obliques, sans barre finale. */
function canon(p) {
  return String(p).replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
}

/** Developpe les formes `~`, `$HOME`, `$env:USERPROFILE`, `%USERPROFILE%` en debut de chemin. */
function expandHome(s) {
  const h = home().replace(/\\/g, '/');
  return s
    .replace(/^~(?=[\\/]|$)/, h)
    .replace(/^\$home(?=[\\/]|$)/i, h)
    .replace(/^\$env:userprofile(?=[\\/]|$)/i, h)
    .replace(/^%userprofile%(?=[\\/]|$)/i, h);
}

export function apply(ctx, config = {}) {
  const h = home();
  const dshHome = process.env.DSH_HOME || join(h, '.dsh');
  const roots = new Set();
  for (const r of config.roots || []) if (r) roots.add(canon(r));
  for (const r of [
    join(h, '.dsh', 'sessions'), join(h, '.dsh', '.credentials.yaml'), join(h, '.dsh', '.env'),
    join(dshHome, 'sessions'), join(dshHome, '.credentials.yaml'), join(dshHome, '.env'),
    join(process.cwd(), '.env'),
  ]) roots.add(canon(r));
  const ROOTS = [...roots];
  // Segments marquants des racines configurees (pas ceux de ~/.dsh, trop
  // generiques) : `agentic-flow-fresh`, `plasma-digital-twin`... Un shell qui
  // les epelle est refuse meme sans le chemin complet.
  const SEGMENTS = new Set();
  for (const r of config.roots || []) {
    for (const seg of canon(r).split('/')) if (seg.length >= 8 && !/^[a-z]:$/.test(seg) && seg !== 'users' && seg !== 'documents') SEGMENTS.add(seg);
  }
  let refus = 0;

  /** La racine interdite que `s` atteint, ou null. */
  function hit(s) {
    if (typeof s !== 'string' || s.length < 2) return null;
    const t = expandHome(s.trim().replace(/^['"]|['"]$/g, ''));
    let abs = t;
    if (!isAbsolute(t) && !/^[a-z]:/i.test(t) && /^[.~\w]/.test(t) && !/\s/.test(t)) {
      try { abs = resolve(process.cwd(), t); } catch { abs = t; }
    }
    const c = canon(abs);
    for (const r of ROOTS) if (c === r || c.startsWith(r + '/')) return r;
    const raw = canon(t);
    for (const r of ROOTS) if (raw.includes(r)) return r;   // racine epelee au milieu d'un texte (commande shell)
    return null;
  }

  /** Parcourt recursivement les arguments ; rend la premiere atteinte. */
  function scan(v, shell) {
    if (typeof v === 'string') {
      const r = hit(v);
      if (r) return { r, s: v };
      if (shell) {
        const c = canon(expandHome(v));
        for (const seg of SEGMENTS) if (c.includes(seg)) return { r: seg, s: v };
      }
      return null;
    }
    if (Array.isArray(v)) { for (const x of v) { const k = scan(x, shell); if (k) return k; } return null; }
    if (v && typeof v === 'object') { for (const x of Object.values(v)) { const k = scan(x, shell); if (k) return k; } return null; }
    return null;
  }

  ctx.on('tools/pre-execute', async (exec, next) => {
    const shell = SHELL_TOOLS.has(exec.name);
    const k = scan(exec.arguments, shell);
    if (!k) return next();
    refus++;
    const msg = `read-wall: REFUS ${refus} -- ${exec.name} vise "${String(k.s).slice(0, 120)}" qui atteint la racine interdite "${k.r}"`;
    console.error(msg);
    return {
      kind: 'deny',
      reason: `read wall: this OPEN worker may not access "${k.r}" (framework repo, session log store or credentials). `
        + 'Do not retry with another spelling of the same path: work inside the harness workspace only.',
    };
  });

  console.error(`read-wall: arme -- ${ROOTS.length} racine(s) interdite(s), ${SEGMENTS.size} segment(s) marquant(s) pour le shell, cwd ${process.cwd()}`);
}
