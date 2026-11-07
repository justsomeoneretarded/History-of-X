"""Finish an in-flight moving render with verified audio timing, without re-rendering its picture."""
import json,shutil,subprocess
from pathlib import Path
from history_of_x.core import read_json,save_json,ffmpeg,duration,PipelineError
from history_of_x.audio_edit import mix
from history_of_x.quality import inspect

source=Path('work/source-film');work=Path('work/animated');out=Path('output/moving-film');out.mkdir(parents=True,exist_ok=True)
for path in source.iterdir():
 if path.is_file() and path.name not in ('final.mp4','quality.json','loudness.json','audio-timing.json','failure.json'):shutil.copy2(path,out/path.name)
script=read_json(source/'script.json');speech=read_json(work/'speech'/'speech.json');shots=read_json(source/'storyboard.json');info=read_json(source/'render.json')
mixed,af,timing=mix(speech,shots,work/'speech',work/'verified-mix',info.get('interludes',[]),out)
# No forced -t: all accepted narration samples must reach the final mux.
ffmpeg('-i',source/'final.mp4','-i',mixed,'-map','0:v:0','-map','1:a:0','-c:v','copy','-af',af,'-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',out/'final.mp4')
def video_hash(path):
 return subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-map','0:v:0','-c','copy','-f','md5','-'],capture_output=True,text=True,check=True).stdout.strip()
unchanged=video_hash(source/'final.mp4')==video_hash(out/'final.mp4')
if not unchanged:raise PipelineError('Picture track changed during audio-only finishing')
info['duration']=duration(out/'final.mp4');info['audio_timing_verified']=True;save_json(out/'render.json',info)
report=inspect(out/'final.mp4',script,speech,{},out);report.update(style=info['style'],visual_beats=len(shots),archival_clips=sum('archive' in s for s in shots),interlude_seconds=info.get('interlude_seconds',0),tts_provider='Gemini',tts_model=speech['model'],audio_timing_verified=True,video_bitstream_preserved=unchanged)
save_json(out/'quality.json',report)
production=read_json(source/'production.json') if (source/'production.json').exists() else {}
production.update(quality_passed=report['passed'],audio_timing=timing,video_bitstream_preserved=unchanged,narration_reused=True);save_json(out/'production.json',production)
print(json.dumps({'passed':report['passed'],'duration':report['duration_seconds'],'audio_timing':timing,'picture_preserved':unchanged}),flush=True)
