"""Deterministic cinematic edit: pan/zoom shots, restrained typography, timed captions."""
from __future__ import annotations
import json
import math
import re
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFilter
from .core import ROOT, PipelineError, duration, ffmpeg, key, save_json, read_json, run, public_text, probe
from .maps import font, draw_map

PROFILES = {'draft':(960,540,24), 'standard':(1920,1080,30), 'cinematic':(1920,1080,30)}

def _strict_audio_decode(path):
    ffmpeg('-i',path,'-f','null','-')

def ass_time(seconds):
    cs=max(0,round(seconds*100))
    return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def srt_time(seconds):
    ms=max(0,round(seconds*1000))
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def highlighted(text, highlights):
    text=public_text(text)
    terms=set(re.sub(r'\W','',w.casefold()) for h in highlights for w in h.split())
    return ' '.join((r'{\c&H75D8F2&}'+w+r'{\c&HFFFFFF&}') if re.sub(r'\W','',w.casefold()) in terms else w for w in text.split())

def write_ass(path, cues, script, width,height,total):
    scale=width/1920
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Caption,DejaVu Sans,{round(64*scale)},&H00FFFFFF,&H00FFFFFF,&H00201612,&H80000000,-1,0,0,0,100,100,0,0,1,{max(1,round(3*scale))},1,2,{round(100*scale)},{round(100*scale)},{round(100*scale)},1
Style: Chapter,DejaVu Sans,{round(27*scale)},&H0075D8F2,&H00FFFFFF,&H00201612,&H80000000,-1,0,0,0,100,100,3,0,1,1,1,7,{round(80*scale)},{round(80*scale)},{round(65*scale)},1
Style: Date,DejaVu Sans,{round(34*scale)},&H00FFFFFF,&H00FFFFFF,&H00201612,&H80000000,0,0,0,0,100,100,1,0,1,1,1,9,{round(80*scale)},{round(80*scale)},{round(65*scale)},1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events=[]
    for cue in cues:
        start,end=max(0,cue['start']),min(total,cue['end'])
        if end<=start:
            continue
        text=highlighted(cue['text'],cue.get('highlights',[]))
        events.append(f'Dialogue: 2,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{{\\fad(50,70)}}{text}')
    position=0
    for scene,spoken in zip(script['scenes'],script['_speech']):
        end=position+spoken['duration']
        label=f'{scene["chapter"].upper()}  /  HISTORY OF X'
        events.append(f'Dialogue: 1,{ass_time(position)},{ass_time(end)},Chapter,,0,0,0,,{public_text(label)}')
        if scene.get('date_label'):
            events.append(f'Dialogue: 1,{ass_time(position)},{ass_time(min(end,position+8))},Date,,0,0,0,,{public_text(scene["date_label"])}')
        position=end
    path.write_text(header+'\n'.join(events)+'\n')

