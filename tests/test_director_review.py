"""Review transport and acceptance contracts; these tests do not certify artistic quality."""
import copy
import json
from pathlib import Path

import pytest

from history_of_x import director_review as subject
from history_of_x.core import PipelineError, read_json, save_json


def ready():
    return {
        "verdict": "ready",
        "scores": {name: 8 for name in subject.CATEGORIES},
        "observations": ["Readable acting and clear spoken delivery observed."],
        "problems": [],
        "revision_priorities": [],
    }


class FakeAPI:
    def __init__(self, reports=None, fail_after=None):
        self.reports = reports or [ready()]
        self.fail_after = fail_after
        self.calls = []

    def request(self, model, endpoint, body, kind):
        self.calls.append((model, endpoint, copy.deepcopy(body), kind))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise PipelineError("Interrupted review quota")
        report = self.reports[min(len(self.calls) - 1, len(self.reports) - 1)]
        return {"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [
                {"thought": True, "text": "not JSON"},
                {"text": json.dumps(report)},
            ]},
        }]}


@pytest.fixture
def film(tmp_path, monkeypatch):
    video = tmp_path / "film.mp4"
    video.write_bytes(b"original audiovisual film")
    output = tmp_path / "output"
    durations, transcodes = {}, []

    def fake_ffmpeg(*args, **kwargs):
        clip = Path(args[-1])
        start = float(args[args.index("-ss") + 1])
        seconds = float(args[args.index("-t") + 1])
        transcodes.append({"start": start, "seconds": seconds, "args": args})
        # Fake media only; production ffmpeg is responsible for real H264 and AAC.
        clip.write_bytes(b"fake mp4 with video and audio " + video.read_bytes() + str(start).encode())
        durations[clip] = seconds

    def fake_duration(path):
        return 68.25 if Path(path) == video else durations[Path(path)]

    monkeypatch.setattr(subject, "ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(subject, "duration", fake_duration)
    monkeypatch.delenv("GEMINI_REVIEW_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    return video, output, transcodes


def test_entire_film_including_tail_uses_actual_inline_audio_video(film):
    video, output, transcodes = film
    api = FakeAPI()
    report = subject.review(api, video, {}, output)

    assert [(part["start"], part["seconds"]) for part in transcodes] == [
        (0, 30), (30, 30), (60, 8.25),
    ]
    assert report["verdict"] == "ready"
    scope = report["scope"]
    assert scope["coverage"] == "entire_film_chunks"
    assert scope["duration_seconds"] == scope["reviewed_seconds"] == 68.25
    assert scope["chunk_count"] == 3 and scope["audio_included"]
    assert [(part["start_seconds"], part["end_seconds"]) for part in scope["ranges"]] == [
        (0, 30), (30, 60), (60, 68.25),
    ]
    assert scope["models"] == ["gemini-3.5-flash-lite"]
    for call, transcode in zip(api.calls, transcodes):
        model, endpoint, body, kind = call
        assert model == "gemini-3.5-flash-lite"
        assert endpoint == "models/" + model + ":generateContent" and kind == "text"
        part = body["contents"][0]["parts"][1]
        assert part["inlineData"]["mimeType"] == "video/mp4"
        assert part["inlineData"]["data"]
        assert "fileData" not in part and part["videoMetadata"] == {"fps": 1}
        assert 1500 <= body["generationConfig"]["maxOutputTokens"] <= 2000
        args = transcode["args"]
        assert args[args.index("-c:v") + 1] == "libx264"
        assert args[args.index("-c:a") + 1] == "aac"
        assert args[args.index("-b:a") + 1] == "64k"
        assert "0:a:0" in args and "-an" not in args
    assert all(
        observation.startswith(f"[{start:.3f}–{end:.3f}s] ")
        for observation, (start, end) in zip(report["observations"], [(0, 30), (30, 60), (60, 68.25)])
    )
    assert read_json(output / "editorial-review.json") == report
    checkpoints = list((output / "editorial-review-parts").glob("*.json"))
    assert len(checkpoints) == 3
    for path in checkpoints:
        saved = read_json(path)
        assert saved["identity"]["video_sha256"] == scope["video_sha256"]
        assert all(len(saved[name]) == 64 for name in ("clip_sha256", "request_sha256", "report_sha256"))


def test_all_chunks_resume_without_api_or_transcode(film):
    video, output, transcodes = film
    first = subject.review(FakeAPI(), video, {}, output)
    api = FakeAPI()
    second = subject.review(api, video, {}, output)
    assert second == first
    assert api.calls == [] and len(transcodes) == 3


def test_interruption_resumes_accepted_chunks_and_removes_old_final_report(film):
    video, output, transcodes = film
    save_json(output / "editorial-review.json", {"verdict": "ready", "stale": True})
    with pytest.raises(PipelineError, match="Interrupted"):
        subject.review(FakeAPI(fail_after=1), video, {}, output)
    assert not (output / "editorial-review.json").exists()
    assert len(list((output / "editorial-review-parts").glob("*.json"))) == 1
    api = FakeAPI()
    result = subject.review(api, video, {}, output)
    assert len(api.calls) == 2 and result["scope"]["reviewed_seconds"] == 68.25
    assert [part["start"] for part in transcodes] == [0, 30, 30, 60]


@pytest.mark.parametrize("bad_verdict,bad_score,expected", [
    ("ready", 5, "revise"), ("revise", 8, "revise"), ("reject", 8, "reject"),
])
def test_one_bad_chunk_prevents_ready_and_keeps_absolute_ranges(film, bad_verdict, bad_score, expected):
    video, output, _ = film
    bad = ready()
    bad["verdict"] = bad_verdict
    bad["scores"]["acting"] = bad_score
    bad["problems"] = ["The prop transfer is incoherent at 00:42."]
    bad["revision_priorities"] = ["Stage the transfer with visible hand contact."]
    result = subject.review(FakeAPI([ready(), bad, ready()]), video, {}, output)
    assert result["verdict"] == expected
    assert result["scores"]["acting"] == bad_score
    assert result["problems"] == ["[30.000–60.000s] The prop transfer is incoherent at 00:42."]
    assert result["revision_priorities"][0].startswith("[30.000–60.000s]")


@pytest.mark.parametrize("bad_score", [True, 7.5, "8", 0, 11, None])
def test_malformed_scores_fail_closed_and_are_not_accepted_checkpoints(film, bad_score):
    video, output, _ = film
    bad = ready()
    bad["scores"]["acting"] = bad_score
    with pytest.raises(PipelineError, match="score"):
        subject.review(FakeAPI([bad]), video, {}, output)
    assert not (output / "editorial-review.json").exists()
    assert list((output / "editorial-review-parts").glob("*.json")) == []


def test_changed_source_or_review_model_does_not_reuse_checkpoints(film, monkeypatch):
    video, output, _ = film
    subject.review(FakeAPI(), video, {}, output)
    video.write_bytes(b"different audiovisual film")
    changed_source = FakeAPI()
    subject.review(changed_source, video, {}, output)
    assert len(changed_source.calls) == 3
    monkeypatch.setenv("GEMINI_REVIEW_MODEL", "gemini-3.1-flash-lite")
    changed_model = FakeAPI()
    result = subject.review(changed_model, video, {}, output)
    assert len(changed_model.calls) == 3
    assert result["scope"]["models"] == ["gemini-3.1-flash-lite"]


def test_only_relevant_bounded_style_and_narration_context_are_sent(film):
    video, output, _ = film
    save_json(output / "timeline.json", [
        {"global_start": 0, "global_end": 30, "narration_context": "First spoken scene."},
        {"global_start": 30, "global_end": 68.25, "narration_context": "Second spoken scene."},
    ])
    api = FakeAPI()
    subject.review(api, video, {"video_reference_study": {
        "writing_guide": "irrelevant large guide " * 1000,
        "composition": "Use a clear focal point.",
    }}, output)
    contexts = [
        json.loads(call[2]["contents"][0]["parts"][0]["text"].split("SEGMENT CONTEXT:\n")[1])
        for call in api.calls
    ]
    assert contexts[0]["narration_context"] == ["First spoken scene."]
    assert contexts[1]["narration_context"] == ["Second spoken scene."]
    assert contexts[2]["narration_context"] == ["Second spoken scene."]
    assert all(context["visual_rules"] == ["composition: Use a clear focal point."] for context in contexts)
    assert "irrelevant large guide" not in api.calls[0][2]["contents"][0]["parts"][0]["text"]


@pytest.mark.parametrize("response", [
    {"candidates": [None]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [None]}}]},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]},
])
def test_incomplete_or_malformed_response_fails_closed(response):
    with pytest.raises(PipelineError):
        subject._parse_response(response)


