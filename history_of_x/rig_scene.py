"""Compile a directed scene graph into real articulated vector animation.

The model chooses staging and timed actions. Original artwork, joint attachment,
two-link arm kinematics and prop ownership are handled deterministically.
"""
from __future__ import annotations
import base64
import io
import math
import re
from html import escape
from pathlib import Path
import numpy as np
from PIL import Image
from .core import PipelineError
from .scene_film import DEFAULT, interpolate, transform_matrix, validate_scene
from .rig_art import CAST, EXPRESSIONS, SETTINGS, PROPS, actor_parts, background, prop_art

def _matrix_text(m):
 return "matrix("+ " ".join(f"{float(x):.7f}" for x in (m[0,0],m[1,0],m[0,1],m[1,1],m[0,2],m[1,2])) +")"

def _trs(x,y,scale=1,angle=0):
 r=math.radians(angle);c=math.cos(r)*scale;s=math.sin(r)*scale
 return np.array([[c,-s,x],[s,c,y],[0.,0.,1.]])

def _number(value,label,low=-20000,high=20000):
 if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low<=value<=high:
  raise PipelineError("Invalid rig "+label)
 return float(value)

class Scene:
 def __init__(self,spec,seconds,assets):
  self.spec=spec;self.seconds=seconds;self.assets={a["id"]:a for a in assets}
  self.layers={};self.art={};self.nodes={};self.actors={};self.formations={};self.props={};self.busy={};self.busy_kind={};self.gesture_interruptions=[]
  self.events=[];self.used=set();self.order=[]
  self.add("environment",background(spec["setting"]),pivot=(960,540),order=-100)
  records=spec.get("nodes")
  if not isinstance(records,list) or not 1<=len(records)<=10 or any(not isinstance(n,dict) for n in records):raise PipelineError("Use 1–10 scene node objects")
  if sum(n.get("kind")=="actor" for n in records)>4:raise PipelineError("Use at most four readable actors")
  for n in records:self.node(n)

 def add(self,identifier,art,parent="",pivot=(0,0),start=0,end=None,opacity=1,order=0):
  if identifier in self.layers:raise PipelineError("Duplicate rig layer")
  self.layers[identifier]={"id":identifier,"pivot":list(pivot),"start":start,"end":self.seconds if end is None else end,
    "keyframes":[{"time":0,**DEFAULT,"opacity":opacity,"ease":"smooth"}],**({"parent":parent} if parent else {})}
  self.art[identifier]=art;self.order.append((order,len(self.order),identifier))
  return identifier

 def animate(self,identifier,t,end,changes,ease="smooth"):
  layer=self.layers[identifier];frames=layer["keyframes"];at={**interpolate(frames,t),"time":t,"ease":"smooth"}
  kept=[f for f in frames if f["time"]<t-1e-7]
  kept.append(at)
  final={**at,**changes,"time":end,"ease":ease}
  if end<=t+1e-7:kept[-1]=final
  else:kept.append(final)
  layer["keyframes"]=kept

 def world(self,identifier,t):
  layer=self.layers[identifier];pose=interpolate(layer["keyframes"],t)
  own=transform_matrix(pose,layer["pivot"])
  return self.world(layer["parent"],t)@own if layer.get("parent") else own

 def node(self,n):
  if not isinstance(n,dict):raise PipelineError("Scene node must be an object")
  ident=n.get("id","")
  if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,35}",ident) or ident in self.nodes:
   raise PipelineError("Use unique short node IDs")
  allowed={"id","kind","x","y","scale","start","end","visible","z","appearance","facing","expression","count","prop","text","asset_id","width","height","points","color","dashed"}
  if set(n)-allowed:raise PipelineError("Unknown node direction; refusing to ignore it")
  kind=n.get("kind")
  if kind=="image":
   # Documentary insert is an editorial full-frame shot, never a prop/card on set.
   n={**n,"x":960,"y":540,"scale":1,"width":1920,"height":1080,"z":8}
  x=_number(n.get("x"),"node x");y=_number(n.get("y"),"node y")
  scale=_number(n.get("scale",1),"node scale",.15,1.8)
  start=_number(n.get("start",0),"node start",0,self.seconds);end=_number(n.get("end",self.seconds),"node end",0,self.seconds)
  if start>=end:raise PipelineError("Node lifetime must be positive")
  n={**n,"x":x,"y":y,"scale":scale,"start":start,"end":end}
  self.nodes[ident]=n;master=ident+"__motion";n["master"]=master
  z=_number(n.get("z",2 if kind=="actor" else 3),"node z",-5,8)
  self.add(master,"",pivot=(x,y),start=start,end=end,opacity=1 if n.get("visible",True) else 0,order=z)
  if kind=="actor":
   appearance=n.get("appearance")
   if appearance not in CAST:raise PipelineError("Choose a supplied original actor appearance")
   facing=n.get("facing","right")
   if facing not in ("left","right"):raise PipelineError("Actor faces left or right")
   sign=1 if facing=="right" else -1
   base=np.array([[scale*sign,0,x-180*scale*sign],[0,scale,y-760*scale],[0,0,1.]])
   actor={"node":n,"base":base,"sign":sign,"parts":{}}
   self.actors[ident]=actor
   expression=n.get("expression","neutral")
   if expression not in EXPRESSIONS:raise PipelineError("Unsupported facial expression")
   for part,svg,parent,pivot in actor_parts(appearance):
    pid=ident+"__"+part
    parent_id=ident+"__"+parent if parent else master
    point=base@np.array([*pivot,1.])
    opacity=1 if not part.startswith("face_") or part=="face_"+expression else 0
    self.add(pid,'<g transform="'+_matrix_text(base)+'">'+svg+'</g>',parent_id,point[:2],start,end,opacity,z)
    actor["parts"][part]=pid
   return
  if kind=="formation":
   appearance=n.get("appearance","italian_officer")
   if appearance not in CAST:raise PipelineError("Unsupported formation appearance")
   count=int(_number(n.get("count",3),"formation count",2,5))
   self.formations[ident]=[]
   for i in range(count):
    b=np.array([[scale*.32,0,x+(i-(count-1)/2)*scale*110-180*scale*.32],[0,scale*.32,y-760*scale*.32],[0,0,1.]])
    parts=actor_parts(appearance)
    body=''.join(art for part,art,_,_ in parts if not part.startswith("leg_") and (not part.startswith("face_") or part=="face_neutral"))
    # Marching figures have articulated legs. Their body art remains a single
    # recording, keeping even a five-person formation inside the layer budget.
    self.add(f"{ident}__figure_{i}",'<g transform="'+_matrix_text(b)+'">'+body+'</g>',master,(x,y),start,end,order=z)
    legs={}
    for part,art,_,pivot in parts:
     if not part.startswith("leg_"):continue
     lid=f"{ident}__figure_{i}_{part}";point=b@np.array([*pivot,1.])
     self.add(lid,'<g transform="'+_matrix_text(b)+'">'+art+'</g>',master,point[:2],start,end,order=z)
     legs[part]=lid
    self.formations[ident].append(legs)
   return
  if kind=="prop":
   if n.get("prop") not in PROPS:raise PipelineError("Choose a supplied original prop")
   self.props[ident]={"node":n,"svg":prop_art(n["prop"],str(n.get("text",""))),
    "segments":[{"start":start,"end":end,"parent":master,"base":_trs(x,y,scale),"upright":False}]}
   return
  if kind=="route":
   points=n.get("points")
   if not isinstance(points,list) or not 2<=len(points)<=8:raise PipelineError("Route needs 2–8 world points")
   pts=[(_number(p[0],"route x",0,1920),_number(p[1],"route y",0,1080)) for p in points]
   color={"gold":"#D1A659","rust":"#B65B48","teal":"#34756F"}.get(n.get("color","gold"),"#D1A659")
   coords=" ".join(f"{xx},{yy}" for xx,yy in pts)
   dash=' stroke-dasharray="18 13"' if n.get("dashed") else ""
   art=f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="8" stroke-linejoin="round" stroke-linecap="round"{dash}/>'
   self.add(ident+"__art",art,master,(x,y),start,end,order=z);return
  if kind=="label":
   text=str(n.get("text",""))
   if not text.strip() or len(text)>45 or len(text.split())>6:raise PipelineError("Use only a short necessary explanatory label")
   if re.search(r"history of x|source:|reference:|subscribe|channel",text,re.I):raise PipelineError("No branding or source chrome in the picture")
   art=f'<text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans" font-size="{round(54*scale)}" font-weight="bold" fill="#304B47">{escape(text)}</text>'
   self.add(ident+"__art",art,master,(x,y),start,end,order=z);return
  if kind=="image":
   asset=self.assets.get(n.get("asset_id"))
   if not asset or asset.get("medium") in ("archival_video","video"):raise PipelineError("Use an approved still-image asset ID")
   p=Path(asset["path"])
   with Image.open(p) as im:
    im=im.convert("RGB");im.thumbnail((1600,1000));buf=io.BytesIO();im.save(buf,format="JPEG",quality=88)
   encoded=base64.b64encode(buf.getvalue()).decode()
   width=_number(n.get("width",1200),"image width",100,1920)*scale;height=_number(n.get("height",800),"image height",100,1080)*scale
   plate=f'<rect x="{x-width/2}" y="{y-height/2}" width="{width}" height="{height}" fill="#E7DFCB"/>' if width>=1700 and height>=900 else ""
   art=plate+f'<image x="{x-width/2}" y="{y-height/2}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet" href="data:image/jpeg;base64,{encoded}"/>'
   self.used.add(asset["id"]);self.add(ident+"__art",art,master,(x,y),start,end,order=z);return
  raise PipelineError("Unsupported scene node kind")

 def expression(self,actor,value,t):
  if value not in EXPRESSIONS:raise PipelineError("Unsupported facial expression")
  for name in EXPRESSIONS:
   lid=actor["parts"]["face_"+name]
   self.animate(lid,max(0,t-.06),t,{"opacity":1 if value==name else 0})

 def reserve_hand(self,actor,hand,t,end,gesture=False):
  token=(actor,hand);previous=self.busy.get(token,-1)
  if t<previous-1e-6:
   if self.busy_kind.get(token)!="gesture":
    raise PipelineError(f"Actions on the same hand overlap: {actor}.{hand} at {t:g}s interrupts physical contact ending at {previous:g}s")
   # A new intentional action may interrupt an idle/pointing gesture. animate()
   # samples its exact current joint pose before replacing its remaining tween.
   self.gesture_interruptions.append({"actor":actor,"hand":hand,"time":t,"previous_end":previous})
  self.busy[token]=end;self.busy_kind[token]="gesture" if gesture else "contact"

 def hand(self,actor_id,hand,t,end,target_world=None,local=None):
  actor=self.actors.get(actor_id)
  if actor is None or hand not in ("front","back"):raise PipelineError("Hand action needs an actor and front/back hand")
  self.reserve_hand(actor_id,hand,t,end,gesture=local is not None)
  torso=actor["parts"]["torso"];base=actor["base"]
  if local is not None:
   if not isinstance(local,list) or len(local)!=2:raise PipelineError("Hand target is a local [x,y] point")
   target=np.array([180+_number(local[0],"hand x"),760+_number(local[1],"hand y"),1.])
  else:
   target=np.linalg.inv(base)@np.linalg.inv(self.world(torso,end))@np.array([*target_world,1.])
  sx=270 if hand=="front" else 90
  dx,dy=float(target[0]-sx),float(target[1]-280);dist=math.hypot(dx,dy)
  stretch=max(1.,dist/249.9)
  if stretch>1.25:
   frame=self.world(torso,end)@base
   origin=(frame@np.array([sx,280.,1.]))[:2]
   requested=(frame@target)[:2]
   limit=249.9*1.25*float(actor["node"]["scale"])
   distance=float(np.linalg.norm(requested-origin))
   raise PipelineError(
    f"{actor_id}.{hand} cannot reach at {end:g}s: shoulder=({origin[0]:.1f},{origin[1]:.1f}), "
    f"target=({requested[0]:.1f},{requested[1]:.1f}), distance={distance:.1f}px, maximum={limit:.1f}px. "
    "Move the actor into reach BEFORE contact, or reposition the unheld prop in the plan. "
    "Walking horizontally cannot fix a vertical gap larger than the arm's reach. "
    "Do not teleport a held prop or increase limb stretch.")
  a,b=130*stretch,120*stretch
  cosine=max(-1.,min(1.,(dist*dist-a*a-b*b)/(2*a*b)))
  elbow=(-1 if hand=="front" else 1)*math.acos(cosine)
  shoulder=math.atan2(dy,dx)-math.atan2(b*math.sin(elbow),a+b*math.cos(elbow))
  sign=actor["sign"]
  self.animate(actor["parts"]["upper_"+hand],t,end,{"rotation":sign*(math.degrees(shoulder)-90),"scale":stretch})
  self.animate(actor["parts"]["forearm_"+hand],t,end,{"rotation":sign*math.degrees(elbow)})
  return actor["parts"]["forearm_"+hand]

 def prop_segment(self,ident,t):
  prop=self.props.get(ident)
  if not prop:raise PipelineError("Contact action needs a prop")
  return next((s for s in reversed(prop["segments"]) if s["start"]<=t+1e-7),prop["segments"][0])

 def prop_world(self,ident,t):
  segment=self.prop_segment(ident,t)
  p=self.world(segment["parent"],t) if segment["parent"] else np.eye(3)
  actual=p@segment["base"]
  if segment["upright"]:
   return _trs(actual[0,2],actual[1,2],segment["scale"],segment["angle"])
  return actual

 def target(self,ident,t):
  if ident in self.props:return self.prop_world(ident,t)[:2,2]
  n=self.nodes.get(ident)
  if n is None:raise PipelineError("Target node not found")
  return (self.world(n["master"],t)@np.array([n["x"],n["y"],1.]))[:2]

 def ownership(self,ident,parent,t,world_pose=None):
  prop=self.props[ident];before=self.prop_world(ident,t) if world_pose is None else world_pose
  last=prop["segments"][-1]
  if t<last["start"]-1e-6:raise PipelineError("Prop ownership changes must be chronological")
  last["end"]=t
  matrix=np.linalg.inv(self.world(parent,t))@before if parent else before
  prop["segments"].append({"start":t,"end":prop["node"]["end"],"parent":parent,"base":matrix,
   "upright":bool(parent),"angle":math.degrees(math.atan2(before[1,0],before[0,0])),
   "scale":math.sqrt(abs(np.linalg.det(before[:2,:2])))})

 def execute(self):
  actions=self.spec.get("actions")
  if not isinstance(actions,list) or not 3<=len(actions)<=18 or any(not isinstance(a,dict) for a in actions):raise PipelineError("Use 3–18 purposeful timed action objects")
  normalized=[]
  for a in actions:
   if a.get("type")=="take" and a.get("object"):
    if a.get("target") and a["target"]!=a["object"]:raise PipelineError("Pickup target and object must identify the same prop")
    a={**a,"target":a["object"]}
   normalized.append(a)
  actions=sorted(normalized,key=lambda a:a.get("time",-1))
  taken={}
  for a in actions:
   if a.get("type")=="take":taken.setdefault(a.get("target"),a.get("time",0))
  for a in actions:
   if a.get("type")=="move" and a.get("node") in taken and a.get("time",0)>=taken[a["node"]]:
    raise PipelineError("After pickup, move a prop through its holder; after placing it, take it again before moving it")
  # Body travel and torso/head poses are known before solving arm contacts.
  allowed_actions={"type","time","duration","node","target","object","hand","x","y","walk","expression","head","lean","front_hand","back_hand","description","sfx"}
  for a in actions:
   if not isinstance(a,dict) or set(a)-allowed_actions:raise PipelineError("Unknown action direction; refusing to ignore it")
   t=_number(a.get("time"),"action time",0,self.seconds);d=_number(a.get("duration",.5),"action duration",0,10);end=t+d
   if end>self.seconds+.001:raise PipelineError("Action extends beyond narration")
   ident=a.get("node");n=self.nodes.get(ident)
   if n is None:raise PipelineError("Action references an unknown node")
   op=a.get("type")
   if op=="move":
    changes={}
    if "x" in a:changes["x"]=_number(a["x"],"move x")-n["x"]
    if "y" in a:changes["y"]=_number(a["y"],"move y")-n["y"]
    if not changes:raise PipelineError("Move needs a destination")
    previous=interpolate(self.layers[n["master"]]["keyframes"],t)
    self.animate(n["master"],t,end,changes)
    walkers=[self.actors[ident]["parts"]] if ident in self.actors else self.formations.get(ident,[])
    if walkers and a.get("walk",True) and d>.4:
     distance=math.hypot(changes.get("x",previous["x"])-previous["x"],changes.get("y",previous["y"])-previous["y"])
     if distance>=20:
      steps=max(2,min(8,round(distance/(90 if ident in self.actors else 55))))
      for index,parts in enumerate(walkers):
       for side,phase in (("front",1),("back",-1)):
        lid=parts["leg_"+side]
        for i in range(steps*2+1):
         at=t+d*i/(steps*2)
         angle=0 if i in (0,steps*2) else phase*((-1)**index)*(13 if i%2 else -13)
         self.animate(lid,at,at,{"rotation":angle})
   elif op in ("show","hide"):
    self.animate(n["master"],t,end,{"opacity":1 if op=="show" else 0})
   elif op=="pose":
    actor=self.actors.get(ident)
    if actor is None:raise PipelineError("Pose needs an actor")
    if "lean" in a:self.animate(actor["parts"]["torso"],t,end,{"rotation":_number(a["lean"],"body lean",-25,25)})
    if "head" in a:self.animate(actor["parts"]["head"],t,end,{"rotation":_number(a["head"],"head tilt",-25,25)})
    if "expression" in a:self.expression(actor,a["expression"],end)
   elif op not in ("reach","take","place"):
    raise PipelineError("Unsupported executable action")
  for a in actions:
   t=float(a["time"]);end=t+float(a.get("duration",.5));ident=a["node"];op=a["type"];hand=a.get("hand","front")
   if op=="pose":
    for side in ("front","back"):
     if side+"_hand" in a:self.hand(ident,side,t,end,local=a[side+"_hand"])
   elif op in ("reach","take"):
    target=a.get("target")
    if target not in self.nodes:raise PipelineError(f"Reach/take target {target!r} must name one of these scene nodes: "+", ".join(self.nodes))
    point=self.target(target,end)
    parent=self.hand(ident,hand,t,end,target_world=point)
    if op=="take":
     if target not in self.props:raise PipelineError("Only a prop can be taken")
     self.ownership(target,parent,end)
   elif op=="place":
    obj=a.get("object");target=a.get("target")
    if obj not in self.props or target not in self.nodes:raise PipelineError("Place needs the held object and a target surface")
    segment=self.prop_segment(obj,t)
    if segment["parent"]!=self.actors.get(ident,{}).get("parts",{}).get("forearm_"+hand):raise PipelineError(f"The selected actor hand must hold the object before placing it: actor={ident!r}, hand={hand!r}, object={obj!r}, time={t:g}s, current_parent={segment['parent']!r}. Use an explicit take before place; reach alone does not acquire a prop.")
    self.hand(ident,hand,t,end,target_world=self.target(target,end))
    pose=self.prop_world(obj,end)
    self.ownership(obj,"",end,pose)
   changed=[lid for lid in self.layers if lid.startswith(ident+"__")]
   description=str(a.get("description","")).strip()
   if not description:raise PipelineError("Each action must explain its visible narrative consequence")
   self.events.append({"time":min(end,self.seconds),"description":description,"layer_ids":changed,"sfx":a.get("sfx","none")})
  return self

 def finish(self,scene_id):
  # A held object's local counter-rotation/scale simulates the wrist keeping it
  # upright while its elbow and shoulder move. Attachment points remain exact.
  for ident,prop in self.props.items():
   n=prop["node"]
   for index,segment in enumerate(prop["segments"]):
    if segment["end"]-segment["start"]<.001:continue
    base=segment["base"];pivot=base[:2,2]
    drawing=prop_art("paper_flat",str(n.get("text",""))) if n["prop"]=="paper" and not segment["upright"] else prop["svg"]
    art='<g transform="'+_matrix_text(base)+'">'+drawing+'</g>'
    lid=self.add(ident+"__segment_"+str(index),art,segment["parent"],pivot,segment["start"],segment["end"],order=n.get("z",3))
    if segment["parent"]!=n["master"]:
     # Ownership changes do not discard the prop's directed visibility track.
     self.layers[lid]["keyframes"]=[{"time":f["time"],"opacity":f["opacity"],"ease":f.get("ease","smooth")} for f in self.layers[n["master"]]["keyframes"]]
    if segment["upright"]:
     initial=self.world(segment["parent"],segment["start"])
     self.layers[lid]["stabilize_parent"]=[float(x) for x in initial[:2,:2].flatten()]
  ordered=[ident for _,_,ident in sorted(self.order)]
  if len(ordered)>100:raise PipelineError("Scene exceeds the 100-layer render budget")
  svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'+''.join('<g id="'+ident+'">'+self.art[ident]+'</g>' for ident in ordered)+'</svg>'
  camera=[]
  camera_input=self.spec.get("camera") or [{"time":0,"zoom":1,"focus_x":960,"focus_y":540}]
  if not isinstance(camera_input,list) or any(not isinstance(f,dict) for f in camera_input):raise PipelineError("Camera needs timed framing objects")
  for frame in camera_input:
   at=_number(frame.get("time"),"camera time",0,self.seconds)
   zoom=_number(frame.get("zoom",1),"camera zoom",1,3)
   fx=_number(frame.get("focus_x",960),"camera focus x",0,1920)
   fy=_number(frame.get("focus_y",540),"camera focus y",0,1080)
   fx=max(960/zoom,min(1920-960/zoom,fx));fy=max(540/zoom,min(1080-540/zoom,fy))
   camera.append({"time":at,"scale":zoom,"x":(960-fx)*zoom,"y":(540-fy)*zoom,"ease":"smooth"})
  result={"scene_id":str(scene_id),"duration":self.seconds,"background":"#F4E6C8","svg":svg,
   "layers":[self.layers[ident] for ident in ordered],
   "camera":{"keyframes":camera},"events":self.events,
   "asset_ids":sorted(self.used)}
  if self.gesture_interruptions:result["gesture_interruptions"]=self.gesture_interruptions
  validate_scene(result)
  return result

def compile_scene(spec,seconds,assets=(),scene_id="scene"):
 if not isinstance(spec,dict) or spec.get("setting") not in SETTINGS:raise PipelineError("Choose a supplied scene setting")
 return Scene(spec,seconds,assets).execute().finish(scene_id)
