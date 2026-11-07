import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from fastapi.testclient import TestClient
from main import app

with TestClient(app) as client:
    manifest=client.get('/manifest.webmanifest')
    assert manifest.status_code==200 and manifest.headers['content-type'].startswith('application/manifest+json')
    assert manifest.json()['start_url']=='/#/home'
    worker=client.get('/sw.js')
    assert worker.status_code==200 and 'javascript' in worker.headers['content-type']
    assert worker.headers['service-worker-allowed']=='/' and worker.headers['cache-control']=='no-cache'
    assert client.get('/static/offline.html').status_code==200
    for size in (180,192,512):assert client.get(f'/static/icons/enwen-{size}.png').status_code==200
    assert 'rel="manifest"' in client.get('/').text
print('Passed PWA route, MIME, scope, offline-page and icon checks; no database records accessed.')
