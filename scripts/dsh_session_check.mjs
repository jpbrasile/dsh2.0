/**
 * dsh_session_check.mjs -- preflight du magasin de sessions DSH.
 *
 * POURQUOI CE FICHIER EXISTE (mesure 2026-08-21)
 *   Au boot, dsh-workspace appelle listArtifacts() de dsh-session-persistence-jsonl,
 *   qui parcourt TOUTES les sessions de TOUS les workspaces sous ~/.dsh/sessions.
 *   UNE seule session illisible fait echouer le boot -- pour tous les workspaces,
 *   avec une trace qui ne NOMME AUCUN FICHIER :
 *     "plugin tree failed to load: ... corrupt Zstandard session log:
 *      first frame is not exactly one header line"
 *   Ce script reproduit exactement les trois refus que listArtifacts peut lever et
 *   sort le NOM du fichier fautif plus la commande de mise en quarantaine.
 *
 * ARMES DU CONTROLE (les deux ont ete tirees le 2026-08-21)
 *   known-GOOD : node scripts/dsh_session_check.mjs
 *                -> 45 journaux, 0 refus
 *   known-BAD  : node scripts/dsh_session_check.mjs "%USERPROFILE%\.dsh\quarantine\20260821-headerless"
 *                -> 1 refus, meme message que celui d'en haut
 *
 * Le controle est ADVISORY : il decrit, il ne refuse rien. Code de sortie 1 quand
 * au moins un journal est fautif, 0 sinon, 2 si le magasin est introuvable.
 */
