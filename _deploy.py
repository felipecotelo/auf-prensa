#!/usr/bin/env python3
"""
AUF Prensa — Auto deploy
Sube public/index.html a GitHub via API → Railway redeploya solo.
Uso: python3 _deploy.py
"""
import json, ssl, base64, urllib.request, sys, os
from datetime import datetime

CONFIG_FILE = os.path.expanduser('~/.auf_deploy_config')
ctx = ssl._create_unverified_context()

def load_config():
    cfg = {}
    with open(CONFIG_FILE) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg

def api_get(url, token):
    req = urllib.request.Request(url)
    req.add_header('Authorization', 'token ' + token)
    return json.loads(urllib.request.urlopen(req, context=ctx).read())

def api_put(url, token, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='PUT')
    req.add_header('Authorization', 'token ' + token)
    req.add_header('Content-Type', 'application/json')
    return json.loads(urllib.request.urlopen(req, context=ctx).read())

def deploy():
    cfg = load_config()
    token = cfg['GITHUB_TOKEN']
    repo  = cfg['GITHUB_REPO']
    src   = cfg['HTML_SRC']

    # Copiar HTML actualizado
    dest = os.path.join(os.path.dirname(__file__), 'public', 'index.html')
    with open(src, 'rb') as f:
        content = f.read()
    with open(dest, 'wb') as f:
        f.write(content)

    # Obtener SHA actual
    api_url = f'https://api.github.com/repos/{repo}/contents/public/index.html'
    current = api_get(api_url, token)
    sha = current['sha']

    # Subir nuevo contenido
    msg = f"update {datetime.now().strftime('%d/%m %H:%M')}"
    result = api_put(api_url, token, {
        'message': msg,
        'content': base64.b64encode(content).decode(),
        'sha': sha
    })
    new_sha = result['content']['sha'][:8]
    print(f'✅ Deploy OK — {msg} (sha {new_sha})')
    print(f'   Railway redeploya en ~60 seg → https://auf-prensa-production.up.railway.app')

if __name__ == '__main__':
    try:
        deploy()
    except Exception as e:
        print(f'❌ Error: {e}', file=sys.stderr)
        sys.exit(1)
