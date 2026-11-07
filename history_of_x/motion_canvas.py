"""Frame-by-frame scenes: articulated characters, props, environments and physical actions.

No still-card renderer or image entrance preset is used here. Every frame redraws
joint poses, interacting props, water/clouds/smoke and world-space camera framing.
"""
from __future__ import annotations
import math,random,subprocess
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps,ImageEnhance
from .core import ROOT,PipelineError,key,duration
from .typography import font

C={'ink':'#172B3C','paper':'#FFF1D8','teal':'#0E9D90','red':'#DB6754','gold':'#E9B34E','blue':'#6AA9C7','white':'#FFF9EE','skin':'#A96E48','light':'#DEAC83'}
def lerp(a,b,u):return a+(b-a)*u
def smooth(u):u=max(0,min(1,u));return u*u*(3-2*u)
def joint(a,b,l1,l2,bend=1):
 dx=b[0]-a[0];dy=b[1]-a[1];dist=max(.001,math.hypot(dx,dy));clamped=min(dist,l1+l2-.001)
 along=(l1*l1-l2*l2+clamped*clamped)/(2*clamped);height=math.sqrt(max(0,l1*l1-along*along))
 return (a[0]+dx/dist*along-dy/dist*height*bend,a[1]+dy/dist*along+dx/dist*height*bend)

class Draw:
 def __init__(self,im,scale,zoom=1,cx=640,cy=360):self.im=im;self.d=ImageDraw.Draw(im);self.s=scale*zoom;self.ox=im.width/2-cx*self.s;self.oy=im.height/2-cy*self.s
 def pt(self,p):return (p[0]*self.s+self.ox,p[1]*self.s+self.oy)
 def points(self,p):return [self.pt(x) for x in p]
 def box(self,b):return (*self.pt(b[:2]),*self.pt(b[2:]))
 def line(self,p,c=C['ink'],w=7):self.d.line(self.points(p),fill=c,width=max(1,round(w*self.s)),joint='curve')
 def polygon(self,p,c):self.d.polygon(self.points(p),fill=c)
 def rect(self,b,c,r=0):self.d.rounded_rectangle(self.box(b),radius=max(0,r*self.s),fill=c)
 def ellipse(self,b,c):self.d.ellipse(self.box(b),fill=c)
 def circle(self,x,y,r,c):self.ellipse((x-r,y-r,x+r,y+r),c)
 def text(self,p,t,size=24,c=C['ink'],anchor='mm'):self.d.text(self.pt(p),t,font=font(round(size*self.s),True),fill=c,anchor=anchor)

def limb(d,a,b,l1,l2,color,width=11,bend=1):
 k=joint(a,b,l1,l2,bend);d.line([a,k,b],color,width)
 for p in [a,k,b]:d.circle(*p,width/2,color)
 return k

