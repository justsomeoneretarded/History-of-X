"""Actual route selection, precise feedback scope and cached action recompilation."""
import copy
import json
import pytest
from history_of_x.core import ROOT
from history_of_x import rig_director, director_batch
from history_of_x.director_film import plan_scene

def passage():
 return {"scene_id":1,"narration":"The document changed hands.","date_label":"1889"}

def spoken():
 return {"scene_id":1,"duration":15.,"words":[{"text":"document","start":.5,"end":1.}]}

def test_one_direction_call_compiles_and_recompiles_saved_actions_without_provider(tmp_path,monkeypatch):
 spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 class API:
  calls=0
  def text(self,*args,**kwargs):
   self.calls+=1
   return copy.deepcopy(spec)
 api=API();assets={"assets":[],"scenes":{}}
 result=rig_director.plan_scene(api,passage(),spoken(),assets,tmp_path)
 assert api.calls==1 and result["director_mode"]=="original-rigged-actors"
 compiled=[]
 real=rig_director.compile_scene
 def compile_again(*args,**kwargs):
  compiled.append(True)
  return real(*args,**kwargs)
 monkeypatch.setattr(rig_director,"compile_scene",compile_again)
 again=rig_director.plan_scene(api,passage(),spoken(),assets,tmp_path)
 assert again==result and compiled and api.calls==1

def test_rigged_batch_and_render_route_never_enter_freeform_svg(tmp_path,monkeypatch):
 monkeypatch.setenv("GEMINI_DIRECTOR_MODE","rigged")
 calls=[]
 def direct(api,scene,speech,*args):
  calls.append(scene["scene_id"])
  return {"scene_id":str(scene["scene_id"]),"duration":speech["duration"]}
 monkeypatch.setattr(rig_director,"plan_scene",direct)
 result=director_batch.plan_all(object(),{"scenes":[passage()]},{"scenes":[spoken()]},
                                {"assets":[],"scenes":{}},tmp_path)
 assert list(result)==["1"] and calls==[1]
 assert plan_scene(object(),passage(),spoken(),{},tmp_path)["scene_id"]=="1"
 assert calls==[1,1]

def test_revision_feedback_only_invalidates_overlapping_observed_scenes():
 report={"candidate_timeline":[{"scene_id":1,"global_start":0,"global_end":15},
                               {"scene_id":3,"global_start":15,"global_end":30}],
         "problems":["[0–15s] The first contact is obscured.",
                     "[16–29s] The portrait covers the new route."],
         "revision_priorities":["[16–29s] Uncover the route."]}
 style={"required_creative_revision":report}
 assert rig_director._feedback(1,style)=={"problems":[report["problems"][0]]}
 assert rig_director._feedback(3,style)["revision_priorities"]==report["revision_priorities"]
 assert rig_director._feedback(9,style)=={}
