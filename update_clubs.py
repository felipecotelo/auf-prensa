#!/usr/bin/env python3
"""
Actualiza clubes actuales de jugadores Mayor y Local desde Transfermarkt.
Correr LOCALMENTE (no en GitHub Actions — TM bloquea IPs de Azure).

Uso:
  python3 update_clubs.py
  python3 update_clubs.py --push    # también hace git commit + push
"""

import re, sys, time, argparse, subprocess

HTML_FILE = 'public/index.html'

def fetch_tm(tmid):
    """Usa curl para traer el perfil TM (evita bloqueos de Python urllib)."""
    url = f'https://www.transfermarkt.es/x/profil/spieler/{tmid}'
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', '12',
             '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
             '-H', 'Accept-Language: es-ES,es;q=0.9',
             url],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout if result.returncode == 0 else None
    except Exception:
        return None

LEAGUE_COUNTRY = {
    # América del Sur
    'Serie A (Brasil)': 'br', 'Brasileirao': 'br', 'Série A': 'br', 'Serie B (Brasil)': 'br',
    'Primera División': 'uy', 'Primera División (Uruguay)': 'uy',
    'Liga Profesional de Fútbol': 'ar', 'Primera Nacional': 'ar', 'Primera División (Argentina)': 'ar',
    'Primera División (Chile)': 'cl', 'Primera División (Colombia)': 'co',
    'Liga 1 (Perú)': 'pe', 'Primera División (Paraguay)': 'py',
    'División de Honor (Bolivia)': 'bo', 'LaLiga BetPlay': 'co',
    # Europa
    'LaLiga': 'es', 'LaLiga2': 'es', 'Segunda División': 'es',
    'Premier League': 'gb-eng', 'Championship': 'gb-eng', 'League One': 'gb-eng',
    'Ligue 1': 'fr', 'Ligue 2': 'fr',
    'Bundesliga': 'de', '2. Bundesliga': 'de',
    'Serie A': 'it', 'Serie B': 'it',
    'Eredivisie': 'nl', 'Eerste Divisie': 'nl',
    'Jupiler Pro League': 'be',
    'Super League (Grecia)': 'gr', 'Super Lig': 'tr',
    'Primeira Liga': 'pt', 'Liga Portugal 2': 'pt',
    'Scottish Premiership': 'gb-sct',
    'Süper Lig': 'tr', 'TFF First League': 'tr',
    # Medio Oriente / Asia
    'Saudi Pro League': 'sa', 'Pro League (Saudi Arabia)': 'sa',
    'UAE Pro League': 'ae', 'Qatar Stars League': 'qa',
    'MLS': 'us', 'USL Championship': 'us',
    'Liga MX': 'mx', 'Liga de Expansión MX': 'mx',
    # Otros
    'Ukrainian Premier League': 'ua', 'RPL': 'ru',
}

def parse_club(html):
    """Extrae club y país. Keywords: 'Jugador,Club,Liga,NacJugador'
       Description: '... ➤ Club, desde XXXX ➤ ...'
    """
    if not html:
        return None, None

    # Club del meta description (nombre más limpio)
    m = re.search(r'<meta name="description" content="[^"]+?➤\s*([^,➤]+?)(?:,\s*desde|\s*➤)', html)
    club = m.group(1).strip() if m else None

    # Fallback: segundo campo del keywords
    if not club:
        mk = re.search(r'<meta name="keywords" content="[^,]+,([^,]+)', html)
        club = mk.group(1).strip() if mk else None

    # País: mapear la liga (tercer campo de keywords) → ISO
    pais = None
    mk2 = re.search(r'<meta name="keywords" content="[^,]+,[^,]+,([^,]+),', html)
    if mk2:
        liga = mk2.group(1).strip()
        pais = LEAGUE_COUNTRY.get(liga)

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
    # Cada jugador está en una sola línea: 'Nombre': {auf:..., pos:..., club:'...', pais:'...', ..., tmId:XXXXX, ...}
    pattern = r"'([^']+)':\s*\{auf:[^\n]+?club:'([^']+)'[^\n]+?pais:'([^']+)'[^\n]+?tmId:(\d+)"
    players = []
    for m in re.finditer(pattern, html):
        players.append({'nom': m.group(1), 'club': m.group(2),
                        'pais': m.group(3), 'tmId': int(m.group(4))})
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

        SKIP = {'Vereinslos', 'Karriereende', 'MLS Pool', 'sin club', 'Retirado'}
        if not club or club in SKIP:
            print(f'⏭ {club or "sin datos"} (omitido)')
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
        subprocess.run(['git', 'add', HTML_FILE], check=True)
        subprocess.run(['git', 'commit', '-m', f'Update clubs from Transfermarkt ({len(changes)} cambios)'], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        print('✓ Push a Railway completado')

if __name__ == '__main__':
    main()
