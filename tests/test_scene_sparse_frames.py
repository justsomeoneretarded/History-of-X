"""Sparse choreography remains executable and enforces existing safety rules."""
import pytest

from history_of_x.core import PipelineError
from history_of_x.scene_film import DEFAULT, interpolate, schema, transform_matrix, validate_scene


def sparse_scene():
    return {
        "scene_id": "sparse-acting", "duration": 8, "background": "#ffffff",
        "svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
               '<g id="body"><rect x="100" y="100" width="80" height="80"/></g>'
               '<g id="hand"><circle cx="200" cy="100" r="20"/></g></svg>',
        "layers": [
            {"id": "body", "pivot": [100, 100], "start": 0, "end": 8,
             "keyframes": [{"time": 0}, {"time": 2, "x": 40, "ease": "linear"},
                           {"time": 4, "rotation": 20}, {"time": 8}]},
            {"id": "hand", "parent": "body", "pivot": [180, 100], "start": 0, "end": 8,
             "keyframes": [{"time": 0, "rotation": 15},
                           {"time": 3, "rotation": -10}, {"time": 8}]}],
        "camera": {"keyframes": [{"time": 0}]},
        "events": [{"time": 3, "description": "The hand reaches as the actor advances.",
                    "layer_ids": ["body", "hand"]}],
    }


def test_schema_requires_only_time_for_layer_and_camera_keyframes():
    properties = schema()["properties"]
    frames = properties["layers"]["items"]["properties"]["keyframes"]["items"]
    camera_frames = properties["camera"]["properties"]["keyframes"]["items"]
    assert frames["required"] == camera_frames["required"] == ["time"]
    assert set(frames["properties"]) == {"time", "ease", *DEFAULT}
    assert "previous pose" in frames["description"]


def test_sparse_authored_poses_inherit_channels_and_execute_parent_rig():
    scene = sparse_scene()
    assert validate_scene(scene) is scene
    body, hand = scene["layers"]
    assert interpolate(scene["camera"]["keyframes"], 3) == DEFAULT
    assert interpolate(body["keyframes"], 1)["x"] == 20
    pose = interpolate(body["keyframes"], 8)
    assert pose == {**DEFAULT, "x": 40, "rotation": 20}
    assert interpolate(hand["keyframes"], 8)["rotation"] == -10
    body_matrix = transform_matrix(pose, body["pivot"])
    hand_matrix = transform_matrix(interpolate(hand["keyframes"], 8), hand["pivot"])
    # The parent's transform carries the child's shoulder along with the body.
    assert body_matrix @ hand_matrix @ [180, 100, 1] == pytest.approx(
        body_matrix @ [180, 100, 1])


@pytest.mark.parametrize("change", [
    {"walk_cycle": 2}, {"x": True}, {"y": float("inf")}, {"rotation": "20"},
    {"scale": 0}, {"opacity": 2}, {"reveal": -.1}, {"ease": "bounce"},
])
def test_sparse_frames_still_reject_unknown_channels_and_invalid_values(change):
    scene = sparse_scene()
    scene["layers"][0]["keyframes"][0].update(change)
    with pytest.raises(PipelineError):
        validate_scene(scene)


@pytest.mark.parametrize("parent", ["unknown", "hand"])
def test_sparse_rig_still_rejects_missing_parents_and_cycles(parent):
    scene = sparse_scene()
    scene["layers"][0]["parent"] = parent
    with pytest.raises(PipelineError, match="parent"):
        validate_scene(scene)


def test_sparse_program_still_rejects_external_svg_resources():
    scene = sparse_scene()
    scene["svg"] = scene["svg"].replace(
        '<circle cx="200"', '<image href="https://example.com/image.png"/><circle cx="200"')
    with pytest.raises(PipelineError, match="local IDs or embedded"):
        validate_scene(scene)
