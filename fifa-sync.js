// Sincronización con FIFA desde el SERVIDOR (Felipe, 25/11/2026: «pasá la sincronización al servidor»).
// Hasta ahora el partido se completaba solo desde una pestaña abierta de la app; si nadie la miraba, quedaba a medias (Sub-17 vs. Francia: sin cambios ni confirmación).
// Acá el server consulta la API oficial de FIFA durante la ventana de cada partido de Uruguay y escribe en Supabase lo MISMO que escribe la app
// (marcador final, goles con minuto, tarjetas e ingresos con `fifa:true`, penales del rival). Es un puerto de `autoPizarra` de public/index.html (mismos nombres y mismas reglas).
// NO toca lo cargado a mano (items sin `fifa:true`), ni la corroboración (`fifaChk`) ni la confirmación automática: eso lo sigue haciendo la app al abrirse.
// Si algún jugador de FIFA no se puede ubicar en la lista de convocados, no escribe nada en ese ciclo (lo resuelve la app).
'use strict';

const https = require('https');
const fs = require('fs');
const path = require('path');

// Torneos que se sincronizan (misma info que _MUND_CFG de index.html). Para sumar otro torneo juvenil, agregar una fila.
const TORNEOS = [
  { cid: 'wc17-2026', comp: 102, season: 292937, cat: 'sub17', year: '2025-2026', constName: 'WC17_2026' },
];

