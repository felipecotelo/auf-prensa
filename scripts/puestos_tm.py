# Completa el puesto (POR/DEF/MED/DEL) en auf4_juvPos de los jugadores que tienen tmId y todavía no tienen puesto,
# leyéndolo de Transfermarkt. Pensado para correr de a ratos: lee pocos perfiles por corrida y corta al primer 403.
# Uso: python3 -I scripts/puestos_tm.py [máximo_de_perfiles=8] [--dry]
# Reglas: si Transfermarkt le pone puesto, se usa ese; si no tiene, se deja como está. Solo agrega claves que faltan
# (nunca pisa un puesto ya cargado). Un perfil cuyo nombre o fecha no coincide con la ficha se descarta y queda anotado.
import re,sys,json,subprocess,time,unicodedata,datetime,os

REPO=os.path.expanduser('~/auf-prensa-work')
ESTADO=REPO+'/backups/puestos_tm_estado.json'
K='sb_publishable_GaiAMaH49DGCJgzDOTKHSQ_42jKWXNq'
SB='https://wsiudiexcodrhyejevco.supabase.co/rest/v1/sync_data'
TM='https://baseceleste.up.railway.app/api/tm/%d'
args=[a for a in sys.argv[1:] if not a.startswith('--')]
MAX=int(args[0]) if args else 8
DRY='--dry' in sys.argv

def curl(*a):
    return subprocess.run(['curl','-s','-m','60']+list(a),capture_output=True,text=True).stdout
def sb_get(key):
    r=json.loads(curl(SB+'?key=eq.%s&select=value'%key,'-H','apikey: '+K) or '[]')
    return json.loads(r[0]['value']) if r else {}
def grupo(p):
    p=str(p or '').lower()
    if re.search('portero|arquero',p): return 'POR'
    if re.search('defens|lateral',p): return 'DEF'
    if re.search('pivote|mediocentro|mediapunta|interior|centrocampista',p): return 'MED'
    if re.search('extremo|delantero|punta',p): return 'DEL'
    return ''
def nk(t):
    t=unicodedata.normalize('NFD',str(t or '')).encode('ascii','ignore').decode().lower()
    return {w for w in re.split(r'[^a-z]+',t) if len(w)>=4}

subprocess.run(['git','-C',REPO,'fetch','-q','origin'])
html=subprocess.run(['git','-C',REPO,'show','origin/main:public/index.html'],capture_output=True,text=True).stdout
ids={}; nac={}
for m in re.finditer(r"\{[^{}\n]*?nom:'((?:[^'\\]|\\.)*)'[^{}\n]*\}",html):
    o=m.group(0); n=m.group(1).replace("\\'","'")
    t=re.search(r"tmId:(\d+)",o)
    if t: ids.setdefault(n,set()).add(int(t.group(1)))
    f=re.search(r"fechaNac:'([^']*)'",o)
    if f: nac.setdefault(n,set()).add(f.group(1))

juv=sb_get('auf4_juvPos'); mayor=sb_get('auf4_jugpos'); loc=sb_get('auf4_local_pos')
estado=json.load(open(ESTADO)) if os.path.exists(ESTADO) else {'descartados':{}}
pend=[n for n,s in sorted(ids.items()) if len(s)==1 and n not in juv and n not in mayor and n not in loc and n not in estado['descartados']]
print('Pendientes al arrancar:',len(pend))

nuevos={}; bloqueado=False
for n in pend[:MAX]:
    tm=next(iter(ids[n]))
    try: d=json.loads(curl(TM%tm))
    except Exception: print('  respuesta ilegible:',n); continue
    if d.get('error'):
        print('  %s (%d): %s'%(n,tm,d['error']))
        if '403' in str(d['error']): bloqueado=True; break
        continue
    if d.get('name') and not (nk(n)&nk(d['name'])):
        estado['descartados'][n]='nombre distinto en TM: '+d['name']
    elif nac.get(n) and d.get('dateOfBirth') and d['dateOfBirth'] not in nac[n]:
        estado['descartados'][n]='fecha distinta: ficha %s, TM %s'%(sorted(nac[n]),d['dateOfBirth'])
    elif not grupo(d.get('position')):
        estado['descartados'][n]='TM no le pone puesto (%s)'%d.get('position')
    else:
        nuevos[n]=grupo(d['position']); print('  %s → %s (%s)'%(n,nuevos[n],d['position']))
    time.sleep(4)

if nuevos and not DRY:
    val=sb_get('auf4_juvPos')   # se relee justo antes de escribir
    add={k:v for k,v in nuevos.items() if k not in val}; val.update(add)
    body=json.dumps({'value':json.dumps(val,ensure_ascii=False),'updated_at':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000+00:00')},ensure_ascii=False)
    r=curl('-X','PATCH',SB+'?key=eq.auf4_juvPos','-H','apikey: '+K,'-H','Authorization: Bearer '+K,'-H','Content-Type: application/json','-H','Prefer: return=minimal','-d',body,'-w','HTTP %{http_code}')
    chk=sb_get('auf4_juvPos')
    print('Escritos:',len(add),r,'| verificado:',all(chk.get(k)==v for k,v in add.items()))
if not DRY: json.dump(estado,open(ESTADO,'w'),ensure_ascii=False,indent=1)
for n,why in estado['descartados'].items(): print('  descartado:',n,'—',why)
quedan=len(pend)-len(nuevos)-sum(1 for n in pend[:MAX] if n in estado['descartados'])
print('BLOQUEADO por Transfermarkt (reintentar más tarde)' if bloqueado else 'Corrida completa','| quedan por leer:',max(quedan,0))
