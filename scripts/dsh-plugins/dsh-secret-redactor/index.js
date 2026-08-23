/**
 * dsh-secret-redactor -- masque les secrets dans les RESULTATS d'outils avant
 * qu'ils n'atteignent le modele, le journal de session ou un consommateur.
 *
 * POURQUOI UN GREFFON LOCAL (mesure du 23/08 sur l'arbre 0.1.1-rc.2)
 *   Aucun des 188 paquets du scope ne redige les resultats d'outils : le mot
 *   `redact` n'apparait que dans la couche settings/credentials (masquage des
 *   cles dans les surfaces de configuration) et dans la telemetrie. Un `cat
 *   .env`, un `Get-ChildItem env:` ou une page lue qui contient un jeton
 *   partent donc tels quels vers le fournisseur -- et pour une route OPEN
 *   (modele stealth/gratuit qui s'entraine sur les entrees), c'est une fuite.
 *
 * OU IL SE BRANCHE
 *   `tools/post-execute`, la cascade qui peut REMPLACER la valeur canonique
 *   d'un resultat reussi (`{ kind: 'accept', value }`, re-rendue par l'outil
 *   lui-meme) et le contenu d'un resultat en erreur (`{ kind: 'accept',
 *   content }`). Le README de dsh-tools est explicite : « Content replacement
 *   is not a confidentiality boundary: block or replace the value when
 *   programmatic consumers must not receive it. » On remplace donc la VALEUR
 *   chaque fois que c'est permis (un resultat en erreur n'a pas de valeur :
 *   contenu seulement). `tools/result`, observe apres, ne voit que la version
 *   masquee -- donc le journal de session aussi.
 *
 * CE QU'IL MASQUE
 *   1. les VALEURS VIVES : chaque variable d'env dont le nom finit par
 *      _API_KEY / _TOKEN / _SECRET / PASSWORD (12 caracteres ou plus), plus les
 *      `refs:` de $DSH_HOME/.credentials.yaml et les lignes NOM=valeur de
 *      $DSH_HOME/.env et <cwd>/.env. Les valeurs sont gardees en memoire du
 *      processus, jamais ecrites, jamais annoncees (seul leur NOMBRE l'est).
 *   2. des MOTIFS de jetons connus (OpenRouter, OpenAI/DeepSeek/z.ai `sk-`,
 *      Google `AIza`, GitHub `ghp_`/`github_pat_`, Slack `xox?-`, FreeLLMAPI,
 *      `Bearer <jeton>`, et `NOM_API_KEY=<valeur>` generique).
 *   Le remplacement garde les 6 premiers caracteres puis `***REDACTED***`,
 *   pour que le modele comprenne qu'il y avait un secret et lequel, sans
 *   pouvoir le reconstituer.
 *
 * CE QU'IL NE FAIT PAS
 *   Il ne lit pas les ARGUMENTS des appels (un secret que le modele ecrit
 *   lui-meme est deja dans son contexte) et ne touche pas aux messages de
 *   l'utilisateur. Ce n'est pas une frontiere noyau : un outil qui ecrit le
 *   secret dans un fichier puis le relit par morceaux de 5 caracteres passe ;
 *   une cle coupee sur deux lignes (continuation `\`) passe de la meme
 *   facon (red team 0-walls, 23/08 : meme classe, documentee). Les autres
 *   greffons `tools/post-execute` places AVANT lui dans la cascade voient la
 *   valeur brute : c'est le contrat de la cascade, pas un defaut local.
 *
 * RED TEAM 0-walls (23/08), corrige ici : `Bearer:jeton` (deux-points), noms
 *   d'env vars ACCESS_KEY / SECRET_KEY / *_PASS / CREDENTIAL, valeurs vives
 *   des 8 caracteres (etait 12), motifs AWS / HuggingFace / Groq / Stripe /
 *   SendGrid / Twilio, et relecture des fichiers de secrets a chaque resultat
 *   (les valeurs etaient figees au demarrage).
 *
 * @module dsh-secret-redactor
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const name = 'secret-redactor';
export const inject = ['tools'];

const KEEP = 6;
const MARK = '***REDACTED***';
const MIN_LIVE = 8;                 // longueur minimale d'une valeur vive masquee (red team : 12 laissait passer 11)
/** Noms d'env vars dont la valeur est un secret. Large a dessein : un faux positif masque
 *  une valeur non secrete dans un resultat d'outil, un faux negatif laisse partir une cle. */
const NOM_SECRET = /(API_?KEY|ACCESS_?KEY|SECRET|TOKEN|PASSW(?:OR)?D|_PASS$|_KEY$|CREDENTIAL|PRIVATE_KEY)/i;

