// Extrae CALENDAR_DAYS directamente del HTML servido en /public, así no hay
// que mantener una copia duplicada: cada deploy (que actualiza public/index.html)
// actualiza automáticamente los datos usados por /api/calendar.ics.
const fs = require('fs');
const path = require('path');

function extractConst(src, name) {
  const marker = `const ${name} = `;
  let start = src.indexOf(marker);
  if (start === -1) {
    const marker2 = `const ${name}=`;
    start = src.indexOf(marker2);
    if (start === -1) throw new Error('No se encontró ' + name + ' en index.html');
    start += marker2.length;
  } else {
    start += marker.length;
  }
  const openChar = src[start];
  const closeChar = openChar === '[' ? ']' : '}';
  let depth = 0, i = start, inStr = null;
  for (; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (c === '\\') { i++; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    if (c === openChar) depth++;
    else if (c === closeChar) { depth--; if (depth === 0) { i++; break; } }
  }
  const literal = src.slice(start, i);
  // eslint-disable-next-line no-eval
  return eval(literal);
}

function loadCalendarDays() {
  const html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');
  return extractConst(html, 'CALENDAR_DAYS');
}

module.exports = { loadCalendarDays };
