import json

import pytest

from history_of_x.core import ROOT, PipelineError, key, read_json, save_json
from history_of_x.director_script import (
    ETHIOPIA_STORY, STYLE_PROFILE, attach_story_contract, audio_review, chapter_story_issues,
    chapter_style_issues, choose_audition, compact_chapter_evidence,
    compact_source_extract, recover_draft_chapter, script_metrics,
    strip_source_citations, story_chapter_evidence, story_scene_plan, word_target, write,
    director_fingerprint as story_fingerprint,
)


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
        "chapter": "Hook", "narration": " ".join(["The king sends his soldiers down the narrow mountain road."] * 5 + ["They keep moving."]),
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


def director_outline(fingerprint):
    return {
        "fingerprint": fingerprint, "organizing_question": "Who holds power?",
        "ending_payoff": "A victory abroad does not settle power at home.",
        "chapters": [
            {"chapter": c, "era": "Aksum through Gondar" if c == "Roots" else c,
             "events": ["Ezana adopts Christianity", "Gondar and the regional rulers"] if c == "Roots" else [c]}
            for c in ["Hook", "Roots", "Catalyst", "Turning Point", "Aftermath"]
        ],
    }


def director_fingerprint(title, evidence):
    return key("director-script-v3-measured-voice-rate", title, "Brief", 1400, 160.0, evidence, STYLE_PROFILE)


def test_actual_chapter_request_has_focused_sources_and_small_continuity(tmp_path, monkeypatch):
    # Exercise the legacy compact path independently of the new story contract.
    import history_of_x.director_script as director_module
    monkeypatch.setattr(director_module, "has_ethiopia_story_contract", lambda *args: False)
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]
    fingerprint = director_fingerprint("Ethiopia", evidence)
    outline = director_outline(fingerprint)
    save_json(tmp_path / "outline.json", outline)
    hook = saved_hook()
    for scene in hook["scenes"]:
        scene["source_ids"] = ["S3"]
    save_json(tmp_path / "draft-script.json", hook)

    class CaptureAPI:
        payload = None

        def text(self, instruction, payload, schema, **kwargs):
            self.payload = payload
            raise PipelineError("captured Roots")

    api = CaptureAPI()
    with pytest.raises(PipelineError, match="captured Roots"):
        write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    payload = api.payload
    assert payload["this_chapter"] == outline["chapters"][1]
    assert set(payload["whole_film_outline"]) == {"organizing_question", "ending_payoff"}
    assert payload["previous_chapter_ending"] == hook["scenes"][-1]["narration"]
    assert [s["id"] for s in payload["evidence"]] == ["S1", "S2"]
    assert sum(len(s["extract"]) for s in payload["evidence"]) <= 5500
    assert "Gondar" in payload["evidence"][1]["extract"]
    assert "Ezana" in payload["evidence"][0]["extract"]


@pytest.mark.parametrize("chapter,ids", [
    ("Hook", ["S3", "S4"]), ("Roots", ["S1", "S2"]), ("Catalyst", ["S3", "S4"]),
    ("Turning Point", ["S4", "S5", "S6"]), ("Aftermath", ["S7", "S8", "S9", "S10", "S11"]),
])
def test_actual_evidence_routing_and_endpoint(chapter, ids):
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]
    compact = compact_chapter_evidence(evidence, {"chapter": chapter}, is_ethiopia=True)
    assert [s["id"] for s in compact] == ids
    assert sum(len(s["extract"]) for s in compact) <= 5500
    assert not any("2026" in s["extract"] or "2024" in s["extract"] for s in compact)
    if chapter == "Aftermath":
        assert compact[-1]["extract"] == evidence["sources"][-1]["extract"]


