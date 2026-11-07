# History of X — moving history documentaries

Give the runner a title and a short brief. It uses Gemini for research-informed writing, narration, speech-timed visual direction, YouTube packaging and visual critique. The picture track uses frame-by-frame articulated characters and physical environments: people walk and carry goods, leaders negotiate, ships move on water, workers build, and troops march or retreat. Historical photographs and public-domain moving footage are mixed into the animated film. A running year display and 3–6 second camera beats keep the chronology clear.

[Watch the 45-second motion proof](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42350418522/artifacts/13565064705). Gemini reviewed the actual video and identified sustained character action rather than a slideshow.

## Run

1. Keep your Gemini API key in the repository Actions secret **GEMINI_API**.
2. Open [Actions → Produce animated history video → Run workflow](https://github.com/justsomeoneretarded/History-of-X/actions/workflows/produce.yml).
3. Enter a title and brief, choose a Gemini voice and target narration length (0.5–10 minutes). **Puck** is the default; Charon, Kore, Fenrir, Orus and Aoede are alternatives.
4. Download **animated-video** after all stages pass. It contains `final.mp4`, `thumbnail.jpg`, two thumbnail alternatives, title, description, SRT/ASS captions, sources, storyboard, contact sheet and quality reports.

The `ethiopia` preset reuses reviewed historical evidence, but Gemini writes a **new animated script**. It does not reuse the earlier archival film's narration or script. The `auto` preset researches your topic. Artifacts are retained for 14 days. The runner does not upload to YouTube.

## What changed in the animated version

- **Gemini 3.8 Flash TTS** replaces Chatterbox. The Gemini voices are honestly labeled; they are not the Warguy/Kit Laser reference voices.
- **Gemini 3.5 Flash-Lite** writes and revises the script, plans each visual around the spoken phrase, designs two thumbnail concepts and critiques rendered images. A verified free text model can be selected with `GEMINI_MODEL`.
- A frame-by-frame renderer redraws jointed limbs, gestures, cargo, ships, water, smoke and moving crowds on every frame. It does not display a row of icon cards or freeze after an entrance animation. Missing choreography stops production; there is no slideshow fallback.
- Characters use two-link limb articulation and continuous world time across camera cuts. The old image-entrance and integer-crop zoom systems are not used.
- Only the year, essential narrative labels and captions appear. No channel/chapter chrome, source/reference labels or long credit screens are added. Sources and attribution remain in the delivery package and description.
- Original locally synthesized instrumental accompaniment and rare short musical stings replace licensed soundtrack excerpts. No creator's songs or jokes are copied.

Google’s current native video generator, **Gemini Omni 1.2 Flash**, has no free API tier; the earlier Veo preview endpoint is retired. Gemini image-generation API models also have **no free tier**. The free-key pipeline therefore uses Gemini to direct bounded vector compositions and thumbnail concepts, then renders them locally. It does not silently call paid image, video or music services. Rendering, audio mixing and encoding use FFmpeg; local faster-whisper checks speech and assists caption timing.

## Quota and recovery

All Gemini request starts are spaced at least 65 seconds apart. Text and speech have separate configurable rolling 24-hour budgets (48 text attempts and 16 speech attempts by default), while sharing a pacing ledger. Repository concurrency prevents this workflow and the legacy Gemini pipeline from overlapping. Other applications using your Google project still share provider quotas.

Successful API responses, scripts, chapter audio and storyboards are checkpointed. If a run fails, use **identical inputs** and put its run ID in `resume_run`. Accepted work is recovered. **Refine saved animated video** re-renders a completed checkpoint with current graphics and captions, preserving its script and voice. Its default text-attempt budget is 48. **Recreate as moving documentary** preserves saved narration, creates Gemini choreography, publishes a short moving preview, and renders the full film only after that preview passes sustained-motion checks and Gemini video review. A provider quota error stops with a checkpoint rather than sleeping all day or switching to a paid service. Transient retries and speech regeneration are bounded.

Variables: `GEMINI_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_TEXT_REQUEST_BUDGET`, `GEMINI_TTS_REQUEST_BUDGET`. Supported TTS models are `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts`; access and quota are project-dependent. Request budget exhaustion is distinct from the model's token limits.

## Local use

Python 3.11, FFmpeg/ffprobe with libass, and the bundled Space Grotesk/DejaVu fonts:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[alignment,test]'
export GEMINI_API='your-key'
python -m history_of_x.animated --title 'The history of Ethiopia' --brief 'Explain power, Adwa and independence; end at the November 2022 Pretoria agreement.' --preset ethiopia --voice Puck --minutes 8
```

Stages: `--stage plan`, `voice`, `direct`, `render`. Preserve the same inputs and work directory. `draft` is 540p/24fps; `standard` and `cinematic` are 1080p/30fps. The historical images and Top10-Movies reference voices remain available through the explicitly labeled **Legacy archival documentary** workflow; they are not used in the new default animated pipeline.

Checks cover evidence IDs, script structure, speech completeness, caption text, shot timing, full media decoding and sustained movement after the first second. A static video is rejected by the motion gate. Gemini watches moving MP4 samples and reports observed physical actions. These checks do not measure audience retention or thumbnail click-through rate.

See [production details](docs/PRODUCTION.md) and [validation history](docs/VALIDATION.md).

## Historical media beyond Wikipedia

The Ethiopia remake includes two genuine 1935 moving-newsreel excerpts from the Internet Archive Universal Newsreels collection, a CC0 Ethiopian gospel leaf from Cleveland Museum of Art Open Access, and relevant public-domain historical portraits. The 1935 footage is a separately dated, wordless nine-second bridge; it is never used as footage of Adwa in 1896. Sources, dates and checksums are bundled in `assets/footage/` and the images actually used are recorded in the delivery’s `media-credits.json`. Credits remain outside the picture.
