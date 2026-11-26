"""Production orchestration must preserve candidates and fail closed on delivery."""
import pytest
from PIL import Image

from history_of_x.core import PipelineError, read_json, save_json
from history_of_x.director_review import CATEGORIES
import history_of_x.director_runner as runner


def reports(output, proof, ready=True):
    save_json(output / "production.json", {
        "proof": proof, "technical_passed": True, "editorial_accepted": ready,
        "runtime_seconds": 525.0})
    save_json(output / "quality.json", {
        "passed": True, "video": {"width": 1920, "height": 1080}})
    save_json(output / "editorial-review.json", {
        "verdict": "ready" if ready else "revise",
        "scores": {name: 8 if ready else 4 for name in CATEGORIES},
        "problems": [] if ready else ["The diagram does not explain the spoken reversal."],
        "scope": {"coverage": "entire_film_chunks", "audio_included": True,
                  "duration_seconds": 525.0, "reviewed_seconds": 525.0}})


def test_only_this_attempts_creative_failure_receives_one_revision(tmp_path, monkeypatch):
    calls = []
    def produce(api, work, output, **kwargs):
        calls.append((output, kwargs))
        reports(output, True, ready=len(calls) == 2)
        if len(calls) == 1:
            raise PipelineError("Creative review requires revision")
    monkeypatch.setattr(runner, "produce", produce)
    chosen = runner.render_phase(object(), tmp_path / "work", tmp_path / "output", True, "cinematic")
    assert chosen == calls[1][0]
    assert calls[0][0] != calls[1][0]
    assert (calls[0][0] / "failure.json").exists()
    assert [kwargs["revise"] for _, kwargs in calls] == [False, True]
    assert read_json(tmp_path / "work" / "editorial-feedback.json")["verdict"] == "revise"


def test_provider_failure_cannot_retry_from_stale_editorial_feedback(tmp_path, monkeypatch):
    save_json(tmp_path / "work" / "editorial-feedback.json", {"verdict": "revise"})
    calls = []
    def produce(api, work, output, **kwargs):
        calls.append(output)
        raise PipelineError("Provider unavailable")
    monkeypatch.setattr(runner, "produce", produce)
    with pytest.raises(PipelineError, match="Provider unavailable"):
        runner.render_phase(object(), tmp_path / "work", tmp_path / "output", False, "cinematic")
    assert len(calls) == 1
    assert not (tmp_path / "output" / "upload-ready").exists()


def test_creative_revision_is_bounded_and_retains_both_candidates(tmp_path, monkeypatch):
    calls = []
    def produce(api, work, output, **kwargs):
        calls.append(output)
        reports(output, False, ready=False)
        raise PipelineError("Creative review requires revision")
    monkeypatch.setattr(runner, "produce", produce)
    with pytest.raises(PipelineError):
        runner.render_phase(object(), tmp_path / "work", tmp_path / "output", False, "cinematic")
    assert len(calls) == 2
    assert all((path / "failure.json").exists() for path in calls)
    assert not (tmp_path / "output" / "upload-ready").exists()


def package_files(candidate, work):
    for name in runner.UPLOAD_FILES:
        (candidate / name).write_text("Deliverable")
    (candidate / "title.txt").write_text("The Entire History of Ethiopia")
    Image.new("RGB", (1280, 720), "#a87840").save(candidate / "thumbnail.jpg")
    save_json(work / "narration-metrics.json", {
        "runtime_within_10_percent_of_target": True, "voice": "Charon",
        "narration_seconds": 525.0})


def test_accepted_preflight_cannot_be_packaged_as_a_complete_film(tmp_path):
    candidate = tmp_path / "candidate"
    reports(candidate, True)
    with pytest.raises(PipelineError, match="complete"):
        runner.upload_package(candidate, tmp_path / "work", tmp_path / "output")


