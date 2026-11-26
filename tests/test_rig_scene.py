"""Articulated contact, attachment continuity and actual rendered prop stability."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from history_of_x.core import ROOT,PipelineError
from history_of_x.rig_scene import Scene,compile_scene
from history_of_x.scene_film import scene_frame,validate_scene
from history_of_x.rig_art import actor_parts

def demo():
 return json.loads((ROOT/"assets/style/rig-demo.json").read_text())

def wrist(scene,actor,t):
 rig=scene.actors[actor]
 source=rig["base"]@np.array([270,530,1.])
 return (scene.world(rig["parts"]["forearm_front"],t)@source)[:2]

def test_two_facing_actors_reach_exactly_and_transfer_without_a_jump():
 s=Scene(demo(),15,[]).execute()
 for actor,at in (("envoy",2.2),("taytu",5.2)):
  assert wrist(s,actor,at)==pytest.approx(s.prop_world("treaty",at)[:2,2],abs=1e-6)
  assert s.prop_world("treaty",at-1e-6)==pytest.approx(s.prop_world("treaty",at+1e-6),abs=1e-3)
 assert s.prop_world("treaty",11.2)[:2,2]==pytest.approx([960,770],abs=1e-6)

def test_holding_keeps_the_document_upright_while_the_arm_bends():
 spec=demo();spec["camera"]=[{"time":0}]
 s=Scene(spec,15,[]).execute();program=s.finish("test")
 validate_scene(program)
 for at in (5.2,7,10.5):
  point=s.prop_world("treaty",at)[:2,2]
  frame=scene_frame(program,at,(1920,1080))
  pixel=frame.getpixel((round(point[0]+60),round(point[1]-55)))
  assert pixel==pytest.approx((246,232,200),abs=3)
 point=s.prop_world("treaty",12.5)[:2,2]
 released=scene_frame(program,12.5,(1920,1080))
 assert released.getpixel((round(point[0]+145),round(point[1]-10)))==pytest.approx((246,232,200),abs=3)
 assert any(layer.get("stabilize_parent") for layer in program["layers"])

def test_unreachable_prop_is_reported_instead_of_floating_into_a_hand():
 spec=demo()
 next(n for n in spec["nodes"] if n["id"]=="treaty")["x"]=1750
 with pytest.raises(PipelineError,match="cannot reach"):
  compile_scene(spec,15)

def test_camera_framing_cannot_expose_empty_outside_scenery():
 spec=demo();spec["camera"]=[{"time":0,"zoom":1.1,"focus_x":1900,"focus_y":50}]
 p=compile_scene(spec,15)
 camera=p["camera"]["keyframes"][0]
 assert abs(camera["x"])<=96.001
 assert abs(camera["y"])<=54.001

def test_unknown_scene_actions_are_never_silently_ignored():
 spec=demo();spec["actions"][0]["invented_action"]=True
 with pytest.raises(PipelineError,match="Unknown action"):
  compile_scene(spec,15)

def test_original_people_have_connected_rigs_and_distinct_costumes():
 male=actor_parts("menelik");female=actor_parts("taytu")
 assert dict((p,s) for p,s,_,_ in male)["head"] != dict((p,s) for p,s,_,_ in female)["head"]
 for parts in (male,female):
  names={p for p,_,_,_ in parts}
  assert {"head","torso","upper_front","forearm_front","leg_front","face_angry"}<=names
  assert all(not parent or parent in names for _,_,parent,_ in parts)


def test_pickup_object_alias_preserves_the_same_contact_and_visibility_track():
 spec=demo()
 take=spec["actions"][0];take["object"]=take.pop("target")
 spec["actions"].append({"type":"hide","time":7.5,"duration":.5,"node":"treaty",
                         "description":"The document is removed from view."})
 scene=Scene(spec,15,[]).execute();program=scene.finish("test")
 assert wrist(scene,"envoy",2.2)==pytest.approx(scene.prop_world("treaty",2.2)[:2,2],abs=1e-6)
 from history_of_x.scene_film import interpolate
 held=next(l for l in program["layers"] if l["id"].startswith("treaty__segment_")
           and l["start"]<=8<l["end"])
 assert interpolate(held["keyframes"],8)["opacity"]==0

def test_historical_images_are_full_frame_inserts_above_the_acting_set(tmp_path):
 from PIL import Image
 image=tmp_path/"archive.jpg";Image.new("RGB",(32,32),"#825533").save(image)
 spec=demo()
 spec["nodes"].append({"id":"archive","kind":"image","asset_id":"A1",
                       "x":500,"y":500,"width":600,"height":400})
 scene=Scene(spec,15,[{"id":"A1","path":str(image),"medium":"historical_photo"}])
 assert scene.nodes["archive"]["x"]==960 and scene.nodes["archive"]["width"]==1920
 program=scene.execute().finish("test")
 assert program["layers"][-1]["id"]=="archive__art"
 assert program["asset_ids"]==["A1"]

def test_unreachable_contact_reports_the_actual_geometry_and_time():
 spec=demo()
 next(n for n in spec["nodes"] if n["id"]=="treaty")["y"]=1000
 with pytest.raises(PipelineError,match=r"shoulder=.*target=.*distance=.*maximum=") as failure:
  compile_scene(spec,15)
 assert "2.2s" in str(failure.value)
 assert "vertical gap" in str(failure.value)


def test_vertical_formation_movement_has_articulated_gait_and_holds_when_stopped():
 from history_of_x.scene_film import interpolate
 spec={"setting":"mountains_night",
       "nodes":[{"id":"army","kind":"formation","x":960,"y":400,"count":3}],
       "actions":[{"type":"move","time":1,"duration":3,"node":"army","x":960,"y":700,"walk":True,"description":"The formation advances down the pass."},
                  {"type":"hide","time":5,"duration":.2,"node":"army","description":"The troops disappear behind the ridge."},
                  {"type":"show","time":7,"duration":.2,"node":"army","description":"The separated formation emerges."}]}
 scene=Scene(spec,9,[]).execute();program=scene.finish("army")
 legs=[l for l in program["layers"] if "_leg_" in l["id"]]
 assert len(legs)==6 and len(program["layers"])<20
 assert all(any(abs(k["rotation"])>0 for k in l["keyframes"]) for l in legs)
 assert all(interpolate(l["keyframes"],4.5)["rotation"]==0 for l in legs)
 assert interpolate(scene.layers["army__motion"]["keyframes"],4)["y"]==300
