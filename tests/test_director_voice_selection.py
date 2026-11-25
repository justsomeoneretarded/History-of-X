"""Explicit narrator selection must not spend quota auditioning other voices."""
import pytest

from history_of_x.core import save_json
import history_of_x.director_script as director
import history_of_x.gemini_speech as gemini_speech


@pytest.mark.parametrize("requested, expected_auditions", [("auto", 1), ("Charon", 0)])
def test_all_stage_only_auditions_for_auto(tmp_path, monkeypatch, requested, expected_auditions):
    calls = {"auditions": 0, "voices": []}

    def write(api, title, brief, minutes, evidence, directory):
        save_json(directory / "script.json", {"word_count": 5, "scenes": [
            {"scene_id": 1, "narration": "A ruler makes a choice."}
        ]})

    def audition(api, script, directory):
        calls["auditions"] += 1
        save_json(directory / "audition.json", {"selected_voice": "Charon"})

    def produce(api, script, voice, directory):
        calls["voices"].append(voice)
        return {"scenes": [{"duration": 30.0}]}

    monkeypatch.setattr(director, "MediaAPI", lambda directory: object())
    monkeypatch.setattr(director, "write", write)
    monkeypatch.setattr(director, "audition", audition)
    monkeypatch.setattr(gemini_speech, "produce", produce)
    result = director.main(["--stage", "all", "--title", "Ethiopia", "--minutes", "0.5",
                            "--voice", requested, "--work", str(tmp_path)])
    assert result == 0
    assert calls == {"auditions": expected_auditions, "voices": ["Charon"]}