def test_upload_package_is_distinct_from_immutable_review_candidates(tmp_path):
    candidate, work, output = tmp_path / "candidate", tmp_path / "work", tmp_path / "output"
    reports(candidate, False)
    package_files(candidate, work)
    (candidate / "review.mp4").write_bytes(b"review copy")
    destination = runner.upload_package(candidate, work, output)
    assert set(runner.UPLOAD_FILES) <= {p.name for p in destination.iterdir()}
    assert not (destination / "review.mp4").exists()
    assert (candidate / "review.mp4").exists()
    assert read_json(destination / "delivery.json")["upload_ready"] is True
    with pytest.raises(PipelineError, match="already exists"):
        runner.upload_package(candidate, work, output)


def test_partial_audiovisual_review_and_oversized_metadata_cannot_release(tmp_path):
    candidate, work, output = tmp_path / "candidate", tmp_path / "work", tmp_path / "output"
    reports(candidate, False)
    package_files(candidate, work)
    report = read_json(candidate / "editorial-review.json")
    report["scope"]["reviewed_seconds"] = 30
    save_json(candidate / "editorial-review.json", report)
    with pytest.raises(PipelineError, match="complete"):
        runner.upload_package(candidate, work, output)
    reports(candidate, False)
    (candidate / "title.txt").write_text("x" * 101)
    with pytest.raises(PipelineError, match="metadata"):
        runner.upload_package(candidate, work, output)
    assert not (output / "upload-ready").exists()


def test_one_command_routes_models_and_preserves_selected_voice(tmp_path, monkeypatch):
    calls = []
    def writing(args):
        calls.append(("writing", list(args), runner.os.environ["GEMINI_MODEL"]))
        return 0
    def phase(api, work, output, proof, profile, **options):
        calls.append(("proof" if proof else "film", profile, runner.os.environ["GEMINI_MODEL"]))
        return output / ("proof" if proof else "film")
    monkeypatch.setattr(runner.director_script, "main", writing)
    monkeypatch.setattr(runner, "MediaAPI", lambda directory: object())
    monkeypatch.setattr(runner, "render_phase", phase)
    monkeypatch.setattr(runner, "upload_package", lambda candidate, work, output: output / "upload-ready")
    monkeypatch.setenv("GEMINI_WRITER_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_DIRECTOR_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_MODEL", "previous-value")
    runner.run("Ethiopia", "An original history across centuries.", "Charon",
               work=tmp_path / "work", output=tmp_path / "output")
    assert [call[0] for call in calls] == ["writing", "proof", "film"]
    assert calls[0][2] == "gemini-3.5-flash-lite"
    assert calls[0][1][calls[0][1].index("--voice") + 1] == "Charon"
    assert calls[1][2] == calls[2][2] == "gemini-3.8-flash"
    assert runner.os.environ["GEMINI_MODEL"] == "previous-value"

def test_rejected_preflight_can_inform_a_full_candidate_without_becoming_accepted(tmp_path,monkeypatch):
 calls=[]
 def produce(api,work,output,**options):
  calls.append(output)
  reports(output,True,ready=False)
  raise PipelineError("Creative review requires revision")
 monkeypatch.setattr(runner,"produce",produce)
 candidate=runner.render_phase(object(),tmp_path/"work",tmp_path/"output",True,"cinematic",preflight_advisory=True)
 assert len(calls)==1 and candidate==calls[-1]
 assert runner._accepted(candidate,True) is False
 with pytest.raises(PipelineError,match="complete"):
  runner.upload_package(candidate,tmp_path/"work",tmp_path/"output")
 assert not (tmp_path/"output"/"upload-ready").exists()


def test_advisory_samples_cannot_bypass_a_provider_or_full_film_failure(tmp_path,monkeypatch):
 def unavailable(api,work,output,**options):
  raise PipelineError("Provider unavailable")
 monkeypatch.setattr(runner,"produce",unavailable)
 with pytest.raises(PipelineError,match="Provider unavailable"):
  runner.render_phase(object(),tmp_path/"work",tmp_path/"output",True,"cinematic",preflight_advisory=True)
 def rejected(api,work,output,**options):
  reports(output,False,ready=False)
  raise PipelineError("Creative review requires revision")
 monkeypatch.setattr(runner,"produce",rejected)
 with pytest.raises(PipelineError,match="Creative review"):
  runner.render_phase(object(),tmp_path/"work",tmp_path/"output",False,"cinematic",preflight_advisory=True)
