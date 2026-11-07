from __future__ import annotations
import json
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from .core import PipelineError, duration, ffmpeg, probe, read_json, save_json, public_text
from .maps import font


def thumbnail(script, assets, directory,output):
    candidates=[x for entry in assets.values() for x in entry['assets']]
    title=script['title']
    im=Image.new('RGB',(1280,720),(10,18,23))
    if candidates:
        with Image.open(directory/candidates[0]['path']) as source:
            art=ImageOps.fit(source.convert('RGB'),(800,720),method=Image.Resampling.LANCZOS)
        im.paste(art,(480,0))
    shade=Image.new('RGBA',im.size)
    d=ImageDraw.Draw(shade)
    for x in range(1280):
        alpha=255 if x<400 else max(0,255-round((x-400)*.55))
        d.line((x,0,x,720),fill=(8,16,23,alpha))
    im=Image.alpha_composite(im.convert('RGBA'),shade)
    d=ImageDraw.Draw(im)
    d.text((65,60),'HISTORY OF X',font=font(24,True),fill=(231,190,111))
    words=title.replace(':',' : ').split()
    lines=[];line=''
    for word in words:
        if d.textlength((line+' '+word).strip(),font=font(66,True))>650 and line:
            lines.append(line);line=word
        else:
            line=(line+' '+word).strip()
    if line:lines.append(line)
    # Full exact title in metadata; thumbnail uses a bounded legible excerpt.
    lines=lines[:5]
    y=190
    for line in lines:
        d.text((60,y),line,font=font(66,True),fill='white',stroke_width=1)
        y+=82
    d.line((65,140,220,140),fill=(231,190,111),width=5)
    d.text((65,650),'EMPIRES  •  CHOICES  •  CONSEQUENCES',font=font(20),fill=(210,215,217))
    im.convert('RGB').save(output/'thumbnail.jpg',quality=95)

