"""Batched directions must preserve voice mapping, valid siblings and quota."""
import copy,json
import pytest
from history_of_x.core import ROOT,PipelineError
from history_of_x import director_batch

def spec(ident):
 graph=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 return {"scene_id":str(ident),**graph}

def input_scenes():
 script={"scenes":[{"scene_id":i,"narration":"The document changes hands.",
                   "date_label":"1889"} for i in (1,2,3)]}
 speech={"scenes":[{"scene_id":i,"duration":15.,"words":[]} for i in (1,2,3)]}
 return script,speech,{"assets":[],"scenes":{}}

def setup(monkeypatch):
 monkeypatch.setenv("GEMINI_DIRECTOR_MODE","rigged")
 monkeypatch.setenv("GEMINI_MODEL","gemini-4-hydrogen")
 monkeypatch.setenv("GEMINI_SCENE_BATCH_SIZE","3")

def accepted_ids(directory):
 records=[]
 for path in directory.rglob("*.json"):
  value=json.loads(path.read_text())
  if isinstance(value,dict) and isinstance(value.get("program"),dict):records.append(value["program"]["scene_id"])
 return set(records)

def test_reordered_three_scene_reply_is_mapped_and_reused_without_another_call(tmp_path,monkeypatch):
 setup(monkeypatch)
 class API:
  calls=0
  def text(self,*args,**kwargs):
   self.calls+=1
   return {"scenes":[spec(3),spec(1),spec(2)]}
 api=API();script,speech,assets=input_scenes()
 result=director_batch.plan_all(api,script,speech,assets,tmp_path)
 assert list(result)==["1","2","3"] and api.calls==1
 assert [result[k]["scene_id"] for k in result]==["1","2","3"]
 assert director_batch.plan_all(api,script,speech,assets,tmp_path)==result and api.calls==1

def test_valid_siblings_survive_a_failed_physical_repair(tmp_path,monkeypatch):
 setup(monkeypatch)
 bad=spec(2)
 next(n for n in bad["nodes"] if n["id"]=="treaty")["x"]=1750
 class API:
  calls=0
  def text(self,*args,**kwargs):
   self.calls+=1
   if self.calls>1:raise PipelineError("Provider unavailable during repair")
   return {"scenes":[spec(1),bad,spec(3)]}
 script,speech,assets=input_scenes()
 with pytest.raises(PipelineError,match="Provider unavailable"):
  director_batch.plan_all(API(),script,speech,assets,tmp_path)
 assert accepted_ids(tmp_path)=={"1","3"}

def test_duplicate_ids_do_not_reassign_another_scenes_speech(tmp_path,monkeypatch):
 setup(monkeypatch)
 class API:
  def text(self,*args,**kwargs):return {"scenes":[spec(1),spec(1),spec(3)]}
 script,speech,assets=input_scenes()
 with pytest.raises(PipelineError,match="IDs missing, duplicated or unexpected"):
  director_batch.plan_all(API(),script,speech,assets,tmp_path)
 assert accepted_ids(tmp_path)=={"3"}


def test_gemini_36_bare_scene_array_is_validated_by_identity_and_cached(tmp_path,monkeypatch):
 setup(monkeypatch)
 monkeypatch.setenv("GEMINI_MODEL","gemini-3.6-flash")
 class API:
  calls=0
  def text(self,*args,**kwargs):
   self.calls+=1
   return [spec(3),spec(1),spec(2)]
 api=API();script,speech,assets=input_scenes()
 result=director_batch.plan_all(api,script,speech,assets,tmp_path)
 assert list(result)==["1","2","3"] and api.calls==1
 assert [result[k]["scene_id"] for k in result]==["1","2","3"]
 assert director_batch.plan_all(api,script,speech,assets,tmp_path)==result and api.calls==1
