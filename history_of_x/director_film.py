"""Reference-informed editorial production. Scene-specific executable animation, not activity loops."""
from __future__ import annotations
import argparse,base64,json,math,os,re,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from .core import ROOT,PipelineError,read_json,save_json,key,ffmpeg,duration

CRAFT='''Create an ORIGINAL history documentary with clear, conversational storytelling.
Jerusalem is the writing/runtime reference: a central question, concrete human stakes, short varied sentences,
causal transitions, compressed stable centuries and a thoughtful payoff. Pig War is the motion reference:
specific acting and reactions, readable staging, visual setup then consequence, different locations and props,
comedy from choices and contradictions. Britain/Rome/Egypt inform varied illustrated staging and scale.
Do not reproduce any creator's characters, visual signature, joke, catchphrase, dialogue, or melody.
Every scene must show what the spoken passage MEANS, not merely a noun from it.
No channel names, source labels, decorative headings, references, watermarks, UI cards, or filler words.
Only a discreet year counter is added by the editor. Meaningful short labels are allowed when explanatory.
Treat suffering seriously. No tragedy punchlines. No fake historical photographs or invented quotations.'''

ILLUSTRATION_BIBLE={
 'style':'Original editorial cartoon illustration: warm ivory, deep indigo, terracotta, muted turquoise, gold accents. Dark confident outlines, selective soft gradients, layered scenic depth. No round white stickman heads or copied creator characters.',
 'faces':'Distinctive human silhouettes, warm varied skin tones, almond eyes, shaped noses and eyebrows, clean expressive mouths. Period clothing defines roles, not generic crowns.',
 'continuity':'A named person retains the same face, clothes, proportions and colors across their scenes. Include period-specific accessories sparingly. Menelik and Taytu are distinct leading characters, not anonymous officials.',
 'staging':'Subjects remain large and readable. Establish space before a reversal. Anticipation, contact and reaction have different timing. Short holds let the viewer understand a consequence. Real object contact and continuous ownership; no floating body parts.',
 'composition':'Deliberate wide/medium/detail changes, foreground depth, restrained shadows. Avoid the same palace, table or centered symmetrical composition in successive scenes.'}