def test_new_outline_uses_all_sources_with_at_most_400_characters_each(tmp_path):
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]

    class CaptureAPI:
        payload = None

        def text(self, instruction, payload, schema, **kwargs):
            self.payload = payload
            raise PipelineError("captured outline")

    api = CaptureAPI()
    with pytest.raises(PipelineError, match="captured outline"):
        write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert len(api.payload["evidence"]) == 11
    assert all(len(s["extract"]) <= 400 for s in api.payload["evidence"])


def test_relevant_paragraph_is_selected_beyond_the_article_opening():
    extract = "An introductory description of the country.\n" + "\n".join(
        ["An unrelated paragraph describes a different period of history."] * 200
    ) + "\nTaytu brings the Ethiopian army to Adwa. The separated Italian columns lose contact."
    compact = compact_source_extract(extract, 700, ("taytu", "adwa", "columns"))
    assert compact.startswith("An introductory description")
    assert "Taytu" in compact and "columns lose contact" in compact
    assert len(compact) <= 700


def test_generic_chapter_selects_a_few_relevant_sources():
    evidence = {"sources": [
        {"id": "S" + str(i), "title": "Other period", "extract": "Unrelated events. " * 500}
        for i in range(8)
    ] + [{"id": "S8", "title": "Caesar in Gaul", "extract": "Caesar campaigns in Gaul. " * 500}]}
    compact = compact_chapter_evidence(evidence, {"chapter": "Roots", "events": ["Caesar campaigns in Gaul"]})
    assert len(compact) == 4
    assert compact[0]["id"] == "S8"
    assert sum(len(s["extract"]) for s in compact) <= 5500


def test_inline_citations_are_removed_without_changing_other_brackets_or_metadata():
    assert strip_source_citations("The king signs [S1, S2]. He leaves[S1][S2]. [pause]", ["S1", "S2"]) == "The king signs. He leaves. [pause]"
    draft = saved_hook()
    for scene in draft["scenes"]:
        scene["narration"] += " [S1]"
    recovered = recover_draft_chapter(draft, "Ethiopia", "Hook", 119, 2, ["S1"])
    assert sum(len(s["narration"].split()) for s in recovered["scenes"]) == 106
    assert all(s["source_ids"] == ["S1"] and "[S1]" not in s["narration"] for s in recovered["scenes"])


