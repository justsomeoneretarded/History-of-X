"""Visible end credits keep attribution with the uploaded film, without external hosting."""
from __future__ import annotations
import textwrap
from PIL import Image,ImageDraw
from .core import ROOT, ffmpeg, duration, read_json
from .maps import font

def credit_lines(assets,music):
    lines=['VISUALS: cropped, graded and animated from the credited sources.','']
    seen=set()
    for entry in assets.values():
        for a in entry['assets']:
            if a['source_url'] in seen:continue
            seen.add(a['source_url'])
            for text in [a['title'],a['artist'] or 'Creator: see source record',a['license']+' '+a.get('license_url',''),a['source_url']]:
                lines.extend(textwrap.wrap(text,width=105,break_long_words=True,break_on_hyphens=False) or [''])
            lines.append('')
    lines+=['MUSIC: excerpted, looped, mixed and ducked under narration.','']
    catalog=read_json(ROOT/'assets'/'music'/'catalog.json')
    for name in music:
        item=catalog[name]
        lines += [item['title']+' — Scott Buckley — Creative Commons Attribution 4.0',item['source'],'https://creativecommons.org/licenses/by/4.0/','']
    lines+=['MAP DATA: Natural Earth, public domain. Present-day geographic reference only.',
            'https://www.naturalearthdata.com/about/terms-of-use/','',
            'NARRATION: Chatterbox Original, selected project voice reference.',
            'Research sources and complete credits are also included in the delivery package.']
    return lines

def append(main_video,assets,music,directory,width,height,fps):
    from .render import concat_video
    lines=credit_lines(assets,music)
    pages=[lines[i:i+15] for i in range(0,len(lines),15)]
    pieces=[]
    for i,page in enumerate(pages):
        im=Image.new('RGB',(width,height),(25,35,45));draw=ImageDraw.Draw(im)
        draw.text((width*.06,height*.07),'SOURCES & CREDITS',font=font(width/42,True),fill=(231,190,111))
        draw.line((width*.06,height*.15,width*.94,height*.15),fill=(100,89,65),width=2)
        for j,line in enumerate(page):
            draw.text((width*.06,height*.2+j*height*.043),line,font=font(width/100),fill=(225,229,229))
        draw.text((width*.94,height*.92),f'{i+1} / {len(pages)}',font=font(width/95),anchor='ra',fill=(172,183,187))
        picture=directory/f'credit-{i}.jpg';video=directory/f'credit-{i}.mp4'
        im.save(picture,quality=94)
        ffmpeg('-loop','1','-i',picture,'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','7','-r',str(fps),
               '-vf','scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-pix_fmt','yuv420p',
               '-c:a','aac','-b:a','192k','-ar','48000','-shortest',video)
        pieces.append(video)
    joined=directory/'with-credits.mp4'
    concat_video([main_video,*pieces],joined)
    ffmpeg('-i',joined,'-c','copy','-movflags','+faststart',main_video.with_name('complete.mp4'))
    main_video.unlink();main_video.with_name('complete.mp4').replace(main_video)
    seconds=sum(duration(p) for p in pieces)
    for p in pieces:p.unlink(missing_ok=True)
    joined.unlink(missing_ok=True)
    return seconds,len(pages)
