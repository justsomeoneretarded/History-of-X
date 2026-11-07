"""Primary-archive moving footage and credits; archival dates never become fake battle footage."""
from pathlib import Path
import hashlib
from PIL import Image,ImageDraw
from .core import ROOT,PipelineError,read_json,save_json,ffmpeg,key
from .typography import font

def bridge(script,shots):
 if 'ethiop' not in script['title'].lower():return shots,[]
 catalog=read_json(ROOT/'assets'/'footage'/'catalog.json')
 boundary=next((s['global_start'] for s in shots if script['scenes'][s['scene_id']-1]['chapter']=='Aftermath'),None)
 if boundary is None:return shots,[]
 result=[];inserted=False
 for shot in shots:
  if not inserted and shot['global_start']>=boundary:
   for i,item in enumerate(catalog):
    path=ROOT/item['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise PipelineError('Archive clip checksum failed')
    result.append({'beat_id':item['id'],'scene_id':0,'global_start':boundary+i*4.5,'global_end':boundary+(i+1)*4.5,'text':'','narration_context':'','year_label':'1935','year':1935,'sting':False,'music_mood':'somber','headline':'','nodes':[], 'archive':item,'rationale':item['context']})
   inserted=True
  shift=9 if inserted else 0
  result.append({**shot,'global_start':shot['global_start']+shift,'global_end':shot['global_end']+shift})
 return result,[{'at':boundary,'seconds':9,'before_scene_id':next(s['scene_id'] for s in shots if s['global_start']>=boundary)}]

def render_clip(shot,directory,profile):
 from .render import PROFILES
 width,height,fps=PROFILES[profile];item=shot['archive'];out=directory/(key('archive-cut-v1',item,profile)+'.mp4')
 if out.exists():return out
 tag=Image.new('RGBA',(round(width*.19),round(height*.075)),(255,241,216,245));d=ImageDraw.Draw(tag);d.text((round(width*.014),round(height*.012)),'1935',font=font(round(width*.022),True),fill='#172B3C')
 png=directory/'archive-year.png';tag.save(png)
 graph=f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x172B3C,setsar=1,fps={fps}[film];[film][1:v]overlay={round(width*.018)}:{round(height*.03)}:format=auto,format=yuv420p[v]'
 ffmpeg('-i',ROOT/item['path'],'-i',png,'-filter_complex',graph,'-map','[v]','-an','-t','4.5','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',out)
 return out

def credits(shots):
 result=[]
 for shot in shots:
  item=shot.get('archive') or shot.get('motion',{}).get('photo_credit')
  if item:
   entry={k:item.get(k,'') for k in ['title','creator','artist','source_url','license','license_url','date','path','bundled_path']}
   if entry not in result:result.append(entry)
 return result
