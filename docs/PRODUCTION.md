# Directed production architecture and limits

This describes the current `history-of-x-film` runner and **Create a complete history video** Actions workflow. The earlier Chatterbox, icon-card, moving-canvas and archival-only workflows are retained as legacy tools; they do not describe the current default.

## Input and complete flow

The user supplies a title and short brief. Charon is the default Gemini narrator; Puck, Kore, Fenrir, Orus, Aoede and an automatic Puck/Charon audition are optional. The default duration is 8.75 minutes. Full production uses cinematic 1920×1080 at 30 fps.

1. Gather bounded source material, then write an original outline and five chronological chapters: Hook, Roots, Catalyst, Turning Point and Aftermath. Chapter budgets, complete thoughts and spoken cadence are checked. There is no additional manual finished-script factual-approval stage.
2. Generate Gemini speech by chapter, verify completeness using local faster-whisper, preserve the accepted audio, and align the written words to actual scene audio. No global time stretching is used to force the runtime.
3. Select genuinely relevant licensed media and direct scene graphs using actual spoken timing. The Ethiopia episode also contains exact-passage production notes and three director-refined choreographies, recorded transparently in the saved programs.
4. Compile original illustrated characters, props, formations, routes and authentic inserts into executable animation. Inspect complete sample scenes; apply one automatic creative revision if the actual media review calls for it. For a full run, a technically valid sample that remains creatively rejected is retained as diagnostic evidence and production continues to the complete review candidate; it is never relabeled accepted. Provider failures and invalid geometry still stop the run. A proof-only request still requires sample acceptance.
5. Render the complete film, mix sound, package the thumbnail and metadata, and review every consecutive section of the actual audiovisual film. Only a complete accepted 1080p film can enter the upload package.

## Models and their roles

| Role | Current default or supported route | Reason and limits |
| --- | --- | --- |
| Outline and script | Gemini 3.1 Flash Lite | Completed the current original script; separate chapter requests use 4,500 output tokens for the outline and 6,500 per chapter/revision. |
| Scene direction | Gemini 3.6 Flash | Returns up to three independent scene plans per request, cutting 24 base directions to eight requests before repairs. Each sibling is validated and saved independently. |
| Scene availability recovery | Hosted Gemma 4 31B for 3.6/Hydrogen; 26B A4B for earlier Gemini routes | Verified free text models, MINIMAL thinking and prompted JSON. They do not handle audiovisual review in this app. Invalid geometry or coordinates still fail validation. |
| Narration | Gemini 3.8 Flash TTS | Studio narration via REST Interactions, v1beta, with style metadata separate from the verbatim transcript. Existing accepted chapters are reused. |
| Packaging and audiovisual review | Gemini 3.6 Flash | Actual title/description generation and actual MP4 plus audio review. Review covers consecutive 90-second sections, including the complete tail. Video sampling uses three frames per second so short physical contacts and marching poses are better represented than at the API's one-frame-per-second default. Older configured Gemini review models use 30-second sections. |
| Optional alternative | Gemini 4 Hydrogen | Officially free; native schemas, LOW thinking, 65,536 combined thinking/output tokens, no sampling parameters. Live attempts returned HTTP 503; availability is not assumed. |
| Experimental CPU comparison | Qwen3 4B Instruct 2507, Q4_K_M through Ollama | The real four-vCPU experiment generated an invalid graph in 545.94 seconds at 4.33 decoded tokens/second; repair timed out. It is excluded from production. |

Gemini 4 Carbon, Argon and Neon are not selected because current pricing excludes them from the free tier. Native image and video generation are also not invoked through paid-only endpoints. The moving picture is original rendered illustration plus authentic media, directed with model text; it is not claimed as Gemini-native generated video.

Legacy Warguy and Kit Laser recordings from Top10-Movies remain in the older Chatterbox path. They are not Gemini built-in voice names. The current Gemini runner explicitly labels its actual selected voice.

## Provider limits versus application bounds

| Item | Documented serving limit or current application policy |
| --- | --- |
| Gemini 3.6 / 3.8 Flash text | 1,048,576 input tokens and 65,536 output tokens. Account RPM, TPM and RPD remain project-specific. |
| Gemini 4 Hydrogen | 1,048,576 unified context; input, thinking and output share it. Normal synchronous output allowance is 65,536. |
| Gemini 3.8 Flash TTS | 8,192 input tokens; 16,384 output audio tokens. Google describes 25 audio tokens/second. These serving limits are not a guaranteed chapter duration or project quota. |
| TTS reliability bound | At most 450 spoken words per chapter request; compare actual speech completeness and duration before accepting it. |
| Text payload guard | The Actions profile sets a conservative 40,000 estimated-token guard using three characters/token. Provider usage metadata supplies actual successful-request counts. |
| Direction output bounds | 14,000 tokens for a grouped scene response; 3,500 for an individual Gemini direction, 5,000 for an individual Gemma recovery. Hydrogen applies its documented 65,536 allowance. |
| API pacing | At least 65 seconds between request starts, shared across roles. This is our conservative policy, not a universal Google sleep requirement. |
| Local daily guard | Actions allows at most 64 text attempts per model and 16 speech attempts in a rolling day. Failed attempts count locally; real provider allowances may be lower. |
| Actual project quota evidence | A November 25 response reported 20 daily free requests for this project's Gemini 3.8 Flash text model. Do not apply that number to every model or account. |
| Request deadlines | 15-second connection timeout; normally 180-second read deadline, or 300 seconds for large-output text requests. Up to three transient attempts. |
| Actions jobs | Production timeout 330 minutes; normal CI 20 minutes. The optional Qwen experiment allows 40 minutes. |