def review_frames(video,output):
    length=duration(video)
    frames=[]
    for i in range(12):
        target=output/f'review-{i:02}.jpg'
        ffmpeg('-ss',str((i+.5)*length/12),'-i',video,'-frames:v','1','-vf','scale=480:270',target)
        frames.append(target)
    sheet=Image.new('RGB',(480*3,300*4),(10,16,22));draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(frames):
        with Image.open(path) as im:sheet.paste(im,(i%3*480,i//3*300))
        draw.text((i%3*480+10,i//3*300+274),f'{(i+.5)*length/12:.1f}s',font=font(17),fill='white')
        path.unlink()
    sheet.save(output/'contact-sheet.jpg',quality=92)

def inspect(video,script,speech,assets,output):
    metadata=probe(video)
    streams=metadata['streams']
    video_stream=next((s for s in streams if s['codec_type']=='video'),None)
    audio_stream=next((s for s in streams if s['codec_type']=='audio'),None)
    failures=[]
    if not video_stream or not audio_stream:
        failures.append('Missing video or audio stream')
    render_info=read_json(output/'render.json')
    expected=sum(s['duration'] for s in speech['scenes'])+render_info.get('credits_seconds',0)+render_info.get('interlude_seconds',0);actual=float(metadata['format']['duration'])
    if abs(actual-expected)>.5:
        failures.append('Video/audio duration mismatch')
    bad=[s['scene_id'] for s in speech['scenes'] if not s['verification']['accepted']]
    if bad:failures.append('Unverified speech scenes')
    # One complete pass checks decoding, black intervals and actual final AAC loudness.
    import subprocess
    detection=subprocess.run(['ffmpeg','-hide_banner','-nostdin','-i',str(video),'-vf','blackdetect=d=0.6:pix_th=0.10','-af','loudnorm=I=-16:TP=-1:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,timeout=max(600,actual*3))
    if detection.returncode:failures.append('Final media decode failed')
    loudness=re.findall(r'\{\s*"input_i".*?\}',detection.stderr,re.S)
    measured=json.loads(loudness[-1]) if loudness else {}
    if not measured:failures.append('Could not measure final encoded soundtrack')
    elif float(measured['input_tp'])>-.05:failures.append('Final soundtrack has insufficient clipping headroom')
    black=[float(x) for x in re.findall(r'black_duration:([\d.]+)',detection.stderr)]
    if any(x>1 for x in black):failures.append('Unexpected black interval over one second')
    unique=len({x['source_url'] for entry in assets.values() for x in entry['assets']})
    report={'passed':not failures,'failures':failures,'duration_seconds':actual,'expected_total_seconds':expected, 'narration_seconds':sum(s['duration'] for s in speech['scenes']), 'credits_seconds':render_info.get('credits_seconds',0),
        'voice':speech['voice'],'scene_count':len(script['scenes']),'unique_licensed_assets':unique,
        'speech_coverage_min':min(s['verification']['coverage'] for s in speech['scenes']),
        'speech_precision_min':min(s['verification']['precision'] for s in speech['scenes']),
        'caption_interpolated_words':sum(w.get('interpolated',False) for s in speech['scenes'] for w in s['words']),
        'black_intervals_seconds':black,'final_audio_lufs':float(measured['input_i']) if measured else None,
        'final_audio_true_peak_dbfs':float(measured['input_tp']) if measured else None,'video':video_stream,'audio':audio_stream,
        'review_needed':['Check historical visual relevance and pronunciation in contact sheet/video.',
                         'Script source references support review; automated checks do not certify historical accuracy.']}
    save_json(output/'quality.json',report)
    if failures:
        raise PipelineError('Final quality gate failed: '+'; '.join(failures))
    review_frames(video,output)
    return report

def package(script,evidence,speech,assets,job,output):
    import shutil
    for name,object in [('script.json',script),('sources.json',evidence),('asset-credits.json',assets)]:
        save_json(output/name,object)
    (output/'script.txt').write_text('\n\n'.join(s['chapter'].upper()+'\n'+s['narration'] for s in script['scenes']))
    (output/'title.txt').write_text(script['title']+'\n')
    timeline=read_json(output/'timeline.json')
    chapter_lines=[];seen=set()
    for x in timeline:
        if x['chapter'] not in seen:
            seen.add(x['chapter']);t=int(x['start']);chapter_lines.append(f'{t//60:02}:{t%60:02} {x["chapter"]}')
    t=int(sum(s['duration'] for s in speech['scenes']));chapter_lines.append(f'{t//60:02}:{t%60:02} Sources and credits')
    credits=[]
    for entry in assets.values():
        for a in entry['assets']:
            text=f'{a["title"]} — {a["artist"]} — {a["license"]}\n{a["source_url"]}\n{a.get("license_url", "")}\n{a["modifications"]}'
            if text not in credits:credits.append(text)
    music=read_json(output/'render.json')['music']
    catalog=read_json(Path(__file__).resolve().parents[1]/'assets'/'music'/'catalog.json')
    music_credits=[f'"{catalog[x]["title"]}" by Scott Buckley — CC BY 4.0\n{catalog[x]["source"]}\nhttps://creativecommons.org/licenses/by/4.0/\nExcerpted, looped, mixed and ducked under narration.' for x in music]
    sources=[f'{x["id"]}: {x["title"]}\n{x["url"]}' for x in evidence['sources']]
    description=script.get('summary','')+'\n\n'+'\n'.join(chapter_lines)+'\n\nSOURCES\n'+'\n\n'.join(sources)
    description+='\n\nVISUAL CREDITS\n'+'\n\n'.join(credits)+'\n\nMUSIC\n'+'\n\n'.join(music_credits)
    description+='\n\nNarration synthesized with Chatterbox Original using the selected project voice reference. Maps show present-day geography, not reconstructed historical borders. Historical images may depict the era rather than the exact narrated event.\n'
    (output/'sources-and-credits.txt').write_text(description)
    # YouTube's description length is bounded. Preserve the complete attribution file separately.
    if len(description)>4900:
        description=script.get('summary','')+'\n\n'+'\n'.join(chapter_lines)+'\n\n'+'\n\n'.join(sources)+'\n\n'+'\n\n'.join(music_credits)+'\n\nComplete visual attribution appears in the video end credits. The delivery package also includes a full sources-and-credits file.'
    (output/'description.txt').write_text(description[:4900])
    from html import escape
    (output/'credits.html').write_text('<!doctype html><meta charset="utf-8"><title>Sources and credits</title><style>body{max-width:900px;margin:40px auto;font:17px/1.6 sans-serif;white-space:pre-wrap}</style>'+escape((output/'sources-and-credits.txt').read_text()))
    thumbnail(script,assets,job,output)
