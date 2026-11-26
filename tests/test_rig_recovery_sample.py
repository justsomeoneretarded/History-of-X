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


def test_lalibela_ruler_picks_up_cross_with_real_contact_and_continuous_ownership(tmp_path):
    records=json.loads((ROOT/"assets/style/production-corrections.json").read_text())["records"]
    spec=next(row["spec"] for row in records if row["scene_id"]==5)
    picture=tmp_path/"church.jpg";Image.new("RGB",(32,32),"#967654").save(picture)
    result=compile_scene(spec,25.,[{"id":"ethiopia-447565849691fcf32ca512ed","path":str(picture),"medium":"modern_documentary_photo"}],"5")
    assert any(event["time"]==9 for event in result["events"])
    assert len(result["layers"])<=100


def test_1941_archive_cannot_illustrate_a_medieval_dynastic_restoration():
    from history_of_x.documentary_assets import matching_assets
    archive={"id":"1941","tags":["restoration"],"medium":"historical_photo","event_period":[1941,1941]}
    assert matching_assets({"date_label":"1270 AD","narration":"The Solomonic restoration."},[archive])==[]
    assert matching_assets({"date_label":"1941","narration":"The monarchy's restoration."},[archive])==["1941"]
