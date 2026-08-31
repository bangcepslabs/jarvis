# Wake-word development models

The Android runtime uses the official openWakeWord v0.5.1 ONNX exports during
local device validation. The source is `dscripka/openWakeWord` release assets:

- `melspectrogram.onnx`
- `embedding_model.onnx`
- `hey_jarvis_v0.1.onnx`

The wrapper configuration uses `hey_jarvis.onnx`; this is an exact local copy
of `hey_jarvis_v0.1.onnx`, not a converted or modified model. All `.onnx`
files in the Android development asset directory are ignored and must not be
committed.

The current local files were downloaded from:

```text
https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx
https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx
https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx
```
