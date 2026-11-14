# Corrobora un partido de la Fecha FIFA nov cargado en la Pizarra contra una fuente externa y guarda el estado en `auf4_fifanov_corrob`.
# Uso: python3 -I scripts/corroborar_partido.py RIVAL liviana|auf FUENTE externo.json [--dry]
#   liviana = ESPN / FotMob / Google (el mismo día) · auf = auf.org.uy (el día siguiente, dato oficial)
# externo.json: {"marcador":[uruguay,rival], "titulares":["Nombre",...], "ingresos":[{"nom":"..","min":58}], "salidas":[{"nom":"..","min":58}],
#                "tarjetas":[{"nom":"..","col":"a|da|r","min":60}], "goles":[{"nom":"..","min":53}], "en_contra":[47]}
# Se compara lo grueso (titulares, ingresos, salidas, tarjetas, autores de goles). Diferencias de hasta 2 minutos NO cuentan; mayores van como observación.
# Los nombres pueden venir solo con apellido: se resuelven contra los de la Pizarra (sin tildes; si hay dos apellidos iguales hace falta nombre o inicial).
import sys, json, subprocess, unicodedata, datetime, urllib.parse
U = 'https://wsiudiexcodrhyejevco.supabase.co/rest/v1/sync_data'
K = 'sb_publishable_GaiAMaH49DGCJgzDOTKHSQ_42jKWXNq'
H = ['-H', 'apikey: ' + K, '-H', 'Authorization: Bearer ' + K]
TOL = 2

def get(key):
    r = subprocess.run(['curl', '-s'] + H + [U + '?select=value&key=eq.' + urllib.parse.quote(key)], capture_output=True, text=True)
    rows = json.loads(r.stdout)
    return json.loads(rows[0]['value']) if rows else None

def put(key, val):
    body = json.dumps([{'key': key, 'value': json.dumps(val, ensure_ascii=False, separators=(',', ':')), 'updated_at': datetime.datetime.utcnow().isoformat() + '+00:00'}], ensure_ascii=False)
    r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-X', 'POST'] + H + ['-H', 'Content-Type: application/json', '-H', 'Prefer: resolution=merge-duplicates', U + '?on_conflict=key', '--data-binary', body], capture_output=True, text=True)
    return r.stdout

def norm(x):
    x = unicodedata.normalize('NFD', str(x)).encode('ascii', 'ignore').decode().lower()
    return ''.join(c if c.isalnum() else ' ' for c in x).split()

def resolver(nom, pool):
    """Devuelve el nombre de la Pizarra que corresponde a `nom` (puede venir solo con apellido o con inicial)."""
    t = norm(nom)
    if not t: return None
    cand = [p for p in pool if norm(p) == t]
    if not cand:
        cand = [p for p in pool if set(t) <= set(norm(p))]
    if not cand and len(t) >= 2 and len(t[0]) == 1:  # «M. Araujo»
        cand = [p for p in pool if norm(p)[0].startswith(t[0]) and set(t[1:]) <= set(norm(p))]
    if not cand:
        cand = [p for p in pool if t[-1] in norm(p)]
    return cand[0] if len(cand) == 1 else (None if not cand else ('?' + '|'.join(cand)))

