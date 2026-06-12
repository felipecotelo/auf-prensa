#!/bin/bash
# ── AUF Prensa · Deploy script ──────────────────────────
# Copia el HTML actualizado y pushea a Railway en un paso

set -e

echo "📋 Copiando HTML actualizado..."
cp ~/Downloads/auf_fwc26_v4.html ./public/index.html

echo "📦 Commiteando cambios..."
git add .
git commit -m "update $(date '+%d/%m %H:%M')" 2>/dev/null || echo "Sin cambios nuevos"

echo "🚀 Pusheando a Railway..."
git push origin main

echo "✅ Listo — Railway redeploya en ~60 segundos"