def fake_chapter(budget, count, source="S1", long_sentences=False, citations=False):
    scenes = []
    base = "The king sends his soldiers down the narrow mountain road".split()
    for index in range(count):
        words = budget // count + (index < budget % count)
        tokens = (base * (words // 10 + 1))[:words]
        if long_sentences:
            narration = " ".join(tokens) + "."
        else:
            narration = " ".join(" ".join(tokens[start:start + 10]) + "." for start in range(0, words, 10))
        if citations:
            narration += " [" + source + "]"
        scenes.append({"narration": narration, "source_ids": [source], "date_label": "1896",
                       "location": "Ethiopia", "asset_search_term": "Ethiopian mountain road"})
    return {"scenes": scenes}


def test_natural_drafts_need_no_revision_and_citations_do_not_reach_tts(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = {"sources": [{"id": "S1", "extract": "Historical evidence"}]}
    fingerprint = director_fingerprint("Ethiopia", evidence)
    save_json(tmp_path / "outline.json", director_outline(fingerprint))

    class NaturalAPI:
        calls = []

        def text(self, instruction, payload, schema, **kwargs):
            self.calls.append(payload)
            assert "draft" not in payload
            assert "5–7 natural complete sentences" in instruction
            count = schema["properties"]["scenes"]["minItems"]
            return fake_chapter(payload["target_chapter_words"], count, citations=True)

    api = NaturalAPI()
    result = write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert len(api.calls) == 5
    assert result["word_count"] == 1400
    assert all("[S1]" not in s["narration"] for s in result["scenes"])
    accepted = (tmp_path / "script.json").read_text()
    assert write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path) == result
    assert len(api.calls) == 5
    assert (tmp_path / "script.json").read_text() == accepted


def test_cached_long_sentences_get_only_one_joint_revision_across_restarts(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = {"sources": [{"id": s, "extract": "Historical evidence"} for s in ("S1", "S2")]}
    fingerprint = director_fingerprint("Ethiopia", evidence)
    save_json(tmp_path / "outline.json", director_outline(fingerprint))
    chapter_path = tmp_path / "director-chapters" / ("1-" + fingerprint + ".json")
    save_json(chapter_path, fake_chapter(106, 2, long_sentences=True))

    class RepairAPI:
        calls = []

        def text(self, instruction, payload, schema, **kwargs):
            self.calls.append((payload["this_chapter"]["chapter"], "draft" in payload))
            if "draft" in payload:
                assert "length and conversational cadence together" in instruction
                assert "Preserve its facts" in instruction
                # A stubborn model must not cause an endless rewrite loop.
                return fake_chapter(119, 2, source="S2", long_sentences=True)
            raise PipelineError("Roots unavailable")

    api = RepairAPI()
    for _ in range(2):
        with pytest.raises(PipelineError, match="Roots unavailable"):
            write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert api.calls == [("Hook", True), ("Roots", False), ("Roots", False)]
    repaired = read_json(chapter_path)
    assert repaired["cadence_length_revision"] == 1
    assert sum(len(s["narration"].split()) for s in repaired["scenes"]) == 119
    assert all(s["source_ids"] == ["S1"] for s in repaired["scenes"])


def test_story_contract_cannot_reuse_the_old_full_script_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]
    old = director_fingerprint("Ethiopia", evidence)
    new = story_fingerprint("Ethiopia", "Brief", 1400, 160.0, evidence)
    assert old != new
    save_json(tmp_path / "script.json", {"fingerprint": old, "scenes": []})

    class API:
        def text(self, instruction, payload, schema, **kwargs):
            assert "this_chapter" not in payload
            raise PipelineError("new outline requested")

    with pytest.raises(PipelineError, match="new outline requested"):
        write(API(), "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert read_json(tmp_path / "script.json")["fingerprint"] == old


def test_story_plan_assigns_every_beat_even_when_scene_count_changes():
    for chapter, beats in ETHIOPIA_STORY.items():
        for count in (2, 5, 7):
            plan = story_scene_plan(chapter, count)
            spoken = [b for scene in plan for b in scene["must_explain"]]
            assert len(plan) == count
            assert all(beat["say"] in spoken for beat in beats)


@pytest.mark.parametrize("chapter,terms", [
    ("Roots", ["Ezana", "Portuguese", "Gondar"]),
    ("Catalyst", ["Taytu", "Wuchale", "Adwa"]),
    ("Turning Point", ["1941", "1974", "Red Terror"]),
    ("Aftermath", ["1993", "Abiy", "2022"]),
])
def test_story_evidence_reserves_passages_for_omitted_milestones(chapter, terms):
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]
    compact = story_chapter_evidence(evidence, chapter)
    assert sum(len(s["extract"]) for s in compact) <= 5500
    text = " ".join(s["extract"] for s in compact).casefold()
    assert all(term.casefold() in text for term in terms)
    assert "2025" not in text and "2026" not in text


def story_scene(text, source_ids, date="1896"):
    return {"narration": text, "source_ids": source_ids, "date_label": date}


def test_actual_missing_eras_and_unpaid_adwa_setup_are_rejected():
    roots = {"scenes": [story_scene(
        "In 1270 Yekuno Amlak overthrew the Zagwe dynasty. He claimed descent from Solomon. "
        "The new dynasty forged an identity that would outlast shifting alliances.", ["S2"], "1270")]}
    issues = chapter_story_issues(roots, "Roots")
    assert any("Adal" in issue for issue in issues)
    assert any("Gondar" in issue for issue in issues)
    catalyst = {"scenes": [story_scene(
        "Menelik took the throne in 1889. His modern weaponry set the stage for the inevitable clash at Adwa.",
        ["S3"], "1889")]}
    issues = chapter_story_issues(catalyst, "Catalyst")
    assert any("Taytu" in issue for issue in issues)
    assert any("Wuchale" in issue for issue in issues)
    assert any("Pay off Adwa" in issue for issue in issues)


def test_concrete_spoken_payoff_passes_but_metadata_mentions_do_not():
    text = (
        "Tewodros tried to reunite the regional rulers. Yohannes defended the borders. "
        "Menelik expanded through conquest and bought modern rifles. "
        "Taytu helped organize resistance to Italy. "
        "The Wuchale treaty had different Amharic and Italian versions. Italy claimed a protectorate, but Menelik rejected it. "
        "At Adwa, Ethiopian forces defeated Italy. The peace treaty recognized Ethiopian independence."
    )
    part = {"scenes": [story_scene(text, ["S3", "S4"])]}
    assert chapter_story_issues(part, "Catalyst") == []
    part["scenes"][0]["narration"] = "Menelik prepared for a confrontation."
    part["scenes"][0]["date_label"] = "1896 Adwa victory; Taytu; Wuchale"
    assert any("Pay off Adwa" in issue for issue in chapter_story_issues(part, "Catalyst"))


def test_wrong_occupation_and_pretoria_metadata_are_rejected():
    turning = {"scenes": [story_scene(
        "Badoglio's victorious troops march into Addis Ababa. Mussolini announces annexation. Resistance continues.",
        ["S5"], "1941")]}
    assert any("mislabeled 1941" in issue for issue in chapter_story_issues(turning, "Turning Point"))
    aftermath = {"scenes": [story_scene(
        "The parties meet in South Africa. The Pretoria cessation of hostilities follows in November twenty twenty two.",
        ["S11"], "October 2025")]}
    issues = chapter_story_issues(aftermath, "Aftermath")
    assert any("stop at November 2022" in issue for issue in issues)
    assert any("Pretoria agreement date_label" in issue for issue in issues)
    turning["scenes"][0] = story_scene(
        "In nineteen forty one, Haile Selassie returns. The monarchy is restored.",
        ["S5"], "1936")
    assert any("conflicts with the year spoken" in issue for issue in chapter_story_issues(turning, "Turning Point"))


def test_median_alone_cannot_approve_formal_padded_narration():
    sentence = "The ruling coalition maintained a powerful grip on all important state affairs."
    part = {"scenes": [story_scene(" ".join([sentence] * 10), ["S10"], "2019")]}
    assert script_metrics({"scenes": [{**part["scenes"][0], "chapter": "Aftermath"}]})["median_sentence_words"] == 12
    assert any("short complete sentences" in issue for issue in chapter_style_issues(part))


def test_failed_story_repair_is_bounded_and_cannot_publish_a_complete_script(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRIPT_TARGET_WPM", "160")
    evidence = read_json(ROOT / "episodes" / "ethiopia.json")["evidence"]
    fingerprint = story_fingerprint("Ethiopia", "Brief", 1400, 160.0, evidence)
    save_json(tmp_path / "outline.json", attach_story_contract(director_outline(fingerprint)))

    class API:
        calls = []

        def text(self, instruction, payload, schema, **kwargs):
            self.calls.append(payload)
            assert payload["scene_plan"]
            assert payload["this_chapter"]["required_spoken_beats"]
            if "draft" in payload:
                assert "missing spoken cause/consequence beat" in instruction
                assert "correct date labels" in instruction
            return fake_chapter(payload["target_chapter_words"], 2, source="S4")

    api = API()
    for _ in range(2):
        with pytest.raises(PipelineError, match="missed required spoken coverage"):
            write(api, "Ethiopia", "Brief", 8.75, evidence, tmp_path)
    assert len(api.calls) == 2
    assert not (tmp_path / "script.json").exists()
    checkpoint = read_json(tmp_path / "director-chapters" / ("1-" + fingerprint + ".json"))
    assert checkpoint["cadence_length_revision"] == 1