def plan_scene(api,scene,spoken,assets,directory,style=None):
 from .scene_film import schema,validate_scene
 seconds=round(spoken['duration'],6)
 catalog={a['id']:a for a in assets['assets']}
 candidates=[catalog[x] for x in assets['scenes'].get(str(scene['scene_id']),[]) if x in catalog and catalog[x].get('medium') not in ('video','archival_video')]
 archives=[catalog[x] for x in assets['scenes'].get(str(scene['scene_id']),[]) if x in catalog and catalog[x].get('medium')=='archival_video'][:2]
 archive_seconds=4.5*len(archives) if seconds>12 else 0
 fingerprint=key('director-scene-v3',scene,seconds,candidates,style)
 target=directory/(fingerprint+'.json')
 if target.exists():return read_json(target)
 prompt=CRAFT+'''
You are also a skilled vector illustrator and animation director. Return a complete executable layered SVG
scene program, NOT a description of an animation, not a slideshow, not a handful of icon cards.
SVG viewBox is 0 0 1920 1080. Its top-level g elements have unique ids. Every top-level group has a layer entry.
Use detailed original illustration: foreground/midground/background, coherent light/shadow, period clothing,
recognizable place/architecture where appropriate, expressive faces, clear silhouettes and strong focal hierarchy.
Avoid generic columns, samey rooms, generic crowned stickmen, arrays of interchangeable soldiers, and floating papers.
Draw full bodies/clothes and expressive eyes/brows/mouths. Separate hands/arms/heads/props into animated layers
when an action requires them. Give each shot its own composition. Use paths, polygons and restrained gradients.
Layer parent is optional: use parent="body_layer_id" on articulated parts to inherit the body's transform.
All artwork remains in world coordinates; rotate arms around shoulders and hands around wrists. Keep limbs
attached, and hold props at the hand until an explicit ownership transfer. No detached floating arms.
Do not put tiny detail everywhere; large readable actors, carefully composed scenery, distinctive silhouettes.
Choose the appropriate mode: acted reconstruction, explanatory diagram, geographic sequence, authentic media,
or a blend. A meaningful map is useful only for geography; don't show maps by default.
Authentic images may be used with <image href="asset:EXACT_ID" x="..." y="..." width="..." height="..."/>.
Use at most two embedded authentic images in a scene. The attached reference images also guide original drawing.
The editor resolves only approved asset IDs. Use a photo as editorial imagery, never an absurd picture frame
on a battlefield. Do not force an available asset into a mismatched era or subject.
Each layer's x/y are offsets from its original SVG position. pivot is in SVG world coordinates.
Keyframes carry time,x,y,scale,rotation,opacity,reveal,ease. reveal is a left-to-right wipe from0to1.
Use hold for an intentional pause, smooth/ease_in/ease_out for acting, linear for continuous travel.
All times must be between0 and scene duration. Specify initial and final keyframes for every layer.
Camera keyframes have the same properties, centred at960,540. Use scale1orhigher, x/y offsets; avoid shakes.
No automatic idle loops. Every movement has a reason: reach/contact/transfer/reaction, assemble/alter/remove,
advance/separate/encircle, obstacle/decision/consequence. Show several stages with timing tied to spoken words.
Include at least three meaningful events for scenes over12seconds and at least one visual development
per3–6seconds. Events name the layers that actually move/change. The keyframes must EXECUTE those events.
An optional event.sfx may request paper, stamp, soft_impact or sting for a specific contact or harmless comic
payoff. Use these sparingly. No automatic effect on every cut, and no comedy stings during suffering.
Changing a caption, drifting the camera or waving an arm does not by itself explain a political event.
For a treaty dispute: display two short differing obligations, reveal the mismatch, show a rejection and response.
For a divided army: establish opposing positions, show separate columns diverging, then opposition exploiting gaps.
These are examples, not a template to repeat. Match THIS passage. Keep top-left180x90clear for the year.
If reserved_archival_opening_seconds is nonzero, the editor places the supplied genuine footage over that
opening interval under the narration. Do not put indispensable SVG actions in that interval. Start the
illustrated setup immediately afterward, and budget its actions to fit the remaining time. Archive intervals
can be noted as events with empty layer_ids; never pretend the SVG itself recreates the archival footage.
Use a rich professional illustrated palette, clean linework and depth. SVG text uses DejaVu Sans.
No embedded scripts, external links, foreignObject, SVGanimate, style imports or XMLentities. Only executable
keyframe data animates the scene. Keep SVG under100000characters. Duration must equal supplied seconds.
Return valid JSON exactly matching schema. scene_id must equal the supplied string id.'''
 payload={'scene':scene,'duration':seconds,'scene_id':str(scene['scene_id']),
  'word_timing':spoken['words'],'approved_assets':[{k:a.get(k) for k in ['id','subject','date','context']} for a in candidates],
  'reference_craft':style or {},'illustration_bible':ILLUSTRATION_BIBLE,
  'reserved_archival_opening_seconds':archive_seconds,'opening_archive_subjects':[a['subject'] for a in archives]}
 # Resolve only explicitly approved local assets. No URL fetching inside generated SVG.
 def embed(match):
  ident=match.group(1)
  if ident not in {a['id'] for a in candidates}:raise PipelineError('Director referenced an unapproved media asset')
  record=catalog[ident];p=Path(record['path']);p=p if p.is_absolute() else ROOT/p
  with Image.open(p) as im:
   import io
   im=im.convert('RGB');im.thumbnail((1280,800));out=io.BytesIO();im.save(out,format='JPEG',quality=82)
  return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
 for attempt in range(2):
  # Show the director actual approved historical imagery, not just asset filenames.
  images=[]
  for a in candidates[:3]:
   p=Path(a['path']);p=p if p.is_absolute() else ROOT/p
   try:
    with Image.open(p) as im:
     im=im.convert('RGB');im.thumbnail((800,600));ref=directory/(key('director-art-reference',a['id'])+'.jpg');im.save(ref,quality=85)
    images.append(ref)
   except (OSError,ValueError):continue
  result=api.vision(prompt+'\nAttached images are approved historical subject references, not art to copy blindly. Match the supplied context and dates.',payload,images,schema(),max_output=18000) if images else api.text(prompt,payload,schema(),max_output=18000)
  save_json(directory/(fingerprint+f'-draft-{attempt}.json'),result)
  try:
   result['duration']=seconds;result['scene_id']=str(scene['scene_id'])
   result['asset_ids']=list(dict.fromkeys(re.findall(r'asset:([A-Za-z0-9_.-]+)',result['svg'])))
   if len(result['asset_ids'])>2:raise PipelineError('Use at most two embedded historical images per scene')
   result['svg']=re.sub(r'asset:([A-Za-z0-9_.-]+)',embed,result['svg'])
   validate_scene(result)
   events=sorted(result['events'],key=lambda e:e['time'])
   if seconds>12 and (len(events)<3 or any(b-a>7 for a,b in zip([0]+[e['time'] for e in events],[e['time'] for e in events]+[seconds]))):
    raise PipelineError('Scene lacks meaningful staged developments within the requested 3–6 second rhythm')
   save_json(target,result);return result
  except (PipelineError,KeyError,ValueError) as exc:
   if attempt:raise PipelineError('Scene director failed bounded revision: '+str(exc)) from exc
   payload={**payload,'previous_draft':read_json(directory/(fingerprint+'-draft-0.json')),'validation_error':str(exc),
    'revision_request':'Correct the executable scene. Preserve visual quality and meaningful acting. Return a complete valid program.'}
 raise PipelineError('No valid directed scene')

