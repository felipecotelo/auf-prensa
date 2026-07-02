"""
Busca jugadores con tmId en index.html, consulta Transfermarkt
y actualiza club + pais si cambiaron.
"""

import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

# Nombre del país en TM (español o inglés) → código ISO para flagcdn.com
PAIS_MAP = {
    'Alemania': 'de', 'España': 'es', 'Portugal': 'pt', 'Francia': 'fr',
    'Italia': 'it', 'Inglaterra': 'gb', 'Brasil': 'br', 'Argentina': 'ar',
    'Uruguay': 'uy', 'Países Bajos': 'nl', 'Bélgica': 'be', 'Turquía': 'tr',
    'Estados Unidos': 'us', 'México': 'mx', 'Colombia': 'co', 'Chile': 'cl',
    'Japón': 'jp', 'Arabia Saudí': 'sa', 'Grecia': 'gr', 'Paraguay': 'py',
    'Ecuador': 'ec', 'Bolivia': 'bo', 'Perú': 'pe', 'Venezuela': 've',
    'Escocia': 'gb', 'Gales': 'gb', 'Suiza': 'ch', 'Austria': 'at',
    'Dinamarca': 'dk', 'Suecia': 'se', 'Noruega': 'no', 'Polonia': 'pl',
    'Croacia': 'hr', 'Serbia': 'rs', 'Ucrania': 'ua', 'Hungría': 'hu',
    'China': 'cn', 'Corea del Sur': 'kr', 'Australia': 'au',
    'República Checa': 'cz', 'Eslovaquia': 'sk', 'Rumania': 'ro',
    'Eslovenia': 'si', 'Bulgaria': 'bg', 'Georgia': 'ge',
    # inglés también (TM a veces responde en inglés)
    'Germany': 'de', 'Spain': 'es', 'France': 'fr', 'Italy': 'it',
    'England': 'gb', 'Netherlands': 'nl', 'Belgium': 'be', 'Turkey': 'tr',
    'United States': 'us', 'Greece': 'gr', 'Switzerland': 'ch',
    'Denmark': 'dk', 'Sweden': 'se', 'Norway': 'no', 'Poland': 'pl',
    'Japan': 'jp', 'Saudi Arabia': 'sa', 'South Korea': 'kr',
    'Romania': 'ro', 'Scotland': 'gb', 'Wales': 'gb', 'Ukraine': 'ua',
    'Croatia': 'hr', 'Serbia': 'rs', 'Hungary': 'hu', 'Slovakia': 'sk',
    'Czech Republic': 'cz', 'Slovenia': 'si', 'Bulgaria': 'bg',
}


def fetch_player(tm_id):
    url = f'https://www.transfermarkt.es/x/profil/spieler/{tm_id}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        print(f'  ✗ Error al obtener {tm_id}: {e}')
        return None, None

    soup = BeautifulSoup(r.text, 'html.parser')
    club = None
    pais = None

    # Club — varios selectores posibles según versión de TM
    for sel in [
        '.data-header__club a',
        '.data-header__box--big a[href*="/startseite/verein/"]',
        'a[href*="/startseite/verein/"]',
    ]:
        el = soup.select_one(sel)
        if el and el.text.strip() and 'transfermarkt' not in el.text.lower():
            club = el.text.strip()
            break

    # País — desde imagen de bandera en la cabecera
    for img in soup.select('img[src*="flagge"], img[src*="flags"], img[class*="flag"]'):
        src = img.get('src', '').lower()
        m = re.search(r'/([a-z]{2})(?:\.png|_|\b)', src)
        if m and m.group(1) not in ('tm',):
            pais = m.group(1)
            break

    # País — desde texto de la página si no encontramos imagen
    if not pais:
        text = soup.get_text()
        for nombre, codigo in PAIS_MAP.items():
            if nombre in text:
                pais = codigo
                break

    return club, pais or 'uy'


def update_html(html, tm_id, club, pais):
    changed = False
    lines = html.split('\n')
    result = []

    for line in lines:
        if f'tmId:{tm_id}' in line or f'tmId: {tm_id}' in line:
            original = line
            if club:
                line, n = re.subn(r"club:'[^']*'", f"club:'{club}'", line)
                changed = changed or n > 0
            if pais:
                line, n = re.subn(r"pais:'[^']*'", f"pais:'{pais}'", line)
                changed = changed or n > 0
            if line != original:
                print(f'  Antes : {original.strip()}')
                print(f'  Después: {line.strip()}')
        result.append(line)

    return '\n'.join(result), changed


def main():
    with open('public/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    tm_ids = sorted(set(int(x) for x in re.findall(r'tmId:(\d+)', html)))
    if not tm_ids:
        print('No se encontraron jugadores con tmId.')
        return

    print(f'Jugadores a actualizar: {len(tm_ids)} → {tm_ids}\n')
    any_change = False

    for tm_id in tm_ids:
        print(f'tmId:{tm_id}')
        club, pais = fetch_player(tm_id)
        if club:
            print(f'  → {club} ({pais})')
            html, changed = update_html(html, tm_id, club, pais)
            any_change = any_change or changed
        else:
            print('  → No se pudo obtener el club.')
        time.sleep(2)

    if any_change:
        with open('public/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print('\n✓ index.html actualizado.')
    else:
        print('\n— Sin cambios.')


if __name__ == '__main__':
    main()
