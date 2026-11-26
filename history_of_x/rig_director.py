"""Gemini directs original illustrated assets through executable scene actions."""
from __future__ import annotations
import copy
import os
import re
from pathlib import Path
from .core import ROOT,PipelineError,key,read_json,save_json
from .gemini import QuotaDeferred
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
Sparse, motivated camera changes; no shakes. The camera interpolates between keys: repeat the current framing key to hold a shot before a short motivated reframing. Keep documents/essential words completely inside detail shots. Do not move a camera merely to manufacture activity.
Trusted production_director_notes specify the intended visual explanation. Follow them with actual executable actions, not descriptive promises. A formation moves as one group: use separate nodes to split columns or show opposing movements. Use short .15–.3 second photo fades rather than long translucent ghost overlays.
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
  "setting":{"type":"string","enum":list(SETTINGS)},"nodes":{"type":"array","minItems":1,"maxItems":12,"items":node},
  "actions":{"type":"array","minItems":3,"maxItems":24,"items":action},
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
  program["events"].append({"time":reserved,"description":"The illustrated explanation continues after the genuine footage.","layer_ids":[],"sfx":"none"})
 events=sorted(program["events"],key=lambda e:e["time"])
 if seconds>12 and (len(events)<3 or any(b-a>7 for a,b in zip([0]+[e["time"] for e in events],[e["time"] for e in events]+[seconds]))):
  raise PipelineError("Add actual narrative developments at intervals of3–6seconds, including near the beginning and ending")
 program["events"]=events
 program["director_mode"]="original-rigged-actors"
 return program

def compact_payload(payload):
 # Phrase timings retain the performance cues with less per-word JSON overhead.
 # The full word alignment remains untouched in the speech checkpoint.
 payload=copy.deepcopy(payload)
 words=payload.pop("word_timing",[])
 if words:
  payload["phrase_timing"]=[[" ".join(str(w[0]) for w in words[i:i+5]),words[i][1],words[min(i+4,len(words)-1)][2]] for i in range(0,len(words),5)]
 return payload

def _text_request(api,instruction,payload,shape,max_output,primary):
 routes=getattr(api,"_director_fallbacks",{})
 selected=routes.get(primary,primary)
 def request(model):
  return api.text(instruction,payload,shape,max_output=max(max_output,5000) if model.startswith("gemma-") else max_output,preserve_bounds=True,model=model)
 try:return request(selected)
 except PipelineError as exc:
  unavailable=isinstance(exc,QuotaDeferred) or any(reason in str(exc) for reason in ("unavailable after three attempts","network deadline"))
  if not unavailable or selected!=primary:raise
  backup="gemini-3.6-flash" if primary.startswith("gemma-") else "gemini-3.5-flash-lite" if primary=="gemini-3.1-flash-lite" else "gemma-4-31b-it" if primary in ("gemini-3.6-flash","gemini-3.8-flash","gemini-4-hydrogen") else "gemma-4-26b-a4b-it"
  print(f"Scene direction: {primary} unavailable or free quota deferred; trying verified free model {backup}.",flush=True)
  result=request(backup)
  api._director_fallbacks={**routes,primary:backup}
  return result

def _request(api,payload,primary):
 return _text_request(api,CONTRACT,compact_payload(payload),schema(),3500,primary)

