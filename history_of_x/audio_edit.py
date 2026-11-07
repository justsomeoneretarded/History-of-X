"""Uniform-format audio assembly; validate duration before any final -t can hide a splice error."""
import json,re,subprocess
from pathlib import Path
from .core import PipelineError,ffmpeg,duration,key,save_json

def assemble(speech,source,directory,interludes):
 source=Path(source);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);parts=[]
 for spoken in speech['scenes']:
  for i,gap in enumerate(interludes):
   if gap.get('before_scene_id')==spoken['scene_id']:
    silence=directory/f'gap-{i}-48k.wav';ffmpeg('-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t',str(gap['seconds']),'-c:a','pcm_s16le',silence);parts.append(silence)
  original=source/spoken['audio'];normalized=directory/(key('uniform-48k-v1',original.name,original.stat().st_size)+'.wav')
  if not normalized.exists():ffmpeg('-i',original,'-ar','48000','-ac','1','-c:a','pcm_s16le',normalized)
  parts.append(normalized)
 for i,gap in enumerate(interludes):
  if gap.get('before_scene_id') is None:
   silence=directory/f'tail-{i}-48k.wav';ffmpeg('-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t',str(gap['seconds']),'-c:a','pcm_s16le',silence);parts.append(silence)
 listing=directory/'voice.concat.txt';listing.write_text('\n'.join("file '"+str(p.resolve()).replace("'","'\\''")+"'" for p in parts))
 narration=directory/'narration.wav';ffmpeg('-f','concat','-safe','0','-i',listing,'-c:a','pcm_s16le',narration)
 expected=sum(s['duration'] for s in speech['scenes'])+sum(g['seconds'] for g in interludes);actual=duration(narration)
 timing={'expected_seconds':expected,'assembled_seconds':actual,'sample_rate':48000,'channels':1,'passed':abs(expected-actual)<.05}
 save_json(directory/'audio-timing.json',timing)
 if not timing['passed']:raise PipelineError('Assembled narration duration is wrong; refusing a truncated final export')
 return narration,timing

def mix(speech,shots,source,directory,interludes,output):
 from .animated_render import soundtrack
 directory=Path(directory);output=Path(output);directory.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
 narration,timing=assemble(speech,source,directory,interludes);soundtrack(speech,shots,directory)
 mixed=directory/'mixed.wav';chain='[0:a]asplit=2[v][side];[1:a][side]sidechaincompress=threshold=0.015:ratio=6:attack=15:release=250[m];[v][m][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.9[out]'
 ffmpeg('-i',narration,'-i',directory/'music.wav','-i',directory/'sfx.wav','-filter_complex',chain,'-map','[out]','-ar','48000','-ac','2',mixed)
 result=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(mixed),'-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,timeout=300)
 matches=re.findall(r'\{\s*"input_i".*?\}',result.stderr,re.S)
 if not matches:raise PipelineError('Cannot measure mixed audio loudness')
 loud=json.loads(matches[-1]);save_json(output/'loudness.json',loud);save_json(output/'audio-timing.json',timing)
 af=f'loudnorm=I=-16:TP=-1.5:LRA=9:measured_I={loud["input_i"]}:measured_TP={loud["input_tp"]}:measured_LRA={loud["input_lra"]}:measured_thresh={loud["input_thresh"]}:offset={loud["target_offset"]}:linear=true'
 return mixed,af,timing