def actor(d,x,ground,t,role='worker',action='walk',facing=1,scale=1,phase=0,prop=None):
 """Two-link IK limbs; feet plant/lift, arms articulate independently of the torso."""
 q=t*5.2+phase;s=scale;moving=action in ('walk','run','carry','march')
 if action=='run':q=t*8+phase
 hip=(x,ground-119*s+(math.cos(q*2)*3*s if moving else math.sin(t*1.7+phase)*1.4*s))
 shoulder=(hip[0],hip[1]-83*s);head=(shoulder[0]+facing*3*s,shoulder[1]-48*s)
 color=C['red'] if role in ('italian','official') else C['teal']
 if role=='queen':color='#AF6C9D'
 if role=='worker':color=C['blue']
 skin=C['light'] if role in ('italian','official') else C['skin']
 for i in range(2):
  p=q+i*math.pi
  if moving:foot=(x+math.sin(p)*38*s,ground-max(0,math.cos(p))*26*s)
  else:foot=(x+(-24 if i==0 else 25)*s,ground)
  root=(hip[0]+(-7 if i==0 else 7)*s,hip[1]);limb(d,root,foot,64*s,66*s,C['ink'],10*s,bend=-facing)
  d.line([(foot[0]-12*s,foot[1]),(foot[0]+facing*15*s,foot[1])],C['ink'],10*s)
 # Robe/coat follows moving hips; no floating head on an icon tile.
 if role in ('ruler','queen'):
  d.polygon([(shoulder[0]-27*s,shoulder[1]-2*s),(shoulder[0]+27*s,shoulder[1]-2*s),(hip[0]+40*s,hip[1]+20*s),(hip[0]-40*s,hip[1]+20*s)],color)
  d.line([(shoulder[0]-13*s,shoulder[1]),(hip[0]+25*s,hip[1]+18*s)],C['gold'],10*s)
 else:
  d.line([shoulder,hip],C['ink'],49*s);d.line([shoulder,hip],color,42*s)
 hands=[]
 for i in range(2):
  side=-1 if i==0 else 1;root=(shoulder[0]+side*20*s,shoulder[1]+5*s)
  if moving:hand=(x+side*15*s-math.sin(q+i*math.pi)*28*s,shoulder[1]+64*s)
  elif action=='point':hand=(x+facing*(83 if i==1 else -22)*s,shoulder[1]+(math.sin(t*3)*7 if i==1 else 70)*s)
  elif action in ('argue','talk','negotiate'):hand=(x+side*(54+10*math.sin(t*3+i))*s,shoulder[1]+(22+22*math.sin(t*2.5+i*1.5))*s)
  elif action=='write':hand=(x+facing*(70+math.sin(t*15)*9)*s,shoulder[1]+(10 if i==1 else 25)*s)
  elif action=='cheer':hand=(x+side*(55+10*math.sin(t*4))*s,shoulder[1]-(45+12*math.cos(t*4))*s)
  elif action=='build':hand=(x+facing*(65+20*math.sin(t*4))*s,shoulder[1]+(35+40*math.cos(t*4))*s)
  elif action in ('aim','fire'):hand=(x+facing*(88 if i==1 else 45)*s,shoulder[1]+(8 if i==1 else 17)*s)
  elif action=='shake':hand=(x+facing*75*s,shoulder[1]+(40+math.sin(t*6)*8)*s)
  else:hand=(x+side*(32+math.sin(t*2+i)*6)*s,shoulder[1]+72*s)
  if prop=='crate':hand=(x+facing*52*s,shoulder[1]+(52 if i==1 else 85)*s)
  limb(d,root,hand,43*s,49*s,color,11*s,bend=side);d.circle(*hand,7*s,skin);hands.append(hand)
 # Small head rotations and brows articulate the delivery rather than sliding the whole sprite.
 tilt=math.sin(t*2.1+phase)*3*s;hx=head[0]+tilt;hy=head[1]
 d.line([shoulder,(hx,hy+24*s)],skin,12*s);d.circle(hx,hy,31*s,skin);d.line([(hx-25*s,hy-18*s),(hx+23*s,hy-18*s)],C['ink'],15*s)
 if role in ('ruler','queen'):
  d.polygon([(hx-26*s,hy-27*s),(hx-29*s,hy-57*s),(hx-12*s,hy-45*s),(hx,hy-65*s),(hx+12*s,hy-45*s),(hx+29*s,hy-57*s),(hx+26*s,hy-27*s)],C['gold'])
  if role=='ruler':d.polygon([(hx-24*s,hy+8*s),(hx+24*s,hy+8*s),(hx+14*s,hy+37*s),(hx-14*s,hy+37*s)],C['ink'])
 elif role in ('soldier','italian'):d.rect((hx-34*s,hy-35*s,hx+32*s,hy-15*s),color,7*s)
 for side in [-1,1]:
  ex=hx+side*11*s+facing*3*s;d.circle(ex,hy-3*s,3*s,C['ink'])
  eyebrow=math.sin(t*2.5+side)*2*s if action in ('argue','talk') else 0
  d.line([(ex-5*s,hy-13*s+eyebrow),(ex+5*s,hy-12*s)],C['ink'],2*s)
 if role!='ruler':
  opening=3+2*math.sin(t*10) if action in ('talk','argue','negotiate') else 1
  d.ellipse((hx-7*s,hy+12*s-opening*s,hx+7*s,hy+12*s+opening*s),C['ink'])
 if prop=='crate':d.rect((x+facing*47*s-25*s,shoulder[1]+45*s,x+facing*47*s+25*s,shoulder[1]+90*s),'#B27D48',3*s)
 if prop=='rifle' or action in ('aim','fire'):
  a=hands[1];b=(a[0]+facing*60*s,a[1]-3*s);d.line([a,b],C['ink'],7*s)
  d.line([(a[0]-facing*27*s,a[1]+8*s),a],'#8E5735',13*s)
  if action=='fire' and (t*1.7+phase)%1<.12:
   d.polygon([(b[0],b[1]),(b[0]+facing*25*s,b[1]-12*s),(b[0]+facing*16*s,b[1]),(b[0]+facing*25*s,b[1]+12*s)],C['gold'])
 return shoulder,hands