def plan_scene(api,scene,spoken,assets,directory,style=None,request_only=False,preplanned=None,repair=True):
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
 notes_path=ROOT/"assets/style/production-direction.json"
 if notes_path.exists():
  for record in read_json(notes_path).get("passages",[]):
   if record.get("narration")==scene["narration"]:
    context["production_director_notes"]=record["directing_notes"];break
 correction=None
 correction_path=ROOT/"assets/style/production-corrections.json"
 if correction_path.exists():
  correction=next((r for r in read_json(correction_path).get("records",[]) if r.get("narration")==scene["narration"]),None)
 if correction:context["production_direction_revision"]=key(correction["spec"])
 primary=os.getenv("GEMINI_MODEL","gemini-3.1-flash-lite")
 identity=key("rigged-scene-v1",VERSION,CONTRACT,schema(),primary,context)
 directory=Path(directory)/"rigged";target=directory/(identity+".json")
 existing=read_json(target) if target.exists() else None
 if existing is None:
  # A validated direction is reusable across provider routing changes. Compare
  # the exact narration, timings, assets and contract fingerprint before reuse.
  for other in ("gemini-4-hydrogen","gemini-3.6-flash","gemini-3.1-flash-lite","gemini-3.5-flash-lite","gemini-3.8-flash","gemma-4-26b-a4b-it","gemma-4-31b-it"):
   alternate=directory/(key("rigged-scene-v1",VERSION,CONTRACT,schema(),other,context)+".json")
   if alternate.exists():
    existing=read_json(alternate)
    break
 feedback_id=key(feedback)
 if correction and feedback_id in correction.get("feedback_ids",[]) and (not existing or existing.get("feedback_id") in correction.get("feedback_ids",[])):
  spec=copy.deepcopy(correction["spec"])
  program=_program(spec,seconds,approved,ident,reserved,archives)
  program["direction_source"]="Original production-director refinement of Gemini blocking"
  save_json(target,{"spec":spec,"program":program,"feedback_id":feedback_id,"direction_source":program["direction_source"]})
  print(f"Validated director-refined scene {ident}: {len(program['layers'])} layers; creative review pending",flush=True)
  return {"accepted":program} if request_only else program
 if existing and (not feedback or existing.get("feedback_id")==feedback_id):
  try:
   # Recompile the saved model directions after renderer/art fixes. No API call.
   program=_program(existing["spec"],seconds,approved,ident,reserved,archives)
   save_json(target,{**existing,"program":program})
   return {"accepted":program} if request_only else program
  except (PipelineError,ValueError,KeyError,TypeError):
   pass
 payload={**context}
 if feedback:payload["required_revision"]=feedback
 if existing:payload["previous_plan"]=existing["spec"]
 # Prefer the latest saved repair, including drafts produced through a different
 # verified free model. Exact context/contract identity and feedback must match.
 draft=None
 for draft_index in (1,0):
  for candidate_model in (primary,"gemini-4-hydrogen","gemini-3.6-flash","gemini-3.1-flash-lite","gemini-3.5-flash-lite","gemini-3.8-flash","gemma-4-26b-a4b-it","gemma-4-31b-it"):
   candidate_id=key("rigged-scene-v1",VERSION,CONTRACT,schema(),candidate_model,context)
   candidate=directory/(candidate_id+"-"+feedback_id+f"-draft-{draft_index}.json")
   if candidate.exists():
    draft=read_json(candidate);break
  if draft is not None:break
 if request_only:
  prepared={"instruction":CONTRACT,"payload":compact_payload(payload),"schema":schema()}
  if draft is not None:prepared["draft"]=draft
  return prepared
 if preplanned is None and draft is not None:preplanned=draft
 for attempt in range(2):
  draft_path=directory/(identity+"-"+feedback_id+f"-draft-{attempt}.json")
  if attempt==0:
   spec=copy.deepcopy(preplanned) if preplanned is not None else read_json(draft_path) if draft_path.exists() else _request(api,payload,primary)
  else:
   # draft-1 is useful as the starting point after a restart, but it has
   # already failed validation here. Never read that same rejected draft
   # again as the new repair. A persisted round also distinguishes the
   # request from the provider's response cache after a resumed failure.
   repair_state=directory/(identity+"-"+feedback_id+"-repair-state.json")
   previous=read_json(repair_state) if repair_state.exists() else {}
   repair_round=int(previous.get("round",0))+1
   save_json(repair_state,{"round":repair_round})
   payload={**payload,"repair_round":repair_round}
   spec=_request(api,payload,primary)
  save_json(draft_path,spec)
  try:
   from .rig_repair import explicit_pickups
   spec,repairs=explicit_pickups(spec)
   program=_program(spec,seconds,approved,ident,reserved,archives)
   if repairs:
    program["direction_repairs"]=repairs
    print(f"Made {len(repairs)} contact pickup(s) explicit in scene {ident}; strict animation checks passed.",flush=True)
   save_json(target,{"spec":spec,"program":program,"feedback_id":feedback_id,"local_repairs":repairs})
   print(f'Validated articulated scene {ident}: {len(program["layers"])} layers, {len(program["events"])} executed actions; creative review pending',flush=True)
   return program
  except (PipelineError,ValueError,KeyError,TypeError) as exc:
   if attempt or not repair:raise PipelineError("Rig director failed bounded repair: "+str(exc)) from exc
   payload={**payload,"previous_plan":spec,"validation_error":str(exc),
            "revision_request":"Repair the executable plan while preserving readable staging and meaningful cause/consequence. Return a complete graph."}
 raise PipelineError("No valid rigged scene")
