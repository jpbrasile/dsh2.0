/**
 * effitech-image -- un serveur MCP stdio, sans aucune dependance, qui rend une
 * photographie du site EFFITECH sous forme de BLOC IMAGE MCP.
 *
 * POURQUOI IL EXISTE
 *   `@deepseek-ai/dsh-mcp-client` sait deja relayer un bloc image d'un serveur
 *   MCP vers le modele : il valide le media-type (png/jpeg/webp/gif), refuse un
 *   base64 non canonique, puis range l'image dans le magasin d'attachements.
 *   Ce qui manquait, c'est un serveur qui en EMETTE un. Aucun serveur MCP
 *   n'etait configure sur cette machine (mesure du 21/08 : zero occurrence de
 *   `mcp` dans settings.yaml et dans les deux cordis.patch.yml).
 *
 * LE REFUS QU'IL FAUT CONNAITRE AVANT DE DEBOGUER
 *   Le pont echoue FERME sur la capacite du modele, pas sur l'image :
 *       if (!info.inputModalities.includes("image"))
 *           throw new Error(`model "${model}" does not declare image input`)
 *   (dsh-mcp-client/lib/index.js:330). Or `llm-pi-ai` met par defaut
 *   `DEFAULT_INPUT = ["text"]` (index.js:862). Une route locale qui ne declare
 *   pas `input: [text, image]` refuse donc TOUTE image, meme servie par un
 *   llama-server multimodal parfaitement charge. Le README de llm-pi-ai dit que
 *   les modalites "have no harness consumer" : c'etait vrai avant ce pont, ce
 *   ne l'est plus.
 *
 * PERIMETRE VOLONTAIREMENT ETROIT
 *   L'outil ne prend PAS d'URL. Il prend un nom parmi une table close, et l'hote
 *   est en dur. Un outil de recuperation pilote par une chaine libre serait
 *   utilisable par le contenu qu'il rapporte pour aller chercher n'importe quoi ;
 *   ici la surface est la table ci-dessous, et rien d'autre.
 *
 * Usage : node server.mjs      (transport stdio, JSON-RPC delimite par lignes)
 */

import { Buffer } from 'node:buffer';

/** Table CLOSE : le seul vocabulaire que l'outil accepte. Pas d'URL libre. */
const ASSETS = {
  dbd: { file: 'dbd.jpg', legend: 'Decharge Barriere Dielectrique (DBD)' },
  corona: { file: 'corona.jpg', legend: 'Decharge Corona' },
  arc_glissant: { file: 'arcglissant.jpg', legend: 'Arc Glissant' }
};

const HOST = 'https://effitech.eu/assets/';

/** Les versions que le SDK 1.12 du client sait negocier. */
const SUPPORTED = ['2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05', '2024-10-07'];
const FALLBACK = '2025-06-18';

const TOOL = {
  name: 'get_site_image',
  description:
    "Rend une photographie de decharge plasma publiee sur le site d'EFFITECH "
    + '(generateurs haute tension pulsee, plasma froid atmospherique) sous forme '
    + "d'image que le modele peut regarder. Trois images existent : dbd, corona, "
    + 'arc_glissant. La legende du site est rendue a part, en texte.',
  inputSchema: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        enum: Object.keys(ASSETS),
        description: 'Quelle photographie rendre.'
      },
      withLegend: {
        type: 'boolean',
        description:
          'Joindre la legende publiee par le site. FAUX par defaut : joindre la '
          + 'legende revient a donner la reponse au modele quand on lui demande '
          + "d'identifier le type de decharge."
      }
    },
    required: ['name']
  }
};

/** Ecrire un message JSON-RPC sur stdout (une ligne = un message). */
function send(message) {
  process.stdout.write(JSON.stringify(message) + String.fromCharCode(10));
}

function reply(id, result) {
  send({ jsonrpc: '2.0', id, result });
}

function fail(id, code, message) {
  send({ jsonrpc: '2.0', id, error: { code, message } });
}

/**
 * Un resultat d'outil en erreur, pas une erreur de protocole : le modele doit
 * VOIR ce qui a rate pour corriger son appel, pas recevoir un echec muet.
 */
function toolError(id, text) {
  reply(id, { content: [{ type: 'text', text }], isError: true });
}

