import 'dart:async';
import 'package:flutter/foundation.dart';

import 'lip_sync_envelope.dart';

/// The small playback contract needed by lip sync.
///
/// A production adapter can forward an audio package's position and complete
/// streams. Tests can provide deterministic positions without an audio device.
abstract interface class LipSyncPlaybackSource {
  Stream<Duration> get positionStream;
  Stream<void> get completionStream;
  Future<void> play(Uint8List audioBytes);
  Future<void> stop();
}

/// Maps the real playback clock to an envelope value.
///
/// This class deliberately does not know about Live2D, Cubism, Android, or
/// AvatarState. Its only published output is a normalized mouth-open value.
class LipSyncPlaybackController {
  LipSyncPlaybackController(this.source) : mouthOpen = ValueNotifier<double>(0);

  final LipSyncPlaybackSource source;
  final ValueNotifier<double> mouthOpen;

  LipSyncEnvelope? _envelope;
  StreamSubscription<Duration>? _positionSubscription;
  StreamSubscription<void>? _completionSubscription;
  bool _active = false;
  bool _disposed = false;
  int _generation = 0;

  bool get isPlaying => _active;

  /// Starts playback and only then begins consuming the playback clock.
  Future<void> play({
    required LipSyncEnvelope envelope,
    required Uint8List audioBytes,
  }) async {
    _ensureNotDisposed();
    final generation = ++_generation;
    await _stopCurrentPlayback();
    _envelope = envelope;
    _active = true;
    _positionSubscription = source.positionStream.listen(
      (position) => _updatePosition(generation, position),
      onError: (_) => _resetIfCurrent(generation),
    );
    _completionSubscription = source.completionStream.listen(
      (_) => _resetIfCurrent(generation),
      onError: (_) => _resetIfCurrent(generation),
    );
    try {
      await source.play(audioBytes);
    } catch (_) {
      _resetIfCurrent(generation);
      rethrow;
    }
  }

  Future<void> stop() async {
    if (_disposed) return;
    ++_generation;
    await _stopCurrentPlayback();
  }

  /// Resets the externally visible value without touching the player.
  void reset() {
    ++_generation;
    _resetCurrent();
  }

  Future<void> _stopCurrentPlayback() async {
    _resetCurrent();
    await source.stop();
  }

  void _resetCurrent() {
    _active = false;
    _envelope = null;
    _positionSubscription?.cancel();
    _completionSubscription?.cancel();
    _positionSubscription = null;
    _completionSubscription = null;
    mouthOpen.value = 0;
  }

  void _resetIfCurrent(int generation) {
    if (generation == _generation) _resetCurrent();
  }

  void _updatePosition(int generation, Duration position) {
    if (generation != _generation || !_active || _envelope == null) return;
    final value = _envelope!.valueAt(position);
    mouthOpen.value = value.isFinite ? value.clamp(0.0, 1.0).toDouble() : 0;
    if (position >= _envelope!.duration) _resetIfCurrent(generation);
  }

  void _ensureNotDisposed() {
    if (_disposed) throw StateError('LipSyncPlaybackController is disposed.');
  }

  void dispose() {
    if (_disposed) return;
    _disposed = true;
    ++_generation;
    _resetCurrent();
    mouthOpen.dispose();
  }
}
