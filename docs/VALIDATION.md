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

## Live free-model API comparison

A real, tiny JSON request was sent through GitHub Actions using the repository's GEMINI_API secret. Request starts were separated by at least 65 seconds. Results:

| Model | Actual result | Request time |
|---|---|---:|
| Gemini 3.8 Flash | HTTP 504 deadline exceeded | 43.12 s |
| Gemini 3.5 Flash-Lite | Successful JSON output | 0.66 s |
| Gemini 3.1 Flash-Lite | Successful JSON output | 7.19 s |

These are single tiny probes, not a general model-quality benchmark. They establish access and motivated choosing 3.5 Flash-Lite as the default. The full research/script/revision integration is tested separately.

## Live GitHub validation

CI has succeeded on multiple commits. Provider probes and a complete GitHub production pilot are separate tests: their actual run conclusions, rather than unit-test results, establish whether the live API and remote production path work. Earlier diagnostic runs that were replaced/cancelled are not counted as successes.

## Ethiopia film

The completed [Ethiopia production](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42305472051) passed its final quality gate. [Download the upload package](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42305472051/artifacts/13546308132) within the 14-day artifact retention period.

- 1,144 spoken words, five chapters, 20 scenes; Warguy narration.
- 518.245 seconds total (8:38), including 84 seconds of visible attribution credits; 434.224 seconds narration.
- H.264, 1920×1080, 30 fps, yuv420p; stereo AAC.
- 31 credited visual sources, with no missing-image map fallbacks. Deliberate geographic reference maps remain labeled as present-day boundaries.
- Final encoded audio: −16.01 LUFS, −2.85 dBTP. Full decode, duration and black-interval checks passed.
- Minimum automated transcript coverage: 0.8966. All five chapter checks passed; normalized spoken-year comparisons found no date mismatches across the 20 scenes. Automated transcription is imperfect for proper names and does not certify every pronunciation.
- Final contact sheet inspected. Modern landscape views are identified as geographic references. Treaty interpretation and the 1991–1993 transition use reviewed explanatory graphics.

The film explicitly ends at the November 2022 Pretoria agreement and does not present that endpoint as current conditions. The script is a curated, source-linked episode, not claimed to be live Gemini output. It has not been uploaded to YouTube.

## Completed live integration and refinements

Both Gemini 3.5 Flash-Lite and 3.1 Flash-Lite completed actual research/script/revision/asset integration on the same short brief. The outputs contained 256 and 304 words respectively. Summed token use was 14,761 and 17,791 respectively; differing source results and one trial per model prevent broad quality conclusions.

The [long-script integration](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42303532786) also passed: an eight-minute target produced 952 words across 15 scenes and all five chapters, using exactly ten generation calls. The minimum observed generation-start interval was 65.0001 seconds. This tests the actual free-key chapter pipeline independently from the curated Ethiopia episode.

A second local comparison after refinement produced passing draft/standard/cinematic films in 25.88/101.62/98.17 seconds, at 7.38/41.19/38.10 MB respectively. Unlike the first iteration, no competing TTS process was running; the timing difference therefore cannot be attributed entirely to code changes. The [hosted comparison](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42302043137) also passed for all three profiles. [Download those comparison videos](https://github.com/justsomeoneretarded/History-of-X/actions/runs/42302043137/artifacts/13543993587).

Further corrections replaced irrelevant search results with exact reviewed curation, bundled 30 licensed Ethiopia photographs with checksums, bound curation to the exact script, refreshed partial visual caches, and labeled modern geographic views. The final local and hosted CI suites passed all 35 tests. No numerical quality multiplier is claimed.
