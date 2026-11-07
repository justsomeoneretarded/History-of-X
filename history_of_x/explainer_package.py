"""Gemini-directed YouTube packaging with no in-video attribution clutter."""
from __future__ import annotations
from PIL import Image,ImageDraw
from .core import PipelineError,save_json,read_json
from .typography import font
from .vector_art import ICONS,PALETTE,icon,outlined_art
from .animated_render import fit_text

def thumbnail_plan(api,script,directory):
 node={'type':'object','required':['icon','color'],'properties':{'icon':{'type':'string','enum':list(ICONS)},'color':{'type':'string','enum':['coral','teal','gold','violet','blue']}}}
 schema={'type':'object','required':['youtube_title','description','concepts'],'properties':{'youtube_title':{'type':'string','maxLength':95},'description':{'type':'string','maxLength':1000},'concepts':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'object','required':['text','nodes','background','rationale'],'properties':{'text':{'type':'string','maxLength':24},'nodes':{'type':'array','minItems':2,'maxItems':2,'items':node},'background':{'type':'string','enum':['cream','navy']},'rationale':{'type':'string'}}}}}}
 return api.text('''You package original animated history explainers for YouTube. Create two distinct thumbnail concepts with a bold 2–4 word hook, TWO large symbolic subjects, strong contrast and readable silhouette at phone size. No full-title paragraphs, no channel name, no tiny text, no sources, no fake quotes or unsupported claims. The text complements rather than repeats the video title. The YouTube title must name the subject and make a truthful curiosity promise. Description states historical endpoint, summarizes angle, no marketing filler. Choose icons from schema; these are flat original illustrations.''',{'title':script['title'],'summary':script['summary'],'script':[s['narration'] for s in script['scenes']]},schema,max_output=3500)

def draw_thumbnail(concept,path,index=0):
 # Compose above target resolution, preserving clean typography on upload.
 scale=2;im=Image.new('RGB',(2560,1440),PALETTE[concept['background']]);d=ImageDraw.Draw(im)
 ink=PALETTE['navy'] if concept['background']=='cream' else PALETTE['cream']
 d.polygon([(1430,0),(2560,0),(2560,1440),(1080,1440)],fill=PALETTE['coral'] if index==0 else PALETTE['teal'])
 # Large subject silhouettes face a central tension, not an unreadable historical collage.
 for node,cx,cy,sz in [(concept['nodes'][0],690,740,1000),(concept['nodes'][1],1930,740,1000)]:
  art=outlined_art(icon(node['icon'],node['color'],sz),concept['background'] if cx<1280 else 'cream');im.paste(art,(cx-sz//2,cy-sz//2),art)
 # Separate text into no more than two short lines with a solid, high-contrast base.
 words=concept['text'].upper().split();split=max(1,(len(words)+1)//2);lines=[' '.join(words[:split]),' '.join(words[split:])];lines=[l for l in lines if l]
 d.rounded_rectangle((170,1010,2390,1370),radius=40,fill=PALETTE['navy'])
 y=1080 if len(lines)==2 else 1160
 for line in lines:
  f=fit_text(d,line,2120,140);d.text((1280,y),line,font=f,fill=PALETTE['cream'],anchor='mm',stroke_width=1);y+=150
 im.resize((1280,720),Image.Resampling.LANCZOS).save(path,quality=95,optimize=True)

def package(api,script,evidence,speech,shots,directory,output):
 cache=directory/'packaging.json'
 plan=read_json(cache) if cache.exists() else thumbnail_plan(api,script,directory)
 save_json(cache,plan)
 candidates=[]
 for i,concept in enumerate(plan['concepts']):
  target=output/f'thumbnail-option-{i+1}.jpg';draw_thumbnail(concept,target,i);candidates.append(target)
 schema={'type':'object','required':['selected','reason','issues'],'properties':{'selected':{'type':'integer','minimum':1,'maximum':2},'reason':{'type':'string'},'issues':{'type':'array','items':{'type':'string'}}}}
 choice=api.vision('Choose the stronger YouTube thumbnail at mobile size. Judge readability, clear subject, truthful relevance, contrast and composition. Image order is option 1 then option 2. Report concrete weaknesses; do not give automatic praise.',{'title':plan['youtube_title'],'concepts':plan['concepts']},candidates,schema)
 import shutil
 shutil.copy2(candidates[choice['selected']-1],output/'thumbnail.jpg');save_json(output/'thumbnail-review.json',choice)
 save_json(output/'packaging-plan.json',plan);save_json(output/'script.json',script);save_json(output/'sources.json',evidence);save_json(output/'storyboard.json',shots)
 (output/'title.txt').write_text(plan['youtube_title']+'\n')
 (output/'script.txt').write_text('\n\n'.join(s['chapter'].upper()+'\n'+s['narration'] for s in script['scenes']))
 chapters=[];position=0;seen=set()
 for scene,spoken in zip(script['scenes'],speech['scenes']):
  if scene['chapter'] not in seen:
   seen.add(scene['chapter']);t=int(position);chapters.append(f'{t//60:02}:{t%60:02} {scene["chapter"]}')
  position+=spoken['duration']
 sources='\n\n'.join(s['title']+'\n'+s['url'] for s in evidence['sources'])
 description=plan['description']+'\n\n'+'\n'.join(chapters)+'\n\nSOURCES\n'+sources+'\n\nNarration: Gemini '+speech['model']+' ('+speech['voice']+'). Original simplified illustrations and locally synthesized instrumental music; illustrations are explanatory, not archival depictions. Source excerpts adapted from Wikipedia are CC BY-SA 4.0; article histories identify contributors. https://creativecommons.org/licenses/by-sa/4.0/\n'
 if len(description)>4900:raise PipelineError('Upload description exceeds bounded length')
 (output/'description.txt').write_text(description)
 (output/'sources-and-credits.txt').write_text(description+'\n\nSource revision and license details are recorded in sources.json. No third-party photographs or music are used in this animated version.\n')
 from html import escape
 (output/'credits.html').write_text('<!doctype html><meta charset="utf-8"><title>Sources</title><pre>'+escape((output/'sources-and-credits.txt').read_text())+'</pre>')