def prepare_image(source, output, width,height,style='cinematic'):
    with Image.open(source) as im:
        source=im.convert('RGB')
        canvas=(round(width*1.18),round(height*1.18))
        im=ImageOps.fit(source,canvas,method=Image.Resampling.LANCZOS,centering=(.5,.40))
        if source.width/source.height<1.15:
            im=im.filter(ImageFilter.GaussianBlur(max(12,width/70)))
            portrait=ImageOps.contain(source,(round(canvas[0]*.82),round(canvas[1]*.88)),method=Image.Resampling.LANCZOS)
            im.paste(portrait,((canvas[0]-portrait.width)//2,(canvas[1]-portrait.height)//2))
    if style=='cinematic':
        im=ImageEnhance.Color(im).enhance(.78)
        im=ImageEnhance.Contrast(im).enhance(1.08)
        # Soft vignette + lower-third shadow support readable captions without covering subjects.
        small=Image.new('L',(160,90))
        pix=small.load()
        for y in range(90):
            for x in range(160):
                r=((x-80)/100)**2+((y-40)/60)**2
                pix[x,y]=min(150,int(40*r+max(0,y-54)*2.3))
        shade=small.resize(im.size,Image.Resampling.BICUBIC)
        im=Image.composite(Image.new('RGB',im.size,(3,9,15)),im,shade)
    im.save(output,quality=94)

def shot_plan(seconds, records, map_path, is_map=False, profile='cinematic'):
    hold=6.0 if profile!='draft' else 7.0
    count=max(1,math.ceil(seconds/hold))
    sources=[Path(x['absolute_path']) for x in records]
    if is_map:
        sources=[map_path,*sources]
    if not sources:
        sources=[map_path]
    return [{'source':str(sources[i%len(sources)]),'seconds':seconds/count,'motion':i%4} for i in range(count)]

def motion_filter(frames,width,height,fps,motion,enabled=True):
    # One source frame emits exactly the required output frames. Bounded zoom avoids out-of-frame crops.
    if not enabled:
        return f'scale={width}:{height},setsar=1,fps={fps}'
    if motion==0:
        z=f'1.02+0.075*on/{max(1,frames-1)}';x='iw/2-iw/zoom/2';y='ih/2-ih/zoom/2'
    elif motion==1:
        z=f'1.095-0.075*on/{max(1,frames-1)}';x='iw/2-iw/zoom/2';y='ih/2-ih/zoom/2'
    else:
        z='1.08';x=f'(iw-iw/zoom)*on/{max(1,frames-1)}' if motion==2 else f'(iw-iw/zoom)*(1-on/{max(1,frames-1)})';y='ih/2-ih/zoom/2'
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps},setsar=1"

def concat_video(paths, output):
    listing=output.with_suffix('.concat.txt')
    # Paths are generated hashes underneath the job workspace, not user text.
    listing.write_text('\n'.join("file '"+str(Path(p).resolve()).replace("'","'\\''")+"'" for p in paths))
    ffmpeg('-f','concat','-safe','0','-i',listing,'-c','copy',output)

def render_scene(scene, spoken, records, map_path, directory,profile):
    width,height,fps=PROFILES[profile]
    signature=key('render-v7',scene,spoken['duration'],records,str(map_path),profile)
    output=directory/(signature+'.mp4')
    if output.exists() and abs(duration(output)-spoken['duration'])<.15:
        return output
    shots=shot_plan(spoken['duration'],records,map_path,scene['visual_type']=='map',profile)
    pieces=[]
    frame_total=round(spoken['duration']*fps)
    for i,shot in enumerate(shots):
        frames=frame_total//len(shots)+(i<frame_total%len(shots))
        picture=directory/f'{signature}-{i}.jpg'
        part=directory/f'{signature}-{i}.mp4'
        if not part.exists():
            prepare_image(shot['source'],picture,width,height,profile)
            vf=motion_filter(frames,width,height,fps,shot['motion'])
            # Fade only at narrative scene boundaries, with hard cuts inside a beat.
            if i==0:
                vf+=',fade=t=in:st=0:d=0.12'
            if i==len(shots)-1:
                vf+=f',fade=t=out:st={max(0,frames/fps-.12):.4f}:d=0.12'
            vf+=',scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p'
            encoding=['-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast',
                '-crf','20' if profile!='draft' else '24','-pix_fmt','yuv420p','-color_range','tv',
                '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-threads','2',part]
            if Path(shot['source'])==map_path and i==0:
                # Fade the geographic highlight into a neutral map. Both states use identical
                # geometry; this animation never implies invented historical border changes.
                neutral=picture.with_name(picture.stem+'-neutral.jpg')
                with Image.open(picture) as im:
                    ImageEnhance.Color(im).enhance(.08).save(neutral,quality=94)
                moving=vf.replace(f':d={frames}:',':d=1:')
                graph=f'[0:v]fps={fps},settb=AVTB[a];[1:v]fps={fps},settb=AVTB[b];[a][b]xfade=transition=fade:duration=1:offset=0,{moving}[out]'
                ffmpeg('-loop','1','-i',neutral,'-loop','1','-i',picture,'-filter_complex',graph,'-map','[out]',*encoding)
                neutral.unlink(missing_ok=True)
            else:
                ffmpeg('-i',picture,'-vf',vf,*encoding)
        pieces.append(part)
        picture.unlink(missing_ok=True)
    concat_video(pieces,output)
    for p in pieces:
        p.unlink(missing_ok=True)
    save_json(output.with_suffix('.json'),{'scene_id':scene['scene_id'],'shots':shots,'frames':frame_total,'profile':profile})
    return output

def music_bed(output,seconds,mood='tense'):
    file={'tense':'titan','reflective':'celestial','resolute':'aurora'}[mood]
    source=ROOT/'assets'/'music'/f'{file}.ogg'
    # Crossfade consecutive excerpts so repeated music does not click at loop boundaries.
    length=duration(source)
    repeats=max(1,math.ceil(seconds/max(1,length-3)))
    if repeats==1:
        ffmpeg('-i',source,'-t',str(seconds),'-af','apad','-ar','48000','-ac','2',output)
        return file
    inputs=[]
    for _ in range(repeats):
        inputs+=['-i',source]
    chain=[];previous='0:a'
    for i in range(1,repeats):
        label=f'm{i}'
        chain.append(f'[{previous}][{i}:a]acrossfade=d=3:c1=tri:c2=tri[{label}]')
        previous=label
    ffmpeg(*inputs,'-filter_complex',';'.join(chain),'-map',f'[{previous}]','-t',str(seconds),'-ar','48000','-ac','2',output)
    return file

def render(script,speech,assets,directory,output,profile='cinematic'):
    width,height,fps=PROFILES[profile]
    directory.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    script={**script,'_speech':speech['scenes']}
    map_path=directory/'reference-map.jpg'
    focus='Ethiopia' if 'ethiopi' in (script['title']+' '+' '.join(x.get('location','') for x in script['scenes'])).casefold() else 'World'
    draw_map(map_path,directory,width,height,focus)
    videos=[];audios=[];cues=[];timeline=[];position=0
    for scene,spoken in zip(script['scenes'],speech['scenes']):
        if scene['scene_id']!=spoken['scene_id']:
            raise PipelineError('Speech/scene ordering mismatch')
        entry=assets.get(str(scene['scene_id']),{'assets':[]})
        records=[{**x,'absolute_path':str(directory.parent/x['path'])} for x in entry['assets']]
        print(f'Rendering scene {scene["scene_id"]}/{len(script["scenes"])}',flush=True)
        videos.append(render_scene(scene,spoken,records,map_path,directory,profile))
        audios.append(directory.parent/'speech'/spoken['audio'])
        for cue in spoken['captions']:
            cues.append({**cue,'start':position+cue['start'],'end':position+cue['end'],'highlights':scene['subtitle_highlights']})
        timeline.append({'scene_id':scene['scene_id'],'chapter':scene['chapter'],'start':position,'end':position+spoken['duration'],
                         'asset_sources':[x['source_url'] for x in records], 'map_fallback':not records})
        position+=spoken['duration']
    silent=directory/'picture.mp4';concat_video(videos,silent)
    audio_list=directory/'audio.concat.txt'
    audio_list.write_text('\n'.join("file '"+str(p.resolve()).replace("'","'\\''")+"'" for p in audios))
    narration=directory/'narration.wav'
    ffmpeg('-f','concat','-safe','0','-i',audio_list,'-ar','48000','-ac','1','-c:a','pcm_s24le',narration)
    position=duration(narration)
    subtitle=output/'captions.ass';write_ass(subtitle,cues,script,width,height,position)
    (output/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues)))
    # Music changes with chapters; crossfaded bed clips are concatenated at quiet chapter edges.
    music_parts=[];music_used=[]
    grouped=[]
    for scene,spoken in zip(script['scenes'],speech['scenes']):
        if grouped and grouped[-1]['chapter']==scene['chapter']:
            grouped[-1]['seconds']+=spoken['duration']
        else:
            grouped.append({'chapter':scene['chapter'],'seconds':spoken['duration'],'mood':scene.get('bg_music_mood','tense')})
    for i,g in enumerate(grouped):
        part=directory/f'music-{i}.wav'
        mood=g['mood'] if g['mood'] in ('tense','reflective','resolute') else 'reflective'
        music_used.append(music_bed(part,g['seconds'],mood))
        faded=directory/f'music-faded-{i}.wav'
        ffmpeg('-i',part,'-af',f'afade=t=in:d=1.2,afade=t=out:st={max(0,g["seconds"]-1.5)}:d=1.5','-c:a','pcm_s16le',faded)
        music_parts.append(faded)
    music_list=directory/'music.concat.txt';music_list.write_text('\n'.join("file '"+str(p.resolve())+"'" for p in music_parts))
    bed=directory/'music.wav';ffmpeg('-f','concat','-safe','0','-i',music_list,'-c:a','pcm_s16le',bed)
    # Original synthesized transition cue, intentionally subtle and limited to chapter boundaries.
    import numpy as np
    import soundfile as sf
    rate=48000;fx=np.zeros(round((position+.5)*rate),dtype=np.float32)
    offsets=[x['start'] for i,x in enumerate(timeline) if i==0 or timeline[i-1]['chapter']!=x['chapter']]
    for offset in offsets:
        t=np.arange(int(.6*rate))/rate
        pulse=.055*np.sin(2*np.pi*(74*t-22*t*t))*np.exp(-t*10)
        start=round(offset*rate);n=min(len(pulse),len(fx)-start)
        fx[start:start+n]+=pulse[:n]
    sfx=directory/'sfx.wav';sf.write(sfx,fx,rate)
    mixed=directory/'mixed.wav'
    chain='[0:a]asplit=2[voice][side];[1:a]volume=0.15[music];[music][side]sidechaincompress=threshold=0.018:ratio=8:attack=25:release=500[duck];[voice][duck][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.89[out]'
    ffmpeg('-i',narration,'-i',bed,'-i',sfx,'-filter_complex',chain,'-map','[out]','-ar','48000','-ac','2',mixed)
    # Two-pass loudness normalization is reproducible; retain measured values in report.
    measurement=__import__('subprocess').run(['ffmpeg','-hide_banner','-nostdin','-i',str(mixed),'-af','loudnorm=I=-16:TP=-1:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,timeout=300)
    matches=re.findall(r'\{\s*"input_i".*?\}',measurement.stderr,re.S)
    if not matches:
        raise PipelineError('Could not measure mixed soundtrack loudness')
    loud=json.loads(matches[-1]);save_json(output/'loudness.json',loud)
    af=f'loudnorm=I=-16:TP=-1:LRA=9:measured_I={loud["input_i"]}:measured_TP={loud["input_tp"]}:measured_LRA={loud["input_lra"]}:measured_thresh={loud["input_thresh"]}:offset={loud["target_offset"]}:linear=true'
    # Subtitle path uses generated safe job directory; escape filter metacharacters for local CLI paths.
    escaped=str(subtitle.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    final=output/'final.mp4'
    ffmpeg('-i',silent,'-i',mixed,'-vf',f"ass=filename='{escaped}'",'-af',af,'-map','0:v','-map','1:a',
           '-c:v','libx264','-preset','fast','-crf','19' if profile!='draft' else '24','-threads','2',
           '-c:a','aac','-b:a','192k','-ar','48000','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart','-t',str(position),final,timeout=max(900,position*8))
    from .credits import append
    credits_seconds, credits_pages=append(final,assets,list(dict.fromkeys(music_used)),directory,width,height,fps)
    save_json(output/'timeline.json',timeline)
    save_json(output/'render.json',{'profile':profile,'width':width,'height':height,'fps':fps,'duration':duration(final),
                                  'music':list(dict.fromkeys(music_used)), 'narration_seconds':position, 'credits_seconds':credits_seconds, 'credits_pages':credits_pages, 'voice':speech['voice'], 'shots':sum(len(read_json(p.with_suffix('.json'))['shots']) for p in videos)})
    return final
