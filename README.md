# History of X — directed history films

A GitHub Actions pipeline for original history videos from a title and short brief. The current rebuild studies the user's supplied reference clips, uses Gemini for writing, narrator auditions and executable scene direction, and renders original layered illustration with historical media. The earlier generic stickman film was rejected creatively; its movement checks did not establish production quality.

## Run the directed pipeline

1. Keep your free Gemini key in the repository Actions secret **GEMINI_API**.
2. Open [Actions → Create a complete history video](https://github.com/justsomeoneretarded/History-of-X/actions/workflows/director-film.yml) and select **Run workflow**.
3. Enter a title and short brief. **Charon** is selected by default; other Gemini voices or an automatic Puck/Charon audition are optional. The target is **8 minutes 45 seconds**.
4. Leave **film** selected. The runner checks complete sample scenes, makes one automatic creative revision if needed, then renders and reviews the full **1080p/30fps** film.
5. On accepted completion, download **youtube-upload-ready**. Upload **final.mp4**, use **thumbnail.jpg**, **title.txt**, **description.txt**, and add **captions.srt** as English subtitles.

The runner does not publish to YouTube. **review-candidates** contains separate samples and rejected attempts; these are not the upload package. A provider failure or a candidate that still misses the creative threshold stops production and preserves its checkpoint. Automated checks cannot guarantee audience retention or replace judgment about the finished film.

Use **resume_run** to restore a prior run's **directed-checkpoint**. Identical accepted scripts, narration, scene programs and renders are reusable; changed writing requirements invalidate the affected writing cache. Partial chapters and narration are preserved before visual production. Artifacts expire after **90 days**. **proof** is an optional sample-only mode.

## Reference roles

All five supplied clips were actually sent to Gemini as MP4 with audio, rather than supplied only as URLs. See the [successful study run](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42453592145) and [grounded directing guide](assets/style/reference-study.json).

- **Jerusalem:** conversational writing, short varied sentences, natural delivery, continuity across centuries and approximately 8:46 runtime. Local ASR measured approximately 1,527 words / 174 words per minute.
- **Pig War:** staged information, character reactions, purposeful holds, physical metaphors and a mixture of animation, maps and historical imagery.
- **Britain, Rome and Egypt:** additional examples of chronological compression, contrasting scale, locations and explanation.

These are craft references. Their scripts, characters, jokes, voices and songs are not copied. Some AI timestamps were inaccurate; the guide distinguishes manually checked examples from uncertain observations. Uploaded reference footage is not committed to the repository. Temporary transfer used encrypted files and a private key held only on the runner.

## Production parts

| Part | Implementation |
| --- | --- |
| Outline and script | Gemini, bounded original scene budgets, source IDs and measured spoken cadence |
| Narration | Gemini 3.8 Flash TTS; actual voice auditions judged for completeness, naturalness, clarity and rhythm |
| Direction | Gemini writes executable scene graphs: staging, timed decisions, expressions, movements, contact and consequences; historical image metadata accompanies approved inserts |
| Animation | Original illustrated period characters/scenery, two-link arm kinematics, continuous prop ownership, Cairo vector replay, supersampled text and bounded camera keyframes; Pillow remains the comparison renderer |
| Historical media | Curated Ethiopia collection and Internet Archive newsreel; other topics discover specifically matched CC0 images through Cleveland and Met museum APIs; actual use is recorded |
| Sound | Licensed Scott Buckley recordings with restrained levels, crossfades, narration ducking, deliberate silence and explicitly requested original foley |
| Editing | FFmpeg; cumulative frame timing, uniform audio format, 48kHz stereo AAC, loudness and decode checks |
| Packaging | Gemini title/description/hook, large authentic subject composition, complete source and media attribution outside the picture |
| Review | Actual video/audio critique for visual relevance, acting, composition, narration and pacing; technical checks remain separate |

Gemini chooses among original illustrated characters, settings and props, and directs their actions through a validated scene graph. Hands reach exact targets, held props stay attached, and walking occurs only during explicit travel. The renderer does not invent actions from prose. Purposeful holds are allowed; decorative movement does not earn creative approval. Saved directions are recompiled after artwork or renderer fixes without another provider request.

## Free-tier limits and recovery

The default runner uses **Gemini 3.1 Flash Lite** for writing and direction, **Gemini 3.5 Flash Lite** for audiovisual review, and **Gemini 3.8 Flash TTS** for speech. These are routing defaults, not a promise of provider availability. The current Ethiopia film remains in production; no newly accepted complete upload package has been delivered.

**Gemini 4 Hydrogen** is also supported as an explicitly selected free alternative. Google's [model documentation](https://aistudio.google.com/docs/models/gemini-4-hydrogen), [migration guide](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen) and [pricing](https://aistudio.google.com/docs/pricing#gemini-4-hydrogen) list free text generation with audiovisual input. Hydrogen does not generate speech, images or video. Its adapter uses native JSON schemas, LOW thinking, a 65,536-token combined thinking/output allowance and no sampling parameters, following the migration guidance. Up to three independent scene directions share a request; audiovisual review covers consecutive 90-second sections. Paid-only Gemini 4 Carbon, Argon and Neon are excluded. Account access and a completed live film still need to be established.

Google also hosts [Gemma 4 through the same API key](https://gemma.ai/deployment/gemini-api/) with [free input/output](https://aistudio.google.com/docs/pricing#gemma-4). The bounded direction recovery path supports Gemma 4 26B A4B as text-only generation, with plain JSON instructions, MINIMAL thinking and local executable-scene validation. Actual production attempts returned incomplete output or service errors, so it is not established as a working recovery route. Gemini remains responsible for speech and audiovisual review.

- Request starts are separated by at least **65 seconds**. This is an application policy, not Google's universal required sleep.
- RPM, input TPM and daily quotas are separate and shared by a Google project. Sleeping cannot cure an exhausted daily quota. A real November 25 response reported **20 daily free-tier requests for this project's Gemini 3.8 Flash**; this is observed project evidence, not a universal allowance for every model.
- Local rolling guards allow at most 64 text attempts per model and 16 speech attempts. Provider allowances can be lower. Both successful and failed attempts enter the local ledger.
- Gemini 3.8 Flash documents a 1,048,576-token input limit and 65,536-token output limit. Hydrogen uses a 1,048,576-token unified context with thinking/output included. Requests remain much smaller; most text directions use a 3,500-token output cap, and Gemma recovery uses 5,000.
- Speech is split by chapter, with at most **450 words per request** as an application reliability bound. ASR checks completeness before audio is accepted. This is not claimed as Google's voice output limit.
- Accepted responses, scripts, audio, scene programs and partial renders are checkpointed. Quota failures preserve progress. There is no silent paid-provider substitution.

An optional CPU-only **Qwen3 4B Instruct 2507, Q4_K_M** benchmark runs through Ollama on GitHub Actions without the Gemini key. Its measured first response took 545.94 seconds at 4.33 decoded tokens/second and failed executable-scene validation; its repair timed out. It produced no accepted video and is not enabled as a production fallback. See the [measured validation record](docs/VALIDATION.md).

Native generated video/images are not assumed to be available on the free key. This implementation uses Gemini direction, original vector illustration and licensed authentic media. It does not claim that procedural animation equals native AI video generation or that automated scores guarantee audience retention.

## Local development

Python 3.11–3.12, FFmpeg/ffprobe with libass, Cairo and the bundled fonts:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[alignment,test]'
export GEMINI_API='your-key'
history-of-x-film --title 'The Entire History of Ethiopia' --brief 'An original story across centuries, ending with the November 2022 Pretoria agreement.' --voice Charon
pytest -q
```

The older `produce.yml`, archival workflows, Chatterbox references and previous validation records remain for recovery and comparison. They are not evidence that the new directed film has passed creative review. See [validation history](docs/VALIDATION.md).
