from history_of_x.director_script import choose_audition, script_metrics


def test_natural_complete_voice_beats_fast_incomplete_voice():
    good = {"voice": "Charon", "verification": {"accepted": True}, "words_per_minute": 163, "review": {"naturalness": 8, "clarity": 9, "rhythm": 8, "overacted": False}}
    bad = {"voice": "Puck", "verification": {"accepted": False}, "words_per_minute": 174, "review": {"naturalness": 10, "clarity": 10, "rhythm": 10, "overacted": False}}
    assert choose_audition([bad, good])["voice"] == "Charon"


def test_metrics_detect_long_monotonous_sentences():
    result = script_metrics({"scenes": [{"chapter": "Hook", "narration": "The king signed. Everything changed. Why did he do it?"}]})
    assert result["words"] == 10
    assert result["median_sentence_words"] == 3
    assert result["chapter_words"]["Hook"] == 10
