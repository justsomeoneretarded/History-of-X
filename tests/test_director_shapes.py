"""Malformed prompt-schema responses enter bounded repair, never silent rendering."""
import copy
import json

import pytest
import requests

from history_of_x.core import PipelineError
from history_of_x.director_film import plan_scene
from history_of_x.scene_film import treaty_proof, validate_scene


def program():
    result = treaty_proof()
    result["scene_id"] = "1"
    return result


@pytest.mark.parametrize("field,value", [
    ("background", None), ("background", []), ("background", 7),
    ("scene_id", None), ("scene_id", []), ("scene_id", ""),
    ("layers", [None]), ("layers", [[]]), ("layers", ["body"]),
    ("events", [None]), ("events", [[]]), ("events", ["action"]),
])
def test_wrong_scene_shapes_raise_pipeline_error(field, value):
    result = program()
    result[field] = value
    with pytest.raises(PipelineError):
        validate_scene(result)


@pytest.mark.parametrize("value", [None, "", [], {}])
def test_layer_identifiers_are_validated_before_sets(value):
    result = program()
    result["layers"][0]["id"] = value
    with pytest.raises(PipelineError, match="layer id"):
        validate_scene(result)


@pytest.mark.parametrize("value", [None, "room", {}, [["room"]], [1]])
def test_event_layer_references_require_an_array_of_strings(value):
    result = program()
    result["events"][0]["layer_ids"] = value
    with pytest.raises(PipelineError, match="layer_ids"):
        validate_scene(result)


@pytest.mark.parametrize("value", [None, [], {}, 1])
def test_event_sound_requires_a_supported_string(value):
    result = program()
    result["events"][0]["sfx"] = value
    with pytest.raises(PipelineError, match="sound effect"):
        validate_scene(result)


@pytest.mark.parametrize("target", ["layer", "camera", "event"])
def test_unknown_direction_is_not_silently_discarded(target):
    result = program()
    record = {"layer": result["layers"][0], "camera": result["camera"],
              "event": result["events"][0]}[target]
    record["walk_cycle"] = True
    with pytest.raises(PipelineError, match="Unknown"):
        validate_scene(result)


class SceneResponses:
    def __init__(self, first):
        self.replies = [copy.deepcopy(first), program()]
        self.calls = []

    def text(self, instruction, payload, schema, max_output):
        self.calls.append(copy.deepcopy(payload))
        return self.replies.pop(0)


@pytest.mark.parametrize("first", [
    None, [], "not a program",
    {**program(), "duration": None},
    {**program(), "duration": []},
    {**program(), "duration": True},
    {**program(), "duration": "15"},
    {**program(), "svg": None},
    {**program(), "svg": []},
    {**program(), "background": None},
    {**program(), "layers": [None]},
    {**program(), "events": [{"time": 1, "description": "Move", "layer_ids": None}]},
])
def test_malformed_draft_receives_exactly_one_bounded_scene_repair(tmp_path, monkeypatch, first):
    monkeypatch.delenv("GEMINI_DIRECTOR_POSITIVE_EXAMPLE", raising=False)
    api = SceneResponses(first)
    scene = {"scene_id": 1, "narration": "A ruler rejects the disputed agreement."}
    result = plan_scene(api, scene, {"duration": 15., "words": []},
                        {"assets": [], "scenes": {}}, tmp_path)
    assert result["scene_id"] == "1"
    assert len(api.calls) == 2
    assert api.calls[1]["previous_draft"] == first
    assert api.calls[1]["validation_error"]


def test_request_diagnostics_include_final_text_size_without_content(tmp_path, monkeypatch, capsys):
    from history_of_x.media_api import MediaAPI
    monkeypatch.setenv("GEMINI_SCHEMA_MODE", "prompt")
    monkeypatch.setenv("GEMINI_API", "diagnostic-test-secret")
    monkeypatch.setenv("GEMINI_MEDIA_LEDGER", str(tmp_path / "ledger.json"))

    class Session:
        def post(self, url, **kwargs):
            self.body = kwargs["json"]
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"candidates": [{
                "finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}).encode()
            return response

    session = Session()
    api = MediaAPI(tmp_path / "cache", session=session, clock=lambda: 1000)
    body = {"contents": [{"role": "user", "parts": [{"text": "PRIVATE SOURCE TEXT"}]}],
            "generationConfig": {"maxOutputTokens": 10000,
                                 "responseJsonSchema": {"type": "object"}}}
    api.request("gemini-3.8-flash", "models/gemini-3.8-flash:generateContent", body, "text")
    output = capsys.readouterr().out
    text_size = len(session.body["contents"][0]["parts"][0]["text"])
    assert f"text_chars={text_size}" in output
    assert "max_output=10000" in output
    assert "schema=prompt" in output
    assert "PRIVATE SOURCE TEXT" not in output
    assert "diagnostic-test-secret" not in output
