"""A model's reach followed by placement must become an actual, validated pickup."""
import json
import pytest
from history_of_x.core import ROOT, PipelineError
from history_of_x.rig_repair import explicit_pickups
from history_of_x.rig_scene import Scene, compile_scene


def source():
    return json.loads((ROOT / "assets/style/rig-demo.json").read_text())


def test_missing_transfer_is_repaired_at_real_contact_without_changing_timing():
    spec = source()
    transfer = next(a for a in spec["actions"] if a["type"] == "take" and a["node"] == "taytu")
    transfer["type"] = "reach"
    with pytest.raises(PipelineError, match="actor='taytu'.*object='treaty'"):
        compile_scene(spec, 15)
    repaired, changes = explicit_pickups(spec)
    assert changes and changes[0]["actor"] == "taytu"
    assert transfer["type"] == "reach"
    assert [(a["time"], a["duration"]) for a in repaired["actions"]] == [
        (a["time"], a["duration"]) for a in spec["actions"]]
    scene = Scene(repaired, 15, []).execute()
    assert scene.prop_segment("treaty", 7)["parent"] == "taytu__forearm_front"
    compile_scene(repaired, 15)


def test_a_placement_without_a_prior_contact_cannot_create_a_pickup():
    spec = source()
    spec["actions"] = [a for a in spec["actions"] if not (a["type"] == "take" and a["node"] == "taytu")]
    repaired, changes = explicit_pickups(spec)
    assert not changes and repaired == spec
    with pytest.raises(PipelineError, match="must hold the object"):
        compile_scene(repaired, 15)


def test_a_competing_later_owner_is_not_overridden():
    spec = source()
    transfer = next(a for a in spec["actions"] if a["type"] == "take" and a["node"] == "taytu")
    transfer["type"] = "reach"
    spec["actions"].append({"type": "take", "time": 8., "duration": .5,
        "node": "envoy", "hand": "front", "target": "treaty",
        "description": "The envoy retrieves the document before its supposed placement."})
    repaired, changes = explicit_pickups(spec)
    assert not changes and repaired == spec
