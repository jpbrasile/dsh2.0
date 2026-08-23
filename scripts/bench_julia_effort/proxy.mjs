// Proxy enregistreur 8006 -> 8005. Il existe pour une seule raison : prouver
// CE QUI PART SUR LE FIL a chaque niveau d'effort. Un banc qui compare des
// niveaux sans lire la requete compare des etiquettes.
import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';

// Amont EN TLS (UP_TLS=1) : l'enregistreur sert aussi une dorsale distante,
// OpenRouter. Sans ca, le seul moyen d'utiliser un modele hors du routeur
// local serait de l'appeler en direct -- et une campagne en direct ne peut pas
// prouver QUI a repondu ni si une bascule a eu lieu. Le port amont vaut alors
// 443 par defaut, et `servername` doit etre pose : sans SNI, un hote mutualise
// presente le mauvais certificat et la poignee de main echoue.
const UP_TLS = process.env.UP_TLS === '1';

const UP_HOST = process.env.UP_HOST || '127.0.0.1';
// L'amont est configurable depuis le 22/08 : le meme enregistreur sert le
// llama-server local (8005) ET le routeur FreeLLMAPI (31415). Sans lui,
// `auto` choisit un modele et RIEN ne dit lequel a repondu -- un banc qui
// ne lit pas le fil compare des etiquettes.
const UP_PORT = Number(process.env.UP_PORT || (UP_TLS ? 443 : 8005));
const PORT = Number(process.env.PROXY_PORT || 8006);
const LOG = process.env.PROXY_LOG || './wire.jsonl';

const append = (rec) => fs.appendFileSync(LOG, JSON.stringify(rec) + '\n', 'utf8');

// VOIES. En campagne parallele, N agents parlent au MEME routeur en meme
// temps : les fenetres de temps se chevauchent, et attribuer un appel a un run
// par son horodatage devient faux sans en avoir l'air. Chaque ouvrier appelle
// donc sa propre voie -- baseURL .../wK/v1 -- et l'enregistreur note K avant de
// retirer le prefixe. L'attribution est alors exacte par CONSTRUCTION, pas par
// coincidence temporelle. Un seul processus proxy suffit pour N ouvriers.
// PROXY_SLOT, et pas seulement un prefixe d'URL : mesure du 22/08, le client
// dsh NORMALISE la baseURL et jette le chemin. Les 47 appels d'un essai a
// trois ouvriers sont tous arrives sans voie -- attribution perdue en silence,
// avec un proxy pourtant correct (le meme prefixe passe en curl). Le seul
// discriminant qu'un client ne peut pas normaliser est le PORT : un
// enregistreur par ouvrier, et l'appartenance devient vraie par construction.
// Le prefixe reste accepte : il sert aux marques, posees par le banc lui-meme.
const SLOT = process.env.PROXY_SLOT === undefined ? null : Number(process.env.PROXY_SLOT);
const voie = (u) => {
  const m = /^\/w([0-9]+)(\/.*)$/.exec(u);
  return m ? { slot: Number(m[1]), url: m[2] } : { slot: SLOT, url: u };
};

