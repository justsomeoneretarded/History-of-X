"""Gestures can yield smoothly; actual competing object contacts remain invalid."""
import json
import numpy as np
import pytest
from history_of_x.core import ROOT, PipelineError
from history_of_x.rig_scene import Scene


def sample():
    return json.loads((ROOT / "assets/style/rig-demo.json").read_text())


def test_a_pickup_interrupts_a_gesture_continuously_and_still_makes_exact_contact():
    spec=sample()
    spec["actions"].append({"type":"pose","node":"envoy","time":.5,"duration":1.5,
        "front_hand":[240,-350],"description":"The envoy gestures before reaching for the document."})
    scene=Scene(spec,15,[]).execute()
    part=scene.actors["envoy"]["parts"]["forearm_front"]
    assert scene.world(part,1.-1e-7)==pytest.approx(scene.world(part,1.+1e-7),abs=1e-3)
    wrist=scene.actors["envoy"]["base"]@np.array([270,530,1.])
    assert (scene.world(part,2.2)@wrist)[:2]==pytest.approx(scene.prop_world("treaty",2.2)[:2,2],abs=1e-6)
    assert scene.gesture_interruptions[0]["actor"]=="envoy"
    scene.finish("interrupted-gesture")


def test_a_second_physical_pickup_cannot_interrupt_an_unfinished_pickup():
    spec=sample()
    spec["actions"].append({"type":"take","node":"envoy","time":1.5,"duration":1.,
        "hand":"front","target":"treaty","description":"An invalid competing pickup."})
    with pytest.raises(PipelineError,match="physical contact ending"):
        Scene(spec,15,[]).execute()