def main():
    if len(sys.argv) < 5: print(__doc__); sys.exit(1)
    rival, nivel, fuente, path = sys.argv[1:5]; dry = '--dry' in sys.argv
    ext = json.load(open(path, encoding='utf-8'))
    ms = get('auf4_amist_juv_fifamayor_nov26') or []
    m = next((x for x in ms if x.get('rival') == rival), None)
    if not m: print('No encuentro el partido', rival); sys.exit(1)
    conv = list(set([n for n in (m['lineup'].get('starters') or {}).values() if n] + [s['nom'] for s in (m.get('subs') or [])]))
    pool = sorted(set(conv + [n for n in (m.get('goles') or {}) if n != '__EC__']))
    difs, obs = [], []
    def res(n):
        r = resolver(n, pool)
        if r is None: obs.append('No pude identificar a «%s» entre los que jugaron' % n); return None
        if r.startswith('?'): obs.append('«%s» es ambiguo (%s): poné nombre completo' % (n, r[1:].replace('|', ', '))); return None
        return r
    # marcador
    if ext.get('marcador'):
        mu, mr = ext['marcador']
        if (m.get('gLocal'), m.get('gRival')) != (mu, mr): difs.append('Marcador: Pizarra %s-%s · fuente %s-%s' % (m.get('gLocal'), m.get('gRival'), mu, mr))
    # titulares
    st = set(n for n in (m['lineup'].get('starters') or {}).values() if n)
    if ext.get('titulares'):
        es = set(filter(None, (res(n) for n in ext['titulares'])))
        for n in sorted(st - es): difs.append('Titular en la Pizarra pero no en la fuente: ' + n)
        for n in sorted(es - st): difs.append('Titular en la fuente pero no en la Pizarra: ' + n)
    # ingresos (quién entró) y minutos
    subs = {s['nom']: s.get('min') for s in (m.get('subs') or [])}
    if 'ingresos' in ext:
        ei = {}
        for x in ext['ingresos']:
            r = res(x['nom'])
            if r: ei[r] = x.get('min')
        for n in sorted(set(subs) - set(ei)): difs.append('Ingreso en la Pizarra pero no en la fuente: ' + n)
        for n in sorted(set(ei) - set(subs)): difs.append('Ingreso en la fuente pero no en la Pizarra: ' + n)
        for n in set(subs) & set(ei):
            try:
                d = abs(int(subs[n]) - int(ei[n]))
                if d > TOL: obs.append('Minuto del ingreso de %s: Pizarra %s\' · fuente %s\'' % (n, subs[n], ei[n]))
            except Exception: pass
    # salidas: la Pizarra todavía no las registra
    if ext.get('salidas'):
        sal = [x for x in ext['salidas']]
        pz = {s['nom']: s.get('por') for s in (m.get('subs') or []) if s.get('por')}
        if not pz: obs.append('Salidas: la Pizarra todavía no registra quién sale (la fuente informa %d)' % len(sal))
        else:
            es = set(filter(None, (res(x['nom']) for x in sal))); ps = set(pz.values())
            for n in sorted(ps - es): difs.append('Salida en la Pizarra pero no en la fuente: ' + n)
            for n in sorted(es - ps): difs.append('Salida en la fuente pero no en la Pizarra: ' + n)
    # tarjetas
    if 'tarjetas' in ext:
        pt = {}
        for t in (m.get('tarjetas') or []): pt[(t['nom'], t.get('col'))] = t.get('min')
        et = {}
        for t in ext['tarjetas']:
            r = res(t['nom'])
            if r: et[(r, t.get('col'))] = t.get('min')
        for k in sorted(set(pt) - set(et)): difs.append('Tarjeta en la Pizarra pero no en la fuente: %s (%s)' % k)
        for k in sorted(set(et) - set(pt)): difs.append('Tarjeta en la fuente pero no en la Pizarra: %s (%s)' % k)
    # autores de goles
    if 'goles' in ext:
        pg = {}
        for g in (m.get('golMins') or []):
            if g['nom'] != '__EC__': pg[g['nom']] = pg.get(g['nom'], 0) + 1
        if not pg:
            for n, c in (m.get('goles') or {}).items():
                if n != '__EC__': pg[n] = int(c)
        eg = {}
        for g in ext['goles']:
            r = res(g['nom'])
            if r: eg[r] = eg.get(r, 0) + 1
        for n in sorted(set(pg) | set(eg)):
            if pg.get(n, 0) != eg.get(n, 0): difs.append('Goles de %s: Pizarra %d · fuente %d' % (n, pg.get(n, 0), eg.get(n, 0)))
        pec = (m.get('goles') or {}).get('__EC__', 0)
        if 'en_contra' in ext and pec != len(ext['en_contra']): difs.append('Goles en contra: Pizarra %d · fuente %d' % (pec, len(ext['en_contra'])))
    out = {'estado': 'dif' if difs else 'ok', 'fuente': fuente, 'ts': datetime.datetime.utcnow().isoformat() + 'Z', 'difs': difs, 'obs': obs}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if dry: print('(--dry: no se guardó nada)'); return
    store = get('auf4_fifanov_corrob') or {}
    store.setdefault(rival, {})[nivel] = out
    print('guardado:', put('auf4_fifanov_corrob', store))

main()
