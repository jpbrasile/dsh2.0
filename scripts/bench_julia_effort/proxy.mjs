// Proxy enregistreur 8006 -> 8005. Il existe pour une seule raison : prouver
// CE QUI PART SUR LE FIL a chaque niveau d'effort. Un banc qui compare des
// niveaux sans lire la requete compare des etiquettes.
import http from 'node:http';
import fs from 'node:fs';

const UP_HOST = process.env.UP_HOST || '127.0.0.1';
// L'amont est configurable depuis le 22/08 : le meme enregistreur sert le
// llama-server local (8005) ET le routeur FreeLLMAPI (31415). Sans lui,
// `auto` choisit un modele et RIEN ne dit lequel a repondu -- un banc qui
// ne lit pas le fil compare des etiquettes.
const UP_PORT = Number(process.env.UP_PORT || 8005);
const PORT = Number(process.env.PROXY_PORT || 8006);
const LOG = process.env.PROXY_LOG || './wire.jsonl';

const append = (rec) => fs.appendFileSync(LOG, JSON.stringify(rec) + '\n', 'utf8');

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/__mark')) {
    const tag = new URL(req.url, 'http://x').searchParams.get('tag') || '';
    append({ kind: 'mark', tag, t: Date.now() });
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
    if (req.method === 'POST' && req.url.includes('chat/completions')) {
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
        };
      } catch (e) { sent = { parse_error: String(e) }; }
    }
    const up = http.request({
      host: UP_HOST, port: UP_PORT, path: req.url, method: req.method,
      headers: { ...req.headers, host: `${UP_HOST}:${UP_PORT}` },
    }, (ur) => {
      res.writeHead(ur.statusCode, ur.headers);
      const out = [];
      ur.on('data', (c) => { out.push(c); res.write(c); });
      ur.on('end', () => {
        res.end();
        if (!sent) return;
        const raw = Buffer.concat(out).toString('utf8');
        const rec = { kind: 'call', t0, ms: Date.now() - t0, status: ur.statusCode, sent };
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
server.listen(PORT, '127.0.0.1', () => console.error(`proxy ${PORT} -> ${UP_HOST}:${UP_PORT}, log=${LOG}`));
