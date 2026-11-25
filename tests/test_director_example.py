"""Positive examples retain actual authored detail and channel semantics, not a quality score."""
import copy

import pytest
from PIL import Image

from history_of_x.director_example import _sparse, positive_request
from history_of_x.scene_film import acted_treaty_proof, interpolate


def test_sparse_example_preserves_every_authored_pose_and_easing():
    source = acted_treaty_proof()
    for layer in [*source["layers"], source["camera"]]:
        frames = layer["keyframes"]
        sparse = _sparse(frames)
        times = [frame["time"] for frame in frames]
        times += [(a["time"] + b["time"]) / 2 for a, b in zip(frames, frames[1:])]
        for time in times:
            assert interpolate(sparse, time) == pytest.approx(interpolate(frames, time))


def test_original_example_and_guide_never_become_approved_historical_assets(tmp_path):
    # Seed a valid cached JPEG so this transport test needs no SVG rasterizer.
    guide = tmp_path / "original-acting-craft-guide-v1.jpg"
    Image.new("RGB", (320, 180), "#789077").save(guide)
    payload = {"scene_id": "9", "duration": 20, "scene": {"narration": "Original passage."},
               "approved_assets": [{"id": "approved", "date": "1896", "context": "Portrait."}]}
    original = copy.deepcopy(payload)
    instruction, result, images, roles = positive_request(
        "Original scene contract", payload, [tmp_path / "approved.jpg"], tmp_path)
    assert payload == original
    assert result["approved_assets"] == original["approved_assets"]
    assert result["scene"] == original["scene"]
    example = result["original_craft_example"]
    assert example["svg_artwork"] == acted_treaty_proof()["svg"]
    assert any(layer["id"] == "left_reading_arm" for layer in example["choreography_excerpt"])
    assert images[-1] == guide
    assert "not a historical subject" in roles[-1]
    assert "not a third-party creator" in instruction
    assert "unacceptable proxy" in instruction
    assert "Do not reuse" in instruction
