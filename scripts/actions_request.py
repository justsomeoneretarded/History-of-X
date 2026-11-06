"""Read dispatch values as data, never interpolate them into shell source."""
import hashlib
import json
import os
from pathlib import Path

if os.getenv('GITHUB_EVENT_NAME')=='push':
    # Automatic production requests are explicit committed files. The latest named request is selected.
    paths=sorted(Path('episodes/requests').glob('*.json'))
    if not paths:raise SystemExit('No production request found')
    request=json.loads(paths[-1].read_text())
else:
    request={'title':os.environ.get('VIDEO_TITLE',''),'brief':os.environ.get('VIDEO_BRIEF',''),
        'voice':os.environ.get('NARRATOR') or 'warguy','minutes':float(os.environ.get('VIDEO_MINUTES') or '8'),
        'profile':os.environ.get('VIDEO_PROFILE') or 'cinematic'}
    if os.getenv('PRESET') in ('ethiopia','pilot'):request['episode']='episodes/'+os.environ['PRESET']+'.json'
if not request.get('title') or not request.get('brief'):raise SystemExit('Title and brief are required')
Path('work').mkdir(exist_ok=True)
Path('work/request.json').write_text(json.dumps(request,indent=2))
seed=Path(request['episode']).read_text() if request.get('episode') else ''
identity=hashlib.sha256((json.dumps(request,sort_keys=True)+seed).encode()).hexdigest()[:24]
if os.getenv('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('id='+identity+'\n')