def editorial_review(api,video,style,output):
 # Actual video+audio; an honest craft assessment, never a pixel-motion pass.
 schema={'type':'object','required':['verdict','scores','observations','problems','revision_priorities'],
 'properties':{'verdict':{'type':'string','enum':['ready','revise','reject']},
 'scores':{'type':'object','required':['visual_specificity','acting','composition','narration_delivery','editorial_pacing'],
 'properties':{k:{'type':'integer','minimum':1,'maximum':10} for k in ['visual_specificity','acting','composition','narration_delivery','editorial_pacing']}},
 'observations':{'type':'array','items':{'type':'string'}},'problems':{'type':'array','items':{'type':'string'}},
 'revision_priorities':{'type':'array','items':{'type':'string'}}}}
 prompt=CRAFT+'''
Watch and listen to the supplied actual output. Evaluate it critically as a history video director.
Reference craft analysis is context, not proof of a match. Do NOT claim to have watched any reference
unless supplied as actual media here. Report timestamped observations and specific shortcomings.
Does acting visibly communicate decisions and consequences? Does narration sound naturally spoken?
Are scenes bespoke, varied and relevant, or generic SVG figures/cards with meaningless movement?
Technical movement alone merits no credit. Don't praise merely because limbs move. Judge illustration,
composition, blocking, comic timing, clarity, rhythmic variation, audio and overall editorial finish.
Reject incoherent staging, badly drawn/overlapping actors, tiny illegible labels, random asset insertion,
or repetitive same-background scenes. Score honestly. This is NOT historical fact verification.
ready requires every category>=7 and no major craft failure; otherwise revise or reject.'''
 parts=[{'text':prompt+'\nREFERENCE CRAFT DATA:\n'+json.dumps(style or {})},
 {'inlineData':{'mimeType':'video/mp4','data':base64.b64encode(Path(video).read_bytes()).decode()}}]
 model=os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite')
 result=api.request(model,'models/'+model+':generateContent',{'contents':[{'role':'user','parts':parts}],
 'generationConfig':{'temperature':.15,'maxOutputTokens':5000,'responseMimeType':'application/json',
 'responseJsonSchema':schema,'thinkingConfig':{'thinkingLevel':'LOW'}}},'text')
 report=json.loads(''.join(p.get('text','') for p in result['candidates'][0]['content']['parts'] if not p.get('thought')))
 save_json(output/'editorial-review.json',report);return report

