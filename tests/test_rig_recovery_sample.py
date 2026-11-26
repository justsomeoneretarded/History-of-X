"""A real model-produced scene stays inside the existing actor/layer budgets."""
import json
from PIL import Image
from history_of_x.core import ROOT
from history_of_x.rig_scene import compile_scene

def test_saved_eleven_node_twenty_one_action_scene_compiles_with_bounded_layers(tmp_path):
    spec=json.loads((ROOT/"assets/style/rig-recovery-sample.json").read_text())
    picture=tmp_path/"test.jpg";Image.new("RGB",(32,32),"#a88b61").save(picture)
    assets=[{"id":"ethiopia-b79e9add8a53d883870832ec","path":str(picture),"medium":"historical_photo"}]
    result=compile_scene(spec,18.65,assets,"1")
    assert len(result["layers"])<=100
    assert len(result["events"])==21
    assert any("figure" in layer["id"] for layer in result["layers"])
