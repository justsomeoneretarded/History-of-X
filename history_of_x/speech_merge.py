"""Merge verified, independently resumable chapter narration checkpoints."""
from pathlib import Path
import shutil
from .core import PipelineError,read_json,save_json,key
from .script import CHAPTERS

def recover(download_root,speech_root):
    for index in range(1,6):
        source=Path(download_root)/f'checkpoint-voice-{index}'
        if source.exists():
            shutil.copytree(source,Path(speech_root)/f'chapter-{index}',dirs_exist_ok=True)

def merge(script,voice,directory):
    records=[]
    for index,chapter in enumerate(CHAPTERS,1):
        root=directory/f'chapter-{index}'
        path=root/'speech.json'
        if not path.exists():raise PipelineError(f'Missing narration checkpoint for {chapter}')
        part=read_json(path)
        if part['voice']!=voice:raise PipelineError('Narrator mismatch across chapters')
        expected=[s['scene_id'] for s in script['scenes'] if s['chapter']==chapter]
        actual=[s['scene_id'] for s in part['scenes']]
        if actual!=expected:raise PipelineError(f'Incomplete or mismatched chapter: {chapter}')
        for scene in part['scenes']:
            if not scene['verification']['accepted'] or not (root/scene['audio']).is_file():
                raise PipelineError(f'Unverified or missing audio in {chapter}')
            records.append({**scene,'audio':f'chapter-{index}/'+scene['audio']})
    result={'voice':voice,'scenes':records,'fingerprint':key('chapter-merge-v1',script,voice)}
    save_json(directory/'speech.json',result)
    return result
