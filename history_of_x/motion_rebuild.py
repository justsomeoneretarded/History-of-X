"""Recreate a saved narration as a moving film, with a motion-gated preview first."""
from __future__ import annotations
import argparse,copy,json
from pathlib import Path
from .core import ROOT,PipelineError,read_json,save_json,ffmpeg,duration
from .media_api import MediaAPI
from .motion_director import direct
from .archival_motion import bridge,credits
from .animated_render import render
from .motion_quality import measure

def preview(api,script,speech,shots,work,out):
 out.mkdir(parents=True,exist_ok=True)
 ids=[script['scenes'][0]['scene_id']]
 for chapter in ['Roots','Catalyst','Turning Point']:
  part=[s['scene_id'] for s in script['scenes'] if s['chapter']==chapter]
  if part:ids.append(part[1] if chapter=='Turning Point' and len(part)>1 else part[0])
 chosen=[];scenes=[];voices=[];position=0
 for sid in ids:
  candidates=[s for s in shots if s['scene_id']==sid][:2]
  if not candidates:continue
  length=candidates[-1]['global_end']-candidates[0]['global_start'];origin=candidates[0]['global_start']
  for s in candidates:chosen.append({**s,'global_start':position+s['global_start']-origin,'global_end':position+s['global_end']-origin})
  scene=next(s for s in script['scenes'] if s['scene_id']==sid);original=next(s for s in speech['scenes'] if s['scene_id']==sid)
  audio=work/'speech'/f'preview-scene-{sid}.wav';ffmpeg('-i',work/'speech'/original['audio'],'-t',str(length),'-ar','24000','-ac','1',audio)
  record={**original,'audio':audio.name,'duration':duration(audio),'words':[w for w in original['words'] if w['start']<length],'captions':[{**c,'end':min(c['end'],length)} for c in original['captions'] if c['start']<length]}
  scenes.append(scene);voices.append(record);position+=length
 gaps=[]
 if 'ethiop' in script['title'].lower():
  for i,item in enumerate(read_json(ROOT/'assets'/'footage'/'catalog.json')):
   chosen.append({'beat_id':item['id'],'scene_id':0,'global_start':position+i*4.5,'global_end':position+(i+1)*4.5,'text':'','narration_context':'','year_label':'1935','year':1935,'sting':False,'music_mood':'somber','headline':'','nodes':[],'archive':item,'rationale':item['context']})
  gaps=[{'at':position,'seconds':9,'before_scene_id':None}]
 preview_script={**script,'scenes':scenes};preview_speech={**speech,'scenes':voices}
 video=render(preview_script,preview_speech,chosen,work/'preview-render',out,'draft',interludes=gaps)
 score=measure(video,1.2,duration(video)-.5);save_json(out/'motion-check.json',score)
 if not score['passed']:raise PipelineError('Preview lacks sustained movement')
 review=api.review_video(video,{'purpose':'Moving-video proof before full render','expected_actions':[s.get('motion',{}).get('activity','archival moving footage') for s in chosen]})
 save_json(out/'gemini-motion-review.json',review)
 if review.get('slideshow_like') or not review.get('genuine_character_action'):raise PipelineError('Gemini video review rejected slideshow-like preview')
 save_json(work/'preview-accepted.json',{'motion':score,'review':review})
 print('MOTION_PREVIEW '+str(video),flush=True)

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['plan','preview','full'],required=True);p.add_argument('--work',type=Path,default=ROOT/'work'/'animated');p.add_argument('--output',type=Path,default=ROOT/'output');a=p.parse_args(argv)
 try:
  api=MediaAPI(a.work/'gemini');script=read_json(a.work/'script.json');speech=read_json(a.work/'speech'/'speech.json')
  if a.stage=='plan':direct(api,script,read_json(a.work/'storyboard.json'),a.work);return 0
  shots=read_json(a.work/'motion-storyboard.json')
  if a.stage=='preview':preview(api,script,speech,shots,a.work,a.output/'motion-preview');return 0
  if not (a.work/'preview-accepted.json').exists():raise PipelineError('A genuinely moving preview must pass first')
  full,gaps=bridge(script,shots);request=read_json(a.work/'request.json');out=a.output/'moving-film'
  video=render(script,speech,full,a.work/'moving-render',out,request['profile'],interludes=gaps)
  from .quality import inspect
  quality=inspect(video,script,speech,{},out);quality.update(style='frame-by-frame-character-animation-with-archive',visual_beats=len(full),archival_clips=sum('archive' in s for s in full),interlude_seconds=sum(g['seconds'] for g in gaps),tts_provider='Gemini',tts_model=speech['model'])
  movement=measure(video,1.2,duration(video)-.5);save_json(out/'motion-check.json',movement)
  if not movement['passed']:raise PipelineError('Full film lacks sustained movement')
  save_json(out/'quality.json',quality)
  from .explainer_package import package
  package(api,script,read_json(a.work/'research.json'),speech,full,a.work,out)
  save_json(out/'production.json',{'request':request,'quality_passed':quality['passed'],'narration_reused':True,'preview_review':read_json(a.work/'preview-accepted.json'),'motion':movement})
  print('MOVING_FILM '+str(video),flush=True);return 0
 except PipelineError as e:
  a.output.mkdir(parents=True,exist_ok=True);save_json(a.output/'failure.json',{'error':str(e),'stage':a.stage});print('Stopped: '+str(e),flush=True);return 1
if __name__=='__main__':raise SystemExit(main())
