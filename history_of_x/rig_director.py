"""Gemini directs original illustrated assets through executable scene actions."""
from __future__ import annotations
import copy
import os
import re
from pathlib import Path
from .core import PipelineError,key,read_json,save_json
from .rig_art import CAST,EXPRESSIONS,SETTINGS,PROPS,VERSION
from .rig_scene import compile_scene

CONTRACT = """Direct this ORIGINAL history passage as a short animated scene.
The renderer supplies our original detailed characters/scenery/props. Return an executable scene
graph, not SVG, prose instructions, icon cards, source labels or a slideshow. Every action executes.
Use the spoken meaning: setup -> decision/contact -> consequence/reaction. Develop the image every
3–6seconds. Avoid repeating the same room/table/gestures across passages. Choose a suitable setting.
A discreet year is added externally. Other text is allowed only for short essential names or ideas.
Use genuine approved historical images as purposeful documentary inserts, never as pictures on
lecterns/battlefields. They have known dates/context and cannot substitute for another event/person.
Use actors/physical reactions for human decisions, formations/routes for military relationships,
appropriate scenery/objects for material changes. A map is optional and must explain geography.
ACTOR coordinates: x is feet centre, y is floor, scale .65–1.1 usually; full rig is360x760.
Good two-person table staging: feet x680 and1220, floor1000, scale.85, facing one another.
Table at960,770; a paper grip at940,740 is reachable by both actors. Shoulders are90*scale forward
from feet and480*scale above them. Hands reach about250*scale from the shoulder, at most312*scale.
Keep people large and inside frame. Face names/period costumes must match the passage.
ACTION semantics:
move(node,x,y,duration,walk): absolute anchor destination; directed walking includes articulated gait.
show/hide(node,duration): visibility change. pose(actor,expression,head,lean,front_hand,back_hand):
head/lean are degrees; hand targets are LOCAL offsets from feet, before facing/scale.
Rest front hand[90,-230], reading[240,-350], stop[110,-670], pointing[300,-400].
reach(actor,hand,target): exactly contact the target grip. take(actor,hand,target): reach then hold
a PROP; it remains physically attached as the actor moves. After pickup move it through its holder,
not with a direct prop move; after placing it, pick it up again to move it. Another actor may take the same prop,
after the previous take finishes. place(actor,hand,object,target): hold it first, reach target surface,
then release it there. No overlapping actions on one hand. No invisible ownership changes or
floating props. Put unreachable objects closer or explicitly move the actor before contact.
Props x/y are their grip points. table's point is its tabletop centre. Paper extends upward/right
from its grip; text on it may be MAY or MUST when explaining a translated obligation.
A formation is2–5 detailed miniature figures for a military diagram, not a substitute for a
readable close actor in a human decision. Routes have2–8 world points; show/hide communicates links.
Images use approved asset_id and width/height; a full-frame insert is centred960,540,1920x1080.
Camera keys use time,zoom,focus_x,focus_y; zoom1establishes all. Framing is clamped to the scenery.
Sparse, motivated camera changes; no shakes. Do not move a camera merely to manufacture activity.
Each action needs a description of its visible NARRATIVE consequence. sfx none by default; paper,
stamp,soft_impact or sting only when motivated. No comic stings during occupation, famine or atrocities.
Use all supplied narration/timing. Do not copy a reference creator's words, characters, joke or song.
If reserved archival seconds >0, real footage covers that opening; begin indispensable illustrated
actions after it. Use the remaining time efficiently. Return only the scene graph JSON."""

def schema():
 num={"type":"number"}
 point={"type":"array","items":num,"minItems":2,"maxItems":2}
 node={"type":"object","required":["id","kind","x","y"],"properties":{
  "id":{"type":"string"},"kind":{"type":"string","enum":["actor","prop","formation","route","label","image"]},
  "x":num,"y":num,"scale":num,"start":num,"end":num,"visible":{"type":"boolean"},"z":num,
  "appearance":{"type":"string","enum":list(CAST)},"facing":{"type":"string","enum":["left","right"]},
  "expression":{"type":"string","enum":list(EXPRESSIONS)},"count":{"type":"integer"},
  "prop":{"type":"string","enum":list(PROPS)},"text":{"type":"string"},
  "asset_id":{"type":"string"},"width":num,"height":num,
  "points":{"type":"array","items":point},"color":{"type":"string","enum":["gold","rust","teal"]},
  "dashed":{"type":"boolean"}}}
 action={"type":"object","required":["type","time","duration","node","description"],"properties":{
  "type":{"type":"string","enum":["move","show","hide","pose","reach","take","place"]},
  "time":num,"duration":num,"node":{"type":"string"},"target":{"type":"string"},
  "object":{"type":"string"},"hand":{"type":"string","enum":["front","back"]},
  "x":num,"y":num,"walk":{"type":"boolean"},"expression":{"type":"string","enum":list(EXPRESSIONS)},
  "head":num,"lean":num,"front_hand":point,"back_hand":point,"description":{"type":"string"},
  "sfx":{"type":"string","enum":["none","paper","stamp","soft_impact","sting"]}}}
 return {"type":"object","required":["setting","nodes","actions"],"properties":{
  "setting":{"type":"string","enum":list(SETTINGS)},"nodes":{"type":"array","minItems":1,"maxItems":10,"items":node},
  "actions":{"type":"array","minItems":3,"maxItems":18,"items":action},
  "camera":{"type":"array","items":{"type":"object","required":["time"],"properties":{
   "time":num,"zoom":num,"focus_x":num,"focus_y":num}}}}}