def clouds(d,t):
 for i in range(7):
  x=((i*237+t*(7+i%3))%1630)-170;y=80+(i*43)%130
  for j in range(3):d.ellipse((x+j*35,y-j%2*15,x+100+j*35,y+35-j%2*15),'#E9DDBD')

def hills(d,t,photo=None):
 d.rect((-1000,-500,2300,900),'#F5E7C8');clouds(d,t)
 d.polygon([(-300,480),(0,270),(180,350),(355,185),(530,330),(750,230),(1040,410),(1500,245),(1800,800),(-300,800)],'#95B7AC')
 d.polygon([(-300,640),(130,430),(380,490),(660,360),(950,530),(1170,385),(1580,585),(1800,900),(-300,900)],'#497A70')
 d.polygon([(-300,720),(80,600),(350,635),(550,540),(850,640),(1200,555),(1600,690),(1800,1000),(-300,1000)],'#B49B64')
 for i in range(12):
  x=i*130-100;d.line([(x,720),(x+110,670),(x+220,690)],'#9A8456',4)

def building(d,x,y,kind='palace',scale=1):
 s=scale
 if kind=='obelisk':
  d.polygon([(x-22*s,y),(x-20*s,y-230*s),(x,y-260*s),(x+20*s,y-230*s),(x+22*s,y)],'#B58D64')
  for j in range(5):d.rect((x-10*s,y-(j*35+40)*s,x+10*s,y-(j*35+18)*s),'#654C37')
 elif kind=='church':
  d.rect((x-120*s,y-180*s,x+120*s,y),'#B87451');d.polygon([(x-140*s,y-180*s),(x,y-260*s),(x+140*s,y-180*s)],'#81513C')
  d.rect((x-25*s,y-90*s,x+25*s,y),C['ink'],20*s);d.line([(x,y-270*s),(x,y-310*s)],C['gold'],8*s);d.line([(x-16*s,y-295*s),(x+16*s,y-295*s)],C['gold'],8*s)
 else:
  d.rect((x-160*s,y-160*s,x+160*s,y),'#D5B48A')
  for side in [-1,1]:
   xx=x+side*130*s;d.rect((xx-32*s,y-230*s,xx+32*s,y),'#BF986D')
   for k in [-1,1]:d.rect((xx+k*20*s-10*s,y-255*s,xx+k*20*s+10*s,y-220*s),'#BF986D')
  d.rect((x-28*s,y-100*s,x+28*s,y),C['ink'],25*s)
  for xx in [-85,85]:d.rect((x+(xx-15)*s,y-115*s,x+(xx+15)*s,y-60*s),C['ink'],14*s)