Daily quota errors preserve work and defer production; sleeping a minute cannot restore an exhausted daily allowance. HTTP 503/network failures have bounded recovery through verified free models. There is no silent paid fallback. Accepted script, speech, scene programs and partial renders are checkpointed.

## Animation and historical media

The renderer uses original period characters and scenery, expressive faces, articulated limbs, two-link arm kinematics, walking during travel and exact prop attachment/ownership. A new contact may smoothly interrupt a gesture; overlapping physical contacts remain errors. Held props stay attached through movement and transfers. Cameras use floating transforms and bounded framing, with Cairo vector replay and supersampled text.

Scene graphs allow at most ten nodes, four full actors, eighteen timed actions and one hundred render layers. Directions must explain setup, decision/contact and consequence. Camera drift or a moving label alone does not establish useful acting. The ordinary visual rhythm is a development every three to six seconds, with purposeful holds.

The Ethiopia collection includes Commons historical photographs and objects, Cleveland and Met CC0 material, and genuine 1935 Universal Newsreel excerpts from the Internet Archive. Other topics discover subject-matched public-domain/CC0 museum material. An available asset is not automatically a relevant asset. Named portraits and dated footage must match the narration; 1935 footage is not reused as 1896 or contemporary war footage.

Only necessary names, ideas and a discreet date indicator appear. Source/channel labels, reference text, chapter chrome and attribution screens are excluded from the picture. Still inserts have deliberate editorial timing; maps are used when they explain geography.

## Sound, editing and packaging

Gemini narration is mixed with licensed Scott Buckley music, narration ducking, crossfades, deliberate quiet and sparse original foley. Suffering is treated seriously; comic stings are not placed over atrocities or famine.

FFmpeg encodes H.264/yuv420p picture and 48 kHz stereo AAC. Cumulative frame timing prevents scene drift. Audio pieces share one sample format before assembly. Captions are supplied separately as SRT so viewers control them.

The upload package contains final.mp4, thumbnail.jpg, title.txt, description.txt, captions.srt, script.txt and sources-and-credits.txt, plus the quality and review records. The thumbnail is 1280×720 and below 2 MB; titles are at most 100 characters and descriptions at most 5,000. Attribution remains in the description and delivery credits. The runner never publishes to YouTube.

## Validation and recovery

Technical checks cover complete decode, streams, black intervals, actual duration, narration completeness, loudness and peak levels. Creative review scores visual relevance, acting, composition, narration and editorial pacing independently; every category must reach seven and the verdict must be ready. Reviews judge the entire film in consecutive audiovisual sections, rather than selected attractive stills.

An invalid or creatively rejected sample cannot become the upload package. A failed later revision does not hide an earlier rendered sample: evidence explicitly distinguishes the chosen movie from the newest failed attempt. Raw model drafts, accepted directions, feedback and renders remain inspectable.

Use resume_run only with a run that actually uploaded directed-checkpoint. Bootstrap/test failures may have no recoverable checkpoint. Identical script and narration are reused; artifact retention is 90 days.

Media bootstrap reuses suitable installed FFmpeg/ffprobe with ass and loudnorm filters. On hosted Ubuntu it otherwise installs maintained media packages, Cairo and fonts with bounded 240-second update and 600-second install deadlines. Per-scene rendering bounds memory, and compiled vector replay avoids repeatedly rasterizing every layer in Python.

See [the validation record](VALIDATION.md) for measured successes and failures. Code tests establish contracts and regressions; only the actual completed production establishes that a film was made and accepted.

## Current provider documentation

- [Gemini 3.6 Flash](https://aistudio.google.com/docs/models/gemini-3.6-flash)
- [Gemini 3.8 Flash TTS](https://aistudio.google.com/docs/models/gemini-3.8-flash-tts)
- [Hydrogen migration](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen)
- [Pricing and free eligibility](https://aistudio.google.com/docs/pricing)
- [Project rate limits](https://aistudio.google.com/docs/rate-limits)
- [Video and audio processing](https://aistudio.google.com/docs/video-understanding)
- [Hosted Gemma models](https://gemma.ai/deployment/gemini-api/)