const server = http.createServer((req, res) => {
  const { slot, url } = voie(req.url);
  if (url.startsWith('/__mark')) {
    const tag = new URL(url, 'http://x').searchParams.get('tag') || '';
    append({ kind: 'mark', tag, slot, t: Date.now() });
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok\n');
    return;
  }
  const chunks = [];
  req.on('data', (c) => chunks.push(c));
  req.on('end', () => {
    const body = Buffer.concat(chunks);
    const t0 = Date.now();
    let sent = null;
    if (req.method === 'POST' && url.includes('chat/completions')) {
      try {
        const p = JSON.parse(body.toString('utf8'));
        sent = {
          model: p.model,
          n_messages: Array.isArray(p.messages) ? p.messages.length : null,
          n_tools: Array.isArray(p.tools) ? p.tools.length : 0,
          stream: !!p.stream,
          temperature: p.temperature,
          max_tokens: p.max_tokens ?? p.max_completion_tokens,
          reasoning_effort: p.reasoning_effort,
          enable_thinking: p.enable_thinking,
          chat_template_kwargs: p.chat_template_kwargs,
          thinking: p.thinking,
          // 23/08, phase 0 : les NOMS des outils offerts et la taille du prompt
          // systeme -- c'est ce que le preset Lean doit faire bouger, et seul le
          // fil peut le dire (un --dump-config prouve la composition, pas ce que
          // le modele recoit).
          tools: Array.isArray(p.tools) ? p.tools.map((t) => (t && t.function && t.function.name) || (t && t.name) || '?') : [],
          sys_chars: Array.isArray(p.messages)
            ? p.messages.filter((m) => m && (m.role === 'system' || m.role === 'developer'))
                .reduce((n, m) => n + (typeof m.content === 'string' ? m.content.length
                  : Array.isArray(m.content) ? m.content.reduce((k, b) => k + ((b && b.text) ? b.text.length : 0), 0) : 0), 0)
            : null,
          roles: Array.isArray(p.messages) ? p.messages.slice(0, 3).map((m) => (m && m.role) || '?') : null,
        };
      } catch (e) { sent = { parse_error: String(e) }; }
    }
    const opts = {
      host: UP_HOST, port: UP_PORT, path: url, method: req.method,
      headers: { ...req.headers, host: UP_HOST },
    };
    if (UP_TLS) opts.servername = UP_HOST;
    const up = (UP_TLS ? https : http).request(opts, (ur) => {
      res.writeHead(ur.statusCode, ur.headers);
      const out = [];
      ur.on('data', (c) => { out.push(c); res.write(c); });
      ur.on('end', () => {
        res.end();
        if (!sent) return;
        const raw = Buffer.concat(out).toString('utf8');
        // `slot` sur l'APPEL, pas seulement sur la marque : sans lui le
        // filtre par ouvrier rejetait tout et `servis` sortait vide alors que
        // le journal contenait bien les modeles. Mesure du 22/08.
        const rec = { kind: 'call', slot, t0, ms: Date.now() - t0, status: ur.statusCode, sent };
        // `sent.model` est ce qu'on a DEMANDE ('auto') ; `servi` est ce qui a
        // REPONDU. Les deux differents, c'est tout l'interet du mode auto.
        // Le modele servi est sur CHAQUE fragment SSE, pas seulement sur celui
        // qui porte `usage`. Mesure 22/08 : en s'appuyant sur `usage`, 4 appels
        // sur 24 seulement etaient attribues -- le flux de ce routeur ne le
        // renvoie presque jamais. On lit donc le PREMIER fragment qui nomme un
        // modele, et l'attribution passe a 24 sur 24.
        if (sent.stream) {
          for (const l of raw.split(String.fromCharCode(10))) {
            if (!l.startsWith('data: ') || l.includes('[DONE]')) continue;
            let o = null; try { o = JSON.parse(l.slice(6)); } catch (e) { o = null; }
            if (o && o.model) { rec.servi = o.model; break; }
          }
        }
        const trail = ur.headers['x-fallback-trail'];
        if (trail) rec.bascule = String(trail);
        // usage/timings : soit dans un JSON simple, soit dans le dernier chunk SSE.
        const grab = (txt) => { try { return JSON.parse(txt); } catch { return null; } };
        let last = grab(raw);
        if (!last && sent.stream) {
          const lines = raw.split('\n').filter((l) => l.startsWith('data: ') && !l.includes('[DONE]'));
          for (let i = lines.length - 1; i >= 0; i--) {
            const o = grab(lines[i].slice(6));
            if (o && (o.usage || o.timings)) { last = o; break; }
          }
        }
        if (last) {
          if (last.model) rec.servi = last.model;
          if (last.usage) rec.usage = last.usage;
          if (last.timings) rec.timings = last.timings;
          if (last.error) rec.error = last.error;
        } else if (ur.statusCode >= 400) {
          rec.error_raw = raw.slice(0, 600);
        }
        append(rec);
      });
    });
    up.on('error', (e) => {
      append({ kind: 'upstream_error', t0, err: String(e), sent });
      if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e) }));
    });
    up.end(body);
  });
});
server.listen(PORT, '127.0.0.1', () => console.error(`proxy ${PORT} -> ${UP_TLS ? 'https' : 'http'}://${UP_HOST}:${UP_PORT}, log=${LOG}`));
