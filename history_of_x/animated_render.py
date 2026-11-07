"""Supersampled object animation with explicit timing; no camera-crop jitter."""
from __future__ import annotations
import json,math,re
from pathlib import Path
from PIL import Image,ImageDraw
from .core import ROOT,PipelineError,ffmpeg,key,read_json,save_json,duration
from .maps import font
from .render import PROFILES,concat_video,write_ass,srt_time
from .vector_art import icon,background,PALETTE,outlined_art

def fit_text(draw,text,width,size,bold=True):
 size=int(size)
 while size>22 and draw.textlength(text,font=font(size,bold))>width:size-=2
 return font(size,bold)

def plate(shot,path,width,height,elapsed,total):
 background(path,shot['background'],width,height)
 im=Image.open(path).convert('RGB');d=ImageDraw.Draw(im);s=width/1920
 ink=PALETTE['navy'] if shot['background']=='cream' else PALETTE['cream']
 # Only time and narrative meaning are displayed. No persistent channel/chapter chrome.
 year=shot['year_label'];d.text((int(110*s),int(70*s)),year,font=font(int(48*s),True),fill=ink)
 headline=shot['headline'];f=fit_text(d,headline,int(1700*s),int(100*s))
 d.text((width/2,int(225*s)),headline,font=f,fill=ink,anchor='mm')
 if len(shot['nodes'])==2 and shot['action'] in ('clash','exchange','balance'):
  # A relationship mark explains the composition instead of decorative UI.
  if shot['action']=='clash':
   d.line([(int(925*s),int(490*s)),(int(995*s),int(570*s))],fill=PALETTE['coral'],width=max(2,int(9*s)))
   d.line([(int(995*s),int(490*s)),(int(925*s),int(570*s))],fill=PALETTE['coral'],width=max(2,int(9*s)))
  elif shot['action']=='exchange':
   d.line([(int(900*s),int(515*s)),(int(1010*s),int(515*s))],fill=ink,width=max(2,int(7*s)))
   d.polygon([(int(1025*s),int(515*s)),(int(1000*s),int(500*s)),(int(1000*s),int(530*s))],fill=ink)
   d.line([(int(1010*s),int(550*s)),(int(900*s),int(550*s))],fill=ink,width=max(2,int(7*s)))
   d.polygon([(int(885*s),int(550*s)),(int(910*s),int(535*s)),(int(910*s),int(565*s))],fill=ink)
 y=int(1025*s);d.line((int(110*s),y,int(1810*s),y),fill='#D8CDBB' if shot['background']=='cream' else '#42566D',width=max(2,int(4*s)))
 if total:d.line((int(110*s),y,int((110+1700*elapsed/total)*s),y),fill=PALETTE['coral'],width=max(3,int(6*s)))
 im.save(path)

def node_layout(count,action):
 # All layouts preserve a safe lower caption area and a clear top time display.
 if count==1:return [(960,560,530)]
 if count==2:return [(570,560,480),(1350,560,480)]
 if count==3:
  return [(430,560,420),(960,550,460),(1490,560,420)]
 return [(320,560,350),(745,560,350),(1170,560,350),(1595,560,350)]

