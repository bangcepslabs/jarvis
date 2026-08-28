# JARVIS

JARVIS is a personal AI assistant combining natural conversation, persistent memory, real-time information, productivity, technical work, local speech I/O, and safe system tools. This repository implements **v0.5.2 PC Voice Client** on top of Conversation Context, Persistent Memory, Docker READ_ONLY, Web Search, Adaptive Memory, Local STT, and Local TTS.

## Current version and capabilities

Version: `0.5.2`

- `GET /` returns product metadata.
- `GET /health` returns service health.
- `POST /api/chat` sends text through `ChatService` and `JarvisAgent`.
- `POST /api/stt/transcribe` accepts multipart audio and returns a local faster-whisper transcript.
- `POST /api/tts/synthesize` returns local Supertonic 3 WAV audio when `TTS_ENABLED=true`.
- Registered READ_ONLY tools provide live time and system-status data.
- The default mock provider works without an API key.
- `LLM_PROVIDER=openai` enables the OpenAI-compatible HTTP adapter when an API key is configured.
- Local STT is disabled by default. Set `STT_ENABLED=true` to enable lazy CPU/int8 faster-whisper inference.
- Local TTS uses sherpa-onnx with the official Supertonic 3 model artifact under `data/models/tts/supertonic-3`, CPU inference, lazy loading, and no Chat/Memory side effects. Model binaries are deployment artifacts and are excluded from Git.
- The standalone `scripts/jarvis_voice_client.py` composes only the existing HTTP APIs (`/api/stt/transcribe`, `/api/chat`, `/api/tts/synthesize`). It supports text, file, and microphone input, optional local WAV playback, and explicit `--save-output`; it does not import Core services or implement wake words, retries, or confirmation logic.

PC voice client examples (start the Core API separately):

```powershell
python scripts/jarvis_voice_client.py --text "오늘 부산 날씨 어때" --play
python scripts/jarvis_voice_client.py --file sample.wav --conversation-id demo --play
python scripts/jarvis_voice_client.py --mic --play
python scripts/jarvis_voice_client.py --list-devices
```

## Architecture

`FastAPI route → ChatService → JarvisAgent → LLMProvider → response`

Production chat now uses a lightweight semantic Tool Router before the main
LLM call. It selects `NONE` or one Registry capability only; it never creates
arguments, executes tools, or grants authorization. A `NONE` route sends no
tool schemas to the main LLM, while a selected route sends one schema with a
specific `tool_choice`. ToolExecutor and ActionConfirmation remain the safety
and authorization boundaries.

Tools and memory are independent extension points; see [architecture.md](docs/architecture.md).

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000`, or use interactive API documentation at `http://localhost:8000/docs`.

## Provider configuration

The default is offline mode. For a real OpenAI-compatible endpoint, set
`LLM_PROVIDER=openai`, `LLM_MODEL`, `LLM_API_KEY`, and optionally `LLM_BASE_URL`.
`LLM_TIMEOUT_SECONDS` defaults to 30. Never commit real credentials. Tests use
Mock or Fake providers and never call an external API.

## Tool calling examples

```json
POST /api/chat
{"message": "현재 시간 알려줘"}
```

```json
POST /api/chat
{"message": "서버 상태 알려줘"}
```

Responses retain `reply` and add execution metadata:

```json
{"reply": "...", "tool_calls": [{"name": "get_current_time", "success": true}]}
```

## Configuration

