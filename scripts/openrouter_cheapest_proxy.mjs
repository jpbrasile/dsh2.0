#!/usr/bin/env node
// openrouter_cheapest_proxy.mjs -- proxy OpenAI-compatible minimal, place entre un
// client qui ne sait nommer QU'UN MODELE (DSH / @deepseek-ai/dsh-llm-pi-ai) et
// OpenRouter, qui n'accepte ses consignes de routage QUE dans le corps de requete.
//
// POURQUOI il existe
// -----------------
// Un profil pi-ai admet exactement : apiKeyEnv, api, baseURL, models,
// modelOverrides, compat, defaultContextWindow, defaultMaxTokens, defaultInput,
// headers, reasoning, thinkingBudgets, cacheRetention, transport, timeoutMs,
// websocketConnectTimeoutMs, streamIdleTimeoutMs, maxRequestImageBytes,
// retryPolicy. AUCUN n'atteint le corps JSON. Le champ `provider` d'OpenRouter
// ({order, sort, allow_fallbacks, only, ignore}) est donc inatteignable depuis
// settings.yaml. Le suffixe de slug `:floor` est le seul levier natif -- et il ne
// prend PAS le plancher : mesure 2026-08-20 sur deepseek/deepseek-v4-pro
// (18 upstreams), plancher DigitalOcean 0,870 $/M en entree, `:floor` a route sur
// StreamLake 1,044 $/M.
//
// CE QU'IL FAIT
// -------------
// Sur chaque POST /chat/completions il lit le `model`, interroge
// GET /api/v1/models/<slug>/endpoints (public, sans cle), classe les upstreams par
// COUT REEL PONDERE et injecte `provider: {order: [...], allow_fallbacks: true}`.
// Le reste du trafic passe tel quel.
//
// La ponderation compte : un tour d'agent DSH mesure ~8000 tokens d'ENTREE
// (prompt systeme + schemas d'outils) pour ~100 de sortie. Classer sur le prix de
// sortie choisirait le mauvais upstream. D'ou --ratio (defaut 40 = 8000/200).
//
// SECRETS : le proxy ne detient AUCUNE cle. Il relaie l'en-tete Authorization que
// le client envoie, et l'API endpoints qu'il interroge est publique.
//
// USAGE
//   node scripts/openrouter_cheapest_proxy.mjs [--port 8011] [--host 127.0.0.1]
//        [--ratio 40] [--top 3] [--pin "DigitalOcean"] [--ttl 600] [--quiet]
//
//   --pin   epingle un upstream nomme (il reste en tete, fallback autorise)
//   --top   combien d'upstreams dans l'ordre de preference
//   --ttl   duree de cache du tarif, en secondes
//
// Cote DSH, dans ~/.dsh/settings.yaml :
//   openrouter-cheap:
//     apiKeyEnv: OPENROUTER_API_KEY
//     api: openai-completions
//     baseURL: http://127.0.0.1:8011/v1
//     models: [ { id: deepseek/deepseek-v4-pro } ]

import http from 'node:http';
import { Readable } from 'node:stream';

const argv = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : dflt;
};
const has = (name) => argv.includes('--' + name);

const HOST = flag('host', '127.0.0.1');
const PORT = Number(flag('port', '8011'));
const UPSTREAM = flag('upstream', 'https://openrouter.ai/api/v1');
const RATIO = Number(flag('ratio', '40'));
const TOPN = Number(flag('top', '3'));
const PIN = flag('pin', '');
const TTL_MS = Number(flag('ttl', '600')) * 1000;
const QUIET = has('quiet');

const log = (...a) => { if (!QUIET) console.error('[proxy]', ...a); };

// Les en-tetes qu'on relaie. Allowlist plutot que blocklist : `host`,
// `content-length` et `connection` recalcules par fetch feraient echouer la requete.
const FORWARD = ['authorization', 'content-type', 'accept', 'http-referer', 'x-title'];
const STRIP_BACK = ['content-encoding', 'content-length', 'transfer-encoding', 'connection'];

