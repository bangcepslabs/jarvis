# Development wake-word assets

Place these deployment-only files here for local Android inference:

- `melspectrogram.onnx`
- `embedding_model.onnx`
- `hey_jarvis.onnx`

The model binaries are intentionally not committed. The application reports
`WakeWordUnavailable` and keeps manual microphone recording available until all
three files exist.
