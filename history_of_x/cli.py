from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from .core import ROOT, PipelineError, key, save_json, read_json, slug


def parser():
    p=argparse.ArgumentParser(description='Generate a documentary from a title and brief. Warguy is the default narrator.')
    p.add_argument('--title',default=os.getenv('VIDEO_TITLE',''))
    p.add_argument('--brief',default=os.getenv('VIDEO_BRIEF',''))
    p.add_argument('--voice',choices=['warguy','kit-laser'],default=os.getenv('NARRATOR','warguy'))
    p.add_argument('--minutes',type=float,default=float(os.getenv('VIDEO_MINUTES','8')))
    p.add_argument('--profile',choices=['draft','standard','cinematic'],default=os.getenv('VIDEO_PROFILE','cinematic'))
    p.add_argument('--chapter',type=int,choices=range(1,6),help='Generate only this chapter in a parallel voice job.')
    p.add_argument('--stage',choices=['all','plan','voice','render'],default='all')
    p.add_argument('--episode',type=Path,help='Use a curated episode file with script/evidence, bypassing Gemini only when explicitly selected.')
    p.add_argument('--request',type=Path,help='Read title/brief/voice/minutes from a production request JSON.')
    p.add_argument('--work',type=Path,default=ROOT/'work'/'job')
    p.add_argument('--output',type=Path,default=ROOT/'output')
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.request:
            data=read_json(args.request)
            for name in ['title','brief','voice','minutes','profile']:
                if name in data:setattr(args,name,data[name])
            if data.get('episode'):args.episode=ROOT/data['episode']
        if not args.title.strip() or not args.brief.strip():
            raise PipelineError('Provide both a title and a small brief.')
        if len(args.title)>200 or len(args.brief)>6000 or not .25<=float(args.minutes)<=60:
            raise PipelineError('Title max 200 characters, brief max 6000, runtime 0.25–60 minutes.')
        if args.voice not in ('warguy','kit-laser') or args.profile not in ('draft','standard','cinematic'):
            raise PipelineError('Invalid voice or profile')
        args.work=args.work.resolve();args.output=args.output.resolve()
        args.work.mkdir(parents=True,exist_ok=True)
        request={'title':args.title,'brief':args.brief,'voice':args.voice,'minutes':args.minutes,'profile':args.profile,
                 'episode':str(args.episode) if args.episode else None}
        request_id=key(request, args.episode.read_text() if args.episode else '')
        state=args.work/'request.json'
        if state.exists() and read_json(state).get('id')!=request_id:
            # Never overwrite another episode's accepted work.
            raise PipelineError('Work directory belongs to another request. Use a new --work directory.')
        save_json(state,{'id':request_id,**request})
        if args.stage in ('all','plan'):
            if args.episode:
                episode=read_json(args.episode)
                evidence=episode['evidence'];script=episode['script']
                from .script import validate
                validate(script,[x['id'] for x in evidence['sources']])
                save_json(args.work/'script.json',script);save_json(args.work/'research.json',evidence)
            else:
                from .research import research
                from .script import generate
                evidence=research(args.title,args.brief,args.work)
                script=generate(args.title,args.brief,float(args.minutes),evidence,args.work)
            from .assets import prepare
            prepare(script,args.work,min_assets=1 if float(args.minutes)<1 else min(60,max(3,round(float(args.minutes)*1.2))))
            print('Plan and licensed assets ready.',flush=True)
        script=read_json(args.work/'script.json');evidence=read_json(args.work/'research.json')
        if args.stage in ('all','voice'):
            from .speech import produce
            if args.chapter:
                from .script import CHAPTERS
                subset={**script,'scenes':[s for s in script['scenes'] if s['chapter']==CHAPTERS[args.chapter-1]]}
                produce(subset,args.voice,args.work/'speech'/f'chapter-{args.chapter}')
            else:
                produce(script,args.voice,args.work/'speech')
        if args.stage in ('all','render'):
            from .render import render
            from .quality import inspect,package
            from .speech_merge import merge
            if not (args.work/'speech'/'speech.json').exists():
                merge(script,args.voice,args.work/'speech')
            speech=read_json(args.work/'speech'/'speech.json')
            assets=read_json(args.work/'assets'/'index.json')
            video=render(script,speech,assets,args.work/'render',args.output,args.profile)
            package(script,evidence,speech,assets,args.work,args.output)
            report=inspect(video,script,speech,assets,args.output)
            save_json(args.output/'production.json',{'request':request,'quality_passed':report['passed'],'source_request_id':request_id})
            print(f'FINAL_VIDEO {video}',flush=True)
        return 0
    except (PipelineError,ValueError,KeyError,FileNotFoundError) as e:
        print(f'Production stopped: {e}',file=sys.stderr)
        args.output.mkdir(parents=True,exist_ok=True)
        save_json(args.output/'failure.json',{'type':type(e).__name__,'message':str(e),'stage':args.stage,
                                            'resume':'Re-run with the same request and work directory; completed assets and speech are retained.'})
        return 75 if type(e).__name__=='QuotaDeferred' else 1

if __name__=='__main__':
    raise SystemExit(main())
