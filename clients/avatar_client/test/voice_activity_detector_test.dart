import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/avatar/voice/voice_activity_detector.dart';

void main() {
  const config = VoiceActivityConfig(
    amplitudeThresholdDb: -40,
    minimumSpeechDuration: Duration(milliseconds: 300),
    silenceTimeout: Duration(milliseconds: 800),
    maximumRecordingDuration: Duration(seconds: 2),
  );

  test('silence before speech does not end or submit', () {
    final detector = VoiceActivityDetector(config: config);
    expect(detector.process(-60, const Duration(milliseconds: 700)).event, VoiceActivityEvent.none);
    expect(detector.speechDetected, isFalse);
  });

  test('speech starts after minimum duration and ends after silence timeout', () {
    final detector = VoiceActivityDetector(config: config);
    expect(detector.process(-20, const Duration(milliseconds: 100)).event, VoiceActivityEvent.none);
    expect(detector.process(-20, const Duration(milliseconds: 400)).event, VoiceActivityEvent.speechStarted);
    expect(detector.process(-60, const Duration(milliseconds: 900)).event, VoiceActivityEvent.none);
    expect(detector.process(-60, const Duration(milliseconds: 1700)).event, VoiceActivityEvent.speechEnded);
  });

  test('short noise candidate is reset', () {
    final detector = VoiceActivityDetector(config: config);
    detector.process(-20, const Duration(milliseconds: 100));
    detector.process(-60, const Duration(milliseconds: 200));
    expect(detector.process(-20, const Duration(milliseconds: 500)).event, VoiceActivityEvent.none);
    expect(detector.speechDetected, isFalse);
  });

  test('maximum duration forces a stop without inventing speech', () {
    final detector = VoiceActivityDetector(config: config);
    final decision = detector.process(-60, const Duration(seconds: 2));
    expect(decision.event, VoiceActivityEvent.maximumDurationReached);
    expect(decision.speechDetected, isFalse);
  });
}
