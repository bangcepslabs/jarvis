import 'package:flutter_test/flutter_test.dart';
import 'package:avatar_client/features/voice/wake_word_detector.dart';

void main() {
  test('wake word is disabled by default when no dart defines are supplied', () {
    expect(wakeWordDetectorFromEnvironment(), isNull);
  });

  test('detected events preserve the configured phrase', () {
    const event = WakeWordDetected('자비스');

    expect(event, isA<WakeWordDetected>());
    expect(event.phrase, '자비스');
  });

  test('error events expose a safe user-facing message', () {
    const event = WakeWordError('microphone unavailable');

    expect(event.message, 'microphone unavailable');
  });
}
