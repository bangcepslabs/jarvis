# Production Core Deployment

JARVIS Core is the only Python service. Windows, Android, and the future
Raspberry Pi client call it over HTTP; they do not run the Core or carry its
LLM/STT/TTS models.

## Ubuntu host

Required runtime files are `app/`, `pyproject.toml`, `.env`, and the persistent
data/model directories. Keep secrets in `.env`, never in Git.

For a native install:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For automatic startup, copy `deploy/jarvis-core.service.example` to
`/etc/systemd/system/jarvis-core.service`, adjust the user and paths, then run
`systemctl enable --now jarvis-core`.

## Persistent paths

The native defaults are `data/jarvis.db` and the configured model paths.
Docker Compose mounts these paths:

| Host | Container | Purpose |
|---|---|---|
| `${JARVIS_DATA_HOST_PATH:-./data}` | `/app/data` | SQLite and data |
| `${JARVIS_TTS_MODEL_HOST_PATH:-./data/models/tts}` | `/app/data/models/tts` | Supertonic 3, read-only |
| `${JARVIS_WHISPER_HOST_PATH:-./data/models/whisper}` | `/app/data/models/whisper` | Faster-Whisper cache |
| container tmpfs | `/tmp/jarvis` | transient STT files |

Do not commit model binaries or audio. Back up the SQLite host directory and
manage `.env` separately.

## Authentication and LAN

Set the following in the server `.env` for production LAN use:

```dotenv
JARVIS_AUTH_ENABLED=true
JARVIS_CLIENT_TOKEN=<random-long-token>
STT_ENABLED=true
TTS_ENABLED=true
```

`/health` is public for readiness checks. `/api/chat`,
`/api/stt/transcribe`, and `/api/tts/synthesize` require
`Authorization: Bearer <JARVIS_CLIENT_TOKEN>` when authentication is enabled.
This client authentication is independent from READ_ONLY/WRITE/DANGEROUS tool
authorization.

Allow TCP 8000 only from the private LAN with UFW. Do not port-forward 8000 to
the public Internet. For remote access use Tailscale or a TLS reverse proxy.

## Clients

Windows:

```powershell
$env:JARVIS_CORE_URL="http://<ubuntu-ip>:8000"
$env:JARVIS_CLIENT_TOKEN="<same-token>"
python scripts/jarvis_voice_client.py --mic --play
```

Android receives the same values through Flutter build definitions:

```bash
flutter build apk --dart-define=JARVIS_CORE_URL=http://<ubuntu-ip>:8000 --dart-define=JARVIS_CLIENT_TOKEN=<same-token>
```

Do not put Groq, Tavily, or other provider keys in either client. Live2D
Cubism SDK/model assets remain Android build inputs only.

## Container limitations

The image does not contain model binaries. Mount them before enabling STT/TTS.
The Docker socket is intentionally not mounted by default; enabling it grants
the container powerful host control and should be limited to installations
that explicitly need Docker tools. Conversation context and summaries remain
in memory across requests but are lost on Core restart; long-term Memory is
SQLite-backed.