/**
 * Appels encore en vol. Sans ce compteur, `stdin` qui se ferme pendant une
 * recuperation reseau emportait le processus AVANT la reponse : le bras
 * known-BAD, synchrone, repondait, et l'appel image restait silencieux --
 * mesure du 21/08. Un client MCP normal laisse stdin ouvert, donc le defaut
 * n'apparait que sous un banc en tube ; c'est exactement pour ca qu'il faut
 * un banc en tube.
 */
let pending = 0;
let stdinClosed = false;

function settle() {
  pending -= 1;
  if (stdinClosed && pending === 0) done();
}

/**
 * Sortir en laissant la boucle d'evenements se vider, PAS en appelant
 * `process.exit`. Mesure du 21/08 : `process.exit(0)` depuis le chemin de
 * fermeture de stdin declenche sous Windows
 *   Assertion failed: !(handle->flags & UV_HANDLE_CLOSING) ... async.c:76
 * -- un handle libuv deja en cours de fermeture. Les reponses etaient toutes
 * parties, mais un exit force PEUT tronquer une ecriture stdout en attente :
 * on retire simplement stdin des handles vivants et le processus s'arrete seul.
 */
function done() {
  process.stdin.pause();
}

async function getImage(id, args) {
  const key = args && args.name;
  const asset = Object.prototype.hasOwnProperty.call(ASSETS, key) ? ASSETS[key] : undefined;
  if (asset === undefined) {
    toolError(id, `nom inconnu ${JSON.stringify(key)} ; valeurs admises : ${Object.keys(ASSETS).join(', ')}`);
    return;
  }
  const url = HOST + asset.file;
  let response;
  try {
    response = await fetch(url, { redirect: 'follow' });
  } catch (error) {
    toolError(id, `echec reseau sur ${url} : ${String(error)}`);
    return;
  }
  if (!response.ok) {
    toolError(id, `${url} a rendu HTTP ${response.status}`);
    return;
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  // Le pont refuse tout base64 non canonique : Buffer.toString('base64') l'est.
  const content = [
    {
      type: 'text',
      text: `Photographie ${asset.file} publiee sur effitech.eu (${bytes.length} octets).`
        + (args && args.withLegend === true ? ` Legende du site : "${asset.legend}".` : '')
    },
    { type: 'image', data: bytes.toString('base64'), mimeType: 'image/jpeg' }
  ];
  reply(id, { content, isError: false });
}

function handle(message) {
  const { id, method, params } = message;
  if (method === 'initialize') {
    const asked = params && params.protocolVersion;
    reply(id, {
      protocolVersion: SUPPORTED.includes(asked) ? asked : FALLBACK,
      capabilities: { tools: {} },
      serverInfo: { name: 'effitech-image', version: '0.1.0' }
    });
    return;
  }
  // Les notifications n'ont pas d'id et n'attendent aucune reponse.
  if (id === undefined || id === null) return;
  if (method === 'tools/list') { reply(id, { tools: [TOOL] }); return; }
  if (method === 'tools/call') {
    if (params && params.name === TOOL.name) {
      pending += 1;
      void getImage(id, params.arguments)
        .catch((error) => { fail(id, -32603, String(error)); })
        .finally(settle);
      return;
    }
    toolError(id, `outil inconnu : ${params && params.name}`);
    return;
  }
  if (method === 'ping') { reply(id, {}); return; }
  fail(id, -32601, `methode non implementee : ${method}`);
}

let buffer = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  for (;;) {
    const cut = buffer.indexOf(String.fromCharCode(10));
    if (cut < 0) break;
    const line = buffer.slice(0, cut).trim();
    buffer = buffer.slice(cut + 1);
    if (line === '') continue;
    let message;
    try {
      message = JSON.parse(line);
    } catch (error) {
      // Une ligne illisible n'a pas d'id : on ne peut repondre a personne.
      process.stderr.write(`effitech-image: ligne JSON illisible ignoree : ${String(error)}` + String.fromCharCode(10));
      continue;
    }
    try {
      handle(message);
    } catch (error) {
      if (message && message.id !== undefined && message.id !== null) {
        fail(message.id, -32603, String(error));
      }
    }
  }
});
process.stdin.on('end', () => {
  stdinClosed = true;
  if (pending === 0) done();
});
