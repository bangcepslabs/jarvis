# JARVIS Avatar Client

Flutter-based visual and voice client for JARVIS Core. The client is independent
from the Python app and communicates only through HTTP.

## Run

From the repository root:

```powershell
cd clients/avatar_client
flutter pub get
flutter run -d android --dart-define=JARVIS_CORE_URL=http://10.0.2.2:8000
```

The default URL is `http://127.0.0.1:8000`. On an Android emulator, use
`10.0.2.2`; on a physical Android device, use the PC's LAN IP, for example
`http://192.168.0.10:8000`. The Core server must be reachable on the network.

## Architecture

`main.dart` wires `ClientConfig`, `JarvisApiClient`, and `AvatarController`.
The controller owns the foundation state machine: idle -> listening -> thinking
-> speaking -> idle, with network/audio failures mapped to error. The current
renderer is a placeholder interface; Live2D is intentionally not integrated.

The API client uses the existing contracts:

- `POST /api/stt/transcribe` multipart field `file` (WAV, mono, 16 kHz when supported)
- `POST /api/chat` JSON `{message, conversation_id}`
- `POST /api/tts/synthesize` JSON `{text, language}` returning `audio/wav`

A conversation id is created once per client session and reused for chat turns.
No Core Python modules are imported, no provider secrets are shipped, and the
client never confirms or executes pending actions automatically.

## Android permissions and assets

Only `RECORD_AUDIO` is declared. Contacts, location, camera, and unrestricted
storage are not requested. Development avatar assets under
`assets/avatars/development/` are local-only and ignored by Git. Live2D model
compatibility and adapter mapping are future work.

## Checks

```powershell
flutter analyze
flutter test
```
