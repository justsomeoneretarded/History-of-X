import json

import pytest

from history_of_x.core import PipelineError, key, read_json, save_json
from history_of_x.director_script import STYLE_PROFILE, audio_review, choose_audition, recover_draft_chapter, script_metrics, word_target, write


def test_natural_complete_voice_beats_fast_incomplete_voice():
    good = {"voice": "Charon", "verification": {"accepted": True}, "words_per_minute": 163, "review": {"naturalness": 8, "clarity": 9, "rhythm": 8, "overacted": False}}
    bad = {"voice": "Puck", "verification": {"accepted": False}, "words_per_minute": 174, "review": {"naturalness": 10, "clarity": 10, "rhythm": 10, "overacted": False}}
    assert choose_audition([bad, good])["voice"] == "Charon"


def test_metrics_detect_long_monotonous_sentences():
    result = script_metrics({"scenes": [{"chapter": "Hook", "narration": "The king signed. Everything changed. Why did he do it?"}]})
    assert result["words"] == 10
    assert result["median_sentence_words"] == 3
    assert result["chapter_words"]["Hook"] == 10


def test_default_script_budget_uses_measured_natural_voice_pace(monkeypatch):
    monkeypatch.delenv("SCRIPT_TARGET_WPM", raising=False)
    assert word_target(8.75) == 1400


@pytest.mark.parametrize("rate", ["100", "160", "174", "210"])
def test_explicit_narrator_rate_changes_script_budget(monkeypatch, rate):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", rate)
    assert word_target(8.75) == round(8.75 * float(rate))


@pytest.mark.parametrize("rate", ["99", "211", "bad", "nan", "inf", ""])
def test_invalid_narrator_rates_are_rejected(monkeypatch, rate):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", rate)
    with pytest.raises(PipelineError, match="SCRIPT_TARGET_WPM"):
        word_target(8.75)


def saved_hook():
    scene = {
        "chapter": "Hook", "narration": " ".join(["history"] * 53),
        "source_ids": ["S1"], "date_label": "1896", "location": "Ethiopia",
        "asset_search_term": "Adwa 1896 commanders",
    }
    return {"title": "Ethiopia", "summary": "Who holds power?", "scenes": [dict(scene), dict(scene)]}


def test_legacy_checkpoint_recovers_complete_106_word_hook_before_retrying_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = {"sources": [{"id": "S1", "extract": "Historical evidence"}]}
    fingerprint = key("director-script-v3-measured-voice-rate", "Ethiopia", "Brief", 1400, 160.0, evidence, STYLE_PROFILE)
    save_json(tmp_path / "outline.json", {
        "fingerprint": fingerprint, "organizing_question": "Who holds power?",
        "chapters": [{"chapter": c} for c in ["Hook", "Roots", "Catalyst", "Turning Point", "Aftermath"]],
    })
    save_json(tmp_path / "draft-script.json", saved_hook())

    class UnavailableAPI:
        calls = []

        def text(self, instruction, payload, schema, **kwargs):
            self.calls.append(payload["this_chapter"]["chapter"])
            raise PipelineError("temporary service outage")

    api = UnavailableAPI()
    with pytest.raises(PipelineError, match="temporary service outage"):
        write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert api.calls == ["Roots"]
    recovered = read_json(tmp_path / "director-chapters" / ("1-" + fingerprint + ".json"))
    assert sum(len(s["narration"].split()) for s in recovered["scenes"]) == 106
    assert read_json(tmp_path / "draft-script.json")["fingerprint"] == fingerprint


@pytest.mark.parametrize("defect", ["missing_scene", "wrong_source", "wrong_title", "short_fragment", "banned_phrase"])
def test_incomplete_or_mismatched_draft_cannot_seed_a_chapter(defect):
    draft = saved_hook()
    if defect == "missing_scene":
        draft["scenes"].pop()
    elif defect == "wrong_source":
        draft["scenes"][0]["source_ids"] = ["UNKNOWN"]
    elif defect == "wrong_title":
        draft["title"] = "Another topic"
    elif defect == "short_fragment":
        for scene in draft["scenes"]:
            scene["narration"] = "One short fragment."
    else:
        draft["scenes"][0]["narration"] += " delve"
    assert recover_draft_chapter(draft, "Ethiopia", "Hook", 119, 2, ["S1"]) is None


def test_audio_review_can_use_separate_model_from_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_AUDIO_REVIEW_MODEL", "gemini-3.1-flash-lite")
    audio = tmp_path / "audition.wav"
    audio.write_bytes(b"original audition bytes")
    review = {"naturalness": 8, "clarity": 9, "rhythm": 8, "overacted": False, "observations": [], "issues": []}

    class API:
        selected_model = None

        def request(self, model, endpoint, body, kind):
            self.selected_model = model
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(review)}]}}]}

    api = API()
    assert audio_review(api, audio, {}) == review
    assert api.selected_model == "gemini-3.1-flash-lite"


@pytest.mark.parametrize("title,is_ethiopia", [("The Entire History of Rome", False), ("The Entire History of Ethiopia", True)])
def test_geographic_outline_direction_is_restricted_to_its_topic(tmp_path, title, is_ethiopia):
    class CaptureAPI:
        instruction = ""

        def text(self, instruction, payload, schema, **kwargs):
            self.instruction = instruction
            raise PipelineError("captured outline")

    api = CaptureAPI()
    evidence = {"sources": [{"id": "S1", "extract": "Historical evidence"}]}
    with pytest.raises(PipelineError, match="captured outline"):
        write(api, title, "Brief", 8.75, evidence, tmp_path)
    assert "cold-open SCENE" in api.instruction
    assert ("Aksum" in api.instruction) is is_ethiopia
    assert ("Adwa" in api.instruction) is is_ethiopia


def test_research_network_outage_becomes_structured_stage_failure(tmp_path, monkeypatch):
    from requests import ConnectionError
    import history_of_x.director_script as director_module
    import history_of_x.research as research_module

    def unavailable(*args, **kwargs):
        raise ConnectionError("source temporarily unreachable")

    monkeypatch.setattr(director_module, "MediaAPI", lambda directory: object())
    monkeypatch.setattr(research_module, "research", unavailable)
    code = director_module.main(["--stage", "plan", "--title", "Rome", "--brief", "Brief", "--work", str(tmp_path)])
    assert code == 1
    failure = read_json(tmp_path / "failure.json")
    assert failure["stage"] == "plan"
    assert "Research source request failed (ConnectionError)" in failure["error"]