// ── Núcleo puro (se prueba sin red) ─────────────────────────────────────────
const nt = s => String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().split(/[^a-z]+/).filter(Boolean);
const mn = x => { const t = String(x == null ? '' : x).replace(/['\s]/g, ''); return t || null; };
const pn = x => { const n = parseInt(String(x || '').replace(/[^0-9]/g, ' ').trim().split(/\s+/)[0], 10); return isNaN(n) ? null : n; };
const nomF = p => (p ? ((p.PlayerName || [{}])[0] || {}).Description || '' : '');

// Lista de convocados de la app (nombres como los escribe Felipe), leída de public/index.html: const <constName> = { ... convocados:[ {nom:'…'}, … ] }
function parsePool(html, constName) {
  const i = html.indexOf('const ' + constName);
  if (i < 0) return [];
  const j = html.indexOf('convocados:[', i);
  if (j < 0) return [];
  let depth = 0, k = j + 'convocados:'.length, end = -1;
  for (; k < html.length; k++) {
    const c = html[k];
    if (c === '[') depth++;
    else if (c === ']') { depth--; if (depth === 0) { end = k; break; } }
  }
  if (end < 0) return [];
  const block = html.slice(j, end);
  const out = [], re = /\bnom\s*:\s*(?:'([^']+)'|"([^"]+)")/g;
  let m;
  while ((m = re.exec(block))) out.push(m[1] || m[2]);
  return [...new Set(out)];
}

function buildFrom(j, pool) {
  const uH = j.HomeTeam.IdCountry === 'URU';
  const U = uH ? j.HomeTeam : j.AwayTeam, R = uH ? j.AwayTeam : j.HomeTeam;
  const sc = x => (x && x.Score != null ? +x.Score : 0);
  const toApp = fn => {
    const T = nt(fn); if (!T.length) return null;
    const h = pool.filter(n => { const A = nt(n); return T.every(t => A.includes(t)); });
    return h.length ? h.sort((a, b) => nt(a).length - nt(b).length)[0] : null;
  };
  const byId = {}; (U.Players || []).forEach(p => { byId[String(p.IdPlayer)] = p; });
  const sinUbicar = [];
  const nomApp = id => {
    const p = byId[String(id)]; const a = p ? toApp(nomF(p)) : null;
    if (p && !a && !sinUbicar.includes(nomF(p))) sinUbicar.push(nomF(p));
    return a;
  };
  const goals = (U.Goals || []).map(g => ({ nom: byId[String(g.IdPlayer)] ? nomApp(g.IdPlayer) : '__EC__', min: mn(g.Minute), ast: g.IdAssistPlayer ? nomApp(g.IdAssistPlayer) : null })).filter(g => g.nom);
  const cards = (U.Bookings || []).map(b => ({ nom: nomApp(b.IdPlayer), min: mn(b.Minute) || '', col: b.Card === 1 ? 'a' : b.Card === 3 ? 'da' : 'r' })).filter(c => c.nom);
  const subs = (U.Substitutions || []).map(x => ({ nom: nomApp(x.IdPlayerOn), por: nomApp(x.IdPlayerOff), min: mn(x.Minute) })).filter(x => x.nom);
  const fin = !!j.Winner || j.MatchStatus === 0;
  const penRival = R && Array.isArray(R.Goals) ? R.Goals.filter(g => g && g.Type === 1).length : null;
  return { goals, cards, subs, fin, gl: sc(U), gr: sc(R), penRival, sinUbicar, uH };
}

// Aplica al partido (objeto de la lista de la app) lo que dice FIFA. Devuelve true si cambió algo. Mismas reglas que `apply` de autoPizarra.
function applyToMatch(mm, b) {
  const antes = JSON.stringify(mm);
  if (mm.fifaAuto && !mm.fifaV2) ['golMins', 'tarjetas', 'subs'].forEach(k => (mm[k] || []).forEach(x => { x.fifa = true; }));
  mm.fifaV2 = true;
  const sg = x => [x.nom, String(x.min || ''), x.ast || '', x.col || '', x.por || ''].join('|');
  const sync = (arr, want, onDel, onAdd) => {
    const cur = arr.filter(x => x.fifa);
    if (cur.map(sg).sort().join('#') === want.map(sg).sort().join('#')) return;
    for (let q = arr.length - 1; q >= 0; q--) if (arr[q].fifa) { if (onDel) onDel(arr[q]); arr.splice(q, 1); }
    want.forEach(d => { arr.push(Object.assign({}, d, { fifa: true })); if (onAdd) onAdd(d); });
  };
  // goles
  const gl = mm.goles || (mm.goles = {}), gm = mm.golMins || (mm.golMins = []);
  const man = gm.filter(x => !x.fifa).map(x => ({ x, used: false })), wantG = [];
  b.goals.forEach(g => {
    const k = man.find(o => !o.used && o.x.nom === g.nom && (!o.x.min || pn(o.x.min) === pn(g.min)));
    if (k) { k.used = true; if (!k.x.min && g.min) k.x.min = g.min; }
    else wantG.push(g.ast ? { nom: g.nom, min: g.min, ast: g.ast } : { nom: g.nom, min: g.min });
  });
  sync(gm, wantG, x => { gl[x.nom] = (gl[x.nom] || 1) - 1; if (gl[x.nom] <= 0) delete gl[x.nom]; }, d => { gl[d.nom] = (gl[d.nom] || 0) + 1; });
  // tarjetas
  const tj = mm.tarjetas || (mm.tarjetas = []), manT = tj.filter(x => !x.fifa).map(x => ({ x, used: false })), wantT = [];
  b.cards.forEach(c => { const k = manT.find(o => !o.used && o.x.nom === c.nom && o.x.col === c.col); if (k) k.used = true; else wantT.push({ nom: c.nom, min: c.min, col: c.col }); });
  sync(tj, wantT);
  // ingresos / cambios
  const sb = mm.subs || (mm.subs = []), manS = new Set(sb.filter(x => !x.fifa).map(x => x.nom));
  sync(sb, b.subs.filter(x => !manS.has(x.nom)).map(x => x.por ? { nom: x.nom, min: x.min, por: x.por } : { nom: x.nom, min: x.min }));
  // resultado final: solo si el partido todavía no tiene marcador cargado
  if (b.fin && mm.gLocal == null && mm.gRival == null) { mm.gLocal = b.gl; mm.gRival = b.gr; }
  mm.fifaAuto = true;
  if (b.penRival != null) mm.fifaPenRival = b.penRival;
  return JSON.stringify(mm) !== antes;
}

// ── Red y programación ──────────────────────────────────────────────────────
function getJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' }, timeout: 20000 }, r => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => { if (r.statusCode >= 400) return reject(new Error('HTTP ' + r.statusCode + ' ' + url)); try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    });
    req.on('timeout', () => req.destroy(new Error('timeout ' + url)));
    req.on('error', reject);
  });
}

