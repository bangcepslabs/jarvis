import 'dart:async';

import 'package:flutter/services.dart';

sealed class WakeWordEvent {
  const WakeWordEvent();
}

class WakeWordDetected extends WakeWordEvent {
  const WakeWordDetected({required this.name, required this.score});
  final String name;
  final double score;
}

class WakeWordError extends WakeWordEvent {
  const WakeWordError(this.message);
  final String message;
}

class WakeWordUnavailable extends WakeWordEvent {
  const WakeWordUnavailable(this.reason);
  final String reason;
}

abstract interface class WakeWordEngine {
  Stream<WakeWordEvent> get events;
  Future<void> start();
  Future<void> stop();
  Future<void> dispose();
}

class OpenWakeWordEngine implements WakeWordEngine {
  OpenWakeWordEngine({this.modelAsset = 'wake_word/development/hey_jarvis.onnx', this.threshold = .5});

  static const _methods = MethodChannel('jarvis/wake_word');
  static const _events = EventChannel('jarvis/wake_word/events');
  final String modelAsset;
  final double threshold;
  Stream<WakeWordEvent>? _eventStream;
  bool _disposed = false;
  bool _initialized = false;

  @override
  Stream<WakeWordEvent> get events => _eventStream ??= _events.receiveBroadcastStream().map(_mapEvent);

  WakeWordEvent _mapEvent(Object? raw) {
    final map = raw is Map ? raw : const <Object?, Object?>{};
    switch (map['type']) {
      case 'detected':
        return WakeWordDetected(name: '${map['name'] ?? 'wake_word'}', score: (map['score'] as num?)?.toDouble() ?? 0);
      case 'unavailable':
        return WakeWordUnavailable('${map['reason'] ?? 'model unavailable'}');
      default:
        return WakeWordError('${map['message'] ?? 'wake word native error'}');
    }
  }

  Future<void> initialize() async {
    _ensureAlive();
    await _methods.invokeMethod<void>('initialize', {'modelAsset': modelAsset, 'threshold': threshold});
  }

  @override
  Future<void> start() async {
    _ensureAlive();
    if (!_initialized) { await initialize(); _initialized = true; }
    await _methods.invokeMethod<void>('start');
  }

  @override
  Future<void> stop() async { if (!_disposed) await _methods.invokeMethod<void>('stop'); }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    await _methods.invokeMethod<void>('dispose');
  }

  void _ensureAlive() { if (_disposed) throw StateError('WakeWordEngine is disposed.'); }
}

class UnavailableWakeWordEngine implements WakeWordEngine {
  UnavailableWakeWordEngine(this.reason);
  final String reason;
  @override
  Stream<WakeWordEvent> get events => Stream<WakeWordEvent>.value(WakeWordUnavailable(reason));
  @override Future<void> start() async {}
  @override Future<void> stop() async {}
  @override Future<void> dispose() async {}
}

class FakeWakeWordEngine implements WakeWordEngine {
  final controller = StreamController<WakeWordEvent>.broadcast();
  int starts = 0;
  int stops = 0;
  bool disposed = false;
  Future<void> Function()? startHook;
  @override Stream<WakeWordEvent> get events => controller.stream;
  @override Future<void> start() async { if (disposed) throw StateError('disposed'); starts++; await startHook?.call(); }
  @override Future<void> stop() async { stops++; }
  @override Future<void> dispose() async { disposed = true; await controller.close(); }
  void emit(WakeWordEvent event) { if (!disposed) controller.add(event); }
}
