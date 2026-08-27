import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/voice/voice_activity_detector.dart';

Uint8List frame(int count, int amplitude) {
  final data = ByteData(count * 2);
  for (var i = 0; i < count; i++)
    data.setInt16(i * 2, amplitude, Endian.little);
  return data.buffer.asUint8List();
}

void main() {
  const config = VoiceActivityDetectorConfig(
    noiseCalibration: Duration.zero,
    startDuration: Duration(milliseconds: 60),
    endSilence: Duration(milliseconds: 80),
    minimumSpeech: Duration(milliseconds: 60),
  );
  test('silence does not activate', () {
    final vad = VoiceActivityDetector(config: config);
    expect(vad.process(frame(16000 ~/ 50, 0)), isEmpty);
    expect(vad.state, VadState.silence);
  });
  test('speech start and end require consecutive frames', () {
    final vad = VoiceActivityDetector(config: config);
    final events = <VadEventType>[];
    for (var i = 0; i < 4; i++)
      events.addAll(vad.process(frame(320, 5000)).map((e) => e.type));
    for (var i = 0; i < 5; i++)
      events.addAll(vad.process(frame(320, 0)).map((e) => e.type));
    expect(events, contains(VadEventType.speechStarted));
    expect(events, contains(VadEventType.speechEnded));
  });
  test('short noise is ignored', () {
    final vad = VoiceActivityDetector(config: config);
    final events = <VadEventType>[];
    for (var i = 0; i < 2; i++)
      events.addAll(vad.process(frame(320, 5000)).map((e) => e.type));
    expect(events, isEmpty);
    expect(vad.state, VadState.silence);
  });
}