/** Motifs de jetons connus. L'ordre compte : les plus specifiques d'abord. */
const PATTERNS = [
  /sk-or-v1-[A-Za-z0-9]{20,}/g,
  /sk-ant-[A-Za-z0-9_-]{20,}/g,
  /sk-[A-Za-z0-9_-]{20,}/g,
  /AIza[0-9A-Za-z_-]{30,}/g,
  /gh[pousr]_[A-Za-z0-9]{30,}/g,
  /github_pat_[A-Za-z0-9_]{20,}/g,
  /xox[abp]-[A-Za-z0-9-]{20,}/g,
  /freellmapi-[A-Za-z0-9_-]{16,}/g,
  /AKIA[0-9A-Z]{16}/g,                          // AWS access key id
  /hf_[A-Za-z0-9]{30,}/g,                       // HuggingFace
  /gsk_[A-Za-z0-9]{30,}/g,                      // Groq
  /sk_(?:live|test)_[A-Za-z0-9]{20,}/g,         // Stripe
  /SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/g, // SendGrid
  /\bSK[0-9a-f]{32}\b/g,                        // Twilio
  /(Bearer[\s:]+)[A-Za-z0-9._~+/=-]{20,}/gi,
  /([A-Z0-9_]*(?:API_KEY|APIKEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*[=:]\s*['"]?)([A-Za-z0-9._~+/=-]{12,})/g,
];

function keep(s) { return s.slice(0, KEEP) + MARK; }

/** Lit les NOM=valeur / `  NOM: valeur` d'un fichier, sans jamais les journaliser. */
function valuesFromFile(path, yamlRefs) {
  let text;
  try { text = readFileSync(path, 'utf8'); } catch { return []; }
  const out = [];
  for (const line of text.split(/\r?\n/)) {
    const m = yamlRefs
      ? /^\s+([A-Za-z0-9_]+):\s*(\S+)\s*$/.exec(line)
      : /^\s*(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*['"]?([^'"\s#]+)/.exec(line);
    if (m && m[2].length >= MIN_LIVE) out.push(m[2]);
  }
  return out;
}

function liveValues() {
  const vals = new Set();
  for (const [k, v] of Object.entries(process.env)) {
    if (NOM_SECRET.test(k) && typeof v === 'string' && v.length >= MIN_LIVE) vals.add(v);
  }
  const home = process.env.DSH_HOME || join(process.env.USERPROFILE || process.env.HOME || '', '.dsh');
  for (const v of valuesFromFile(join(home, '.credentials.yaml'), true)) vals.add(v);
  for (const v of valuesFromFile(join(home, '.env'), false)) vals.add(v);
  for (const v of valuesFromFile(join(process.cwd(), '.env'), false)) vals.add(v);
  // les plus longues d'abord : une valeur prefixe d'une autre ne doit pas la laisser a moitie
  return [...vals].sort((a, b) => b.length - a.length);
}

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

export function apply(ctx, config = {}) {
  const values = liveValues();
  let hits = 0;

  function maskString(s) {
    let out = s;
    // relu a chaque resultat : un .env ou un credentials modifie pendant la session
    // etait invisible (red team 0-walls). Trois petits fichiers, cout negligeable.
    for (const v of liveValues()) out = out.replace(new RegExp(escapeRe(v), 'g'), (m) => { hits++; return keep(m); });
    for (const re of PATTERNS) {
      // Le callback de String.replace recoit (match, ...groupes, offset, chaine) :
      // pour un motif SANS groupe, le 2e argument est l'OFFSET et le 3e la chaine
      // entiere. La version du matin lisait `(m, g1, g2)` et, sur les motifs sans
      // groupe, renvoyait offset + keep(chaine entiere) : la cle disparaissait
      // (le banc sur le fil disait OK) mais TOUT le resultat d'outil etait detruit,
      // et le motif Bearer (un groupe) plantait sur keep(offset). Trouve par
      // harness/murs_unit.mjs le 23/08, pas par le banc a agents.
      out = out.replace(re, (...args) => {
        hits++;
        const m = args[0];
        const g = args.slice(1, -2);                       // groupes captures seulement
        if (g.length >= 2 && g[1] !== undefined) return g[0] + keep(g[1]);   // NOM=valeur : on garde le nom
        if (g.length >= 1 && typeof g[0] === 'string' && /^Bearer/i.test(g[0])) return g[0] + MARK;
        return keep(m);
      });
    }
    return out;
  }

  function deepMask(v) {
    if (typeof v === 'string') return maskString(v);
    if (Array.isArray(v)) return v.map(deepMask);
    if (v && typeof v === 'object') {
      const o = {};
      for (const [k, x] of Object.entries(v)) o[k] = deepMask(x);
      return o;
    }
    return v;
  }

  ctx.on('tools/post-execute', async (exec, result, next) => {
    const decision = await next();
    if (!decision || decision.kind !== 'accept') return decision;
    const before = hits;
    if (!result.isError && !Object.hasOwn(decision, 'content')) {
      const src = Object.hasOwn(decision, 'value') ? decision.value : result.value;
      const masked = deepMask(src);
      if (hits !== before) {
        console.error(`secret-redactor: ${hits - before} secret(s) masque(s) dans la valeur de ${exec.name}`);
        return { ...decision, value: masked };
      }
      return decision;
    }
    const content = Object.hasOwn(decision, 'content') ? decision.content : result.content;
    const masked = deepMask(content);
    if (hits !== before) {
      console.error(`secret-redactor: ${hits - before} secret(s) masque(s) dans le contenu de ${exec.name}`);
      return { ...decision, content: masked };
    }
    return decision;
  });

  // L'annonce au demarrage : pas d'annonce = pas de garde (recette DSH_EXTENSION_RECIPE).
  console.error(`secret-redactor: arme -- ${PATTERNS.length} motifs, ${values.length} valeur(s) vive(s) (env + credentials + .env), jamais affichees`);
}