def test_short_final_tail_is_merged_without_losing_coverage(film, monkeypatch):
    video, output, transcodes = film
    original_duration = subject.duration
    monkeypatch.setattr(
        subject, "duration",
        lambda path: 66.0 if Path(path) == video else original_duration(path),
    )
    api = FakeAPI()
    report = subject.review(api, video, {}, output)
    assert [(part["start"], part["seconds"]) for part in transcodes] == [(0, 30), (30, 36)]
    assert len(api.calls) == 2
    assert report["scope"]["duration_seconds"] == report["scope"]["reviewed_seconds"] == 66
    assert [(part["start_seconds"], part["end_seconds"]) for part in report["scope"]["ranges"]] == [
        (0, 30), (30, 66),
    ]


def test_larger_model_review_ranges_cover_every_second_without_gaps():
    from history_of_x.director_review import _ranges
    spans=_ranges(508.64,90)
    assert len(spans)==6
    assert spans[0][0]==0 and spans[-1][1]==508.64
    assert all(a[1]==b[0] for a,b in zip(spans,spans[1:]))
    assert sum(b-a for a,b in spans)==pytest.approx(508.64)
    assert _ranges(184.,90)==[(0.,90.),(90.,184.)]


def test_available_free_reviewer_recovers_same_clip_and_reuses_its_real_report(film,monkeypatch):
    video,output,transcodes=film
    monkeypatch.setenv("GEMINI_REVIEW_MODEL","gemini-3.6-flash")
    class AvailabilityAPI(FakeAPI):
        def request(self,model,endpoint,body,kind):
            if model=="gemini-3.6-flash":
                self.calls.append((model,endpoint,copy.deepcopy(body),kind))
                raise PipelineError("Gemini gemini-3.6-flash unavailable after three attempts")
            return super().request(model,endpoint,body,kind)
    api=AvailabilityAPI()
    report=subject.review(api,video,{},output)
    assert [call[0] for call in api.calls]==["gemini-3.6-flash","gemini-3.5-flash-lite"]
    assert report["scope"]["models"]==["gemini-3.5-flash-lite"]
    assert report["scope"]["reviewed_seconds"]==68.25
    assert report["scope"]["chunk_count"]==1
    again=AvailabilityAPI()
    assert subject.review(again,video,{},output)==report
    assert again.calls==[] and len(transcodes)==2


def test_a_low_creative_score_never_triggers_reviewer_fallback(film,monkeypatch):
    video,output,_=film
    monkeypatch.setenv("GEMINI_REVIEW_MODEL","gemini-3.6-flash")
    bad=ready();bad["scores"]["acting"]=4;bad["verdict"]="revise"
    bad["problems"]=["The object visibly misses the hand at 00:12."]
    api=FakeAPI([bad])
    report=subject.review(api,video,{},output)
    assert len(api.calls)==1 and report["verdict"]=="revise"
    assert report["scores"]["acting"]==4
    assert report["scope"]["models"]==["gemini-3.6-flash"]
