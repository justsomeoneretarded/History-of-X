"""The director-refined passages must execute exact real prop transfers."""
import json
import pytest
from PIL import Image
from history_of_x.core import ROOT
from history_of_x.rig_director import plan_scene
from history_of_x.rig_scene import Scene


@pytest.mark.parametrize("ident",[1,3,11])
def test_director_refinements_compile_without_a_provider_and_preserve_ownership(ident,tmp_path):
    record=next(r for r in json.loads((ROOT/"assets/style/production-corrections.json").read_text())["records"] if r["scene_id"]==ident)
    picture=tmp_path/"approved-test-image.jpg"
    Image.new("RGB",(32,32),"#ccbbaa").save(picture)
    ids=[n["asset_id"] for n in record["spec"]["nodes"] if n["kind"]=="image"]
    assets={"assets":[{"id":i,"path":str(picture),"medium":"historical_photo"} for i in ids],
            "scenes":{str(ident):ids}}
    class NoProvider:
        def text(self,*args,**kwargs):raise AssertionError("A matched original director refinement does not need another model call")
    program=plan_scene(NoProvider(),{"scene_id":ident,"narration":record["narration"],"date_label":"Historical passage"},
                       {"scene_id":ident,"duration":record["duration_seconds"],"words":[]},assets,tmp_path/"programs")
    assert program["scene_id"]==str(ident) and program["direction_source"]
    scene=Scene(record["spec"],record["duration_seconds"],assets["assets"]).execute()
    if ident==3:
        assert scene.prop_segment("gold_coin",8)["parent"]=="trader_foreign__forearm_back"
        assert scene.prop_segment("trade_crate",10)["parent"]=="merchant_aksum__forearm_front"
    elif ident==11:
        assert scene.prop_segment("doc_italian",16)["parent"]=="menelik_actor__forearm_front"
        assert scene.prop_world("doc_italian",22)[:2,2]==pytest.approx([960,770],abs=1e-6)

    else:
        assert len(scene.formations)==4
        assert len(program["layers"])<=100
