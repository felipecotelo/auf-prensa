#!/bin/bash
# Prueba de humo sin node: sintaxis de cada <script> inline + funciones clave definidas.
# Uso: bash scripts/smoke.sh [ruta/a/index.html]   (por defecto public/index.html)
F="${1:-public/index.html}"
D=$(mktemp -d)
python3 - "$F" "$D" <<'E'
import re,sys
T=open(sys.argv[1],encoding='utf8').read(); n=0
for m in re.finditer(r'<script(?![^>]*\bsrc=)(?![^>]*text/plain)[^>]*>(.*?)</script>',T,re.S):
    open(f'{sys.argv[2]}/s{n}.js','w').write(m.group(1)); n+=1
print('scripts inline:',n)
E
cat > "$D/syn.js" <<E
ObjC.import('Foundation');
function run(){
  var bad=0,i=0,out=[];
  while(\$.NSFileManager.defaultManager.fileExistsAtPath('$D/s'+i+'.js')){
    var s=\$.NSString.stringWithContentsOfFileEncodingError('$D/s'+i+'.js',4,null).js;
    try{ new Function(s); out.push('OK  s'+i); }catch(e){ out.push('ERR s'+i+' '+e); bad++; }
    i++;
  }
  out.push(bad?'SINTAXIS FAIL':'SINTAXIS PASS'); return out.join('\n');
}
E
RES=$(osascript -l JavaScript "$D/syn.js"); echo "$RES"
MISS=0
for f in showSection showTab toast stor _rerenderTab _livePollSync autoSyncCheck renderInicio renderFifaNov26 renderFifaSep26 _juvFichaCard cloudPushDebounced _futbolTablaHTML _buildJuvAmistosos _mundSyncFifa; do
  grep -qE "^(async )?function $f\(|^(const|let|var) $f\b|window\.$f *=" "$F" || { echo "FALTA $f"; MISS=1; }
done
grep -qE 'window\.renderJuveniles *=' "$F" || { echo "FALTA window.renderJuveniles"; MISS=1; }
rm -rf "$D"
if echo "$RES" | grep -q FAIL || [ $MISS = 1 ]; then echo "SMOKE: FAIL"; exit 1; else echo "SMOKE: PASS"; fi
