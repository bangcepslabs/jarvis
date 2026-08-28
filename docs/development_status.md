# JARVIS Development Status

Updated: 2026-08-27

## Continuous Voice (foreground)

The avatar client now has a separate `VoiceMode.continuous` path on
`feat/continuous-voice`. It uses the existing `record` plugin's 16-bit PCM
stream, a platform-independent 20 ms RMS VAD, 300 ms pre-roll, 240 ms speech
start qualification, 800 ms silence end, 280 ms minimum speech, 30 s maximum
utterance, and 12 s no-speech timeout. Noise floor calibration is collected
for the first 400 ms and the threshold is `max(0.06, noiseFloor + 0.025)`.

The existing one-shot WAV microphone flow is retained. Continuous mode stops
capture during STT/chat/TTS and playback, resets mouth output after TTS, waits
300 ms, then reacquires the microphone. Session generation and turn guards
ignore delayed callbacks from cancelled sessions and prevent duplicate turns.
Raw PCM is kept only in bounded pre-roll/current-utterance buffers and is not
logged, persisted, or added to memory.

- Continuous Conversation: IMPLEMENTED / UNIT TESTED
- VAD Runtime: PASS (Pixel 7 emulator: PCM capture, listening state, idle timeout, cancel)
- Continuous Voice E2E: NOT VERIFIED
- Multi-turn Continuous Voice: NOT VERIFIED (emulator speech input unavailable)

## Live2D Framing and Idle Life

The Ellen model keeps the existing loading, renderer, physics, lip-sync, and
overlay pipeline. The model projection is now a medium shot using height
`2.95f` and Y offset `-0.30f`: the full head remains visible with a small top
margin, the face sits above screen center, and the lower body remains covered
around the thigh/slightly-below-thigh area by the conversation UI.

Idle motion is explicitly configured to loop. The official Cubism eye-blink
effect is enabled for the model's four eye-blink parameters, and the official
breath effect is enabled for four available body/head parameters with subtle
weights. Physics remains applied after motion/effects, and mouth lip sync is
still applied afterward. Runtime logs confirmed `idleLoop=true`,
`eyeBlinkParams=4`, and `breathParams=4`; two emulator screenshots taken three
seconds apart had different SHA-256 hashes, confirming continuous animation.

The expression preview remains debug-only and the existing overlay/status UI
is retained. STT, chat, TTS, and lip-sync client code was not changed.

Presentation refinements completed on the current branch:

- Debug expression controls are now opt-in with
  `JARVIS_AVATAR_DEBUG_CONTROLS=true`; default builds hide them.
- The working Android Live2D composition path retains the existing surface
  configuration; opaque/alpha EGL variants were tested but hid the model.
  The legacy white platform-view background therefore remains a known visual
  limitation.
- Text input uses a denser layout while microphone and continuous controls
  remain available.
- Pixel 7 emulator confirmed the Live2D model renders with the final framing;
  no renderer crash was observed.
- Wake Word interface: IMPLEMENTED
- Porcupine: EXPERIMENTAL / DEFERRED
- Local Wake Word: PLANNED

Flutter verification on this branch: 30 tests passed and debug APK build
completed. `flutter analyze` reported only lint/info diagnostics. Root pytest
was not available in the active shell (`python` reported that `pytest` is not
installed).

## Avatar Presentation Polish

The `feat/avatar-presentation` branch keeps the validated Live2D projection
(`2.95f`, Y `-0.30f`) and idle pipeline unchanged. Header typography and safe
area padding are reduced, the text input uses a restrained dark surface, and
the microphone action is compact while retaining its existing tap semantics.
Continuous remains a secondary action and its ON indicator is shown only when
active. Expression controls remain hidden by default and are still available
with `JARVIS_AVATAR_DEBUG_CONTROLS=true`.

The Flutter scaffold is dark, but the Android platform-view surface still
renders white around the model on the Pixel 7 emulator. Translucent/opaque EGL
experiments hid the model, so no unsafe surface change was retained. Dark
background is therefore NOT VERIFIED and remains the next native composition
task.

## Current Voice Status

The Core voice pipeline has been validated on a Windows PC with a real headset.
The avatar client is outside the scope of this validation.

