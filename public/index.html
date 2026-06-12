const express = require('express');
const fs      = require('fs');
const path    = require('path');

const app      = express();
const DATA_DIR = path.join(__dirname, 'data');
const DATA_FILE= path.join(DATA_DIR, 'state.json');

// Soporte para JSON grandes (fotos en base64)
app.use(express.json({ limit: '50mb' }));

// Sirve el HTML como página principal
app.use(express.static(path.join(__dirname, 'public')));

// Crea la carpeta data si no existe
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR);

// ── GET /api/load ── devuelve el estado guardado
app.get('/api/load', (req, res) => {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
      res.json({ ok: true, data });
    } else {
      res.json({ ok: true, data: null });
    }
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// ── POST /api/save ── guarda el estado completo
app.post('/api/save', (req, res) => {
  try {
    fs.writeFileSync(DATA_FILE, JSON.stringify(req.body));
    res.json({ ok: true });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`AUF Prensa corriendo en puerto ${PORT}`));
