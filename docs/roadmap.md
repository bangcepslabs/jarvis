# Roadmap

## v0.1 Core Chat

- [x] FastAPI root, health, and chat endpoints
- [x] Provider abstraction and offline mock provider
- [x] Agent and application-service separation
- [x] Configuration, logging, Docker, tests, and documentation

## v0.2 Tool Calling

- [x] Define tool-call request, metadata, and result models
- [x] Add current-time and system-status read-only tools
- [x] Validate tool parameters at the execution boundary
- [x] Enforce READ_ONLY execution and log tool activity
- [x] Return tool activity transparently to the API client
- [x] Add registry, tool, agent, and safety tests

## v0.2.5 Native LLM

- [x] Common LLM response and tool-call models
- [x] OpenAI-compatible concrete Provider adapter
- [x] Native Tool Calling and ToolResult feedback
- [x] Provider timeout and safe provider error handling
- [x] Native Tool Calling tests without external API access

## v0.3 Server / Docker

- [x] List Docker containers and states (READ_ONLY)
- [x] Inspect one container status (READ_ONLY)
- [x] Inspect bounded container logs (READ_ONLY)
- [x] Handle Docker daemon unavailable and container-not-found safely
- [ ] Add restart confirmation workflow
- [ ] Persist auditable tool-execution logs

## v0.3.5 Action Confirmation

- [x] Generic PendingAction model and in-memory store
- [x] Approval, rejection, expiration, and one-shot authorization
- [x] WRITE/DANGEROUS runtime enforcement
- [x] Controlled `restart_container` Docker Tool
- [x] Confirmation and duplicate-execution tests

## v0.4 Memory

- [x] Implement SQLite memory store
- [x] Store preferences, facts, projects, and environment entries
- [x] Search relevant context with bounded retrieval
- [x] Explicit save, update, delete, and search commands
- [x] Secret-memory guard and Memory/Safety separation
- [ ] Define broader retention and deletion policy

## v0.4.5 Conversation Context

- [x] Conversation message model and in-memory store
- [x] Recent message and conversation isolation support
- [x] Message-count and character-count context limits
- [x] LLM context integration and regression tests

## v0.4.6 Persona / Natural Dialogue

- [x] JARVIS personal-assistant identity
- [x] Natural conversation and response-style guidance
- [x] Memory and conversation trust boundaries
- [x] Real-time information/tool-use policy
- [x] Persona safety regression tests
- [x] Package metadata alignment

## v0.4.7 Weather / Daily Information

- [x] Weather provider abstraction and Open-Meteo integration
- [x] Geocoding and default-location fallback
- [x] Current weather and bounded forecast tools
- [x] Safe provider error translation and weather tests
- [x] Optional Groq/Qwen OpenAI-compatible configuration

## v0.4.7.1 LLM Usage / Context Observability

- [x] Provider-independent token usage metadata
- [x] Rate-limit header parsing and safe 429 mapping
- [x] No automatic retry
- [x] Context and tool-schema size metrics
- [x] Usage/rate-limit regression tests

## v0.4.8 Lightweight Tool Router / Web Search / News

- [x] Semantic routing with a provider-independent route decision
- [x] Registry-owned routing hints
- [x] JSON route validation and unknown-tool rejection
- [x] Candidate filtering to NONE or one Tool schema
- [x] Specific single-tool `tool_choice`
- [x] Router usage/rate-limit observability
- [x] Safety regression coverage
- [x] Real Qwen routing validation (partial due to rate-limit budget)
- [x] SearchProvider abstraction and Tavily adapter
- [x] `web_search` and `search_news` READ_ONLY tools
- [x] Source metadata, publication date, and retrieved timestamp
- [x] External-content trust boundary
- [x] Search disabled-mode and normalization tests

## v0.4.9 Adaptive Memory

- [x] Add opt-in provider-independent MemoryCurator with SAVE/UPDATE/IGNORE decisions
- [x] Preserve explicit memory precedence, secret blocking, and best-effort failure isolation
- [x] Track explicit versus adaptive memory source metadata

## v0.5.0 Local STT

- [x] STTProvider and TranscriptionResult contracts
- [x] Lazy faster-whisper CPU/int8 provider
- [x] Multipart `/api/stt/transcribe` endpoint
- [x] File-size, timeout, concurrency, and no-speech handling
- [x] Privacy-safe logging and temporary-file cleanup
- [x] Mock/unit/API regression tests
- [ ] Real local audio smoke (requires a supplied speech sample)

## v0.5.1 Local TTS

- [x] sherpa-onnx Python 3.14 compatibility gate
- [x] Official Supertonic 3 OpenRAIL-M artifact validation
- [x] Provider-independent TTSService and WAV result
- [x] CPU synthesis, lazy loading, timeout, and concurrency guard
- [x] Multipart-independent binary `/api/tts/synthesize` response
- [x] Privacy-safe handling and mock regression tests
- [x] Production API smoke with Korean and mixed text
- [x] Cold/warm performance and model reuse measurement
- [ ] Human listening validation

## v0.5.2 PC Voice Client

- [x] Standalone HTTP-only text/file/microphone client.
- [x] Existing STT, Chat, and TTS endpoint composition with optional local playback.
- [x] Explicit WAV saving, conversation reuse, isolated failures, and mock regression tests.
- [ ] Real microphone/headset and human listening validation.

## v0.6 Wake Word

- [ ] Evaluate wake-word engine
- [ ] Detect voice activity
- [ ] Forward recognized commands to core

## v0.7 External Integrations

- [ ] Define OAuth credential storage strategy
- [ ] Add Home Assistant adapter
- [ ] Add calendar and email read-only adapters

## v0.8 Automation / Scheduler

- [ ] Model schedules and triggers
- [ ] Add condition evaluation
- [ ] Add notification delivery abstraction

## v0.9 Security & Permissions

- [ ] Add API authentication
- [ ] Implement user confirmations
- [ ] Add authorization and audit log policy

## v1.0 Proactive JARVIS

- [ ] Detect server and container incidents
- [ ] Notify on capacity thresholds
- [ ] Deliver schedule and priority-mail reminders
- [ ] Support user-configured proactive rules
