"""One command: original writing, Gemini narration, creative preflight and full delivery."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path

from PIL import Image

from .core import ROOT, PipelineError, read_json, save_json
from .gemini import QuotaDeferred
from .media_api import MediaAPI, VOICES
from . import director_script
from .director_film import produce
from .director_review import CATEGORIES

UPLOAD_FILES = ("final.mp4", "thumbnail.jpg", "title.txt", "description.txt",
                "captions.srt", "script.txt", "sources-and-credits.txt")
MODEL_DEFAULT = "gemini-3.1-flash-lite"


def _reports(output, proof):
    try:
        production = read_json(output / "production.json")
        quality = read_json(output / "quality.json")
        review = read_json(output / "editorial-review.json")
        scores = review["scores"]
        scope = review["scope"]
        duration = float(scope["duration_seconds"])
        covered = float(scope["reviewed_seconds"])
        if production.get("proof") is not proof:
            return None
        if production.get("technical_passed") is not True or quality.get("passed") is not True:
            return None
        if set(scores) != set(CATEGORIES) or any(type(x) is not int or not 1 <= x <= 10 for x in scores.values()):
            return None
        if scope.get("coverage") != "entire_film_chunks" or scope.get("audio_included") is not True:
            return None
        if duration <= 0 or abs(covered - duration) > .1:
            return None
        if abs(float(production["runtime_seconds"]) - duration) > .75:
            return None
        return production, quality, review
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _accepted(output, proof):
    reports = _reports(output, proof)
    return bool(reports and reports[0].get("editorial_accepted") is True
                and reports[2].get("verdict") == "ready"
                and min(reports[2]["scores"].values()) >= 7)


def _creative_failure(output, proof):
    # Inspect this attempt's own complete reports. Stale work/editorial-feedback
    # cannot turn a provider, schema, decode or missing-media failure into a retry.
    reports = _reports(output, proof)
    return bool(reports and reports[0].get("editorial_accepted") is False
                and (reports[2].get("verdict") in ("revise", "reject")
                     or min(reports[2]["scores"].values()) < 7))


def render_phase(api, work, output, proof, profile):
    phase = "preflight" if proof else "film"
    for attempt in (1, 2):
        candidate = output / "candidates" / f"{phase}-{uuid.uuid4().hex[:12]}-attempt-{attempt}"
        candidate.mkdir(parents=True, exist_ok=False)
        save_json(work / "runner-progress.json", {
            "phase": phase, "attempt": attempt, "candidate": str(candidate),
            "upload_ready": False})
        try:
            produce(api, work, candidate, profile=profile, proof=proof, revise=attempt == 2)
        except PipelineError as exc:
            save_json(candidate / "failure.json", {"phase": phase, "error": str(exc)})
            if attempt == 1 and _creative_failure(candidate, proof):
                feedback = read_json(candidate / "editorial-review.json")
                if (candidate / "timeline.json").exists():
                    feedback = {**feedback, "candidate_timeline": read_json(candidate / "timeline.json")}
                save_json(work / "editorial-feedback.json", feedback)
                print(f"Creative revision: {phase}; applying this candidate's observed feedback once.", flush=True)
                continue
            raise
        if not _accepted(candidate, proof):
            raise PipelineError("Candidate did not produce complete accepted technical and audiovisual review reports")
        return candidate
    raise PipelineError("Creative revision did not produce an accepted candidate")


def upload_package(candidate, work, output):
    if not _accepted(candidate, False):
        raise PipelineError("Only a complete technically and creatively accepted film can enter the upload package")
    metrics = read_json(work / "narration-metrics.json")
    if metrics.get("runtime_within_10_percent_of_target") is not True:
        raise PipelineError("Narration runtime missed the requested duration")
    for name in UPLOAD_FILES:
        path = candidate / name
        if not path.is_file() or path.stat().st_size == 0:
            raise PipelineError("Missing upload deliverable: " + name)
    title = (candidate / "title.txt").read_text().strip()
    description = (candidate / "description.txt").read_text()
    if not title or len(title) > 100 or len(description) > 5000:
        raise PipelineError("Upload metadata exceeds YouTube's title/description limits")
    thumbnail = candidate / "thumbnail.jpg"
    with Image.open(thumbnail) as image:
        if image.width < 1280 or image.height < 720 or abs(image.width / image.height - 16 / 9) > .01:
            raise PipelineError("Thumbnail must be at least 1280x720 with a 16:9 aspect ratio")
    if thumbnail.stat().st_size > 2_000_000:
        raise PipelineError("Thumbnail exceeds the 2 MB upload budget")
    video = read_json(candidate / "quality.json").get("video", {})
    if video.get("width", 0) < 1920 or video.get("height", 0) < 1080:
        raise PipelineError("The final upload package requires the cinematic 1080p render")
    destination = output / "upload-ready"
    if destination.exists():
        raise PipelineError("Upload package already exists; choose a new output directory to preserve it")
    temporary = output / (".packaging-" + uuid.uuid4().hex)
    temporary.mkdir(parents=True)
    try:
        for name in UPLOAD_FILES:
            shutil.copy2(candidate / name, temporary / name)
        for name in ("production.json", "quality.json", "editorial-review.json", "media-credits.json", "music-credits.txt"):
            if (candidate / name).exists():
                shutil.copy2(candidate / name, temporary / name)
        save_json(temporary / "delivery.json", {
            "upload_ready": True, "candidate": str(candidate),
            "voice": metrics["voice"], "duration_seconds": metrics["narration_seconds"],
            "review": "Entire audiovisual film in consecutive reviewed segments",
            "youtube_published": False})
        (temporary / "UPLOAD.txt").write_text(
            "Upload final.mp4 to YouTube. Use title.txt and description.txt, set thumbnail.jpg, "
            "and add captions.srt as English subtitles. Sources and music attribution are included "
            "in the description. The runner does not publish to YouTube.\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def run(title, brief, voice="Charon", minutes=8.75, work=None, output=None,
        profile="cinematic", proof_only=False):
    work = Path(work or ROOT / "work" / "director")
    output = Path(output or ROOT / "output" / "director")
    if not title.strip() or not brief.strip() or len(title) > 200 or len(brief) > 6000:
        raise PipelineError("Supply a title and a short brief")
    if voice not in ("auto", *VOICES) or not .5 <= minutes <= 10:
        raise PipelineError("Choose a supported Gemini voice and 0.5–10 minute duration")
    if profile != "cinematic" and not proof_only:
        raise PipelineError("Draft renders are for proof-only; a full delivery uses cinematic 1080p")
    if (output / "upload-ready").exists():
        raise PipelineError("This output already has a finished upload package; preserve it and choose another directory")
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    defaults = {"GEMINI_SCHEMA_MODE": "prompt", "GEMINI_DIRECTOR_MODE": "rigged",
                "GEMINI_SCENE_BATCH_SIZE": "3",
                "GEMINI_PACKAGE_MODEL": "gemini-3.6-flash",
                "GEMINI_REVIEW_MODEL": "gemini-3.6-flash",
                "GEMINI_REVIEW_CACHE": str(work / "editorial-review-parts")}
    previous = {name: os.environ.get(name) for name in ("GEMINI_MODEL", *defaults)}
    for name, value in defaults.items():
        os.environ.setdefault(name, value)
    try:
        os.environ["GEMINI_MODEL"] = os.getenv("GEMINI_WRITER_MODEL", MODEL_DEFAULT)
        status = director_script.main([
            "--stage", "all", "--title", title, "--brief", brief,
            "--voice", voice, "--minutes", str(minutes), "--work", str(work)])
        if status:
            if status == 75:
                raise QuotaDeferred("Writing or speech quota deferred; resume this checkpoint after quota resets")
            raise PipelineError("Writing or narration stopped; inspect the preserved work/failure.json")
        os.environ["GEMINI_MODEL"] = os.getenv("GEMINI_DIRECTOR_MODEL", "gemini-3.6-flash")
        api = MediaAPI(work / "gemini")
        preflight = render_phase(api, work, output, True, profile)
        save_json(work / "runner-preflight.json", {"accepted": True, "candidate": str(preflight)})
        if proof_only:
            print("DIRECTOR_ACCEPTED_PROOF " + str(preflight), flush=True)
            return preflight
        film = render_phase(api, work, output, False, profile)
        delivery = upload_package(film, work, output)
        save_json(work / "runner-progress.json", {"phase": "complete", "upload_ready": True, "delivery": str(delivery), "candidate": str(film)})
        print("DIRECTOR_UPLOAD_PACKAGE " + str(delivery), flush=True)
        return delivery
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default=os.getenv("VIDEO_TITLE", "The Entire History of Ethiopia"))
    parser.add_argument("--brief", default=os.getenv("VIDEO_BRIEF", "Connect Ethiopia's ancient kingdoms, Adwa, occupation, restoration, revolution and the November 2022 Pretoria agreement through the struggle over who holds power."))
    parser.add_argument("--voice", choices=("auto", *VOICES), default=os.getenv("NARRATOR", "Charon"))
    parser.add_argument("--minutes", type=float, default=float(os.getenv("VIDEO_MINUTES", "8.75")))
    parser.add_argument("--work", type=Path, default=ROOT / "work" / "director")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "director")
    parser.add_argument("--profile", choices=("draft", "cinematic"), default="cinematic")
    parser.add_argument("--proof-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        run(args.title, args.brief, args.voice, args.minutes, args.work, args.output, args.profile, args.proof_only)
        return 0
    except (PipelineError, ValueError, KeyError, FileNotFoundError) as exc:
        save_json(args.output / "failure.json", {"error": str(exc), "upload_ready": False})
        print(str(exc), flush=True)
        return 75 if isinstance(exc, QuotaDeferred) else 1


if __name__ == "__main__":
    raise SystemExit(main())
