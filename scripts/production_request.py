"""Configure a reviewed production request and expose visual evidence in Actions logs."""
from __future__ import annotations
import argparse,base64,json,os,subprocess,uuid
from pathlib import Path
from history_of_x.media_api import TEXT_MODELS, VOICES as GEMINI_VOICES

VOICES={'auto',*GEMINI_VOICES}

def validate(config):
    if not isinstance(config,dict):raise ValueError('Production request must be an object')
    if not isinstance(config.get('title'),str) or not 1<=len(config['title'].strip())<=200:raise ValueError('Title must contain1–200characters')
    if not isinstance(config.get('brief'),str) or not 1<=len(config['brief'].strip())<=6000:raise ValueError('Brief must contain1–6000characters')
    if config.get('voice','auto') not in VOICES:raise ValueError('Unsupported narrator')
    if not .5<=float(config.get('minutes',8.75))<=10:raise ValueError('Runtime must be0.5–10minutes')
    if config.get('phase','proof') not in {'proof','film'}:raise ValueError('Phase must beprooforfilm')
    if config.get('profile','cinematic') not in {'draft','cinematic'}:raise ValueError('Unsupported render profile')
    if config.get('director_model','gemini-3.5-flash-lite') not in TEXT_MODELS:raise ValueError('Unsupported free director model')
    if config.get('writer_model','gemini-3.5-flash-lite') not in TEXT_MODELS:raise ValueError('Unsupported free writer model')
    if config.get('review_model','gemini-3.5-flash-lite') not in TEXT_MODELS or str(config.get('review_model','')).startswith('gemma-'):raise ValueError('Unsupported free audiovisual review model')
    if config.get('package_model','gemini-3.5-flash-lite') not in TEXT_MODELS:raise ValueError('Unsupported free packaging model')
    if str(config.get('scene_batch_size',1)) not in {'1','2','3'}:raise ValueError('Scene batch size must be1–3')
    if config.get('resume_run') and not str(config['resume_run']).isdigit():raise ValueError('Checkpoint run ID must be numeric')
    if config.get('phase','proof')=='film' and not str(config.get('resume_run','')).isdigit():raise ValueError('Full production requires a reviewed proof checkpoint run')
    return config

def configure(request_file=None):
    root=Path.cwd().resolve()
    if not request_file:
        changed=subprocess.check_output(['git','diff','--name-only','HEAD^','HEAD','--','production/requests/'],text=True).splitlines()
        files=[p for p in changed if p.endswith('.json')]
        if len(files)!=1:raise ValueError('Commit exactly one production request JSON at a time')
        request_file=files[0]
    path=(root/request_file).resolve()
    path.relative_to(root/'production'/'requests')
    config=validate(json.loads(path.read_text()))
    fields={'VIDEO_TITLE':config['title'],'VIDEO_BRIEF':config['brief'],'VIDEO_MINUTES':str(config.get('minutes',8.75)),
      'NARRATOR':config.get('voice','auto'),'REQUEST_PHASE':config.get('phase','proof'),'FILM_PROFILE':config.get('profile','cinematic'),
      'RESUME_RUN':str(config.get('resume_run','')),'DIRECTOR_MODEL':config.get('director_model','gemini-3.5-flash-lite'),
      'WRITER_MODEL':config.get('writer_model','gemini-3.5-flash-lite'),'REVIEW_MODEL':config.get('review_model','gemini-3.5-flash-lite'),'PACKAGE_MODEL':config.get('package_model','gemini-3.5-flash-lite'),'GEMINI_SCENE_BATCH_SIZE':str(config.get('scene_batch_size',1)),
      'SCRIPT_TARGET_WPM':str(config.get('script_target_wpm',160)),'REVISE_FILM':str(config.get('revise',False)).lower()}
    with open(os.environ['GITHUB_ENV'],'a') as stream:
        for name,value in fields.items():
            delimiter='history_'+uuid.uuid4().hex
            stream.write(name+'<<'+delimiter+'\n'+value+'\n'+delimiter+'\n')
    print('PRODUCTION_REQUEST '+json.dumps(config,ensure_ascii=False))

def evidence():
    output=Path('output/director');work=Path('work/director')
    progress=work/'runner-progress.json'
    if not (output/'final.mp4').exists() and progress.exists():
        candidate=Path(json.loads(progress.read_text()).get('candidate',''))
        if candidate.is_dir() and candidate.resolve().is_relative_to(output.resolve()):
            output=candidate
    data={}
    for name in ['production.json','quality.json','editorial-review.json','failure.json','timeline.json','media-credits.json']:
        path=output/name
        if path.exists():data[name]=json.loads(path.read_text())
    for name in ['writing-metrics.json','narration-metrics.json','runner-progress.json','script.json','draft-script.json','failure.json']:
        path=work/name
        if path.exists():data[name]=json.loads(path.read_text())
    print('DIRECTOR_EVIDENCE_START\n'+json.dumps(data,ensure_ascii=False)+'\nDIRECTOR_EVIDENCE_END',flush=True)
    movie=output/'final.mp4';timeline=data.get('timeline.json',[])
    if not movie.exists():return
    from PIL import Image,ImageDraw
    from history_of_x.core import ffmpeg
    frames=output/'evidence';frames.mkdir(exist_ok=True)
    # Six successive states per scene let a reviewer verify action and reactions.
    chosen=timeline if len(timeline)<=4 else [timeline[i] for i in sorted({0,len(timeline)//3,2*len(timeline)//3,len(timeline)-1})]
    sheet=Image.new('RGB',(1920,max(1,len(chosen))*210),'#102934');draw=ImageDraw.Draw(sheet)
    for row,shot in enumerate(chosen):
        for col,fraction in enumerate([.04,.2,.4,.6,.8,.96]):
            at=shot['global_start']+(shot['global_end']-shot['global_start'])*fraction
            path=frames/f'{row}-{col}.jpg'
            ffmpeg('-ss',str(at),'-i',movie,'-frames:v','1','-vf','scale=320:180',path)
            with Image.open(path) as im:sheet.paste(im,(col*320,row*210))
            draw.text((col*320+8,row*210+184),f'{at:.2f}s / scene{shot["scene_id"]}',fill='white')
    image_path=output/'temporal-evidence.jpg';sheet.save(image_path,quality=82,optimize=True)
    encoded=base64.b64encode(image_path.read_bytes()).decode()
    print('DIRECTOR_IMAGE_START',flush=True)
    for i in range(0,len(encoded),8000):print('DIRECTOR_IMAGE_CHUNK '+encoded[i:i+8000],flush=True)
    print('DIRECTOR_IMAGE_END',flush=True)
    thumbnail=output/'thumbnail.jpg'
    if thumbnail.exists():
        encoded=base64.b64encode(thumbnail.read_bytes()).decode()
        print('DIRECTOR_THUMBNAIL_START',flush=True)
        for i in range(0,len(encoded),8000):print('DIRECTOR_THUMBNAIL_CHUNK '+encoded[i:i+8000],flush=True)
        print('DIRECTOR_THUMBNAIL_END',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['configure','evidence']);parser.add_argument('--request')
    args=parser.parse_args()
    if args.stage=='configure':configure(args.request)
    else:evidence()

if __name__=='__main__':main()