- Voice pipeline implementation: COMPLETE
- Real headset validation: COMPLETE
- Microphone recording: PASS
- Korean STT basic validation: PASS
- Groq/Qwen chat: PASS
- Supertonic 3 local TTS: PASS
- WAV playback: PASS
- PC voice round trip: PASS
- Last observed end-to-end response: 8.81 seconds
- Latest file-pipeline processing time: 13.29 seconds without playback

Warm latency observations with the server kept running:

```text
Run 1: STT 5.94s, Chat 2.92s, TTS 4.86s, total 13.73s (success)
Run 2: STT 6.35s, Chat 1.60s, TTS 0.64s, total 8.59s (Chat fallback after Router 400)
Run 3: STT 8.43s, Chat 2.85s, TTS 7.74s, total 19.01s (success)
```

TTS model reuse reduced the second TTS stage substantially. STT remained near
six to eight seconds and varies with audio/model processing. Response length
also affects TTS duration, so no optimization decision is being made yet.

Validated path:

```text
Microphone -> faster-whisper STT -> Groq/Qwen -> JARVIS Agent
    -> Supertonic 3 TTS -> Speaker
```

The validated input device was Windows device `2`, `Microphone (High Definition Audio Device)`.
The local configuration uses `STT_ENABLED=true` and `STT_LANGUAGE=ko`.
Secrets remain local and are not recorded in this document or application logs.

## Pending Validation

- [x] Real human Korean STT
- [x] PC headset voice round trip
- [ ] Korean sentence STT quality validation with several samples
- [ ] Voice tool-calling scenario
- [ ] Multi-turn voice conversation with the same conversation id
- [ ] Weather tool voice invocation
- [ ] Supertonic preferred voice selection
- [ ] End-to-end latency profiling across multiple turns
- [ ] Android physical-device voice round trip
- [x] Live2D model selection and compatibility gate
- [ ] Wake word

## Immediate Voice Scenarios

The weather scenarios have passed with text input as a transport proxy, while
the microphone versions remain pending. The text proxy selected
`get_current_weather` for turn 1 and `get_weather_forecast` for turn 2 while
preserving the Busan context under `voice-weather-test`.

### Scenario A: Weather Tool

Speak:

```text
JARVIS, tell me today's weather in Busan.
```

Expected path:

```text
Microphone -> STT -> Router -> Weather Tool -> Groq/Qwen
    -> TTS -> Speaker
```

Confirm STT transcription, actual weather-tool execution, natural final response,
and successful WAV playback.

### Scenario B: Multi-turn Forecast

Use one `conversation_id` for both turns:

```text
Turn 1: JARVIS, tell me today's weather in Busan.
Turn 2: What about tomorrow?
```

Confirm that the second turn uses the prior location context and selects the
forecast tool appropriately.

## Voice Client Observability

`scripts/jarvis_voice_client.py` reports these measurements after each successful
round trip:

```text
[voice]
recording_elapsed=...
stt_elapsed=...
chat_elapsed=...
tts_elapsed=...
processing_elapsed=...
playback_elapsed=...
total_elapsed=...
```

`processing_elapsed` covers STT, chat, and TTS requests. `total_elapsed` also
includes local playback when `--play` is used. Recording time is measured for
microphone input and is not included in the HTTP processing time.

Latest measured file-pipeline sample:

```text
stt_elapsed=5.20s
chat_elapsed=2.78s
tts_elapsed=5.31s
processing_elapsed=13.29s
total_elapsed=13.29s
```

The earlier real-headset run completed in 8.81 seconds including playback.

## Commands

Run from the repository root with the project virtual environment:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\jarvis_voice_client.py --list-devices
.venv\Scripts\python.exe scripts\jarvis_voice_client.py --mic --play --input-device 2
```

The Core server must be running at `http://127.0.0.1:8000`. The avatar client,
Live2D, wake word, streaming STT/TTS, WebSocket transport, model replacement,
and Docker configuration changes are intentionally excluded from this status.

## Live2D Integration Spike

The first Android integration spike keeps proprietary Cubism binaries local:

