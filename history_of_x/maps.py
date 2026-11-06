from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFont
from .core import ROOT, save_json, read_json
from .research import get

FONT=str(ROOT/'assets'/'fonts'/'DejaVuSans.ttf')
BOLD=str(ROOT/'assets'/'fonts'/'DejaVuSans-Bold.ttf')

def font(size,bold=False):
    return ImageFont.truetype(BOLD if bold else FONT,max(10,int(size)))

def countries(cache):
    output=cache/'countries.geojson'
    if not output.exists():
        data=get('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson').json()
        save_json(output,data)
    return read_json(output)['features']

def draw_map(output, cache, width=1920,height=1080,focus='Ethiopia'):
    im=Image.new('RGB',(width,height),(12,22,29))
    draw=ImageDraw.Draw(im)
    # Present-day location reference only. Never asserted as a historical territorial reconstruction.
    bounds=(20,-7,58,24) if focus.casefold()=='ethiopia' else (-180,-60,180,85)
    xmin,ymin,xmax,ymax=bounds
    def project(lon,lat):
        return ((lon-xmin)/(xmax-xmin)*width, height-(lat-ymin)/(ymax-ymin)*height)
    for lon in range(int(xmin),int(xmax)+1,5):
        x,_=project(lon,ymin);draw.line((x,0,x,height),fill=(24,36,43),width=1)
    for lat in range(int(ymin),int(ymax)+1,5):
        _,y=project(xmin,lat);draw.line((0,y,width,y),fill=(24,36,43),width=1)
    labels=[]
    for feature in countries(cache):
        props=feature['properties']; name=props.get('ADMIN') or props.get('NAME','')
        geom=feature['geometry']
        polygons=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
        allpoints=[]
        for polygon in polygons:
            points=polygon[0]
            if not any(xmin<=p[0]<=xmax and ymin<=p[1]<=ymax for p in points):
                continue
            screen=[project(*p[:2]) for p in points]
            draw.polygon(screen,fill=(132,94,40) if name.casefold()==focus.casefold() else (35,49,53),outline=(173,135,69) if name.casefold()==focus.casefold() else (79,94,96),width=max(1,width//700))
            allpoints.extend(screen)
        if allpoints and focus.casefold()=='ethiopia':
            x=sum(p[0] for p in allpoints)/len(allpoints);y=sum(p[1] for p in allpoints)/len(allpoints)
            if 70<x<width-100 and 100<y<height-170:
                if name=='Ethiopia':
                    x,y=project(38,6)
                elif name=='Eritrea':
                    x,y=project(38.5,16)
                labels.append((x,y,name))
    for x,y,name in labels:
        draw.text((x,y),name.upper(),font=font(width/90,True),anchor='mm',fill=(232,222,196))
    if focus.casefold()=='ethiopia':
        for name,lon,lat in [('ADWA',38.90,14.17),('AKSUM',38.72,14.12),('ADDIS ABABA',38.75,9.03)]:
            x,y=project(lon,lat)
            if name=='AKSUM':
                continue # Aksum and Adwa overlap at this reference scale.
            draw.ellipse((x-4,y-4,x+4,y+4),fill=(246,210,125))
            draw.text((x+12,y-10),name,font=font(width/95,True),fill='white')
    draw.text((width*.045,height*.16),'GEOGRAPHIC REFERENCE',font=font(width/70,True),fill=(211,175,100))
    draw.text((width*.045,height*.80),'Present-day boundaries • Natural Earth • not historical borders',font=font(width/95),fill=(210,214,213))
    im.save(output,quality=95)
    return output
