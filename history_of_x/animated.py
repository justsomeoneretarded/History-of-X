"""Gemini-first animated history runner. All accepted stages are resumable."""
from __future__ import annotations
import argparse,os
from pathlib import Path
from .core import ROOT,PipelineError,key,read_json,save_json
from .media_api import MediaAPI,VOICES
from .gemini import QuotaDeferred

def parser():
 p=argparse.ArgumentParser(description='Original animated history explainer, Gemini text + Gemini speech')
 p.add_argument('--title',default=os.getenv('VIDEO_TITLE',''))
 p.add_argument('--brief',default=os.getenv('VIDEO_BRIEF',''))
 p.add_argument('--voice',choices=VOICES,default=os.getenv('NARRATOR') or 'Puck')
 p.add_argument('--minutes',type=float,default=float(os.getenv('VIDEO_MINUTES') or '8'))
 p.add_argument('--profile',choices=['draft','standard','cinematic'],default=os.getenv('VIDEO_PROFILE') or 'cinematic')
 p.add_argument('--preset',choices=['auto','ethiopia'],default=os.getenv('PRESET') or 'auto')
 p.add_argument('--stage',choices=['all','plan','voice','direct','render'],default='all')
 p.add_argument('--work',type=Path,default=ROOT/'work'/'animated')
 p.add_argument('--output',type=Path,default=ROOT/'output')
 return p

def main(argv=None):
 args=parser().parse_args(argv);args.work.mkdir(parents=True,exist_ok=True);args.output.mkdir(parents=True,exist_ok=True)
 try:
  if not args.title.strip() or not args.brief.strip():raise PipelineError('Title and brief are required')
  if len(args.title)>200 or len(args.brief)>6000 or not .5<=args.minutes<=10:raise PipelineError('Title max200 chars, brief max6000, target 0.5–10 minutes')
  request={k:getattr(args,k) for k in ['title','brief','voice','minutes','profile','preset']};identity=key('animated-v1',request)
  path=args.work/'request.json'
  if path.exists() and read_json(path).get('id')!=identity:raise PipelineError('Work directory contains another request; use a new directory')
  save_json(path,{'id':identity,**request});api=MediaAPI(args.work/'gemini')
  if args.stage in ('all','plan'):
   if args.preset=='ethiopia':
    evidence=read_json(ROOT/'episodes'/'ethiopia.json')['evidence'];save_json(args.work/'research.json',evidence)
   else:
    from .research import research
    evidence=research(args.title,args.brief,args.work)
   from .explainer_plan import write
   write(api,args.title,args.brief,args.minutes,evidence,args.work)
  script=read_json(args.work/'script.json');evidence=read_json(args.work/'research.json')
  if args.stage in ('all','voice'):
   from .gemini_speech import produce
   produce(api,script,args.voice,args.work/'speech')
  if args.stage in ('all','direct'):
   from .explainer_plan import direct
   direct(api,script,read_json(args.work/'speech'/'speech.json'),args.work)
  if args.stage in ('all','render'):
   speech=read_json(args.work/'speech'/'speech.json');base=read_json(args.work/'storyboard.json')
   from .motion_director import direct as choreograph
   from .archival_motion import bridge
   shots,interludes=bridge(script,base if all(s.get('motion') for s in base) else choreograph(api,script,base,args.work))
   from .animated_render import render
   video=render(script,speech,shots,args.work/'render',args.output,args.profile,interludes=interludes)
   from .quality import inspect
   report=inspect(video,script,speech,{},args.output)
   lengths=[s['global_end']-s['global_start'] for s in shots]
   report.update(style='frame-by-frame-character-animation-with-archive',tts_provider='Gemini',tts_model=speech['model'],visual_beats=len(shots),visual_duration_min=min(lengths),visual_duration_max=max(lengths),on_screen_branding=False,review_needed=['Motion and technical checks are recorded; no added manual factual review.'])
   if any(not 3<=v<=6 for v in lengths):raise PipelineError('A visual beat falls outside the 3–6 second rhythm')
   save_json(args.output/'quality.json',report)
   from .explainer_package import package
   package(api,script,evidence,speech,shots,args.work,args.output)
   review_schema={'type':'object','required':['issues','strengths','ready_for_human_review'],'properties':{'issues':{'type':'array','items':{'type':'string'}},'strengths':{'type':'array','items':{'type':'string'}},'ready_for_human_review':{'type':'boolean'}}}
   review=api.vision('Critique this contact sheet from an original animated history explainer. Check clutter, text readability, visual diversity and relevance to its storyboard. Do not claim to have watched motion or heard audio. Identify specific issues honestly. Only year counter, essential narrative labels and captions should be visible.',{'title':script['title'],'sample_storyboard':[{'spoken':s['text'],'visual':s['headline'],'nodes':s['nodes']} for s in shots[::max(1,len(shots)//12)]]},[args.output/'contact-sheet.jpg'],review_schema)
   save_json(args.output/'gemini-visual-review.json',review)
   save_json(args.output/'production.json',{'request':request,'quality_passed':report['passed'],'request_id':identity,'gemini_review':review})
   print('FINAL_VIDEO '+str(video),flush=True)
  return 0
 except (PipelineError,ValueError,KeyError,FileNotFoundError) as e:
  save_json(args.output/'failure.json',{'error':str(e),'stage':args.stage,'resume':'Use identical inputs and recover prior run checkpoint.'})
  print('Production stopped: '+str(e),flush=True);return 75 if isinstance(e,QuotaDeferred) else 1

if __name__=='__main__':raise SystemExit(main())
