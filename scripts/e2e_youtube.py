"""Live local integration check. Use only a public source you may process.
Run in the API container: python - URL < scripts/e2e_youtube.py
"""
import sys
import secrets
import time
import httpx

with httpx.Client(base_url="http://api:8000", timeout=60) as client:
    r = client.post('/api/auth/register', json={
        'email': f'qa-youtube-{secrets.token_hex(5)}@example.test',
        'name': 'YouTube integration QA', 'password': secrets.token_urlsafe(24)})
    r.raise_for_status()
    r = client.post('/api/imports/preview', json={'url': sys.argv[1]})
    r.raise_for_status()
    preview = r.json()
    print({'preview_available': preview['available'], 'provider': preview.get('provider'), 'duration': preview.get('duration')}, flush=True)
    assert preview['available']
    r = client.post('/api/projects/import', json={
        'url': sys.argv[1], 'name': 'QA · public YouTube import', 'rights_confirmed': True,
        'config': {'clip_count': 1, 'min_duration': 10, 'max_duration': 20}})
    r.raise_for_status()
    project_id = r.json()['id']
    print({'project_id': project_id}, flush=True)
    deadline = time.monotonic() + 3600
    last = None
    while time.monotonic() < deadline:
        r = client.get('/api/projects/' + project_id)
        r.raise_for_status()
        project = r.json()
        state = (project['status'], project['progress'], project['stage'])
        if state != last:
            print({'status': state[0], 'progress': state[1], 'stage': state[2]}, flush=True)
            last = state
        if project['status'] == 'failed':
            print({'result': 'FAILED', 'error': project['error']}, flush=True)
            sys.exit(1)
        if project['status'] == 'ready':
            break
        time.sleep(3)
    else:
        raise TimeoutError('Project still processing; inspect its status before retrying')
    assert project['clips']
    clip = project['clips'][0]
    r = client.post('/api/clips/' + clip['id'] + '/exports')
    r.raise_for_status()
    export_id = r.json()['id']
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        r = client.get('/api/exports')
        r.raise_for_status()
        export = next(x for x in r.json() if x['id'] == export_id)
        if export['status'] == 'failed':
            raise RuntimeError(export['error'])
        if export['status'] == 'complete':
            break
        time.sleep(3)
    else:
        raise TimeoutError('Export still processing')
    r = client.get('/api/exports/' + export_id + '/download')
    r.raise_for_status()
    assert len(r.content) > 1000 and b'ftyp' in r.content[:64]
    print({'result': 'PASS', 'clips': len(project['clips']), 'words': len(project['transcript']), 'mp4_bytes': len(r.content)}, flush=True)
