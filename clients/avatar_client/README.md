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

`main.dart` wires `ClientConfig`, `JarvisApiClient`, `AvatarController`, and the
renderer selection. The controller owns the foundation state machine:
idle -> listening -> thinking -> speaking -> idle, with network/audio failures
mapped to error. The renderer boundary supports `placeholder` and an Android
`live2d` PlatformView bridge.

The default renderer is the existing Placeholder renderer. Select the Live2D
spike with:

```powershell
flutter run -d android `
  --dart-define=JARVIS_AVATAR_RENDERER=live2d `
  --dart-define=JARVIS_CORE_URL=http://10.0.2.2:8000
```

For the development-only `shuiyin` expression comparison, add:

```powershell
flutter run -d android `
  --dart-define=JARVIS_AVATAR_RENDERER=live2d `
  --dart-define=JARVIS_CORE_URL=http://10.0.2.2:8000 `
  --dart-define=JARVIS_LIVE2D_EXPRESSION=shuiyin
```

Without `JARVIS_LIVE2D_EXPRESSION`, no expression is applied. The Android
bridge loads expression names and files from the model3.json `Expressions`
section and applies them through the official Cubism expression manager.

The bridge passes the model asset and `idle` motion to Android. The official
Cubism Java Framework and Core binaries are installed locally under
`android/live2d_sdk/`; no proprietary SDK binaries are included in Git.

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
`assets/avatars/development/` are local-only and ignored by Git. The development
model is under `assets/avatars/development/ellen_workshop/`; its model3.json,
moc3, textures, physics, CDI, expressions, and idle motions are present and the
model references resolve correctly. Unicode filenames are intentionally kept as
provided by the source model.

The official Cubism SDK/Core is also local-only under `android/live2d_sdk/` and
must be obtained through Live2D's official SDK distribution and license terms.
The current spike does not implement lip sync, wake word, or state-to-motion
mapping. The official Framework module and Core AAR are wired
into the local Android build. The native view reads Flutter asset lookup keys
through `AssetManager`, copies the model tree to the app cache while preserving
relative paths, then loads model3.json and its moc3, textures, physics, idle
motion, and registered expressions through Cubism before rendering with
OpenGL. The `shuiyin` expression was smoke-tested on the Pixel 7 Android
emulator: it removes the visible `FREE MODEL`/watermark overlay without any
texture, moc3, or ArtMesh modification.

## Checks

```powershell
flutter analyze
flutter test
```

For the Android Live2D runtime gate, a connected emulator or physical device is
required. The debug APK build and Pixel 7 emulator rendering smoke test pass.