def ship(d,x,y,t,scale=1):
 s=scale;bob=math.sin(t*1.9+x*.01)*5*s
 d.polygon([(x-110*s,y+bob),(x+110*s,y+bob),(x+65*s,y+55*s+bob),(x-70*s,y+55*s+bob)],'#72503A')
 d.line([(x,y+10*s+bob),(x,y-190*s+bob)],C['ink'],6*s)
 flutter=math.sin(t*3)*9*s
 d.polygon([(x+8*s,y-180*s+bob),(x+85*s+flutter,y-25*s+bob),(x+8*s,y-25*s+bob)],C['white'])
 d.polygon([(x-8*s,y-150*s+bob),(x-75*s+flutter,y-25*s+bob),(x-8*s,y-25*s+bob)],C['gold'])

def scroll(d,x,y,t,angle=0,split=False,scale=1):
 s=scale;gap=(15+20*math.sin(t*2)**2)*s if split else 0
 for side in [-1,1]:
  xx=x+side*gap;d.rect((xx+(0 if side>0 else -48)*s,y-38*s,xx+(48 if side>0 else 0)*s,y+38*s),C['white'],3*s)
  for j in range(3):d.line([(xx+side*8*s,y+(-20+j*18)*s),(xx+side*37*s,y+(-20+j*18)*s)],'#A8997C',2*s)
 if split:d.line([(x,y-40*s),(x-8*s,y-15*s),(x+8*s,y+10*s),(x,y+40*s)],C['red'],4*s)

@lru_cache(maxsize=12)
def photo_texture(path,width,height):
 with Image.open(path) as im:return ImageOps.fit(im.convert('RGB'),(width,height),Image.Resampling.LANCZOS)

