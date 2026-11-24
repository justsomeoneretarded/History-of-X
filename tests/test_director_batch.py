"""Batch transport/checkpoint contracts, not artistic quality assertions."""
import copy

import pytest

from history_of_x import director_film
from history_of_x.core import PipelineError, save_json
from history_of_x.director_batch import plan_all


def inputs(ids=(1, 2, 3)):
    script = {"scenes": [{"scene_id": i, "narration": f"Original scene {i}."} for i in ids]}
    speech = {"scenes": [{"scene_id": i, "duration": 15., "words": []} for i in ids]}
    return script, speech, {"assets": [], "scenes": {}}


def program(identifier):
    return {"scene_id": str(identifier), "duration": 15., "svg": "<svg/>"}


class SceneHooks:
    def __init__(self):
        self.accepted = {}
        self.validations = []
        self.fail_id = None
        self.images = {}

    def __call__(self, api, scene, spoken, assets, directory, style=None,
                 request_only=False, preplanned=None):
        identifier = str(scene["scene_id"])
        if request_only:
            if identifier in self.accepted:
                return {"accepted": copy.deepcopy(self.accepted[identifier])}
            return {
                "instruction": "Draw and animate this original historical scene.",
                "payload": {"scene_id": identifier, "duration": spoken["duration"],
                            "reference_craft": {"pace": 174},
                            "illustration_bible": {"style": "original"}},
                "images": self.images.get(identifier, []),
                "schema": {"type": "object", "properties": {
                    "scene_id": {"type": "string"}, "duration": {"type": "number"},
                    "svg": {"type": "string"}}, "required": ["scene_id", "duration", "svg"]},
            }
        assert preplanned is not None
        self.validations.append(identifier)
        if identifier == self.fail_id:
            raise PipelineError("Individual scene still invalid after bounded repair")
        accepted = copy.deepcopy(preplanned)
        self.accepted[identifier] = accepted
        save_json(directory / f"test-accepted-{identifier}.json", accepted)
        return accepted


class FakeAPI:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def _response(self, kind, payload, images, max_output):
        self.calls.append({"kind": kind, "payload": copy.deepcopy(payload),
                           "images": list(images), "max_output": max_output})
        if self.replies:
            return copy.deepcopy(self.replies.pop(0))
        return {"scenes": [program(identifier) for identifier in payload["required_scene_ids"]]}

    def text(self, instruction, payload, schema, max_output):
        return self._response("text", payload, [], max_output)

    def vision(self, instruction, payload, images, schema, max_output):
        return self._response("vision", payload, images, max_output)


@pytest.fixture(autouse=True)
def default_batch_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_SCENE_BATCH_SIZE", raising=False)


@pytest.fixture
def hooks(monkeypatch):
    value = SceneHooks()
    monkeypatch.setattr(director_film, "plan_scene", value)
    return value


def test_three_new_scenes_use_two_calls_with_individual_checkpoints(tmp_path, hooks):
    api = FakeAPI()
    result = plan_all(api, *inputs(), tmp_path)
    assert list(result) == ["1", "2", "3"]
    assert [c["payload"]["required_scene_ids"] for c in api.calls] == [["1", "2"], ["3"]]
    assert [c["max_output"] for c in api.calls] == [30000, 18000]
    assert hooks.validations == ["1", "2", "3"]
    assert len(list((tmp_path / "batch-drafts").glob("*.json"))) == 3
    assert len(list(tmp_path.glob("test-accepted-*.json"))) == 3
    assert api.calls[0]["payload"]["shared_craft"]["reference_craft"]["pace"] == 174
    assert "reference_craft" not in api.calls[0]["payload"]["scenes"][0]


def test_accepted_scene_caches_consume_zero_requests(tmp_path, hooks):
    hooks.accepted = {str(i): program(i) for i in (1, 2, 3)}
    api = FakeAPI()
    result = plan_all(api, *inputs(), tmp_path)
    assert len(result) == 3
    assert api.calls == []
    assert hooks.validations == []


def test_batch_response_order_is_mapped_by_exact_scene_id(tmp_path, hooks):
    api = FakeAPI([{"scenes": [program(2), program(1)]}])
    result = plan_all(api, *inputs((1, 2)), tmp_path)
    assert list(result) == ["1", "2"]
    assert hooks.validations == ["1", "2"]


def test_missing_scene_fails_explicitly_but_keeps_valid_sibling(tmp_path, hooks):
    api = FakeAPI([{"scenes": [program(1)]}])
    with pytest.raises(PipelineError, match="missing IDs: 2"):
        plan_all(api, *inputs((1, 2)), tmp_path)
    assert set(hooks.accepted) == {"1"}
    assert (tmp_path / "test-accepted-1.json").exists()


