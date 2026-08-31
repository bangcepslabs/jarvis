import 'dart:async';

typedef WakeWordCallback = FutureOr<void> Function();

enum WakeWordStatus { disabled, unavailable, listening, paused, error }

/// Boundary for a local wake-word engine. Implementations must not upload audio.
abstract interface class WakeWordEngine {
  bool get isAvailable;
  Future<void> start(WakeWordCallback onDetected);
  Future<void> pause();
  Future<void> resume();
  Future<void> stop();
  Future<void> dispose();
}

/// Safe default until a real keyword model and engine are configured.
final class UnavailableWakeWordEngine implements WakeWordEngine {
  const UnavailableWakeWordEngine();
  @override bool get isAvailable => false;
  @override Future<void> dispose() async {}
  @override Future<void> pause() async {}
  @override Future<void> resume() async {}
  @override Future<void> start(WakeWordCallback onDetected) async {}
  @override Future<void> stop() async {}
}

/// Owns wake-word lifecycle independently from AvatarState and audio turns.
class WakeWordController {
  WakeWordController({required this._engine, required this._onDetected});
  final WakeWordEngine _engine;
  final WakeWordCallback _onDetected;
  WakeWordStatus status = WakeWordStatus.disabled;
  bool enabled = false;
  int _generation = 0;
  bool _disposed = false;
  bool get isAvailable => _engine.isAvailable;

  Future<void> setEnabled(bool value) async {
    if (_disposed) return;
    enabled = value;
    final generation = ++_generation;
    if (!value) {
      await _engine.stop();
      if (!_disposed && generation == _generation) status = WakeWordStatus.disabled;
      return;
    }
    if (!_engine.isAvailable) {
      status = WakeWordStatus.unavailable;
      return;
    }
    try {
      await _engine.start(() async {
        if (_disposed || generation != _generation || !enabled || status != WakeWordStatus.listening) return;
        await _onDetected();
      });
      if (!_disposed && generation == _generation && enabled) status = WakeWordStatus.listening;
    } catch (_) {
      if (!_disposed && generation == _generation) status = WakeWordStatus.error;
    }
  }

  Future<void> pause() async {
    if (_disposed || !enabled || !_engine.isAvailable) return;
    await _engine.pause();
    if (!_disposed && enabled) status = WakeWordStatus.paused;
  }

  Future<void> resume() async {
    if (_disposed || !enabled || !_engine.isAvailable) return;
    final generation = _generation;
    try {
      await _engine.resume();
      if (!_disposed && enabled && generation == _generation) status = WakeWordStatus.listening;
    } catch (_) {
      if (!_disposed && generation == _generation) status = WakeWordStatus.error;
    }
  }

  Future<void> stop() async {
    if (_disposed) return;
    ++_generation;
    await _engine.stop();
    if (!_disposed) status = enabled ? WakeWordStatus.paused : WakeWordStatus.disabled;
  }

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    ++_generation;
    await _engine.dispose();
  }
}
