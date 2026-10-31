# Una persona, una ficha: copia tmId, fecha de nacimiento y (opcional) club actual a TODAS las apariciones de cada jugador en public/index.html.
# Uso: python3 -I scripts/propagar_fichas.py [commit_base]   → los clubes "actuales" se toman de las entradas con tmId agregadas desde commit_base.
import re,sys,subprocess,collections
P='public/index.html'
base=sys.argv[1] if len(sys.argv)>1 else None
s=open(P,encoding='utf-8').read()
ent=re.compile(r"\{[^{}\n]*?nom:'((?:[^'\\]|\\.)*)'[^{}\n]*\}")
def isplayer(o):
    if re.search(r"\brival:|\bfase:|\bs:'|\bn:\d",o): return False
    if re.search(r"\b(g|min|f|goles):",o) and not re.search(r"\bclub:",o): return False
    return bool(re.search(r"\b(club|pos|num|tmId|fechaNac):",o))
HOM={'Luciano González','Agustín Pérez','Nicolás González','Juan Rodríguez','Ignacio González','Nicolás López','Nicolás Fernández','Facundo Pérez','Renzo Rodríguez','Facundo Martínez','Cristian Rodríguez','Diego Rossi'}
clubs={}
if base:
    d=subprocess.run(['git','diff','-U0',base,'--',P],capture_output=True,text=True).stdout
    for l in d.split('\n'):
        if not l.startswith('+') or l.startswith('+++'): continue
        for m in ent.finditer(l):
            o=m.group(0)
            if isplayer(o) and 'tmId:' in o:
                c=re.search(r"club:'([^']*)'",o)
                if c and c.group(1): clubs[m.group(1)]=c.group(1)
info=collections.defaultdict(lambda:{'tm':set(),'fn':set()})
lines=s.split('\n')
for l in lines:
    for m in ent.finditer(l):
        o=m.group(0)
        if not isplayer(o): continue
        t=re.search(r"tmId:(\d+)",o); f=re.search(r"fechaNac:'([\d-]+)'",o)
        if t: info[m.group(1)]['tm'].add(t.group(1))
        if f: info[m.group(1)]['fn'].add(f.group(1))
tocadas=0; nombres=set()
for i,l in enumerate(lines):
    out=[]
    for m in ent.finditer(l):
        o=m.group(0); nom=m.group(1)
        if nom in HOM or not isplayer(o): continue
        d=info[nom]
        if len(d['tm'])>1 or len(d['fn'])>1: continue
        tm=next(iter(d['tm']),None); fn=next(iter(d['fn']),None)
        new=o
        if nom in clubs and "club:'" in new:
            new=re.sub(r"club:'[^']*'","club:'%s'"%clubs[nom],new,1)
        add=''
        if fn and 'fechaNac:' not in new: add+=", fechaNac:'%s'"%fn
        if tm and 'tmId:' not in new: add+=", tmId:%s"%tm
        if add:
            new=new[:-1].rstrip(); new=new[:-1] if new.endswith(',') else new; new+=add+'}'
        if new!=o: out.append((m.start(),m.end(),new)); tocadas+=1; nombres.add(nom)
    for st,en,new in reversed(out): l=l[:st]+new+l[en:]
    lines[i]=l
open(P,'w',encoding='utf-8').write('\n'.join(lines))
print('entradas tocadas',tocadas,'jugadores',len(nombres))