def package(api,script,speech,assets,output,work):
 from .typography import font
 save_json(output/'script.json',script);save_json(output/'media-credits.json',assets)
 (output/'script.txt').write_text('\n\n'.join(s['chapter'].upper()+'\n'+s['narration'] for s in script['scenes']))
 metadata_path=work/'directed-packaging.json'
 metadata_id=key('directed-packaging-v1',script['title'],[s['narration'] for s in script['scenes']])
 metadata_schema={'type':'object','required':['title','thumbnail_hook','description'], 'properties':{'title':{'type':'string'},'thumbnail_hook':{'type':'string'},'description':{'type':'string'}}}
 previous=read_json(metadata_path) if metadata_path.exists() else {}
 metadata=previous if previous.get('fingerprint')==metadata_id else api.text(
  'Package this original history video for YouTube. Return a clear searchable title naming the subject, a concrete truthful thumbnail curiosity hook of2–4short words (not the full title), and a concise description of the actual scope and endpoint. No fake quotes, sensational invented claims, marketing filler, channel branding or technical implementation details. The hook should be readily legible on a mobile thumbnail. Do not copy any reference title.',
  {'working_title':script['title'],'summary':script['summary'],'opening':script['scenes'][0]['narration'],'ending':script['scenes'][-1]['narration']},metadata_schema,max_output=1200)
 metadata['fingerprint']=metadata_id;save_json(metadata_path,metadata)
 (output/'title.txt').write_text(metadata['title']+'\n')
 # Authentic large portrait/architecture: purposeful composition, no tiny icon collage.
 photos=[a for a in assets['assets'] if a.get('medium') not in ('video','archival_video')]
 subjects=sorted(photos,key=lambda a:('menelik' not in a.get('subject','').lower(), 'adwa' not in a.get('subject','').lower()))
 im=Image.new('RGB',(1280,720),'#102934')
 if subjects:
  p=Path(subjects[0]['path']);p=p if p.is_absolute() else ROOT/p
  with Image.open(p) as picture:im.paste(ImageOps.fit(picture.convert('RGB'),(760,720),centering=(.5,.3)),(520,0))
 shade=Image.new('RGBA',im.size)
 d=ImageDraw.Draw(shade)
 for x in range(1280):d.line((x,0,x,720),fill=(9,27,34,255 if x<420 else max(0,255-int((x-420)*.6))))
 im=Image.alpha_composite(im.convert('RGBA'),shade);d=ImageDraw.Draw(im)
 title='ETHIOPIA' if 'ethiop' in script['title'].lower() else script['title'].split(':')[0].upper()[:18]
 d.text((58,115),title,font=font(76,True),fill='#F4D588')
 words=metadata['thumbnail_hook'].upper().split()[:5];middle=max(1,math.ceil(len(words)/2))
 for i,line in enumerate([' '.join(words[:middle]),' '.join(words[middle:])]):
  size=88
  while size>36 and d.textlength(line,font=font(size,True))>620:size-=2
  d.text((58,255+i*105),line,font=font(size,True),fill='white')
 im.convert('RGB').save(output/'thumbnail.jpg',quality=95)
 chapters=[];position=0;seen=set()
 for scene,spoken in zip(script['scenes'],speech['scenes']):
  if scene['chapter'] not in seen:
   seen.add(scene['chapter']);n=int(position);chapters.append(f'{n//60:02}:{n%60:02} {scene["chapter"]}')
  position+=spoken['duration']
 text=metadata['description']+'\n\n'+'\n'.join(chapters)+'\n\nOriginal illustrated reconstructions and licensed historical media.\n'
 credits='\n\n'.join(f'{a["subject"]} — {a.get("creator","Historical archive")} — {a["license"]}\n{a["source_url"]}\n{a.get("license_url","")}' for a in assets['assets'])
 sources=read_json(output/'sources.json') if (output/'sources.json').exists() else {'sources':[]}
 evidence='\n'.join(s['title']+'\n'+s['url'] for s in sources['sources'])
 music=(output/'music-credits.txt').read_text() if (output/'music-credits.txt').exists() else ''
 full=text+'\nSOURCES\n'+evidence+'\n\nHISTORICAL MEDIA\n'+credits+'\n\nMUSIC\n'+music
 (output/'sources-and-credits.txt').write_text(full)
 # Attribution must remain accessible in upload metadata; no in-frame credit clutter.
 description=full
 if len(description)>4900:
  # PD/CC0 attribution is retained in full delivery credits; preserve required CC BY attribution in upload metadata.
  required=[a for a in assets['assets'] if not any(x in a['license'].casefold() for x in ['public domain','cc0'])]
  compact='\n\n'.join(f'{a["subject"]} — {a.get("creator","Historical archive")} — {a["license"]}\n{a["source_url"]}\n{a.get("license_url","")}' for a in required)
  description=text+'\nSOURCES\n'+'\n'.join(s['url'] for s in sources['sources'])+'\n\nVISUAL ATTRIBUTION\n'+compact+'\n\nMUSIC\n'+music
 if len(description)>4900:raise PipelineError('Required attribution exceeds YouTube description budget; reduce used CC BY assets')
 (output/'description.txt').write_text(description)

