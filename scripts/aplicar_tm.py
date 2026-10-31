# Aplica los datos de Transfermarkt (tmId, fecha, club actual) a TODAS las apariciones de un jugador en public/index.html.
# Uso: python3 -I scripts/aplicar_tm.py "Nombre en la app" tmId [club_manual]
import re,sys,json,subprocess,html,unicodedata
P='public/index.html'; nom=sys.argv[1]; tm=int(sys.argv[2]); club_manual=sys.argv[3] if len(sys.argv)>3 else None
r=subprocess.run(['curl','-s','-m','60','https://baseceleste.up.railway.app/api/tm/%d'%tm],capture_output=True,text=True).stdout
d=json.loads(r)
if d.get('error'): print('TM:',d['error']); sys.exit(1)
fn=d.get('dateOfBirth'); club=(d.get('club') or {}).get('name') or ''
if d.get('retired'): club='Retirado'
if club in ('Sin equipo','Desconocido',''): club='sin club'
if club_manual: club=club_manual
s=open(P,encoding='utf-8').read()
def norm(x): return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFD',html.unescape(x).lower()).encode('ascii','ignore').decode())
db={}
for m in re.finditer(r"^ *'([^'|]+)\|([a-z-]+)\|([^']*)',",s,re.M):
    for a in [m.group(1)]+[x for x in m.group(3).split(';') if x]: db[norm(a)]=m.group(1)
cn=db.get(norm(club),None)
ent=re.compile(r"\{[^{}\n]*?nom:'%s'[^{}\n]*\}"%re.escape(nom.replace("'","\\'")))
n=0; lines=s.split('\n')
for i,l in enumerate(lines):
    for mm in list(ent.finditer(l)):
        o=mm.group(0)
        if not re.search(r"\b(club|pos|num):",o) or re.search(r"\bclubPais|\bbajaGira",o): continue
        new=o
        new=re.sub(r"club:'[^']*'","club:'%s'"%(cn or club),new,1) if "club:'" in new else new
        new=re.sub(r",\s*retirado:true","",new) if club!='Retirado' else new
        new=re.sub(r",\s*pais:'[a-z-]+'","",new)
        new=re.sub(r"tmId:\d+","tmId:%d"%tm,new) if 'tmId:' in new else new[:-1].rstrip()+", tmId:%d}"%tm
        if fn: new=re.sub(r"fechaNac:'[^']*'","fechaNac:'%s'"%fn,new) if 'fechaNac:' in new else new[:-1].rstrip()+", fechaNac:'%s'}"%fn
        if new!=o: lines[i]=lines[i].replace(o,new); n+=1
open(P,'w',encoding='utf-8').write('\n'.join(lines))
print(nom,'→',club,'(en base: %s)'%cn if cn else '(CLUB NUEVO, agregar a CLUBES_DB)',fn,tm,'entradas:',n)
