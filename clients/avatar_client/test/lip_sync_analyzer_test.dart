import 'dart:typed_data';

import 'package:avatar_client/features/avatar/lip_sync/lip_sync_analyzer.dart';
import 'package:avatar_client/features/avatar/lip_sync/lip_sync_envelope.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final analyzer = const LipSyncAnalyzer();

  test('silence is gated to zero', () {
    final envelope = analyzer.analyzeWav(_wav(List.filled(4410, 0)));
    expect(envelope.frames.every((frame) => frame.mouthOpen == 0), isTrue);
  });

  test('low amplitude is gated and medium amplitude is stable', () {
    final low = analyzer.analyzeWav(_wav(List.filled(4410, 400)));
    final medium = analyzer.analyzeWav(_wav(List.filled(4410, 12000)));
    expect(low.frames.first.mouthOpen, 0);
    expect(medium.frames[2].mouthOpen, greaterThan(0.2));
    expect(medium.frames[2].mouthOpen, lessThan(1));
  });

  test('high amplitude is clamped to one or below', () {
    final envelope = const LipSyncAnalyzer(
      config: LipSyncConfig(attackFactor: 1),
    ).analyzeWav(_wav(List.filled(4410, 32767)));
    expect(envelope.frames.every((frame) => frame.mouthOpen <= 1), isTrue);
    expect(envelope.frames.any((frame) => frame.mouthOpen == 1), isTrue);
  });

  test('attack smoothing follows an increasing signal', () {
    final samples = <int>[];
    samples.addAll(List.filled(1323, 0));
    samples.addAll(List.filled(1323, 25000));
    final envelope = analyzer.analyzeWav(_wav(samples));
    expect(envelope.valueAt(Duration.zero), 0);
    expect(envelope.valueAt(const Duration(milliseconds: 30)), greaterThan(0));
  });

  test('release smoothing decays instead of dropping immediately', () {
    final samples = <int>[];
    samples.addAll(List.filled(1323, 25000));
    samples.addAll(List.filled(1323, 0));
    final envelope = analyzer.analyzeWav(_wav(samples));
    expect(envelope.valueAt(const Duration(milliseconds: 30)), greaterThan(0));
    expect(envelope.valueAt(const Duration(milliseconds: 40)), greaterThan(0));
  });

  test('valueAt linearly interpolates and silences after duration', () {
    final envelope = LipSyncEnvelope(
      duration: const Duration(milliseconds: 200),
      frames: const [
        LipSyncFrame(timestamp: Duration.zero, mouthOpen: 0.2),
        LipSyncFrame(timestamp: Duration(milliseconds: 100), mouthOpen: 0.8),
      ],
    );
    expect(
      envelope.valueAt(const Duration(milliseconds: 50)),
      closeTo(0.5, 0.001),
    );
    expect(envelope.valueAt(const Duration(milliseconds: 200)), 0);
    expect(envelope.valueAt(const Duration(milliseconds: 300)), 0);
  });

  test('invalid and unsupported WAV files fail clearly', () {
    expect(
      () => analyzer.analyzeWav(Uint8List.fromList([1, 2, 3])),
      throwsA(isA<LipSyncFormatException>()),
    );
    expect(
      () => analyzer.analyzeWav(_wav(List.filled(100, 1), bitsPerSample: 8)),
      throwsA(isA<LipSyncFormatException>()),
    );
  });

  test('stereo input is downmixed to mono', () {
    final samples = <int>[];
    for (var index = 0; index < 4410; index++) {
      samples.add(12000);
      samples.add(-12000);
    }
    final envelope = analyzer.analyzeWav(_wav(samples, channels: 2));
    expect(envelope.frames.every((frame) => frame.mouthOpen == 0), isTrue);
  });
}

Uint8List _wav(
  List<int> samples, {
  int sampleRate = 44100,
  int channels = 1,
  int bitsPerSample = 16,
}) {
  final data = BytesBuilder();
  for (final sample in samples) {
    final value = sample.clamp(-32768, 32767);
    data.addByte(value & 0xff);
    data.addByte((value >> 8) & 0xff);
  }
  final raw = data.takeBytes();
  final bytes = BytesBuilder();
  void ascii(String value) => bytes.add(value.codeUnits);
  void u16(int value) => bytes.add(
    Uint8List(2)..buffer.asByteData().setUint16(0, value, Endian.little),
  );
  void u32(int value) => bytes.add(
    Uint8List(4)..buffer.asByteData().setUint32(0, value, Endian.little),
  );
  ascii('RIFF');
  u32(36 + raw.length);
  ascii('WAVE');
  ascii('fmt ');
  u32(16);
  u16(1);
  u16(channels);
  u32(sampleRate);
  u32(sampleRate * channels * bitsPerSample ~/ 8);
  u16(channels * bitsPerSample ~/ 8);
  u16(bitsPerSample);
  ascii('data');
  u32(raw.length);
  bytes.add(raw);
  return bytes.takeBytes();
}
