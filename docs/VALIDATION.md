# Validation record

## Real local production comparison

A source-linked five-chapter Ethiopia pilot was synthesized with the actual Warguy reference, transcribed, aligned and rendered in three profiles using the same script, audio and licensed visuals. These are actual video files, not mocked model outputs.

| Profile | Output | Render + package + QA time | File size | Quality gate |
|---|---|---:|---:|---|
| Draft | 960×540, 24 fps | 26.93 s | 6.17 MB | Passed |
| Standard | 1920×1080, 30 fps | 173.56 s | 35.21 MB | Passed |
| Cinematic | 1920×1080, 30 fps | 182.72 s | 32.74 MB | Passed |

The films are approximately 67.6 seconds including visible attribution credits; the narration is approximately 39.6 seconds. Minimum transcript coverage across scenes was 0.9375. All three passed stream, duration, full decode and black-interval checks. Output pixel format is yuv420p. Contact sheets were inspected. Measured wall times are specific to this session's CPU and concurrent load, not promised GitHub Actions timings. The cinematic profile was retained as the default for its more restrained palette, readable captions and preserved portrait framing. No invented numerical improvement multiplier is claimed.

The actual Kit Laser reference was also used to synthesize and transcribe the same opening passage. It passed the speech completeness checks. This verifies the selector changes real reference conditioning rather than merely changing a label.

## Corrections made during iteration

- Replaced a retired/unavailable Gemini 2.5 Flash default after a real API 404, and listed live model capabilities with the user's key.
- Added bounded API probes, request pacing, explicit local budgets, disabled nested SDK retries and saved quota state.
- Pinned PyAV 16 after the latest release broke faster-whisper's metadata_errors argument.
- Corrected Wikipedia redirects and extract truncation; retained source revision IDs in the curated episode.
- Preserved full portrait subjects over softly blurred side backgrounds.
- Moved map labels apart and separated reference-map text from caption/header areas.
- Added visible image/music credits so required attribution travels with the uploaded film.
- Standardized limited-range BT.709/yuv420p media output after probing the first encoded film.
- Split long scripts into bounded chapter drafts/revisions and narration into three concurrent chapter jobs, with strict merge checks.
- Added an actual animated geographic-highlight render test; it does not fabricate historical borders.
- Re-query empty asset searches on resume, and broaden overly specific queries by one term.

## Test suite

The local suite includes script/schema and citation constraints, banned phrases, license acceptance/rejection, exact caption text preservation, shared quota ledgers, pacing, cached requests, daily-budget exhaustion, truncated responses, voice checkpoint merging, and actual FFmpeg motion rendering. The current count is recorded in CI and should be checked there as tests evolve.

## Live GitHub validation

CI has succeeded on multiple commits. Provider probes and a complete GitHub production pilot are separate tests: their actual run conclusions, rather than unit-test results, establish whether the live API and remote production path work. Earlier diagnostic runs that were replaced/cancelled are not counted as successes.

## Ethiopia film

The curated script has 1,144 spoken words, five chapters and 20 narrative scenes. It explicitly ends at the November 2022 Pretoria agreement and does not present that endpoint as current conditions. A preflight visual search found 36 licensed asset records across 19 scenes before a broader final-scene search. Full-length production is a separate run and must pass its final quality gate before being described as complete.
