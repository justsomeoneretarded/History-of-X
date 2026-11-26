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


def test_free_model_failover_is_bounded_and_does_not_retry_schema_errors():
 from history_of_x.core import PipelineError
 class API:
  def __init__(self,reason):self.models=[];self.reason=reason
  def text(self,*args,**kwargs):
   self.models.append(kwargs["model"])
   if len(self.models)==1:raise PipelineError(self.reason)
   return {"nodes":[]}
 api=API("Gemini gemini-3.1-flash-lite unavailable after three attempts")
 assert rig_director._request(api,{},"gemini-3.1-flash-lite")=={"nodes":[]}
 assert api.models==["gemini-3.1-flash-lite","gemma-4-26b-a4b-it"]
 api=API("Invalid Gemini structured output")
 with pytest.raises(PipelineError):
  rig_director._request(api,{},"gemini-3.1-flash-lite")
 assert len(api.models)==1

def test_model_switch_reuses_an_exact_accepted_scene_without_another_call(tmp_path,monkeypatch):
 spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 class API:
  calls=0
  def text(self,*args,**kwargs):self.calls+=1;return copy.deepcopy(spec)
 api=API();assets={"assets":[],"scenes":{}}
 monkeypatch.setenv("GEMINI_MODEL","gemini-3.1-flash-lite")
 first=rig_director.plan_scene(api,passage(),spoken(),assets,tmp_path)
 monkeypatch.setenv("GEMINI_MODEL","gemini-3.5-flash-lite")
 assert rig_director.plan_scene(api,passage(),spoken(),assets,tmp_path)==first
 assert api.calls==1


def test_request_compaction_preserves_alignment_without_mutating_the_checkpoint():
 words=[[f"word{i}",i/2,(i+1)/2] for i in range(12)]
 payload={"word_timing":words,"scene_id":"1"}
 class API:
  def text(self,instruction,data,schema,**kwargs):
   assert data["phrase_timing"]==[
    ["word0 word1 word2 word3 word4",0.,2.5],
    ["word5 word6 word7 word8 word9",2.5,5.],
    ["word10 word11",5.,6.]]
   assert "word_timing" not in data
   assert kwargs["max_output"]==3500
   return {"ok":True}
 assert rig_director._request(API(),payload,"gemini-3.8-flash")=={"ok":True}
 assert payload["word_timing"]==words and "phrase_timing" not in payload


def test_archive_to_illustration_cut_is_a_real_visual_development():
 spec={"setting":"mountains","nodes":[{"id":"column","kind":"formation","x":400,"y":800}],
       "actions":[{"type":"move","node":"column","time":9,"duration":3,"x":800,"y":700,"description":"The force enters the hills."},
                  {"type":"move","node":"column","time":13,"duration":2,"x":1100,"y":650,"description":"Its advance continues."},
                  {"type":"move","node":"column","time":16,"duration":2,"x":1450,"y":600,"description":"The movement reaches the defended approach."}]}
 program=rig_director._program(spec,21,[],"archive-test",9,[{},{}])
 assert [event["time"] for event in program["events"]]==[0.,4.5,9,12.,15.,18.]

def test_resuming_a_rejected_repair_requests_a_new_correction_and_then_caches_success(tmp_path):
 from history_of_x.core import PipelineError
 valid=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 invalid=copy.deepcopy(valid)
 next(node for node in invalid["nodes"] if node["id"]=="treaty")["x"]=1750
 class API:
  def __init__(self,responses):self.responses=responses;self.calls=[]
  def text(self,instruction,payload,schema,**options):
   self.calls.append(copy.deepcopy(payload))
   return copy.deepcopy(self.responses.pop(0))
 assets={"assets":[],"scenes":{}}
 first=API([invalid,invalid])
 with pytest.raises(PipelineError,match="cannot reach"):
  rig_director.plan_scene(first,passage(),spoken(),assets,tmp_path)
 assert len(first.calls)==2 and first.calls[-1]["repair_round"]==1
 resumed=API([valid])
 program=rig_director.plan_scene(resumed,passage(),spoken(),assets,tmp_path)
 assert program["scene_id"]=="1" and len(resumed.calls)==1
 assert resumed.calls[0]["repair_round"]==2
 assert "shoulder=" in resumed.calls[0]["validation_error"]
 assert rig_director.plan_scene(API([]),passage(),spoken(),assets,tmp_path)==program


def test_free_quota_fallback_is_shared_and_reuses_the_available_model():
 from history_of_x.gemini import QuotaDeferred
 class API:
  def __init__(self):self.models=[]
  def text(self,*args,**options):
   self.models.append(options["model"])
   if options["model"]=="gemini-3.8-flash":raise QuotaDeferred("Free daily limit reached")
   return {"nodes":[]}
 api=API()
 assert rig_director._request(api,{},"gemini-3.8-flash")=={"nodes":[]}
 assert rig_director._request(api,{},"gemini-3.8-flash")=={"nodes":[]}
 assert api.models==["gemini-3.8-flash","gemma-4-31b-it","gemma-4-31b-it"]