def frame(plan,t,seconds,width=1920,height=1080):
 """t is continuous world time within a narrative scene, not an entrance timer."""
 ss=1.35;w=round(width*ss);h=round(height*ss);im=Image.new('RGB',(w,h),C['paper'])
 camera=plan.get('camera','wide');z={'wide':1,'medium':1.12,'close':1.28,'tracking':1.08}.get(camera,1)
 # Camera follows world action smoothly; no integer crop/zoompan rounding.
 cx=640+math.sin(t*.23)*14 if camera=='tracking' else 640
 d=Draw(im,w/1280,z,cx,360);env=plan.get('environment','highlands');activity=plan.get('activity','march')
 phase=t;u=(t%12)/12;action_t=max(0,t-plan.get('action_start_time',0))
 lead=plan.get('lead_role','ruler');opponent=plan.get('opponent_role','official')
 if env=='harbor':
  d.rect((-500,-500,1800,1000),'#F3E5C8');clouds(d,t)
  d.rect((-500,350,1800,900),'#64A6B1')
  for j in range(12):
   y=375+j*27
   for i in range(9):
    x=i*180+(t*23+j*19)%180-180;d.line([(x,y),(x+35,y-4),(x+85,y)],'#A7CDD0',3)
  ship(d,880+t*9,400,t,1.15);ship(d,250+t*4,365,t,.6)
  building(d,110,365,'obelisk',.75)
  d.polygon([(-300,570),(670,570),(770,610),(-300,610)],'#9A724C')
  for x in [80,270,460,640]:d.rect((x,610,x+15,850),'#6A503C')
  for i in range(3):
   route=t*.45+i*2.1;x=85+520*(.5-.5*math.cos(route));facing=1 if math.sin(route)>=0 else -1
   actor(d,x,570,t,'worker','carry',facing,.78,i*1.3,'crate')
  for i in range(4):d.rect((60+i*55,532,105+i*55,570),'#B98751',3)
 elif env in ('palace','council','treaty','workshop'):
  d.rect((-500,-500,1800,900),'#E8D8B9');d.rect((-500,480,1800,1000),'#BF9E78')
  for x in [100,360,920,1180]:
   d.rect((x-30,100,x+30,490),'#F8EBD3');d.rect((x-45,85,x+45,115),'#B28E67')
  for x in [235,1050]:
   d.rect((x-50,175,x+50,340),C['teal']);d.polygon([(x-50,340),(x,320+math.sin(t*2)*10),(x+50,340)],C['teal'])
  # Genuine portrait can be embedded as an environment detail, with live action in front.
  photo=str(ROOT/plan['photo_path']) if plan.get('photo_path') else None
  if photo:
   a=d.pt((500,95));b=d.pt((780,370));pw=max(1,round(b[0]-a[0]));ph=max(1,round(b[1]-a[1]));im.paste(photo_texture(photo,pw,ph),(round(a[0]),round(a[1])))
  d.rect((430,425,850,465),'#72503A',8);d.rect((450,455,470,620),'#72503A');d.rect((810,455,830,620),'#72503A')
  action='negotiate' if activity in ('negotiate','debate','treaty') else 'write' if activity=='write' else 'point'
  approach=smooth(min((t%12)/3,(12-t%12)/2));left=350+150*approach;right=930-150*approach
  walking=(t%12)<3 or (t%12)>10;facing=-1 if (t%12)>10 else 1
  actor(d,left,620,t,lead,'walk' if walking else action,facing,1.05,0);actor(d,right,620,t,opponent,'walk' if walking else 'argue' if activity=='debate' else action,-facing,1,2)
  if activity in ('treaty','negotiate','debate','write'):
   x=640+math.sin(t*.85)*90;scroll(d,x,410+math.sin(t*2)*4,t,split=activity=='debate')
   if activity=='write':
    d.line([(640+math.sin(t*8)*12,410),(660+math.sin(t*8)*12,375)],C['ink'],4)
  if env=='council':actor(d,180,650,t,'queen','talk',1,.9,1.2)
 elif env in ('city','church'):
  hills(d,t)
  d.rect((-300,550,1800,1000),'#D3B583')
  building(d,700,540,'church' if env=='church' else 'palace',1.3)
  building(d,180,540,'obelisk',.8);building(d,1150,540,'palace',.65)
  for i in range(3):
   x=-140+(t*(35+i*6)+i*400)%1560
   actor(d,x,650,t,'worker','carry' if activity=='build' else 'walk',1,.9,i,prop='crate' if activity=='build' else None)
  if activity=='build':
   # Masonry and a crane progress continuously, not a scale-up icon.
   d.line([(880,550),(880,170),(1040,170)],'#6D5037',9);yy=300+math.sin(t*1.1)*80;d.line([(1010,170),(1010,yy)],C['ink'],3);d.rect((975,yy,1045,yy+40),'#BD8660')
   actor(d,920,650,t,'worker','build',-1,.9,1)
 elif env=='assembly':
  d.rect((-500,-500,1800,1000),'#E5D4B7');d.rect((-500,480,1800,1000),'#B79D80')
  for row in range(3):
   for i in range(7):actor(d,190+i*155,400+row*80,t,'worker','talk',1,.43,row+i)
  d.rect((540,470,740,610),'#72503A',7);actor(d,640,650,t,lead,'point',-1,1.15,0)
 elif env=='rebuild':
  hills(d,t);d.rect((-300,550,1800,1000),'#D3B583')
  for i in range(5):building(d,120+i*250,520,'palace',.35+(.15 if i%2 else 0))
  for i in range(4):actor(d,-140+(t*48+i*400)%1560,650,t,'worker','carry',1,.9,i,'crate')
  actor(d,800,650,t,'worker','build',-1,1,1)
 else:
  hills(d,t)
  if env=='camp':
   for x in [160,650,1120]:d.polygon([(x-90,560),(x,400),(x+100,560)],'#DAC5A0')
  # Two columns move through actual terrain; their joint poses change every frame.
  battle=activity in ('battle','retreat','fire')
  for row in range(2):
   for i in range(5):
    x=90+i*145+row*45 if battle else -150+((t*42+i*250+row*90)%1650)
    ground=610+row*60-30*math.sin(x/230)
    actor(d,x,ground,t,'soldier','march' if not battle else 'fire',1,.65+row*.12,i*1.2+row,'rifle')
  for i in range(3):
   x=850+i*160+action_t*75 if activity=='retreat' else (950+i*110 if battle else 1400-((t*32+i*250)%1650))
   actor(d,x,625+i*10,t,'italian','run' if activity=='retreat' else 'fire' if battle else 'march',1 if activity=='retreat' else -1,.88,i*1.7,'rifle')
  if battle:
   for i in range(7):
    age=(t*.7+i*.2)%1;x=920+age*100+math.sin(i*3)*70;y=460-age*120+i%2*35;r=12+age*25
    d.circle(x,y,r,'#C5C0AD')
   # Cannon recoil and rolling wheel spokes are genuine object animation.
   recoil=math.exp(-((t*1.1)%1)*12)*10;d.circle(1100,625,32,C['ink']);d.circle(1100,625,24,'#907355')
   for a in range(5):
    ang=t*.5+a*math.tau/5;d.line([(1100,625),(1100+22*math.cos(ang),625+22*math.sin(ang))],C['ink'],4)
   d.line([(1090+recoil,592),(1000+recoil,560)],C['ink'],23)
   flight=(t*1.1)%1;d.circle(1000-flight*700,560-170*math.sin(flight*math.pi),5,C['ink'])
  if activity=='rally':actor(d,590,650,t,lead,'cheer',1,1.25,.5)
 # A historical image is a real illustrated object in a live scene, not a full-screen slide.
 if plan.get('photo_path') and env not in ('palace','council','treaty','workshop'):
  a=d.pt((130,330));b=d.pt((300,540));pw=max(1,round(b[0]-a[0]));ph=max(1,round(b[1]-a[1]))
  d.rect((120,320,310,550),'#72503A',6);d.rect((207,545,223,680),'#72503A')
  im.paste(photo_texture(str(ROOT/plan['photo_path']),pw,ph),(round(a[0]),round(a[1])))
  actor(d,385,660,t,'worker','point',-1,.9,1)
 # A subtle foreground layer gives action a physical stage instead of a white slide.
 d.polygon([(-1000,735),(300,690),(730,735),(1100,695),(2100,760),(2100,1200),(-1000,1200)],'#796E50')
 ui=Draw(im,w/1280);ui.rect((24,22,245,76),C['paper'],12);ui.text((42,48),plan.get('year_label',''),27,C['ink'],'lm')
 return im.resize((width,height),Image.Resampling.LANCZOS)

def render_shot(shot,directory,profile,elapsed,total):
 from .render import PROFILES
 width,height,fps=PROFILES[profile];plan=shot.get('motion')
 if not plan:raise PipelineError('Missing motion choreography; slideshow fallback is disabled')
 seconds=shot['global_end']-shot['global_start'];frames=round(seconds*fps)
 identity=key('living-scene-v3',shot,profile);out=directory/(identity+'.mp4')
 if out.exists() and abs(duration(out)-frames/fps)<.1:return out
 directory.mkdir(parents=True,exist_ok=True)
 command=['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-','-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-crf','20' if profile!='draft' else '24','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
 with __import__('tempfile').TemporaryFile() as errors:
  p=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=errors)
  try:
   for index in range(frames):
    image=frame(plan,plan.get('scene_time',0)+index/fps,seconds,width,height);p.stdin.write(image.tobytes())
   p.stdin.close();code=p.wait(timeout=120)
  except BaseException:
   p.kill();p.wait();out.unlink(missing_ok=True);raise
  if code:
   errors.seek(0);raise PipelineError('Motion encoder failed: '+errors.read().decode()[-1200:])
 return out
