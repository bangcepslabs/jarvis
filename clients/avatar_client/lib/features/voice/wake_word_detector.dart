/// Client-side wake-word boundary. A concrete engine can be added without
/// changing the STT, chat, TTS, or avatar layers.
abstract interface class WakeWordDetector {
  Stream<WakeWordEvent> get events;
  Future<void> start();
  Future<void> stop();
  void dispose();
}

sealed class WakeWordEvent {
  const WakeWordEvent();
}

final class WakeWordDetected extends WakeWordEvent {
  const WakeWordDetected(this.phrase);
  final String phrase;
}

final class WakeWordError extends WakeWordEvent {
  const WakeWordError(this.message);
  final String message;
}
