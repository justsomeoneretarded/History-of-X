import json
import os
from pathlib import Path
path=Path('output/quality.json')
text='## Documentary production\n\n'
if path.exists():
    q=json.loads(path.read_text())
    text+=f'Quality checks: **{"passed" if q["passed"] else "failed"}**\n\n'
    text+=f'Duration: {q["duration_seconds"]:.1f}s · Voice: {q["voice"]} · Scenes: {q["scene_count"]} · Licensed assets: {q["unique_licensed_assets"]}\n\n'
    text+='Download **documentary-final** for the video, captions, thumbnail, description, sources, credits and contact sheet. Review historical imagery and pronunciation before uploading.\n'
else:text+='Production did not finish. Inspect the logs and checkpoint artifacts.\n'
if os.getenv('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(text)
print(text)