- Renderer abstraction: READY
- Placeholder renderer: PASS and remains the default
- Android PlatformView bridge: READY
- Model asset reference validation: PASS
- Official Cubism SDK/Core: PRESENT locally and wired through Gradle
- Android Framework/Core compile: PASS (local `:app:assembleDebug`)
- model3.json resource loader: IMPLEMENTED (moc3, textures, physics, idle motion)
- PlatformView OpenGL renderer: IMPLEMENTED
- Android model rendering: PASS (Pixel 7 Android emulator)
- Idle motion playback: PASS (Pixel 7 Android emulator)
- Physics: PASS (loaded and exercised during renderer smoke)
- Cubism expressions: PASS (`shuiyin` loaded from model3.json and applied through
  `CubismExpressionMotionManager`)
- Phone projection/scaling: PASS (Pixel 7 portrait framing adjusted to head,
  torso, and upper-leg emphasis)
- Live2D dark background: NOT VERIFIED (legacy PlatformView surface remains
  white despite native clear/background attempts)
- Eye blink: PASS (official Cubism eye-blink effect, four parameters)
- Flutter analyze: PASS
- Flutter test: PASS
- Flutter APK build: PASS (`flutter build apk --debug`)
- Android runtime smoke: PASS (Pixel 7 Android emulator)

The renderer can be selected with
`--dart-define=JARVIS_AVATAR_RENDERER=live2d`. On Android it creates the
`jarvis/live2d` PlatformView and passes the development model asset plus the
`idle` motion. The SDK is present locally and the native bridge now extracts the
Flutter asset tree, loads model3.json references, initializes Cubism, uploads
textures, and drives the OpenGL renderer. Runtime smoke passed on the Pixel 7
Android emulator.

The local development model is copied from the VTube Studio Workshop directory
to `clients/avatar_client/assets/avatars/development/ellen_workshop/`. All model
files are covered by the existing local-only ignore rule, and no Workshop model
or proprietary SDK binary is committed.

