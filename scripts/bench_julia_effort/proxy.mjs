// Proxy enregistreur 8006 -> 8005. Il existe pour une seule raison : prouver
// CE QUI PART SUR LE FIL a chaque niveau d'effort. Un banc qui compare des
// niveaux sans lire la requete compare des etiquettes.
import http from 'node:http';
import fs from 'node:fs';

const UP_HOST = '127.0.0.1';
const UP_PORT = 8005;
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
server.listen(PORT, UP_HOST, () => console.error(`proxy 8006 -> ${UP_PORT}, log=${LOG}`));
