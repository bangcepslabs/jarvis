import 'dart:math' as math;
import 'dart:typed_data';

import 'lip_sync_envelope.dart';

class LipSyncConfig {
  const LipSyncConfig({
    this.frameDuration = const Duration(milliseconds: 30),
    this.noiseGateThreshold = 0.02,
    this.referenceLevel = 0.60,
    this.gain = 1.0,
    this.attackFactor = 0.70,
    this.releaseFactor = 0.35,
  }) : assert(noiseGateThreshold >= 0 && noiseGateThreshold <= 1),
       assert(referenceLevel > noiseGateThreshold && referenceLevel <= 1),
       assert(gain > 0),
       assert(attackFactor >= 0 && attackFactor <= 1),
       assert(releaseFactor >= 0 && releaseFactor <= 1);

  final Duration frameDuration;
  final double noiseGateThreshold;
  final double referenceLevel;
  final double gain;
  final double attackFactor;
  final double releaseFactor;
}

class LipSyncFormatException implements Exception {
  const LipSyncFormatException(this.message);
  final String message;
  @override
  String toString() => 'LipSyncFormatException: $message';
}

class _WavData {
  const _WavData({
    required this.channels,
    required this.sampleRate,
    required this.bytes,
  });
  final int channels;
  final int sampleRate;
  final Uint8List bytes;
}

/// Converts standard PCM16 RIFF/WAVE bytes into a smoothed mouth envelope.
/// This class intentionally has no Live2D, Android, or renderer dependency.
class LipSyncAnalyzer {
  const LipSyncAnalyzer({this.config = const LipSyncConfig()});

  final LipSyncConfig config;

  LipSyncEnvelope analyzeWav(Uint8List wavBytes) {
    final wav = _parseWav(wavBytes);
    final bytesPerFrame = wav.channels * 2;
    if (wav.bytes.length < bytesPerFrame) {
      return LipSyncEnvelope(duration: Duration.zero, frames: const []);
    }

    final sampleFrames = wav.bytes.length ~/ bytesPerFrame;
    final frameSize = math.max(
      1,
      (wav.sampleRate *
              config.frameDuration.inMicroseconds /
              Duration.microsecondsPerSecond)
          .round(),
    );
    final values = <double>[];
    var offset = 0;
    while (offset < sampleFrames) {
      final count = math.min(frameSize, sampleFrames - offset);
      var sumSquares = 0.0;
      for (var sampleIndex = 0; sampleIndex < count; sampleIndex++) {
        var mono = 0.0;
        for (var channel = 0; channel < wav.channels; channel++) {
          final byteIndex =
              (offset + sampleIndex) * bytesPerFrame + channel * 2;
          final raw = wav.bytes[byteIndex] | (wav.bytes[byteIndex + 1] << 8);
          final signed = raw >= 0x8000 ? raw - 0x10000 : raw;
          mono += signed / 32768.0;
        }
        mono /= wav.channels;
        sumSquares += mono * mono;
      }
      final rms = math.sqrt(sumSquares / count);
      values.add(_normalize(rms));
      offset += count;
    }

    final duration = Duration(
      microseconds:
          (sampleFrames * Duration.microsecondsPerSecond / wav.sampleRate)
              .round(),
    );
    final frames = <LipSyncFrame>[];
    var current = 0.0;
    for (var index = 0; index < values.length; index++) {
      final target = values[index];
      final factor = target >= current
          ? config.attackFactor
          : config.releaseFactor;
      current = current + (target - current) * factor;
      frames.add(
        LipSyncFrame(
          timestamp: Duration(
            microseconds: index * config.frameDuration.inMicroseconds,
          ),
          mouthOpen: _clamp(current),
        ),
      );
    }
    // Explicit trailing silence makes the close visible during the final
    // release and keeps post-duration lookups silent.
    frames.add(LipSyncFrame(timestamp: duration, mouthOpen: 0));
    return LipSyncEnvelope(duration: duration, frames: frames);
  }

  double _normalize(double rms) {
    if (rms <= config.noiseGateThreshold) return 0;
    final normalized =
        (rms - config.noiseGateThreshold) /
        (config.referenceLevel - config.noiseGateThreshold) *
        config.gain;
    return _clamp(normalized);
  }

  static double _clamp(double value) {
    if (!value.isFinite || value <= 0) return 0;
    if (value >= 1) return 1;
    return value;
  }

  static _WavData _parseWav(Uint8List bytes) {
    if (bytes.length < 12 ||
        _ascii(bytes, 0, 4) != 'RIFF' ||
        _ascii(bytes, 8, 4) != 'WAVE') {
      throw const LipSyncFormatException('Expected a RIFF/WAVE file.');
    }
    int? channels;
    int? sampleRate;
    int? audioFormat;
    int? bitsPerSample;
    int? dataOffset;
    int? dataLength;
    var cursor = 12;
    while (cursor + 8 <= bytes.length) {
      final id = _ascii(bytes, cursor, 4);
      final length = _u32(bytes, cursor + 4);
      final chunkStart = cursor + 8;
      final chunkEnd = chunkStart + length;
      if (chunkEnd > bytes.length) {
        throw const LipSyncFormatException(
          'WAV chunk exceeds the input length.',
        );
      }
      if (id == 'fmt ') {
        if (length < 16) {
          throw const LipSyncFormatException('WAV fmt chunk is too short.');
        }
        audioFormat = _u16(bytes, chunkStart);
        channels = _u16(bytes, chunkStart + 2);
        sampleRate = _u32(bytes, chunkStart + 4);
        bitsPerSample = _u16(bytes, chunkStart + 14);
      } else if (id == 'data') {
        dataOffset = chunkStart;
        dataLength = length;
      }
      cursor = chunkEnd + (length.isOdd ? 1 : 0);
    }
    if (audioFormat != 1 ||
        channels == null ||
        channels < 1 ||
        sampleRate == null ||
        sampleRate <= 0 ||
        bitsPerSample != 16) {
      throw const LipSyncFormatException(
        'Only PCM integer 16-bit WAV is supported.',
      );
    }
    if (dataOffset == null || dataLength == null) {
      throw const LipSyncFormatException('WAV data chunk was not found.');
    }
    final usableLength = dataLength - (dataLength % (channels * 2));
    return _WavData(
      channels: channels,
      sampleRate: sampleRate,
      bytes: Uint8List.sublistView(
        bytes,
        dataOffset,
        dataOffset + usableLength,
      ),
    );
  }

  static int _u16(Uint8List bytes, int offset) =>
      bytes[offset] | (bytes[offset + 1] << 8);
  static int _u32(Uint8List bytes, int offset) =>
      _u16(bytes, offset) | (_u16(bytes, offset + 2) << 16);
  static String _ascii(Uint8List bytes, int offset, int length) =>
      String.fromCharCodes(bytes.sublist(offset, offset + length));
}
