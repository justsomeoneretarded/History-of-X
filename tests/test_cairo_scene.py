"""The faster compositor must preserve attachment, visible motion and pose holds."""
import json
import numpy as np
import pytest
from history_of_x.core import ROOT
from history_of_x.rig_scene import compile_scene
from history_of_x.scene_film import frame_identity,scene_frame,_raster_layers
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

def test_compiled_compositor_preserves_art_and_contacts():
 pytest.importorskip("cairocffi")
 spec=json.loads((ROOT/"assets/style/rig-demo.json").read_text())
 program=compile_scene(spec,15,scene_id="test")
 raster=_raster_layers(program,1)
 compositor=CairoCompositor(program,(480,270),raster,1)
 previous=None
 for at in (2.2,5.2,7,11.2,13.2):
  actual=compositor.frame(at)
  reference=scene_frame(program,at,(480,270),raster,1)
  error=np.abs(np.asarray(actual,dtype=float)-np.asarray(reference,dtype=float))
  assert error.mean()<2
  assert (error.max(axis=2)>30).mean()<.04
  if previous is not None:assert actual.tobytes()!=previous
  previous=actual.tobytes()
