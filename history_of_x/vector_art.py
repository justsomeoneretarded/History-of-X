"""Original flat illustrations. No downloaded creator assets or execution of model code."""
from __future__ import annotations
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter
from .maps import font

PALETTE={'cream':'#FFF5E4','navy':'#182B44','coral':'#F56554','teal':'#18A999','gold':'#F4BD4A','violet':'#8A70D6','blue':'#5EABDB','pink':'#ED9CB4'}
ICONS=('ruler','queen','person','crowd','soldier','crown','obelisk','church','castle','city','mountain','ship','coins','coffee','wheat','document','broken_document','handshake','scales','shield','rifle','cannon','tank','plane','flag','chain','broken_chain','ballot','factory','railway','cross','books','globe','border','arrow','question','lightbulb','radio')

def icon(kind,color='coral',size=720):
 # Draw at a 600-square design coordinate system, then rasterize above output resolution.
 im=Image.new('RGBA',(600,600));d=ImageDraw.Draw(im);ink=PALETTE['navy'];fill=PALETTE.get(color,color);cream=PALETTE['cream'];gold=PALETTE['gold']
 def poly(points,c=fill):d.polygon(points,fill=c)
 def line(points,c=ink,w=14):d.line(points,fill=c,width=w,joint='curve')
 def rect(box,c=fill,r=0):d.rounded_rectangle(box,radius=r,fill=c)
 def circle(box,c=fill):d.ellipse(box,fill=c)
 def person(x=300,y=260,s=1,role='person',c=fill):
  def box(a,b,c_,e):return (x+(a-300)*s,y+(b-260)*s,x+(c_-300)*s,y+(e-260)*s)
  # A single coherent silhouette: neck, shoulders, robe, arms and hands.
  d.rounded_rectangle(box(278,270,322,330),radius=12*s,fill='#B7734F')
  if role in ('ruler','queen'):
   d.polygon([(x+(a-300)*s,y+(b-260)*s) for a,b in [(220,316),(380,316),(455,540),(145,540)]],fill=c)
   d.polygon([(x+(a-300)*s,y+(b-260)*s) for a,b in [(220,316),(260,325),(345,540),(300,540)]],fill=gold)
  else:d.rounded_rectangle(box(202,315,398,540),radius=40*s,fill=c)
  d.line([box(218,340,175,465)[:2],box(218,340,175,465)[2:]],fill=c,width=max(4,int(45*s)))
  d.line([box(382,340,425,465)[:2],box(382,340,425,465)[2:]],fill=c,width=max(4,int(45*s)))
  d.ellipse(box(151,445,199,493),fill='#B7734F');d.ellipse(box(401,445,449,493),fill='#B7734F')
  d.ellipse(box(222,100,378,300),fill='#B7734F')
  d.pieslice(box(218,84,382,247),180,360,fill=ink)
  d.ellipse(box(250,192,262,205),fill=ink);d.ellipse(box(338,192,350,205),fill=ink)
  d.line([box(276,250,324,250)[:2],box(276,250,324,250)[2:]],fill=ink,width=max(2,int(7*s)))
  if role in ('ruler','queen'):
   points=[(224,127),(218,48),(266,85),(300,30),(334,85),(382,48),(376,127)]
   d.polygon([(x+(a-300)*s,y+(b-260)*s) for a,b in points],fill=gold)
   d.line([box(225,140,375,140)[:2],box(225,140,375,140)[2:]],fill=ink,width=max(2,int(8*s)))
  if role=='ruler':d.pieslice(box(230,210,370,321),0,180,fill=ink)
  if role=='soldier':d.rounded_rectangle(box(214,92,386,158),radius=12*s,fill=ink)
 if kind in ('person','ruler','queen','soldier'):person(role=kind)
 elif kind=='crowd':
  for x,y in [(170,240),(430,240),(300,300)]:person(x,y,.65,c=fill if x==300 else PALETTE['teal'])
 elif kind=='crown':poly([(90,390),(60,160),(195,245),(300,80),(405,245),(540,160),(510,390)]);rect((88,410,512,470),gold,18)
 elif kind in ('church','castle','city','factory','obelisk'):
  if kind=='obelisk':
   poly([(245,510),(250,110),(300,40),(350,110),(355,510)]);rect((180,510,420,550),ink,8)
   for y in range(160,440,65):rect((274,y,326,y+38),cream,3)
  elif kind=='church':
   rect((135,230,465,520),fill,12);poly([(100,240),(300,100),(500,240)],ink);rect((268,343,332,520),ink,24)
   for x in [182,370]:rect((x,285,x+45,345),cream,15)
   rect((288,45,312,130),gold);rect((259,72,341,94),gold)
  elif kind=='castle':
   rect((120,245,480,520),fill);rect((65,150,175,520),fill);rect((425,150,535,520),fill)
   for x in [65,130,425,490]:rect((x,100,x+45,185),ink)
   rect((255,360,345,520),ink,45)
  elif kind=='factory':
   poly([(90,300),(210,220),(210,300),(330,220),(330,300),(500,300),(500,520),(90,520)])
   rect((410,100,470,310),ink,8)
   for x in [140,270,400]:rect((x,370,x+60,430),cream,4)
   for x,y in [(435,45),(380,15),(320,5)]:circle((x,y,x+70,y+50),'#CED2D0')
  else:
   for x,h in [(60,200),(180,350),(310,270),(440,400)]:
    rect((x,540-h,x+100,540),fill,9)
    for yy in range(560-h,480,55):rect((x+25,yy,x+45,yy+25),cream,2)
 elif kind=='mountain':
  poly([(25,520),(225,100),(425,520)]);poly([(210,520),(400,175),(580,520)],PALETTE['teal']);poly([(177,200),(225,100),(272,200)],cream);poly([(354,260),(400,175),(443,260)],cream)
 elif kind=='ship':
  poly([(50,390),(550,390),(465,515),(145,515)]);line([(300,75),(300,390)],ink,15);poly([(320,100),(510,350),(320,350)],gold);poly([(275,160),(100,350),(275,350)],cream)
  for yy in [540,570]:line([(65,yy),(170,yy-12),(275,yy),(380,yy-12),(535,yy)],PALETTE['blue'],10)
 elif kind=='coins':
  for x,h in [(100,3),(250,5),(400,7)]:
   for y in range(h):d.ellipse((x,490-y*42,x+120,550-y*42),fill=gold,outline=ink,width=5)
 elif kind=='coffee':
  rect((115,205,430,475),fill,55);d.arc((340,230,535,425),270,90,fill=ink,width=27);line([(90,500),(490,500)],ink,13)
  for x in [220,325]:d.arc((x,70,x+60,200),90,270,fill=ink,width=10)
 elif kind=='wheat':
  for x in [200,300,400]:
   line([(x,510),(x,130)],ink,9)
   for y in [180,250,320]:d.ellipse((x-65,y-40,x,y+20),fill=gold);d.ellipse((x,y-75,x+65,y-15),fill=gold)
 elif kind in ('document','broken_document','ballot','books'):
  if kind=='books':
   for i,c in enumerate([fill,gold,PALETTE['teal']]):rect((95,120+i*120,505,220+i*120),c,15);line([(135,140+i*120),(460,140+i*120)],cream,8)
  else:
   rect((140,65,460,530),cream,22);d.rounded_rectangle((140,65,460,530),22,outline=ink,width=12)
   for y in [170,245,320]:line([(195,y),(405,y)],fill,15)
   if kind=='broken_document':line([(315,65),(265,180),(340,260),(260,370),(310,530)],PALETTE['coral'],20)
   if kind=='ballot':line([(200,390),(270,450),(410,345)],PALETTE['teal'],25)
 elif kind=='shield':
  poly([(80,120),(300,45),(520,120),(490,360),(420,470),(300,555),(180,470),(110,360)])
  poly([(300,95),(465,150),(440,340),(385,425),(300,495)],gold)
 elif kind in ('rifle','cannon','tank','plane'):
  if kind=='rifle':
   poly([(70,450),(145,515),(280,345),(435,185),(405,145),(240,300),(195,280)]);line([(280,310),(510,80)],ink,22);rect((250,300,300,390),gold,7)
  elif kind=='cannon':
   poly([(65,270),(510,165),(535,255),(95,360)]);circle((195,315,375,495),ink);circle((240,360,330,450),gold);line([(355,390),(510,490)],ink,23)
  elif kind=='tank':
   rect((75,350,525,490),ink,65);poly([(130,340),(190,245),(420,245),(480,340)]);rect((255,160,385,260),fill,16);rect((365,185,565,215),ink,10)
   for x in [150,245,340,435]:circle((x-27,385,x+27,439),gold)
  else:poly([(270,50),(325,50),(345,225),(540,340),(540,395),(340,330),(330,470),(400,520),(400,550),(300,520),(200,550),(200,520),(270,470),(260,330),(60,395),(60,340),(255,225)])
 elif kind in ('chain','broken_chain'):
  for x,y in [(100,320),(220,220),(340,120)]:d.rounded_rectangle((x,y,x+180,y+120),55,outline=fill,width=30)
  if kind=='broken_chain':poly([(265,180),(300,140),(335,255),(300,280)],cream);line([(180,120),(225,165)],gold,12);line([(360,340),(405,385)],gold,12)
 elif kind=='flag':
  line([(160,70),(160,540)],ink,18)
  for i,c in enumerate([PALETTE['teal'],gold,PALETTE['coral']]):rect((170,90+i*75,500,165+i*75),c)
 elif kind=='scales':
  line([(300,100),(300,500)],ink,17);line([(115,200),(485,160)],ink,15);line([(180,200),(140,350),(220,350),(180,200)],fill,10);line([(420,175),(380,325),(460,325),(420,175)],fill,10);rect((180,500,420,530),ink,12);circle((270,70,330,130),gold)
 elif kind=='handshake':
  poly([(60,280),(190,170),(300,230),(410,170),(540,280),(420,450),(320,405),(250,450),(160,400)])
  line([(190,280),(285,205),(385,280),(325,350),(270,310)],ink,13);line([(330,370),(420,450)],ink,12)
 elif kind=='railway':
  for xx in [220,380]:line([(xx,100),(xx,550)],ink,15)
  for yy in range(140,550,65):line([(175,yy),(425,yy)],fill,18)
 elif kind=='cross':rect((250,70,350,530));rect((100,205,500,305))
 elif kind=='radio':
  rect((70,210,530,510),fill,40);circle((115,275,300,460),ink);circle((150,310,265,425),cream);rect((345,280,475,320),cream,10);circle((375,365,435,425),ink);line([(380,205),(490,65)],ink,12)
 elif kind in ('globe','border'):
  circle((70,70,530,530),PALETTE['blue']);poly([(150,150),(265,110),(340,180),(290,250),(345,315),(260,460),(205,330),(135,300)],fill);poly([(395,200),(470,260),(430,390),(370,300)],gold)
  if kind=='border':line([(300,80),(300,530)],ink,12)
 elif kind=='arrow':poly([(80,245),(355,245),(355,140),(550,300),(355,460),(355,355),(80,355)])
 elif kind=='lightbulb':circle((150,65,450,365),gold);rect((235,350,365,465),ink,18);rect((260,480,340,510),ink,10)
 else:
  circle((80,80,520,520),fill);text='?';f=font(310,True);box=d.textbbox((0,0),text,font=f);d.text((300-(box[2]-box[0])/2,90),text,font=f,fill=cream)
 return im.resize((size,size),Image.Resampling.LANCZOS)

def background(path,color='cream',width=3840,height=2160):
 im=Image.new('RGB',(width,height),PALETTE[color]);d=ImageDraw.Draw(im)
 # A small amount of geometry, deliberately no labels, logos or source chrome.
 accent='#F6E9D2' if color=='cream' else '#223C5B'
 d.ellipse((int(width*.58),-int(height*.4),int(width*1.3),int(height*.85)),fill=accent)
 d.rounded_rectangle((-width//6,height*3//4,width//3,height*5//4),radius=100,fill=accent)
 im.save(path)


def outlined_art(art,background):
 """Preserve dark silhouette readability on dark backgrounds without a card frame."""
 if background!='navy':return art
 alpha=art.getchannel('A');edge=alpha.filter(ImageFilter.MaxFilter(9))
 backing=Image.new('RGBA',art.size,PALETTE['cream']);backing.putalpha(edge)
 return Image.alpha_composite(backing,art)