The official Java model-loading flow is based on `.model3.json` file references
and a `CubismUserModel`, as described in the [official Cubism Java model
manual](https://docs.live2d.com/en/cubism-sdk-manual/model-java/).

### Development Expression Comparison

The `shuiyin.exp3.json` expression is registered by the Ellen model3.json and
is available through the official expression manager. The development renderer
defaults to `shuiyin`; it can still be selected explicitly with
`--dart-define=JARVIS_LIVE2D_EXPRESSION=shuiyin`. On the Pixel 7 Android
emulator:

- Without `shuiyin`: `FREE MODEL` and the watermark text are visible.
- With `shuiyin`: `FREE MODEL` and the watermark text are not visible.
- Runtime log: `expression=shuiyin applied=true`.

The result was achieved without changing the model, textures, moc3, or
ArtMesh. `applyExpression(name)` starts the registered Cubism expression and
`removeExpression(name)` stops expression motions through the SDK manager.

### Lip Sync Audio Analysis

The renderer-independent Dart layer at
`clients/avatar_client/lib/features/avatar/lip_sync/` is IMPLEMENTED and unit
tested. It parses RIFF/WAVE chunks, supports PCM integer 16-bit mono/stereo
input, calculates 30 ms RMS frames, applies noise gating, normalization, and
attack/release smoothing, and exposes interpolated `mouthOpen` values through
`LipSyncEnvelope.valueAt(position)`. The output is clamped to `0.0..1.0` and
is ephemeral; raw audio and PCM samples are not logged or persisted.

Live2D Lip Sync Runtime: PASS on the Pixel 7 Android emulator. The Flutter
renderer sends normalized mouth values through `MethodChannel('jarvis/live2d')`.
The Android bridge queues updates on the GLSurfaceView render thread and the
model adapter applies `ParamMouthOpenY` after motion, expression, and physics
updates. Ellen's model-specific maximum is kept in the adapter as `2.1`.
During a real TTS playback, the normalized value changed from `0.0` to roughly
`0.145` and returned to `0.0` after completion; the app remained stable and
the audio playback path completed normally.
The development renderer accepts `JARVIS_LIVE2D_MOUTH_GAIN` in the `0.0..2.0`
range. The Android adapter applies this gain after normalization and clamps
the final Ellen parameter value to `2.1`; `1.5` was smoke-tested during the
current development run, but is not yet selected as a final tuned value.

### Lip Sync Playback Synchronization

`LipSyncPlaybackController` is IMPLEMENTED and UNIT TESTED. It receives a
playback source abstraction, subscribes to the source's actual position and
completion streams, maps positions through `LipSyncEnvelope.valueAt`, and
publishes a clamped `ValueNotifier<double>` mouth value. Start, completion,
stop, playback error, dispose, and replacement all reset the value to `0.0`.
The controller does not analyze WAV data again and has no Live2D or Android
dependency. `AvatarController` now analyzes the returned TTS WAV once and uses
the same `AudioPlayer` position/completion streams for playback synchronization.

No proprietary SDK files or local model files were committed. Eye blink and
state-to-motion mapping remain outside this phase.

Development expression preview is available only in debug Live2D builds. It
exposes the model-registered expressions and a clear action through the same
official Cubism expression manager bridge. The Pixel 7 preview screen loaded
without a crash; visual acceptance of each expression remains pending.

Wake Word is IMPLEMENTED as a foreground-only Porcupine adapter using
`porcupine_flutter 4.0.0`. It owns the microphone only while the avatar is
idle, stops before recording/STT/thinking/TTS, and re-arms after the command
returns to idle. Detection errors fall back to the existing manual microphone
flow. The AccessKey and custom Korean `.ppn`/`.pv` files are supplied locally
through `--dart-define` and are not committed. Runtime detection on the Pixel
7 remains NOT VERIFIED until the local key/model files and emulator microphone
are available.

Example development configuration:

```powershell
flutter run -d emulator-5554 `
  --dart-define=JARVIS_WAKE_WORD_ENABLED=true `
  --dart-define=JARVIS_PICOVOICE_ACCESS_KEY=<local-key> `
  --dart-define=JARVIS_WAKE_WORD_KEYWORD_ASSET=assets/wake_word/development/jarvis_ko.ppn `
  --dart-define=JARVIS_WAKE_WORD_MODEL_ASSET=assets/wake_word/development/porcupine_ko.pv
```

The Flutter client treats those values as Flutter asset lookup keys. Local
wake-word development assets are ignored by Git. No raw audio is logged,
stored, or uploaded by the detector.

### Conversation Context Budget

`ConversationContextManager` is IMPLEMENTED and UNIT TESTED on branch
`feat/context-budget`. It is called by `JarvisAgent` before provider calls and
uses a replaceable lightweight token estimate, configurable total/reserve
budgets, recent turn selection, memory selection, and compact observability
metrics. The current user message and system prompt are retained; tool-related
messages are selected as part of their conversation turn. Conversation storage
remains in-memory.

### Conversation Summarization

`ConversationSummarizer` and `ConversationSummaryStore` extend the Context
Budget layer. When newly dropped turns reach the configured threshold, the
existing provider abstraction performs a best-effort incremental summary. Each
conversation tracks summarized turn keys in memory, so the same turn is not
summarized twice. Summary is lower priority than recent raw turns and never
replaces the current message or system/safety prompt.

Conversation Summarization: IMPLEMENTED / UNIT TESTED
Summary persistence: NOT IMPLEMENTED (in-memory only)
Summary → Authorization: NOT ALLOWED
Summary → Persistent Memory automatic promotion: NOT IMPLEMENTED

### LLM Prompt Token Calibration

`OpenAICompatibleProvider` remains the source of provider-reported usage. The
agent records a best-effort comparison between the existing heuristic estimate
of all submitted messages plus tool schemas and `usage.prompt_tokens` from the
provider response. In-memory aggregates expose sample count, average ratio,
and minimum/maximum ratio; missing usage is recorded as unavailable and never
blocks a chat response. Calibration is observability-only: it does not change
context selection, budgets, routing, authorization, or safety behavior.

LLM Prompt Calibration: IMPLEMENTED / UNIT TESTED
Adaptive budget changes: NOT IMPLEMENTED (measure only)
Raw prompt/memory/tool result logging: NOT ALLOWED

### Live2D Aspect Ratio

Live2D model framing remains uniform and viewport aspect correction is applied
through a separate projection matrix. Diagnostic viewport, canvas, scale, and
projection values are logged only during initialization or resize.

Live2D Aspect Ratio: IMPLEMENTED / NOT RUNTIME VERIFIED
