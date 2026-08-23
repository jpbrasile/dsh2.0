// Lit un journal de session dsh (session.jsonl.zstd : frames Zstandard concatenees,
// une ligne JSON par evenement) et le rend en JSONL clair sur stdout -- Phase 3.
//
//     node harness/session_lire.mjs <session.jsonl.zstd>            # JSONL clair
//     node harness/session_lire.mjs <session.jsonl.zstd> --resume   # types d'evenements, comptes
//
// Pas de decodage "intelligent" : le distilleur (harness/distiller.py) lit ce JSONL.
import { readFileSync } from 'node:fs';
import { zstdDecompressSync } from 'node:zlib';

const [fichier, mode] = process.argv.slice(2);
if (!fichier) { console.error('usage : node harness/session_lire.mjs <session.jsonl.zstd> [--resume]'); process.exit(2); }

const brut = readFileSync(fichier);
// Un journal = N frames ; zstdDecompressSync ne rend que la premiere -> on avance frame par frame
// en relisant la taille consommee (info.bytesWritten n'existe pas : on re-scanne les en-tetes).
const MAGIC = 0xfd2fb528, SKIP_LO = 0x184d2a50, SKIP_HI = 0x184d2a5f;
const morceaux = [];
let off = 0;
while (off + 4 <= brut.length) {
  const magic = brut.readUInt32LE(off);
  if (magic >= SKIP_LO && magic <= SKIP_HI) { off += 8 + brut.readUInt32LE(off + 4); continue; }
  if (magic !== MAGIC) { console.error(`frame inconnue a l'octet ${off} (magic ${magic.toString(16)})`); break; }
  const fin = finDeFrame(brut, off);
  if (fin === null) { console.error(`frame tronquee a l'octet ${off} (journal encore ouvert ?)`); break; }
  morceaux.push(zstdDecompressSync(brut.subarray(off, fin)));
  off = fin;
}
const texte = Buffer.concat(morceaux).toString('utf8');
const lignes = texte.split('\n').filter((l) => l.trim());

if (mode === '--resume') {
  const comptes = new Map();
  for (const l of lignes) {
    let t = '?';
    try { const o = JSON.parse(l); t = o.type || o.kind || o.event || Object.keys(o).slice(0, 3).join(','); } catch { t = 'JSON invalide'; }
    comptes.set(t, (comptes.get(t) || 0) + 1);
  }
  console.log(`${lignes.length} evenement(s), ${morceaux.length} frame(s), ${texte.length} car.`);
  for (const [t, n] of [...comptes].sort((a, b) => b[1] - a[1])) console.log(`  ${String(n).padStart(5)}  ${t}`);
} else {
  process.stdout.write(lignes.join('\n') + '\n');
}

/** Fin (exclusive) d'une frame Zstandard complete commencant a `off`, ou null si tronquee. */
function finDeFrame(b, off) {
  let p = off + 4;
  if (p >= b.length) return null;
  const fhd = b[p++];
  const fcsFlag = fhd >> 6, single = (fhd >> 5) & 1, checksum = (fhd >> 2) & 1, didSize = fhd & 3;
  if (!single) p += 1;                       // Window_Descriptor
  p += [0, 1, 2, 4][didSize];                 // Dictionary_ID
  p += fcsFlag === 0 ? (single ? 1 : 0) : [1, 2, 4, 8][fcsFlag];   // Frame_Content_Size
  for (;;) {                                  // blocs
    if (p + 3 > b.length) return null;
    const h = b[p] | (b[p + 1] << 8) | (b[p + 2] << 16);
    const dernier = h & 1, type = (h >> 1) & 3, taille = h >> 3;
    p += 3 + (type === 1 ? 1 : taille);       // RLE : 1 octet ; raw / compresse : `taille`
    if (p > b.length) return null;
    if (dernier) break;
  }
  if (checksum) p += 4;
  return p <= b.length ? p : null;
}