def _feedback(scene_id,style):
 report=(style or {}).get("required_creative_revision",{})
 if not isinstance(report,dict):return {}
 timeline=report.get("candidate_timeline",[])
 intervals=[(s["global_start"],s["global_end"]) for s in timeline if str(s.get("scene_id"))==str(scene_id)]
 selected={}
 for field in ("problems","revision_priorities"):
  entries=[]
  for item in report.get(field,[]):
   if not isinstance(item,str):continue
   match=re.match(r"\[([\d.]+)[–-]([\d.]+)s\]",item)
   if not timeline or (match and any(float(match[1])<b and float(match[2])>a for a,b in intervals)):
    entries.append(item)
  if entries:selected[field]=entries
 return selected

def _program(spec,seconds,approved,ident,reserved,archives):
 program=compile_scene(spec,seconds,approved,ident)
 if len(program["asset_ids"])>2:raise PipelineError("Use at most two approved historical images in a scene")
 if reserved:
  if any(a["time"]<reserved-.05 for a in spec["actions"]):raise PipelineError("Begin illustrated actions after the reserved real-footage opening")
  for at in (0.,4.5)[:len(archives)]:
   program["events"].append({"time":at,"description":"Corresponding genuine historical footage plays under narration.","layer_ids":[],"sfx":"none"})
 events=sorted(program["events"],key=lambda e:e["time"])
 if seconds>12 and (len(events)<3 or any(b-a>7 for a,b in zip([0]+[e["time"] for e in events],[e["time"] for e in events]+[seconds]))):
  raise PipelineError("Add actual narrative developments at intervals of3–6seconds, including near the beginning and ending")
 program["events"]=events
 program["director_mode"]="original-rigged-actors"
 return program

def plan_scene(api,scene,spoken,assets,directory,style=None):
 seconds=float(spoken["duration"]);ident=str(scene["scene_id"])
 catalog={a["id"]:a for a in assets["assets"]}
 approved=[catalog[i] for i in assets["scenes"].get(ident,[]) if i in catalog and catalog[i].get("medium") not in ("video","archival_video")]
 archives=[catalog[i] for i in assets["scenes"].get(ident,[]) if i in catalog and catalog[i].get("medium")=="archival_video"][:2]
 reserved=4.5*len(archives) if seconds>12 else 0
 feedback=_feedback(ident,style)
 context={"scene_id":ident,"narration":scene["narration"],"date":scene["date_label"],
  "duration":seconds,"word_timing":[[w.get("word",w.get("text","")),w["start"],w["end"]] for w in spoken["words"]],
  "reserved_archival_seconds":reserved,
  "approved_images":[{k:a.get(k) for k in ("id","subject","date","context")} for a in approved],
  "cast":list(CAST),"settings":list(SETTINGS),"props":list(PROPS)}
 identity=key("rigged-scene-v1",VERSION,CONTRACT,schema(),os.getenv("GEMINI_MODEL"),context)
 directory=Path(directory)/"rigged";target=directory/(identity+".json")
 existing=read_json(target) if target.exists() else None
 feedback_id=key(feedback)
 if existing and (not feedback or existing.get("feedback_id")==feedback_id):
  try:
   # Recompile the saved model directions after renderer/art fixes. No API call.
   program=_program(existing["spec"],seconds,approved,ident,reserved,archives)
   save_json(target,{**existing,"program":program})
   return program
  except (PipelineError,ValueError,KeyError,TypeError):
   pass
 payload={**context}
 if feedback:payload["required_revision"]=feedback
 if existing:payload["previous_plan"]=existing["spec"]
 for attempt in range(2):
  draft_path=directory/(identity+"-"+feedback_id+f"-draft-{attempt}.json")
  spec=read_json(draft_path) if draft_path.exists() else api.text(CONTRACT,payload,schema(),max_output=6500,preserve_bounds=True)
  save_json(draft_path,spec)
  try:
   program=_program(spec,seconds,approved,ident,reserved,archives)
   save_json(target,{"spec":spec,"program":program,"feedback_id":feedback_id})
   print(f'Validated articulated scene {ident}: {len(program["layers"])} layers, {len(events)} executed actions; creative review pending',flush=True)
   return program
  except (PipelineError,ValueError,KeyError,TypeError) as exc:
   if attempt:raise PipelineError("Rig director failed bounded repair: "+str(exc)) from exc
   payload={**payload,"previous_plan":spec,"validation_error":str(exc),
            "revision_request":"Repair the executable plan while preserving readable staging and meaningful cause/consequence. Return a complete graph."}
 raise PipelineError("No valid rigged scene")