@pytest.mark.parametrize("ids, expected", [
    ((1, 1), "duplicate IDs: 1"),
    ((1, 9), "unexpected IDs: 9"),
])
def test_duplicate_and_unknown_ids_are_not_silently_accepted(tmp_path, hooks, ids, expected):
    api = FakeAPI([{"scenes": [program(i) for i in ids]}])
    with pytest.raises(PipelineError, match=expected):
        plan_all(api, *inputs((1, 2)), tmp_path)
    assert "2" not in hooks.accepted
    if ids == (1, 1):
        assert "1" not in hooks.accepted


def test_saved_sibling_drafts_resume_without_regenerating_the_pair(tmp_path, hooks):
    api = FakeAPI()
    hooks.fail_id = "2"
    with pytest.raises(PipelineError, match="bounded repair"):
        plan_all(api, *inputs(), tmp_path)
    assert len(api.calls) == 1
    assert set(hooks.accepted) == {"1"}
    assert len(list((tmp_path / "batch-drafts").glob("*.json"))) == 2
    hooks.fail_id = None
    result = plan_all(api, *inputs(), tmp_path)
    assert list(result) == ["1", "2", "3"]
    assert len(api.calls) == 2
    assert api.calls[1]["payload"]["required_scene_ids"] == ["3"]


def test_shared_reference_images_are_deduplicated_and_scene_labeled(tmp_path, hooks):
    shared = tmp_path / "shared.jpg"
    unique = tmp_path / "unique.jpg"
    hooks.images = {"1": [shared], "2": [shared, unique]}
    api = FakeAPI()
    plan_all(api, *inputs((1, 2)), tmp_path)
    call = api.calls[0]
    assert call["kind"] == "vision"
    assert call["images"] == [shared, unique]
    assert call["payload"]["attached_images"] == [
        {"image_index": 1, "scene_ids": ["1", "2"]},
        {"image_index": 2, "scene_ids": ["2"]},
    ]


def test_missing_recorded_speech_fails_before_any_request(tmp_path, hooks):
    script, speech, assets = inputs()
    speech["scenes"].pop()
    api = FakeAPI()
    with pytest.raises(PipelineError, match="missing recorded speech"):
        plan_all(api, script, speech, assets, tmp_path)
    assert api.calls == []


def test_only_selected_scenes_are_planned(tmp_path, hooks):
    api = FakeAPI()
    result = plan_all(api, *inputs(), tmp_path, selected_scene_ids=[3])
    assert list(result) == ["3"]
    assert api.calls[0]["payload"]["required_scene_ids"] == ["3"]


def test_invalid_accepted_duration_is_rejected(tmp_path, hooks):
    hooks.accepted = {"1": {**program(1), "duration": 27.}}
    api = FakeAPI()
    with pytest.raises(PipelineError, match="Cached scene"):
        plan_all(api, *inputs((1,)), tmp_path)
    assert api.calls == []


def test_invalid_batch_shape_is_checkpointed_then_rejected(tmp_path, hooks):
    api = FakeAPI([{"scene": program(1)}])
    with pytest.raises(PipelineError, match="no scenes array"):
        plan_all(api, *inputs((1,)), tmp_path)
    assert len(list((tmp_path / "batches").glob("*.json"))) == 1


def test_three_scene_configuration_uses_one_complete_request(tmp_path, hooks, monkeypatch):
    monkeypatch.setenv("GEMINI_SCENE_BATCH_SIZE", "3")
    api = FakeAPI()
    result = plan_all(api, *inputs(), tmp_path)
    assert list(result) == ["1", "2", "3"]
    assert len(api.calls) == 1
    assert api.calls[0]["payload"]["required_scene_ids"] == ["1", "2", "3"]
    assert api.calls[0]["max_output"] == 45000
    assert hooks.validations == ["1", "2", "3"]
    assert len(list((tmp_path / "batch-drafts").glob("*.json"))) == 3


def test_single_scene_configuration_respects_the_request_limit(tmp_path, hooks, monkeypatch):
    monkeypatch.setenv("GEMINI_SCENE_BATCH_SIZE", "1")
    api = FakeAPI()
    result = plan_all(api, *inputs(), tmp_path)
    assert list(result) == ["1", "2", "3"]
    assert [c["payload"]["required_scene_ids"] for c in api.calls] == [["1"], ["2"], ["3"]]
    assert [c["max_output"] for c in api.calls] == [18000, 18000, 18000]


@pytest.mark.parametrize("value", ["0", "4", "-1", "not-an-integer", "1.5", ""])
def test_invalid_batch_configuration_fails_before_any_request(tmp_path, hooks, monkeypatch, value):
    monkeypatch.setenv("GEMINI_SCENE_BATCH_SIZE", value)
    api = FakeAPI()
    with pytest.raises(PipelineError, match="GEMINI_SCENE_BATCH_SIZE"):
        plan_all(api, *inputs(), tmp_path)
    assert api.calls == []
    assert hooks.validations == []
