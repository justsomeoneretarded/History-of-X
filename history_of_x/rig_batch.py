"""Group independent articulated directions without losing validated siblings."""
from __future__ import annotations
import copy,os
from collections import Counter
from pathlib import Path
from .core import PipelineError,key,read_json,save_json
from . import rig_director

def plan(api,script_index,speech_index,assets,directory,style,selected,size):
 directory=Path(directory);accepted={};pending=[]
 for ident,scene in script_index.items():
  if ident not in selected:continue
  spoken=speech_index[ident]
  prepared=rig_director.plan_scene(api,scene,spoken,assets,directory,style,request_only=True)
  if "accepted" in prepared:
   accepted[ident]=prepared["accepted"];continue
  item={"id":ident,"scene":scene,"spoken":spoken,"prepared":prepared}
  if "draft" in prepared:
   accepted[ident]=rig_director.plan_scene(api,scene,spoken,assets,directory,style,preplanned=prepared["draft"])
  else:pending.append(item)
 model=os.getenv("GEMINI_MODEL","gemini-4-hydrogen")
 def accept(item,spec,repair=True):
  result=rig_director.plan_scene(api,item["scene"],item["spoken"],assets,directory,style,preplanned=spec,repair=repair)
  if str(result["scene_id"])!=item["id"] or abs(result["duration"]-item["spoken"]["duration"])>.001:
   raise PipelineError("Batched articulated direction has the wrong ID or duration")
  accepted[item["id"]]=result
 for offset in range(0,len(pending),size):
  batch=pending[offset:offset+size]
  if len(batch)==1:
   item=batch[0]
   accepted[item["id"]]=rig_director.plan_scene(api,item["scene"],item["spoken"],assets,directory,style)
   continue
  individual=rig_director.schema()
  item_schema={**individual,"required":["scene_id",*individual["required"]],
    "properties":{"scene_id":{"type":"string"},**individual["properties"]}}
  shape={"type":"object","required":["scenes"],"properties":{"scenes":{
    "type":"array","minItems":len(batch),"maxItems":len(batch),"items":item_schema}}}
  instruction=rig_director.CONTRACT+"\nDirect these passages independently. Return one scenes array with each requested scene_id exactly once. Each scene retains its own duration, assets and action timing. Do not connect their staging into one scene."
  payload={"scenes":[item["prepared"]["payload"] for item in batch]}
  path=directory/"rig-batches"/(key("rig-batch-v1",model,instruction,payload,shape)+".json")
  if path.exists():response=read_json(path)
  else:
   response=rig_director._text_request(api,instruction,payload,shape,14000,model)
   actual=getattr(api,"_director_fallbacks",{}).get(model,model)
   if actual!=model:
    if isinstance(response,list):response={"scenes":response}
    if not isinstance(response,dict):raise PipelineError("Free batch recovery returned no object")
    response={**response,"generation_model":actual}
  save_json(path,response)
  specs=response if isinstance(response,list) else response.get("scenes") if isinstance(response,dict) else None
  if not isinstance(specs,list):raise PipelineError("Batched direction returned no scenes array; response type="+type(response).__name__+" keys="+str(list(response) if isinstance(response,dict) else []))
  ids=[str(spec.get("scene_id","")) for spec in specs if isinstance(spec,dict)]
  counts=Counter(ids);expected={item["id"] for item in batch}
  by_id={str(spec["scene_id"]):spec for spec in specs if isinstance(spec,dict)
          and str(spec.get("scene_id","")) in expected and counts[str(spec.get("scene_id",""))]==1}
  failures=[]
  # Save all identifiable drafts/valid siblings before any repair uses quota.
  for item in batch:
   if item["id"] not in by_id:continue
   try:accept(item,by_id[item["id"]],repair=False)
   except PipelineError:failures.append(item)
  for item in failures:accept(item,by_id[item["id"]],repair=True)
  if set(ids)!=expected or any(n!=1 for n in counts.values()):
   raise PipelineError("Batched direction IDs missing, duplicated or unexpected; valid siblings were retained")
 return {ident:accepted[ident] for ident in script_index if ident in selected}
