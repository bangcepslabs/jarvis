import 'dart:math' as math;
import 'dart:typed_data';

enum VadState { silence, speech }

enum VadEventType { speechStarted, speeching, speechEnded }

class VadEvent {
  const VadEvent(this.type, {this.rms = 0});
  final VadEventType type;
  final double rms;
}

class VoiceActivityDetectorConfig {
  const VoiceActivityDetectorConfig({
    this.sampleRate = 16000,
    this.frameDuration = const Duration(milliseconds: 20),
    this.noiseCalibration = const Duration(milliseconds: 400),
    this.noiseMargin = 0.025,
    this.speechThreshold = 0.06,
    this.startDuration = const Duration(milliseconds: 240),
    this.endSilence = const Duration(milliseconds: 800),
    this.minimumSpeech = const Duration(milliseconds: 280),
  });

  final int sampleRate;
  final Duration frameDuration;
  final Duration noiseCalibration;
  final double noiseMargin;
  final double speechThreshold;
  final Duration startDuration;
  final Duration endSilence;
  final Duration minimumSpeech;

  int get frameBytes => sampleRate * frameDuration.inMilliseconds ~/ 1000 * 2;
  int get startFrames =>
      math.max(1, startDuration.inMilliseconds ~/ frameDuration.inMilliseconds);
  int get endFrames =>
      math.max(1, endSilence.inMilliseconds ~/ frameDuration.inMilliseconds);
  int get minimumSpeechFrames =>
      math.max(1, minimumSpeech.inMilliseconds ~/ frameDuration.inMilliseconds);
  int get calibrationFrames =>
      noiseCalibration.inMilliseconds ~/ frameDuration.inMilliseconds;
}

/// Small, platform-independent energy VAD for signed 16-bit mono PCM.
class VoiceActivityDetector {
  VoiceActivityDetector({this.config = const VoiceActivityDetectorConfig()});
  final VoiceActivityDetectorConfig config;
  VadState state = VadState.silence;
  final List<int> _pending = [];
  int _calibrationFrames = 0;
  double _noiseFloor = 0;
  int _speechFrames = 0;
  int _silenceFrames = 0;
  int _speechDurationFrames = 0;

  double get noiseFloor => _noiseFloor;
  double get threshold =>
      math.max(config.speechThreshold, _noiseFloor + config.noiseMargin);

  List<VadEvent> process(Uint8List bytes) {
    _pending.addAll(bytes);
    final events = <VadEvent>[];
    while (_pending.length >= config.frameBytes) {
      final frame = Uint8List.fromList(_pending.sublist(0, config.frameBytes));
      _pending.removeRange(0, config.frameBytes);
      events.addAll(_processFrame(frame));
    }
    return events;
  }

  List<VadEvent> _processFrame(Uint8List frame) {
    var sum = 0.0;
    for (var i = 0; i + 1 < frame.length; i += 2) {
      final sample = ByteData.sublistView(frame).getInt16(i, Endian.little);
      sum += sample * sample;
    }
    final rms = math.sqrt(sum / (frame.length ~/ 2)) / 32768.0;
    if (_calibrationFrames < config.calibrationFrames) {
      _noiseFloor =
          (_noiseFloor * _calibrationFrames + rms) / (_calibrationFrames + 1);
      _calibrationFrames++;
    }
    final loud = rms >= threshold;
    if (state == VadState.silence) {
      if (loud) {
        _speechFrames++;
        if (_speechFrames >= config.startFrames) {
          state = VadState.speech;
          _speechDurationFrames = _speechFrames;
          _silenceFrames = 0;
          return [VadEvent(VadEventType.speechStarted, rms: rms)];
        }
      } else {
        _speechFrames = 0;
      }
      return const [];
    }
    _speechDurationFrames++;
    if (loud) {
      _silenceFrames = 0;
      return [VadEvent(VadEventType.speeching, rms: rms)];
    }
    _silenceFrames++;
    if (_silenceFrames >= config.endFrames) {
      final valid = _speechDurationFrames >= config.minimumSpeechFrames;
      state = VadState.silence;
      _speechFrames = 0;
      _silenceFrames = 0;
      _speechDurationFrames = 0;
      return valid ? [VadEvent(VadEventType.speechEnded, rms: rms)] : const [];
    }
    return [VadEvent(VadEventType.speeching, rms: rms)];
  }

  void reset() {
    state = VadState.silence;
    _pending.clear();
    _calibrationFrames = 0;
    _noiseFloor = 0;
    _speechFrames = 0;
    _silenceFrames = 0;
    _speechDurationFrames = 0;
  }
}
