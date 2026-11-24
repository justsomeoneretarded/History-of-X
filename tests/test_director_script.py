import pytest

from history_of_x.core import PipelineError
from history_of_x.director_script import choose_audition, script_metrics, word_target


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
