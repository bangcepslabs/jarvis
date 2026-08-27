// Client-side wake-word boundary. A concrete engine can be added without
// changing the STT, chat, TTS, or avatar layers.
import 'dart:async';

import 'package:porcupine_flutter/porcupine.dart';
import 'package:porcupine_flutter/porcupine_error.dart';
import 'package:porcupine_flutter/porcupine_manager.dart';

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

/// Porcupine adapter. Custom `.ppn` and `.pv` paths are Flutter asset keys;
/// they are never treated as repository or host filesystem paths.
final class PorcupineWakeWordDetector implements WakeWordDetector {
  PorcupineWakeWordDetector({
    required this.accessKey,
    this.keywordAsset,
    this.modelAsset,
    this.sensitivity = 0.5,
  });

  final String accessKey;
  final String? keywordAsset;
  final String? modelAsset;
  final double sensitivity;
  final StreamController<WakeWordEvent> _events =
      StreamController<WakeWordEvent>.broadcast();
  PorcupineManager? _manager;
  bool _started = false;
  bool _disposed = false;

  @override
  Stream<WakeWordEvent> get events => _events.stream;

  Future<PorcupineManager> _createManager() {
    final keyword = keywordAsset;
    final model = modelAsset;
    if (keyword != null && keyword.isNotEmpty) {
      return PorcupineManager.fromKeywordPaths(
        accessKey,
        [keyword],
        _onDetected,
        modelPath: model?.isNotEmpty == true ? model : null,
        sensitivities: [sensitivity.clamp(0.0, 1.0)],
        errorCallback: _onError,
      );
    }
    return PorcupineManager.fromBuiltInKeywords(
      accessKey,
      [BuiltInKeyword.JARVIS],
      _onDetected,
      modelPath: model?.isNotEmpty == true ? model : null,
      sensitivities: [sensitivity.clamp(0.0, 1.0)],
      errorCallback: _onError,
    );
  }

  @override
  Future<void> start() async {
    if (_disposed || _started) return;
    try {
      _manager ??= await _createManager();
      await _manager!.start();
      _started = true;
    } on PorcupineException catch (error) {
      _onError(error);
      rethrow;
    }
  }

  @override
  Future<void> stop() async {
    if (!_started || _manager == null) return;
    await _manager!.stop();
    _started = false;
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    unawaited(_manager?.delete());
    _manager = null;
    _events.close();
  }

  void _onDetected(int keywordIndex) {
    if (!_disposed) _events.add(const WakeWordDetected('JARVIS'));
  }

  void _onError(PorcupineException error) {
    if (!_disposed) _events.add(WakeWordError(error.message ?? error.toString()));
  }
}

WakeWordDetector? wakeWordDetectorFromEnvironment() {
  const enabled = bool.fromEnvironment('JARVIS_WAKE_WORD_ENABLED');
  const accessKey = String.fromEnvironment('JARVIS_PICOVOICE_ACCESS_KEY');
  if (!enabled || accessKey.isEmpty) return null;
  const keyword = String.fromEnvironment('JARVIS_WAKE_WORD_KEYWORD_ASSET');
  const model = String.fromEnvironment('JARVIS_WAKE_WORD_MODEL_ASSET');
  const sensitivityText = String.fromEnvironment(
    'JARVIS_WAKE_WORD_SENSITIVITY',
    defaultValue: '0.5',
  );
  final sensitivity = double.tryParse(sensitivityText) ?? 0.5;
  return PorcupineWakeWordDetector(
    accessKey: accessKey,
    keywordAsset: keyword.isEmpty ? null : keyword,
    modelAsset: model.isEmpty ? null : model,
    sensitivity: sensitivity,
  );
}
