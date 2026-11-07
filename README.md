# History of X — animated history explainers

Give the runner a title and a short brief. It uses Gemini for research-informed writing, narration, speech-timed visual direction, YouTube packaging and visual critique. Original flat illustrations animate locally into a colourful 1080p explainer with understated humor, a running year display and a new visual every 3–6 seconds.

## Run

1. Keep your Gemini API key in the repository Actions secret **GEMINI_API**.
2. Open [Actions → Produce animated history video → Run workflow](https://github.com/justsomeoneretarded/History-of-X/actions/workflows/produce.yml).
3. Enter a title and brief, choose a Gemini voice and target narration length (0.5–10 minutes). **Puck** is the default; Charon, Kore, Fenrir, Orus and Aoede are alternatives.
4. Download **animated-video** after all stages pass. It contains `final.mp4`, `thumbnail.jpg`, two thumbnail alternatives, title, description, SRT/ASS captions, sources, storyboard, contact sheet and quality reports.

The `ethiopia` preset reuses reviewed historical evidence, but Gemini writes a **new animated script**. It does not reuse the earlier archival film's narration or script. The `auto` preset researches your topic. Artifacts are retained for 14 days. The runner does not upload to YouTube.

## What changed in the animated version

- **Gemini 3.8 Flash TTS** replaces Chatterbox. The Gemini voices are honestly labeled; they are not the Warguy/Kit Laser reference voices.
- **Gemini 3.5 Flash-Lite** writes and revises the script, plans each visual around the spoken phrase, designs two thumbnail concepts and critiques rendered images. A verified free text model can be selected with `GEMINI_MODEL`.
- Original vector-style people, buildings, documents, trade objects and other subjects replace a repeating photographic slideshow. Maps are not a default or fallback.
- Objects animate with easing on a supersampled canvas; the old integer-crop pan/zoom system is not used.
- Only the year, essential narrative labels and captions appear. No channel/chapter chrome, source/reference labels or long credit screens are added. Sources and attribution remain in the delivery package and description.
- Original locally synthesized instrumental accompaniment and rare short musical stings replace licensed soundtrack excerpts. No creator's songs or jokes are copied.

Gemini image-generation API models currently have **no free tier**. The free-key pipeline therefore uses Gemini to direct bounded vector compositions and thumbnail concepts, then renders them locally. It does not silently call paid image, video or music services. Rendering, audio mixing and encoding use FFmpeg; local faster-whisper checks speech and assists caption timing.

## Quota and recovery

All Gemini request starts are spaced at least 65 seconds apart. Text and speech have separate configurable rolling 24-hour budgets (24 text attempts and 16 speech attempts by default), while sharing a pacing ledger. Repository concurrency prevents this workflow and the legacy Gemini pipeline from overlapping. Other applications using your Google project still share provider quotas.

Successful API responses, scripts, chapter audio and storyboards are checkpointed. If a run fails, use **identical inputs** and put its run ID in `resume_run`. Accepted work is recovered. A provider quota error stops with a checkpoint rather than sleeping all day or switching to a paid service. Transient retries and speech regeneration are bounded.

Variables: `GEMINI_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_TEXT_REQUEST_BUDGET`, `GEMINI_TTS_REQUEST_BUDGET`. Supported TTS models are `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts`; access and quota are project-dependent. Request budget exhaustion is distinct from the model's token limits.

## Local use

Python 3.11, FFmpeg/ffprobe with libass, and the bundled DejaVu fonts:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[alignment,test]'
export GEMINI_API='your-key'
python -m history_of_x.animated --title 'The history of Ethiopia' --brief 'Explain power, Adwa and independence; end at the November 2022 Pretoria agreement.' --preset ethiopia --voice Puck --minutes 8
```

Stages: `--stage plan`, `voice`, `direct`, `render`. Preserve the same inputs and work directory. `draft` is 540p/24fps; `standard` and `cinematic` are 1080p/30fps. The historical images and Top10-Movies reference voices remain available through the explicitly labeled **Legacy archival documentary** workflow; they are not used in the new default animated pipeline.

Automated checks cover evidence IDs, script structure, speech completeness, exact caption text, shot timing, stable settled frames, stream duration, full media decoding and black intervals. Gemini's visual critique does not certify historical accuracy, pronunciation, motion quality or thumbnail performance. Review the completed film before uploading.

See [production details](docs/PRODUCTION.md) and [validation history](docs/VALIDATION.md).