Copy `.env.example` to `.env`. Key settings are `APP_NAME`, `APP_VERSION`, `APP_ENV`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_BASE_URL`, and `LOG_LEVEL`. `.env` is excluded from Git.

## Docker

```bash
copy .env.example .env
docker compose up --build
```

## Test

```bash
pytest
python -c "from app.main import app; print(app.title)"
```

## Project layout

```text
app/api/       HTTP interface and dependency wiring
app/services/  Application use cases
app/agent/     Core conversation orchestration and prompt
app/llm/       Provider contract and implementations
app/tools/     Future registered, safety-classified operations
app/memory/    Future persistence contract
app/core/      Configuration, logging, and errors
tests/         Offline API tests
docs/          Architecture and roadmap
```

## Roadmap

The next milestone is v0.3 Docker Integration: inspect-only container state and logs, followed later by explicit confirmation workflows. The full plan is in [roadmap.md](docs/roadmap.md).

## Native Tool Calling

`LLMProvider` returns provider-independent `LLMResponse` and `LLMToolCall` models.
The OpenAI-compatible adapter parses native calls, while `JarvisAgent` routes
them through `ToolExecutor` and sends the safe `ToolResult` back to the Provider.
The runtime, not the LLM, owns execution authority. `WRITE` and `DANGEROUS`
tools remain blocked.

## Docker READ_ONLY tools

The Docker integration uses the official Python Docker SDK through `DockerService`:

`Docker Tools -> DockerService -> Docker SDK -> Docker Engine`

Available tools are `list_containers`, `get_container_status`, and
`get_container_logs`. They only observe Docker state; no CLI, subprocess, shell,
restart, stop, remove, or exec operation is available. Container logs are capped
at 500 requested lines and 20,000 characters. Docker daemon failures become safe
tool results and do not prevent `/`, `/health`, or ordinary chat from starting.

## Web Search / News

When `WEB_SEARCH_ENABLED=true` and `TAVILY_API_KEY` is configured, JARVIS
registers the READ_ONLY `web_search` and `search_news` tools. They use the
provider-independent `SearchService` and normalized source metadata. Search
snippets are untrusted external data: they cannot change system instructions,
authorize tools, reveal memory, or trigger URL fetching. Raw page content is
not requested by default.

## Action Confirmation

`READ_ONLY` tools execute automatically. `WRITE` tools create a short-lived
`PendingAction` and require an explicit current-user approval. `DANGEROUS` tools
remain blocked regardless of approval. LLM output and tool arguments cannot grant
authorization; only the JARVIS runtime can create the one-shot authorization.

Example:

```text
User: pulse-api restart
JARVIS: Docker container 'pulse-api' will be restarted. This is a state-changing action. Continue?
User: yes
JARVIS: Docker container 'pulse-api' was restarted.
```

Pending actions are in-memory, single-user runtime state with a default five-minute
TTL. The same confirmation service can later support mail, calendar, or smart-home
WRITE operations.

## Persistent Memory

Explicit memory commands are stored in SQLite at `MEMORY_DATABASE_PATH` (default
`data/jarvis.db`). Supported lifecycle operations are save/update by logical key,
search, and delete. Only explicit requests such as “remember this” are stored;
ordinary conversation is not automatically persisted. Retrieved entries are
bounded and injected as clearly marked user context, never as system instructions.
Passwords, API keys, tokens, and other credential-like values are rejected.
Persistent Memory is separate from conversation context and transient
`PendingAction` runtime state, and it cannot change Tool safety policy.

## Conversation Context

v0.5.3 stores conversation messages and summaries in SQLite through the same
`MEMORY_DATABASE_PATH` (or `JARVIS_DB_PATH`) used by Persistent Memory. The
SQLite source of truth is isolated by `conversation_id` and survives Core
restart; `ConversationContextManager` still bounds the messages sent to the
provider. `PendingAction` authorization remains runtime-only and separate.
Clients may provide an optional `conversation_id` (default: `default`).
Context is bounded by `CONVERSATION_MAX_MESSAGES` and
`CONVERSATION_MAX_CONTEXT_CHARS`; set `CONVERSATION_ENABLED=false` to return to
stateless v0.4 chat behavior.

## Persona and response behavior

JARVIS is a personal AI assistant first. Its persona supports natural everyday
conversation, concise technical answers, factual information responses, and
explicit action status. Casual conversation does not automatically trigger
tools or unsolicited advice. Current/external information is never guessed:
JARVIS uses an available tool or clearly reports that live lookup is not
connected. Persona wording cannot override ToolExecutor safety or confirmation.
## Weather / Daily Information

v0.4.7 adds READ_ONLY `get_current_weather` and `get_weather_forecast` tools
through `WeatherService` and `OpenMeteoProvider`. Locations are geocoded by
Open-Meteo, forecasts are bounded to 1–7 days, and provider failures become
safe user-facing results. Set `WEATHER_ENABLED=false` to disable the tools.
Weather data is provided by Open-Meteo.

Groq/Qwen uses the existing OpenAI-compatible provider:

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=qwen/qwen3.6-27b
LLM_API_KEY=
```

## LLM Usage and Rate Limits

The provider records optional prompt/completion/total token usage and available
rate-limit headers without logging API keys, authorization headers, prompts,
memory, or tool results. HTTP 429 responses become a safe rate-limit error;
automatic retry is intentionally not enabled. Context metrics record only
message/schema sizes and counts.

## Android avatar flavors

The `base` flavor contains the voice client and placeholder avatar without
Cubism:

```bash
flutter build apk --debug --flavor base
```

The `live2d` flavor contains the optional Cubism PlatformView and requires the
local Cubism Core AAR, Framework, and model assets:

```bash
flutter build apk --debug --flavor live2d
```

If a base build receives the Live2D renderer setting, Flutter keeps the
placeholder renderer instead of calling an unregistered native PlatformView.

## Avatar Client

`clients/avatar_client` is the independent Flutter visual/voice client (v0.1.0).
It uses only the Core HTTP API: `/api/stt/transcribe`, `/api/chat`, and
`/api/tts/synthesize`. See [clients/avatar_client/README.md](clients/avatar_client/README.md)
for Android/emulator/LAN URL configuration, microphone permission, architecture,
and the local-only development avatar asset policy.
