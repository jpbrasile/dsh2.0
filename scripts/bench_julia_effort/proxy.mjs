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
// GUETTEUR (23/08, phase 0) : des chaines a chercher dans le CORPS de chaque
// requete (separees par `|`). Si l'une y est, l'appel la nomme dans `guette`.
// C'est la preuve, ou la refutation, qu'un secret plante ou un contenu interdit
// est parti vers le fournisseur -- sans stocker le corps lui-meme.
const GUETTE = (process.env.PROXY_GUETTE || '').split('|').filter(Boolean);

// INJECTION D'ECHANTILLONNAGE (26/08, banc polyglot).
//
// POURQUOI. Mesure au serveur temoin : NI dsh NI pi n'envoient temperature,
// top_p, top_k ou min_p. Les deux heritent du defaut de l'amont OpenRouter,
// inconnu, non journalise, et susceptible de changer si le routeur bascule
// d'amont. pi sait poser un `samplingParams` (verifie sur le fil) ; dsh n'a
// AUCUNE voie de configuration -- sa doc amont le confirme, l'echantillonnage
// arrive par `GenerateOptions` a l'appel, et aucun paquet dsh ne le remplit.
// Regler pi seul casserait la seule propriete propre etablie : les deux agents
// emettent aujourd'hui des corps identiques au champ pres, donc leur
// comparaison est equitable. La correction doit etre EXTERIEURE aux deux et
// identique pour eux : c'est ici.
//
// PROXY_INJECT = objet JSON des champs a POSER dans chaque corps
// chat/completions. Absent ou vide : comportement inchange, octet pour octet.
// Ce fichier sert aussi le banc julia -- l'injection ne doit rien lui changer.
//
// ON ECRASE, ET ON LE DIT. N'injecter que les champs manquants rendrait
// l'echantillonnage dependant de l'agent (pi pose, dsh non) et recreerait
// l'asymetrie qu'on ferme. Tout ecrasement est NOMME dans le journal, cle par
// cle : jamais de correction silencieuse. C'est exactement le defaut qu'on
// vient de trouver chez dsh, qui jette une cle de configuration inconnue sans
// un mot -- un fichier qui a l'air regle et une requete qui ne l'est pas.
//
// UN JSON ILLISIBLE ARRETE LE PROXY. Demarrer sans injecter alors qu'on l'a
// demandee produirait un run entier au mauvais reglage, avec un proxy qui a
// l'air en place.
const INJECT = (() => {
  const s = (process.env.PROXY_INJECT || '').trim();
  if (!s) return null;
  let o;
  try { o = JSON.parse(s); } catch (e) {
    console.error(`PROXY_INJECT illisible, ARRET : ${e}`); process.exit(2);
  }
  if (!o || typeof o !== 'object' || Array.isArray(o) || !Object.keys(o).length) {
    console.error('PROXY_INJECT doit etre un objet JSON non vide, ARRET.');
    process.exit(2);
  }
  return o;
})();

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
    // Le corps SORTANT peut differer du corps recu (voir INJECT). `sent` est
    // construit APRES l'injection : ce journal decrit ce qui PART, jamais ce
    // qui est arrive -- c'est la raison d'etre de ce proxy. Ce que l'agent
    // avait mis, quand ca differe, est dans `ecrase`.
    let corpsSortant = body;
    let injecte = null, ecrase = null;
    if (req.method === 'POST' && url.includes('chat/completions')) {
      try {
        const p = JSON.parse(body.toString('utf8'));
        if (INJECT) {
          injecte = {}; ecrase = {};
          for (const [k, v] of Object.entries(INJECT)) {
            // `k in p` et non `p[k] !== undefined` : un agent qui pose
            // explicitement `temperature: null` a bien pose la cle, et
            // l'ecraser doit se voir.
            if (k in p && JSON.stringify(p[k]) !== JSON.stringify(v)) ecrase[k] = p[k];
            p[k] = v;
            injecte[k] = v;
          }
          if (!Object.keys(ecrase).length) ecrase = null;
          corpsSortant = Buffer.from(JSON.stringify(p), 'utf8');
        }
    // --- sonde de prefixe (26/08) : ou le cache meurt-il ? -------------
    // Empreinte FNV-1a 32 bits, cumulee message par message. On ne stocke
    // AUCUN contenu, seulement des longueurs et des empreintes.
    const _fnv = (s) => {
      let h = 0x811c9dc5;
      for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
      }
      return h.toString(16).padStart(8, '0');
    };
    const _texte = (m) => {
      if (!m) return '';
      const c = m.content;
      if (typeof c === 'string') return c;
      if (Array.isArray(c)) return c.map((b) => (b && b.text) || '').join('');
      return '';
    };
        sent = {
          model: p.model,
          n_messages: Array.isArray(p.messages) ? p.messages.length : null,
          n_tools: Array.isArray(p.tools) ? p.tools.length : 0,
          stream: !!p.stream,
          temperature: p.temperature,
          // Les quatre champs d'echantillonnage sont journalises ENSEMBLE :
          // une temperature seule ne decrit pas un decodage.
          top_p: p.top_p,
          top_k: p.top_k,
          min_p: p.min_p,
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
          roles: Array.isArray(p.messages) ? p.messages.slice(0, 300).map((m) => (m && m.role) || '?') : null,
          msg_chars: Array.isArray(p.messages) ? p.messages.slice(0, 300).map((m) => _texte(m).length) : null,
          // Empreinte du prefixe APRES chaque message : le premier indice ou
          // deux appels successifs divergent est l'endroit ou le cache meurt.
          // On seme avec le prompt systeme ET la liste d'outils, qui precedent
          // les messages dans le prompt reellement servi.
          prefix_h: Array.isArray(p.messages) ? (() => {
            let acc = _fnv(JSON.stringify(p.tools || []));
            const out = [acc];
            for (const m of p.messages.slice(0, 300)) {
              acc = _fnv(acc + '|' + ((m && m.role) || '?') + '|' + _texte(m));
              out.push(acc);
            }
            return out;
          })() : null,
        };
      } catch (e) { sent = { parse_error: String(e) }; }
    }
    const enTetes = { ...req.headers, host: UP_HOST };
    // LE PIEGE DE L'INJECTION. Le corps a change de TAILLE ; le `content-length`
    // recopie du client vaut alors pour l'ancien. Trop petit, l'amont lit un
    // JSON tronque et rend 400 ; trop grand, il attend des octets qui ne
    // viennent jamais et l'appel pend jusqu'au delai. On le recalcule, et on
    // retire `transfer-encoding` : les deux ensemble sont invalides et
    // certains amonts choisissent le mauvais.
    if (corpsSortant !== body) {
      delete enTetes['transfer-encoding'];
      enTetes['content-length'] = String(corpsSortant.length);
    }
    const opts = {
      host: UP_HOST, port: UP_PORT, path: url, method: req.method,
      headers: enTetes,
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
        // `injecte` sur CHAQUE appel, pas seulement au demarrage : un run se
        // relit par son journal, et « le proxy etait lance » n'est pas une
        // preuve que la requete n° 812 portait le reglage.
        if (injecte) rec.injecte = injecte;
        if (ecrase) rec.ecrase = ecrase;
        if (GUETTE.length) {
          const corps = corpsSortant.toString('utf8');
          rec.guette = GUETTE.filter((g) => corps.includes(g));
        }
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
            if (o && o.provider && !rec.fournisseur) rec.fournisseur = o.provider;
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
          if (last.provider) rec.fournisseur = last.provider;
          if (last.model) rec.servi = last.model;
          if (last.usage) rec.usage = last.usage;
          if (last.timings) rec.timings = last.timings;
          // POURQUOI LA RAISON D'ARRET (26/08, apres le bras Venice). Ce bras
          // s'est arrete au 8e appel en 187 s, et la paroi seule le faisait
          // passer pour 7x plus rapide que la reference. Le fil disait autre
          // chose : le dernier appel avait rendu 16 384 jetons, c'est-a-dire le
          // PLAFOND, et le tour etait mort dessus. Sans ce champ, la difference
          // entre « a fini » et « a ete coupe » se deduit d'une egalite entre
          // deux nombres -- une deduction, la ou une declaration existe.
          const ch = (last.choices || [])[0];
          if (ch && ch.finish_reason) rec.fin_raison = ch.finish_reason;
          // En flux, le fragment qui porte `usage` a souvent `choices: []` :
          // la raison d'arret est sur un fragment ANTERIEUR. La chercher a
          // rebours, sinon un bras coupe au plafond passe pour un bras fini.
          if (!rec.fin_raison && sent.stream) {
            const lg = raw.split(String.fromCharCode(10));
            for (let i = lg.length - 1; i >= 0 && !rec.fin_raison; i--) {
              if (!lg[i].startsWith('data: ') || lg[i].includes('[DONE]')) continue;
              let o = null; try { o = JSON.parse(lg[i].slice(6)); } catch (e) { continue; }
              const c0 = (o.choices || [])[0];
              if (c0 && c0.finish_reason) rec.fin_raison = c0.finish_reason;
            }
          }
          // PENSEE CONTRE VISIBLE, MESUREE ICI ET PAS DEDUITE (26/08 20:05).
          // J'ai ecrit dans le carnet que la separation pensee/visible
          // « n'existe pas en local ». FAUX. `--reasoning-format none` ne
          // supprime rien -- l'aide du binaire le dit : « leaves thoughts
          // unparsed in message.content ». La pensee est donc LA, entre
          // <think> et </think> ; ce qui manque est un compteur pre-calcule
          // dans `usage`, pas l'information. C'etait un trou de MON
          // instrument, lu comme une limite de la pile locale.
          //
          // On ne stocke que des LONGUEURS, jamais le texte -- meme regle que
          // la sonde de prefixe. Et on ne touche pas au serveur : basculer en
          // `--reasoning-format deepseek` sortirait la pensee de `content` et
          // casserait le parseur du banc GPQA (`pensee_de()`), qui tourne.
          //
          // `reasoning_content` est lu AUSSI : si un amont separe deja la
          // pensee, elle ne doit pas compter pour zero.
          // EN FLUX, `message` N'EXISTE PAS. Constate le 26/08 a 20:10 : dsh
          // appelle avec `stream: true`, le contenu arrive en `delta` fragment
          // par fragment, et le dernier fragment ne porte que `usage`. Une
          // premiere version de ce compteur lisait `choices[0].message` et ne
          // s'est jamais declenchee -- un instrument muet qui a l'air pose.
          // On reconstitue donc le texte a partir des `delta`, on le mesure, et
          // on ne le garde pas.
          let txt = '', rc = '';
          const msg = (ch && ch.message) || {};
          if (typeof msg.content === 'string') txt = msg.content;
          if (typeof msg.reasoning_content === 'string') rc = msg.reasoning_content;
          if (!txt && !rc && sent.stream) {
            for (const l of raw.split(String.fromCharCode(10))) {
              if (!l.startsWith('data: ') || l.includes('[DONE]')) continue;
              let o = null; try { o = JSON.parse(l.slice(6)); } catch (e) { continue; }
              const d = ((o.choices || [])[0] || {}).delta || {};
              if (typeof d.content === 'string') txt += d.content;
              if (typeof d.reasoning_content === 'string') rc += d.reasoning_content;
            }
          }
          if (txt || rc) {
            const i = txt.indexOf('<think>');
            const j = txt.indexOf('</think>');
            // j sans i : l'ouverture peut manquer si l'amont l'a rognee.
            const dedans = j >= 0 ? txt.slice(i >= 0 ? i + 7 : 0, j).length : 0;
            rec.pensee_car = dedans + rc.length;
            rec.visible_car = j >= 0 ? txt.length - j - 8 - (i >= 0 ? i + 7 : 0)
                                     : txt.length;
          }
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
    up.end(corpsSortant);
  });
});
server.listen(PORT, '127.0.0.1', () => {
  console.error(`proxy ${PORT} -> ${UP_TLS ? 'https' : 'http'}://${UP_HOST}:${UP_PORT}, log=${LOG}`);
  // La ligne d'injection est ECRITE AU DEMARRAGE : sans elle, deux runs
  // separes par un redemarrage se ressemblent dans la console et pas sur le
  // fil. Le journal reste la preuve appel par appel.
  console.error(INJECT ? `injection : ${JSON.stringify(INJECT)}`
                       : 'injection : AUCUNE (comportement d\'origine)');
});
