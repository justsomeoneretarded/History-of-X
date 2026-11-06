# History of X

Generate a cinematic historical documentary from a title and a short brief. GitHub Actions coordinates research, a five-chapter script, licensed stills, Chatterbox Original narration, moving shots, captions, a ducked soundtrack, thumbnail and upload metadata.

**Default narrator: Warguy.** Kit Laser is also available. Both reference recordings and the CPU narration design come from the owner's Top10-Movies repository. Speech does not consume Gemini quota.

Completed film: [download the Ethiopia upload package](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42305472051/artifacts/13546308132) — 1080p, 8:38 including credits, Warguy narration. Includes the MP4, thumbnail, captions, description and sources. Its historical scope ends at the November 2022 Pretoria agreement. Actions artifacts are retained for 14 days.

## Run a video

1. Add a repository Actions secret named `GEMINI_API` containing your Gemini API key.
2. Open **Actions → Produce documentary → Run workflow**.
3. Enter the title and small brief. Select Warguy or Kit Laser, a target runtime, and a render profile.
4. Download the `documentary-final` artifact after the render job succeeds. It contains `final.mp4`, captions, thumbnail, description, source/asset credits and a quality report.

The default `auto` preset generates a new script from your title and brief. The `ethiopia` and `pilot` presets use fixed, curated scripts; their length does not change with the minutes input. Ethiopia includes reviewed, bundled visual assets to avoid depending on live Wikimedia downloads. **Render saved production** can rebuild the visuals from accepted narration without more Gemini or TTS calls.

For repeatable comparisons, use **Actions → Compare production renders** with a completed production run ID. It reuses verified narration and renders draft, standard and cinematic versions with measured quality reports.

The default Gemini text model is `gemini-3.5-flash-lite`. Set repository variable `GEMINI_MODEL` to another verified free model if required. New models outside the conservative allowlist also require `CONFIRMED_FREE_MODEL` set to that exact ID. Model access and free quota depend on your project. No paid media API fallback is configured. API calls start at least 65 seconds apart; a rolling 24-hour request budget defaults to 12. Set `GEMINI_REQUEST_BUDGET` and `GEMINI_INPUT_TOKEN_BUDGET` to your actual limits. One workflow is serialized to avoid overlapping generation within this repo; other apps using your Gemini project still share its quota.

An exhausted quota stops cleanly. Resume the same inputs using the failed run ID to recover checkpoints. For long videos, source gathering and free quota may require multiple runs. Ordinary runner CPU inference can take substantially longer than the final video's length. Narration is split into five independently resumable chapter jobs, with up to three running concurrently.

## Local use

Python 3.11, FFmpeg, DejaVu fonts. Install CPU PyTorch first:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
bash scripts/install_voice.sh
export GEMINI_API='your-key'
history-of-x --title 'The history of Ethiopia' --brief 'Explain Adwa, sovereignty and the costs of centralization.' --voice warguy --minutes 8
```

Stages can be run separately with `--stage plan`, `--stage voice`, and `--stage render`. Keep the same inputs and `--work` directory. Use a new work directory for a different request. Accepted speech and cached outputs are retained. The `draft` profile renders 540p/24fps; `cinematic` renders 1080p/30fps with grading and vignette.

## What is checked

Five ordered chapters, banned writing phrases, valid evidence IDs, bounded narration, licensed image metadata, audio completeness via local transcription, missing/repeated speech, caption grouping, final duration, full media decoding and unexpected black intervals. A contact sheet is included. These checks support editorial review; they do not certify historical accuracy or every image's relevance. A source-linked model revision is not independent historical verification.

All maps are labeled present-day geographic references. Historical boundaries are never inferred from modern borders. Missing scene images may use the reference map, but the production stops when insufficient licensed assets are found.

## Attribution

Music: Titan, Celestial and Aurora by Scott Buckley, CC BY 4.0. See `assets/music/LICENSE.md`. Complete visual and soundtrack credits are generated with the video. Complete attribution is also rendered into the video end credits, so it travels with the film. `credits.html` is included for convenient reference. This runner does not upload to YouTube.

See `docs/PRODUCTION.md` for limits and the implementation record. No API secret is stored in the code or artifacts.