def shot_video(shot,directory,profile,elapsed,total):
 width,height,fps=PROFILES[profile];s=width/1920;factor=2 # all movement occurs on a 2x canvas before downsampling
 identity=key('vector-render-v5',shot,profile,elapsed,total);target=directory/(identity+'.mp4')
 seconds=shot['global_end']-shot['global_start'];frames=max(1,round(seconds*fps));seconds=frames/fps
 if target.exists() and abs(duration(target)-seconds)<.1:return target
 bg=directory/(identity+'-bg.png');plate(shot,bg,width*factor,height*factor,elapsed,total)
 inputs=['-loop','1','-framerate',str(fps),'-i',bg];layers=[]
 for i,(node,(cx,cy,size)) in enumerate(zip(shot['nodes'],node_layout(len(shot['nodes']),shot['action']))):
  pix=max(10,round(size*s*factor));art=outlined_art(icon(node['icon'],node['color'],pix),shot['background'])
  # Labels attach to their subject, and are included only when meaningful.
  labeled=Image.new('RGBA',(pix,round(pix*1.18)));labeled.paste(art,(0,0));d=ImageDraw.Draw(labeled)
  label=node['label'];ink=PALETTE['navy'] if shot['background']=='cream' else PALETTE['cream']
  if label:d.text((pix/2,pix*1.04),label,font=fit_text(d,label,pix*.95,round(36*s*factor)),fill=ink,anchor='mm')
  path=directory/f'{identity}-node-{i}.png';labeled.save(path);layers.append(path)
  inputs+=['-loop','1','-framerate',str(fps),'-i',path]
 graph=[f'[0:v]format=rgba,setsar=1[b0]']
 for i,(node,(cx,cy,size)) in enumerate(zip(shot['nodes'],node_layout(len(shot['nodes']),shot['action']))):
  delay=i*.09;settle=.52
  # Smooth cubic ease-out, evaluated per frame at supersampled resolution.
  progress=f'min(1,max(0,(t-{delay:.3f})/{settle}))';ease=f'(1-pow(1-({progress}),3))'
  x=(cx-size/2)*s*factor;y=(cy-size/2)*s*factor
  offset=(1 if i%2 else -1)*100*s*factor
  # Different narrative actions have different blocking, rather than identical canned pans.
  if shot['action']=='rise':dx='0';dy=f'{150*s*factor}*(1-{ease})'
  elif shot['action']=='fracture':dx=f'{offset}*min(1,max(0,(t-0.7)/1.1))';dy='0'
  elif shot['action']=='march':dx=f'{offset}*(1-{ease})+{18*s*factor}*t/{seconds}';dy='0'
  else:dx=f'{offset}*(1-{ease})';dy=f'{24*s*factor}*(1-{ease})'
  graph.append(f'[{i+1}:v]format=rgba,fade=t=in:st={delay}:d=0.16:alpha=1[n{i}]')
  graph.append(f"[b{i}][n{i}]overlay=x='{x}+({dx})':y='{y}+({dy})':eval=frame:shortest=1:format=auto[b{i+1}]")
 # Supersampling + explicit rgb->BT.709 conversion avoids integer crop jitter and flicker.
 graph.append(f'[b{len(layers)}]scale={width}:{height}:flags=lanczos:in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p[out]')
 ffmpeg(*inputs,'-filter_complex',';'.join(graph),'-map','[out]','-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-crf','19' if profile!='draft' else '24','-threads','2','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',target,timeout=max(180,seconds*40))
 for p in [bg,*layers]:p.unlink(missing_ok=True)
 return target

def captions(output,script,speech,width,height):
 # Caption-only ASS; no legacy chapter, channel, source or reference overlays.
 cues=[];offset=0
 for scene,spoken in zip(script['scenes'],speech['scenes']):
  cues.extend({**c,'start':offset+c['start'],'end':offset+c['end'],'highlights':scene['subtitle_highlights']} for c in spoken['captions']);offset+=spoken['duration']
 clean={**script,'scenes':[],'_speech':[]};write_ass(output/'captions.ass',cues,clean,width,height,offset)
 (output/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues)))
 return cues

def soundtrack(speech,shots,directory):
 import numpy as np,soundfile as sf
 total=sum(s['duration'] for s in speech['scenes']);rate=48000
 # Original restrained plucked ostinato, composed algorithmically. No third-party attribution chrome.
 length=round((total+.2)*rate);music=np.zeros(length,dtype=np.float32);sfx=np.zeros(length,dtype=np.float32)
 def note(buffer,at,hz,seconds,volume):
  n=min(round(seconds*rate),len(buffer)-round(at*rate))
  if n<=0:return
  t=np.arange(n)/rate;env=(1-np.exp(-t*100))*np.exp(-t*5)
  wave=(np.sin(2*np.pi*hz*t)+.18*np.sin(2*np.pi*hz*2*t))*env*volume
  start=round(at*rate);buffer[start:start+n]+=wave.astype(np.float32)
 for shot in shots:
  mood=shot.get('music_mood','neutral')
  serious=bool(re.search(r'\b(famine|massacre|killed|deaths|terror|repression|starv)',shot.get('narration_context',''),re.I))
  if serious:mood='somber'
  scale={'neutral':[130.8128,195.9977,164.8138,195.9977], 'playful':[261.6256,329.6276,391.9954,329.6276], 'tense':[130.8128,155.5635,195.9977,146.8324], 'somber':[130.8128,155.5635,174.6141,155.5635]}[mood]
  step={'neutral':.8,'playful':.4,'tense':.6,'somber':1.6}[mood]
  volume=.009 if mood=='somber' else .016
  for i,at in enumerate(np.arange(shot['global_start'],shot['global_end'],step)):
   note(music,float(at),scale[i%len(scale)],1.2 if mood=='somber' else .65,volume)
 for shot in shots:
  if shot['sting']:
   # Original three-note dry pluck; never a borrowed tune or a tragedy gag.
   for j,hz in enumerate([392,329.63,261.63]):note(sfx,shot['global_end']-.6+j*.18,hz,.35,.075)
  else:note(sfx,shot['global_start'],130.81,.12,.012)
 sf.write(directory/'music.wav',music,rate);sf.write(directory/'sfx.wav',sfx,rate)
 return total

