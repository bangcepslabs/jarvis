# Production Core Deployment

JARVIS Core is the only Python service. Windows, Android, and the future
Raspberry Pi client call it over HTTP; they do not run the Core or carry its
LLM/STT/TTS models.

## Ubuntu host

Required runtime files are `app/`, `pyproject.toml`, and persistent data/model
directories. Keep secrets in ignored environment files, never in Git. Local
development continues to load `.env`; production systemd loads
`.env.production` explicitly through `EnvironmentFile`.

If a server checkout previously used `.env` for production values, do not copy
that file through Git or expose its contents. Create `.env.production` manually
from `.env.example`, enter the production values yourself, and restore `.env`
from the safe development template only when that checkout is used for local
development or tests. systemd always uses `.env.production`, never `.env`.

For a native install:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For a production server, create the secret file without committing it:

```bash
cp .env.example .env.production
chmod 600 .env.production
openssl rand -hex 32  # use the output for JARVIS_CLIENT_TOKEN
```

Set at least the production values below. `JARVIS_TTS_MODEL_DIR` is the
recommended deployment name; `TTS_MODEL_DIR` remains compatible.

```dotenv
APP_ENV=production
JARVIS_AUTH_ENABLED=true
JARVIS_CLIENT_TOKEN=<generated-token>
LLM_PROVIDER=openai
LLM_API_KEY=<provider-key>
LLM_BASE_URL=https://api.groq.com/openai/v1
STT_ENABLED=true
STT_CPU_THREADS=6
TTS_ENABLED=true
JARVIS_TTS_MODEL_DIR=data/models/tts/supertonic-3
STT_PRELOAD=true
TTS_PRELOAD=true
VOICE_LATENCY_METRICS=true
```

For automatic startup, copy `deploy/jarvis-core.service.example` to
`/etc/systemd/system/jarvis-core.service`, replace `<USER>`, `<GROUP>`, and
`<PROJECT_DIR>`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-core
sudo systemctl status jarvis-core
journalctl -u jarvis-core -f
```

`WorkingDirectory` must be the repository root so relative SQLite and model
paths work. Run the service as the normal deployment user (and ensure it has
any required Docker group access), not root.

To update:

```bash
cd <PROJECT_DIR>
git pull
.venv/bin/pip install -e .
sudo systemctl restart jarvis-core
curl http://127.0.0.1:8000/health
```

Preload trades slower startup and higher resident RAM for a faster first voice
turn. A preload failure is isolated and lazy loading remains available.

## Test isolation

`pytest` sets its own process-level test configuration before application
imports: mock LLM, disabled client auth, disabled web search, and disabled model
preload. These values override any repository `.env` or systemd production
environment, so the normal test suite never calls Groq or Tavily. Provider smoke
tests remain opt-in scripts, not default pytest behavior.

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
persistently in SQLite across Core restarts. PendingAction state remains
runtime-only and is intentionally not restored from conversation records.
