# Busca jugadores en transfermarkt.es y muestra fecha de nacimiento, club, posición y nacionalidad de cada candidato.
# Uso: python3 -I scripts/tm_buscar.py nombres.json salida.json   (nombres.json = lista de nombres)
import re,sys,time,urllib.parse,html,json,subprocess
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
def get(u):
    return subprocess.run(['curl','-s','-L','--max-time','30','-A',UA,'-H','Accept-Language: es',u],capture_output=True).stdout.decode('utf-8','ignore')
def prof(u):
    h=get('https://www.transfermarkt.es'+u)
    g=lambda rx:(re.search(rx,h,re.S) or [None,None])[1]
    dob=g(r'itemprop="birthDate"[^>]*>\s*([0-9/]+)')
    club=g(r'data-header__club"[^>]*>\s*<a title="([^"]+)"')
    pos=g(r'Posición:\s*</span>\s*<span[^>]*>\s*([^<]+?)\s*<')
    mn=re.search(r'itemprop="nationality"[^>]*>(.*?)</span>',h,re.S); nat=re.findall(r'title="([^"]+)"',mn.group(1)) if mn else []
    return dict(url=u,dob=dob,club=html.unescape(club or '').strip(),pos=(pos or '').strip(),nat=nat)
names=json.load(open(sys.argv[1]))
out={}
for n in names:
    q=urllib.parse.quote_plus(n)
    h=get('https://www.transfermarkt.es/schnellsuche/ergebnis/schnellsuche?query='+q)
    # solo la tabla de jugadores
    i=h.find('Jugadores'); seg=h[i:i+60000]
    links=[]
    for m in re.finditer(r'href="(/[a-z0-9-]+/profil/spieler/\d+)"',seg):
        if m.group(1) not in links: links.append(m.group(1))
    cands=[]
    for u in links[:4]:
        try:
            time.sleep(0.8); p=prof(u); cands.append(p)
        except Exception as e: cands.append({'url':u,'err':str(e)})
    out[n]=cands
    print(n,'->',[ (c.get('dob'),c.get('club'),c.get('pos'),c.get('nat')) for c in cands],flush=True)
    time.sleep(0.8)
json.dump(out,open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
