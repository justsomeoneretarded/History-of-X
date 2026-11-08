# History of X — directed history films

A GitHub Actions pipeline for original history videos from a title and short brief. The current rebuild studies the user's supplied reference clips, uses Gemini for writing, narrator auditions and executable scene direction, and renders original layered illustration with historical media. The earlier generic stickman film was rejected creatively; its movement checks did not establish production quality.

## Run the directed pipeline

1. Keep your free Gemini key in the repository Actions secret **GEMINI_API**.
2. Open [Actions → Directed history film](https://github.com/justsomeoneretarded/History-of-X/actions/workflows/director-film.yml) and select **Run workflow**.
3. Enter a title and brief. The default is an original Ethiopia history, approximately **8 minutes 45 seconds**. `auto` auditions Puck and Charon; individual Gemini voices are also selectable.
4. Start with **proof**, which renders complete opening and treaty scenes. **film** renders the whole narration. `draft` is 540p; `cinematic` is 1080p/30fps.
5. Download **directed-proof** or **directed-film**. Read `production.json` and `editorial-review.json`: technical success alone does not mean the candidate is upload-ready.

The workflow writes a video, external subtitles, thumbnail, title, description, full credits, contact sheet, executable scene programs and review evidence. It does not upload to YouTube. A failed creative review preserves the candidate for revision and stops the workflow.

`audio_run` reuses a **director-audio** checkpoint. `resume_run` reuses a **directed-checkpoint**. Select `revise` to apply the previous candidate's concrete editorial feedback. Reusing accepted audio does not rewrite the script or regenerate its voice. Artifacts expire after 14 days.

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
| Direction | Gemini generates original SVG artwork and explicit timed layer transforms; it also sees approved historical subject images |
| Animation | CairoSVG rasterization, Pillow floating-point composition, parent rigs, expressions, gestures, props, reveals and camera keyframes |
| Historical media | Subject-specific licensed collection, Internet Archive newsreel, Cleveland Museum and Met open-access objects; actual use recorded separately from availability |
| Sound | Licensed Scott Buckley recordings with restrained levels, crossfades, narration ducking, deliberate silence and explicitly requested original foley |
| Editing | FFmpeg; cumulative frame timing, uniform audio format, 48kHz stereo AAC, loudness and decode checks |
| Packaging | Gemini title/description/hook, large authentic subject composition, complete source and media attribution outside the picture |
| Review | Actual video/audio critique for visual relevance, acting, composition, narration and pacing; technical checks remain separate |

The renderer has no required palace/army templates or implicit walking loops. The scene program actually executes the authored timing. Purposeful stillness is allowed; decorative movement does not earn creative approval.

## Free-tier limits and recovery

The directed workflow defaults to **Gemini 3.8 Flash** for complex writing/direction/review, and **Gemini 3.8 Flash TTS** for speech. `GEMINI_DIRECTOR_MODEL` can select a supported alternative; the older workflows retain their separate settings. Google's current standard pricing lists free text input/output for 3.8 Flash, but project access and quotas still vary. Consult [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [project rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

- Request starts are separated by at least 65 seconds. This is a conservative application policy, not Google's universal required sleep.
- RPM, input TPM and daily quotas are separate and shared by a Google project. Sleeping cannot cure an exhausted daily quota.
- Local rolling budgets default to 48 text attempts and 16 speech attempts. They are guardrails, not a claim about the provider allowance.
- 3.8 Flash documents a 1,048,576-token input limit and 65,536-token output limit. This application uses substantially smaller requests and bounded outputs.
- Speech is split by chapter, with at most 450 words per request as an application reliability bound. ASR checks completeness before audio is accepted.
- Accepted responses, scripts, audio and scene programs are checkpointed. Provider quota failures preserve progress; the pipeline does not silently use a paid provider.

Native generated video/images are not assumed to be available on the free key. This implementation uses Gemini direction, original vector illustration and licensed authentic media. It does not claim that procedural animation equals native AI video generation or that automated scores guarantee audience retention.

## Local development

Python 3.11–3.12, FFmpeg/ffprobe with libass, Cairo and the bundled fonts:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[alignment,test]'
export GEMINI_API='your-key'
python -m history_of_x.director_script --title 'The Entire History of Ethiopia' --minutes 8.75
python -m history_of_x.director_film --proof --profile draft
pytest -q
```

The older `produce.yml`, archival workflows, Chatterbox references and previous validation records remain for recovery and comparison. They are not evidence that the new directed film has passed creative review. See [validation history](docs/VALIDATION.md).