def render(script,speech,shots,directory,output,profile='cinematic'):
 directory.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
 width,height,fps=PROFILES[profile];total=sum(s['duration'] for s in speech['scenes']);videos=[]
 # Frame rounding is cumulative, preventing one rounding error per shot from drifting the edit.
 frame_cursor=0
 for i,shot in enumerate(shots):
  endframe=round(shot['global_end']*fps);framed={**shot,'global_start':frame_cursor/fps,'global_end':endframe/fps}
  print(f'Animating beat {i+1}/{len(shots)}: {shot["text"][:65]}',flush=True)
  videos.append(shot_video(framed,directory,profile,shot['global_start'],total));frame_cursor=endframe
 silent=directory/'picture.mp4';concat_video(videos,silent)
 captions(output,script,speech,width,height)
 listing=directory/'voice.concat.txt';listing.write_text('\n'.join("file '"+str((directory.parent/'speech'/s['audio']).resolve()).replace("'","'\\''")+"'" for s in speech['scenes']))
 narration=directory/'narration.wav';ffmpeg('-f','concat','-safe','0','-i',listing,'-ar','48000','-ac','1',narration)
 soundtrack(speech,shots,directory)
 mixed=directory/'mixed.wav';chain='[0:a]asplit=2[v][side];[1:a][side]sidechaincompress=threshold=0.015:ratio=6:attack=15:release=250[m];[v][m][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.9[out]'
 ffmpeg('-i',narration,'-i',directory/'music.wav','-i',directory/'sfx.wav','-filter_complex',chain,'-map','[out]','-ar','48000','-ac','2',mixed)
 import subprocess
 measure=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(mixed),'-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,timeout=300)
 matches=re.findall(r'\{\s*"input_i".*?\}',measure.stderr,re.S)
 if not matches:raise PipelineError('Loudness measurement failed')
 loud=json.loads(matches[-1]);save_json(output/'loudness.json',loud)
 af=f'loudnorm=I=-16:TP=-1.5:LRA=9:measured_I={loud["input_i"]}:measured_TP={loud["input_tp"]}:measured_LRA={loud["input_lra"]}:measured_thresh={loud["input_thresh"]}:offset={loud["target_offset"]}:linear=true'
 escaped=str((output/'captions.ass').resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
 final=output/'final.mp4'
 ffmpeg('-i',silent,'-i',mixed,'-vf',f"ass=filename='{escaped}':fontsdir='{ROOT/'assets'/'fonts'}'",'-af',af,'-map','0:v','-map','1:a','-t',str(total),'-c:v','libx264','-preset','fast','-crf','19' if profile!='draft' else '24','-threads','2','-c:a','aac','-b:a','192k','-ar','48000','-pix_fmt','yuv420p','-movflags','+faststart',final,timeout=max(900,total*6))
 timeline=[{'scene_id':s['beat_id'],'start':s['global_start'],'end':s['global_end'],'year':s['year_label'],'spoken_text':s['text'],'headline':s['headline'],'nodes':s['nodes'],'rationale':s['rationale']} for s in shots]
 save_json(output/'timeline.json',timeline);save_json(output/'render.json',{'style':'original-flat-animation','profile':profile,'width':width,'height':height,'fps':fps,'duration':duration(final),'narration_seconds':total,'credits_seconds':0,'voice':speech['voice'],'tts_provider':'Gemini','tts_model':speech['model'],'shots':len(shots),'music':['original local instrumental and stings']})
 return final