import { open, readdir, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { zstdDecompressSync } from 'node:zlib';

/** Meme constante que dsh-session-persistence-jsonl (0xFD2FB528). */
const ZSTD_MAGIC = 4247762216;
const CHUNK = 8192;

/**
 * Port fidele de scanZstdFrames() : delimite les frames Zstandard COMPLETES sans
 * les decompresser. Renvoie {frames, tornStart} ; tornStart marque une frame
 * incomplete en fin de buffer (attendu tant qu'on lit par morceaux).
 */
function scanZstdFrames(buffer, maxFrames = Number.POSITIVE_INFINITY) {
  const frames = [];
  let offset = 0;
  while (offset < buffer.length) {
    const start = offset;
    if (buffer.length - offset < 4) return { frames, tornStart: start };
    if (buffer.readUInt32LE(offset) !== ZSTD_MAGIC) {
      throw new Error('invalid frame magic at byte ' + offset);
    }
    offset += 4;
    if (offset === buffer.length) return { frames, tornStart: start };
    const descriptor = buffer.readUInt8(offset);
    offset += 1;
    if ((descriptor & 24) !== 0) throw new Error('reserved frame-header bit at byte ' + (offset - 1));
    const contentSizeFlag = descriptor >>> 6;
    const singleSegment = (descriptor & 32) !== 0;
    const checksum = (descriptor & 4) !== 0;
    const dictionaryFlag = descriptor & 3;
    const dictionaryBytes = dictionaryFlag === 3 ? 4 : dictionaryFlag;
    const contentSizeBytes = contentSizeFlag === 0 ? (singleSegment ? 1 : 0) : 1 << contentSizeFlag;
    const remainingHeaderBytes = (singleSegment ? 0 : 1) + dictionaryBytes + contentSizeBytes;
    if (buffer.length - offset < remainingHeaderBytes) return { frames, tornStart: start };
    offset += remainingHeaderBytes;
    for (;;) {
      if (buffer.length - offset < 3) return { frames, tornStart: start };
      const blockHeader = buffer.readUIntLE(offset, 3);
      offset += 3;
      const lastBlock = (blockHeader & 1) !== 0;
      const blockType = (blockHeader >>> 1) & 3;
      const blockSize = blockHeader >>> 3;
      if (blockType === 3) throw new Error('reserved block type at byte ' + (offset - 3));
      const payloadBytes = blockType === 1 ? 1 : blockSize;
      if (buffer.length - offset < payloadBytes) return { frames, tornStart: start };
      offset += payloadBytes;
      if (lastBlock) break;
    }
    if (checksum) {
      if (buffer.length - offset < 4) return { frames, tornStart: start };
      offset += 4;
    }
    frames.push({ start, end: offset });
    if (frames.length === maxFrames) return { frames };
  }
  return { frames };
}

/**
 * Port fidele de readFirstZstdLine() : lit par morceaux de 8 Ko jusqu'a tenir la
 * PREMIERE frame complete, la decompresse, puis exige qu'elle contienne
 * exactement une ligne (assertZstdHeaderFrame).
 * @returns {Promise<{ok: true, line: string} | {ok: false, why: string}>}
 */
async function readFirstZstdLine(path) {
  const handle = await open(path, 'r');
  try {
    let content = Buffer.alloc(0);
    const chunk = Buffer.alloc(CHUNK);
    for (;;) {
      const { bytesRead } = await handle.read(chunk, 0, CHUNK, null);
      if (bytesRead === 0) {
        return { ok: false, why: 'journal vide ou premiere frame jamais terminee (fichier tronque)' };
      }
      content = Buffer.concat([content, chunk.subarray(0, bytesRead)]);
      let first;
      try {
        first = scanZstdFrames(content, 1).frames[0];
      } catch (error) {
        return { ok: false, why: 'structure Zstandard invalide : ' + error.message };
      }
      if (first === undefined) continue;
      let plaintext;
      try {
        plaintext = zstdDecompressSync(content.subarray(first.start, first.end));
      } catch (error) {
        return { ok: false, why: 'la frame d en-tete ne se decompresse pas : ' + error.message };
      }
      const nl = plaintext.indexOf(10);
      if (plaintext.length === 0) {
        return { ok: false, why: 'first frame is not exactly one header line (frame d en-tete VIDE)' };
      }
      if (nl !== plaintext.length - 1) {
        return {
          ok: false,
          why: 'first frame is not exactly one header line (' + plaintext.length
            + ' octets, premier saut de ligne a ' + nl
            + ' -- l en-tete a ete perdu, la frame commence par des evenements)'
        };
      }
      return { ok: true, line: plaintext.subarray(0, -1).toString('utf8') };
    }
  } finally {
    await handle.close();
  }
}

/** Premiere ligne d'un journal NON compresse (compression: none). */
async function readFirstPlainLine(path) {
  const handle = await open(path, 'r');
  try {
    const chunk = Buffer.alloc(CHUNK);
    let content = Buffer.alloc(0);
    for (;;) {
      const { bytesRead } = await handle.read(chunk, 0, CHUNK, null);
      if (bytesRead === 0) return { ok: false, why: 'journal vide' };
      content = Buffer.concat([content, chunk.subarray(0, bytesRead)]);
      const nl = content.indexOf(10);
      if (nl !== -1) return { ok: true, line: content.subarray(0, nl).toString('utf8') };
    }
  } finally {
    await handle.close();
  }
}

/** Reproduit isHeaderLine/parseHeaderMeta : l'id de session porte par l'en-tete. */
function headerId(line) {
  try {
    const parsed = JSON.parse(line);
    if (parsed?.type !== 'session' || typeof parsed.id !== 'string') return undefined;
    return parsed.id;
  } catch {
    return undefined;
  }
}

async function listDirs(path) {
  const entries = await readdir(path, { withFileTypes: true });
  return entries.filter((e) => e.isDirectory()).map((e) => e.name);
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

const root = process.argv[2] ?? join(homedir(), '.dsh', 'sessions');

if (!await exists(root)) {
  console.log('magasin de sessions absent : ' + root + ' (rien a verifier)');
  process.exit(2);
}

const bad = [];
const ids = new Map();
let scanned = 0;

for (const project of await listDirs(root)) {
  const pdir = join(root, project);
  for (const session of await listDirs(pdir)) {
    const sdir = join(pdir, session);
    const zstdPath = join(sdir, 'session.jsonl.zstd');
    const plainPath = join(sdir, 'session.jsonl');
    const hasZstd = await exists(zstdPath);
    const hasPlain = await exists(plainPath);

    // Refus 2 de listArtifacts : les deux encodages coexistent -> encodingMismatch.
    if (hasZstd && hasPlain) {
      bad.push({ path: sdir, why: 'les deux encodages coexistent (session.jsonl ET session.jsonl.zstd) -> encoding mismatch au boot' });
      continue;
    }
    if (!hasZstd && !hasPlain) continue;

    const path = hasZstd ? zstdPath : plainPath;
    scanned += 1;
    const result = hasZstd ? await readFirstZstdLine(path) : await readFirstPlainLine(path);
    if (!result.ok) {
      bad.push({ path, why: result.why });
      continue;
    }
    // Refus 3 de listArtifacts : deux repertoires portent le meme id d'en-tete.
    const id = headerId(result.line);
    if (id === undefined) continue; // en-tete non reconnu -> listArtifacts l'ignore, pas un refus
    const seen = ids.get(id);
    if (seen !== undefined) {
      bad.push({ path, why: 'id de session "' + id + '" deja porte par ' + seen + ' -> duplicate id au boot' });
    } else {
      ids.set(id, path);
    }
  }
}

if (bad.length === 0) {
  console.log('magasin de sessions DSH : ' + scanned + ' journaux, aucun ne bloque le boot   [' + root + ']');
  process.exit(0);
}

console.log('magasin de sessions DSH : ' + bad.length + ' journal(aux) sur ' + scanned + ' BLOQUENT le boot de dsh');
console.log('  (listArtifacts parcourt TOUS les workspaces : un seul fichier fautif tue tous les profils)');
for (const b of bad) {
  console.log('');
  console.log('  ' + b.path);
  console.log('      ' + b.why);
}
console.log('');
console.log('METTRE EN QUARANTAINE (les octets sont conserves, rien n est supprime) :');
for (const b of bad) {
  const dir = b.path.endsWith('.zstd') || b.path.endsWith('.jsonl')
    ? b.path.slice(0, b.path.lastIndexOf('\\') === -1 ? b.path.lastIndexOf('/') : b.path.lastIndexOf('\\'))
    : b.path;
  console.log('  .\\scripts\\dsh.ps1 -QuarantineSession "' + dir + '"');
}
process.exit(1);
