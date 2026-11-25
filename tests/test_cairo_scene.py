"""Compiled compositors must preserve contact, visibility and subpixel motion."""
import json
import numpy as np
import pytest
from history_of_x.core import ROOT
from history_of_x.rig_scene import Scene
from history_of_x.scene_film import frame_identity,_raster_layers
from history_of_x.cairo_scene import CairoCompositor

def test_exact_pose_signatures_reuse_only_identical_frames():
 program={"layers":[{"start":0,"end":10,"keyframes":[{"time":0},
        {"time":3},{"time":5,"x":.001}]}],
        "camera":{"keyframes":[{"time":0}]}}
 assert frame_identity(program,1)==frame_identity(program,2)
 assert frame_identity(program,3)!=frame_identity(program,3.01)
 assert frame_identity(program,9)!=frame_identity(program,10)
 program["camera"]["keyframes"].append({"time":12,"scale":1.001})
 assert frame_identity(program,1)!=frame_identity(program,2)

@pytest.mark.parametrize("recording",[False,True])
def test_compiled_compositors_keep_held_and_released_props_in_contact(recording):
 pytest.importorskip("cairocffi")
 spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 spec["camera"]=[{"time":0}]
 scene=Scene(spec,15,[]).execute();program=scene.finish("test")
 raster=None if recording else _raster_layers(program,1)
 compositor=CairoCompositor(program,(1920,1080),raster,1,recording=recording)
 previous=None
 for at in (5.2,7,10.5):
  point=scene.prop_world("treaty",at)[:2,2]
  actual=compositor.frame(at)
  assert actual.getpixel((round(point[0]+60),round(point[1]-55)))==pytest.approx((246,232,200),abs=3)
  if previous is not None:assert actual.tobytes()!=previous
  previous=actual.tobytes()
 point=scene.prop_world("treaty",12.5)[:2,2]
 released=compositor.frame(12.5)
 assert released.getpixel((round(point[0]+145),round(point[1]-10)))==pytest.approx((246,232,200),abs=3)


@pytest.mark.parametrize("with_text",[False,True])
def test_artwork_staged_offscreen_can_move_into_the_camera(with_text):
 from history_of_x.scene_film import validate_scene
 word='<text x="2100" y="450" font-family="DejaVu Sans" font-size="60" fill="#0000ff">MOVE</text>' if with_text else ""
 program={"scene_id":"entry","duration":2.,"background":"#ffffff",
  "svg":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"><g id="entry"><circle cx="2100" cy="300" r="60" fill="#ff0000"/>'+word+'</g></svg>',
  "layers":[{"id":"entry","pivot":[2100,300],"start":0,"end":2,"keyframes":[{"time":0},{"time":1,"x":-1200}]}],
  "camera":{"keyframes":[{"time":0}]},"events":[]}
 validate_scene(program)
 compositor=CairoCompositor(program,(1920,1080),recording=True)
 before=compositor.frame(0);after=compositor.frame(1)
 assert before.getpixel((900,300))==(255,255,255)
 assert after.getpixel((900,300))==(255,0,0)
 if with_text:
  word=np.asarray(after)[380:460,890:1120]
  assert ((word[:,:,2]>150)&(word[:,:,0]<100)).sum()>300
