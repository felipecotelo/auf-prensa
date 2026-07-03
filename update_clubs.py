#!/usr/bin/env python3
"""
Actualiza clubes actuales de jugadores Mayor y Local desde Transfermarkt.
Correr LOCALMENTE (no en GitHub Actions — TM bloquea IPs de Azure).

Uso:
  python3 update_clubs.py
  python3 update_clubs.py --push    # también hace git commit + push
"""

import re, sys, time, argparse
import urllib.request, urllib.error

HTML_FILE = 'public/index.html'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def fetch_tm(tmid):
    url = f'https://www.transfermarkt.es/x/profil/spieler/{tmid}'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None

def parse_club(html):
    if not html:
        return None, None
    # Club actual — aparece en el header de perfil
    # <span itemprop="name">Club Name</span> dentro del bloque de club actual
    m = re.search(r'Club actual[^<]*</span>\s*</td>\s*<td[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.S)
    if m:
        club = m.group(1).strip()
    else:
        # fallback: buscar el primer club en data-club-name
        m2 = re.search(r'data-club-name="([^"]+)"', html)
        club = m2.group(1).strip() if m2 else None

    # País del club
    pais = None
    m3 = re.search(r'<img[^>]*class="flagge[^"]*"[^>]*title="([^"]+)"', html)
    if m3:
        country_name = m3.group(1).strip()
        pais = COUNTRY_ISO.get(country_name)

    return club, pais

# Mapa de nombres TM → ISO 2 letras
COUNTRY_ISO = {
    'Uruguay': 'uy', 'Argentina': 'ar', 'Brasil': 'br', 'España': 'es',
    'Portugal': 'pt', 'Francia': 'fr', 'Italia': 'it', 'Alemania': 'de',
    'Inglaterra': 'gb-eng', 'México': 'mx', 'Colombia': 'co', 'Chile': 'cl',
    'Ecuador': 'ec', 'Paraguay': 'py', 'Bolivia': 'bo', 'Perú': 'pe',
    'Venezuela': 've', 'Estados Unidos': 'us', 'Turquía': 'tr',
    'Países Bajos': 'nl', 'Bélgica': 'be', 'Grecia': 'gr', 'Rusia': 'ru',
    'Arabia Saudí': 'sa', 'Emiratos Árabes': 'ae', 'China': 'cn',
    'Japón': 'jp', 'Australia': 'au', 'Suiza': 'ch', 'Austria': 'at',
    'Escocia': 'gb-sct', 'Gales': 'gb-wls', 'Irlanda': 'ie',
    'Ucrania': 'ua', 'Polonia': 'pl', 'República Checa': 'cz',
    'Croacia': 'hr', 'Serbia': 'rs', 'Eslovenia': 'si', 'Dinamarca': 'dk',
    'Suecia': 'se', 'Noruega': 'no', 'Finlandia': 'fi', 'Romania': 'ro',
    'Hungría': 'hu', 'Eslovaquia': 'sk', 'Egipto': 'eg', 'Marruecos': 'ma',
    'Qatar': 'qa', 'Corea del Sur': 'kr', 'Indonesia': 'id',
}

def extract_mayor_players(html):
    """Extrae (nombre, tmId, club_actual, pais_actual) del bloque JUGADORES."""
    pattern = r"'([^']+)':\s*\{auf:[^}]+?tmId:(\d+)[^}]+?club:'([^']+)'[^}]+?pais:'([^']+)'"
    players = []
    for m in re.finditer(pattern, html):
        players.append({'nom': m.group(1), 'tmId': int(m.group(2)),
                        'club': m.group(3), 'pais': m.group(4)})
    return players

def flag_to_iso(flag_emoji):
    """Convierte emoji de bandera a código ISO 2 letras (ej 🇧🇷 → br)."""
    try:
        points = [ord(c) - 0x1F1E6 for c in flag_emoji if '\U0001F1E6' <= c <= '\U0001F1FF']
        if len(points) == 2:
            return chr(ord('a') + points[0]) + chr(ord('a') + points[1])
    except:
        pass
    return None

def update_mayor_club(html, nom, new_club, new_pais_emoji):
    """Reemplaza club y pais en la entrada JUGADORES del jugador."""
    escaped = re.escape(nom)
    # Reemplazar club:'...'
    html, n1 = re.subn(
        rf"('{escaped}':\s*\{{[^}}]*?club:')([^']+)(')",
        rf'\g<1>{new_club}\g<3>', html
    )
    # Reemplazar pais:'...' (emoji)
    html, n2 = re.subn(
        rf"('{escaped}':\s*\{{[^}}]*?pais:')([^']+)(')",
        rf'\g<1>{new_pais_emoji}\g<3>', html
    )
    return html, (n1 > 0 or n2 > 0)

def iso_to_flag(iso):
    if not iso or len(iso) < 2: return '🏳'
    iso = iso.lower()[:2]
    return chr(0x1F1E6 + ord(iso[0]) - ord('a')) + chr(0x1F1E6 + ord(iso[1]) - ord('a'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--push', action='store_true', help='git commit + push after update')
    parser.add_argument('--dry-run', action='store_true', help='solo mostrar cambios, no escribir')
    args = parser.parse_args()

    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    players = extract_mayor_players(html)
    print(f'Encontrados {len(players)} jugadores Mayor con tmId\n')

    changes = []

    for p in players:
        print(f'Buscando {p["nom"]} (tmId:{p["tmId"]})...', end=' ', flush=True)
        page = fetch_tm(p['tmId'])
        club, pais_iso = parse_club(page)
        time.sleep(1.2)  # respetar rate limit

        if not club:
            print('❌ sin datos')
            continue

        new_flag = iso_to_flag(pais_iso) if pais_iso else p['pais']
        if club == p['club'] and new_flag == p['pais']:
            print(f'✓ sin cambio ({club})')
            continue

        print(f'✎ {p["club"]} → {club} {new_flag}')
        changes.append({'nom': p['nom'], 'old_club': p['club'], 'new_club': club, 'new_flag': new_flag})

        if not args.dry_run:
            html, ok = update_mayor_club(html, p['nom'], club, new_flag)
            if not ok:
                print(f'  ⚠ No se pudo actualizar en HTML')

    if not changes:
        print('\nNingún cambio detectado.')
        return

    print(f'\n{len(changes)} cambios:')
    for c in changes:
        print(f'  {c["nom"]}: {c["old_club"]} → {c["new_club"]} {c["new_flag"]}')

    if args.dry_run:
        print('\n(dry-run: no se escribió nada)')
        return

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n✓ {HTML_FILE} actualizado')

    if args.push:
        import subprocess
        subprocess.run(['git', 'add', HTML_FILE], check=True)
        subprocess.run(['git', 'commit', '-m', f'Update clubs from Transfermarkt ({len(changes)} cambios)'], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        print('✓ Push a Railway completado')

if __name__ == '__main__':
    main()