def produce(api,work,output,profile='cinematic',proof=False,resume=None,revise=False):
 from .documentary_assets import catalog
 from .scene_film import render_scene
 from .render import PROFILES,concat_video,ass_time
 from .audio_edit import mix
 from .quality import inspect
 script=read_json(work/'script.json');speech=read_json(work/'speech'/'speech.json')
 metrics_path=work/'narration-metrics.json'
 if not proof and metrics_path.exists() and not read_json(metrics_path).get('runtime_within_10_percent_of_target',True):
  raise PipelineError('Narration misses the requested runtime; revise performance before a full-film render')
 style_path=ROOT/'assets'/'style'/'director.json'
 style=read_json(work/'style-profile.json') if (work/'style-profile.json').exists() else read_json(style_path) if style_path.exists() else {'narration_wpm':174,'median_sentence_words':10,'runtime_seconds':525.58}
 report_path=ROOT/'assets'/'style'/'reference-study.json'
 if report_path.exists():style={**style,'video_reference_study':read_json(report_path)}
 if revise and (work/'editorial-feedback.json').exists():style={**style,'required_creative_revision':read_json(work/'editorial-feedback.json')}
 assets=catalog(script,work/'media')
 if proof:
  # Opening and later acted narrative samples, preserving each complete spoken scene.
  acted=next((i for i,s in enumerate(script['scenes']) if s['chapter']=='Catalyst' and 'treaty' in s['narration'].lower()),next((i for i,s in enumerate(script['scenes']) if s['chapter']=='Catalyst'),max(0,len(script['scenes'])//2)))
  roots=next((i for i,s in enumerate(script['scenes']) if s['chapter']=='Roots'),min(1,len(script['scenes'])-1))
  selected=list(dict.fromkeys([0,roots,acted]))
  script={**script,'scenes':[script['scenes'][i] for i in selected]}
  speech={**speech,'scenes':[speech['scenes'][i] for i in selected]}
 output.mkdir(parents=True,exist_ok=True);directory=work/'directed-render';directory.mkdir(parents=True,exist_ok=True)
 plan_dir=work/'scene-programs';plan_dir.mkdir(parents=True,exist_ok=True)
 videos=[];shots=[];position=0;fps=PROFILES[profile][2];frame_cursor=0;used_assets=set()
 for scene,spoken in zip(script['scenes'],speech['scenes']):
  print(f'Directing original scene {scene["scene_id"]}: {scene["narration"][:90]}',flush=True)
  program=plan_scene(api,scene,spoken,assets,plan_dir,style)
  used_assets.update(program.get('asset_ids',[]))
  end_frame=round((position+spoken['duration'])*fps)
  program={**program,'duration':(end_frame-frame_cursor)/fps}
  # Float precision in exact output frame duration must not invalidate last keyframe.
  for layer in [*program['layers'],program.get('camera',{})]:
   if 'end' in layer:layer['end']=min(layer['end'],program['duration'])
   unique={}
   for k in layer.get('keyframes',[]):
    k['time']=min(k['time'],program['duration']);unique[k['time']]=k
   if 'keyframes' in layer:layer['keyframes']=list(unique.values())
  program['events']=[{**e,'time':min(e['time'],program['duration'])} for e in program['events']]
  picture=render_scene(program,directory,profile)
  # Authentic archive appears under the corresponding narration, never as a disconnected pause.
  archives=[a for a in assets['assets'] if a['id'] in assets['scenes'].get(str(scene['scene_id']),[]) and a.get('medium')=='archival_video']
  if archives and spoken['duration']>12:
   archive_parts=[]
   for a in archives[:2]:
    ap=directory/(key('directed-archive-v1',a['id'],profile)+'.mp4');w,h,_=PROFILES[profile]
    ffmpeg('-i',a['path'],'-vf',f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x102934,setsar=1,fps={fps}','-t','4.5','-an','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',ap)
    archive_parts.append(ap);used_assets.add(a['id'])
   archive_seconds=4.5*len(archive_parts);tail=directory/(key('archive-tail',str(picture))+'.mp4')
   ffmpeg('-ss',str(archive_seconds),'-i',picture,'-an','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',tail)
   combined=directory/(key('archive-under-narration',str(picture))+'.mp4');concat_video([*archive_parts,tail],combined);picture=combined
  videos.append(picture)
  shots.append({'scene_id':scene['scene_id'],'global_start':position,'global_end':position+spoken['duration'],
   'chapter':scene['chapter'],'narration_context':scene['narration'],'music_mood':'neutral' if scene['chapter']=='Roots' else 'somber' if scene['bg_music_mood']=='reflective' else 'tense' if scene['bg_music_mood']=='tense' else 'neutral','sting':False,'events':program.get('events',[]),'year_label':scene['date_label']})
  position+=spoken['duration'];frame_cursor=end_frame
 silent=directory/'picture.mp4';concat_video(videos,silent)
 from .animated_render import captions
 width,height,_=PROFILES[profile];captions(output,script,speech,width,height)
 # Year counter only; captions supplied separately for viewer control.
 header=(output/'captions.ass').read_text().split('[Events]')[0]
 years=header+'[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'
 for shot in shots:
  safe=shot['year_label'].replace('{','').replace('}','').replace('\\','')
  years+=f'Dialogue: 0,{ass_time(shot["global_start"])},{ass_time(shot["global_end"])},Date,,0,0,0,,{{\\an7\\pos({round(width*.035)},{round(height*.035)})\\fs{round(width*.021)}}}{safe}\n'
 (output/'years.ass').write_text(years)
 from .director_sound import compose
 mixed,af,_=mix(speech,shots,work/'speech',directory,[],output,soundtrack_builder=compose)
 for name in ['music-credits.json','music-credits.txt','soundtrack.json']:
  if (directory/name).exists():shutil.copy2(directory/name,output/name)
 escaped=str((output/'years.ass').resolve()).replace(':','\\:').replace("'","\\'")
 final=output/'final.mp4'
 ffmpeg('-i',silent,'-i',mixed,'-vf',f"ass=filename='{escaped}'",'-af',af,'-map','0:v','-map','1:a','-t',str(position),'-c:v','libx264','-preset','fast','-crf','18','-threads','2','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',final,timeout=max(900,position*6))
 music=read_json(output/'music-credits.json') if (output/'music-credits.json').exists() else []
 save_json(output/'render.json',{'style':'directed-layered-animation','duration':duration(final),'profile':profile,'credits_seconds':0,'interlude_seconds':0,'music':music,'voice':speech['voice']})
 save_json(output/'timeline.json',shots)
 asset_map={'film':{'assets':[{'source_url':a['source_url']} for a in assets['assets']]}}
 technical=inspect(final,script,speech,asset_map,output)
 save_json(output/'sources.json',read_json(work/'research.json'))
 if 'ethiop' in script['title'].lower():
  hero=next((a for a in assets['assets'] if 'menelik' in a.get('subject','').lower() and a.get('medium')=='historical_photo'),None)
  if hero:used_assets.add(hero['id'])
 used={**assets,'assets':[a for a in assets['assets'] if a['id'] in used_assets]}
 package(api,script,speech,used,output,work)
 sample=output/'review.mp4'
 if position>100:
  # Send the entire film, including audio, with a bounded payload. No three-excerpt acceptance shortcut.
  ffmpeg('-i',final,'-vf','scale=640:360','-c:v','libx264','-b:v','180k','-maxrate','220k','-bufsize','440k','-c:a','aac','-b:a','64k',sample,timeout=max(900,position*4))
 else:ffmpeg('-i',final,'-vf','scale=960:540','-c:v','libx264','-crf','27','-c:a','aac','-b:a','80k',sample)
 review=editorial_review(api,sample,style,output)
 save_json(work/'editorial-feedback.json',review)
 acceptable=review['verdict']=='ready' and min(review['scores'].values())>=7
 request=read_json(work/'request.json') if (work/'request.json').exists() else {}
 save_json(output/'production.json',{'technical_passed':technical['passed'],'editorial_accepted':acceptable,'proof':proof,'reference_craft_used':style,'runtime_target_seconds':request.get('minutes',8.75)*60,'runtime_seconds':position,'editorial_review_scope':'entire candidate at reduced resolution, with audio'})
 if not acceptable:raise PipelineError('Creative review requires revision; output is a review candidate, not upload-ready')
 print('DIRECTED_FILM '+str(final),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=ROOT/'work'/'director');p.add_argument('--output',type=Path,default=ROOT/'output'/'director');p.add_argument('--profile',choices=['draft','standard','cinematic'],default='cinematic');p.add_argument('--proof',action='store_true');p.add_argument('--revise',action='store_true');args=p.parse_args()
 from .media_api import MediaAPI
 try:produce(MediaAPI(args.work/'gemini'),args.work,args.output,args.profile,args.proof,revise=args.revise)
 except (PipelineError,ValueError,KeyError,FileNotFoundError) as exc:
  save_json(args.output/'failure.json',{'error':str(exc)});print(str(exc),flush=True);return 1
 return 0

if __name__=='__main__':raise SystemExit(main())
