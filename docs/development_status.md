# JARVIS Development Status

Updated: 2026-08-27

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
- Eye blink: NOT IMPLEMENTED in this phase
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

Live2D Lip Sync Runtime: NOT YET CONNECTED. No `ParamMouthOpenY`, Android
bridge, Cubism parameter update, or render-loop change was made in this phase.

### Lip Sync Playback Synchronization

`LipSyncPlaybackController` is IMPLEMENTED and UNIT TESTED. It receives a
playback source abstraction, subscribes to the source's actual position and
completion streams, maps positions through `LipSyncEnvelope.valueAt`, and
publishes a clamped `ValueNotifier<double>` mouth value. Start, completion,
stop, playback error, dispose, and replacement all reset the value to `0.0`.
The controller does not analyze WAV data again and has no Live2D or Android
dependency. The current `AvatarController` playback is not wired to this
controller yet; that integration remains part of the next Live2D step.

No proprietary SDK files or local model files were committed. Live2D runtime
lip sync, eye blink, wake word, and state-to-motion mapping remain outside this
phase.

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

### Conversation Persistence

Conversation history is persisted through `SQLiteConversationStore` and
conversation summaries through `SQLiteConversationSummaryStore`, using the
same `JARVIS_DB_PATH`/`MEMORY_DATABASE_PATH` SQLite file as long-term Memory.
Messages use deterministic per-conversation sequence ordering. Summary text,
summarized turn keys, and `summarized_through_sequence` are persisted so a Core
restart with the same `conversation_id` can recover context and avoid duplicate
summarization.

Conversation History: PERSISTENT / UNIT TESTED
Conversation Summary: PERSISTENT / UNIT TESTED
Core Restart Context Recovery: IMPLEMENTED / UNIT TESTED
PendingAction Persistence: NOT IMPLEMENTED (runtime-only by policy)
Summary -> Authorization: NOT ALLOWED
Summary -> Persistent Memory automatic promotion: NOT IMPLEMENTED

### Natural Conversation Personalization

The stable JARVIS identity remains in the base system prompt while a bounded,
deterministic style hint adapts to recent user turns. Chat requests may specify
`response_mode` as `text` or `voice`; voice mode requests concise, conclusion-
first spoken responses. Relevant long-term memory is ranked locally in SQLite
by token overlap, key/category matches, recency, and explicit source, with a
small retrieval budget. Current conversation context remains higher priority
than persistent memory, and memory/Persona/context never grant authorization.

Natural Conversation Personalization: IMPLEMENTED / UNIT TESTED
Vector database, embeddings, and model fine-tuning: NOT IMPLEMENTED