function start(opts) {
  const { sbUrl, sbKey } = opts;
  const sb = (method, pathq, body, prefer) => new Promise((resolve, reject) => {
    const url = new URL(sbUrl + pathq), payload = body != null ? JSON.stringify(body) : null;
    const headers = { apikey: sbKey, Authorization: 'Bearer ' + sbKey, 'Content-Type': 'application/json' };
    if (prefer) headers.Prefer = prefer;
    if (payload) headers['Content-Length'] = Buffer.byteLength(payload);
    const req = https.request(url, { method, headers, timeout: 20000 }, r => {
      let d = ''; r.on('data', c => d += c);
      r.on('end', () => r.statusCode >= 400 ? reject(new Error('Supabase ' + method + ' ' + r.statusCode + ' ' + d)) : resolve(d));
    });
    req.on('timeout', () => req.destroy(new Error('timeout supabase')));
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });

  const estado = {};   // cid → { matches:[{id,stage,date,status}], calAt, hash:{id:str}, finalHecho:{id:true} }
  const poolCache = {};
  const loadPool = t => {
    if (poolCache[t.cid] && Date.now() - poolCache[t.cid].at < 10 * 60000) return poolCache[t.cid].v;
    let v = [];
    try { v = parsePool(fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8'), t.constName); } catch (e) { console.warn('[fifa-sync] no pude leer la lista de convocados:', e.message); }
    poolCache[t.cid] = { at: Date.now(), v };
    return v;
  };

  async function refrescarCalendario(t, st) {
    const j = await getJson(`https://api.fifa.com/api/v3/calendar/matches?idSeason=${t.season}&count=200&language=es`);
    st.matches = (j.Results || []).filter(m => (m.Home && m.Home.IdCountry === 'URU') || (m.Away && m.Away.IdCountry === 'URU'))
      .map(m => ({ id: String(m.IdMatch), comp: m.IdCompetition, stage: m.IdStage, date: new Date(m.Date).getTime(), status: m.MatchStatus }));
    st.calAt = Date.now();
  }

  async function tickTorneo(t) {
    const st = estado[t.cid] || (estado[t.cid] = { matches: [], calAt: 0, hash: {}, finalHecho: {} });
    if (Date.now() - st.calAt > 15 * 60000) await refrescarCalendario(t, st);
    const ahora = Date.now();
    for (const m of st.matches) {
      // ventana: desde 10 min antes hasta 3 h 30 después del comienzo; terminado y ya aplicado: no se vuelve a consultar
      if (ahora < m.date - 10 * 60000 || ahora > m.date + 210 * 60000 || st.finalHecho[m.id]) continue;
      const live = await getJson(`https://api.fifa.com/api/v3/live/football/${m.comp}/${t.season}/${m.stage}/${m.id}?language=es`);
      if (!live || !live.HomeTeam) continue;
      const pool = loadPool(t);
      if (!pool.length) { console.warn('[fifa-sync] lista de convocados vacía'); continue; }
      const b = buildFrom(live, pool);
      if (b.sinUbicar.length) { console.warn('[fifa-sync] no pude ubicar en la lista a: ' + b.sinUbicar.join(', ') + ' — lo resuelve la app'); continue; }
      const h = JSON.stringify([b.gl, b.gr, b.fin, b.goals, b.cards, b.subs, b.penRival]);
      if (st.hash[m.id] === h) { if (b.fin) st.finalHecho[m.id] = true; continue; }
      const key = `auf4_amist_juv_${t.cat}_${t.year}`;
      const rows = JSON.parse(await sb('GET', `/rest/v1/sync_data?key=eq.${key}&select=value`));
      if (!rows.length) continue;
      const list = JSON.parse(rows[0].value);
      const mm = Array.isArray(list) ? list.find(x => x.compId === t.cid && String(x.fifaId || '') === m.id) : null;
      if (!mm) { st.hash[m.id] = h; continue; } // el partido todavía no está en la lista: lo crea la app
      if (applyToMatch(mm, b)) {
        await sb('POST', '/rest/v1/sync_data?on_conflict=key', [{ key, value: JSON.stringify(list), updated_at: new Date().toISOString() }], 'resolution=merge-duplicates,return=minimal');
        console.log(`[fifa-sync] ${t.cid} ${m.id}: ${b.gl}-${b.gr}${b.fin ? ' (final)' : ''} · ${b.subs.length} cambios · ${b.goals.length} goles · ${b.cards.length} tarjetas`);
      }
      st.hash[m.id] = h;
      if (b.fin) st.finalHecho[m.id] = true;
    }
  }

  let corriendo = false;
  const tick = async () => {
    if (corriendo) return; corriendo = true;
    try { for (const t of TORNEOS) { try { await tickTorneo(t); } catch (e) { console.warn('[fifa-sync] ' + t.cid + ':', e.message); } } }
    finally { corriendo = false; }
  };
  setTimeout(tick, 20000);
  setInterval(tick, 60000);
  console.log('[fifa-sync] activo para: ' + TORNEOS.map(t => t.cid).join(', '));
}

module.exports = { start, parsePool, buildFrom, applyToMatch, nt, TORNEOS };