// `deepseek/deepseek-v4-pro:floor` -> `deepseek/deepseek-v4-pro`
// L'API endpoints ne connait que le slug nu, et un suffixe garde en meme temps
// qu'un `provider` explicite ferait cohabiter deux politiques de routage.
const bareSlug = (model) => {
  const i = model.lastIndexOf(':');
  return i > 0 ? model.slice(0, i) : model;
};

const cache = new Map(); // slug -> { at, order, rows }

async function rankUpstreams(model) {
  const slug = bareSlug(model);
  const hit = cache.get(slug);
  if (hit && Date.now() - hit.at < TTL_MS) return hit;

  const r = await fetch(UPSTREAM + '/models/' + slug + '/endpoints');
  if (!r.ok) throw new Error('endpoints HTTP ' + r.status);
  const payload = await r.json();
  const endpoints = (payload.data && payload.data.endpoints) || [];

  const rows = endpoints
    .map((e) => ({
      name: e.provider_name,
      in: Number(e.pricing && e.pricing.prompt),
      out: Number(e.pricing && e.pricing.completion),
    }))
    .filter((x) => x.name && Number.isFinite(x.in) && Number.isFinite(x.out))
    .map((x) => ({ ...x, cost: x.in * RATIO + x.out }))
    .sort((a, b) => a.cost - b.cost);

  if (!rows.length) throw new Error('aucun upstream tarife pour ' + slug);

  let order = rows.slice(0, TOPN).map((x) => x.name);
  if (PIN) order = [PIN, ...order.filter((n) => n !== PIN)].slice(0, Math.max(TOPN, 1));

  const entry = { at: Date.now(), order, rows };
  cache.set(slug, entry);
  log('tarifs ' + slug + ' :', rows.slice(0, TOPN)
    .map((x) => x.name + ' ' + (x.in * 1e6).toFixed(3) + '/' + (x.out * 1e6).toFixed(3) + ' $/M')
    .join('  |  '));
  return entry;
}

const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks);

  const url = req.url || '/';
  const path = url.startsWith('/v1') ? url.slice(3) : url;

  let body = raw;
  let note = 'passthrough';

  const isChat = req.method === 'POST' && path.startsWith('/chat/completions');
  if (isChat && raw.length) {
    try {
      const j = JSON.parse(raw.toString('utf8'));
      if (j.model && !j.provider) {
        const { order } = await rankUpstreams(j.model);
        const asked = j.model;
        j.model = bareSlug(j.model);
        j.provider = { order, allow_fallbacks: true };
        body = Buffer.from(JSON.stringify(j), 'utf8');
        note = asked + ' -> ' + order.join(' > ');
      } else if (j.provider) {
        note = 'provider deja fourni par le client, intact';
      }
    } catch (e) {
      // Un echec d'injection ne doit JAMAIS casser la requete : on transmet
      // l'original et on le dit fort dans le log.
      note = 'INJECTION IGNOREE (' + e.message + ') -- requete transmise telle quelle';
    }
  }

  const headers = {};
  for (const k of FORWARD) if (req.headers[k]) headers[k] = req.headers[k];

  let up;
  try {
    up = await fetch(UPSTREAM + path, {
      method: req.method,
      headers,
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : body,
    });
  } catch (e) {
    log(req.method, path, '-> ECHEC amont:', e.message);
    res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: { message: 'proxy: upstream unreachable: ' + e.message } }));
    return;
  }

  log(req.method, path, '->', up.status, '|', note);

  const out = {};
  up.headers.forEach((v, k) => { if (!STRIP_BACK.includes(k)) out[k] = v; });
  res.writeHead(up.status, out);

  // Pipe sans tampon : le SSE du streaming doit traverser en direct, sinon
  // l'UI DSH reste muette jusqu'a la fin de la generation.
  if (up.body) Readable.fromWeb(up.body).pipe(res);
  else res.end();
});

server.listen(PORT, HOST, () => {
  console.error('openrouter-cheapest-proxy: http://' + HOST + ':' + PORT + '/v1  -> ' + UPSTREAM);
  console.error('  classement: cout = prix_entree * ' + RATIO + ' + prix_sortie   (top ' + TOPN
    + (PIN ? ', epingle "' + PIN + '"' : '') + ', cache ' + TTL_MS / 1000 + ' s)');
});
