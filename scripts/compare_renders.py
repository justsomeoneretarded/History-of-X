"""Compare render profiles using the same verified narration and source assets."""
from pathlib import Path
import time
from history_of_x.core import read_json,save_json
from history_of_x.speech_merge import recover,merge
from history_of_x.render import render
from history_of_x.quality import package,inspect

root=Path('work/job')
recover('work/recovered-voices',root/'speech')
script=read_json(root/'script.json');request=read_json('work/request.json')
speech=merge(script,request['voice'],root/'speech')
assets=read_json(root/'assets'/'index.json');evidence=read_json(root/'research.json')
# For a long episode, use one complete verified scene per chapter rather than rerender the entire film three times.
if len(script['scenes'])>5:
    selected=[]
    for chapter in ['Hook','Roots','Catalyst','Turning Point','Aftermath']:
        selected.append(next(s for s in script['scenes'] if s['chapter']==chapter))
    ids={s['scene_id'] for s in selected};script={**script,'scenes':selected}
    speech={**speech,'scenes':[s for s in speech['scenes'] if s['scene_id'] in ids]}
    assets={str(s['scene_id']):assets[str(s['scene_id'])] for s in selected}
results=[]
for profile in ['draft','standard','cinematic']:
    started=time.monotonic();output=Path('output/comparison')/profile
    video=render(script,speech,assets,root/f'compare-{profile}',output,profile)
    package(script,evidence,speech,assets,root,output)
    qa=inspect(video,script,speech,assets,output)
    results.append({'profile':profile,'render_seconds':round(time.monotonic()-started,2),
        'file_megabytes':round(video.stat().st_size/1e6,2),'quality':qa})
    save_json(Path('output/comparison/comparison.json'),results)
